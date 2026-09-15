# SPDX-FileCopyrightText: 2026 zcbacxc
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Production Knowledge: stable rules harvested from history for the next Spec.

Production Knowledge is not Provenance. Provenance records what happened;
Production Knowledge distills reusable identity / style / continuity / quality
rules that re-enter the next Production Spec / Generation Spec.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from drama_forge.domain.common import MetadataBag, new_id, stable_hash


@dataclass(slots=True)
class ProductionKnowledge:
    """Versioned, reusable production rules for a story.

    Attributes:
        id: Knowledge bundle id.
        story_id: Story this knowledge belongs to.
        version: Monotonic knowledge version.
        character_identity: character_id -> stable identity facts.
        world_rules: Global world constraints.
        style_rules: Style / palette / render constraints.
        continuity_constraints: Cross-shot continuity requirements.
        accepted_decisions: Selected candidate / routing decisions worth reusing.
        quality_rules: Quality thresholds and gate preferences.
        repair_patterns: Observed repair patterns (issue type -> action hints).
        source_refs: Provenance references (artifact/execution ids).
        fingerprint: Content fingerprint for reuse checks.
        metadata: Free-form bag.
    """

    id: str
    story_id: str
    version: int = 1
    character_identity: dict[str, dict[str, Any]] = field(default_factory=dict)
    world_rules: list[str] = field(default_factory=list)
    style_rules: dict[str, Any] = field(default_factory=dict)
    continuity_constraints: dict[str, Any] = field(default_factory=dict)
    accepted_decisions: list[dict[str, Any]] = field(default_factory=list)
    quality_rules: dict[str, Any] = field(default_factory=dict)
    repair_patterns: list[dict[str, Any]] = field(default_factory=list)
    source_refs: list[str] = field(default_factory=list)
    fingerprint: str = ""
    metadata: MetadataBag = field(default_factory=MetadataBag)

    @classmethod
    def create(cls, story_id: str, **kwargs: Any) -> ProductionKnowledge:
        """Create a knowledge bundle with a generated id.

        Args:
                    story_id: str
                    **kwargs

        Returns:
                    ProductionKnowledge
        """
        bundle = cls(id=new_id("know"), story_id=story_id, **kwargs)
        bundle.fingerprint = bundle.compute_fingerprint()
        return bundle

    def compute_fingerprint(self) -> str:
        """Fingerprint of distilled rules (excludes source_refs / ids).

        Returns:
                    str
        """
        return stable_hash(
            {
                "story_id": self.story_id,
                "version": self.version,
                "character_identity": self.character_identity,
                "world_rules": self.world_rules,
                "style_rules": self.style_rules,
                "continuity_constraints": self.continuity_constraints,
                "quality_rules": self.quality_rules,
                "repair_patterns": self.repair_patterns,
            }
        )

    def recompute_fingerprint(self) -> str:
        """Refresh and return fingerprint.

        Returns:
                    str
        """
        self.fingerprint = self.compute_fingerprint()
        return self.fingerprint

    def merge(self, other: ProductionKnowledge) -> ProductionKnowledge:
        """Merge another bundle into a new version (other wins on conflicts).

        Args:
                    other: ProductionKnowledge

        Returns:
                    ProductionKnowledge
        """
        characters = dict(self.character_identity)
        characters.update(other.character_identity)
        style = dict(self.style_rules)
        style.update(other.style_rules)
        continuity = dict(self.continuity_constraints)
        continuity.update(other.continuity_constraints)
        quality = dict(self.quality_rules)
        quality.update(other.quality_rules)
        world = list(dict.fromkeys([*self.world_rules, *other.world_rules]))
        merged = ProductionKnowledge.create(
            story_id=self.story_id or other.story_id,
            version=max(self.version, other.version) + 1,
            character_identity=characters,
            world_rules=world,
            style_rules=style,
            continuity_constraints=continuity,
            accepted_decisions=[*self.accepted_decisions, *other.accepted_decisions],
            quality_rules=quality,
            repair_patterns=[*self.repair_patterns, *other.repair_patterns],
            source_refs=list(dict.fromkeys([*self.source_refs, *other.source_refs])),
        )
        return merged

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dict.

        Returns:
                    dict[str, Any]
        """
        return {
            "id": self.id,
            "story_id": self.story_id,
            "version": self.version,
            "character_identity": self.character_identity,
            "world_rules": self.world_rules,
            "style_rules": self.style_rules,
            "continuity_constraints": self.continuity_constraints,
            "accepted_decisions": self.accepted_decisions,
            "quality_rules": self.quality_rules,
            "repair_patterns": self.repair_patterns,
            "source_refs": self.source_refs,
            "fingerprint": self.fingerprint,
            "metadata": dict(self.metadata.data),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ProductionKnowledge:
        """Deserialize from a plain dict.

        Args:
                    data: dict[str, Any]

        Returns:
                    ProductionKnowledge
        """
        meta = data.get("metadata") or {}
        return cls(
            id=str(data.get("id") or new_id("know")),
            story_id=str(data.get("story_id") or ""),
            version=int(data.get("version") or 1),
            character_identity=dict(data.get("character_identity") or {}),
            world_rules=list(data.get("world_rules") or []),
            style_rules=dict(data.get("style_rules") or {}),
            continuity_constraints=dict(data.get("continuity_constraints") or {}),
            accepted_decisions=list(data.get("accepted_decisions") or []),
            quality_rules=dict(data.get("quality_rules") or {}),
            repair_patterns=list(data.get("repair_patterns") or []),
            source_refs=list(data.get("source_refs") or []),
            fingerprint=str(data.get("fingerprint") or ""),
            metadata=MetadataBag(data=dict(meta)),
        )


def harvest_knowledge_from_story(
    story: Any,
    *,
    selected_candidates: list[Any] | None = None,
    decision_records: list[Any] | None = None,
    quality_results: list[Any] | None = None,
    repair_plans: list[Any] | None = None,
    source_refs: list[str] | None = None,
) -> ProductionKnowledge:
    """Distill Production Knowledge from a story + one execution outcome.

    Args:
        story: Compiled Story domain object.
        selected_candidates: Selected Candidate objects from the run.
        decision_records: DecisionRecord objects (routing/selection).
        quality_results: QualityResult objects.
        repair_plans: RepairPlan objects applied or proposed.
        source_refs: Optional artifact/execution ids for provenance.

    Returns:
        A new ProductionKnowledge bundle grounded in this story.
    """
    character_identity: dict[str, dict[str, Any]] = {}
    for character in getattr(story, "characters", {}).values():
        character_identity[character.id] = {
            "name": character.name,
            "appearance": character.appearance,
            "voice_identity": character.voice_identity,
            "costume_state": character.costume_state,
        }

    world = getattr(story, "world", None)
    world_rules = list(getattr(world, "rules", []) or [])
    style_rules: dict[str, Any] = {}
    if world is not None:
        if getattr(world, "style", ""):
            style_rules["style"] = world.style

    continuity: dict[str, Any] = {
        "characters": sorted(character_identity),
        "enforce_character_identity": True,
        "enforce_scene_continuity": True,
    }

    accepted: list[dict[str, Any]] = []
    for record in decision_records or []:
        if hasattr(record, "to_dict"):
            accepted.append(
                {
                    "decision_type": getattr(record, "decision_type", ""),
                    "subject": getattr(record, "subject", ""),
                    "selected": getattr(record, "selected", ""),
                    "reason": getattr(record, "reason", ""),
                }
            )
    for candidate in selected_candidates or []:
        artifact = getattr(candidate, "artifact", None)
        accepted.append(
            {
                "decision_type": "candidate_selection",
                "subject": getattr(candidate, "node_id", ""),
                "selected": getattr(candidate, "id", ""),
                "artifact_id": getattr(artifact, "id", None),
            }
        )

    quality_rules: dict[str, Any] = {
        "enforce_continuity": True,
        "block_on_character_continuity": True,
    }
    for result in quality_results or []:
        gate = getattr(result, "gate", None)
        if gate is not None and str(getattr(gate, "value", gate)).upper() == "BLOCK":
            quality_rules["last_block_gate"] = True

    repair_patterns: list[dict[str, Any]] = []
    for plan in repair_plans or []:
        kinds = [str(k) for k in getattr(plan, "actions", []) or []]
        repair_patterns.append(
            {
                "kind": str(getattr(plan, "kind", "")),
                "actions": kinds,
                "invalidate_count": len(getattr(plan, "invalidate_node_ids", []) or []),
            }
        )

    return ProductionKnowledge.create(
        story_id=getattr(story, "id", ""),
        character_identity=character_identity,
        world_rules=world_rules,
        style_rules=style_rules,
        continuity_constraints=continuity,
        accepted_decisions=accepted,
        quality_rules=quality_rules,
        repair_patterns=repair_patterns,
        source_refs=list(source_refs or []),
    )


def apply_knowledge_to_continuity_constraints(
    knowledge: ProductionKnowledge,
) -> dict[str, Any]:
    """Map knowledge into constraints usable by generation specs / validators.

    Args:
            knowledge: ProductionKnowledge

    Returns:
            dict[str, Any]
    """
    constraints = dict(knowledge.continuity_constraints)
    if knowledge.style_rules:
        constraints.setdefault("style", knowledge.style_rules.get("style", ""))
        constraints["style_rules"] = dict(knowledge.style_rules)
    if knowledge.character_identity:
        constraints["character_identity"] = dict(knowledge.character_identity)
    return constraints
