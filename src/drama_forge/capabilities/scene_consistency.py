# SPDX-FileCopyrightText: 2026 zcbacxc
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Scene continuity constraints: location, lighting, and prop state."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from drama_forge.domain.asset import Asset, Candidate
from drama_forge.domain.common import stable_hash
from drama_forge.domain.story import Scene


@dataclass(slots=True)
class SceneConsistencyConstraints:
    """Constraints that keep a scene visually and spatially coherent.

    Attributes:
        location: Canonical location name/label.
        lighting: Lighting description (time of day, mood, sources).
        props: Key prop names expected to remain consistent in the scene.
        style: Global style token applied to the scene.
    """

    location: str = ""
    lighting: str = ""
    props: list[str] = field(default_factory=list)
    style: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize constraints to a plain dict for generation specs.

        Returns:
                    dict[str, Any]
        """
        return {
            "location": self.location,
            "lighting": self.lighting,
            "props": list(self.props),
            "style": self.style,
            **self.extra,
        }


def build_scene_constraints(
    scene: Scene,
    asset: Asset | None = None,
    style: str = "",
    props: list[str] | None = None,
) -> SceneConsistencyConstraints:
    """Build scene continuity constraints.

    Args:
        scene: Source scene domain object.
        asset: Optional scene_reference asset that may override constraints.
        style: Global production style to embed.
        props: Explicit prop list; defaults to empty.

    Returns:
        SceneConsistencyConstraints for generation specs and scoring.
    """
    location = scene.location
    description = scene.description
    if asset is not None and asset.constraints:
        location = str(asset.constraints.get("location", location) or location)
        description = str(
            asset.constraints.get("description", description) or description
        )

    return SceneConsistencyConstraints(
        location=location,
        lighting=description,
        props=list(props or []),
        style=style,
        extra={"scene_id": scene.id, "scene_index": scene.index},
    )


def check_scene_consistency(
    candidates: list[Candidate],
    constraints: SceneConsistencyConstraints | dict[str, Any],
) -> dict[str, float]:
    """Score candidates against scene continuity constraints.

    Uses a deterministic digest/identity affinity so scores are stable
    offline without provider calls.

    Args:
        candidates: Candidates to score.
        constraints: SceneConsistencyConstraints or dict form.

    Returns:
        Map of candidate id -> consistency score in [0.0, 1.0].
    """
    if isinstance(constraints, SceneConsistencyConstraints):
        location = constraints.location
        style = constraints.style
    else:
        location = str(constraints.get("location", ""))
        style = str(constraints.get("style", ""))

    scene_key = stable_hash({"location": location, "style": style})
    scores: dict[str, float] = {}
    for candidate in candidates:
        digest = str(candidate.artifact.generation_metadata.get("digest", ""))
        if not digest:
            scores[candidate.id] = 0.5
            continue
        combined = stable_hash({"digest": digest, "scene": scene_key})
        base = int(combined[:2], 16) / 255.0
        if candidate.continuity_score:
            base = 0.7 * base + 0.3 * candidate.continuity_score
        scores[candidate.id] = round(max(0.0, min(1.0, base)), 4)
    return scores
