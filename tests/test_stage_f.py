"""Stage F tests: capabilities, consistency, dialogue audio, timeline renderer."""

from __future__ import annotations

from drama_forge.capabilities import (
    CapabilityRegistry,
    CapabilitySpec,
    DialogueAudioSpec,
    build_character_constraints,
    build_scene_constraints,
    check_character_consistency,
    check_scene_consistency,
    default_capability_registry,
    plan_dialogue_audio_nodes,
)
from drama_forge.capabilities.audio import estimate_dialogue_duration
from drama_forge.capabilities.character_consistency import (
    CharacterConsistencyConstraints,
)
from drama_forge.capabilities.scene_consistency import SceneConsistencyConstraints
from drama_forge.compiler.story_graph import build_production_graph
from drama_forge.domain.asset import Artifact, Candidate
from drama_forge.domain.common import ArtifactType, ExecutionStatus, GateResult
from drama_forge.domain.continuity import ContinuityFinding, ContinuityReport, ContinuityRule
from drama_forge.domain.story import Story
from drama_forge.engine import Engine
from drama_forge.timeline import (
    CanonicalTimelineBuilder,
    Timeline,
    TimelineRenderer,
)

# ---------------------------------------------------------------------------
# Capability registry
# ---------------------------------------------------------------------------


def test_default_capability_registry_contains_stage_f_names() -> None:
    """Default registry exposes all named Stage F capabilities."""
    registry = default_capability_registry()
    expected = {
        "text_generation",
        "image_generation",
        "video_generation",
        "audio_generation",
        "vision_evaluation",
        "image_evaluation",
        "video_evaluation",
        "continuity_validation",
        "timeline_render",
        "dialogue_audio",
    }
    assert expected.issubset(set(registry.list_capabilities()))


def test_capability_registry_register_and_require() -> None:
    """Registry supports custom registration and require semantics."""
    registry = CapabilityRegistry()
    spec = CapabilitySpec(
        name="custom_cap",
        input_types=["text"],
        output_types=["json"],
        supports_continuity=False,
    )
    registry.register(spec)
    assert registry.supports("custom_cap")
    assert registry.require("custom_cap") is spec
    assert registry.get("missing") is None


def test_capability_registry_duplicate_rejected() -> None:
    """Registering a different spec with the same name raises ValueError."""
    registry = CapabilityRegistry()
    registry.register(CapabilitySpec(name="cap_a", input_types=["text"]))
    try:
        registry.register(CapabilitySpec(name="cap_a", input_types=["image"]))
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for conflicting capability")


def test_capability_continuity_flags() -> None:
    """Continuity-capable capabilities are discoverable."""
    registry = default_capability_registry()
    capable = registry.continuity_capable()
    assert "image_generation" in capable
    assert "video_generation" in capable
    assert "dialogue_audio" in capable
    assert "timeline_render" not in capable


# ---------------------------------------------------------------------------
# Character / scene consistency
# ---------------------------------------------------------------------------


def test_build_character_constraints(story: Story) -> None:
    """Constraints capture identity hash, appearance, costume, and voice."""
    character = next(iter(story.characters.values()))
    constraints = build_character_constraints(character)
    assert isinstance(constraints, CharacterConsistencyConstraints)
    assert constraints.identity_hash
    assert constraints.appearance_anchor == character.appearance
    assert constraints.extra["character_id"] == character.id

    as_dict = constraints.to_dict()
    assert as_dict["identity_hash"] == constraints.identity_hash
    assert as_dict["character_id"] == character.id


def test_check_character_consistency_scores(story: Story) -> None:
    """Candidate consistency scores are deterministic and bounded."""
    character = next(iter(story.characters.values()))
    constraints = build_character_constraints(character)

    candidates = []
    for index in range(3):
        artifact = Artifact.create(
            artifact_type=ArtifactType.IMAGE,
            content_reference="",
            generation_metadata={"digest": f"digest-{index:04d}"},
        )
        candidates.append(Candidate.create(node_id="n1", artifact=artifact))

    scores = check_character_consistency(candidates, constraints)
    assert set(scores) == {c.id for c in candidates}
    for value in scores.values():
        assert 0.0 <= value <= 1.0
    # deterministic: same inputs -> same scores
    again = check_character_consistency(candidates, constraints)
    assert scores == again


