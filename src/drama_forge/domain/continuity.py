# SPDX-FileCopyrightText: 2026 zcbacxc
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Continuity constraint domain models.

Lightweight rule and report objects used by the capability layer and quality
runtime to express and evaluate continuity requirements without coupling to
any particular provider or evaluator implementation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from drama_forge.domain.asset import utc_now_iso
from drama_forge.domain.common import GateResult, IssueType, Severity, new_id


@dataclass(slots=True)
class ContinuityRule:
    """One continuity requirement over a production subject.

    Attributes:
        scope: What the rule applies to (character, scene, style, temporal).
        subject_id: Domain entity the rule is about (character id, scene id, ...).
        constraint_key: Named constraint field being enforced.
        expected_value: Expected value for the constraint.
        severity: Severity when the rule is violated.
    """

    id: str
    scope: str
    subject_id: str
    constraint_key: str
    expected_value: Any = None
    severity: Severity = Severity.MEDIUM
    message: str = ""

    @classmethod
    def create(
        cls,
        scope: str,
        subject_id: str,
        constraint_key: str,
        expected_value: Any = None,
        **kwargs: object,
    ) -> ContinuityRule:
        """Create a continuity rule with a generated id."""
        return cls(
            id=new_id("crule"),
            scope=scope,
            subject_id=subject_id,
            constraint_key=constraint_key,
            expected_value=expected_value,
            **kwargs,  # type: ignore[arg-type]
        )

    def to_issue_type(self) -> IssueType:
        """Map this rule's scope to a structured issue type."""
        mapping = {
            "character": IssueType.CHARACTER_CONTINUITY,
            "scene": IssueType.SCENE_CONTINUITY,
            "style": IssueType.STYLE_CONTINUITY,
            "temporal": IssueType.TEMPORAL_CONTINUITY,
        }
        return mapping.get(self.scope, IssueType.CHARACTER_CONTINUITY)

    def fingerprint(self) -> str:
        """Stable fingerprint for rule reuse/dedup."""
        from drama_forge.domain.common import stable_hash

        return stable_hash(
            {
                "scope": self.scope,
                "subject_id": self.subject_id,
                "constraint_key": self.constraint_key,
                "expected_value": self.expected_value,
            }
        )


@dataclass(slots=True)
class ContinuityFinding:
    """Outcome of checking one rule against one subject."""

    rule_id: str
    subject_ref: str
    passed: bool
    score: float = 1.0
    detail: str = ""


@dataclass(slots=True)
class ContinuityReport:
    """Aggregated continuity evaluation over a set of rules and findings."""

    id: str
    subject_id: str = ""
    gate: GateResult = GateResult.PASS
    findings: list[ContinuityFinding] = field(default_factory=list)
    scores: dict[str, float] = field(default_factory=dict)
    evidence: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now_iso)

    @classmethod
    def create(cls, subject_id: str = "") -> ContinuityReport:
        """Create an empty continuity report."""
        return cls(id=new_id("crep"), subject_id=subject_id)

    def add_finding(self, finding: ContinuityFinding) -> ContinuityFinding:
        """Append a finding and recompute the gate."""
        self.findings.append(finding)
        self._recompute_gate()
        return finding

    def _recompute_gate(self) -> None:
        """Recompute gate from current findings."""
        if any(not f.passed and f.score < 0.4 for f in self.findings):
            self.gate = GateResult.BLOCK
        elif any(not f.passed for f in self.findings):
            self.gate = GateResult.WARN
        else:
            self.gate = GateResult.PASS

    @property
    def passed(self) -> bool:
        """True when no finding failed."""
        return all(f.passed for f in self.findings)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the report for artifact payloads."""
        return {
            "id": self.id,
            "subject_id": self.subject_id,
            "gate": self.gate.value,
            "passed": self.passed,
            "finding_count": len(self.findings),
            "scores": dict(self.scores),
            "findings": [
                {
                    "rule_id": f.rule_id,
                    "subject_ref": f.subject_ref,
                    "passed": f.passed,
                    "score": f.score,
                    "detail": f.detail,
                }
                for f in self.findings
            ],
            "created_at": self.created_at,
        }
