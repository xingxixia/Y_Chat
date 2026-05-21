from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..events import EventEnvelope, make_event, sanitize_event_for_debug
from ..memory import create_text_evidence_record
from ..reasoning import run_deterministic_reasoning
from ..shared.contracts import EventType


router = APIRouter()


@router.post("/events/internal")
async def internal_event(event: EventEnvelope) -> dict[str, list[dict]]:
    if event.type == EventType.USER_COMMAND_SUBMITTED:
        text = str(event.payload.get("text", "")).strip()
        if text:
            create_text_evidence_record(
                {
                    "source": "user_command",
                    "text": text,
                    "source_event_id": event.event_id,
                    "language": "unknown",
                    "text_reader_status": "observed",
                }
            )
        return {"events": [sanitize_event_for_debug(item) for item in run_deterministic_reasoning(event)["events"]]}

    debug = make_event(
        "debug.log",
        "backend",
        {
            "message": "event received",
            "received_type": event.type,
        },
        correlation_id=event.event_id,
    )
    return {"events": [sanitize_event_for_debug(debug)]}


@router.websocket("/ws/internal")
async def internal_ws(websocket: WebSocket) -> None:
    await websocket.accept()
    hello = make_event(
        EventType.SYSTEM_HELLO,
        "backend",
        {"message": "Y_Chat backend connected"},
    )
    await websocket.send_json(sanitize_event_for_debug(hello))

    try:
        while True:
            message = await websocket.receive_json()
            try:
                incoming = EventEnvelope.model_validate(message)
                echo = make_event(
                    "debug.log",
                    "backend",
                    {
                        "message": "event received",
                        "received_type": incoming.type,
                    },
                    correlation_id=incoming.event_id,
                )
            except Exception as exc:
                echo = make_event(
                    "error.reported",
                    "backend",
                    {
                        "message": "invalid event envelope",
                        "error": str(exc),
                    },
                )
            await websocket.send_json(sanitize_event_for_debug(echo))
    except WebSocketDisconnect:
        return