def test_build_and_check_scene_constraints(story: Story) -> None:
    """Scene constraints capture location/lighting and score candidates."""
    episode = story.episodes[0]
    scene = episode.scenes[0]
    constraints = build_scene_constraints(scene, style="neo-noir anime")
    assert isinstance(constraints, SceneConsistencyConstraints)
    assert constraints.location == scene.location
    assert constraints.style == "neo-noir anime"

    artifact = Artifact.create(
        artifact_type=ArtifactType.VIDEO,
        content_reference="",
        generation_metadata={"digest": "scene-digest-01"},
    )
    candidate = Candidate.create(node_id="n1", artifact=artifact)
    scores = check_scene_consistency([candidate], constraints)
    assert candidate.id in scores
    assert 0.0 <= scores[candidate.id] <= 1.0


# ---------------------------------------------------------------------------
# Dialogue audio planning
# ---------------------------------------------------------------------------


def test_dialogue_audio_nodes_appear_for_shots_with_dialogue(story: Story) -> None:
    """Only shots with non-empty dialogue get generate_dialogue_audio nodes."""
    plan = build_production_graph(story, candidate_count=1)
    graph = plan.graph
    audio_nodes = [
        n for n in graph.nodes.values() if n.action == "generate_dialogue_audio"
    ]
    # sample story has exactly one shot with dialogue
    assert len(audio_nodes) == 1
    node = audio_nodes[0]
    assert node.generation_spec is not None
    assert node.generation_spec.capability == "audio_generation"
    dialogue_text = node.generation_spec.audio_requirements.get("text", "")
    assert dialogue_text
    # depends on the matching select node
    deps = graph.dependencies(node.id)
    dep_actions = {graph.nodes[d].action for d in deps}
    assert "select_shot_candidate" in dep_actions
    # feeds assemble_timeline
    dependents = graph.dependents(node.id)
    assert any(graph.nodes[d].action == "assemble_timeline" for d in dependents)


def test_plan_dialogue_audio_nodes_idempotent(story: Story) -> None:
    """Planning twice does not duplicate dialogue audio nodes."""
    plan = build_production_graph(story, candidate_count=1)
    graph = plan.graph
    before = sum(1 for n in graph.nodes.values() if n.action == "generate_dialogue_audio")
    again = plan_dialogue_audio_nodes(story, graph, assets=plan.assets)
    after = sum(1 for n in graph.nodes.values() if n.action == "generate_dialogue_audio")
    assert after == before
    assert len(again) == before


def test_dialogue_audio_spec_and_duration() -> None:
    """DialogueAudioSpec serializes inputs and duration estimate is positive."""
    spec = DialogueAudioSpec(
        text="你好，世界",
        character_voice="voice-a",
        duration_seconds=2.0,
        character_id="char_1",
    )
    inputs = spec.to_generation_inputs()
    assert inputs["text"] == "你好，世界"
    assert inputs["character_voice"] == "voice-a"
    assert estimate_dialogue_duration("hello there friend") >= 1.0
    assert estimate_dialogue_duration("") >= 1.0


# ---------------------------------------------------------------------------
# Timeline model + renderer
# ---------------------------------------------------------------------------


def test_timeline_renderer_orders_segments_with_offsets() -> None:
    """Renderer lays out video segments sequentially and computes end times."""
    builder = CanonicalTimelineBuilder()
    timeline = builder.build(
        video_entries=[
            {
                "node_name": "shot_select:1.1",
                "node_id": "n1",
                "artifact_id": "a1",
                "duration_seconds": 4.0,
            },
            {
                "node_name": "shot_select:1.2",
                "node_id": "n2",
                "artifact_id": "a2",
                "duration_seconds": 3.5,
            },
        ],
        audio_entries=[
            {
                "node_name": "dialogue_audio:1.2",
                "node_id": "n3",
                "artifact_id": "a3",
                "duration_seconds": 2.0,
                "text": "hello",
                "character_id": "char_1",
            },
        ],
        name="test-timeline",
    )
    rendered = TimelineRenderer().render(timeline)

    video = timeline.video_segments()
    assert video[0].start_seconds == 0.0
    assert video[0].end_seconds == 4.0
    assert video[1].start_seconds == 4.0
    assert video[1].end_seconds == 7.5
    assert rendered.total_duration == 7.5

    # audio aligned to host video segment 1.2
    audio = timeline.audio_segments()
    assert audio[0].start_seconds == 4.0
    assert rendered.audio_alignment
    assert rendered.audio_alignment[0]["video_node"] == "shot_select:1.2"

    assert "shot_select:1.1" in rendered.segment_order
    assert "dialogue_audio:1.2" in rendered.segment_order


