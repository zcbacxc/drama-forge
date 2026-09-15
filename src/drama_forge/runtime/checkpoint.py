# SPDX-FileCopyrightText: 2026 zcbacxc
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Checkpoint store for interrupt/resume."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from drama_forge.domain.common import NodeStatus


@dataclass(slots=True)
class Checkpoint:
    """Production state snapshot for recovery."""

    graph_id: str
    execution_id: str
    graph_fingerprint: str
    input_fingerprint: str
    completed_nodes: list[str] = field(default_factory=list)
    node_outputs: dict[str, dict[str, Any]] = field(default_factory=dict)
    node_status: dict[str, str] = field(default_factory=dict)
    artifact_refs: dict[str, list[str]] = field(default_factory=dict)
    candidate_refs: dict[str, list[str]] = field(default_factory=dict)
    execution_status: str = "RUNNING"
    failure_state: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize checkpoint.

        Returns:
                    dict[str, Any]
        """
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Checkpoint:
        """Deserialize checkpoint.

        Args:
                    data: dict[str, Any]

        Returns:
                    Checkpoint
        """
        return cls(**data)


class CheckpointStore:
    """In-memory checkpoint store (swap for SQLite/FS later)."""

    def __init__(self) -> None:
        """__init__.

        Args:
                    None.
        """
        self._store: dict[str, Checkpoint] = {}

    def save(self, checkpoint: Checkpoint) -> Checkpoint:
        """Persist a checkpoint by execution id.

        Args:
                    checkpoint: Checkpoint

        Returns:
                    Checkpoint
        """
        self._store[checkpoint.execution_id] = checkpoint
        return checkpoint

    def load(self, execution_id: str) -> Checkpoint | None:
        """Load a checkpoint if present.

        Args:
                    execution_id: str

        Returns:
                    Checkpoint | None
        """
        return self._store.get(execution_id)

    def update_status_from_graph(
        self,
        execution_id: str,
        statuses: dict[str, NodeStatus],
    ) -> Checkpoint | None:
        """Refresh node statuses into an existing checkpoint.

        Args:
                    execution_id: str
                    statuses: dict[str, NodeStatus]

        Returns:
                    Checkpoint | None
        """
        cp = self._store.get(execution_id)
        if cp is None:
            return None
        cp.node_status = {k: v.value for k, v in statuses.items()}
        cp.completed_nodes = [
            nid for nid, st in statuses.items() if st == NodeStatus.SUCCEEDED
        ]
        return cp
