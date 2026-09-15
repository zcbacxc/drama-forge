# SPDX-FileCopyrightText: 2026 zcbacxc
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Canonical timeline model: tracks, segments, dialogues, transitions, markers."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from drama_forge.domain.common import new_id, stable_hash


@dataclass(slots=True)
class VideoSegment:
    """One video take placed on the video track."""

    id: str
    node_name: str
    node_id: str = ""
    artifact_id: str = ""
    candidate_id: str = ""
    start_seconds: float = 0.0
    duration_seconds: float = 0.0
    media: str = "video"
    digest: str = ""
    replaced: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def end_seconds(self) -> float:
        """Exclusive end time of this segment."""
        return self.start_seconds + self.duration_seconds

    @classmethod
    def create(
        cls,
        node_name: str,
        duration_seconds: float = 3.0,
        **kwargs: object,
    ) -> VideoSegment:
        """Create a video segment with a generated id."""
        return cls(
            id=new_id("vseg"),
            node_name=node_name,
            duration_seconds=duration_seconds,
            **kwargs,  # type: ignore[arg-type]
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize for deterministic JSON export."""
        return {
            "id": self.id,
            "node_name": self.node_name,
            "node_id": self.node_id,
            "artifact_id": self.artifact_id,
            "candidate_id": self.candidate_id,
            "start_seconds": self.start_seconds,
            "end_seconds": self.end_seconds,
            "duration_seconds": self.duration_seconds,
            "media": self.media,
            "digest": self.digest,
            "replaced": self.replaced,
        }


@dataclass(slots=True)
class AudioSegment:
    """One audio clip placed on the audio track."""

    id: str
    node_name: str
    node_id: str = ""
    artifact_id: str = ""
    start_seconds: float = 0.0
    duration_seconds: float = 0.0
    character_id: str | None = None
    text: str = ""
    media: str = "audio"
    digest: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def end_seconds(self) -> float:
        """Exclusive end time of this segment."""
        return self.start_seconds + self.duration_seconds

    @classmethod
    def create(
        cls,
        node_name: str,
        duration_seconds: float = 2.0,
        **kwargs: object,
    ) -> AudioSegment:
        """Create an audio segment with a generated id."""
        return cls(
            id=new_id("aseg"),
            node_name=node_name,
            duration_seconds=duration_seconds,
            **kwargs,  # type: ignore[arg-type]
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize for deterministic JSON export."""
        return {
            "id": self.id,
            "node_name": self.node_name,
            "node_id": self.node_id,
            "artifact_id": self.artifact_id,
            "start_seconds": self.start_seconds,
            "end_seconds": self.end_seconds,
            "duration_seconds": self.duration_seconds,
            "character_id": self.character_id,
            "text": self.text,
            "media": self.media,
            "digest": self.digest,
        }


@dataclass(slots=True)
class Dialogue:
    """Spoken line bound to a time range on the timeline."""

    character_id: str | None
    text: str
    start_seconds: float = 0.0
    duration_seconds: float = 0.0
    audio_segment_id: str | None = None

    @property
    def end_seconds(self) -> float:
        """Exclusive end time of this dialogue."""
        return self.start_seconds + self.duration_seconds

    def to_dict(self) -> dict[str, Any]:
        """Serialize for deterministic JSON export."""
        return {
            "character_id": self.character_id,
            "text": self.text,
            "start_seconds": self.start_seconds,
            "end_seconds": self.end_seconds,
            "duration_seconds": self.duration_seconds,
            "audio_segment_id": self.audio_segment_id,
        }


@dataclass(slots=True)
class Transition:
    """Transition between two adjacent video segments."""

    kind: str
    at_seconds: float
    from_segment_id: str = ""
    to_segment_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialize for deterministic JSON export."""
        return {
            "kind": self.kind,
            "at_seconds": self.at_seconds,
            "from_segment_id": self.from_segment_id,
            "to_segment_id": self.to_segment_id,
        }


@dataclass(slots=True)
class Marker:
    """Named point of interest on the timeline."""

    kind: str
    at_seconds: float
    label: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialize for deterministic JSON export."""
        return {
            "kind": self.kind,
            "at_seconds": self.at_seconds,
            "label": self.label,
        }


@dataclass(slots=True)
class Track:
    """Ordered list of segments of one media kind."""

    kind: str
    segments: list[Any] = field(default_factory=list)

    def add(self, segment: Any) -> Any:
        """Append a segment to the track."""
        self.segments.append(segment)
        return segment

    def to_dict(self) -> dict[str, Any]:
        """Serialize for deterministic JSON export."""
        return {
            "kind": self.kind,
            "segments": [s.to_dict() for s in self.segments],
        }


@dataclass(slots=True)
class Timeline:
    """Canonical production timeline (ordered segments + time model)."""

    id: str
    name: str = ""
    tracks: dict[str, Track] = field(default_factory=dict)
    dialogues: list[Dialogue] = field(default_factory=list)
    transitions: list[Transition] = field(default_factory=list)
    markers: list[Marker] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(cls, name: str = "", **kwargs: object) -> Timeline:
        """Create an empty timeline."""
        return cls(id=new_id("tl"), name=name, **kwargs)  # type: ignore[arg-type]

    def ensure_track(self, kind: str) -> Track:
        """Get or create a track of the given kind."""
        track = self.tracks.get(kind)
        if track is None:
            track = Track(kind=kind)
            self.tracks[kind] = track
        return track

    def video_segments(self) -> list[VideoSegment]:
        """Return video track segments in order."""
        track = self.tracks.get("video")
        return list(track.segments) if track else []

    def audio_segments(self) -> list[AudioSegment]:
        """Return audio track segments in order."""
        track = self.tracks.get("audio")
        return list(track.segments) if track else []

    def find_segment_by_node(self, node_name: str) -> VideoSegment | AudioSegment | None:
        """Find a segment whose node name or node id matches."""
        for segment in self.video_segments():
            if segment.node_name == node_name or segment.node_id == node_name:
                return segment
        for segment in self.audio_segments():
            if segment.node_name == node_name or segment.node_id == node_name:
                return segment
        return None

    def total_duration(self) -> float:
        """Return the timeline duration as max end time across tracks."""
        duration = 0.0
        for segment in self.video_segments():
            duration = max(duration, segment.end_seconds)
        for segment in self.audio_segments():
            duration = max(duration, segment.end_seconds)
        return duration

    def fingerprint(self) -> str:
        """Structural fingerprint of the timeline content."""
        return stable_hash(
            {
                "name": self.name,
                "video": [
                    (s.node_name, s.artifact_id, s.duration_seconds)
                    for s in self.video_segments()
                ],
                "audio": [
                    (s.node_name, s.artifact_id, s.duration_seconds)
                    for s in self.audio_segments()
                ],
            }
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize the full timeline deterministically."""
        return {
            "id": self.id,
            "name": self.name,
            "tracks": {
                kind: track.to_dict() for kind, track in sorted(self.tracks.items())
            },
            "dialogues": [d.to_dict() for d in self.dialogues],
            "transitions": [t.to_dict() for t in self.transitions],
            "markers": [m.to_dict() for m in self.markers],
            "metadata": dict(self.metadata),
            "total_duration": self.total_duration(),
        }

    def to_json(self, indent: int = 2) -> str:
        """Export deterministic JSON (sorted keys)."""
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True, default=str)
