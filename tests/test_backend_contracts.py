from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from y_chat.config import RUNTIME_DIR
from y_chat.logs import clean_log_line, redact_log_line
from y_chat.main import app
from y_chat.model_provider import provider_config_payload, provider_readiness_payload, run_model_provider_test_call, save_provider_config_candidate
from y_chat import reasoning
from y_chat.events import make_event, sanitize_event_for_debug
from y_chat.provider_client import ProviderCallError, post_chat_completion
from y_chat.services.model_provider_cadence import reset_provider_cadence_state
from y_chat.services.redaction import REDACTED, REDACTED_MULTIMODAL, redact_payload


client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "app": "y_chat"}


def test_contracts_index_is_read_only() -> None:
    response = client.get("/contracts")
    assert response.status_code == 200
    body = response.json()
    assert body["schema_version"] == "contracts.index.v1"
    assert body["read_only"] is True
    assert body["mutation_enabled"] is False
    endpoints = [entry["endpoint"] for entry in body["entries"]]
    assert "/reasoning/contract" in endpoints
    assert "/memory/contract" in endpoints
    assert "/screen/observation/status" in endpoints
    assert "/project-reader/contract" in endpoints
    assert "/permissions/contract" in endpoints
    assert "/events/contract" in endpoints
    assert "/state/contract" in endpoints
    assert "/backend/status" in body["status_endpoints"]
    assert "/data/status" in body["status_endpoints"]
    assert "/vision/config" in body["status_endpoints"]
    assert "API key saving" in body["blocked_until_explicit_user_selection"]
    assert "real model calls" in body["blocked_until_explicit_user_selection"]
    assert "physical camera capture" in body["blocked_until_explicit_user_selection"]
    assert "screen capture" not in body["blocked_until_explicit_user_selection"]


def test_backend_and_data_status_expose_backend_core_without_raw_payloads() -> None:
    backend = client.get("/backend/status")
    assert backend.status_code == 200
    backend_body = backend.json()
    assert backend_body["schema_version"] == "backend.status.v1"
    assert backend_body["status"] == "ok"
    assert backend_body["modules"]["reasoning"]["provider_mode"] in {"deterministic_fallback", "deepseek", "openai_compatible"}
    assert "visual_evidence_count" in backend_body["modules"]["memory"]
    assert backend_body["modules"]["vision"]["extraction"]["schema_version"] == "vision_extraction.status.v1"
    assert backend_body["modules"]["vision"]["reader"]["schema_version"] == "vision_reader.adapters.v1"
    assert backend_body["modules"]["vision"]["reader"]["adapter_boundary"] == "independent_vision_reader"
    assert backend_body["modules"]["vision"]["reader"]["image_generation_supported"] is False
    assert backend_body["modules"]["audio"]["reader"]["schema_version"] == "audio_reader.adapters.v1"
    assert backend_body["modules"]["audio"]["reader"]["adapter_boundary"] == "independent_audio_reader"
    assert backend_body["raw_payload_returned"] is False
    assert backend_body["api_key_returned"] is False

    data = client.get("/data/status")
    assert data.status_code == 200
    data_body = data.json()
    assert data_body["schema_version"] == "data.status.v1"
    assert data_body["runtime_files"]["sqlite"]["exists"] is True
    assert data_body["tables"]["memory"]["memory_visual_evidence"]["exists"] is True
    assert data_body["tables"]["reasoning"]["reasoning_runs"]["exists"] is True
    assert data_body["raw_payload_returned"] is False


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
    assert all(event["raw_payload_stored_in_event"] is False for event in response.json()["events"])


def test_internal_event_response_redacts_diagnostic_payloads() -> None:
    response = client.post(
        "/events/internal",
        json={
            "type": "debug.custom",
            "source": "test",
            "payload": {
                "message": "Authorization: Bearer FAKE_SECRET_TOKEN_FOR_TEST",
                "image": "data:image/png;base64,abcdef",
                "audio": "data:audio/wav;base64,abcdef",
                "attachment_ref": {"raw_ref": "runtime://memory_blobs/vision/screenshots/frame.jpg"},
            },
        },
    )

    assert response.status_code == 200
    body = response.json()
    serialized = str(body)
    assert "FAKE_SECRET_TOKEN_FOR_TEST" not in serialized
    assert "data:image" not in serialized
    assert body["events"][0]["raw_payload_stored_in_event"] is False


def test_model_provider_status_is_disabled_by_default() -> None:
    response = client.get("/model/provider/status")
    assert response.status_code == 200
    assert response.json()["enabled"] is False


def test_model_provider_config_is_read_only_and_masked() -> None:
    response = client.get("/model/provider/config")
    assert response.status_code == 200
    body = response.json()
    assert body["read_only"] is False
    assert body["real_model_calls"] is False
    assert body["effective_enabled"] is False
    assert body["call_route"] == "openai_compatible_chat_completions"
    assert body["real_call_test_endpoint"] == "/model/provider/test"
    assert "providers" in body
    serialized = str(body)
    serialized_without_safe_flags = serialized.replace("api_key_configured", "").replace("api_key_masked", "").replace("api_key_returned", "")
    assert "api_key" not in serialized_without_safe_flags
    assert "deepseek-secret" not in serialized


