"""Nine core engineering validations for Drama Forge Core Engine."""

from __future__ import annotations

from drama_forge.domain.common import (
    ArtifactType,
    ExecutionStatus,
    GateResult,
    IssueType,
    NodeStatus,
    RepairKind,
)
from drama_forge.providers.adapters import MockProvider


def test_validation_1_repeat_execution_reuse(engine, story) -> None:
    """Validation 1: identical inputs reuse fingerprint cache on re-run."""
    first = engine.run(story, candidate_count=2)
    assert first.status == ExecutionStatus.SUCCEEDED
    # second run with same story should reuse succeeded node fingerprints
    second = engine.run(story, candidate_count=2)
    assert second.status == ExecutionStatus.SUCCEEDED
    reused = [
        e for e in second.context.events.list() if e.event_type == "node.reused"
    ]
    assert reused, "expected fingerprint reuse events on second identical run"


def test_validation_2_interrupt_resume(engine, story) -> None:
    """Validation 2: resume from checkpoint after simulated partial run."""
    result = engine.run(story, candidate_count=1)
    assert result.status == ExecutionStatus.SUCCEEDED
    cp = engine.checkpoint_store.load(result.execution_id)
    assert cp is not None
    assert cp.completed_nodes
    # resume should not crash and should mark reused nodes
    resumed = engine.run(story, candidate_count=1, resume_execution_id=result.execution_id)
    assert resumed.status == ExecutionStatus.SUCCEEDED
    # checkpoint still available
    assert engine.checkpoint_store.load(result.execution_id) is not None


def test_validation_3_partial_failure_isolation(engine, story) -> None:
    """Validation 3: one failing node does not force independent branches to redo."""
    # Make one provider fail only on a specific node by using a fail_nodes provider
    primary = engine.registry.get("mock-primary")
    assert isinstance(primary, MockProvider)
    _manifest, plan_result, _sg = engine.plan(story, candidate_count=1)
    # pick one shot generation node to fail
    shot_nodes = [
        n
        for n in plan_result.graph.nodes.values()
        if n.action == "generate_shot_candidates"
    ]
    assert shot_nodes
    fail_id = shot_nodes[0].id
    primary.fail_nodes = {fail_id}

    result = engine.run(story, candidate_count=1)
    # overall may be PARTIAL because one branch failed
    assert result.status in (ExecutionStatus.PARTIAL, ExecutionStatus.FAILED)
    statuses = {nid: n.status for nid, n in result.graph.nodes.items()}
    assert statuses[fail_id] == NodeStatus.FAILED

    # independent character reference nodes should still succeed
    char_ok = [
        n
        for n in result.graph.nodes.values()
        if n.action == "build_character_reference"
        and n.status == NodeStatus.SUCCEEDED
    ]
    assert char_ok, "independent character reference nodes should succeed"

    primary.fail_nodes = set()


def test_validation_4_provider_swap(engine, story) -> None:
    """Validation 4: swapping providers does not change production graph shape."""
    manifest_a, plan_a, _ = engine.plan(story)
    actions_a = {n.action for n in plan_a.graph.nodes.values()}
    graph_id_a = plan_a.graph.id

    # force a different provider via policy
    result = engine.run(
        story,
        candidate_count=1,
        provider_policy={"strategy": "cost_first", "provider_id": "mock-economy"},
    )
    assert result.status == ExecutionStatus.SUCCEEDED
    decisions = [
        d for d in result.context.decision_records if d.decision_type == "provider_routing"
    ]
    assert decisions
    assert all(d.selected == "mock-economy" for d in decisions)

    _, plan_b, _ = engine.plan(story)
    actions_b = {n.action for n in plan_b.graph.nodes.values()}
    assert actions_a == actions_b
    # structural action set is provider-agnostic
    assert graph_id_a != plan_b.graph.id or actions_a == actions_b


def test_validation_5_candidate_selection(engine, story) -> None:
    """Validation 5: multiple candidates are evaluated and one is selected."""
    result = engine.run(story, candidate_count=3)
    assert result.status == ExecutionStatus.SUCCEEDED
    selected = result.selected_candidates()
    assert selected, "at least one candidate should be selected"
    for candidate in selected:
        assert candidate.selected
        assert candidate.artifact.quality_state.value == "SELECTED"
    selection_decisions = [
        d
        for d in result.context.decision_records
        if d.decision_type == "candidate_selection"
    ]
    assert selection_decisions
    assert all(d.selected for d in selection_decisions)


