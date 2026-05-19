from __future__ import annotations

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .events import EventEnvelope, make_event
from .logs import log_status_payload
from .memory import add_memory_item, delete_memory_item, list_memory_items, memory_enabled
from .model_provider import provider_status_payload
from .permissions import permission_status_payload
from .project_reader import list_root_files, status_payload as project_reader_status_payload


app = FastAPI(title="test atri backend", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class MemoryCreateRequest(BaseModel):
    kind: str = "note"
    text: str


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "app": "test_atri"}


@app.get("/model/provider/status")
async def model_provider_status() -> dict:
    return provider_status_payload()


@app.get("/permissions/status")
async def permissions_status() -> dict:
    return permission_status_payload()


@app.get("/logs/status")
async def logs_status() -> dict:
    return log_status_payload()


@app.get("/memory")
async def memory_list() -> dict:
    return {
        "enabled": memory_enabled(),
        "items": list_memory_items(),
    }


@app.post("/memory")
async def memory_create(request: MemoryCreateRequest) -> dict:
    text = request.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="text is required")

    try:
        item = add_memory_item(request.kind.strip() or "note", text)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return {"item": item}


@app.delete("/memory/{item_id}")
async def memory_delete(item_id: str) -> dict:
    return {"deleted": delete_memory_item(item_id)}


@app.get("/project-reader/status")
async def project_reader_status() -> dict:
    return project_reader_status_payload()


@app.get("/project-reader/files")
async def project_reader_files(root_index: int = 0) -> dict:
    try:
        items = list_root_files(root_index)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"items": items}


@app.post("/events/internal")
async def internal_event(event: EventEnvelope) -> dict[str, list[dict]]:
    if event.type == "user.command.submitted":
        text = str(event.payload.get("text", "")).strip()
        thinking = make_event(
            "pet.state.changed",
            "backend",
            {
                "state": "thinking",
                "previous_state": "idle",
            },
            correlation_id=event.event_id,
        )
        response = make_event(
            "pet.bubble.show",
            "backend",
            {
                "text": f"Received: {text}\n\nBackend event bus is connected."
            },
            correlation_id=event.event_id,
        )
        talking = make_event(
            "pet.state.changed",
            "backend",
            {
                "state": "talking",
                "previous_state": "thinking",
            },
            correlation_id=event.event_id,
        )
        return {"events": [thinking.model_dump(), response.model_dump(), talking.model_dump()]}

    debug = make_event(
        "debug.log",
        "backend",
        {
            "message": "event received",
            "received_type": event.type,
        },
        correlation_id=event.event_id,
    )
    return {"events": [debug.model_dump()]}


@app.websocket("/ws/internal")
async def internal_ws(websocket: WebSocket) -> None:
    await websocket.accept()
    hello = make_event(
        "system.hello",
        "backend",
        {"message": "test atri backend connected"},
    )
    await websocket.send_json(hello.model_dump())

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
            await websocket.send_json(echo.model_dump())
    except WebSocketDisconnect:
        return