def test_model_provider_config_validation_is_dry_run_and_audited() -> None:
    response = client.post(
        "/model/provider/config/validate",
        json={
            "provider": "deepseek",
            "base_url": "https://api.deepseek.com",
            "model": "deepseek-chat",
            "api_key": "deepseek-secret-value",
            "temperature": 0.7,
            "stream": True,
            "enabled_requested": True,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["saved"] is False
    assert body["real_model_calls"] is False
    assert body["requires_secondary_confirmation_for_save"] is True
    assert body["candidate"]["api_key_configured"] is True
    assert body["candidate"]["api_key_masked"] == "dee...alue"
    assert "deepseek-secret-value" not in str(body)

    bad_response = client.post(
        "/model/provider/config/validate",
        json={
            "provider": "unknown",
            "base_url": "not-a-url",
            "model": "",
            "api_key": "bad-secret-value",
        },
    )

    assert bad_response.status_code == 200
    bad_body = bad_response.json()
    assert bad_body["ok"] is False
    assert "provider must be deepseek or openai_compatible" in bad_body["errors"]
    assert "base_url must be an http or https URL" in bad_body["errors"]
    assert "model is required" in bad_body["errors"]
    assert "bad-secret-value" not in str(bad_body)

    audit = client.get("/model/provider/config/audit")
    assert audit.status_code == 200
    audit_body = audit.json()
    assert len(audit_body["audits"]) >= 2
    assert "deepseek-secret-value" not in str(audit_body)
    assert "bad-secret-value" not in str(audit_body)
    assert any(item["status"] == "validated" for item in audit_body["audits"])
    assert any(item["status"] == "validation_failed" for item in audit_body["audits"])


def test_model_provider_config_save_updates_local_config_without_leaking_key() -> None:
    saved_configs = []

    def fake_load_config() -> dict:
        return {
            "permissions": {"model.call": False},
            "llm": {
                "enabled": False,
                "active_provider": "deepseek",
                "providers": {
                    "deepseek": {
                        "base_url": "https://api.deepseek.com",
                        "api_key": "",
                        "model": "deepseek-v4-flash",
                        "temperature": 0.7,
                        "stream": False,
                    }
                },
            },
        }

    with (
        patch("y_chat.model_provider.load_config", fake_load_config),
        patch("y_chat.model_provider.save_config", lambda config: saved_configs.append(config)),
    ):
        result = save_provider_config_candidate(
            {
                "provider": "deepseek",
                "base_url": "https://api.deepseek.com",
                "model": "deepseek-v4-flash",
                "api_key": "deepseek-secret-value",
                "temperature": 0.7,
                "stream": False,
                "enabled_requested": True,
                "secondary_confirmed": True,
            }
        )

    assert result["ok"] is True
    assert result["saved"] is True
    assert "deepseek-secret-value" not in str(result)
    assert saved_configs[0]["llm"]["providers"]["deepseek"]["api_key"] == "deepseek-secret-value"
    assert saved_configs[0]["llm"]["enabled"] is True
    assert saved_configs[0]["permissions"]["model.call"] is True


def test_model_provider_save_requires_secondary_confirmation() -> None:
    saved_configs = []

    def fake_load_config() -> dict:
        return {
            "permissions": {"model.call": False},
            "llm": {"enabled": False, "active_provider": "deepseek", "providers": {}},
        }

    with (
        patch("y_chat.model_provider.load_config", fake_load_config),
        patch("y_chat.model_provider.save_config", lambda config: saved_configs.append(config)),
    ):
        result = save_provider_config_candidate(
            {
                "provider": "deepseek",
                "base_url": "https://api.deepseek.com",
                "model": "deepseek-v4-flash",
                "api_key": "deepseek-secret-value",
                "temperature": 0.7,
                "stream": False,
                "enabled_requested": True,
                "secondary_confirmed": False,
            }
        )

    assert result["saved"] is False
    assert "secondary confirmation is required" in result["message"]
    assert "deepseek-secret-value" not in str(result)
    assert saved_configs == []


def test_model_provider_config_save_can_enable_existing_key_without_retyping() -> None:
    saved_configs = []

    def fake_load_config() -> dict:
        return {
            "permissions": {"model.call": False},
            "llm": {
                "enabled": False,
                "active_provider": "deepseek",
                "providers": {
                    "deepseek": {
                        "base_url": "https://api.deepseek.com",
                        "api_key": "deepseek-secret-value",
                        "model": "deepseek-v4-flash",
                        "temperature": 0.7,
                        "stream": False,
                    }
                },
            },
        }

    with (
        patch("y_chat.model_provider.load_config", fake_load_config),
        patch("y_chat.model_provider.save_config", lambda config: saved_configs.append(config)),
    ):
        result = save_provider_config_candidate(
            {
                "provider": "deepseek",
                "base_url": "https://api.deepseek.com",
                "model": "deepseek-v4-flash",
                "api_key": "",
                "temperature": 0.7,
                "stream": False,
                "enabled_requested": True,
                "secondary_confirmed": True,
            }
        )

    assert result["ok"] is True
    assert result["saved"] is True
    assert result["real_model_calls"] is True
    assert saved_configs[0]["llm"]["providers"]["deepseek"]["api_key"] == "deepseek-secret-value"
    assert saved_configs[0]["llm"]["enabled"] is True
    assert saved_configs[0]["permissions"]["model.call"] is True


def test_provider_config_and_readiness_report_real_call_gate() -> None:
    def fake_load_config() -> dict:
        return {
            "permissions": {"model.call": True},
            "llm": {
                "enabled": True,
                "active_provider": "deepseek",
                "providers": {
                    "deepseek": {
                        "base_url": "https://api.deepseek.com",
                        "api_key": "deepseek-secret-value",
                        "model": "deepseek-v4-flash",
                        "temperature": 0.7,
                        "stream": False,
                    }
                },
            },
        }

    with patch("y_chat.model_provider.load_config", fake_load_config):
        config = provider_config_payload()
        readiness = provider_readiness_payload()

    assert config["real_model_calls"] is True
    assert config["effective_enabled"] is True
    assert config["read_only"] is False
    assert config["call_route"] == "openai_compatible_chat_completions"
    assert readiness["ready"] is True
    assert readiness["will_call_model_on_next_reasoning_run"] is True
    assert readiness["dry_run_only"] is True
    assert readiness["api_key_returned"] is False
    assert "deepseek-secret-value" not in str(config)
    assert "deepseek-secret-value" not in str(readiness)
    assert config["cadence"]["policy"]["deepseek_role"] == "text_reasoning_api_only"
    assert config["cadence"]["policy"]["high_frequency_inputs"] == "local_adapters_only"
    assert readiness["cadence"]["scopes"]["reasoning_foreground"]["high_frequency_allowed"] is False


def test_model_provider_cadence_status_endpoint_is_redacted() -> None:
    response = client.get("/model/provider/cadence")
    assert response.status_code == 200
    body = response.json()
    assert body["schema_version"] == "model_provider.cadence_status.v1"
    assert body["policy"]["coalescing_required_before_api"] is True
    assert body["policy"]["provider_receives"] == "sanitized multimodal summaries, refs, and feature descriptions"
    assert "raw_image_bytes" in body["policy"]["provider_must_not_receive"]
    assert body["api_key_returned"] is False
    assert body["raw_payload_returned"] is False
    assert "api_key" not in str(body).replace("api_key_returned", "")


def test_post_chat_completion_uses_cadence_guard() -> None:
    reset_provider_cadence_state()
    calls = []

    class FakeResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def read(self):
            return b'{"choices":[{"message":{"content":"{\\"ok\\":true}"}}]}'

    def fake_urlopen(request, timeout):
        calls.append((request, timeout))
        return FakeResponse()

    config = {
        "provider": "deepseek",
        "base_url": "https://api.deepseek.com",
        "api_key": "deepseek-secret-value",
        "model": "deepseek-v4-flash",
        "temperature": 0.0,
        "timeout_seconds": 5,
        "max_tokens": 128,
        "cadence_scope": "provider_test",
    }

    with patch("y_chat.provider_client.urlopen", fake_urlopen):
        first = post_chat_completion(config, [{"role": "user", "content": "hi"}])
        try:
            post_chat_completion(config, [{"role": "user", "content": "again"}])
            raise AssertionError("second provider call should have been cadence-blocked")
        except ProviderCallError as exc:
            assert exc.error_type == "rate_limited"

    assert first["status_code"] == 200
    assert len(calls) == 1
    cadence = client.get("/model/provider/cadence").json()
    assert cadence["scopes"]["provider_test"]["started_count"] == 1
    assert cadence["scopes"]["provider_test"]["blocked_count"] >= 1
    assert cadence["scopes"]["provider_test"]["allowed_now"] is False
    reset_provider_cadence_state()


def test_model_provider_test_call_requires_confirmation_and_masks_key() -> None:
    blocked = run_model_provider_test_call({"secondary_confirmed": False})
    assert blocked["ok"] is False
    assert blocked["called"] is False
    assert blocked["api_key_returned"] is False

    def fake_load_config() -> dict:
        return {
            "permissions": {"model.call": True},
            "llm": {
                "enabled": True,
                "active_provider": "deepseek",
                "providers": {
                    "deepseek": {
                        "base_url": "https://api.deepseek.com",
                        "api_key": "deepseek-secret-value",
                        "model": "deepseek-v4-flash",
                        "temperature": 0.0,
                        "stream": False,
                    }
                },
            },
        }

    def fake_post_chat_completion(config, messages, *, json_mode=True):
        assert config["api_key"] == "deepseek-secret-value"
        assert json_mode is True
        assert messages[0]["role"] == "system"
        return {
            "payload": {"choices": [{"message": {"content": '{"ok": true}'}}]},
            "elapsed_ms": 12,
            "status_code": 200,
            "url": "https://api.deepseek.com/chat/completions",
            "request_body": {},
        }

    with (
        patch("y_chat.model_provider.load_config", fake_load_config),
        patch("y_chat.model_provider.post_chat_completion", fake_post_chat_completion),
    ):
        result = run_model_provider_test_call({"secondary_confirmed": True})

    assert result["ok"] is True
    assert result["called"] is True
    assert result["json_object"] == {"ok": True}
    assert result["api_key_returned"] is False
    assert "deepseek-secret-value" not in str(result)


def test_vision_config_validate_and_save_are_gated_and_masked() -> None:
    config = client.get("/vision/config")
    assert config.status_code == 200
    assert config.json()["schema_version"] == "vision.config.v1"
    assert config.json()["api_key_returned"] is False

    validation = client.post(
        "/vision/config/validate",
        json={
            "provider": "openai_compatible",
            "base_url": "http://127.0.0.1:11434/v1",
            "model": "llava-test",
            "api_key": "vision-secret-value",
            "enabled_requested": True,
        },
    )
    assert validation.status_code == 200
    validation_body = validation.json()
    assert validation_body["ok"] is True
    assert validation_body["saved"] is False
    assert validation_body["candidate"]["api_key_configured"] is True
    assert validation_body["candidate"]["api_key_masked"] == "vis...alue"
    assert "vision-secret-value" not in str(validation_body)

    blocked = client.post(
        "/vision/config/save",
        json={
            "provider": "openai_compatible",
            "base_url": "http://127.0.0.1:11434/v1",
            "model": "llava-test",
            "api_key": "vision-secret-value",
            "enabled_requested": True,
            "secondary_confirmed": False,
        },
    )
    assert blocked.status_code == 200
    assert blocked.json()["saved"] is False
    assert "secondary confirmation is required" in blocked.json()["message"]
    assert "vision-secret-value" not in str(blocked.json())


def test_project_reader_is_blocked_by_default() -> None:
    status = client.get("/project-reader/status")
    assert status.status_code == 200
    assert status.json()["enabled"] is False
    assert status.json()["read_only"] is True
    assert status.json()["content_reading_enabled"] is False
    assert status.json()["raw_content_return_enabled"] is False
    assert status.json()["recursive_content_scan_enabled"] is False
    assert status.json()["path_escape_blocking"] is True
    assert status.json()["roots"] == []

    contract = client.get("/project-reader/contract")
    assert contract.status_code == 200
    assert contract.json()["schema_version"] == "project_reader.contract.v1"
    assert contract.json()["read_only"] is True
    assert contract.json()["permission_gate"] == "permissions.project.read"
    assert contract.json()["content_reading_enabled"] is False
    assert contract.json()["raw_content_return_enabled"] is False
    assert contract.json()["recursive_content_scan_enabled"] is False
    assert contract.json()["path_escape_blocking"] is True
    assert "path traversal outside an authorized root" in contract.json()["blocked_until_enabled"]

    response = client.get("/project-reader/files")
    assert response.status_code == 403


def test_permission_contract_is_read_only() -> None:
    def fake_load_config() -> dict:
        return {
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
        }

    with patch("y_chat.permissions.load_config", fake_load_config):
        contract = client.get("/permissions/contract")
    assert contract.status_code == 200
    body = contract.json()
    assert body["schema_version"] == "permissions.contract.v1"
    assert body["read_only"] is True
    assert body["mutation_enabled"] is False
    assert body["config_write_enabled"] is False
    assert body["sensitive_enabled"] == []
    assert "real model calls" in body["blocked_until_explicit_user_selection"]
    assert "project file reading" in body["blocked_until_explicit_user_selection"]
    assert "process execution" in body["blocked_until_explicit_user_selection"]


def test_event_contract_blocks_external_and_raw_capture_paths() -> None:
    contract = client.get("/events/contract")
    assert contract.status_code == 200
    body = contract.json()
    assert body["schema_version"] == "events.contract.v1"
    assert body["read_only"] is True
    assert "user.command.submitted" in body["active_event_types"]
    assert "external.http" in body["inactive_adapters"]
    assert all(ingress["external"] is False for ingress in body["active_ingress"])
    assert all(ingress["accepts_raw_capture"] is False for ingress in body["active_ingress"])
    assert "external network ingress" in body["blocked_until_enabled"]
    assert "raw audio/video payloads" in body["blocked_until_enabled"]
    assert body["diagnostic_payload_redaction"]["enabled"] is True
    assert "raw multimodal payload fields" in body["diagnostic_payload_redaction"]["patterns"]
    assert "raw_ref" in body["diagnostic_payload_redaction"]["safe_ref_fields_preserved"]


def test_multimodal_diagnostic_payload_redaction_preserves_refs() -> None:
    payload = {
        "text": "hello api_key=secret-value Authorization: Bearer FAKE_LIVE_TOKEN_FOR_TEST",
        "attachment_ref": {
            "raw_ref": "runtime://memory_blobs/vision/screenshots/frame.jpg",
            "sha256": "abc123",
        },
        "image": "data:image/png;base64,abcdef",
        "audio": "data:audio/wav;base64,abcdef",
        "nested": {"token": "nested-secret", "message": "Bearer nested-token"},
    }

    redacted, changed = redact_payload(payload)

    assert changed is True
    assert "secret-value" not in str(redacted)
    assert "FAKE_LIVE_TOKEN_FOR_TEST" not in str(redacted)
    assert redacted["image"] == REDACTED_MULTIMODAL
    assert redacted["audio"] == REDACTED_MULTIMODAL
    assert redacted["nested"]["token"] == REDACTED
    assert redacted["attachment_ref"]["raw_ref"] == "runtime://memory_blobs/vision/screenshots/frame.jpg"

    event = make_event("vision.debug", "test", payload)
    safe_event = sanitize_event_for_debug(event)
    assert safe_event["payload_redacted"] is True
    assert safe_event["raw_payload_stored_in_event"] is False
    assert "secret-value" not in str(safe_event)
    assert "data:image" not in str(safe_event)


def test_state_contract_exposes_safe_state_scope() -> None:
    contract = client.get("/state/contract")
    assert contract.status_code == 200
    body = contract.json()
    assert body["schema_version"] == "state.contract.v1"
    assert body["read_only"] is True
    assert body["event_type"] == "pet.state.changed"
    implemented = [state["name"] for state in body["implemented_states"]]
    assert "idle" in implemented
    assert "thinking" in implemented
    assert "talking" in implemented
    assert "dragging" in implemented
    assert "reading" in body["reserved_states"]
    assert "observing" in body["reserved_states"]
    assert "simulation meters" in body["blocked_until_explicit_design"]
    assert "screen observation" in body["blocked_until_explicit_design"]
    assert "VR/OSC output" in body["blocked_until_explicit_design"]


def test_memory_formal_tables_are_read_only_shell() -> None:
    status = client.get("/memory/status")
    assert status.status_code == 200
    body = status.json()
    assert body["formal_tables_ready"] is True
    assert body["automatic_writes_enabled"] is False
    assert body["manual_notes_legacy"] is True
    assert body["multimodal_tables_ready"] is True
    assert body["capture_enabled"] == {
        "vision": False,
        "audio": False,
        "screen": False,
        "voice": False,
    }
    assert body["observations_count"] >= 0
    assert body["entities_count"] >= 0
    assert body["features_count"] >= 0
    assert body["links_count"] >= 0
    assert body["review_count"] >= 0
    assert body["consolidation_buffer_count"] >= 0
    assert body["visual_evidence_count"] >= 0
    assert body["text_evidence_count"] >= 0
    assert body["audio_evidence_count"] >= 0
    assert body["raw_backup_count"] >= 0
    assert body["visual_evidence_tables_ready"] is True
    assert body["text_evidence_tables_ready"] is True
    assert body["audio_evidence_tables_ready"] is True
    assert body["consolidation_buffer_ready"] is True

    records = client.get("/memory/records")
    assert records.status_code == 200
    assert records.json()["automatic_writes_enabled"] is False
    assert isinstance(records.json()["records"], list)

    shell = client.get("/memory/shell")
    assert shell.status_code == 200
    shell_body = shell.json()
    assert shell_body["automatic_writes_enabled"] is False
    assert shell_body["capture_enabled"]["vision"] is False
    assert isinstance(shell_body["observations"], list)
    assert isinstance(shell_body["entities"], list)
    assert isinstance(shell_body["features"], list)
    assert isinstance(shell_body["links"], list)
    assert isinstance(shell_body["review_queue"], list)
    assert isinstance(shell_body["consolidation_buffer"], list)
    assert isinstance(shell_body["visual_evidence"], list)
    assert isinstance(shell_body["text_evidence"], list)
    assert isinstance(shell_body["audio_evidence"], list)
    assert isinstance(shell_body["raw_backups"], list)
    assert shell_body["attachment_ref_contract"]["raw_payload_allowed"] is False
    assert "manual_file" in shell_body["attachment_ref_contract"]["supported_sources"]
    assert shell_body["vision_reader"]["enabled"] is False
    assert shell_body["vision_reader"]["mode"] == "metadata_only"
    assert shell_body["text_reader"]["mode"] == "local_text_metadata"
    assert shell_body["audio_reader"]["mode"] == "metadata_only"

    consolidation = client.get("/memory/consolidation-buffer")
    assert consolidation.status_code == 200
    assert consolidation.json()["automatic_writes_enabled"] is False
    assert consolidation.json()["sleep_consolidation_enabled"] is False
    assert consolidation.json()["schema_ready"] is True
    assert isinstance(consolidation.json()["buffer"], list)

    vision = client.get("/vision/status")
    assert vision.status_code == 200
    vision_body = vision.json()
    assert vision_body["enabled"] is False
    assert vision_body["mode"] == "metadata_only"
    assert vision_body["capture_enabled"] is False
    assert vision_body["screen_observation_enabled"] is False
    assert vision_body["model_download_enabled"] is False
    assert vision_body["attachment_ref_contract"]["raw_payload_allowed"] is False
    assert "pending" in vision_body["supported_statuses"]

    vision_reader = client.get("/vision/reader/status")
    assert vision_reader.status_code == 200
    vision_reader_body = vision_reader.json()
    assert vision_reader_body["schema_version"] == "vision_reader.adapters.v1"
    assert vision_reader_body["adapter_boundary"] == "independent_vision_reader"
    assert vision_reader_body["api_swap_ready"] is True
    assert vision_reader_body["deepseek_receives_raw_images"] is False
    assert vision_reader_body["image_generation_supported"] is False
    assert vision_reader_body["active_adapters"]["generation"] == "unsupported"
    assert "audio_reader" in vision_reader_body["independent_from"]
    assert vision_reader_body["adapters"]["local_clip_embedding"]["capability"] == "image_embedding"
    assert vision_reader_body["raw_payload_returned"] is False
    assert vision_reader_body["api_key_returned"] is False

    text = client.get("/text/status")
    assert text.status_code == 200
    assert text.json()["enabled"] is True
    assert text.json()["mode"] == "local_text_metadata"
    assert text.json()["auto_observe_command_text"] is True

    audio = client.get("/audio/status")
    assert audio.status_code == 200
    assert audio.json()["enabled"] is False
    assert audio.json()["mode"] == "metadata_only"
    assert audio.json()["capture_enabled"] is False
    assert audio.json()["microphone_enabled"] is False

    audio_reader = client.get("/audio/reader/status")
    assert audio_reader.status_code == 200
    audio_reader_body = audio_reader.json()
    assert audio_reader_body["schema_version"] == "audio_reader.adapters.v1"
    assert audio_reader_body["adapter_boundary"] == "independent_audio_reader"
    assert audio_reader_body["api_swap_ready"] is True
    assert audio_reader_body["deepseek_receives_raw_audio"] is False
    assert audio_reader_body["active_adapters"]["tts"] == "unsupported"
    assert "vision_reader" in audio_reader_body["independent_from"]
    assert audio_reader_body["adapters"]["local_faster_whisper_asr"]["capability"] == "speech_to_text_auxiliary"
    assert audio_reader_body["raw_payload_returned"] is False
    assert audio_reader_body["api_key_returned"] is False


def test_screen_observation_status_and_start_gate_are_explicit() -> None:
    status = client.get("/screen/observation/status")
    assert status.status_code == 200
    body = status.json()
    assert body["schema_version"] == "screen_observation.status.v1"
    assert body["active"] is False
    assert body["enabled"] is False
    assert body["permission"] == "screen.observe"
    assert body["requires_secondary_confirmation"] is True
    assert body["display"] == "primary"
    assert body["full_frame"] is True
    assert body["interval_seconds"] == 3
    assert body["base_interval_seconds"] == 3
    assert body["max_interval_seconds"] == 5
    assert body["adaptive_interval_seconds"] == 3
    assert body["adaptive_pressure_mode"] is False
    assert body["adaptive_reason"] == "steady"
    assert body["samples_skipped"] == 0
    assert body["last_capture_duration_ms"] is None
    assert body["capture_avg_duration_ms"] is None
    assert body["capture_max_duration_ms"] is None
    assert body["capture_history_count"] == 0
    assert body["last_skip_reason"] is None
    assert body["last_skip_at"] is None
    assert body["raw_payload_in_events"] is False
    assert body["raw_payload_in_provider_prompt"] is False
    assert body["raw_payload_returned_in_debug"] is False

    contract = client.get("/screen/observation/contract")
    assert contract.status_code == 200
    contract_body = contract.json()
    assert contract_body["schema_version"] == "screen_observation.contract.v1"
    assert contract_body["permission"] == "screen.observe"
    assert contract_body["requires_secondary_confirmation"] is True
    assert contract_body["sampling_cadence"] == "adaptive_fixed_tick"
    assert contract_body["overrun_policy"] == "average_duration_pressure_adjusts_interval"
    assert contract_body["adaptive_policy"]["default_interval_seconds"] == 3
    assert contract_body["adaptive_policy"]["max_interval_seconds"] == 5
    assert contract_body["event_payload_policy"] == "refs_and_metadata_only"
    assert contract_body["preview_endpoint"] == "/screen/observation/preview?raw_ref=runtime://..."
    assert contract_body["extraction_queue_policy"]["auto_extract_after_persist"] is True
    assert contract_body["extraction_queue_policy"]["max_pending_frames"] == 1
    assert contract_body["extraction_queue_policy"]["min_extract_interval_ms"] == 2500

    start = client.post(
        "/screen/observation/start",
        json={"secondary_confirmed": False, "retain_raw": True},
    )
    assert start.status_code == 200
    assert start.json()["start_allowed"] is False
    assert "secondary confirmation is required" in start.json()["message"]


def test_screen_observation_preview_is_limited_to_runtime_screenshots() -> None:
    screenshot_dir = RUNTIME_DIR / "memory_blobs" / "vision" / "screenshots"
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    preview_file = screenshot_dir / "contract-preview.jpg"
    preview_file.write_bytes(b"fake-jpeg")

    ok = client.get(
        "/screen/observation/preview",
        params={"raw_ref": "runtime://memory_blobs/vision/screenshots/contract-preview.jpg"},
    )
    assert ok.status_code == 200
    assert ok.content == b"fake-jpeg"

    outside_screenshots = client.get(
        "/screen/observation/preview",
        params={"raw_ref": "runtime://events.jsonl"},
    )
    assert outside_screenshots.status_code == 403

    escaped = client.get(
        "/screen/observation/preview",
        params={"raw_ref": "runtime://../secret.jpg"},
    )
    assert escaped.status_code == 400


def test_visual_evidence_post_creates_metadata_only_screen_frame_refs() -> None:
    response = client.post(
        "/memory/visual-evidence",
        json={
            "source": "screen_frame",
            "raw_ref": "runtime://memory_blobs/vision/screenshots/test-frame.png",
            "sha256": "abc123",
            "source_event_id": "event-screen-frame",
            "mime": "image/jpeg",
            "width": 640,
            "height": 360,
            "size_bytes": 1234,
            "source_display_width": 2560,
            "source_display_height": 1440,
            "thumbnail_max_width": 640,
            "raw_available": True,
            "vision_reader_status": "metadata_only",
        },
    )

    assert response.status_code == 200
    item = response.json()["item"]
    assert item["attachment_ref"]["source"] == "screen_frame"
    assert item["attachment_ref"]["raw_ref"].startswith("runtime://")
    assert item["attachment_ref"]["vision_reader_status"] == "metadata_only"
    assert item["raw_payload_returned"] is False
    assert item["feature_refs"]
    assert item["attachment_ref"]["source_display_width"] == 2560
    assert item["attachment_ref"]["source_display_height"] == 1440
    assert item["attachment_ref"]["thumbnail_max_width"] == 640
    assert item["consolidation_buffer_id"]


def test_visual_evidence_with_resolved_raw_ref_creates_comparable_signature_and_candidate() -> None:
    from PIL import Image

    image_path = Path(RUNTIME_DIR) / "memory_blobs" / "vision" / "screenshots" / "contract-signature.png"
    image_path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (16, 16), (240, 20, 20)).save(image_path)

    response = client.post(
        "/memory/visual-evidence",
        json={
            "source": "screen_frame",
            "raw_ref": "runtime://memory_blobs/vision/screenshots/contract-signature.png",
            "sha256": "signature-image-hash",
            "source_event_id": "event-screen-frame-signature",
            "mime": "image/png",
            "width": 16,
            "height": 16,
            "size_bytes": image_path.stat().st_size,
            "source_display_width": 16,
            "source_display_height": 16,
            "thumbnail_max_width": 16,
            "raw_available": True,
            "vision_reader_status": "metadata_only",
        },
    )

    assert response.status_code == 200
    item = response.json()["item"]
    assert len(item["feature_refs"]) == 2
    assert item["entity_candidate_refs"]

    shell = client.get("/memory/shell").json()
    feature_rows = [row for row in shell["features"] if row["feature_id"] in item["feature_refs"]]
    assert {row["feature_kind"] for row in feature_rows} == {"metadata_only", "visual_signature"}
    candidate_rows = [row for row in shell["entities"] if row["entity_id"] in item["entity_candidate_refs"]]
    assert candidate_rows
    assert candidate_rows[0]["kind"] == "visual_candidate"
    assert candidate_rows[0]["status"] in {"temporary", "candidate"}


def test_vision_extract_requires_gate_before_provider_call() -> None:
    blocked = client.post("/vision/extract", json={"secondary_confirmed": False})
    assert blocked.status_code == 200
    assert blocked.json()["ok"] is False
    assert blocked.json()["called"] is False

    status = client.get("/vision/extraction/status")
    assert status.status_code == 200
    assert status.json()["schema_version"] == "vision_extraction.status.v1"
    assert status.json()["api_key_returned"] is False


def test_vision_extract_writes_vlm_feature_and_auxiliary_ocr_text_refs() -> None:
    from PIL import Image

    image_path = Path(RUNTIME_DIR) / "memory_blobs" / "vision" / "screenshots" / "contract-vlm.png"
    image_path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (18, 18), (20, 120, 240)).save(image_path)

    visual = client.post(
        "/memory/visual-evidence",
        json={
            "source": "screen_frame",
            "raw_ref": "runtime://memory_blobs/vision/screenshots/contract-vlm.png",
            "sha256": "vlm-image-hash",
            "source_event_id": "event-screen-frame-vlm",
            "mime": "image/png",
            "width": 18,
            "height": 18,
            "size_bytes": image_path.stat().st_size,
            "raw_available": True,
            "vision_reader_status": "metadata_only",
        },
    )
    assert visual.status_code == 200
    evidence_id = visual.json()["item"]["evidence_id"]

    provider_payload = {
        "choices": [
            {
                "message": {
                    "content": (
                        '{"description":"A blue screen with text.",'
                        '"visible_text":["HELLO SCREEN"],'
                        '"objects":["screen"],'
                        '"uncertainty":"low"}'
                    )
                }
            }
        ]
    }
    with patch(
        "y_chat.vision_extractor._vision_config",
        return_value={
            "enabled": True,
            "provider": "test-vlm",
            "base_url": "http://vlm.test/v1",
            "model": "test-vision-model",
            "api_key": "secret",
            "temperature": 0,
            "timeout_seconds": 30,
            "max_tokens": 500,
            "stream": False,
        },
    ), patch(
        "y_chat.vision_extractor.post_chat_completion",
        return_value={"payload": provider_payload, "elapsed_ms": 12},
    ):
        extracted = client.post(
            "/vision/extract",
            json={"secondary_confirmed": True, "evidence_id": evidence_id},
        )

    assert extracted.status_code == 200
    body = extracted.json()
    assert body["ok"] is True
    assert body["called"] is True
    assert body["feature_id"] in body["feature_refs"]
    assert body["auxiliary_text_evidence_id"]
    assert body["raw_payload_returned"] is False
    assert body["api_key_returned"] is False

    shell = client.get("/memory/shell").json()
    evidence_rows = [row for row in shell["visual_evidence"] if row["evidence_id"] == evidence_id]
    assert evidence_rows[0]["vision_reader_status"] == "extracted"
    assert body["feature_id"] in evidence_rows[0]["feature_refs"]
    feature_rows = [row for row in shell["features"] if row["feature_id"] == body["feature_id"]]
    assert feature_rows[0]["feature_kind"] == "vlm_extracted_text"
    text_rows = [row for row in shell["text_evidence"] if row["evidence_id"] == body["auxiliary_text_evidence_id"]]
    assert text_rows
    assert text_rows[0]["source"] == "ocr_text"


