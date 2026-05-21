from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


CURRENT_SCREEN_MAX_AGE_SECONDS = 120.0


def parse_iso_datetime(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def visual_age_seconds(created_at: Any, *, now: datetime | None = None) -> float | None:
    parsed = parse_iso_datetime(created_at)
    if parsed is None:
        return None
    reference = now or datetime.now(timezone.utc)
    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=timezone.utc)
    age = (reference.astimezone(timezone.utc) - parsed).total_seconds()
    return round(max(0.0, age), 3)


def visual_freshness_status(created_at: Any, *, now: datetime | None = None) -> dict[str, Any]:
    age_seconds = visual_age_seconds(created_at, now=now)
    fresh = age_seconds is not None and age_seconds <= CURRENT_SCREEN_MAX_AGE_SECONDS
    return {
        "age_seconds": age_seconds,
        "fresh_for_current_screen": fresh,
        "stale_for_current_screen": not fresh,
        "current_screen_max_age_seconds": CURRENT_SCREEN_MAX_AGE_SECONDS,
    }
