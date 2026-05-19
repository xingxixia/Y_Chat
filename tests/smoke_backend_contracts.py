from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from test_atri.main import app  # noqa: E402


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
        ["pet.state.changed", "pet.bubble.show", "pet.state.changed"],
        "command event sequence",
    )

    provider = client.get("/model/provider/status")
    assert_equal(provider.status_code, 200, "provider status")
    assert_equal(provider.json()["enabled"], False, "provider enabled default")

    permissions = client.get("/permissions/status")
    assert_equal(permissions.status_code, 200, "permissions status")
    assert_equal(permissions.json()["permissions"]["project.read"], False, "project read default")

    logs = client.get("/logs/status")
    assert_equal(logs.status_code, 200, "logs status")
    assert "logs" in logs.json()

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
