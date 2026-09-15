# SPDX-FileCopyrightText: 2026 zcbacxc
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Soft quality evaluators for candidates."""

from __future__ import annotations

import json
from typing import Any

from drama_forge.domain.asset import CandidateSet
from drama_forge.domain.common import GateResult, QualityState
from drama_forge.domain.quality import QualityResult


def evaluate_candidates(
    candidate_set: CandidateSet,
    evaluation_payload: dict[str, Any] | None = None,
) -> QualityResult:
    """Apply evaluation scores onto candidates and rank them.

    Args:
        candidate_set: Candidates produced for a node.
        evaluation_payload: Optional evaluator output with "scores" list.

    Returns:
        QualityResult summarizing evaluation.
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

    for index, candidate in enumerate(candidate_set.candidates):
        scores = scores_by_index.get(index)
        if scores:
            candidate.quality_score = scores["quality_score"]
            candidate.constraint_score = scores["constraint_score"]
            candidate.continuity_score = scores["continuity_score"]
            candidate.technical_score = scores["technical_score"]
        else:
            # fallback heuristic from digest
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
        candidate.artifact.quality_state = QualityState.UNEVALUATED

    ranked = candidate_set.rank()
    avg_quality = (
        sum(c.quality_score for c in ranked) / len(ranked) if ranked else 0.0
    )
    gate = GateResult.PASS if ranked and avg_quality >= 0.4 else GateResult.WARN
    return QualityResult.create(
        subject_id=candidate_set.node_id,
        gate=gate,
        scores={"average_quality": avg_quality, "count": float(len(ranked))},
        evidence={
            "ranked": [
                {"id": c.id, "total": c.total_score} for c in ranked
            ]
        },
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