def test_vision_extract_without_provider_uses_local_ocr_when_available() -> None:
    from PIL import Image

    image_path = Path(RUNTIME_DIR) / "memory_blobs" / "vision" / "screenshots" / "contract-local-ocr.png"
    image_path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (20, 20), (250, 250, 250)).save(image_path)

    visual = client.post(
        "/memory/visual-evidence",
        json={
            "source": "screen_frame",
            "raw_ref": "runtime://memory_blobs/vision/screenshots/contract-local-ocr.png",
            "sha256": "local-ocr-image-hash",
            "source_event_id": "event-screen-frame-local-ocr",
            "mime": "image/png",
            "width": 20,
            "height": 20,
            "size_bytes": image_path.stat().st_size,
            "raw_available": True,
            "vision_reader_status": "metadata_only",
        },
    )
    evidence_id = visual.json()["item"]["evidence_id"]

    with patch("y_chat.vision_extractor._local_vlm_ready", return_value=False), patch(
        "y_chat.vision_extractor._local_ocr_available",
        return_value=True,
    ), patch(
        "y_chat.vision_extractor._extract_with_local_ocr",
        return_value={
            "description": "Local OCR extracted visible text from the image.",
            "visible_text": ["LOCAL OCR TEXT"],
            "objects": [{"kind": "text_region", "text": "LOCAL OCR TEXT", "confidence": 0.9}],
            "uncertainty": "medium",
            "provider": "local_rapidocr",
            "model": "rapidocr_onnxruntime",
        },
    ):
        extracted = client.post(
            "/vision/extract",
            json={"secondary_confirmed": True, "evidence_id": evidence_id},
        )

    assert extracted.status_code == 200
    body = extracted.json()
    assert body["ok"] is True
    assert body["called"] is True
    assert body["provider"] == "local_rapidocr"
    assert body["auxiliary_text_evidence_id"]
    assert body["api_key_returned"] is False
    assert body["raw_payload_returned"] is False