def test_timeline_replace_segment_without_full_rebuild() -> None:
    """replace_segment swaps artifact ref and marks the segment replaced."""
    builder = CanonicalTimelineBuilder()
    timeline = builder.build(
        video_entries=[
            {
                "node_name": "shot_select:1.1",
                "node_id": "n1",
                "artifact_id": "old-artifact",
                "duration_seconds": 3.0,
            },
            {
                "node_name": "shot_select:1.2",
                "node_id": "n2",
                "artifact_id": "keep-artifact",
                "duration_seconds": 3.0,
            },
        ],
    )
    renderer = TimelineRenderer()
    renderer.render(timeline)

    updated = renderer.replace_segment(timeline, "shot_select:1.1", "new-artifact")
    assert updated is timeline
    segment = timeline.find_segment_by_node("shot_select:1.1")
    assert segment is not None
    assert segment.artifact_id == "new-artifact"
    assert segment.replaced is True
    # other segment untouched
    other = timeline.find_segment_by_node("shot_select:1.2")
    assert other is not None
    assert other.artifact_id == "keep-artifact"
    assert other.replaced is False


def test_timeline_replace_segment_unknown_raises() -> None:
    """Replacing an unknown segment raises ValueError."""
    timeline = Timeline.create(name="empty")
    try:
        TimelineRenderer.replace_segment(timeline, "missing", "art")
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for unknown segment")


def test_timeline_json_export_deterministic() -> None:
    """JSON export is stable across calls (sorted keys, same content)."""
    builder = CanonicalTimelineBuilder()
    timeline = builder.build(
        video_entries=[
            {
                "node_name": "shot_select:1.1",
                "artifact_id": "a1",
                "duration_seconds": 2.0,
            },
        ],
    )
    TimelineRenderer().render(timeline)
    first = timeline.to_json()
    second = timeline.to_json()
    assert first == second
    assert '"total_duration"' in first


# ---------------------------------------------------------------------------
# Continuity domain models
# ---------------------------------------------------------------------------


def test_continuity_rule_and_report() -> None:
    """ContinuityRule maps to issue types and report gate recomputes."""
    rule = ContinuityRule.create(
        scope="character",
        subject_id="char_1",
        constraint_key="appearance_anchor",
        expected_value="black hair",
    )
    assert rule.fingerprint()
    assert rule.to_issue_type().value == "CHARACTER_CONTINUITY"

    report = ContinuityReport.create(subject_id="timeline-1")
    report.add_finding(
        ContinuityFinding(rule_id=rule.id, subject_ref="cand-1", passed=True, score=0.9)
    )
    assert report.gate == GateResult.PASS
    assert report.passed

    report.add_finding(
        ContinuityFinding(rule_id=rule.id, subject_ref="cand-2", passed=False, score=0.2)
    )
    assert report.gate == GateResult.BLOCK
    payload = report.to_dict()
    assert payload["gate"] == "BLOCK"
    assert payload["finding_count"] == 2


# ---------------------------------------------------------------------------
# Engine integration
# ---------------------------------------------------------------------------


def test_engine_run_with_dialogue_audio_and_timeline(engine: Engine, story: Story) -> None:
    """Full engine run succeeds and timeline includes audio track + times."""
    result = engine.run(story, candidate_count=1)
    assert result.status == ExecutionStatus.SUCCEEDED

    actions = {n.action for n in result.graph.nodes.values()}
    assert "generate_dialogue_audio" in actions

    timeline_artifact = result.timeline_artifact
    assert timeline_artifact is not None
    payload = timeline_artifact.generation_metadata
    assert "video" in payload["tracks"]
    assert "audio" in payload["tracks"]
    assert payload["tracks"]["audio"], "expected at least one dialogue audio segment"
    assert payload["metadata"]["total_duration"] > 0

    # video segments carry resolved start/end times
    for segment in payload["tracks"]["video"]:
        assert "start_seconds" in segment
        assert "end_seconds" in segment
        assert segment["end_seconds"] > segment["start_seconds"]


def test_engine_update_timeline_shot_still_works(engine: Engine, story: Story) -> None:
    """Timeline substitution via engine still functions after Stage F."""
    result = engine.run(story, candidate_count=1)
    assert result.timeline_artifact is not None

    video = result.timeline_artifact.generation_metadata["tracks"]["video"]
    assert video
    target_node_name = video[0].get("node_name") or video[0].get("node_id")
    # find a real artifact to swap in
    replacement = next(iter(result.context.artifacts.values()))
    if replacement.id == video[0]["artifact_id"]:
        replacement = list(result.context.artifacts.values())[1]

    updated = engine.update_timeline_shot(
        result.execution_id, str(target_node_name), replacement
    )
    new_video = updated.generation_metadata["tracks"]["video"]
    assert new_video[0]["artifact_id"] == replacement.id
    assert new_video[0].get("replaced") is True
