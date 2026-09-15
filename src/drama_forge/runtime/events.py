"""Execution events."""

from __future__ import annotations

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
    """Simple in-memory event log for an execution."""

    def __init__(self) -> None:
        self._events: list[ExecutionEvent] = []
        self._next_id = 1

    def emit(self, event_type: str, subject: str, **payload: Any) -> ExecutionEvent:
        """Append and return a new event."""
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
        if event_type is None:
            return list(self._events)
        return [e for e in self._events if e.event_type == event_type]
