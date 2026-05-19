from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RUNTIME_DIR = PROJECT_ROOT / "runtime"
CONFIG_PATH = RUNTIME_DIR / "config.yaml"


def load_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        return {}
    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Config must be a mapping: {CONFIG_PATH}")
    return data


def app_machine_name() -> str:
    config = load_config()
    raw_name = str(config.get("app", {}).get("machine_name", "y_chat")).strip()
    return raw_name or "y_chat"


def runtime_sqlite_path() -> Path:
    return RUNTIME_DIR / f"{app_machine_name()}.sqlite3"


def backend_host() -> str:
    config = load_config()
    return str(config.get("backend", {}).get("host", "127.0.0.1"))


def backend_port() -> int:
    config = load_config()
    return int(config.get("backend", {}).get("port", 18080))
