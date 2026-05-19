from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class EventEnvelope(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    type: str
    source: str
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    correlation_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


def make_event(
    event_type: str,
    source: str,
    payload: dict[str, Any] | None = None,
    correlation_id: str | None = None,
) -> EventEnvelope:
    return EventEnvelope(
        type=event_type,
        source=source,
        payload=payload or {},
        correlation_id=correlation_id,
    )
