# SPDX-FileCopyrightText: 2026 zcbacxc
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Soft quality evaluators for candidates."""

from __future__ import annotations

import json
from typing import Any

from drama_forge.domain.asset import CandidateSet
from drama_forge.domain.common import DimensionStatus, GateResult, QualityState
from drama_forge.domain.quality import (
    DimensionMeasurement,
    QualityResult,
    compute_overall_score,
)

# Canonical evaluation dimensions applied to every candidate.
EVALUATION_DIMENSION_NAMES: tuple[str, ...] = (
    "quality_score",
    "constraint_score",
    "continuity_score",
    "technical_score",
)


def evaluate_candidates(
    candidate_set: CandidateSet,
    evaluation_payload: dict[str, Any] | None = None,
) -> QualityResult:
    """Apply evaluation scores onto candidates and rank them.

    Dimensions produced here carry provenance status:
    payload-provided scores are ``measured`` (judge_source=provider);
    digest-heuristic fallbacks are ``proxy`` (judge_source=heuristic).

    Args:
        candidate_set: Candidates produced for a node.
        evaluation_payload: Optional evaluator output with "scores" list.

    Returns:
        QualityResult summarizing evaluation, including dimensions/overall.
    """
    scores_by_index: dict[int, dict[str, float]] = {}
    if evaluation_payload:
        for row in evaluation_payload.get("scores", []):
            idx = int(row.get("candidate_index", -1))
            scores_by_index[idx] = {
                "quality_score": float(row.get("quality_score", 0.5)),
                "constraint_score": float(row.get("constraint_score", 0.5)),
                "continuity_score": float(row.get("continuity_score", 0.5)),
                "technical_score": float(row.get("technical_score", 0.5)),
            }

    # Per-candidate source flags so set-level dimension status is honest.
    used_heuristic: set[int] = set()
    used_provider: set[int] = set()

    for index, candidate in enumerate(candidate_set.candidates):
        scores = scores_by_index.get(index)
        if scores:
            candidate.quality_score = scores["quality_score"]
            candidate.constraint_score = scores["constraint_score"]
            candidate.continuity_score = scores["continuity_score"]
            candidate.technical_score = scores["technical_score"]
            used_provider.add(index)
        else:
            # fallback heuristic from digest — proxy measurement, not measured
            digest = str(
                candidate.artifact.generation_metadata.get("digest", "00")
            )
            try:
                value = int(digest[:2], 16) / 255.0
            except ValueError:
                value = 0.5
            candidate.quality_score = round(0.5 + 0.4 * value, 4)
            candidate.constraint_score = round(0.55 + 0.35 * value, 4)
            candidate.continuity_score = round(0.6 + 0.3 * value, 4)
            candidate.technical_score = round(0.7 + 0.2 * value, 4)
            used_heuristic.add(index)
        candidate.artifact.quality_state = QualityState.UNEVALUATED

    ranked = candidate_set.rank()
    avg_quality = (
        sum(c.quality_score for c in ranked) / len(ranked) if ranked else 0.0
    )
    gate = GateResult.PASS if ranked and avg_quality >= 0.4 else GateResult.WARN

    # Set-level status: measured only when every scored candidate came from
    # the provider payload; proxy if any digest heuristic was applied.
    if ranked and used_heuristic and not used_provider:
        dim_status = DimensionStatus.PROXY
        judge_source = "heuristic"
    elif ranked and used_provider and not used_heuristic:
        dim_status = DimensionStatus.MEASURED
        judge_source = "provider"
    elif ranked and used_provider:
        # mixed sources — treat as proxy so overall does not over-claim
        dim_status = DimensionStatus.PROXY
        judge_source = "heuristic+provider"
    else:
        dim_status = DimensionStatus.UNAVAILABLE
        judge_source = None

    dimensions: dict[str, DimensionMeasurement] = {}
    if ranked and dim_status in (DimensionStatus.MEASURED, DimensionStatus.PROXY):
        for name in EVALUATION_DIMENSION_NAMES:
            mean_score = sum(getattr(c, name) for c in ranked) / len(ranked)
            dimensions[name] = DimensionMeasurement(
                name=name,
                score=round(mean_score, 4),
                status=dim_status,
                judge_source=judge_source,
                details={"candidate_count": len(ranked)},
            )

    overall = compute_overall_score(dimensions)

    return QualityResult.create(
        subject_id=candidate_set.node_id,
        gate=gate,
        scores={"average_quality": avg_quality, "count": float(len(ranked))},
        evidence={
            "ranked": [
                {"id": c.id, "total": c.total_score} for c in ranked
            ],
            "provenance": {
                "judge_source": judge_source,
                "dimension_status": str(dim_status),
            },
        },
        dimensions=dimensions,
        overall=overall,
    )


def parse_evaluation_json(content: str | bytes) -> dict[str, Any]:
    """Parse evaluator JSON content safely.

    Args:
            content: str | bytes

    Returns:
            dict[str, Any]
    """
    if isinstance(content, bytes):
        content = content.decode("utf-8")
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return {"scores": []}
