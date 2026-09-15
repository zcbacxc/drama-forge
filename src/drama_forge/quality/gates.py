# SPDX-FileCopyrightText: 2026 zcbacxc
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Quality gate aggregation."""

from __future__ import annotations

from drama_forge.domain.common import GateResult, Severity
from drama_forge.domain.quality import Issue, QualityResult


def gate_from_issues(issues: list[Issue]) -> GateResult:
    """Derive gate result from issue severities.

    Args:
            issues: list[Issue]

    Returns:
            GateResult
    """
    if any(i.severity in (Severity.HIGH, Severity.CRITICAL) for i in issues):
        return GateResult.BLOCK
    if issues:
        return GateResult.WARN
    return GateResult.PASS


def combine_gates(results: list[QualityResult]) -> GateResult:
    """Combine multiple quality results into an overall gate.

    Args:
            results: list[QualityResult]

    Returns:
            GateResult
    """
    if any(r.gate == GateResult.BLOCK for r in results):
        return GateResult.BLOCK
    if any(r.gate == GateResult.WARN for r in results):
        return GateResult.WARN
    return GateResult.PASS
