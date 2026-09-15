"""Compliance-sensitive unit tests: retry vs repair, SPDX is static."""

from __future__ import annotations

from drama_forge.domain.common import ExecutionStatus, NodeStatus
from drama_forge.providers.adapters import MockProvider


def test_retry_reruns_failed_nodes_without_repair_plan(engine, story) -> None:
    """Retry re-executes failed nodes with the same production definition."""
    primary = engine.registry.get("mock-primary")
    assert isinstance(primary, MockProvider)
    _manifest, plan, _ = engine.plan(story, candidate_count=1)
    shot_nodes = [
        n for n in plan.graph.nodes.values() if n.action == "generate_shot_candidates"
    ]
    assert shot_nodes
    fail_id = shot_nodes[0].id
    primary.fail_nodes = {fail_id}

    first = engine.run(story, candidate_count=1)
    assert first.status in (ExecutionStatus.PARTIAL, ExecutionStatus.FAILED)
    assert first.graph.nodes[fail_id].status == NodeStatus.FAILED

    # clear failure and retry with unchanged production definition
    primary.fail_nodes = set()
    retried = engine.retry(first.execution_id, story=story)
    assert retried.status == ExecutionStatus.SUCCEEDED
    assert retried.graph.nodes[fail_id].status == NodeStatus.SUCCEEDED


def test_retry_unknown_execution_raises(engine, story) -> None:
    """Retry of unknown execution id raises KeyError."""
    import pytest

    with pytest.raises(KeyError):
        engine.retry("exec_missing", story=story)
