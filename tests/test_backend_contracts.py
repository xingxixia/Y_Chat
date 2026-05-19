from __future__ import annotations

from fastapi.testclient import TestClient

from test_atri.logs import clean_log_line, redact_log_line
from test_atri.main import app


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
    assert event_types == ["pet.state.changed", "pet.bubble.show", "pet.state.changed"]


def test_model_provider_status_is_disabled_by_default() -> None:
    response = client.get("/model/provider/status")
    assert response.status_code == 200
    assert response.json()["enabled"] is False


def test_project_reader_is_blocked_by_default() -> None:
    response = client.get("/project-reader/files")
    assert response.status_code == 403


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