def test_vision_extract_local_ocr_provider_does_not_auto_route_to_local_vlm() -> None:
    from PIL import Image

    image_path = Path(RUNTIME_DIR) / "memory_blobs" / "vision" / "screenshots" / "contract-forced-local-ocr.png"
    image_path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (20, 20), (250, 250, 250)).save(image_path)

    visual = client.post(
        "/memory/visual-evidence",
        json={
            "source": "screen_frame",
            "raw_ref": "runtime://memory_blobs/vision/screenshots/contract-forced-local-ocr.png",
            "sha256": "forced-local-ocr-image-hash",
            "source_event_id": "event-screen-frame-forced-local-ocr",
            "mime": "image/png",
            "width": 20,
            "height": 20,
            "size_bytes": image_path.stat().st_size,
            "raw_available": True,
            "vision_reader_status": "metadata_only",
        },
    )
    evidence_id = visual.json()["item"]["evidence_id"]

    disabled_vision_config = {
        "enabled": False,
        "provider": "",
        "base_url": "",
        "model": "",
        "api_key": "",
        "temperature": 0,
        "timeout_seconds": 30,
        "max_tokens": 500,
        "stream": False,
    }
    with patch("y_chat.vision_extractor._vision_config", return_value=disabled_vision_config), patch(
        "y_chat.vision_extractor._local_vlm_ready",
        return_value=True,
    ), patch(
        "y_chat.vision_extractor.recognize_visual_evidence",
        side_effect=AssertionError("local_ocr extraction must not call the local VLM"),
    ), patch(
        "y_chat.vision_extractor._local_ocr_available",
        return_value=True,
    ), patch(
        "y_chat.vision_extractor._extract_with_local_ocr",
        return_value={
            "description": "Local OCR extracted visible text from the image.",
            "visible_text": ["FORCED LOCAL OCR"],
            "objects": [{"kind": "text_region", "text": "FORCED LOCAL OCR", "confidence": 0.9}],
            "uncertainty": "medium",
            "provider": "local_rapidocr",
            "model": "rapidocr_onnxruntime",
        },
    ):
        extracted = client.post(
            "/vision/extract",
            json={"secondary_confirmed": True, "evidence_id": evidence_id, "provider": "local_ocr"},
        )

    assert extracted.status_code == 200
    body = extracted.json()
    assert body["ok"] is True
    assert body["provider"] == "local_rapidocr"
    assert body["auxiliary_text_evidence_id"]
    assert body["api_key_returned"] is False
    assert body["raw_payload_returned"] is False


