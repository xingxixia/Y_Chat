from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

from ..config import RUNTIME_DIR, load_config, runtime_sqlite_path


SUPPORTED_PROVIDER_NAMES = {"deepseek", "openai_compatible"}
RECOMMENDED_DEEPSEEK_MODELS = ["deepseek-v4-flash", "deepseek-v4-pro", "deepseek-chat"]


def mask_secret(value: str) -> str:
    secret = value.strip()
    if not secret:
        return ""
    if len(secret) <= 8:
        return "*" * len(secret)
    return f"{secret[:3]}...{secret[-4:]}"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_provider_audit_db() -> None:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(runtime_sqlite_path()) as db:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS provider_config_audit (
                audit_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )


def record_provider_config_audit(status: str, payload: dict[str, Any]) -> str:
    ensure_provider_audit_db()
    audit_id = str(uuid4())
    with sqlite3.connect(runtime_sqlite_path()) as db:
        db.execute(
            """
            INSERT INTO provider_config_audit (
                audit_id, status, payload_json, created_at
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                audit_id,
                status,
                json.dumps(payload, ensure_ascii=True),
                now_iso(),
            ),
        )
    return audit_id


def validate_provider_config_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    provider = str(candidate.get("provider") or candidate.get("active_provider") or "").strip()
    base_url = str(candidate.get("base_url") or "").strip()
    model = str(candidate.get("model") or "").strip()
    api_key = str(candidate.get("api_key") or "")
    enabled_requested = bool(candidate.get("enabled_requested", False))
    secondary_confirmed = bool(candidate.get("secondary_confirmed", False))
    stream = bool(candidate.get("stream", False))
    timeout_seconds = safe_positive_int(candidate.get("timeout_seconds"), default=45, minimum=5, maximum=120)
    max_tokens = safe_positive_int(candidate.get("max_tokens"), default=1200, minimum=128, maximum=8192)
    thinking_type = str(candidate.get("thinking_type", "disabled")).strip() or "disabled"

    errors: list[str] = []
    warnings: list[str] = []
    try:
        temperature = safe_temperature(candidate.get("temperature"))
    except (TypeError, ValueError) as exc:
        temperature = None
        errors.append(str(exc))

    if not provider:
        errors.append("provider is required")
    elif provider not in SUPPORTED_PROVIDER_NAMES:
        errors.append("provider must be deepseek or openai_compatible")

    if not base_url:
        errors.append("base_url is required")
    elif not valid_http_url(base_url):
        errors.append("base_url must be an http or https URL")

    if not model:
        errors.append("model is required")
    if provider == "deepseek" and model == "deepseek-chat":
        warnings.append("deepseek-chat is legacy; prefer deepseek-v4-flash or deepseek-v4-pro")
    if thinking_type not in {"enabled", "disabled"}:
        errors.append("thinking_type must be enabled or disabled")

    if not api_key.strip():
        warnings.append("api_key is not configured; real calls would remain unavailable")

    permissions = load_config().get("permissions", {})
    permission_allowed = bool(permissions.get("model.call", False)) if isinstance(permissions, dict) else False
    if enabled_requested:
        warnings.append("validation is dry-run only and does not enable model calls")
        if not permission_allowed:
            warnings.append("permissions.model.call is disabled")
    if not secondary_confirmed:
        warnings.append("saving an API key or enabling model calls requires secondary confirmation")

    sanitized_candidate = {
        "provider": provider,
        "base_url": base_url,
        "model": model,
        "temperature": temperature,
        "stream": stream,
        "timeout_seconds": timeout_seconds,
        "max_tokens": max_tokens,
        "thinking_type": thinking_type,
        "enabled_requested": enabled_requested,
        "secondary_confirmed": secondary_confirmed,
        "permission_allowed": permission_allowed,
        "api_key_configured": bool(api_key.strip()),
        "api_key_masked": mask_secret(api_key),
    }
    ok = not errors
    audit_payload = {
        "action": "validate_provider_config_candidate",
        "saved": False,
        "real_model_calls": False,
        "requires_secondary_confirmation_for_save": True,
        "candidate": sanitized_candidate,
        "errors": errors,
        "warnings": warnings,
    }
    audit_id = record_provider_config_audit(
        "validated" if ok else "validation_failed",
        audit_payload,
    )

    return {
        "ok": ok,
        "saved": False,
        "real_model_calls": False,
        "requires_secondary_confirmation_for_save": True,
        "audit_id": audit_id,
        "candidate": sanitized_candidate,
        "errors": errors,
        "warnings": warnings,
    }


def provider_config_audit_payload(limit: int = 50) -> dict[str, Any]:
    ensure_provider_audit_db()
    safe_limit = max(1, min(limit, 100))
    with sqlite3.connect(runtime_sqlite_path()) as db:
        db.row_factory = sqlite3.Row
        rows = db.execute(
            """
            SELECT audit_id, status, payload_json, created_at
            FROM provider_config_audit
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (safe_limit,),
        ).fetchall()

    return {
        "audits": [
            {
                **dict(row),
                "payload": json.loads(row["payload_json"]),
                "payload_json": None,
            }
            for row in rows
        ]
    }


def valid_http_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def safe_temperature(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError("temperature must be numeric")
    temperature = float(value)
    if temperature < 0 or temperature > 2:
        raise ValueError("temperature must be between 0 and 2")
    return temperature


def safe_positive_int(value: Any, *, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(parsed, maximum))
