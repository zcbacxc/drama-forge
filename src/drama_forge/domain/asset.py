# SPDX-FileCopyrightText: 2026 zcbacxc
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Asset vs Artifact domain separation."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from drama_forge.domain.common import (
    ArtifactType,
    MetadataBag,
    QualityState,
    new_id,
    stable_hash,
)


def utc_now_iso() -> str:
    """Return current UTC time as ISO-8601 string."""
    return datetime.now(UTC).isoformat()


@dataclass(slots=True)
class Asset:
    """Semantic production identity (what), independent of any single file."""

    id: str
    kind: str
    name: str
    version: int = 1
    subject_id: str | None = None
    constraints: dict[str, Any] = field(default_factory=dict)
    reference_artifact_ids: list[str] = field(default_factory=list)
    metadata: MetadataBag = field(default_factory=MetadataBag)

    @classmethod
    def create(cls, kind: str, name: str, **kwargs: object) -> Asset:
        """Create an asset identity with a content-stable id.

        The id is derived from kind + name + subject_id so replanning the
        same story content reuses the same asset identity and fingerprints.
        """
        subject_id = kwargs.get("subject_id")
        key = {
            "kind": kind,
            "name": name,
            "subject_id": subject_id if isinstance(subject_id, str) else "",
        }
        asset_id = f"asset_{stable_hash(key)[:16]}"
        return cls(id=asset_id, kind=kind, name=name, **kwargs)  # type: ignore[arg-type]

    def bump_version(self) -> Asset:
        """Return a new version of this asset identity."""
        self.version += 1
        return self

    def fingerprint(self) -> str:
        """Fingerprint of semantic identity + constraints + version."""
        return stable_hash(
            {
                "id": self.id,
                "kind": self.kind,
                "name": self.name,
                "version": self.version,
                "subject_id": self.subject_id,
                "constraints": self.constraints,
            }
        )


@dataclass(slots=True)
class Provenance:
    """How an artifact was produced (traceability record)."""

    story_id: str | None = None
    story_version: int | None = None
    asset_ids: list[str] = field(default_factory=list)
    graph_node_id: str | None = None
    execution_id: str | None = None
    generation_spec_hash: str | None = None
    provider_id: str | None = None
    model_id: str | None = None
    candidate_id: str | None = None
    quality_results: list[str] = field(default_factory=list)
    repair_history: list[str] = field(default_factory=list)
    inputs: dict[str, str] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        """Serialize provenance for persistence/trace."""
        return {
            "story_id": self.story_id,
            "story_version": self.story_version,
            "asset_ids": list(self.asset_ids),
            "graph_node_id": self.graph_node_id,
            "execution_id": self.execution_id,
            "generation_spec_hash": self.generation_spec_hash,
            "provider_id": self.provider_id,
            "model_id": self.model_id,
            "candidate_id": self.candidate_id,
            "quality_results": list(self.quality_results),
            "repair_history": list(self.repair_history),
            "inputs": dict(self.inputs),
            "created_at": self.created_at,
        }


@dataclass(slots=True)
class Artifact:
    """Typed generation result (file + contract + lifecycle)."""

    id: str
    artifact_type: ArtifactType
    content_reference: str
    source_node: str | None = None
    asset_id: str | None = None
    schema_version: str = "1.0"
    technical_metadata: dict[str, Any] = field(default_factory=dict)
    provider_metadata: dict[str, Any] = field(default_factory=dict)
    generation_metadata: dict[str, Any] = field(default_factory=dict)
    quality_state: QualityState = QualityState.UNEVALUATED
    provenance: Provenance = field(default_factory=Provenance)
    created_at: str = field(default_factory=utc_now_iso)

    @classmethod
    def create(
        cls,
        artifact_type: ArtifactType,
        content_reference: str,
        **kwargs: object,
    ) -> Artifact:
        """Create a typed artifact."""
        return cls(
            id=new_id("art"),
            artifact_type=artifact_type,
            content_reference=content_reference,
            **kwargs,  # type: ignore[arg-type]
        )

    def fingerprint(self) -> str:
        """Fingerprint of production conditions (not raw bytes)."""
        return stable_hash(
            {
                "type": self.artifact_type.value,
                "content_reference": self.content_reference,
                "source_node": self.source_node,
                "asset_id": self.asset_id,
                "generation_metadata": self.generation_metadata,
            }
        )


@dataclass(slots=True)
class Candidate:
    """One take / candidate result for a production node."""

    id: str
    node_id: str
    artifact: Artifact
    quality_score: float = 0.0
    constraint_score: float = 0.0
    continuity_score: float = 0.0
    technical_score: float = 0.0
    selected: bool = False
    metadata: MetadataBag = field(default_factory=MetadataBag)
    created_at: str = field(default_factory=utc_now_iso)

    @classmethod
    def create(cls, node_id: str, artifact: Artifact, **kwargs: object) -> Candidate:
        """Create a candidate for a node."""
        return cls(id=new_id("cand"), node_id=node_id, artifact=artifact, **kwargs)  # type: ignore[arg-type]

    @property
    def total_score(self) -> float:
        """Weighted aggregate score used for ranking."""
        return (
            0.35 * self.quality_score
            + 0.25 * self.constraint_score
            + 0.25 * self.continuity_score
            + 0.15 * self.technical_score
        )


@dataclass(slots=True)
class CandidateSet:
    """All candidates produced for one production node."""

    node_id: str
    candidates: list[Candidate] = field(default_factory=list)

    def add(self, candidate: Candidate) -> Candidate:
        """Append a candidate."""
        self.candidates.append(candidate)
        return candidate

    def rank(self) -> list[Candidate]:
        """Return candidates sorted by total score descending."""
        return sorted(self.candidates, key=lambda c: c.total_score, reverse=True)

    def best(self) -> Candidate | None:
        """Return the highest scoring candidate."""
        ranked = self.rank()
        return ranked[0] if ranked else None

    def select(self, candidate_id: str | None = None) -> Candidate | None:
        """Mark a candidate as selected (best if id omitted)."""
        target = None
        if candidate_id is None:
            target = self.best()
        else:
            target = next((c for c in self.candidates if c.id == candidate_id), None)
        if target is None:
            return None
        for c in self.candidates:
            c.selected = c.id == target.id
        target.artifact.quality_state = QualityState.SELECTED
        return target
