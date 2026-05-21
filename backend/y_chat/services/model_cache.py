from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

from ..config import RUNTIME_DIR


MODEL_CACHE_DIR = RUNTIME_DIR / "models" / "hf"


def local_model_path(local_dir: str) -> Path:
    return MODEL_CACHE_DIR / local_dir


def model_state(name: str, spec: dict[str, Any]) -> dict[str, Any]:
    local_path = local_model_path(str(spec["local_dir"]))
    present_files = [file.name for file in local_path.iterdir() if file.is_file()] if local_path.exists() else []
    missing_files = [file for file in spec["required_files"] if file not in present_files]
    package_state = {
        package: importlib.util.find_spec(package) is not None
        for package in spec["required_packages"]
    }
    return {
        "name": name,
        "modality": spec["modality"],
        "model_id": spec["model_id"],
        "purpose": spec["purpose"],
        "local_path": str(local_path),
        "path_exists": local_path.exists(),
        "downloaded": local_path.exists() and not missing_files,
        "required_files": spec["required_files"],
        "missing_files": missing_files,
        "packages": package_state,
        "packages_ready": all(package_state.values()),
        "text_auxiliary_only": bool(spec["text_auxiliary_only"]),
    }


def model_ready(state: dict[str, Any]) -> bool:
    return bool(state["downloaded"] and state["packages_ready"])


def blocked_reasons(models: dict[str, dict[str, Any]]) -> list[str]:
    blocked: list[str] = []
    for name, state in models.items():
        if not state["packages_ready"]:
            missing = [package for package, ready in state["packages"].items() if not ready]
            blocked.append(f"{name} missing packages: {', '.join(missing)}")
        if not state["downloaded"]:
            blocked.append(f"{name} model files are not fully downloaded")
    return blocked
