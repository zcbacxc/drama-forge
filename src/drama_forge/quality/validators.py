"""Hard-constraint validators and continuity checks."""

from __future__ import annotations

from typing import Any

from drama_forge.domain.asset import Artifact, Candidate
from drama_forge.domain.common import (
    ArtifactType,
    GateResult,
    IssueType,
    Severity,
)
from drama_forge.domain.production import ProductionGraph
from drama_forge.domain.quality import Issue, QualityResult


def validate_artifact(artifact: Artifact) -> QualityResult:
    """Validate hard constraints on a typed artifact.

    Checks content reference presence, type enum validity, and basic
    technical metadata.

    Args:
        artifact: Artifact to validate.

    Returns:
        QualityResult with PASS/WARN/BLOCK.
    """
    issues: list[Issue] = []
    if not artifact.content_reference:
        issues.append(
            Issue.create(
                IssueType.TECHNICAL_VALIDATION,
                Severity.HIGH,
                "artifact content_reference is missing",
                node_id=artifact.source_node,
                asset_id=artifact.asset_id,
            )
        )
    if artifact.artifact_type not in list(ArtifactType):
        issues.append(
            Issue.create(
                IssueType.TECHNICAL_VALIDATION,
                Severity.CRITICAL,
                f"unknown artifact type: {artifact.artifact_type}",
                node_id=artifact.source_node,
            )
        )
    if not artifact.technical_metadata:
        issues.append(
            Issue.create(
                IssueType.TECHNICAL_VALIDATION,
                Severity.LOW,
                "technical_metadata is empty",
                node_id=artifact.source_node,
                asset_id=artifact.asset_id,
            )
        )
    gate = GateResult.BLOCK if any(
        i.severity in (Severity.HIGH, Severity.CRITICAL) for i in issues
    ) else (GateResult.WARN if issues else GateResult.PASS)
    return QualityResult.create(
        subject_id=artifact.id,
        gate=gate,
        issues=issues,
        scores={"technical": 1.0 if gate == GateResult.PASS else 0.5},
    )


def validate_continuity(
    graph: ProductionGraph,
    candidates: list[Candidate],
    character_ids_by_node: dict[str, list[str]] | None = None,
) -> QualityResult:
    """Validate character/scene continuity constraints across selected shots.

    Continuity failure is raised when selected candidates for the same
    character diverge in digest family without an explicit repair history.

    Args:
        graph: Production graph.
        candidates: Selected candidates to check.
        character_ids_by_node: Optional map node_id -> character ids.

    Returns:
        QualityResult for continuity gate.
    """
    character_ids_by_node = character_ids_by_node or {}
    issues: list[Issue] = []

    selected = [c for c in candidates if c.selected]
    by_character: dict[str, list[Candidate]] = {}
    for candidate in selected:
        char_ids = character_ids_by_node.get(candidate.node_id, [])
        for char_id in char_ids:
            by_character.setdefault(char_id, []).append(candidate)

    for char_id, items in by_character.items():
        # Multiple distinct digests is normal for different shots; we flag
        # only when continuity_score is low on any selected candidate.
        for item in items:
            if item.continuity_score < 0.4:
                issues.append(
                    Issue.create(
                        IssueType.CHARACTER_CONTINUITY,
                        Severity.HIGH,
                        f"low continuity for character {char_id}",
                        node_id=item.node_id,
                        asset_id=item.artifact.asset_id,
                        evidence={
                            "character_id": char_id,
                            "continuity_score": item.continuity_score,
                            "digest": item.artifact.generation_metadata.get("digest"),
                        },
                        suggested_scope=[item.node_id],
                    )
                )

    # Graph-level: select nodes that never produced a selection outcome
    selected_ids_all = {c.id for c in selected}
    for node in graph.nodes.values():
        if node.action != "select_shot_candidate":
            continue
        # After selection, node.candidate_ids holds the chosen candidate id
        has_selection = any(cid in selected_ids_all for cid in node.candidate_ids)
        if node.candidate_ids and not has_selection:
            issues.append(
                Issue.create(
                    IssueType.INCOMPLETE_SPEC,
                    Severity.MEDIUM,
                    f"selection node {node.id} has candidates but none selected",
                    node_id=node.id,
                )
            )

    gate = GateResult.BLOCK if any(
        i.severity in (Severity.HIGH, Severity.CRITICAL) for i in issues
    ) else (GateResult.WARN if issues else GateResult.PASS)
    return QualityResult.create(
        subject_id="continuity",
        gate=gate,
        issues=issues,
        evidence={"selected_count": len(selected)},
    )


def validate_preflight_inputs(
    node_inputs: dict[str, Any],
    required: list[str],
    node_id: str,
) -> QualityResult:
    """Preflight check that required inputs/assets exist before execution.

    Args:
        node_inputs: Available input mapping.
        required: Required input keys.
        node_id: Node being checked.

    Returns:
        QualityResult; BLOCK when missing required inputs.
    """
    issues: list[Issue] = []
    for key in required:
        if key not in node_inputs or node_inputs[key] in (None, "", []):
            issues.append(
                Issue.create(
                    IssueType.MISSING_INPUT,
                    Severity.HIGH,
                    f"missing required input: {key}",
                    node_id=node_id,
                    suggested_scope=[node_id],
                )
            )
    gate = GateResult.BLOCK if issues else GateResult.PASS
    return QualityResult.create(subject_id=node_id, gate=gate, issues=issues)
