from __future__ import annotations

from fastapi.testclient import TestClient

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