def test_vision_extract_without_evidence_id_skips_non_runtime_visual_refs() -> None:
    from PIL import Image

    image_path = Path(RUNTIME_DIR) / "memory_blobs" / "vision" / "screenshots" / "contract-latest-runtime-ocr.png"
    image_path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (20, 20), (250, 250, 250)).save(image_path)

    runtime_visual = client.post(
        "/memory/visual-evidence",
        json={
            "source": "screen_frame",
            "raw_ref": "runtime://memory_blobs/vision/screenshots/contract-latest-runtime-ocr.png",
            "sha256": "latest-runtime-ocr-image-hash",
            "source_event_id": "event-latest-runtime-ocr",
            "mime": "image/png",
            "width": 20,
            "height": 20,
            "size_bytes": image_path.stat().st_size,
            "raw_available": True,
            "vision_reader_status": "metadata_only",
        },
    )
    runtime_evidence_id = runtime_visual.json()["item"]["evidence_id"]

    absolute_visual = client.post(
        "/memory/visual-evidence",
        json={
            "source": "manual_file",
            "raw_ref": "C:\\private\\newer-non-runtime.png",
            "sha256": "newer-non-runtime-image-hash",
            "source_event_id": "event-newer-non-runtime",
            "mime": "image/png",
            "width": 20,
            "height": 20,
            "size_bytes": 20,
            "raw_available": True,
            "vision_reader_status": "metadata_only",
        },
    )
    assert absolute_visual.status_code == 200

    with patch("y_chat.vision_extractor._local_vlm_ready", return_value=True), patch(
        "y_chat.vision_extractor.recognize_visual_evidence",
        side_effect=AssertionError("implicit extraction must not call the local VLM"),
    ), patch(
        "y_chat.vision_extractor._local_ocr_available",
        return_value=True,
    ), patch(
        "y_chat.vision_extractor._extract_with_local_ocr",
        return_value={
            "description": "Local OCR extracted visible text from the image.",
            "visible_text": ["LATEST RUNTIME OCR"],
            "objects": [{"kind": "text_region", "text": "LATEST RUNTIME OCR", "confidence": 0.9}],
            "uncertainty": "medium",
            "provider": "local_rapidocr",
            "model": "rapidocr_onnxruntime",
        },
    ):
        extracted = client.post(
            "/vision/extract",
            json={"secondary_confirmed": True, "provider": "local_ocr"},
        )

    assert extracted.status_code == 200
    body = extracted.json()
    assert body["ok"] is True
    assert body["evidence_id"] == runtime_evidence_id
    assert body["provider"] == "local_rapidocr"
    assert body["api_key_returned"] is False
    assert body["raw_payload_returned"] is False


def test_vision_reader_recognize_reports_not_ready_without_local_vlm() -> None:
    with patch("y_chat.services.local_vision_vlm.local_vlm_ready", return_value=False):
        response = client.post("/vision/reader/recognize", json={"secondary_confirmed": True})
    assert response.status_code == 200
    body = response.json()
    assert body["called"] is False
    assert body["not_ready"] is True
    assert body["provider"] == "local_smolvlm"
    assert body["download_command"].endswith("scripts\\download_local_models.py vision_vlm")
    assert body["image_generation_supported"] is False
    assert body["raw_payload_returned"] is False
    assert body["api_key_returned"] is False


def test_vision_reader_recognize_writes_local_vlm_feature() -> None:
    from PIL import Image

    image_path = Path(RUNTIME_DIR) / "memory_blobs" / "vision" / "screenshots" / "contract-local-vlm.png"
    image_path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (24, 24), (120, 40, 220)).save(image_path)

    visual = client.post(
        "/memory/visual-evidence",
        json={
            "source": "screen_frame",
            "raw_ref": "runtime://memory_blobs/vision/screenshots/contract-local-vlm.png",
            "sha256": "local-vlm-image-hash",
            "source_event_id": "event-screen-frame-local-vlm",
            "mime": "image/png",
            "width": 24,
            "height": 24,
            "size_bytes": image_path.stat().st_size,
            "raw_available": True,
            "vision_reader_status": "metadata_only",
        },
    )
    evidence_id = visual.json()["item"]["evidence_id"]

    with patch("y_chat.services.local_vision_vlm.local_vlm_ready", return_value=True), patch(
        "y_chat.services.local_vision_vlm._recognize_image",
        return_value={
            "description": "A purple square used by the local VLM test.",
            "visible_text": [],
            "objects": [{"kind": "shape", "name": "purple square", "confidence": 0.8}],
            "uncertainty": "low",
            "provider": "local_smolvlm",
            "model": "HuggingFaceTB/SmolVLM-256M-Instruct",
            "raw_image_sent_to_configured_vision_provider": False,
            "raw_image_processed_locally": True,
            "raw_image_sent_to_deepseek": False,
            "image_generation_supported": False,
        },
    ):
        recognized = client.post(
            "/vision/reader/recognize",
            json={"secondary_confirmed": True, "evidence_id": evidence_id},
        )

    assert recognized.status_code == 200
    body = recognized.json()
    assert body["ok"] is True
    assert body["provider"] == "local_smolvlm"
    assert body["image_generation_supported"] is False
    assert body["raw_payload_returned"] is False
    assert body["api_key_returned"] is False

    shell = client.get("/memory/shell").json()
    feature_rows = [row for row in shell["features"] if row["feature_id"] == body["feature_id"]]
    assert feature_rows
    assert feature_rows[0]["feature_kind"] == "vlm_extracted_text"
    summary = __import__("json").loads(feature_rows[0]["summary_json"])
    assert summary["provider"] == "local_smolvlm"
    assert summary["raw_image_processed_locally"] is True
    assert summary["raw_image_sent_to_configured_vision_provider"] is False
    assert summary["raw_image_sent_to_deepseek"] is False
    assert summary["image_generation_supported"] is False


