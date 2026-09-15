# SPDX-FileCopyrightText: 2026 zcbacxc
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Timeline renderer: build, resolve times, align audio, and substitute segments."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from drama_forge.timeline.model import (
    AudioSegment,
    Dialogue,
    Marker,
    Timeline,
    VideoSegment,
)


@dataclass(slots=True)
class RenderedTimeline:
    """Result of rendering a timeline: ordered segments with resolved times."""

    timeline: Timeline
    segment_order: list[str] = field(default_factory=list)
    total_duration: float = 0.0
    audio_alignment: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the rendered timeline deterministically."""
        return {
            "timeline": self.timeline.to_dict(),
            "segment_order": list(self.segment_order),
            "total_duration": self.total_duration,
            "audio_alignment": list(self.audio_alignment),
            "metadata": dict(self.metadata),
        }

    def to_json(self, indent: int = 2) -> str:
        """Export deterministic JSON."""
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True, default=str)


class CanonicalTimelineBuilder:
    """Build a Timeline from production graph outcomes and selected candidates."""

    def build(
        self,
        video_entries: list[dict[str, Any]],
        audio_entries: list[dict[str, Any]] | None = None,
        name: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> Timeline:
        """Assemble a Timeline model from raw segment entries.

        Args:
            video_entries: Video segment dicts with node/ artifact/ duration fields.
            audio_entries: Optional audio segment dicts (dialogue lines).
            name: Timeline name.
            metadata: Extra metadata to embed.

        Returns:
            Timeline with video and audio tracks in insertion order.
        """
        timeline = Timeline.create(name=name)
        video_track = timeline.ensure_track("video")
        for entry in video_entries:
            segment = VideoSegment.create(
                node_name=str(entry.get("node_name") or entry.get("node_id", "")),
                duration_seconds=float(entry.get("duration_seconds", 3.0) or 3.0),
                node_id=str(entry.get("node_id", "")),
                artifact_id=str(entry.get("artifact_id", "")),
                candidate_id=str(entry.get("candidate_id", "")),
                media=str(entry.get("media", "video")),
                digest=str(entry.get("digest", "")),
            )
            video_track.add(segment)

        audio_track = timeline.ensure_track("audio")
        for entry in audio_entries or []:
            segment = AudioSegment.create(
                node_name=str(entry.get("node_name") or entry.get("node_id", "")),
                duration_seconds=float(entry.get("duration_seconds", 2.0) or 2.0),
                node_id=str(entry.get("node_id", "")),
                artifact_id=str(entry.get("artifact_id", "")),
                character_id=entry.get("character_id"),
                text=str(entry.get("text", "")),
                digest=str(entry.get("digest", "")),
            )
            audio_track.add(segment)
            if segment.text:
                timeline.dialogues.append(
                    Dialogue(
                        character_id=segment.character_id,
                        text=segment.text,
                        duration_seconds=segment.duration_seconds,
                        audio_segment_id=segment.id,
                    )
                )

        if metadata:
            timeline.metadata.update(metadata)
        timeline.metadata["segment_count"] = len(video_track.segments)
        timeline.metadata["audio_segment_count"] = len(audio_track.segments)
        return timeline

    def build_from_execution(
        self,
        select_nodes: list[Any],
        audio_nodes: list[Any],
        candidates: dict[str, Any],
        artifacts: dict[str, Any],
        name: str = "",
    ) -> Timeline:
        """Build a timeline from executed graph nodes.

        Args:
            select_nodes: select_shot_candidate nodes in graph order.
            audio_nodes: generate_dialogue_audio nodes in graph order.
            candidates: Candidate map from execution context.
            artifacts: Artifact map from execution context.
            name: Timeline name.

        Returns:
            Timeline ready for rendering.
        """
        video_entries: list[dict[str, Any]] = []
        for select_node in select_nodes:
            candidate_id = (
                select_node.candidate_ids[0] if select_node.candidate_ids else None
            )
            candidate = candidates.get(candidate_id) if candidate_id else None
            if candidate is None:
                continue
            artifact = candidate.artifact
            duration = float(
                artifact.generation_metadata.get("duration_seconds", 3.0)
                or artifact.technical_metadata.get("duration_seconds", 3.0)
                or 3.0
            )
            video_entries.append(
                {
                    "node_name": select_node.name,
                    "node_id": select_node.id,
                    "artifact_id": artifact.id,
                    "candidate_id": candidate.id,
                    "duration_seconds": duration,
                    "media": artifact.artifact_type.value,
                    "digest": artifact.generation_metadata.get("digest"),
                }
            )

        audio_entries: list[dict[str, Any]] = []
        for audio_node in audio_nodes:
            artifact_id = (
                audio_node.artifact_ids[0] if audio_node.artifact_ids else None
            )
            artifact = artifacts.get(artifact_id) if artifact_id else None
            if artifact is None:
                continue
            requirements = {}
            if audio_node.generation_spec is not None:
                requirements = dict(audio_node.generation_spec.audio_requirements)
            duration = float(
                artifact.generation_metadata.get("duration_seconds")
                or requirements.get("duration_seconds")
                or artifact.technical_metadata.get("duration_seconds")
                or 2.0
            )
            audio_entries.append(
                {
                    "node_name": audio_node.name,
                    "node_id": audio_node.id,
                    "artifact_id": artifact.id,
                    "duration_seconds": duration,
                    "character_id": requirements.get("character_id"),
                    "text": requirements.get("text", ""),
                    "digest": artifact.generation_metadata.get("digest"),
                }
            )

        return self.build(video_entries, audio_entries, name=name)


class TimelineRenderer:
    """Render a Timeline into ordered segments with resolved time offsets."""

    def render(self, timeline: Timeline) -> RenderedTimeline:
        """Resolve segment order, compute start/end times, and align audio.

        Video segments are laid out sequentially starting at t=0. Audio
        segments are aligned to the video segment that shares the same
        scene/shot key (parsed from node names like ``dialogue_audio:1.2``
        and ``shot_select:1.2``).

        Args:
            timeline: Timeline to render.

        Returns:
            RenderedTimeline with resolved times and audio alignment.
        """
        video_segments = timeline.video_segments()
        cursor = 0.0
        for segment in video_segments:
            segment.start_seconds = cursor
            cursor += segment.duration_seconds

        # Build shot-key index from video node names
        video_by_key: dict[str, VideoSegment] = {}
        for segment in video_segments:
            key = _shot_key(segment.node_name)
            if key:
                video_by_key[key] = segment

        audio_alignment: list[dict[str, Any]] = []
        for segment in timeline.audio_segments():
            key = _shot_key(segment.node_name)
            host = video_by_key.get(key)
            if host is not None:
                # Align dialogue audio to the start of its host video segment,
                # clamped so audio does not start past the host end.
                start = host.start_seconds
                if segment.duration_seconds > host.duration_seconds:
                    segment.duration_seconds = host.duration_seconds
                segment.start_seconds = start
                audio_alignment.append(
                    {
                        "audio_node": segment.node_name,
                        "video_node": host.node_name,
                        "start_seconds": segment.start_seconds,
                        "duration_seconds": segment.duration_seconds,
                    }
                )
            else:
                # No host video: place sequentially after the video tail.
                segment.start_seconds = cursor
                cursor += segment.duration_seconds
                audio_alignment.append(
                    {
                        "audio_node": segment.node_name,
                        "video_node": None,
                        "start_seconds": segment.start_seconds,
                        "duration_seconds": segment.duration_seconds,
                    }
                )

        # Sync dialogue entries with resolved audio times
        audio_by_id = {s.id: s for s in timeline.audio_segments()}
        for dialogue in timeline.dialogues:
            host = (
                audio_by_id.get(dialogue.audio_segment_id)
                if dialogue.audio_segment_id
                else None
            )
            if host is not None:
                dialogue.start_seconds = host.start_seconds
                dialogue.duration_seconds = host.duration_seconds

        # Rebuild transitions at video segment boundaries
        timeline.transitions.clear()
        for prev, nxt in zip(video_segments, video_segments[1:], strict=False):
            from drama_forge.timeline.model import Transition

            timeline.transitions.append(
                Transition(
                    kind="cut",
                    at_seconds=nxt.start_seconds,
                    from_segment_id=prev.id,
                    to_segment_id=nxt.id,
                )
            )

        total = timeline.total_duration()
        timeline.metadata["total_duration"] = total
        timeline.metadata["rendered"] = True

        if not any(m.kind == "end" for m in timeline.markers):
            timeline.markers.append(Marker(kind="end", at_seconds=total, label="end"))

        segment_order = [s.node_name for s in video_segments]
        segment_order.extend(
            s.node_name for s in timeline.audio_segments()
        )

        return RenderedTimeline(
            timeline=timeline,
            segment_order=segment_order,
            total_duration=total,
            audio_alignment=audio_alignment,
            metadata={
                "video_count": len(video_segments),
                "audio_count": len(timeline.audio_segments()),
            },
        )

    @staticmethod
    def replace_segment(
        timeline: Timeline,
        node_name: str,
        new_artifact_ref: str,
        new_duration_seconds: float | None = None,
    ) -> Timeline:
        """Replace one segment's artifact without rebuilding the timeline.

        Mutates the timeline in place and returns it for chaining. Times are
        left as-is; call ``render`` again to recompute offsets after a
        duration change.

        Args:
            timeline: Timeline to modify.
            node_name: Node name or node id of the segment to replace.
            new_artifact_ref: Replacement artifact id (or content reference).
            new_duration_seconds: Optional new duration for the segment.

        Returns:
            The same timeline instance with the segment updated.

        Raises:
            ValueError: If no segment matches ``node_name``.
        """
        segment = timeline.find_segment_by_node(node_name)
        if segment is None:
            raise ValueError(f"segment not found: {node_name}")
        segment.artifact_id = new_artifact_ref
        if hasattr(segment, "replaced"):
            segment.replaced = True
        if new_duration_seconds is not None:
            segment.duration_seconds = float(new_duration_seconds)
        timeline.metadata["last_replaced_segment"] = node_name
        timeline.metadata["rendered"] = False
        return timeline


def _shot_key(node_name: str) -> str:
    """Extract the scene.shot key from a production node name.

    Node names look like ``shot_select:1.2`` or ``dialogue_audio:1.2``.
    Returns the ``1.2`` key, or an empty string when no key is present.
    """
    if ":" in node_name:
        return node_name.rsplit(":", 1)[-1]
    return ""
