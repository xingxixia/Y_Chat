from __future__ import annotations

from typing import Any

from .config import load_config


def permission_status_payload() -> dict[str, Any]:
    config = load_config()
    permissions = config.get("permissions", {})
    if not isinstance(permissions, dict):
        permissions = {}

    sorted_permissions = {
        str(name): bool(value)
        for name, value in sorted(permissions.items(), key=lambda item: str(item[0]))
    }
    enabled = [name for name, value in sorted_permissions.items() if value]
    disabled = [name for name, value in sorted_permissions.items() if not value]

    return {
        "permissions": sorted_permissions,
        "enabled": enabled,
        "disabled": disabled,
    }