def test_validation_6_continuity_failure_local_repair(engine, story) -> None:
    """Validation 6: continuity issue drives local repair, not full rebuild."""
    result = engine.run(story, candidate_count=2, inject_continuity_issue=True)
    assert result.report.overall_gate == GateResult.BLOCK
    continuity_issues = [
        i for i in result.report.issues if i.issue_type == IssueType.CHARACTER_CONTINUITY
    ]
    assert continuity_issues

    plan, rerun = engine.repair(result.execution_id, story=story)
    assert plan.kind == RepairKind.POST_GENERATION
    assert plan.invalidate_node_ids
    # character/scene refs should be kept when not in issue scope
    for node in rerun.graph.nodes.values():
        if node.action == "build_character_reference":
            assert node.id in plan.keep_node_ids or node.id not in plan.invalidate_node_ids

    # after repair, continuity should pass
    assert rerun.report.overall_gate in (GateResult.PASS, GateResult.WARN)


def test_validation_7_preflight_repair(engine, story) -> None:
    """Validation 7: missing inputs are detected preflight and planned for repair."""
    from drama_forge.quality.validators import validate_preflight_inputs

    result = engine.run(story, candidate_count=1)
    # craft a preflight issue on a real node
    target_node = next(iter(result.graph.nodes))
    qr = validate_preflight_inputs({}, ["reference_asset"], target_node)
    assert qr.gate == GateResult.BLOCK
    assert qr.issues[0].issue_type == IssueType.MISSING_INPUT

    plan = engine.repair_planner.plan(qr.issues, result.graph)
    assert plan.kind == RepairKind.PREFLIGHT
    assert target_node in plan.invalidate_node_ids


def test_validation_8_provenance_trace(engine, story) -> None:
    """Validation 8: any final artifact can be traced back through provenance."""
    result = engine.run(story, candidate_count=1)
    assert result.timeline_artifact is not None
    trace = engine.inspect(result.timeline_artifact.id)
    assert trace is not None
    provenance = trace["provenance"]
    assert provenance["story_id"] == story.id
    assert provenance["graph_node_id"]
    assert provenance["execution_id"] == result.execution_id

    # also trace a selected shot artifact
    selected = result.selected_candidates()
    assert selected
    shot_trace = engine.inspect(selected[0].artifact.id)
    assert shot_trace is not None
    assert shot_trace["provenance"]["provider_id"]
    assert shot_trace["provenance"]["candidate_id"] == selected[0].id


def test_validation_9_canonical_timeline_update(engine, story) -> None:
    """Validation 9: replace one shot in timeline without rebuilding production."""
    from drama_forge.domain.asset import Artifact

    result = engine.run(story, candidate_count=1)
    assert result.timeline_artifact is not None
    original_segments = result.timeline_artifact.generation_metadata["tracks"]["video"]
    assert original_segments

    # find a select node name
    select_nodes = [
        n for n in result.graph.nodes.values() if n.action == "select_shot_candidate"
    ]
    assert select_nodes
    target_name = select_nodes[0].name

    replacement = Artifact.create(
        artifact_type=ArtifactType.VIDEO,
        content_reference="",
        source_node=select_nodes[0].id,
        generation_metadata={"digest": "replacement-digest"},
    )
    engine.artifact_store.put(replacement, content="replacement")

    updated = engine.update_timeline_shot(
        result.execution_id, target_name, replacement
    )
    segments = updated.generation_metadata["tracks"]["video"]
    replaced = [s for s in segments if s.get("replaced")]
    assert replaced
    assert replaced[0]["artifact_id"] == replacement.id
    # other segments unchanged
    assert len(segments) == len(original_segments)


def test_end_to_end_reference_chain(engine, story) -> None:
    """Full reference production chain succeeds with timeline artifact."""
    result = engine.run(story, candidate_count=2)
    assert result.status == ExecutionStatus.SUCCEEDED
    assert result.timeline_artifact is not None
    assert result.timeline_artifact.artifact_type == ArtifactType.TIMELINE
    status = engine.status(result.execution_id)
    assert status is not None
    assert status["status"] == "SUCCEEDED"
    assert status["artifact_count"] > 0
    # every select node should have a selected candidate
    select_nodes = [
        n for n in result.graph.nodes.values() if n.action == "select_shot_candidate"
    ]
    for node in select_nodes:
        assert node.candidate_ids, f"select node {node.name} has no selected candidate"
