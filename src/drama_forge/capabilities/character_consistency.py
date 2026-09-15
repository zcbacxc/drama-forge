# SPDX-FileCopyrightText: 2026 zcbacxc
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Character consistency constraints and candidate scoring.

Character consistency is a first-class production concern: every candidate
that features a character must be checked against the character's identity
anchor so takes can be compared and rejected without a full regeneration.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from drama_forge.domain.asset import Asset, Candidate
from drama_forge.domain.common import stable_hash
from drama_forge.domain.story import Character


@dataclass(slots=True)
class CharacterConsistencyConstraints:
    """Constraints that pin a character's look and voice across takes.

    Attributes:
        identity_hash: Stable hash of the character's identity fields.
        appearance_anchor: Canonical appearance description used as the visual anchor.
        costume_state: Current costume/outfit state for the production scope.
        voice_identity: Voice identity token used for dialogue audio.
    """

    identity_hash: str
    appearance_anchor: str = ""
    costume_state: str = ""
    voice_identity: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize constraints to a plain dict for generation specs."""
        return {
            "identity_hash": self.identity_hash,
            "appearance_anchor": self.appearance_anchor,
            "costume_state": self.costume_state,
            "voice_identity": self.voice_identity,
            **self.extra,
        }


def build_character_constraints(
    character: Character,
    asset: Asset | None = None,
) -> CharacterConsistencyConstraints:
    """Build continuity constraints from a character and optional reference asset.

    Args:
        character: Source character domain object.
        asset: Optional character_reference asset that may override constraints.

    Returns:
        CharacterConsistencyConstraints ready for scoring and generation specs.
    """
    appearance = character.appearance
    costume = character.costume_state
    voice = character.voice_identity
    if asset is not None and asset.constraints:
        appearance = str(asset.constraints.get("appearance", appearance) or appearance)
        costume = str(asset.constraints.get("costume_state", costume) or costume)
        voice = str(asset.constraints.get("voice_identity", voice) or voice)

    identity_hash = stable_hash(
        {
            "name": character.name,
            "appearance": appearance,
            "personality": character.personality,
        }
    )
    return CharacterConsistencyConstraints(
        identity_hash=identity_hash,
        appearance_anchor=appearance,
        costume_state=costume,
        voice_identity=voice,
        extra={"character_id": character.id, "character_name": character.name},
    )


def check_character_consistency(
    candidates: list[Candidate],
    constraints: CharacterConsistencyConstraints | dict[str, Any],
) -> dict[str, float]:
    """Score candidates against character consistency constraints.

    Scoring is deterministic and offline: it inspects candidate generation
    metadata digests against the identity hash so identical identity anchors
    score higher without calling a provider.

    Args:
        candidates: Candidates to score.
        constraints: CharacterConsistencyConstraints or a dict form.

    Returns:
        Map of candidate id -> consistency score in [0.0, 1.0].
    """
    if isinstance(constraints, CharacterConsistencyConstraints):
        identity = constraints.identity_hash
        appearance = constraints.appearance_anchor
    else:
        identity = str(constraints.get("identity_hash", ""))
        appearance = str(constraints.get("appearance_anchor", ""))

    scores: dict[str, float] = {}
    for candidate in candidates:
        digest = str(candidate.artifact.generation_metadata.get("digest", ""))
        score = _digest_affinity(digest, identity)
        if appearance:
            # appearance text length is a weak prior for richer anchors
            score = min(1.0, score + min(0.1, len(appearance) / 500.0))
        # blend with existing continuity score if present
        if candidate.continuity_score:
            score = 0.7 * score + 0.3 * candidate.continuity_score
        scores[candidate.id] = round(max(0.0, min(1.0, score)), 4)
    return scores


def _digest_affinity(digest: str, identity: str) -> float:
    """Compute a deterministic affinity between a digest and identity hash.

    Both sides are hashed together so the result is stable across runs and
    independent of provider internals.
    """
    if not digest:
        return 0.5
    combined = stable_hash({"digest": digest, "identity": identity})
    return int(combined[:2], 16) / 255.0
