# SPDX-FileCopyrightText: 2026 zcbacxc
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Tests for Production Knowledge, parallel scheduler, failure classes, manifest IO."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from drama_forge.compiler.manifest_io import (
    dump_manifest_file,
    load_manifest_file,
    manifest_from_contract,
    manifest_to_contract,
)
from drama_forge.domain.common import FailureClass, NodeStatus
from drama_forge.domain.knowledge import (
    ProductionKnowledge,
    apply_knowledge_to_continuity_constraints,
    harvest_knowledge_from_story,
)
from drama_forge.domain.production import (
    GraphEdge,
    GraphNode,
    ProductionGraph,
    ProductionManifest,
)
from drama_forge.engine import Engine
from drama_forge.runtime.cancellation import CancellationToken
from drama_forge.runtime.scheduler import (
    ExecutionContext,
    Scheduler,
    TaskResult,
)

# --- Production Knowledge -----------------------------------------------------


def test_harvest_knowledge_from_story(story) -> None:
    knowledge = harvest_knowledge_from_story(story)
    assert knowledge.story_id == story.id
    assert knowledge.character_identity
    assert "林默" in str(knowledge.character_identity.values())
    assert knowledge.fingerprint
    assert knowledge.version == 1


def test_knowledge_merge_bumps_version(story) -> None:
    base = harvest_knowledge_from_story(story)
    extra = ProductionKnowledge.create(
        story_id=story.id,
        style_rules={"style": "neo-noir anime", "palette": "cool"},
        world_rules=["雨夜霓虹"],
    )
    merged = base.merge(extra)
    assert merged.version == base.version + 1
    assert merged.style_rules.get("palette") == "cool"
    assert "雨夜霓虹" in merged.world_rules


def test_knowledge_injected_into_graph_continuity(story) -> None:
    from drama_forge.compiler.story_graph import build_production_graph

    knowledge = ProductionKnowledge.create(
        story_id=story.id,
        style_rules={"style": "neo-noir anime"},
        continuity_constraints={"character_identity": {"x": {"name": "林默"}}},
    )
    plan = build_production_graph(story, knowledge=knowledge)
    char_nodes = [
        n
        for n in plan.graph.nodes.values()
        if n.action == "build_character_reference" and n.generation_spec
    ]
    assert char_nodes
    cont = char_nodes[0].generation_spec.continuity_constraints
    assert cont.get("character_identity") or cont.get("style")


def test_engine_run_harvests_knowledge(engine: Engine, story) -> None:
    result = engine.run(story, candidate_count=1)
    assert result.knowledge is not None
    assert result.knowledge.story_id == story.id
    assert result.knowledge.character_identity
    assert result.knowledge.fingerprint


def test_engine_run_with_prior_knowledge_merge(engine: Engine, story) -> None:
    prior = ProductionKnowledge.create(
        story_id=story.id,
        style_rules={"palette": "neon"},
    )
    result = engine.run(story, candidate_count=1, knowledge=prior)
    assert result.knowledge is not None
    # injected knowledge is used in plan; harvested bundle is story-grounded
    assert result.knowledge.character_identity


def test_knowledge_persisted_when_db_enabled(tmp_path: Path, sample_story_dict) -> None:
    engine = Engine(artifact_root=tmp_path / "a", db_path=tmp_path / "p.db")
    story = engine.compile(sample_story_dict)
    result = engine.run(story, candidate_count=1)
    assert result.knowledge is not None
    repo = engine._repos["knowledge"]
    loaded = repo.latest_for_story(story.id)
    assert loaded is not None
    assert loaded["story_id"] == story.id


def test_apply_knowledge_constraints_shape() -> None:
    knowledge = ProductionKnowledge.create(
        story_id="s",
        style_rules={"style": "anime"},
        continuity_constraints={"enforce_character_identity": True},
    )
    constraints = apply_knowledge_to_continuity_constraints(knowledge)
    assert constraints["style"] == "anime"
    assert constraints["enforce_character_identity"] is True


# --- Parallel scheduler / cancellation ----------------------------------------


class _CountingExecutor:
    """Executor that records concurrent overlap."""

    def __init__(self, delay: float = 0.0) -> None:
        self.calls: list[str] = []
        self.max_inflight = 0
        self._inflight = 0
        self.delay = delay

    def execute(self, node: GraphNode, context: ExecutionContext) -> TaskResult:
        import threading
        import time

        with threading.Lock():
            self._inflight += 1
            self.max_inflight = max(self.max_inflight, self._inflight)
        try:
            if self.delay:
                time.sleep(self.delay)
            self.calls.append(node.id)
            return TaskResult(node_id=node.id, success=True)
        finally:
            with threading.Lock():
                self._inflight -= 1


def _diamond_graph() -> ProductionGraph:
    graph = ProductionGraph.create(name="diamond")
    root = GraphNode.create(name="root", action="noop")
    left = GraphNode.create(name="left", action="noop")
    right = GraphNode.create(name="right", action="noop")
    sink = GraphNode.create(name="sink", action="noop")
    for node in (root, left, right, sink):
        graph.add_node(node)
    graph.add_edge(GraphEdge.create(root.id, left.id))
    graph.add_edge(GraphEdge.create(root.id, right.id))
    graph.add_edge(GraphEdge.create(left.id, sink.id))
    graph.add_edge(GraphEdge.create(right.id, sink.id))
    graph.recompute_all_fingerprints()
    return graph


def test_parallel_scheduler_runs_independent_nodes() -> None:
    graph = _diamond_graph()
    executor = _CountingExecutor(delay=0.05)
    scheduler = Scheduler(executor=executor, max_attempts=1, max_workers=4)
    context = ExecutionContext(execution_id="exec-p", graph=graph)
    status = scheduler.run(graph, context)
    assert status.value == "SUCCEEDED"
    assert len(executor.calls) == 4
    # left and right are independent — expect overlap > 1 under parallel workers
    assert executor.max_inflight >= 2


