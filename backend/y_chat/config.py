from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _runtime_dir() -> Path:
    override = str(os.environ.get("Y_CHAT_RUNTIME_DIR") or "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return PROJECT_ROOT / "runtime"


RUNTIME_DIR = _runtime_dir()
CONFIG_PATH = RUNTIME_DIR / "config.yaml"


def load_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        return {}
    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Config must be a mapping: {CONFIG_PATH}")
    return data


def save_config(config: dict[str, Any]) -> None:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    with CONFIG_PATH.open("w", encoding="utf-8", newline="\n") as f:
        yaml.safe_dump(config, f, sort_keys=False, allow_unicode=True)


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
