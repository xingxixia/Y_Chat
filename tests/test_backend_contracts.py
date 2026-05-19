from __future__ import annotations

from fastapi.testclient import TestClient

from test_atri.logs import clean_log_line, redact_log_line
from test_atri.main import app
from test_atri import reasoning


client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "app": "test_atri"}


def test_internal_event_command_flow() -> None:
    response = client.post(
        "/events/internal",
        json={
            "type": "user.command.submitted",
            "source": "test",
            "payload": {"text": "hello"},
        },
    )
    assert response.status_code == 200
    event_types = [event["type"] for event in response.json()["events"]]
    assert event_types == [
        "reasoning.started",
        "pet.state.changed",
        "reasoning.step.completed",
        "reasoning.step.completed",
        "reasoning.step.completed",
        "reasoning.output.produced",
        "pet.bubble.show",
        "pet.state.changed",
    ]
    assert response.json()["events"][4]["payload"]["step_type"] == "schema_validating"
    assert "deterministic fallback" in response.json()["events"][6]["payload"]["text"]


def test_model_provider_status_is_disabled_by_default() -> None:
    response = client.get("/model/provider/status")
    assert response.status_code == 200
    assert response.json()["enabled"] is False


def test_project_reader_is_blocked_by_default() -> None:
    response = client.get("/project-reader/files")
    assert response.status_code == 403


def test_reasoning_r1_status_and_run_detail() -> None:
    event_response = client.post(
        "/events/internal",
        json={
            "type": "user.command.submitted",
            "source": "test",
            "payload": {"text": "reasoning detail"},
        },
    )
    assert event_response.status_code == 200
    run_id = event_response.json()["events"][0]["payload"]["run_id"]

    status = client.get("/reasoning/status")
    assert status.status_code == 200
    assert status.json()["provider"] == "deterministic_fallback"
    assert status.json()["real_model_calls"] is False

    runs = client.get("/reasoning/runs")
    assert runs.status_code == 200
    assert any(run["run_id"] == run_id for run in runs.json()["runs"])

    detail = client.get(f"/reasoning/runs/{run_id}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["run"]["run_id"] == run_id
    assert [step["step_type"] for step in body["steps"][:3]] == [
        "context_check",
        "deterministic_fallback",
        "schema_validating",
    ]
    assert len(body["memory_candidates"]) == 1
    assert body["memory_candidates"][0]["accepted"] == 0
    assert body["schema_failures"] == []
    assert body["actions"] == []
    assert body["pending_actions"] == []
    assert len(body["audit"]) == 1
    assert body["audit"][0]["kind"] == "memory_write"
    assert body["audit"][0]["status"] == "candidate_recorded"
    assert body["audit"][0]["payload"]["accepted"] is False


def test_reasoning_r1_schema_failure_is_auditable(monkeypatch) -> None:
    original_builder = reasoning.build_deterministic_output

    def build_invalid_output(run_id, event):
        output = original_builder(run_id, event)
        output["schema_version"] = "broken"
        output["reply"] = {"should_reply": True}
        return output

    monkeypatch.setattr(reasoning, "build_deterministic_output", build_invalid_output)

    response = client.post(
        "/events/internal",
        json={
            "type": "user.command.submitted",
            "source": "test",
            "payload": {"text": "force schema failure"},
        },
    )

    assert response.status_code == 200
    events = response.json()["events"]
    assert [event["type"] for event in events] == [
        "reasoning.started",
        "reasoning.schema.invalid",
        "reasoning.failed",
    ]

    run_id = events[0]["payload"]["run_id"]
    detail = client.get(f"/reasoning/runs/{run_id}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["run"]["status"] == "schema_failed"
    assert "schema_version" in body["run"]["failure_summary"]
    assert body["steps"][-1]["step_type"] == "schema_validating"
    assert body["steps"][-1]["status"] == "failed"
    assert len(body["schema_failures"]) >= 1
    assert body["memory_candidates"] == []
    assert body["audit"] == []


def test_reasoning_r1_action_proposals_are_pending_and_not_executed(monkeypatch) -> None:
    original_builder = reasoning.build_deterministic_output

    def build_output_with_action(run_id, event):
        output = original_builder(run_id, event)
        output["actions"] = [
            {
                "action_id": "action-probe",
                "capability": "project.read",
                "name": "list_project_files",
                "params": {"root_index": 0},
                "reason": "exercise pending authorization storage",
                "risk": "low",
                "requires_confirmation": False,
                "retryable": False,
            }
        ]
        return output

    monkeypatch.setattr(reasoning, "build_deterministic_output", build_output_with_action)

    response = client.post(
        "/events/internal",
        json={
            "type": "user.command.submitted",
            "source": "test",
            "payload": {"text": "propose project read"},
        },
    )

    assert response.status_code == 200
    events = response.json()["events"]
    assert "action.proposed" in [event["type"] for event in events]
    assert "action.pending_authorization" in [event["type"] for event in events]
    assert "action.executed" not in [event["type"] for event in events]

    run_id = events[0]["payload"]["run_id"]
    detail = client.get(f"/reasoning/runs/{run_id}")
    assert detail.status_code == 200
    body = detail.json()
    assert len(body["actions"]) == 1
    assert body["actions"][0]["status"] == "pending_authorization"
    assert body["actions"][0]["payload"]["executed"] is False
    assert body["actions"][0]["payload"]["policy_reason"] == "permission_disabled"
    assert len(body["pending_actions"]) == 1
    assert body["pending_actions"][0]["status"] == "pending"
    assert body["pending_actions"][0]["payload"]["executed"] is False
    action_audit = [record for record in body["audit"] if record["kind"] == "action"]
    assert len(action_audit) == 1
    assert action_audit[0]["status"] == "pending_authorization"


def test_log_redaction_masks_sensitive_values() -> None:
    line = (
        "Authorization: Bearer sk-secret-value api_key='deepseek-secret' "
        "\"x-api-key\": \"quoted-secret\" token=abc123456789 password: hunter2"
    )

    redacted = redact_log_line(line)

    assert "sk-secret-value" not in redacted
    assert "deepseek-secret" not in redacted
    assert "quoted-secret" not in redacted
    assert "abc123456789" not in redacted
    assert "hunter2" not in redacted
    assert redacted.count("[REDACTED]") >= 5


def test_log_cleanup_removes_bom_ansi_and_common_mojibake() -> None:
    mojibake_arrow = b"\xe2\x9e\x9c".decode("latin1")

    assert clean_log_line("\ufeff\x1b[32m" + mojibake_arrow + "\x1b[39m Local") == "\u279c Local"
    assert clean_log_line("\x1b") == ""
    assert clean_log_line("[32m" + mojibake_arrow) == "\u279c"
    assert clean_log_line("[39m Local") == "Local"
