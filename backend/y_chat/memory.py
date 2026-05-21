from __future__ import annotations

from pathlib import Path
from typing import Any

from .config import load_config
from .services.memory_contracts import (
    ATTACHMENT_REF_CONTRACT,
    AUDIO_READER_STATUS,
    MEMORY_LAYER_CONTRACTS,
    MEMORY_MODALITY_CONTRACTS,
    TEXT_READER_STATUS,
    VISION_READER_STATUS,
)
from .services.memory_manual import (
    add_memory_item as service_add_memory_item,
    delete_memory_item as service_delete_memory_item,
    list_memory_items,
)
from .services.memory_query import (
    list_memory_audit_log,
    list_memory_records,
    list_memory_review_queue,
    memory_contract_payload,
    memory_shell_payload as service_memory_shell_payload,
    memory_status_payload as service_memory_status_payload,
)
from .services.memory_store import (
    db_path,
    ensure_memory_db,
    json_dumps as _json_dumps,
    list_table_rows as _list_table_rows,
    now_iso,
    parse_json_field as _parse_json_field,
)


def memory_enabled() -> bool:
    config = load_config()
    return bool(config.get("permissions", {}).get("memory.write", False))


def _ensure_column(db, table: str, column: str, definition: str) -> None:
    from .data.sqlite_store import ensure_column

    ensure_column(db, table, column, definition)


def memory_status_payload() -> dict[str, Any]:
    return service_memory_status_payload(memory_enabled)


def memory_shell_payload() -> dict[str, Any]:
    return service_memory_shell_payload(
        list_consolidation_buffer_fn=list_consolidation_buffer,
        list_visual_evidence_fn=list_visual_evidence,
        list_text_evidence_fn=list_text_evidence,
        list_audio_evidence_fn=list_audio_evidence,
        vision_status_payload_fn=vision_status_payload,
        text_status_payload_fn=text_status_payload,
        audio_status_payload_fn=audio_status_payload,
    )


def list_visual_evidence(limit: int = 100) -> list[dict[str, Any]]:
    from .services.memory_evidence import list_visual_evidence as impl

    return impl(limit)


def list_text_evidence(limit: int = 100) -> list[dict[str, Any]]:
    from .services.memory_evidence import list_text_evidence as impl

    return impl(limit)


def list_audio_evidence(limit: int = 100) -> list[dict[str, Any]]:
    from .services.memory_evidence import list_audio_evidence as impl

    return impl(limit)


def list_consolidation_buffer(limit: int = 100) -> list[dict[str, Any]]:
    from .services.memory_evidence import list_consolidation_buffer as impl

    return impl(limit)


def consolidation_buffer_payload() -> dict[str, Any]:
    from .services.memory_evidence import consolidation_buffer_payload as impl

    return impl()


def create_visual_evidence_record(payload: dict[str, Any]) -> dict[str, Any]:
    from .services.memory_evidence import create_visual_evidence_record as impl

    return impl(payload)


def create_text_evidence_record(payload: dict[str, Any]) -> dict[str, Any]:
    from .services.memory_evidence import create_text_evidence_record as impl

    return impl(payload)


def create_audio_evidence_record(payload: dict[str, Any]) -> dict[str, Any]:
    from .services.memory_evidence import create_audio_evidence_record as impl

    return impl(payload)


def vision_status_payload() -> dict[str, Any]:
    from .services.memory_evidence import vision_status_payload as impl

    return impl()


def text_status_payload() -> dict[str, Any]:
    from .services.memory_evidence import text_status_payload as impl

    return impl()


def audio_status_payload() -> dict[str, Any]:
    from .services.memory_evidence import audio_status_payload as impl

    return impl()


def add_memory_item(kind: str, text: str) -> dict[str, Any]:
    if not memory_enabled():
        raise PermissionError("memory.write is disabled")
    return service_add_memory_item(kind, text)


def delete_memory_item(item_id: str) -> bool:
    return service_delete_memory_item(item_id)


__all__ = [
    "ATTACHMENT_REF_CONTRACT",
    "AUDIO_READER_STATUS",
    "MEMORY_LAYER_CONTRACTS",
    "MEMORY_MODALITY_CONTRACTS",
    "TEXT_READER_STATUS",
    "VISION_READER_STATUS",
    "Path",
    "add_memory_item",
    "audio_status_payload",
    "consolidation_buffer_payload",
    "create_audio_evidence_record",
    "create_text_evidence_record",
    "create_visual_evidence_record",
    "db_path",
    "delete_memory_item",
    "ensure_memory_db",
    "list_audio_evidence",
    "list_consolidation_buffer",
    "list_memory_audit_log",
    "list_memory_items",
    "list_memory_records",
    "list_memory_review_queue",
    "list_text_evidence",
    "list_visual_evidence",
    "memory_contract_payload",
    "memory_enabled",
    "memory_shell_payload",
    "memory_status_payload",
    "now_iso",
    "text_status_payload",
    "vision_status_payload",
]
