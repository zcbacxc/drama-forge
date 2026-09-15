"""Quality gate aggregation."""

from __future__ import annotations

from drama_forge.domain.common import GateResult, Severity
from drama_forge.domain.quality import Issue, QualityResult


def gate_from_issues(issues: list[Issue]) -> GateResult:
    """Derive gate result from issue severities."""
    if any(i.severity in (Severity.HIGH, Severity.CRITICAL) for i in issues):
        return GateResult.BLOCK
    if issues:
        return GateResult.WARN
    return GateResult.PASS


def combine_gates(results: list[QualityResult]) -> GateResult:
    """Combine multiple quality results into an overall gate."""
    if any(r.gate == GateResult.BLOCK for r in results):
        return GateResult.BLOCK
    if any(r.gate == GateResult.WARN for r in results):
        return GateResult.WARN
    return GateResult.PASS
