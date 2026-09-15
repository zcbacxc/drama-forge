# SPDX-FileCopyrightText: 2026 zcbacxc
# SPDX-License-Identifier: AGPL-3.0-or-later
"""SQLite connection lifecycle and schema migration."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from drama_forge.persistence.schema import MIGRATIONS, SCHEMA_VERSION


def dumps(value: Any) -> str:
    """Serialize a value to compact JSON text for storage.

    Args:
        value: JSON-serializable structure (dict/list/primitives).

    Returns:
        JSON text with stable key order.
    """
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def loads(text: str | None, default: Any = None) -> Any:
    """Deserialize JSON text from storage.

    Args:
        text: Stored JSON string or None.
        default: Value returned when text is empty/None.

    Returns:
        Parsed structure, or ``default`` when nothing was stored.
    """
    if text is None or text == "":
        return default
    return json.loads(text)


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    """Convert a sqlite3.Row into a plain dict."""
    if row is None:
        return None
    return {key: row[key] for key in row.keys()}


class Database:
    """Thin SQLite handle with connect/migrate/close lifecycle.

    Usage:
        db = Database(":memory:")
        db.migrate()
        repo = StoryRepository(db)
        ...
        db.close()
    """

    def __init__(self, path: str | Path = ":memory:") -> None:
        """Open (or create) a database at ``path``.

        Args:
            path: Filesystem path or ``":memory:"`` for an in-memory DB.
        """
        self.path = str(path)
        self._conn: sqlite3.Connection | None = None

    def connect(self) -> sqlite3.Connection:
        """Return the underlying connection, creating it on first use.

        Returns:
            A sqlite3 connection with Row factory and FKs enabled.
        """
        if self._conn is None:
            if self.path != ":memory:":
                parent = Path(self.path).expanduser().resolve().parent
                parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(self.path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")
            self._conn = conn
        return self._conn

    @property
    def connection(self) -> sqlite3.Connection:
        """Alias for :meth:`connect` (creates on first access)."""
        return self.connect()

    def migrate(self) -> int:
        """Apply pending schema migrations via PRAGMA user_version.

        Returns:
            The schema version after migration.
        """
        conn = self.connect()
        current = int(conn.execute("PRAGMA user_version").fetchone()[0])
        if current >= SCHEMA_VERSION:
            return current
        for target_version, statements in MIGRATIONS:
            if current >= target_version:
                continue
            with conn:
                for sql in statements:
                    conn.execute(sql)
                conn.execute(f"PRAGMA user_version = {int(target_version)}")
            current = target_version
        return current

    def schema_version(self) -> int:
        """Return the current PRAGMA user_version."""
        return int(self.connect().execute("PRAGMA user_version").fetchone()[0])

    def close(self) -> None:
        """Close the connection if open."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def __enter__(self) -> Database:
        """Enter context manager; opens connection."""
        self.connect()
        return self

    def __exit__(self, *exc: object) -> None:
        """Exit context manager; always closes connection."""
        self.close()