def test_reasoning_context_includes_recent_visual_and_ocr_memory_refs() -> None:
    from PIL import Image

    image_path = Path(RUNTIME_DIR) / "memory_blobs" / "vision" / "screenshots" / "contract-reasoning-vision.png"
    image_path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (22, 22), (40, 200, 120)).save(image_path)

    visual = client.post(
        "/memory/visual-evidence",
        json={
            "source": "screen_frame",
            "raw_ref": "runtime://memory_blobs/vision/screenshots/contract-reasoning-vision.png",
            "sha256": "reasoning-vision-hash",
            "source_event_id": "event-reasoning-vision",
            "mime": "image/png",
            "width": 22,
            "height": 22,
            "size_bytes": image_path.stat().st_size,
            "raw_available": True,
            "vision_reader_status": "metadata_only",
        },
    )
    evidence_id = visual.json()["item"]["evidence_id"]

    with patch("y_chat.vision_extractor._local_vlm_ready", return_value=False), patch(
        "y_chat.vision_extractor._local_ocr_available",
        return_value=True,
    ), patch(
        "y_chat.vision_extractor._extract_with_local_ocr",
        return_value={
            "description": "Local OCR extracted visible text from the image.",
            "visible_text": ["REASONING OCR"],
            "objects": [{"kind": "text_region", "text": "REASONING OCR", "confidence": 0.9}],
            "uncertainty": "medium",
            "provider": "local_rapidocr",
            "model": "rapidocr_onnxruntime",
        },
    ):
        extracted = client.post(
            "/vision/extract",
            json={"secondary_confirmed": True, "evidence_id": evidence_id},
        )
    assert extracted.json()["ok"] is True

    response = client.post(
        "/events/internal",
        json={
            "type": "user.command.submitted",
            "source": "test",
            "payload": {"text": "what is on screen?"},
        },
    )
    assert response.status_code == 200
    run_id = next(event["payload"]["run_id"] for event in response.json()["events"] if event["type"] == "reasoning.started")
    run = client.get(f"/reasoning/runs/{run_id}")
    assert run.status_code == 200
    snapshot = run.json()["context_snapshots"][0]["payload"]
    visual_context = snapshot["visual_context"]
    assert visual_context["raw_image_bytes_included"] is False
    assert visual_context["absolute_local_paths_included"] is False
    assert any(item["evidence_id"] == evidence_id for item in visual_context["recent_visual_evidence"])
    assert any(item["text"] == "REASONING OCR" for item in visual_context["recent_ocr_text"])
    assert snapshot["context_summary"]["recent_visual_evidence_count"] >= 1
    assert snapshot["context_summary"]["recent_ocr_text_count"] >= 1


def test_text_evidence_post_and_command_observation_create_refs() -> None:
    direct = client.post(
        "/memory/text-evidence",
        json={
            "source": "user_command",
            "text": "remember this text observation",
            "source_event_id": "event-text-direct",
        },
    )
    assert direct.status_code == 200
    item = direct.json()["item"]
    assert item["evidence_id"]
    assert item["observation_id"]
    assert item["feature_refs"]
    assert item["raw_payload_returned"] is False
    assert item["text_chars"] == len("remember this text observation")

    command = client.post(
        "/events/internal",
        json={
            "type": "user.command.submitted",
            "source": "test",
            "payload": {"text": "text evidence from command"},
        },
    )
    assert command.status_code == 200
    shell = client.get("/memory/shell")
    assert shell.status_code == 200
    source_event_id = command.json()["events"][0]["correlation_id"]
    assert any(row["source_event_id"] == source_event_id for row in shell.json()["text_evidence"])


def test_audio_evidence_post_is_metadata_only_and_does_not_enable_capture() -> None:
    response = client.post(
        "/memory/audio-evidence",
        json={
            "source": "voice_clip",
            "raw_ref": "runtime://memory_blobs/audio/test.wav",
            "sha256": "audiohash",
            "mime": "audio/wav",
            "duration_ms": 1200,
            "size_bytes": 2048,
            "raw_available": True,
            "audio_reader_status": "metadata_only",
            "transcript": "optional transcript text",
        },
    )

    assert response.status_code == 200
    item = response.json()["item"]
    assert item["attachment_ref"]["kind"] == "audio"
    assert item["attachment_ref"]["source"] == "voice_clip"
    assert item["attachment_ref"]["audio_reader_status"] == "metadata_only"
    assert item["transcript_observation_id"]
    assert item["raw_payload_returned"] is False

    audio = client.get("/audio/status").json()
    assert audio["capture_enabled"] is False
    assert audio["microphone_enabled"] is False


def test_reasoning_context_includes_current_refs_and_recent_audio_evidence() -> None:
    audio = client.post(
        "/memory/audio-evidence",
        json={
            "source": "voice_clip",
            "raw_ref": "runtime://memory_blobs/audio/reasoning-audio.wav",
            "sha256": "reasoning-audio-hash",
            "mime": "audio/wav",
            "duration_ms": 2400,
            "size_bytes": 4096,
            "raw_available": True,
            "audio_reader_status": "metadata_only",
            "transcript": "transcript should stay out of reasoning snapshots",
        },
    )
    assert audio.status_code == 200
    evidence_id = audio.json()["item"]["evidence_id"]

    response = client.post(
        "/events/internal",
        json={
            "type": "user.command.submitted",
            "source": "test",
            "payload": {
                "text": "use this multimodal context",
                "screenshot_ref": "runtime://memory_blobs/vision/screenshots/reasoning-current.png",
                "audio_ref": "runtime://memory_blobs/audio/reasoning-current.wav",
                "audio": "data:audio/wav;base64,raw-audio-should-not-appear",
                "attachment_ref": {
                    "kind": "audio",
                    "raw_ref": "runtime://memory_blobs/audio/reasoning-attachment.wav",
                    "mime": "audio/wav",
                    "duration_ms": 500,
                    "sha256": "attachment-audio-hash",
                },
            },
        },
    )
    assert response.status_code == 200
    run_id = next(event["payload"]["run_id"] for event in response.json()["events"] if event["type"] == "reasoning.started")
    run = client.get(f"/reasoning/runs/{run_id}")
    assert run.status_code == 200
    snapshot = run.json()["context_snapshots"][0]["payload"]

    assert snapshot["input"]["modalities"] == ["text", "vision", "audio"]
    assert snapshot["context_summary"]["current_event_ref_counts"]["vision"] == 1
    assert snapshot["context_summary"]["current_event_ref_counts"]["audio"] == 2
    assert snapshot["context_summary"]["recent_audio_evidence_count"] >= 1
    assert snapshot["audio_context"]["raw_audio_bytes_included"] is False
    assert snapshot["audio_context"]["absolute_local_paths_included"] is False
    assert snapshot["audio_context"]["provider_must_not_claim_unparsed_audio"] is True
    assert any(item["evidence_id"] == evidence_id for item in snapshot["audio_context"]["recent_audio_evidence"])
    assert any(item["raw_text_included"] is False for item in [
        evidence.get("transcript")
        for evidence in snapshot["audio_context"]["recent_audio_evidence"]
        if evidence.get("transcript")
    ])
    assert "raw-audio-should-not-appear" not in str(snapshot)


def test_provider_prompt_carries_multimodal_refs_without_raw_payloads() -> None:
    event = reasoning.EventEnvelope(
        type="user.command.submitted",
        source="test",
        payload={
            "text": "provider multimodal prompt",
            "screenshot_ref": "runtime://memory_blobs/vision/screenshots/prompt.png",
            "audio_ref": "C:\\private\\prompt.wav",
            "audio": "data:audio/wav;base64,raw-prompt-audio",
        },
    )

    request = reasoning.build_reasoning_request("run-provider-multimodal", event)
    prompt = reasoning.build_provider_prompt(request)
    safe_request = reasoning.strip_secrets_from_request(request)

    assert "multimodal_context_summary_json" in prompt
    assert "current_event_refs_json" in prompt
    assert "visual_context_json" in prompt
    assert "audio_context_json" in prompt
    assert "runtime://memory_blobs/vision/screenshots/prompt.png" in prompt
    assert "raw-prompt-audio" not in prompt
    assert "data:audio" not in prompt
    assert "C:\\private\\prompt.wav" not in prompt
    assert "[LOCAL_PATH_REF]" in prompt
    assert safe_request["source_event"]["payload"]["audio"] == REDACTED_MULTIMODAL


def test_provider_prompt_summarizes_multimodal_context_for_real_model() -> None:
    from y_chat.services.reasoning_context import build_reasoning_request

    request = build_reasoning_request(
        "run-provider-multimodal-summary",
        reasoning.EventEnvelope(
            type="user.command.submitted",
            source="test",
            payload={"text": "\u6709\u6ca1\u6709\u591a\u6a21\u6001\u4e0a\u4e0b\u6587\uff1f"},
        ),
        {
            "schema_version": "reasoning_visual_context.v1",
            "recent_visual_evidence": [
                {
                    "evidence_id": "vision-1",
                    "features": [
                        {
                            "feature_kind": "vlm_extracted_text",
                            "description": "A local visual recognition summary.",
                        },
                        {
                            "feature_kind": "image_embedding",
                            "dimensions": 512,
                        },
                    ],
                }
            ],
            "recent_ocr_text": [{"text": "OCR AUX"}],
            "raw_image_bytes_included": False,
            "absolute_local_paths_included": False,
        },
        {
            "schema_version": "reasoning_audio_context.v1",
            "recent_audio_evidence": [
                {
                    "evidence_id": "audio-1",
                    "transcript": {"raw_text_included": False, "text_chars": 8},
                }
            ],
            "raw_audio_bytes_included": False,
            "absolute_local_paths_included": False,
            "provider_must_not_claim_unparsed_audio": True,
        },
    )

    summary = reasoning.multimodal_context_summary(request)
    prompt = reasoning.build_provider_prompt(request)

    assert summary["recent_visual_evidence_count"] == 1
    assert summary["recent_visual_description_count"] == 1
    assert summary["recent_visual_embedding_count"] == 1
    assert summary["recent_ocr_text_count"] == 1
    assert summary["recent_audio_evidence_count"] == 1
    assert summary["recent_audio_transcript_metadata_count"] == 1
    assert "multimodal_context_summary_json" in prompt
    assert "preferred_reply_language: Chinese" in prompt
    assert "reply.text and reply.bubble_text must be Chinese" in prompt
    assert "Answer the user's latest request directly and in the user's language" in prompt
    assert "Do not summarize stale visual memory" in prompt
    assert "raw_audio_should_not_exist" not in prompt


