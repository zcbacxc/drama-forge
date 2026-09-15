# SPDX-FileCopyrightText: 2026 zcbacxc
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Shared domain primitives: IDs, versions, fingerprints, enums."""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


def new_id(prefix: str = "") -> str:
    """Create a new unique identifier.

    Args:
        prefix: Optional short type prefix such as "story" or "shot".

    Returns:
        A string identifier.
    """
    raw = uuid.uuid4().hex[:12]
    return f"{prefix}_{raw}" if prefix else raw


def stable_hash(payload: Any) -> str:
    """Compute a deterministic fingerprint for a JSON-serializable payload.

    Args:
        payload: Any JSON-serializable structure.

    Returns:
        Hex digest string used as fingerprint.
    """
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:32]


class NodeStatus(StrEnum):
    """Production graph node lifecycle status."""

    PENDING = "PENDING"
    READY = "READY"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    RETRYING = "RETRYING"
    BLOCKED = "BLOCKED"
    SKIPPED = "SKIPPED"
    INVALIDATED = "INVALIDATED"
    DEGRADED = "DEGRADED"


class ArtifactType(StrEnum):
    """Typed artifact categories."""

    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    SUBTITLE = "subtitle"
    TIMELINE = "timeline"
    MANIFEST = "manifest"
    EVALUATION = "evaluation"
    JSON = "json"
    TEXT = "text"


class QualityState(StrEnum):
    """Quality lifecycle for artifacts and candidates."""

    UNEVALUATED = "UNEVALUATED"
    PASSED = "PASSED"
    WARNED = "WARNED"
    FAILED = "FAILED"
    SELECTED = "SELECTED"
    REJECTED = "REJECTED"


class GateResult(StrEnum):
    """Quality gate outcome."""

    PASS = "PASS"
    WARN = "WARN"
    BLOCK = "BLOCK"


class ExecutionStatus(StrEnum):
    """Overall execution status."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    PARTIAL = "PARTIAL"
    CANCELLED = "CANCELLED"


class Severity(StrEnum):
    """Issue severity levels."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class IssueType(StrEnum):
    """Structured quality issue types."""

    MISSING_INPUT = "MISSING_INPUT"
    MISSING_REFERENCE = "MISSING_REFERENCE"
    INCOMPLETE_SPEC = "INCOMPLETE_SPEC"
    INVALID_DEPENDENCY = "INVALID_DEPENDENCY"
    TECHNICAL_VALIDATION = "TECHNICAL_VALIDATION"
    VISUAL_QUALITY = "VISUAL_QUALITY"
    CHARACTER_CONTINUITY = "CHARACTER_CONTINUITY"
    SCENE_CONTINUITY = "SCENE_CONTINUITY"
    TEMPORAL_CONTINUITY = "TEMPORAL_CONTINUITY"
    STYLE_CONTINUITY = "STYLE_CONTINUITY"
    EXECUTION_FAILURE = "EXECUTION_FAILURE"


class RepairKind(StrEnum):
    """How a repair should be applied."""

    PREFLIGHT = "PREFLIGHT"
    POST_GENERATION = "POST_GENERATION"


class FailureClass(StrEnum):
    """Typed failure semantics for tasks and nodes.

    Separates retryable execution problems from quality / policy blocks
    so Scheduler (Retry) and RepairPlanner keep clear boundaries.
    """

    HARD_FAILURE = "HARD_FAILURE"
    SOFT_FAILURE = "SOFT_FAILURE"
    PARTIAL_FAILURE = "PARTIAL_FAILURE"
    BLOCKED = "BLOCKED"
    SKIPPED = "SKIPPED"
    DEGRADED = "DEGRADED"


@dataclass(frozen=True, slots=True)
class VersionedRef:
    """Reference to a versioned domain object."""

    id: str
    version: int = 1

    def fingerprint(self) -> str:
        """Return stable fingerprint of this reference."""
        return stable_hash({"id": self.id, "version": self.version})


@dataclass(slots=True)
class MetadataBag:
    """Free-form metadata attached to domain objects."""

    data: dict[str, Any] = field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any:
        """Read a metadata value."""
        return self.data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Write a metadata value."""
        self.data[key] = value
