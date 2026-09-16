# SPDX-FileCopyrightText: 2026 zcbacxc
# SPDX-License-Identifier: AGPL-3.0-or-later
"""W4a: CostTracker wiring through Engine → ExecutionContext → ProductionWorker."""

from __future__ import annotations

from pathlib import Path

from drama_forge.artifacts.store import ArtifactStore
from drama_forge.domain.common import ExecutionStatus
from drama_forge.domain.production import CanonicalGenerationSpec, GraphNode, ProductionGraph
from drama_forge.providers.adapters import MockEvaluatorProvider, MockProvider
from drama_forge.providers.base import ProviderResponse
from drama_forge.providers.registry import ProviderRegistry
from drama_forge.providers.router import ProviderRouter
from drama_forge.runtime.scheduler import ExecutionContext
from drama_forge.runtime.worker import ProductionWorker


def _mock_generate_total(engine) -> int:
    """Sum generate() counters across all mock providers in the registry."""
    total = 0
    for provider in engine.registry.all():
        if isinstance(provider, (MockProvider, MockEvaluatorProvider)):
            total += provider.call_count
    return total


def test_run_records_cost_for_every_generate(engine, story) -> None:
    """After Engine.run, CostTracker.call_count matches Mock generate invocations."""
    result = engine.run(story, candidate_count=2)
    assert result.status == ExecutionStatus.SUCCEEDED

    tracker = result.context.cost_tracker
    assert tracker is not None

    mock_calls = _mock_generate_total(engine)
    assert mock_calls > 0

    summary = result.cost_summary()
    assert summary is not None
    assert summary.call_count == mock_calls
    assert summary.call_count >= mock_calls
    assert summary.total_cost > 0
    assert summary.by_capability
    events = [e for e in result.events if e.event_type == "provider.called"]
    assert len(events) == summary.call_count


def test_parallel_run_does_not_lose_counts(engine, story) -> None:
    """max_workers>1: CostTracker must not drop concurrent record() calls."""
    result = engine.run(story, candidate_count=2, max_workers=4)
    assert result.status == ExecutionStatus.SUCCEEDED

    tracker = result.context.cost_tracker
    assert tracker is not None

    mock_calls = _mock_generate_total(engine)
    assert mock_calls > 0

    summary = tracker.summary(result.execution_id)
    assert summary.call_count == mock_calls
    assert summary.total_cost > 0


def test_worker_without_cost_tracker_does_not_raise(tmp_path: Path) -> None:
    """Workers skip bookkeeping when context.cost_tracker is None; task still succeeds."""
    provider = MockProvider("mock-primary", quality_score=0.9)
    registry = ProviderRegistry()
    registry.register(provider)
    router = ProviderRouter(registry)
    store = ArtifactStore(tmp_path / "artifacts")
    worker = ProductionWorker(router=router, artifact_store=store)

    graph = ProductionGraph.create(name="no-tracker")
    node = GraphNode.create(
        name="char",
        action="build_character_reference",
        generation_spec=CanonicalGenerationSpec(
            node_id="n-char",
            capability="image_generation",
        ),
    )
    graph.add_node(node)
    context = ExecutionContext(execution_id="exec-no-tracker", graph=graph)
    assert context.cost_tracker is None

    result = worker.execute(node, context)
    assert result.success is True
    assert provider.call_count == 1
    # no tracker → no cost events required, but provider.selected still fires
    assert any(e.event_type == "provider.selected" for e in context.events.list())


def test_record_failure_is_best_effort(engine, story, monkeypatch) -> None:
    """A raising CostTracker.record must not fail the task or the run."""

    class BoomTracker:
        def record(self, *args, **kwargs):
            raise RuntimeError("tracker boom")

        def summary(self, execution_id):
            raise RuntimeError("tracker boom")

    result = engine.run(story, candidate_count=1)
    assert result.status == ExecutionStatus.SUCCEEDED
    assert result.context.cost_tracker is not None
    monkeypatch.setattr(result.context, "cost_tracker", BoomTracker(), raising=True)

    # Re-execute one generation node handler path via a second run after patching
    # is awkward on slots; instead call the private recorder directly.
    graph = result.graph
    node = next(iter(graph.nodes.values()))
    worker = ProductionWorker(
        router=engine.router,
        artifact_store=engine.artifact_store,
    )
    response = ProviderResponse(ok=True, cost=0.01, provider_metadata={"provider": "x"})
    worker._record_provider_outcome(
        result.context,
        node,
        provider_id="x",
        capability="image_generation",
        response=response,
    )
    # no exception raised


def test_cost_tracker_thread_safe_under_parallel_record() -> None:
    """Direct parallel record() calls lose no counts (lock coverage)."""
    import threading

    from drama_forge.providers.cost import CostTracker

    tracker = CostTracker()
    n_threads = 8
    n_per = 50

    def worker() -> None:
        for _ in range(n_per):
            tracker.record("exec-p", cost=0.001)

    threads = [threading.Thread(target=worker) for _ in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    summary = tracker.summary("exec-p")
    assert summary.call_count == n_threads * n_per
    assert abs(summary.total_cost - n_threads * n_per * 0.001) < 1e-9
