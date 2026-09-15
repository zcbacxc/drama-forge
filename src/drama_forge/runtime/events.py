# SPDX-FileCopyrightText: 2026 zcbacxc
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Execution events."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


def _now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(slots=True)
class ExecutionEvent:
    """What happened during execution (not why a decision was made)."""

    id: int
    event_type: str
    subject: str
    payload: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=_now)


class EventBus:
    """Thread-safe in-memory event log for an execution."""

    def __init__(self) -> None:
        self._events: list[ExecutionEvent] = []
        self._next_id = 1
        self._lock = threading.Lock()

    def emit(self, event_type: str, subject: str, **payload: Any) -> ExecutionEvent:
        """Append and return a new event."""
        with self._lock:
            event = ExecutionEvent(
                id=self._next_id,
                event_type=event_type,
                subject=subject,
                payload=payload,
            )
            self._next_id += 1
            self._events.append(event)
            return event

    def list(self, event_type: str | None = None) -> list[ExecutionEvent]:
        """List events optionally filtered by type."""
        with self._lock:
            snapshot = list(self._events)
        if event_type is None:
            return snapshot
        return [e for e in snapshot if e.event_type == event_type]
