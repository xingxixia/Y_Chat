from __future__ import annotations

from pathlib import Path
from typing import Any

from .config import load_config


TEXT_EXTENSIONS = {".md", ".txt", ".json", ".yaml", ".yml", ".py", ".ts", ".tsx", ".js", ".cjs", ".css"}


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
        root_items.append(
            {
                "index": index,
                "path": str(root),
                "exists": exists,
                "is_dir": is_dir,
                "listing_allowed": enabled and exists and is_dir,
            }
        )
    return {
        "enabled": enabled,
        "allowed_roots": [str(root) for root in roots],
        "roots": root_items,
        "text_extensions": sorted(TEXT_EXTENSIONS),
        "content_reading_enabled": False,
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
