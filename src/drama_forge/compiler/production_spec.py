# SPDX-FileCopyrightText: 2026 zcbacxc
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Build ProductionSpec from a Story."""

from __future__ import annotations

from typing import Any

from drama_forge.domain.production import ProductionSpec
from drama_forge.domain.story import Story


def build_production_spec(
    story: Story,
    style_constraints: dict[str, Any] | None = None,
) -> ProductionSpec:
    """Derive production requirements from story content.

    Args:
        story: Compiled story.
        style_constraints: Optional global style constraints.

    Returns:
        ProductionSpec describing what production needs.
    """
    spec = ProductionSpec.create(story_id=story.id, story_version=story.version)
    if style_constraints:
        spec.style_constraints = style_constraints
    elif story.world and story.world.style:
        spec.style_constraints = {"style": story.world.style}

    char_ids = list(story.characters.keys())
    spec.required_character_asset_ids = char_ids

    for episode in story.episodes:
        for scene in episode.scenes:
            spec.scene_requirements[scene.id] = {
                "location": scene.location,
                "description": scene.description,
                "character_ids": list(scene.character_ids),
            }
            spec.required_scene_asset_ids.append(scene.id)
            for shot in scene.shots:
                spec.shot_requirements[shot.id] = {
                    "description": shot.description,
                    "dialogue": shot.dialogue,
                    "duration_seconds": shot.duration_seconds,
                    "camera": shot.camera,
                    "character_ids": list(shot.character_ids),
                    "scene_id": scene.id,
                }

    spec.continuity_requirements = {
        "enforce_character_identity": True,
        "enforce_scene_continuity": True,
        "enforce_temporal_continuity": True,
    }
    return spec