def test_serial_scheduler_default_no_overlap() -> None:
    graph = _diamond_graph()
    executor = _CountingExecutor(delay=0.01)
    scheduler = Scheduler(executor=executor, max_attempts=1, max_workers=1)
    context = ExecutionContext(execution_id="exec-s", graph=graph)
    status = scheduler.run(graph, context)
    assert status.value == "SUCCEEDED"
    assert executor.max_inflight == 1


def test_cancellation_skips_pending_nodes() -> None:
    graph = _diamond_graph()
    token = CancellationToken()
    token.cancel()
    executor = _CountingExecutor()
    scheduler = Scheduler(executor=executor, max_attempts=1, max_workers=1)
    context = ExecutionContext(
        execution_id="exec-c", graph=graph, cancellation=token
    )
    status = scheduler.run(graph, context)
    assert status.value == "CANCELLED"
    assert executor.calls == []


def test_failure_class_soft_marks_degraded() -> None:
    class _SoftFail:
        def execute(self, node, context):
            return TaskResult(
                node_id=node.id,
                success=False,
                error="soft",
                failure_class=FailureClass.SOFT_FAILURE,
            )

    graph = ProductionGraph.create(name="soft")
    node = GraphNode.create(name="n", action="noop")
    graph.add_node(node)
    graph.recompute_all_fingerprints()
    scheduler = Scheduler(executor=_SoftFail(), max_attempts=3, max_workers=1)
    context = ExecutionContext(execution_id="exec-soft", graph=graph)
    status = scheduler.run(graph, context)
    assert node.status == NodeStatus.DEGRADED
    assert status.value in {"PARTIAL", "FAILED", "SUCCEEDED"}


def test_failure_class_hard_retries_then_fails() -> None:
    class _HardFail:
        def __init__(self) -> None:
            self.calls = 0

        def execute(self, node, context):
            self.calls += 1
            return TaskResult(
                node_id=node.id,
                success=False,
                error="hard",
                failure_class=FailureClass.HARD_FAILURE,
            )

    graph = ProductionGraph.create(name="hard")
    node = GraphNode.create(name="n", action="noop")
    graph.add_node(node)
    graph.recompute_all_fingerprints()
    executor = _HardFail()
    scheduler = Scheduler(executor=executor, max_attempts=2, max_workers=1)
    context = ExecutionContext(execution_id="exec-hard", graph=graph)
    scheduler.run(graph, context)
    assert executor.calls == 2
    assert node.status == NodeStatus.FAILED


# --- Manifest JSON contract ---------------------------------------------------


def test_manifest_contract_roundtrip() -> None:
    manifest = ProductionManifest.create(
        story_id="story_1",
        story_version=2,
        production_spec_id="spec_1",
        graph_id="graph_1",
        provider_policy={"strategy": "balanced"},
        quality_policy={"enforce_continuity": True},
    )
    contract = manifest_to_contract(manifest)
    again = manifest_from_contract(contract)
    assert again.story_id == "story_1"
    assert again.story_version == 2
    assert again.graph_id == "graph_1"
    assert again.provider_policy["strategy"] == "balanced"
    assert again.fingerprint() == manifest.fingerprint()


def test_manifest_file_roundtrip(tmp_path: Path) -> None:
    manifest = ProductionManifest.create(
        story_id="story_1",
        story_version=1,
        production_spec_id="spec_1",
        graph_id="graph_1",
    )
    path = dump_manifest_file(manifest, tmp_path / "manifest.json")
    assert path.is_file()
    loaded = load_manifest_file(path)
    assert loaded.story_id == "story_1"
    assert json.loads(path.read_text(encoding="utf-8"))["schema_version"] == "1.0"


def test_manifest_missing_fields_raises() -> None:
    with pytest.raises(ValueError, match="missing required"):
        manifest_from_contract({"story_id": "s"})


def test_manifest_unsupported_schema_major_raises() -> None:
    with pytest.raises(ValueError, match="unsupported"):
        manifest_from_contract(
            {
                "schema_version": "2.0",
                "story_id": "s",
                "production_spec_id": "p",
                "graph_id": "g",
            }
        )


def test_engine_plan_writes_manifest_file(tmp_path: Path, sample_story_dict) -> None:
    engine = Engine(artifact_root=tmp_path / "a")
    story = engine.compile(sample_story_dict)
    manifest, _plan, _sg = engine.plan(story, candidate_count=1)
    path = dump_manifest_file(manifest, tmp_path / "m.json")
    loaded = load_manifest_file(path)
    assert loaded.graph_id == manifest.graph_id


# --- Persistence repositories -------------------------------------------------


def test_candidate_and_event_repositories(tmp_path: Path) -> None:
    from drama_forge.persistence import (
        CandidateRepository,
        Database,
        EventRepository,
    )

    db = Database(str(tmp_path / "t.db"))
    db.migrate()
    cand = CandidateRepository(db)
    cand.save(
        "cand_1",
        "node_1",
        artifact_id="art_1",
        selected=True,
        score=0.9,
        execution_id="exec_1",
        payload={"digest": "abc"},
    )
    rows = cand.list_by_node("node_1")
    assert len(rows) == 1
    assert rows[0]["selected"] is True
    assert rows[0]["payload"]["digest"] == "abc"

    events = EventRepository(db)
    events.append("exec_1", "node.succeeded", "node_1", {"ok": True})
    events.append("exec_1", "execution.finished", "exec_1", {"status": "SUCCEEDED"})
    listed = events.list_by_execution("exec_1")
    assert len(listed) == 2
    assert listed[0]["event_type"] == "node.succeeded"
