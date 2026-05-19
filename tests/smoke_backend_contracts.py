from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from test_atri.main import app  # noqa: E402
from test_atri.logs import LOG_DIR  # noqa: E402
from test_atri import reasoning  # noqa: E402


def assert_equal(actual: object, expected: object, label: str) -> None:
    if actual != expected:
        raise AssertionError(f"{label}: expected {expected!r}, got {actual!r}")


def main() -> None:
    client = TestClient(app)

    health = client.get("/health")
    assert_equal(health.status_code, 200, "health status")
    assert_equal(health.json(), {"status": "ok", "app": "test_atri"}, "health body")

    event_response = client.post(
        "/events/internal",
        json={
            "type": "user.command.submitted",
            "source": "smoke",
            "payload": {"text": "hello"},
        },
    )
    assert_equal(event_response.status_code, 200, "event status")
    event_types = [event["type"] for event in event_response.json()["events"]]
    assert_equal(
        event_types,
        [
            "reasoning.started",
            "pet.state.changed",
            "reasoning.step.completed",
            "reasoning.step.completed",
            "reasoning.step.completed",
            "reasoning.output.produced",
            "pet.bubble.show",
            "pet.state.changed",
        ],
        "command event sequence",
    )
    run_id = event_response.json()["events"][0]["payload"]["run_id"]

    reasoning_status = client.get("/reasoning/status")
    assert_equal(reasoning_status.status_code, 200, "reasoning status")
    assert_equal(reasoning_status.json()["provider"], "deterministic_fallback", "r1 provider")
    assert_equal(reasoning_status.json()["real_model_calls"], False, "r1 real model calls")

    reasoning_detail = client.get(f"/reasoning/runs/{run_id}")
    assert_equal(reasoning_detail.status_code, 200, "reasoning detail")
    assert_equal(reasoning_detail.json()["run"]["run_id"], run_id, "reasoning run id")
    assert_equal(reasoning_detail.json()["schema_failures"], [], "reasoning schema failures")
    assert_equal(len(reasoning_detail.json()["audit"]), 1, "reasoning memory audit count")
    assert_equal(
        reasoning_detail.json()["audit"][0]["status"],
        "candidate_recorded",
        "reasoning memory audit status",
    )

    original_builder = reasoning.build_deterministic_output

    def build_invalid_output(invalid_run_id, invalid_event):
        output = original_builder(invalid_run_id, invalid_event)
        output["schema_version"] = "broken"
        output["reply"] = {"should_reply": True}
        return output

    with patch("test_atri.reasoning.build_deterministic_output", build_invalid_output):
        failure_response = client.post(
            "/events/internal",
            json={
                "type": "user.command.submitted",
                "source": "smoke",
                "payload": {"text": "schema failure probe"},
            },
        )
    assert_equal(failure_response.status_code, 200, "schema failure status")
    failure_events = [event["type"] for event in failure_response.json()["events"]]
    assert_equal(
        failure_events,
        ["reasoning.started", "reasoning.schema.invalid", "reasoning.failed"],
        "schema failure event sequence",
    )
    failure_run_id = failure_response.json()["events"][0]["payload"]["run_id"]
    failure_detail = client.get(f"/reasoning/runs/{failure_run_id}")
    assert_equal(failure_detail.status_code, 200, "schema failure detail")
    assert_equal(failure_detail.json()["run"]["status"], "schema_failed", "schema failure run status")
    assert_equal(len(failure_detail.json()["memory_candidates"]), 0, "schema failure memory writes")
    assert_equal(failure_detail.json()["audit"], [], "schema failure audit writes")
    if len(failure_detail.json()["schema_failures"]) < 1:
        raise AssertionError("schema failure detail did not expose schema_failures")

    provider = client.get("/model/provider/status")
    assert_equal(provider.status_code, 200, "provider status")
    assert_equal(provider.json()["enabled"], False, "provider enabled default")

    permissions = client.get("/permissions/status")
    assert_equal(permissions.status_code, 200, "permissions status")
    assert_equal(permissions.json()["permissions"]["project.read"], False, "project read default")

    logs = client.get("/logs/status")
    assert_equal(logs.status_code, 200, "logs status")
    assert "logs" in logs.json()

    log_probe = LOG_DIR / "redaction-smoke.log"
    mojibake_arrow = bytes([0xE2, 0x9E, 0x9C]).decode("latin1")
    log_probe.write_text(
        "\n".join(
            [
                "Authorization: Bearer sk-secret-value",
                "api_key=deepseek-secret",
                "token=abc123456789",
                "password: hunter2",
                "\x1b",
                f"[32m{mojibake_arrow}",
                "[39m Local",
            ]
        ),
        encoding="utf-8",
    )
    try:
        redacted_logs = client.get("/logs/status").json()["logs"]
    finally:
        log_probe.unlink(missing_ok=True)
    redaction_tail = "\n".join(
        next(log["tail"] for log in redacted_logs if log["name"] == "redaction-smoke.log")
    )
    for secret in ("sk-secret-value", "deepseek-secret", "abc123456789", "hunter2"):
        if secret in redaction_tail:
            raise AssertionError(f"log redaction leaked {secret!r}: {redaction_tail!r}")
    for noise in ("\x1b", "[32m", "[39m"):
        if noise in redaction_tail:
            raise AssertionError(f"log cleanup leaked {noise!r}: {redaction_tail!r}")

    project_reader = client.get("/project-reader/files")
    assert_equal(project_reader.status_code, 403, "project reader default denial")

    memory = client.get("/memory")
    assert_equal(memory.status_code, 200, "memory status")

    created = client.post("/memory", json={"kind": "smoke", "text": "smoke memory item"})
    assert_equal(created.status_code, 200, "memory create status")
    item_id = created.json()["item"]["id"]
    deleted = client.delete(f"/memory/{item_id}")
    assert_equal(deleted.status_code, 200, "memory delete status")
    assert_equal(deleted.json()["deleted"], True, "memory deleted")

    print("backend smoke contracts ok")


if __name__ == "__main__":
    main()
