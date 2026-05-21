from __future__ import annotations

from typing import Any

from .config import load_config
from .shared.contracts import PermissionName, SchemaVersion


SENSITIVE_CAPABILITIES = [
    PermissionName.MODEL_CALL,
    PermissionName.PROJECT_READ,
    PermissionName.SCREEN_OBSERVE,
    PermissionName.VOICE_LISTEN,
    PermissionName.VOICE_SPEAK,
    PermissionName.EXTERNAL_HTTP,
    PermissionName.EXTERNAL_WEBSOCKET,
    PermissionName.EXTERNAL_LAN,
    PermissionName.EXTERNAL_OSC,
    PermissionName.FILES_WRITE,
    PermissionName.INPUT_CONTROL,
    PermissionName.PROCESS_RUN,
    PermissionName.VR_OUTPUT,
]

PERMISSION_METADATA: dict[str, dict[str, Any]] = {
    PermissionName.MODEL_CALL: {
        "group": "model",
        "risk": "medium",
        "requires_secondary_confirmation": True,
        "reason": "Allows real model provider requests; default off until config, keys, and audit are ready.",
    },
    PermissionName.MEMORY_WRITE: {
        "group": "memory",
        "risk": "low",
        "requires_secondary_confirmation": False,
        "reason": "Allows manual debug notes now; automatic memory writes still use separate reasoning/audit rules.",
    },
    PermissionName.PROJECT_READ: {
        "group": "project",
        "risk": "medium",
        "requires_secondary_confirmation": True,
        "reason": "Allows reading user-authorized project roots; file contents remain gated separately.",
    },
    PermissionName.SCREEN_OBSERVE: {
        "group": "vision",
        "risk": "high",
        "requires_secondary_confirmation": True,
        "reason": "Screen perception can expose sensitive visual context; capture remains disabled.",
    },
    PermissionName.VOICE_LISTEN: {
        "group": "voice",
        "risk": "high",
        "requires_secondary_confirmation": True,
        "reason": "Microphone listening can capture private audio; capture remains disabled.",
    },
    PermissionName.VOICE_SPEAK: {
        "group": "voice",
        "risk": "medium",
        "requires_secondary_confirmation": True,
        "reason": "Speech output affects the user's environment and future persona/audio behavior.",
    },
    PermissionName.EXTERNAL_HTTP: {
        "group": "external",
        "risk": "high",
        "requires_secondary_confirmation": True,
        "reason": "External network access can transmit data outside the local machine.",
    },
    PermissionName.EXTERNAL_WEBSOCKET: {
        "group": "external",
        "risk": "high",
        "requires_secondary_confirmation": True,
        "reason": "Persistent external connections can transmit or receive uncontrolled data.",
    },
    PermissionName.EXTERNAL_LAN: {
        "group": "external",
        "risk": "high",
        "requires_secondary_confirmation": True,
        "reason": "LAN access can interact with devices or services on the local network.",
    },
    PermissionName.EXTERNAL_OSC: {
        "group": "external",
        "risk": "high",
        "requires_secondary_confirmation": True,
        "reason": "OSC adapters may control external creative, avatar, or VR tools.",
    },
    PermissionName.FILES_WRITE: {
        "group": "system",
        "risk": "high",
        "requires_secondary_confirmation": True,
        "reason": "File writes can modify or delete user data and must remain explicitly gated.",
    },
    PermissionName.INPUT_CONTROL: {
        "group": "system",
        "risk": "high",
        "requires_secondary_confirmation": True,
        "reason": "Input control can operate the user's desktop and must never run without explicit permission.",
    },
    PermissionName.PROCESS_RUN: {
        "group": "system",
        "risk": "high",
        "requires_secondary_confirmation": True,
        "reason": "Process execution can run local commands and must remain explicitly gated.",
    },
    PermissionName.VR_OUTPUT: {
        "group": "vr",
        "risk": "high",
        "requires_secondary_confirmation": True,
        "reason": "VR output can affect external avatar/session state and must remain explicitly gated.",
    },
}


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
    details = []
    for name, value in sorted_permissions.items():
        metadata = PERMISSION_METADATA.get(
            name,
            {
                "group": "other",
                "risk": "medium",
                "requires_secondary_confirmation": True,
                "reason": "Unclassified capability; keep gated until it has an explicit policy.",
            },
        )
        details.append(
            {
                "name": name,
                "enabled": value,
                **metadata,
            }
        )

    return {
        "permissions": sorted_permissions,
        "enabled": enabled,
        "disabled": disabled,
        "details": details,
        "contract_endpoint": "/permissions/contract",
    }


def permission_contract_payload() -> dict[str, Any]:
    config = load_config()
    permissions = config.get("permissions", {})
    if not isinstance(permissions, dict):
        permissions = {}

    details = []
    for name in sorted(PERMISSION_METADATA):
        metadata = PERMISSION_METADATA[name]
        enabled = bool(permissions.get(name, False))
        details.append(
            {
                "name": name,
                "enabled": enabled,
                "default_enabled": False,
                **metadata,
            }
        )

    sensitive_enabled = [name for name in SENSITIVE_CAPABILITIES if bool(permissions.get(name, False))]
    secondary_required = [
        name
        for name, metadata in sorted(PERMISSION_METADATA.items())
        if metadata["requires_secondary_confirmation"]
    ]
    return {
        "schema_version": SchemaVersion.PERMISSIONS_CONTRACT,
        "read_only": True,
        "mutation_enabled": False,
        "config_write_enabled": False,
        "audit_required_for_sensitive_changes": True,
        "secondary_confirmation_required_for": secondary_required,
        "sensitive_capabilities": SENSITIVE_CAPABILITIES,
        "sensitive_enabled": sensitive_enabled,
        "blocked_until_explicit_user_selection": [
            "real model calls",
            "project file reading",
            "screen capture",
            "microphone listening",
            "voice output",
            "external HTTP/WebSocket/LAN/OSC adapters",
            "file writes",
            "process execution",
            "desktop input control",
            "VR output",
        ],
        "rules": [
            {
                "name": "status_is_read_only",
                "enabled": True,
                "detail": "Permission endpoints report configured state but do not mutate runtime/config.yaml.",
            },
            {
                "name": "sensitive_defaults_off",
                "enabled": True,
                "detail": "Sensitive capabilities stay off unless explicitly selected by the user.",
            },
            {
                "name": "secondary_confirmation_required",
                "enabled": True,
                "detail": "Medium/high-risk capabilities require secondary confirmation before future enablement.",
            },
            {
                "name": "audit_required",
                "enabled": True,
                "detail": "Future sensitive permission changes require audit records.",
            },
            {
                "name": "memory_cannot_change_hard_permissions",
                "enabled": True,
                "detail": "Memory may propose permission changes later but cannot directly flip real capability gates.",
            },
        ],
        "capabilities": details,
    }
