# SPDX-FileCopyrightText: 2026 zcbacxc
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Capability layer: first-class generation and evaluation capabilities."""

from drama_forge.capabilities.audio import (
    DialogueAudioSpec,
    plan_dialogue_audio_nodes,
)
from drama_forge.capabilities.capability import (
    CapabilityRegistry,
    CapabilitySpec,
    default_capability_registry,
)
from drama_forge.capabilities.character_consistency import (
    CharacterConsistencyConstraints,
    build_character_constraints,
    check_character_consistency,
)
from drama_forge.capabilities.scene_consistency import (
    SceneConsistencyConstraints,
    build_scene_constraints,
    check_scene_consistency,
)

__all__ = [
    "CapabilityRegistry",
    "CapabilitySpec",
    "default_capability_registry",
    "CharacterConsistencyConstraints",
    "build_character_constraints",
    "check_character_consistency",
    "SceneConsistencyConstraints",
    "build_scene_constraints",
    "check_scene_consistency",
    "DialogueAudioSpec",
    "plan_dialogue_audio_nodes",
]
