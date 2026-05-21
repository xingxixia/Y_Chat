from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from y_chat.main import app  # noqa: E402
from y_chat.logs import LOG_DIR  # noqa: E402
from y_chat import reasoning  # noqa: E402


def assert_equal(actual: object, expected: object, label: str) -> None:
    if actual != expected:
        raise AssertionError(f"{label}: expected {expected!r}, got {actual!r}")


def main() -> None:
    client = TestClient(app)

    health = client.get("/health")
    assert_equal(health.status_code, 200, "health status")
    assert_equal(health.json(), {"status": "ok", "app": "y_chat"}, "health body")

    contracts = client.get("/contracts")
    assert_equal(contracts.status_code, 200, "contracts index")
    contracts_payload = contracts.json()
    assert_equal(contracts_payload["schema_version"], "contracts.index.v1", "contracts index schema")
    assert_equal(contracts_payload["read_only"], True, "contracts index read only")
    assert_equal(contracts_payload["mutation_enabled"], False, "contracts index mutation")
    contract_endpoints = [entry["endpoint"] for entry in contracts_payload["entries"]]
    for endpoint in (
        "/reasoning/contract",
        "/memory/contract",
        "/screen/observation/status",
        "/text/status",
        "/audio/status",
        "/project-reader/contract",
        "/permissions/contract",
        "/events/contract",
        "/state/contract",
    ):
        if endpoint not in contract_endpoints:
            raise AssertionError(f"contracts index missing endpoint {endpoint!r}")
    for blocked in ("API key saving", "real model calls", "project file content reads"):
        if blocked not in contracts_payload["blocked_until_explicit_user_selection"]:
            raise AssertionError(f"contracts index missing blocked item {blocked!r}")

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
    source_event_id = event_response.json()["events"][0]["correlation_id"]

    reasoning_status = client.get("/reasoning/status")
    assert_equal(reasoning_status.status_code, 200, "reasoning status")
    assert_equal(reasoning_status.json()["provider"], "deterministic_fallback", "r1 provider")
    assert_equal(reasoning_status.json()["provider_mode"], "deterministic_fallback", "r1 provider mode")
    assert_equal(reasoning_status.json()["real_model_calls"], False, "r1 real model calls")
    if "real model calls are disabled until" not in " ".join(reasoning_status.json()["model_blocked_reasons"]):
        raise AssertionError("reasoning status missing model blocked reason")
    if "vision" not in reasoning_status.json()["supported_input_modalities"]:
        raise AssertionError("reasoning status did not expose multimodal input readiness")
    assert_equal(
        reasoning_status.json()["capture_enabled"]["vision"],
        True,
        "vision capture default",
    )
    assert_equal(
        reasoning_status.json()["capture_enabled"]["screen"],
        True,
        "screen capture evidence path",
    )
    assert_equal(
        reasoning_status.json()["write_paths"]["formal_memory"],
        "disabled",
        "reasoning formal memory write path",
    )

    reasoning_contract = client.get("/reasoning/contract")
    assert_equal(reasoning_contract.status_code, 200, "reasoning contract")
    assert_equal(reasoning_contract.json()["schema_version"], "reasoning.v1", "reasoning contract schema")
    assert_equal(
        reasoning_contract.json()["execution_requires_complete_json"],
        True,
        "reasoning contract complete JSON gate",
    )
    assert_equal(reasoning_contract.json()["repair_attempts"], 1, "reasoning contract repair attempts")
    for blocked in ("final reply bubble", "formal memory writes", "action execution"):
        if blocked not in reasoning_contract.json()["blocked_until_valid"]:
            raise AssertionError(f"reasoning contract missing blocked item {blocked!r}")
    section_names = [section["name"] for section in reasoning_contract.json()["top_level_sections"]]
    for section in ("reply", "actions", "memory", "debug", "audit"):
        if section not in section_names:
            raise AssertionError(f"reasoning contract missing section {section!r}")

    reasoning_detail = client.get(f"/reasoning/runs/{run_id}")
    assert_equal(reasoning_detail.status_code, 200, "reasoning detail")
    assert_equal(reasoning_detail.json()["run"]["run_id"], run_id, "reasoning run id")
    assert_equal(reasoning_detail.json()["run"]["primary_modality"], "text", "reasoning modality")
    assert_equal(reasoning_detail.json()["run"]["modalities"], ["text"], "reasoning modalities")
    assert_equal(len(reasoning_detail.json()["context_snapshots"]), 1, "reasoning context snapshot count")
    assert_equal(
        reasoning_detail.json()["context_snapshots"][0]["payload"]["raw_payload_stored"],
        False,
        "reasoning context raw payload",
    )
    assert_equal(
        [step["step_type"] for step in reasoning_detail.json()["steps"][:3]],
        ["context_check", "provider_running", "schema_validating"],
        "reasoning step sequence",
    )
    assert_equal(reasoning_detail.json()["schema_failures"], [], "reasoning schema failures")
    assert_equal(reasoning_detail.json()["actions"], [], "reasoning action proposals")
    assert_equal(reasoning_detail.json()["pending_actions"], [], "reasoning pending actions")
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

    with patch("y_chat.reasoning.build_deterministic_output", build_invalid_output):
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
        [
            "reasoning.started",
            "reasoning.schema.invalid",
            "reasoning.repair.requested",
            "reasoning.failed",
        ],
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

    def build_repairable_output(repair_run_id, repair_event):
        output = original_builder(repair_run_id, repair_event)
        output.pop("actions")
        output.pop("memory")
        return output

    with patch("y_chat.reasoning.build_deterministic_output", build_repairable_output):
        repair_response = client.post(
            "/events/internal",
            json={
                "type": "user.command.submitted",
                "source": "smoke",
                "payload": {"text": "repairable schema probe"},
            },
        )
    assert_equal(repair_response.status_code, 200, "schema repair status")
    repair_event_types = [event["type"] for event in repair_response.json()["events"]]
    if "reasoning.repair.requested" not in repair_event_types:
        raise AssertionError(f"schema repair event missing: {repair_event_types!r}")
    if "reasoning.failed" in repair_event_types:
        raise AssertionError(f"repairable schema should not fail: {repair_event_types!r}")
    repair_run_id = repair_response.json()["events"][0]["payload"]["run_id"]
    repair_detail = client.get(f"/reasoning/runs/{repair_run_id}")
    assert_equal(repair_detail.status_code, 200, "schema repair detail")
    assert_equal(repair_detail.json()["run"]["status"], "completed", "schema repair run status")
    assert_equal(len(repair_detail.json()["memory_candidates"]), 0, "schema repair memory writes")
    assert_equal(len(repair_detail.json()["actions"]), 0, "schema repair actions")

    def build_action_output(action_run_id, action_event):
        output = original_builder(action_run_id, action_event)
        output["actions"] = [
            {
                "action_id": "smoke-action-probe",
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

    with patch("y_chat.reasoning.build_deterministic_output", build_action_output):
        action_response = client.post(
            "/events/internal",
            json={
                "type": "user.command.submitted",
                "source": "smoke",
                "payload": {"text": "action proposal probe"},
            },
        )
    assert_equal(action_response.status_code, 200, "action proposal status")
    action_event_types = [event["type"] for event in action_response.json()["events"]]
    if "action.proposed" not in action_event_types:
        raise AssertionError(f"action.proposed missing: {action_event_types!r}")
    if "action.pending_authorization" not in action_event_types:
        raise AssertionError(f"action.pending_authorization missing: {action_event_types!r}")
    if "action.executed" in action_event_types:
        raise AssertionError(f"action should not execute in R1: {action_event_types!r}")
    action_run_id = action_response.json()["events"][0]["payload"]["run_id"]
    action_detail = client.get(f"/reasoning/runs/{action_run_id}")
    assert_equal(action_detail.status_code, 200, "action proposal detail")
    assert_equal(len(action_detail.json()["actions"]), 1, "action audit count")
    assert_equal(action_detail.json()["actions"][0]["status"], "pending_authorization", "action status")
    assert_equal(len(action_detail.json()["pending_actions"]), 1, "pending action count")
    assert_equal(
        action_detail.json()["pending_actions"][0]["payload"]["executed"],
        False,
        "pending action execution flag",
    )

    provider = client.get("/model/provider/status")
    assert_equal(provider.status_code, 200, "provider status")
    assert_equal(provider.json()["enabled"], False, "provider enabled default")

    provider_config = client.get("/model/provider/config")
    assert_equal(provider_config.status_code, 200, "provider config")
    assert_equal(provider_config.json()["read_only"], False, "provider config editable")
    assert_equal(provider_config.json()["real_model_calls"], False, "provider config real calls")
    assert_equal(
        provider_config.json()["call_route"],
        "openai_compatible_chat_completions",
        "provider call route",
    )
    if "permissions.model.call is disabled" not in provider_config.json()["blocked_reasons"]:
        raise AssertionError("provider config missing permission blocked reason")
    if "keep final output gated by complete reasoning.v1 JSON validation" not in provider_config.json()["next_requirements"]:
        raise AssertionError("provider config missing reasoning.v1 requirement")
    if "api_key" in str(provider_config.json()).replace("api_key_configured", "").replace("api_key_masked", ""):
        raise AssertionError("provider config leaked an api_key field")

    provider_validate = client.post(
        "/model/provider/config/validate",
        json={
            "provider": "deepseek",
            "base_url": "https://api.deepseek.com",
            "model": "deepseek-chat",
            "api_key": "deepseek-secret-value",
            "temperature": 0.7,
            "stream": True,
            "enabled_requested": True,
            "secondary_confirmed": False,
        },
    )
    assert_equal(provider_validate.status_code, 200, "provider config validate")
    assert_equal(provider_validate.json()["ok"], True, "provider validate ok")
    assert_equal(provider_validate.json()["saved"], False, "provider validate saved")
    assert_equal(provider_validate.json()["real_model_calls"], False, "provider validate real calls")
    validate_text = str(provider_validate.json())
    if "deepseek-secret-value" in validate_text:
        raise AssertionError("provider validation leaked a clear API key")
    if provider_validate.json()["candidate"]["api_key_masked"] != "dee...alue":
        raise AssertionError("provider validation did not return masked key state")
    provider_save_missing_key = client.post(
        "/model/provider/config/save",
        json={
            "provider": "deepseek",
            "base_url": "https://api.deepseek.com",
            "model": "deepseek-v4-flash",
            "api_key": "",
            "temperature": 0.7,
            "stream": False,
            "enabled_requested": True,
            "secondary_confirmed": False,
        },
    )
    assert_equal(provider_save_missing_key.status_code, 200, "provider save missing key")
    assert_equal(provider_save_missing_key.json()["saved"], False, "provider save without key")
    if "api_key is required to save provider config" not in str(provider_save_missing_key.json()):
        raise AssertionError("provider save without key did not explain missing key")
    provider_save_no_confirmation = client.post(
        "/model/provider/config/save",
        json={
            "provider": "deepseek",
            "base_url": "https://api.deepseek.com",
            "model": "deepseek-v4-flash",
            "api_key": "deepseek-secret-value",
            "temperature": 0.7,
            "stream": False,
            "enabled_requested": True,
            "secondary_confirmed": False,
        },
    )
    assert_equal(provider_save_no_confirmation.status_code, 200, "provider save confirmation")
    assert_equal(provider_save_no_confirmation.json()["saved"], False, "provider save without confirmation")
    if "secondary confirmation is required" not in str(provider_save_no_confirmation.json()):
        raise AssertionError("provider save without secondary confirmation did not explain the gate")
    if "deepseek-secret-value" in str(provider_save_no_confirmation.json()):
        raise AssertionError("provider save without confirmation leaked a clear API key")

    provider_validate_bad = client.post(
        "/model/provider/config/validate",
        json={
            "provider": "unknown",
            "base_url": "not-a-url",
            "model": "",
            "api_key": "another-secret",
        },
    )
    assert_equal(provider_validate_bad.status_code, 200, "provider bad config validate")
    assert_equal(provider_validate_bad.json()["ok"], False, "provider bad validate ok")
    if "another-secret" in str(provider_validate_bad.json()):
        raise AssertionError("provider bad validation leaked a clear API key")

    provider_audit = client.get("/model/provider/config/audit")
    assert_equal(provider_audit.status_code, 200, "provider config audit")
    assert len(provider_audit.json()["audits"]) >= 2
    if "deepseek-secret-value" in str(provider_audit.json()) or "another-secret" in str(provider_audit.json()):
        raise AssertionError("provider config audit leaked a clear API key")

    provider_readiness = client.get("/model/provider/readiness")
    assert_equal(provider_readiness.status_code, 200, "provider readiness")
    assert_equal(provider_readiness.json()["dry_run_only"], True, "provider readiness dry run")
    assert_equal(provider_readiness.json()["api_key_returned"], False, "provider readiness api key")
    assert_equal(
        provider_readiness.json()["call_route"],
        "openai_compatible_chat_completions",
        "provider readiness route",
    )
    provider_test_blocked = client.post(
        "/model/provider/test",
        json={"secondary_confirmed": False},
    )
    assert_equal(provider_test_blocked.status_code, 200, "provider test blocked")
    assert_equal(provider_test_blocked.json()["called"], False, "provider test no confirmation")
    if provider_test_blocked.json()["api_key_returned"] is not False:
        raise AssertionError("provider test returned API key state incorrectly")

    permissions = client.get("/permissions/status")
    assert_equal(permissions.status_code, 200, "permissions status")
    assert_equal(permissions.json()["permissions"]["project.read"], False, "project read default")
    assert_equal(permissions.json()["contract_endpoint"], "/permissions/contract", "permission contract endpoint")
    with patch(
        "y_chat.permissions.load_config",
        lambda: {
            "permissions": {
                "model.call": False,
                "memory.write": True,
                "project.read": False,
                "screen.observe": False,
                "voice.listen": False,
                "voice.speak": False,
                "external.http": False,
                "external.websocket": False,
                "external.lan": False,
                "external.osc": False,
                "files.write": False,
                "process.run": False,
                "input.control": False,
                "vr.output": False,
            }
        },
    ):
        permission_contract = client.get("/permissions/contract")
        assert_equal(permission_contract.status_code, 200, "permission contract")
        permission_contract_payload = permission_contract.json()
    assert_equal(permission_contract_payload["schema_version"], "permissions.contract.v1", "permission contract schema")
    assert_equal(permission_contract_payload["read_only"], True, "permission contract read only")
    assert_equal(permission_contract_payload["mutation_enabled"], False, "permission mutation")
    assert_equal(permission_contract_payload["config_write_enabled"], False, "permission config writes")
    assert_equal(permission_contract_payload["sensitive_enabled"], [], "sensitive permissions enabled")
    for blocked in ("real model calls", "project file reading", "screen capture", "process execution"):
        if blocked not in permission_contract_payload["blocked_until_explicit_user_selection"]:
            raise AssertionError(f"permission contract missing blocked item {blocked!r}")

    event_contract = client.get("/events/contract")
    assert_equal(event_contract.status_code, 200, "event contract")
    event_contract_payload = event_contract.json()
    assert_equal(event_contract_payload["schema_version"], "events.contract.v1", "event contract schema")
    assert_equal(event_contract_payload["read_only"], True, "event contract read only")
    if "user.command.submitted" not in event_contract_payload["active_event_types"]:
        raise AssertionError("event contract missing command event")
    assert_equal(
        event_contract_payload["diagnostic_payload_redaction"]["enabled"],
        True,
        "event diagnostic redaction",
    )
    for ingress in event_contract_payload["active_ingress"]:
        assert_equal(ingress["external"], False, f"event ingress external {ingress['route']}")
        assert_equal(ingress["accepts_raw_capture"], False, f"event ingress raw capture {ingress['route']}")
    for blocked in ("external network ingress", "microphone capture events", "screen capture events", "raw audio/video payloads"):
        if blocked not in event_contract_payload["blocked_until_enabled"]:
            raise AssertionError(f"event contract missing blocked item {blocked!r}")

    redacted_event = client.post(
        "/events/internal",
        json={
            "type": "debug.custom",
            "source": "smoke",
            "payload": {
                "message": "Authorization: Bearer FAKE_SECRET_TOKEN_FOR_TEST",
                "image": "data:image/png;base64,abcdef",
                "audio": "data:audio/wav;base64,abcdef",
                "attachment_ref": {"raw_ref": "runtime://memory_blobs/vision/screenshots/frame.jpg"},
            },
        },
    )
    assert_equal(redacted_event.status_code, 200, "event redaction probe")
    redacted_text = str(redacted_event.json())
    for forbidden in ("FAKE_SECRET_TOKEN_FOR_TEST", "data:image", "data:audio"):
        if forbidden in redacted_text:
            raise AssertionError(f"event diagnostic redaction leaked {forbidden!r}")
    assert_equal(
        redacted_event.json()["events"][0]["raw_payload_stored_in_event"],
        False,
        "event diagnostic raw payload flag",
    )

    state_contract = client.get("/state/contract")
    assert_equal(state_contract.status_code, 200, "state contract")
    state_contract_payload = state_contract.json()
    assert_equal(state_contract_payload["schema_version"], "state.contract.v1", "state contract schema")
    assert_equal(state_contract_payload["read_only"], True, "state contract read only")
    assert_equal(state_contract_payload["event_type"], "pet.state.changed", "state contract event")
    implemented_states = [state["name"] for state in state_contract_payload["implemented_states"]]
    for state in ("idle", "thinking", "talking", "dragging"):
        if state not in implemented_states:
            raise AssertionError(f"state contract missing implemented state {state!r}")
    for state in ("reading", "error", "listening", "observing", "speaking"):
        if state not in state_contract_payload["reserved_states"]:
            raise AssertionError(f"state contract missing reserved state {state!r}")
    for blocked in ("simulation meters", "screen observation", "voice speaking output", "VR/OSC output"):
        if blocked not in state_contract_payload["blocked_until_explicit_design"]:
            raise AssertionError(f"state contract missing blocked item {blocked!r}")

    logs = client.get("/logs/status")
    assert_equal(logs.status_code, 200, "logs status")
    assert "logs" in logs.json()
    assert_equal(logs.json()["redaction_enabled"], True, "logs redaction enabled")
    if "authorization headers" not in logs.json()["redaction_patterns"]:
        raise AssertionError("logs status missing authorization header redaction rule")
    if "common UTF-8 mojibake" not in logs.json()["display_cleanup"]:
        raise AssertionError("logs status missing mojibake cleanup rule")

    log_probe = LOG_DIR / "redaction-smoke.log"
    mojibake_arrow = bytes([0xE2, 0x9E, 0x9C]).decode("latin1")
    log_probe.write_text(
        "\n".join(
            [
                "Authorization: Bearer FAKE_SECRET_VALUE_FOR_TEST",
                "api_key=deepseek-secret",
                "token=abc123456789",
                "password: hunter2",
                "\x1b",
                f"[32m{mojibake_arrow}",
                "[39m Local",
                "\x1b[32m\u9253?\x1b[39m  Local",
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
    redaction_entry = next(log for log in redacted_logs if log["name"] == "redaction-smoke.log")
    if redaction_entry["redacted_lines"] < 4:
        raise AssertionError(f"log status did not count redacted lines: {redaction_entry!r}")
    assert_equal(redaction_entry["display_cleaned"], True, "log display cleaned")
    for secret in ("FAKE_SECRET_VALUE_FOR_TEST", "deepseek-secret", "abc123456789", "hunter2"):
        if secret in redaction_tail:
            raise AssertionError(f"log redaction leaked {secret!r}: {redaction_tail!r}")
    for noise in ("\x1b", "[32m", "[39m", "\u9253?"):
        if noise in redaction_tail:
            raise AssertionError(f"log cleanup leaked {noise!r}: {redaction_tail!r}")

    project_reader = client.get("/project-reader/files")
    assert_equal(project_reader.status_code, 403, "project reader default denial")
    project_reader_status = client.get("/project-reader/status")
    assert_equal(project_reader_status.status_code, 200, "project reader status")
    project_reader_payload = project_reader_status.json()
    assert_equal(project_reader_payload["enabled"], False, "project reader enabled")
    assert_equal(project_reader_payload["read_only"], True, "project reader read only")
    assert_equal(project_reader_payload["listing_enabled"], False, "project reader listing")
    assert_equal(
        project_reader_payload["content_reading_enabled"],
        False,
        "project reader content reading",
    )
    assert_equal(
        project_reader_payload["raw_content_return_enabled"],
        False,
        "project reader raw content",
    )
    assert_equal(
        project_reader_payload["recursive_content_scan_enabled"],
        False,
        "project reader recursive scan",
    )
    assert_equal(project_reader_payload["path_escape_blocking"], True, "project reader path escape blocking")
    for reason in ("permissions.project.read is disabled", "project_reader.allowed_roots is empty"):
        if reason not in project_reader_payload["blocked_reasons"]:
            raise AssertionError(f"project reader missing blocked reason {reason!r}")
    for reason in ("file content reading is disabled", "raw content return is disabled", "recursive content scan is disabled"):
        if reason not in project_reader_payload["blocked_reasons"]:
            raise AssertionError(f"project reader missing safety reason {reason!r}")
    project_reader_contract = client.get("/project-reader/contract")
    assert_equal(project_reader_contract.status_code, 200, "project reader contract")
    contract_payload = project_reader_contract.json()
    assert_equal(contract_payload["schema_version"], "project_reader.contract.v1", "project reader contract schema")
    assert_equal(contract_payload["read_only"], True, "project reader contract read only")
    assert_equal(contract_payload["permission_gate"], "permissions.project.read", "project reader permission gate")
    assert_equal(contract_payload["content_reading_enabled"], False, "project reader contract content reading")
    assert_equal(contract_payload["raw_content_return_enabled"], False, "project reader contract raw content")
    assert_equal(contract_payload["recursive_content_scan_enabled"], False, "project reader contract recursive scan")
    assert_equal(contract_payload["path_escape_blocking"], True, "project reader contract path escape")
    for blocked in ("file content reads", "raw content return", "recursive content scans", "path traversal outside an authorized root"):
        if blocked not in contract_payload["blocked_until_enabled"]:
            raise AssertionError(f"project reader contract missing blocked item {blocked!r}")

    memory = client.get("/memory")
    assert_equal(memory.status_code, 200, "memory status")
    formal_memory = client.get("/memory/status")
    assert_equal(formal_memory.status_code, 200, "formal memory status")
    assert_equal(formal_memory.json()["formal_tables_ready"], True, "formal memory tables")
    assert_equal(formal_memory.json()["multimodal_tables_ready"], True, "multimodal memory tables")
    assert_equal(formal_memory.json()["visual_evidence_tables_ready"], True, "visual evidence tables")
    assert_equal(formal_memory.json()["text_evidence_tables_ready"], True, "text evidence tables")
    assert_equal(formal_memory.json()["audio_evidence_tables_ready"], True, "audio evidence tables")
    assert_equal(formal_memory.json()["consolidation_buffer_ready"], True, "consolidation buffer table")
    assert_equal(formal_memory.json()["automatic_writes_enabled"], False, "formal memory auto writes")
    assert_equal(formal_memory.json()["capture_enabled"]["vision"], False, "memory vision capture")
    memory_contract = client.get("/memory/contract")
    assert_equal(memory_contract.status_code, 200, "memory contract")
    assert_equal(memory_contract.json()["unified_memory"], True, "memory unified contract")
    assert_equal(memory_contract.json()["scene_isolation_allowed"], False, "memory scene isolation")
    assert_equal(memory_contract.json()["text_only_identity_allowed"], False, "memory text-only identity")
    assert_equal(memory_contract.json()["automatic_writes_enabled"], False, "memory contract auto writes")
    modality_names = [item["modality"] for item in memory_contract.json()["modalities"]]
    for modality in ("text", "vision", "audio", "event_state_project"):
        if modality not in modality_names:
            raise AssertionError(f"memory contract missing modality {modality!r}")
    vision_contract = next(item for item in memory_contract.json()["modalities"] if item["modality"] == "vision")
    assert_equal(vision_contract["text_is_auxiliary"], True, "vision text auxiliary")
    if "image embedding" not in vision_contract["required_feature_refs"]:
        raise AssertionError("vision contract missing image embedding feature")
    memory_records = client.get("/memory/records")
    assert_equal(memory_records.status_code, 200, "formal memory records")
    assert_equal(memory_records.json()["automatic_writes_enabled"], False, "formal memory records auto writes")
    memory_review = client.get("/memory/review")
    assert_equal(memory_review.status_code, 200, "memory review")
    assert_equal(memory_review.json()["automatic_writes_enabled"], False, "memory review auto writes")
    if not isinstance(memory_review.json()["review_queue"], list):
        raise AssertionError("memory review queue is not a list")
    memory_audit = client.get("/memory/audit")
    assert_equal(memory_audit.status_code, 200, "memory audit")
    assert_equal(memory_audit.json()["automatic_writes_enabled"], False, "memory audit auto writes")
    if not isinstance(memory_audit.json()["audit"], list):
        raise AssertionError("memory audit rows are not a list")
    memory_shell = client.get("/memory/shell")
    assert_equal(memory_shell.status_code, 200, "memory shell")
    assert_equal(memory_shell.json()["automatic_writes_enabled"], False, "memory shell auto writes")
    for key in (
        "observations",
        "entities",
        "features",
        "consolidation_buffer",
        "text_evidence",
        "visual_evidence",
        "audio_evidence",
        "raw_backups",
    ):
        if not isinstance(memory_shell.json()[key], list):
            raise AssertionError(f"memory shell {key} is not a list")
    assert_equal(
        memory_shell.json()["attachment_ref_contract"]["raw_payload_allowed"],
        False,
        "attachment raw payload blocked",
    )
    assert_equal(memory_shell.json()["vision_reader"]["mode"], "metadata_only", "vision reader mode")
    assert_equal(memory_shell.json()["vision_reader"]["enabled"], False, "vision reader disabled")
    assert_equal(memory_shell.json()["text_reader"]["mode"], "local_text_metadata", "text reader mode")
    assert_equal(memory_shell.json()["audio_reader"]["mode"], "metadata_only", "audio reader mode")
    if not any(row.get("source_event_id") == source_event_id for row in memory_shell.json()["text_evidence"]):
        raise AssertionError("command text did not create text evidence")

    consolidation = client.get("/memory/consolidation-buffer")
    assert_equal(consolidation.status_code, 200, "memory consolidation buffer")
    assert_equal(consolidation.json()["automatic_writes_enabled"], False, "consolidation auto writes")
    assert_equal(consolidation.json()["sleep_consolidation_enabled"], False, "sleep consolidation disabled")
    assert_equal(consolidation.json()["schema_ready"], True, "consolidation schema")
    if not isinstance(consolidation.json()["buffer"], list):
        raise AssertionError("consolidation rows are not a list")

    vision_status = client.get("/vision/status")
    assert_equal(vision_status.status_code, 200, "vision status")
    assert_equal(vision_status.json()["enabled"], False, "vision status enabled")
    assert_equal(vision_status.json()["mode"], "metadata_only", "vision status mode")
    assert_equal(vision_status.json()["capture_enabled"], False, "vision capture disabled")
    assert_equal(vision_status.json()["model_download_enabled"], False, "vision model download disabled")
    assert_equal(
        vision_status.json()["attachment_ref_contract"]["raw_payload_allowed"],
        False,
        "vision attachment raw payload blocked",
    )
    vision_extract_status = client.get("/vision/extraction/status")
    assert_equal(vision_extract_status.status_code, 200, "vision extraction status")
    assert_equal(vision_extract_status.json()["api_key_returned"], False, "vision extraction key redaction")
    vision_extract_blocked = client.post("/vision/extract", json={"secondary_confirmed": False})
    assert_equal(vision_extract_blocked.status_code, 200, "vision extract blocked")
    assert_equal(vision_extract_blocked.json()["called"], False, "vision extract no confirmation")

    text_status = client.get("/text/status")
    assert_equal(text_status.status_code, 200, "text status")
    assert_equal(text_status.json()["enabled"], True, "text status enabled")
    assert_equal(text_status.json()["mode"], "local_text_metadata", "text status mode")
    audio_status = client.get("/audio/status")
    assert_equal(audio_status.status_code, 200, "audio status")
    assert_equal(audio_status.json()["enabled"], False, "audio status enabled")
    assert_equal(audio_status.json()["capture_enabled"], False, "audio capture disabled")
    assert_equal(audio_status.json()["microphone_enabled"], False, "microphone disabled")

    screen_status = client.get("/screen/observation/status")
    assert_equal(screen_status.status_code, 200, "screen observation status")
    assert_equal(screen_status.json()["schema_version"], "screen_observation.status.v1", "screen status schema")
    assert_equal(screen_status.json()["active"], False, "screen observation active")
    assert_equal(screen_status.json()["permission"], "screen.observe", "screen observation permission")
    assert_equal(screen_status.json()["requires_secondary_confirmation"], True, "screen secondary confirmation")
    assert_equal(screen_status.json()["interval_seconds"], 3, "screen sampling interval")
    assert_equal(screen_status.json()["adaptive_interval_seconds"], 3, "screen adaptive interval")
    assert_equal(screen_status.json()["max_interval_seconds"], 5, "screen max adaptive interval")
    assert_equal(screen_status.json()["adaptive_pressure_mode"], False, "screen adaptive pressure")
    assert_equal(screen_status.json()["samples_skipped"], 0, "screen skipped samples")
    assert_equal(screen_status.json()["last_skip_reason"], None, "screen last skip reason")
    assert_equal(screen_status.json()["raw_payload_in_events"], False, "screen raw payload events")
    screen_contract = client.get("/screen/observation/contract")
    assert_equal(screen_contract.status_code, 200, "screen observation contract")
    assert_equal(screen_contract.json()["sampling_cadence"], "adaptive_fixed_tick", "screen sampling cadence")
    assert_equal(
        screen_contract.json()["overrun_policy"],
        "average_duration_pressure_adjusts_interval",
        "screen overrun policy",
    )
    assert_equal(screen_contract.json()["event_payload_policy"], "refs_and_metadata_only", "screen event payload policy")
    screen_start = client.post(
        "/screen/observation/start",
        json={"secondary_confirmed": False, "retain_raw": True},
    )
    assert_equal(screen_start.status_code, 200, "screen start gate")
    assert_equal(screen_start.json()["start_allowed"], False, "screen start requires confirmation")

    screen_frame = client.post(
        "/memory/visual-evidence",
        json={
            "source": "screen_frame",
            "raw_ref": "runtime://memory_blobs/vision/screenshots/smoke.jpg",
            "sha256": "abc123",
            "source_event_id": "smoke-screen-frame",
            "mime": "image/jpeg",
            "width": 640,
            "height": 360,
            "size_bytes": 1234,
            "thumbnail_max_width": 640,
            "raw_available": True,
            "vision_reader_status": "metadata_only",
        },
    )
    assert_equal(screen_frame.status_code, 200, "screen frame evidence write")
    assert_equal(screen_frame.json()["item"]["attachment_ref"]["source"], "screen_frame", "screen frame source")
    assert_equal(screen_frame.json()["item"]["raw_payload_returned"], False, "screen frame raw payload response")

    text_evidence = client.post(
        "/memory/text-evidence",
        json={
            "source": "user_command",
            "text": "smoke text evidence",
            "source_event_id": "smoke-text-evidence",
        },
    )
    assert_equal(text_evidence.status_code, 200, "text evidence write")
    assert_equal(text_evidence.json()["item"]["raw_payload_returned"], False, "text evidence raw payload response")
    audio_evidence = client.post(
        "/memory/audio-evidence",
        json={
            "source": "voice_clip",
            "raw_ref": "runtime://memory_blobs/audio/smoke.wav",
            "sha256": "audiohash",
            "mime": "audio/wav",
            "duration_ms": 1200,
            "size_bytes": 2048,
            "raw_available": True,
            "audio_reader_status": "metadata_only",
            "transcript": "smoke transcript",
        },
    )
    assert_equal(audio_evidence.status_code, 200, "audio evidence write")
    assert_equal(audio_evidence.json()["item"]["attachment_ref"]["kind"], "audio", "audio attachment kind")
    assert_equal(audio_evidence.json()["item"]["raw_payload_returned"], False, "audio evidence raw payload response")

    multimodal_reasoning = client.post(
        "/events/internal",
        json={
            "type": "user.command.submitted",
            "source": "smoke",
            "payload": {
                "text": "multimodal context probe",
                "screenshot_ref": "runtime://memory_blobs/vision/screenshots/smoke.jpg",
                "audio_ref": "runtime://memory_blobs/audio/smoke.wav",
                "audio": "data:audio/wav;base64,smoke-raw-audio",
            },
        },
    )
    assert_equal(multimodal_reasoning.status_code, 200, "multimodal reasoning status")
    multimodal_run_id = next(
        event["payload"]["run_id"]
        for event in multimodal_reasoning.json()["events"]
        if event["type"] == "reasoning.started"
    )
    multimodal_detail = client.get(f"/reasoning/runs/{multimodal_run_id}")
    assert_equal(multimodal_detail.status_code, 200, "multimodal reasoning detail")
    multimodal_snapshot = multimodal_detail.json()["context_snapshots"][0]["payload"]
    assert_equal(
        multimodal_snapshot["context_summary"]["current_event_ref_counts"]["vision"],
        1,
        "current vision ref count",
    )
    assert_equal(
        multimodal_snapshot["context_summary"]["current_event_ref_counts"]["audio"],
        1,
        "current audio ref count",
    )
    if multimodal_snapshot["context_summary"]["recent_audio_evidence_count"] < 1:
        raise AssertionError("reasoning snapshot did not include recent audio evidence metadata")
    assert_equal(
        multimodal_snapshot["audio_context"]["raw_audio_bytes_included"],
        False,
        "reasoning audio raw bytes",
    )
    if "smoke-raw-audio" in str(multimodal_snapshot):
        raise AssertionError("reasoning snapshot leaked raw audio payload")

    created = client.post("/memory", json={"kind": "smoke", "text": "smoke memory item"})
    assert_equal(created.status_code, 200, "memory create status")
    item_id = created.json()["item"]["id"]
    deleted = client.delete(f"/memory/{item_id}")
    assert_equal(deleted.status_code, 200, "memory delete status")
    assert_equal(deleted.json()["deleted"], True, "memory deleted")

    print("backend smoke contracts ok")


if __name__ == "__main__":
    main()
