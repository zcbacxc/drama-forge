# SPDX-FileCopyrightText: 2026 zcbacxc
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Typed artifact store with provenance and fingerprint cache."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from drama_forge.domain.asset import Artifact, Provenance
from drama_forge.domain.common import ArtifactType


class ArtifactStore:
    """Store artifacts on filesystem with in-memory index + provenance."""

    def __init__(self, root: str | Path | None = None) -> None:
        self.root = Path(root) if root else Path.cwd() / ".drama_forge_artifacts"
        self.root.mkdir(parents=True, exist_ok=True)
        self._by_id: dict[str, Artifact] = {}
        self._fingerprint_index: dict[str, str] = {}

    def put(
        self,
        artifact: Artifact,
        content: bytes | str | None = None,
    ) -> Artifact:
        """Store artifact content and index it.

        Args:
            artifact: Typed artifact to store.
            content: Optional raw content; if provided, written under root.

        Returns:
            Stored artifact (content_reference resolved).
        """
        path = self.root / f"{artifact.id}.{_extension(artifact.artifact_type)}"
        if content is not None:
            if isinstance(content, str):
                path.write_text(content, encoding="utf-8")
            else:
                path.write_bytes(content)
            artifact.content_reference = str(path)
        elif not artifact.content_reference:
            # materialize placeholder metadata
            path.write_text(
                f"{artifact.artifact_type.value}:{artifact.generation_metadata}",
                encoding="utf-8",
            )
            artifact.content_reference = str(path)

        self._by_id[artifact.id] = artifact
        self._fingerprint_index[artifact.fingerprint()] = artifact.id
        return artifact

    def get(self, artifact_id: str) -> Artifact | None:
        """Fetch artifact by id."""
        return self._by_id.get(artifact_id)

    def find_by_fingerprint(self, fingerprint: str) -> Artifact | None:
        """Reuse lookup by production-condition fingerprint."""
        artifact_id = self._fingerprint_index.get(fingerprint)
        return self._by_id.get(artifact_id) if artifact_id else None

    def list_by_asset(self, asset_id: str) -> list[Artifact]:
        """List artifacts belonging to an asset."""
        return [a for a in self._by_id.values() if a.asset_id == asset_id]

    def all(self) -> list[Artifact]:
        """Return all stored artifacts."""
        return list(self._by_id.values())

    def attach_provenance(self, artifact_id: str, provenance: Provenance) -> Artifact | None:
        """Overwrite provenance on an artifact."""
        artifact = self._by_id.get(artifact_id)
        if artifact is None:
            return None
        artifact.provenance = provenance
        return artifact

    def trace(self, artifact_id: str) -> dict[str, Any] | None:
        """Return full provenance trace for an artifact."""
        artifact = self._by_id.get(artifact_id)
        if artifact is None:
            return None
        return {
            "artifact_id": artifact.id,
            "type": artifact.artifact_type.value,
            "content_reference": artifact.content_reference,
            "quality_state": artifact.quality_state.value,
            "provenance": artifact.provenance.to_dict(),
        }


def _extension(artifact_type: ArtifactType) -> str:
    """Map artifact type to file extension."""
    mapping = {
        ArtifactType.IMAGE: "png",
        ArtifactType.VIDEO: "mp4",
        ArtifactType.AUDIO: "wav",
        ArtifactType.SUBTITLE: "srt",
        ArtifactType.TIMELINE: "json",
        ArtifactType.MANIFEST: "json",
        ArtifactType.EVALUATION: "json",
        ArtifactType.JSON: "json",
        ArtifactType.TEXT: "txt",
    }
    return mapping.get(artifact_type, "bin")
