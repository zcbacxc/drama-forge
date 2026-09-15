# SPDX-FileCopyrightText: 2026 zcbacxc
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Quality domain objects: issues, gates, repair plans."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from drama_forge.domain.asset import utc_now_iso
from drama_forge.domain.common import (
    GateResult,
    IssueType,
    RepairKind,
    Severity,
    new_id,
)


@dataclass(slots=True)
class Issue:
    """Structured quality problem discovered during validation/evaluation."""

    id: str
    issue_type: IssueType
    severity: Severity
    node_id: str | None = None
    asset_id: str | None = None
    message: str = ""
    evidence: dict[str, Any] = field(default_factory=dict)
    suggested_scope: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=utc_now_iso)

    @classmethod
    def create(
        cls,
        issue_type: IssueType,
        severity: Severity,
        message: str = "",
        **kwargs: object,
    ) -> Issue:
        """Create a quality issue."""
        return cls(
            id=new_id("issue"),
            issue_type=issue_type,
            severity=severity,
            message=message,
            **kwargs,  # type: ignore[arg-type]
        )


@dataclass(slots=True)
class QualityResult:
    """Outcome of validating/evaluating one subject."""

    id: str
    subject_id: str
    gate: GateResult
    scores: dict[str, float] = field(default_factory=dict)
    issues: list[Issue] = field(default_factory=list)
    evidence: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now_iso)

    @classmethod
    def create(cls, subject_id: str, gate: GateResult, **kwargs: object) -> QualityResult:
        """Create a quality result."""
        return cls(id=new_id("qr"), subject_id=subject_id, gate=gate, **kwargs)  # type: ignore[arg-type]


@dataclass(slots=True)
class RepairAction:
    """One concrete repair step."""

    node_id: str | None = None
    action: str = "regenerate"
    reason: str = ""
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class RepairPlan:
    """Plan describing how to fix discovered issues without full rebuild."""

    id: str
    kind: RepairKind
    issues: list[str] = field(default_factory=list)
    invalidate_node_ids: list[str] = field(default_factory=list)
    keep_node_ids: list[str] = field(default_factory=list)
    actions: list[RepairAction] = field(default_factory=list)
    rationale: str = ""
    created_at: str = field(default_factory=utc_now_iso)

    @classmethod
    def create(cls, kind: RepairKind, rationale: str = "") -> RepairPlan:
        """Create an empty repair plan."""
        return cls(id=new_id("repair"), kind=kind, rationale=rationale)

    def add_invalidate(self, node_id: str, reason: str = "") -> None:
        """Mark a node for invalidation/regeneration."""
        if node_id not in self.invalidate_node_ids:
            self.invalidate_node_ids.append(node_id)
        self.actions.append(
            RepairAction(node_id=node_id, action="regenerate", reason=reason)
        )

    def add_keep(self, node_id: str) -> None:
        """Mark a node to keep (do not regenerate)."""
        if node_id not in self.keep_node_ids:
            self.keep_node_ids.append(node_id)


@dataclass(slots=True)
class ValidationReport:
    """Aggregated report over multiple quality results."""

    results: list[QualityResult] = field(default_factory=list)
    issues: list[Issue] = field(default_factory=list)

    @property
    def overall_gate(self) -> GateResult:
        """Worst gate among all results."""
        if any(r.gate == GateResult.BLOCK for r in self.results):
            return GateResult.BLOCK
        if any(r.gate == GateResult.WARN for r in self.results):
            return GateResult.WARN
        return GateResult.PASS

    def add(self, result: QualityResult) -> QualityResult:
        """Append a quality result and flatten issues."""
        self.results.append(result)
        self.issues.extend(result.issues)
        return result
