# SPDX-FileCopyrightText: 2026 zcbacxc
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Dialogue audio planning: attach TTS/dialogue nodes after shot selection."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from drama_forge.domain.asset import Asset
from drama_forge.domain.production import (
    CanonicalGenerationSpec,
    GraphEdge,
    GraphNode,
    ProductionGraph,
)
from drama_forge.domain.story import Story


@dataclass(slots=True)
class DialogueAudioSpec:
    """Specification for one dialogue audio line.

    Attributes:
        text: Dialogue text to synthesize.
        character_voice: Voice identity token for the speaking character.
        duration_seconds: Target duration of the audio clip.
        character_id: Optional speaking character id.
    """

    text: str
    character_voice: str = ""
    duration_seconds: float = 0.0
    character_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_generation_inputs(self) -> dict[str, Any]:
        """Convert to provider-facing generation inputs.

        Returns:
                    dict[str, Any]
        """
        return {
            "text": self.text,
            "character_voice": self.character_voice,
            "duration_seconds": self.duration_seconds,
            "character_id": self.character_id,
        }


def estimate_dialogue_duration(text: str, words_per_second: float = 2.5) -> float:
    """Estimate spoken duration from dialogue text.

    Args:
        text: Dialogue text.
        words_per_second: Speaking rate; defaults to a neutral pace.

    Returns:
        Estimated duration in seconds (minimum 1.0).
    """
    words = len(text.split()) if text else 0
    if words == 0:
        # CJK dialogue may not use spaces; fall back to character heuristic
        words = max(1, len(text) // 2)
    return max(1.0, round(words / max(0.1, words_per_second), 2))


def plan_dialogue_audio_nodes(
    story: Story,
    graph: ProductionGraph,
    assets: dict[str, Asset] | None = None,
) -> list[GraphNode]:
    """Add generate_dialogue_audio nodes for shots that have dialogue.

    Each dialogue audio node depends on the corresponding select_shot_candidate
    node so voice synthesis uses the selected take. If a dialogue audio node
    already exists for the shot, it is skipped (idempotent).

    Args:
        story: Compiled story providing character voice identities.
        graph: Production graph to extend in place.
        assets: Optional asset map; new dialogue_audio assets are registered here.

    Returns:
        List of dialogue audio nodes that exist after planning (new or prior).
    """
    select_by_shot_key: dict[str, GraphNode] = {}
    for node in graph.nodes.values():
        if node.action == "select_shot_candidate":
            # name format: shot_select:{scene}.{shot}
            select_by_shot_key[node.name] = node

    created: list[GraphNode] = []
    for episode in story.episodes:
        for scene in episode.scenes:
            for shot in scene.shots:
                dialogue = (shot.dialogue or "").strip()
                if not dialogue:
                    continue
                node_name = f"dialogue_audio:{scene.index}.{shot.index}"
                existing = next(
                    (n for n in graph.nodes.values() if n.name == node_name),
                    None,
                )
                if existing is not None:
                    created.append(existing)
                    continue

                select_name = f"shot_select:{scene.index}.{shot.index}"
                select_node = select_by_shot_key.get(select_name)
                if select_node is None:
                    continue

                speaking_char_id = shot.character_ids[0] if shot.character_ids else None
                speaking_char = (
                    story.characters.get(speaking_char_id)
                    if speaking_char_id
                    else None
                )
                voice = speaking_char.voice_identity if speaking_char else ""
                duration = estimate_dialogue_duration(dialogue)

                spec = DialogueAudioSpec(
                    text=dialogue,
                    character_voice=voice,
                    duration_seconds=duration,
                    character_id=speaking_char_id,
                )

                audio_asset = Asset.create(
                    kind="dialogue_audio",
                    name=f"{scene.index}.{shot.index}",
                    subject_id=shot.id,
                    constraints={
                        "dialogue": dialogue,
                        "voice_identity": voice,
                        "duration_seconds": duration,
                    },
                )
                if assets is not None:
                    assets[audio_asset.id] = audio_asset

                audio_node = GraphNode.create(
                    name=node_name,
                    action="generate_dialogue_audio",
                    input_asset_ids=[audio_asset.id],
                    output_asset_id=audio_asset.id,
                )
                audio_node.generation_spec = CanonicalGenerationSpec(
                    node_id=audio_node.id,
                    capability="audio_generation",
                    character_asset_ids=(
                        [audio_asset.id]
                        if speaking_char_id
                        else []
                    ),
                    style_constraints=(
                        {"style": story.world.style}
                        if story.world and story.world.style
                        else {}
                    ),
                    continuity_constraints={
                        "characters": shot.character_ids,
                        "voice_identity": voice,
                    },
                    audio_requirements=spec.to_generation_inputs(),
                    output_requirements={
                        "media": "audio",
                        "duration_seconds": duration,
                    },
                    candidate_count=1,
                )
                graph.add_edge(GraphEdge.create(select_node.id, audio_node.id))
                graph.add_node(audio_node)
                created.append(audio_node)

    return created
