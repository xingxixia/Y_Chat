from __future__ import annotations

import sqlite3
from pathlib import Path
from ..config import RUNTIME_DIR, runtime_sqlite_path


def sqlite_path() -> Path:
    return runtime_sqlite_path()


def connect(*, row_factory: bool = False) -> sqlite3.Connection:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(sqlite_path())
    if row_factory:
        db.row_factory = sqlite3.Row
    return db


def table_names(db: sqlite3.Connection) -> set[str]:
    return {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def table_columns(db: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in db.execute(f"PRAGMA table_info({table})").fetchall()}


def ensure_column(db: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    if column not in table_columns(db, table):
        db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
