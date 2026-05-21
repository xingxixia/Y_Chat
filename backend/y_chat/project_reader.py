from __future__ import annotations

from pathlib import Path
from typing import Any

from .config import load_config


TEXT_EXTENSIONS = {".md", ".txt", ".json", ".yaml", ".yml", ".py", ".ts", ".tsx", ".js", ".cjs", ".css"}

SAFETY_RULES: list[dict[str, Any]] = [
    {
        "name": "authorized_roots_required",
        "enabled": True,
        "detail": "Only roots from project_reader.allowed_roots may ever be considered.",
    },
    {
        "name": "text_whitelist_required",
        "enabled": True,
        "detail": "Future content reads must be limited to the configured text extension whitelist.",
    },
    {
        "name": "content_reading_enabled",
        "enabled": False,
        "detail": "This slice never returns file contents.",
    },
    {
        "name": "raw_content_return_enabled",
        "enabled": False,
        "detail": "Raw project content is not returned by any Project Reader endpoint.",
    },
    {
        "name": "path_escape_blocking",
        "enabled": True,
        "detail": "Caller-supplied paths are not accepted; future paths must resolve inside an authorized root.",
    },
    {
        "name": "recursive_content_scan_enabled",
        "enabled": False,
        "detail": "Recursive project scans are disabled; the current file endpoint is top-level listing only.",
    },
]


def _root_blocked_reason(enabled: bool, exists: bool, is_dir: bool) -> str | None:
    if not enabled:
        return "permissions.project.read is disabled"
    if not exists:
        return "authorized root does not exist"
    if not is_dir:
        return "authorized root is not a directory"
    return None


def project_read_enabled() -> bool:
    config = load_config()
    return bool(config.get("permissions", {}).get("project.read", False))


def allowed_roots() -> list[Path]:
    config = load_config()
    roots = config.get("project_reader", {}).get("allowed_roots", [])
    if not isinstance(roots, list):
        return []
    return [Path(str(root)).resolve() for root in roots]


def status_payload() -> dict[str, Any]:
    roots = allowed_roots()
    enabled = project_read_enabled()
    root_items = []
    for index, root in enumerate(roots):
        exists = root.exists()
        is_dir = root.is_dir() if exists else False
        listing_allowed = enabled and exists and is_dir
        root_items.append(
            {
                "index": index,
                "path": str(root),
                "exists": exists,
                "is_dir": is_dir,
                "listing_allowed": listing_allowed,
                "blocked_reason": _root_blocked_reason(enabled, exists, is_dir),
            }
        )
    blocked_reasons = []
    if not enabled:
        blocked_reasons.append("permissions.project.read is disabled")
    if not roots:
        blocked_reasons.append("project_reader.allowed_roots is empty")
    blocked_reasons.append("file content reading is disabled")
    blocked_reasons.append("raw content return is disabled")
    blocked_reasons.append("recursive content scan is disabled")
    return {
        "enabled": enabled,
        "read_only": True,
        "allowed_roots": [str(root) for root in roots],
        "roots": root_items,
        "text_extensions": sorted(TEXT_EXTENSIONS),
        "content_reading_enabled": False,
        "raw_content_return_enabled": False,
        "recursive_content_scan_enabled": False,
        "path_escape_blocking": True,
        "authorized_roots_required": True,
        "text_whitelist_required": True,
        "contract_endpoint": "/project-reader/contract",
        "listing_enabled": enabled and any(item["listing_allowed"] for item in root_items),
        "blocked_reasons": blocked_reasons,
        "safety_rules": SAFETY_RULES,
    }


def contract_payload() -> dict[str, Any]:
    return {
        "schema_version": "project_reader.contract.v1",
        "read_only": True,
        "permission_gate": "permissions.project.read",
        "config_gate": "project_reader.allowed_roots",
        "authorized_roots_required": True,
        "text_whitelist_required": True,
        "text_extensions": sorted(TEXT_EXTENSIONS),
        "content_reading_enabled": False,
        "raw_content_return_enabled": False,
        "recursive_content_scan_enabled": False,
        "path_escape_blocking": True,
        "listing_scope": "top_level_only",
        "path_policy": {
            "caller_supplied_paths_accepted": False,
            "root_selection": "allowed root index only",
            "escape_rule": "resolved paths must stay inside an authorized root before any future content read",
        },
        "blocked_until_enabled": [
            "file content reads",
            "raw content return",
            "recursive content scans",
            "unauthorized roots",
            "path traversal outside an authorized root",
            "non-whitelisted file types",
        ],
        "safety_rules": SAFETY_RULES,
    }


def list_root_files(root_index: int = 0) -> list[dict[str, Any]]:
    if not project_read_enabled():
        raise PermissionError("project.read is disabled")

    roots = allowed_roots()
    if root_index < 0 or root_index >= len(roots):
        raise FileNotFoundError("allowed root not found")

    root = roots[root_index]
    if not root.exists() or not root.is_dir():
        raise FileNotFoundError("allowed root does not exist")

    items: list[dict[str, Any]] = []
    for child in sorted(root.iterdir(), key=lambda path: path.name.lower()):
        if child.name.startswith("."):
            continue
        items.append(
            {
                "name": child.name,
                "kind": "dir" if child.is_dir() else "file",
                "text_allowed": child.is_file() and child.suffix.lower() in TEXT_EXTENSIONS,
            }
        )
        if len(items) >= 200:
            break
    return items
