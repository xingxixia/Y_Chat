from __future__ import annotations

from typing import Any

from .memory_contracts import (
    ATTACHMENT_REF_CONTRACT,
    AUDIO_READER_STATUS,
    TEXT_READER_STATUS,
    VISION_READER_STATUS,
)
from .memory_store import (
    db_path,
    ensure_memory_db,
    json_dumps as store_json_dumps,
    list_table_rows,
    now_iso,
    parse_json_field,
)


def json_dumps(value: Any) -> str:
    return store_json_dumps(value)