def test_provider_summary_does_not_count_ocr_as_visual_semantic_description() -> None:
    from y_chat.services.reasoning_context import build_reasoning_request

    request = build_reasoning_request(
        "run-provider-ocr-summary",
        reasoning.EventEnvelope(
            type="user.command.submitted",
            source="test",
            payload={"text": "\u4f60\u80fd\u8bc6\u522b\u5c4f\u5e55\u56fe\u50cf\u5417\uff1f"},
        ),
        {
            "schema_version": "reasoning_visual_context.v1",
            "recent_visual_evidence": [
                {
                    "evidence_id": "vision-ocr-only",
                    "features": [
                        {
                            "feature_kind": "vlm_extracted_text",
                            "provider": "local_rapidocr",
                            "model": "rapidocr_onnxruntime",
                            "description": "Local OCR extracted visible text from the image.",
                        }
                    ],
                }
            ],
            "recent_ocr_text": [{"text": "OCR AUX"}],
            "raw_image_bytes_included": False,
            "absolute_local_paths_included": False,
        },
        {
            "schema_version": "reasoning_audio_context.v1",
            "recent_audio_evidence": [],
            "raw_audio_bytes_included": False,
            "absolute_local_paths_included": False,
        },
    )

    summary = reasoning.multimodal_context_summary(request)

    assert summary["recent_visual_description_count"] == 0
    assert summary["recent_ocr_feature_description_count"] == 1


def test_provider_summary_ignores_prompt_echo_visual_description() -> None:
    from y_chat.services.reasoning_context import build_reasoning_request

    request = build_reasoning_request(
        "run-provider-visual-echo-summary",
        reasoning.EventEnvelope(
            type="user.command.submitted",
            source="test",
            payload={"text": "\u4f60\u80fd\u8bc6\u522b\u5c4f\u5e55\u56fe\u50cf\u5417\uff1f"},
        ),
        {
            "schema_version": "reasoning_visual_context.v1",
            "recent_visual_evidence": [
                {
                    "evidence_id": "vision-echo",
                    "features": [
                        {
                            "feature_kind": "vlm_extracted_text",
                            "provider": "local_smolvlm",
                            "model": "HuggingFaceTB/SmolVLM-256M-Instruct",
                            "description": "This is a local image recognition, not image generation.",
                        }
                    ],
                }
            ],
            "recent_ocr_text": [],
            "raw_image_bytes_included": False,
            "absolute_local_paths_included": False,
        },
        {
            "schema_version": "reasoning_audio_context.v1",
            "recent_audio_evidence": [],
            "raw_audio_bytes_included": False,
            "absolute_local_paths_included": False,
        },
    )

    summary = reasoning.multimodal_context_summary(request)

    assert summary["recent_visual_description_count"] == 0


def test_visual_question_enriches_latest_evidence_with_local_vlm_before_reasoning() -> None:
    from PIL import Image

    image_path = Path(RUNTIME_DIR) / "memory_blobs" / "vision" / "screenshots" / "contract-visual-question.png"
    image_path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (28, 28), (30, 140, 220)).save(image_path)

    visual = client.post(
        "/memory/visual-evidence",
        json={
            "source": "screen_frame",
            "raw_ref": "runtime://memory_blobs/vision/screenshots/contract-visual-question.png",
            "sha256": "visual-question-image-hash",
            "source_event_id": "event-screen-frame-visual-question",
            "mime": "image/png",
            "width": 28,
            "height": 28,
            "size_bytes": image_path.stat().st_size,
            "raw_available": True,
            "vision_reader_status": "metadata_only",
        },
    )
    evidence_id = visual.json()["item"]["evidence_id"]

    with patch("y_chat.services.reasoning_visual_enrichment.local_vlm_ready", return_value=True), patch(
        "y_chat.services.reasoning_visual_enrichment.recognize_visual_evidence",
        return_value={
            "ok": True,
            "called": True,
            "evidence_id": evidence_id,
            "provider": "local_smolvlm",
            "model": "HuggingFaceTB/SmolVLM-256M-Instruct",
            "feature_id": "feature-local-vlm",
            "feature_refs": ["feature-local-vlm"],
            "raw_payload_returned": False,
            "api_key_returned": False,
        },
    ) as recognize:
        response = client.post(
            "/events/internal",
            json={
                "type": "user.command.submitted",
                "source": "test",
                "payload": {"text": "\u4f60\u80fd\u8bc6\u522b\u5f53\u524d\u5c4f\u5e55\u56fe\u50cf\u5417\uff1f"},
            },
        )

    assert response.status_code == 200
    recognize.assert_called_once()
    called_payload = recognize.call_args.args[0]
    assert called_payload["provider"] == "local_smolvlm"
    assert called_payload["evidence_id"] == evidence_id
    event_types = [event["type"] for event in response.json()["events"]]
    assert event_types.count("reasoning.step.completed") == 4
    enrichment_events = [
        event
        for event in response.json()["events"]
        if event["type"] == "reasoning.step.completed"
        and event["payload"]["step_type"] == "visual_context_enrichment"
    ]
    assert enrichment_events
    assert enrichment_events[0]["payload"]["called"] is True
    assert enrichment_events[0]["payload"]["provider"] == "local_smolvlm"


def test_visual_question_does_not_treat_stale_evidence_as_current_screen() -> None:
    import sqlite3
    from datetime import datetime, timedelta, timezone

    from PIL import Image
    from y_chat.config import runtime_sqlite_path

    image_path = Path(RUNTIME_DIR) / "memory_blobs" / "vision" / "screenshots" / "contract-stale-visual.png"
    image_path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (30, 30), (200, 80, 40)).save(image_path)

    visual = client.post(
        "/memory/visual-evidence",
        json={
            "source": "screen_frame",
            "raw_ref": "runtime://memory_blobs/vision/screenshots/contract-stale-visual.png",
            "sha256": "stale-visual-image-hash",
            "source_event_id": "event-screen-frame-stale-visual",
            "mime": "image/png",
            "width": 30,
            "height": 30,
            "size_bytes": image_path.stat().st_size,
            "raw_available": True,
            "vision_reader_status": "metadata_only",
        },
    )
    evidence_id = visual.json()["item"]["evidence_id"]
    stale_created_at = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
    with sqlite3.connect(runtime_sqlite_path()) as db:
        db.execute("UPDATE memory_visual_evidence SET created_at = ?", ("2000-01-01T00:00:00+00:00",))
        db.execute(
            "UPDATE memory_visual_evidence SET created_at = ? WHERE evidence_id = ?",
            (stale_created_at, evidence_id),
        )

    with patch("y_chat.services.reasoning_visual_enrichment.local_vlm_ready", return_value=True), patch(
        "y_chat.services.reasoning_visual_enrichment.recognize_visual_evidence"
    ) as recognize:
        response = client.post(
            "/events/internal",
            json={
                "type": "user.command.submitted",
                "source": "test",
                "payload": {"text": "\u4f60\u80fd\u770b\u5230\u4ec0\u4e48\uff1f"},
            },
        )

    assert response.status_code == 200
    recognize.assert_not_called()
    enrichment_events = [
        event
        for event in response.json()["events"]
        if event["type"] == "reasoning.step.completed"
        and event["payload"]["step_type"] == "visual_context_enrichment"
    ]
    assert enrichment_events
    assert enrichment_events[0]["payload"]["status"] == "skipped"

    run_id = next(event["payload"]["run_id"] for event in response.json()["events"] if event["type"] == "reasoning.started")
    detail = client.get(f"/reasoning/runs/{run_id}")
    assert detail.status_code == 200
    snapshot = detail.json()["context_snapshots"][0]["payload"]
    visual_context = snapshot["visual_context"]
    stale_rows = [
        item for item in visual_context["recent_visual_evidence"] if item["evidence_id"] == evidence_id
    ]
    assert stale_rows
    assert stale_rows[0]["fresh_for_current_screen"] is False
    assert stale_rows[0]["stale_for_current_screen"] is True
    assert stale_rows[0]["age_seconds"] > 120
    assert visual_context["current_screen_evidence_available"] is False
    assert snapshot["context_summary"]["current_screen_evidence_available"] is False
    assert snapshot["context_summary"]["stale_visual_evidence_count"] >= 1


def test_visual_question_enriches_current_event_visual_evidence_id_before_latest_memory() -> None:
    from PIL import Image

    first_path = Path(RUNTIME_DIR) / "memory_blobs" / "vision" / "screenshots" / "contract-current-ref-first.png"
    latest_path = Path(RUNTIME_DIR) / "memory_blobs" / "vision" / "screenshots" / "contract-current-ref-latest.png"
    first_path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (24, 24), (10, 180, 90)).save(first_path)
    Image.new("RGB", (24, 24), (220, 80, 80)).save(latest_path)

    first = client.post(
        "/memory/visual-evidence",
        json={
            "source": "screen_frame",
            "raw_ref": "runtime://memory_blobs/vision/screenshots/contract-current-ref-first.png",
            "sha256": "current-ref-first-hash",
            "source_event_id": "event-current-ref-first",
            "mime": "image/png",
            "width": 24,
            "height": 24,
            "size_bytes": first_path.stat().st_size,
            "raw_available": True,
            "vision_reader_status": "metadata_only",
        },
    )
    target_evidence_id = first.json()["item"]["evidence_id"]
    latest = client.post(
        "/memory/visual-evidence",
        json={
            "source": "screen_frame",
            "raw_ref": "runtime://memory_blobs/vision/screenshots/contract-current-ref-latest.png",
            "sha256": "current-ref-latest-hash",
            "source_event_id": "event-current-ref-latest",
            "mime": "image/png",
            "width": 24,
            "height": 24,
            "size_bytes": latest_path.stat().st_size,
            "raw_available": True,
            "vision_reader_status": "metadata_only",
        },
    )
    latest_evidence_id = latest.json()["item"]["evidence_id"]

    with patch("y_chat.services.reasoning_visual_enrichment.local_vlm_ready", return_value=True), patch(
        "y_chat.services.reasoning_visual_enrichment.recognize_visual_evidence",
        return_value={
            "ok": True,
            "called": True,
            "evidence_id": target_evidence_id,
            "provider": "local_smolvlm",
            "model": "HuggingFaceTB/SmolVLM-256M-Instruct",
            "feature_id": "feature-current-ref-vlm",
            "feature_refs": ["feature-current-ref-vlm"],
            "raw_payload_returned": False,
            "api_key_returned": False,
        },
    ) as recognize:
        response = client.post(
            "/events/internal",
            json={
                "type": "user.command.submitted",
                "source": "test",
                "payload": {
                    "text": "\u4f60\u80fd\u8bc6\u522b\u8fd9\u5f20\u5f53\u524d\u622a\u56fe\u5417\uff1f",
                    "visual_evidence_id": target_evidence_id,
                },
            },
        )

    assert response.status_code == 200
    recognize.assert_called_once()
    assert recognize.call_args.args[0]["evidence_id"] == target_evidence_id
    assert recognize.call_args.args[0]["evidence_id"] != latest_evidence_id


