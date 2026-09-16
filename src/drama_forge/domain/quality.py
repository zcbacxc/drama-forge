# SPDX-FileCopyrightText: 2026 zcbacxc
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Quality domain objects: issues, gates, repair plans."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

from drama_forge.domain.asset import utc_now_iso
from drama_forge.domain.common import (
    DimensionStatus,
    GateResult,
    IssueType,
    RepairKind,
    Severity,
    new_id,
)

# Statuses that may contribute to the overall arithmetic mean.
AVAILABLE_DIMENSION_STATUSES: frozenset[DimensionStatus] = frozenset(
    {DimensionStatus.MEASURED, DimensionStatus.PROXY}
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
        """Create a quality issue.

        Args:
                    issue_type: IssueType
                    severity: Severity
                    message: default ''
                    **kwargs

        Returns:
                    Issue
        """
        return cls(
            id=new_id("issue"),
            issue_type=issue_type,
            severity=severity,
            message=message,
            **kwargs,  # type: ignore[arg-type]
        )


@dataclass(slots=True)
class DimensionMeasurement:
    """One quality dimension score with provenance status.

    Attributes:
        name: Dimension identifier (e.g. quality_score).
        score: Normalized score, or None when unavailable/error.
        status: measured | proxy | unavailable | error.
        judge_source: Who/how produced the score (e.g. "heuristic", "provider").
        details: Free-form diagnostic payload.
    """

    name: str
    score: float | None = None
    status: DimensionStatus = DimensionStatus.UNAVAILABLE
    judge_source: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def is_available(self) -> bool:
        """Return True when this dimension may count toward overall.

        Returns:
                    bool
        """
        return (
            self.status in AVAILABLE_DIMENSION_STATUSES and self.score is not None
        )


def compute_overall_score(
    dimensions: Mapping[str, DimensionMeasurement] | Iterable[DimensionMeasurement],
) -> float | None:
    """Arithmetic mean over available dimensions only.

    Only measured/proxy dimensions with a non-None score enter the mean.
    unavailable/error dimensions are excluded from the denominator and are
    never coerced to 0. All unavailable (or empty) → None.

    Args:
        dimensions: Mapping of name → measurement, or an iterable of measurements.

    Returns:
        Overall score in the same scale as dimension scores, or None.
    """
    if isinstance(dimensions, Mapping):
        items: Iterable[DimensionMeasurement] = dimensions.values()
    else:
        items = dimensions
    available = [m.score for m in items if m.is_available() and m.score is not None]
    if not available:
        return None
    return sum(available) / len(available)


@dataclass(slots=True)
class QualityResult:
    """Outcome of validating/evaluating one subject.

    Attributes:
        id: Result identifier.
        subject_id: Evaluated subject (node / artifact / candidate set).
        gate: Gate outcome.
        scores: Flat score bag kept for backward compatibility.
        issues: Structured quality issues.
        evidence: Free-form evidence payload.
        created_at: ISO timestamp.
        dimensions: Optional per-dimension measurements with status/provenance.
            Absent/empty on legacy validators — callers must tolerate missing.
        overall: Optional mean of available dimensions; None when no measured
            or proxy dimension has a score. Never treats unavailable as 0.
    """

    id: str
    subject_id: str
    gate: GateResult
    scores: dict[str, float] = field(default_factory=dict)
    issues: list[Issue] = field(default_factory=list)
    evidence: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now_iso)
    dimensions: dict[str, DimensionMeasurement] = field(default_factory=dict)
    overall: float | None = None

    @classmethod
    def create(cls, subject_id: str, gate: GateResult, **kwargs: object) -> QualityResult:
        """Create a quality result.

        Args:
                    subject_id: str
                    gate: GateResult
                    **kwargs

        Returns:
                    QualityResult
        """
        return cls(id=new_id("qr"), subject_id=subject_id, gate=gate, **kwargs)  # type: ignore[arg-type]

    def recompute_overall(self) -> float | None:
        """Recompute overall from dimensions and store it on self.

        Returns:
                    float | None
        """
        self.overall = compute_overall_score(self.dimensions)
        return self.overall


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
        """Create an empty repair plan.

        Args:
                    kind: RepairKind
                    rationale: default ''

        Returns:
                    RepairPlan
        """
        return cls(id=new_id("repair"), kind=kind, rationale=rationale)

    def add_invalidate(self, node_id: str, reason: str = "") -> None:
        """Mark a node for invalidation/regeneration.

        Args:
                    node_id: str
                    reason: default ''

        Returns:
                    None
        """
        if node_id not in self.invalidate_node_ids:
            self.invalidate_node_ids.append(node_id)
        self.actions.append(
            RepairAction(node_id=node_id, action="regenerate", reason=reason)
        )

    def add_keep(self, node_id: str) -> None:
        """Mark a node to keep (do not regenerate).

        Args:
                    node_id: str

        Returns:
                    None
        """
        if node_id not in self.keep_node_ids:
            self.keep_node_ids.append(node_id)


@dataclass(slots=True)
class ValidationReport:
    """Aggregated report over multiple quality results."""

    results: list[QualityResult] = field(default_factory=list)
    issues: list[Issue] = field(default_factory=list)

    @property
    def overall_gate(self) -> GateResult:
        """Worst gate among all results.

        Returns:
                    GateResult
        """
        if any(r.gate == GateResult.BLOCK for r in self.results):
            return GateResult.BLOCK
        if any(r.gate == GateResult.WARN for r in self.results):
            return GateResult.WARN
        return GateResult.PASS

    def add(self, result: QualityResult) -> QualityResult:
        """Append a quality result and flatten issues.

        Args:
                    result: QualityResult

        Returns:
                    QualityResult
        """
        self.results.append(result)
        self.issues.extend(result.issues)
        return result