def test_reasoning_visual_context_redacts_absolute_local_refs_from_provider_prompt() -> None:
    visual = client.post(
        "/memory/visual-evidence",
        json={
            "source": "manual_file",
            "raw_ref": "C:\\private\\screen.png",
            "sha256": "absolute-ref-hash",
            "mime": "image/png",
            "width": 10,
            "height": 10,
            "size_bytes": 100,
            "raw_available": True,
            "vision_reader_status": "metadata_only",
        },
    )
    assert visual.status_code == 200
    evidence_id = visual.json()["item"]["evidence_id"]
    event = reasoning.EventEnvelope(
        type="user.command.submitted",
        source="test",
        payload={"text": "absolute visual ref prompt"},
    )

    request = reasoning.build_reasoning_request("run-absolute-visual-ref", event)
    prompt = reasoning.build_provider_prompt(request)

    visual_rows = request["context"]["visual_context"]["recent_visual_evidence"]
    assert any(row["evidence_id"] == evidence_id and row["raw_ref"] == "[LOCAL_PATH_REF]" for row in visual_rows)
    assert "C:\\private\\screen.png" not in prompt


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
    assert "vision" in status.json()["supported_input_modalities"]
    assert status.json()["capture_enabled"]["vision"] is True
    assert status.json()["capture_enabled"]["screen"] is True

    runs = client.get("/reasoning/runs")
    assert runs.status_code == 200
    assert any(run["run_id"] == run_id for run in runs.json()["runs"])
    run_summary = next(run for run in runs.json()["runs"] if run["run_id"] == run_id)
    assert run_summary["primary_modality"] == "text"
    assert run_summary["modalities"] == ["text"]

    detail = client.get(f"/reasoning/runs/{run_id}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["run"]["run_id"] == run_id
    assert body["run"]["primary_modality"] == "text"
    assert body["run"]["modalities"] == ["text"]
    assert len(body["context_snapshots"]) == 1
    assert body["context_snapshots"][0]["payload"]["input"]["primary_modality"] == "text"
    assert body["context_snapshots"][0]["payload"]["raw_payload_stored"] is False
    assert body["context_snapshots"][0]["payload"]["source_event"]["payload_keys"] == ["text"]
    assert [step["step_type"] for step in body["steps"][:3]] == [
        "context_check",
        "provider_running",
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
    assert body["memory_candidates"][0]["payload"]["content"]["primary_modality"] == "text"


def test_reasoning_request_tracks_multimodal_input_metadata() -> None:
    event = reasoning.EventEnvelope(
        type="screen.observation.created",
        source="test",
        payload={
            "text": "visible label",
            "screenshot_ref": "runtime://screens/1.png",
            "audio_ref": "runtime://audio/1.wav",
        },
    )

    request = reasoning.build_reasoning_request("run-multimodal", event)

    assert request["input"]["primary_modality"] == "vision"
    assert request["input"]["modalities"] == ["vision", "text", "audio"]
    assert request["context"]["modality_context"]["vision"]["available"] is True
    assert request["context"]["modality_context"]["vision"]["capture_enabled"] is True
    assert request["context"]["modality_context"]["vision"]["current_event_ref_count"] == 1
    assert request["context"]["modality_context"]["audio"]["available"] is True
    assert request["context"]["modality_context"]["audio"]["capture_enabled"] is False
    assert request["context"]["modality_context"]["audio"]["current_event_ref_count"] == 1
    assert request["context"]["current_event_refs"]["vision"][0]["ref"] == "runtime://screens/1.png"
    assert request["context"]["current_event_refs"]["audio"][0]["ref"] == "runtime://audio/1.wav"

    snapshot = reasoning.build_context_snapshot(request)

    assert snapshot["source_event"]["payload_keys"] == ["audio_ref", "screenshot_ref", "text"]
    assert snapshot["context_summary"]["has_current_event_text"] is True
    assert snapshot["context_summary"]["current_event_ref_counts"]["vision"] == 1
    assert snapshot["context_summary"]["current_event_ref_counts"]["audio"] == 1
    assert snapshot["raw_payload_stored"] is False


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
        "reasoning.repair.requested",
        "reasoning.failed",
    ]

    run_id = events[0]["payload"]["run_id"]
    detail = client.get(f"/reasoning/runs/{run_id}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["run"]["status"] == "schema_failed"
    assert "schema_version" in body["run"]["failure_summary"]
    assert len(body["context_snapshots"]) == 1
    assert body["steps"][-2]["step_type"] == "schema_validating"
    assert body["steps"][-2]["status"] == "failed"
    assert body["steps"][-1]["step_type"] == "schema_repair"
    assert body["steps"][-1]["status"] == "failed"
    assert len(body["schema_failures"]) >= 1
    assert body["memory_candidates"] == []
    assert body["audit"] == []


def test_reasoning_r1_schema_repair_is_structural_only(monkeypatch) -> None:
    original_builder = reasoning.build_deterministic_output

    def build_repairable_output(run_id, event):
        output = original_builder(run_id, event)
        output.pop("actions")
        output.pop("memory")
        return output

    monkeypatch.setattr(reasoning, "build_deterministic_output", build_repairable_output)

    response = client.post(
        "/events/internal",
        json={
            "type": "user.command.submitted",
            "source": "test",
            "payload": {"text": "repairable schema"},
        },
    )

    assert response.status_code == 200
    events = response.json()["events"]
    event_types = [event["type"] for event in events]
    assert "reasoning.repair.requested" in event_types
    assert "reasoning.failed" not in event_types
    assert "action.proposed" not in event_types

    run_id = events[0]["payload"]["run_id"]
    detail = client.get(f"/reasoning/runs/{run_id}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["run"]["status"] == "completed"
    assert len(body["context_snapshots"]) == 1
    assert [step["step_type"] for step in body["steps"][:4]] == [
        "context_check",
        "provider_running",
        "schema_validating",
        "schema_repair",
    ]
    assert body["steps"][3]["status"] == "completed"
    assert body["memory_candidates"] == []
    assert body["actions"] == []
    assert body["pending_actions"] == []
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


def test_reasoning_can_use_real_provider_route_when_enabled() -> None:
    provider_output = {
        "schema_version": "reasoning.v1",
        "run_id": "placeholder",
        "reply": {
            "should_reply": True,
            "text": "provider reply",
            "bubble_text": "provider reply",
            "style": "normal",
            "final": True,
        },
        "state": {"pet_state": "talking", "emotion": "neutral", "animation": None},
        "actions": [],
        "memory": {"write_candidates": [], "do_not_write_reason": None, "needs_consolidation": False},
        "observations": [],
        "voice": {"speak": False, "text": None, "voice_style": None},
        "debug": {"depth": "lightweight", "needs_deep_retrieval": False, "deep_retrieval_query": None, "trace": []},
        "audit": {"safety_notes": [], "permission_requests": []},
    }

    def fake_model_config() -> dict:
        return {
            "enabled": True,
            "provider": "deepseek",
            "base_url": "https://api.deepseek.com",
            "model": "deepseek-v4-flash",
            "api_key": "deepseek-secret-value",
            "temperature": 0.7,
            "stream": False,
        }

    def fake_provider_call(request, config):
        output = dict(provider_output)
        output["run_id"] = request["run_id"]
        return output

    with (
        patch("y_chat.reasoning.active_model_call_config", fake_model_config),
        patch("y_chat.reasoning.call_openai_compatible_chat", fake_provider_call),
    ):
        response = client.post(
            "/events/internal",
            json={
                "type": "user.command.submitted",
                "source": "test",
                "payload": {"text": "real provider route probe"},
            },
        )

    assert response.status_code == 200
    events = response.json()["events"]
    assert events[0]["payload"]["provider"] == "deepseek"
    assert events[0]["payload"]["real_model_call"] is True
    assert any(event["type"] == "pet.bubble.show" and event["payload"]["text"] == "provider reply" for event in events)


def test_log_redaction_masks_sensitive_values() -> None:
    line = (
        "Authorization: Bearer FAKE_SECRET_VALUE_FOR_TEST api_key='deepseek-secret' "
        "\"x-api-key\": \"quoted-secret\" token=abc123456789 password: hunter2"
    )

    redacted, changed = redact_log_line(line)

    assert changed is True
    assert "FAKE_SECRET_VALUE_FOR_TEST" not in redacted
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
    assert clean_log_line("\x1b[32m\u9253?\x1b[39m  Local") == "\u279c  Local"
