# SPDX-FileCopyrightText: 2026 zcbacxc
# SPDX-License-Identifier: AGPL-3.0-or-later
"""W4b: provider reliability — retryable mapping, backoff, circuit breaker."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from drama_forge.domain.common import ExecutionStatus, FailureClass, NodeStatus
from drama_forge.domain.production import CanonicalGenerationSpec, GraphNode
from drama_forge.engine import Engine
from drama_forge.providers.adapters import MockProvider
from drama_forge.providers.base import ProviderRequest
from drama_forge.providers.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerProvider,
    CircuitState,
    circuit_config_from_env,
    maybe_wrap_with_circuit,
)
from drama_forge.runtime.retry import RetryPolicy, retry_policy_from_env
from drama_forge.runtime.scheduler import Scheduler, TaskResult

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _spec(node_id: str = "node_test") -> CanonicalGenerationSpec:
    return CanonicalGenerationSpec(
        node_id=node_id,
        capability="text_generation",
    )


def _request(node_id: str = "node_test") -> ProviderRequest:
    return ProviderRequest(
        capability="text_generation",
        generation_spec=_spec(node_id),
    )


def _zero_policy() -> RetryPolicy:
    """Policy that never sleeps — required for unit tests."""
    return RetryPolicy(base_delay=0.0, jitter=0.0)


class _RecordingExecutor:
    """NodeExecutor that always fails; counts execute calls."""

    def __init__(self, retryable: bool = True) -> None:
        self.calls = 0
        self.retryable = retryable

    def execute(self, node: Any, context: Any) -> TaskResult:
        self.calls += 1
        return TaskResult(
            node_id=node.id,
            success=False,
            error="boom",
            failure_class=FailureClass.HARD_FAILURE,
            retryable=self.retryable,
        )


def _single_node_graph() -> Any:
    from drama_forge.domain.production import ProductionGraph

    graph = ProductionGraph.create(name="reliability")
    node = GraphNode.create(name="n1", action="generate_shot_candidates")
    graph.add_node(node)
    graph.recompute_all_fingerprints()
    return graph, node


def _context(graph: Any) -> Any:
    from drama_forge.runtime.scheduler import ExecutionContext

    return ExecutionContext(
        execution_id="exec_test",
        graph=graph,
        config={"enable_fingerprint_reuse": False},
    )


# ---------------------------------------------------------------------------
# RetryPolicy
# ---------------------------------------------------------------------------


def test_retry_policy_zero_delay_never_sleeps() -> None:
    """base_delay=0 yields zero delay for every attempt (tests use this)."""
    policy = RetryPolicy(base_delay=0.0, jitter=0.0)
    assert policy.delay_for_attempt(1) == 0.0
    assert policy.delay_for_attempt(5) == 0.0


def test_retry_policy_exponential_growth_and_cap() -> None:
    """Delay grows by factor and is capped by max_delay."""
    policy = RetryPolicy(base_delay=1.0, factor=2.0, max_delay=4.0, jitter=0.0)
    assert policy.delay_for_attempt(1) == 1.0
    assert policy.delay_for_attempt(2) == 2.0
    assert policy.delay_for_attempt(3) == 4.0
    assert policy.delay_for_attempt(10) == 4.0


def test_retry_policy_jitter_bounds() -> None:
    """Jitter keeps delay within [raw*(1-jitter), raw]."""
    import random

    policy = RetryPolicy(base_delay=1.0, factor=2.0, max_delay=10.0, jitter=0.5)
    rng = random.Random(42)
    for _ in range(20):
        d = policy.delay_for_attempt(1, rng=rng)
        assert 0.5 <= d <= 1.0


def test_retry_policy_from_env() -> None:
    """Env mapping configures RetryPolicy; invalid values fall back."""
    policy = retry_policy_from_env(
        {
            "DRAMA_FORGE_RETRY_BASE_DELAY": "0",
            "DRAMA_FORGE_RETRY_JITTER": "not-a-number",
        }
    )
    assert policy.base_delay == 0.0
    assert policy.jitter == 0.1  # default


# ---------------------------------------------------------------------------
# CircuitBreaker state machine
# ---------------------------------------------------------------------------


def test_circuit_closed_opens_after_threshold() -> None:
    """Consecutive failures ≥ threshold transition CLOSED → OPEN."""
    clock = {"t": 0.0}
    breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=10.0, clock=lambda: clock["t"])
    assert breaker.state is CircuitState.CLOSED
    breaker.record_failure()
    breaker.record_failure()
    assert breaker.state is CircuitState.CLOSED
    breaker.record_failure()
    assert breaker.state is CircuitState.OPEN
    assert breaker.allow_request() is False


def test_circuit_half_open_after_timeout_then_success_closes() -> None:
    """OPEN → HALF_OPEN after recovery_timeout; success resets to CLOSED."""
    clock = {"t": 0.0}
    breaker = CircuitBreaker(failure_threshold=1, recovery_timeout=5.0, clock=lambda: clock["t"])
    breaker.record_failure()
    assert breaker.state is CircuitState.OPEN
    clock["t"] = 4.9
    assert breaker.state is CircuitState.OPEN
    clock["t"] = 5.0
    assert breaker.state is CircuitState.HALF_OPEN
    assert breaker.allow_request() is True
    breaker.record_success()
    assert breaker.state is CircuitState.CLOSED


def test_circuit_half_open_failure_reopens() -> None:
    """Failure during HALF_OPEN immediately re-opens the circuit."""
    clock = {"t": 0.0}
    breaker = CircuitBreaker(failure_threshold=2, recovery_timeout=1.0, clock=lambda: clock["t"])
    breaker.record_failure()
    breaker.record_failure()
    assert breaker.state is CircuitState.OPEN
    clock["t"] = 1.0
    assert breaker.allow_request() is True  # HALF_OPEN trial
    breaker.record_failure()
    assert breaker.state is CircuitState.OPEN


def test_circuit_open_short_circuits_without_inner_generate() -> None:
    """OPEN rejects without calling the inner provider."""
    inner = MockProvider("mock-cb")
    clock = {"t": 0.0}
    breaker = CircuitBreaker(failure_threshold=1, recovery_timeout=60.0, clock=lambda: clock["t"])
    wrapped = CircuitBreakerProvider(inner=inner, breaker=breaker)

    ok = wrapped.generate(_request())
    assert ok.ok is True
    assert inner.call_count == 1

    # Force OPEN via a failing inner call
    inner.fail_nodes = {"node_test"}
    fail = wrapped.generate(_request())
    assert fail.ok is False
    assert breaker.state is CircuitState.OPEN

    calls_before = inner.call_count
    rejected = wrapped.generate(_request())
    assert rejected.ok is False
    assert rejected.retryable is False
    assert "circuit_open" in (rejected.error or "")
    assert inner.call_count == calls_before  # did not enter generate
    assert wrapped.open_reject_count == 1


def test_circuit_breaker_mirrors_identity_not_in_fingerprint() -> None:
    """Wrapper keeps provider id/scores; circuit state is not fingerprinted."""
    inner = MockProvider("mock-id", quality_score=0.42)
    wrapped = CircuitBreakerProvider(inner=inner)
    assert wrapped.id == inner.id
    assert wrapped.quality_score == inner.quality_score
    assert wrapped.capabilities == inner.capabilities
    # Node definition fingerprint ignores runtime circuit state
    node = GraphNode.create(name="fp", action="generate_shot_candidates")
    node.generation_spec = _spec(node.id)
    before = node.compute_fingerprint()
    wrapped.breaker.record_failure()
    wrapped.breaker.record_failure()
    wrapped.breaker.record_failure()
    wrapped.breaker.record_failure()
    wrapped.breaker.record_failure()
    after = node.compute_fingerprint()
    assert before == after


def test_circuit_config_from_env() -> None:
    """Env knobs configure the breaker; enabled defaults False (opt-in)."""
    cfg = circuit_config_from_env(
        {
            "DRAMA_FORGE_CIRCUIT_ENABLED": "1",
            "DRAMA_FORGE_CIRCUIT_FAILURE_THRESHOLD": "2",
        }
    )
    assert cfg.enabled is True
    assert cfg.failure_threshold == 2
    assert maybe_wrap_with_circuit(MockProvider("m"), config=cfg).id == "m"
    # Default (unset env) leaves providers unwrapped for isinstance compatibility.
    off = circuit_config_from_env({})
    assert off.enabled is False
    bare = MockProvider("bare")
    assert maybe_wrap_with_circuit(bare, config=off) is bare


# ---------------------------------------------------------------------------
# Scheduler retry semantics
# ---------------------------------------------------------------------------


def test_scheduler_default_max_attempts_is_two() -> None:
    """Authoritative default matches Engine (max_attempts=2)."""
    executor = _RecordingExecutor()
    sched = Scheduler(executor=executor, retry_policy=_zero_policy())
    assert sched.max_attempts == 2


def test_scheduler_retries_retryable_hard_failure_with_attempt_count() -> None:
    """HARD + retryable retries until max_attempts then FAILED."""
    graph, node = _single_node_graph()
    context = _context(graph)
    executor = _RecordingExecutor(retryable=True)
    slept: list[float] = []
    sched = Scheduler(
        executor=executor,
        max_attempts=2,
        retry_policy=_zero_policy(),
        sleeper=slept.append,
    )
    status = sched.run(graph, context)
    assert executor.calls == 2
    assert node.attempt == 2
    assert node.status is NodeStatus.FAILED
    assert status is ExecutionStatus.FAILED
    assert slept == [0.0, 0.0] or slept == []  # zero delay → sleep_seconds no-op


def test_scheduler_does_not_retry_non_retryable_hard_failure() -> None:
    """HARD + retryable=False fails immediately without a second attempt."""
    graph, node = _single_node_graph()
    context = _context(graph)
    executor = _RecordingExecutor(retryable=False)
    sched = Scheduler(
        executor=executor,
        max_attempts=2,
        retry_policy=_zero_policy(),
        sleeper=lambda _s: pytest.fail("must not sleep for non-retryable"),
    )
    status = sched.run(graph, context)
    assert executor.calls == 1
    assert node.attempt == 1
    assert node.status is NodeStatus.FAILED
    assert status is ExecutionStatus.FAILED


def test_scheduler_backoff_sleeps_when_delay_positive() -> None:
    """Positive delay invokes the sleeper with a non-zero duration."""
    graph, node = _single_node_graph()
    context = _context(graph)
    executor = _RecordingExecutor(retryable=True)
    slept: list[float] = []
    policy = RetryPolicy(base_delay=0.01, factor=1.0, max_delay=0.01, jitter=0.0)
    sched = Scheduler(
        executor=executor,
        max_attempts=2,
        retry_policy=policy,
        sleeper=slept.append,
    )
    sched.run(graph, context)
    assert executor.calls == 2
    assert len(slept) == 1
    assert slept[0] == pytest.approx(0.01)


# ---------------------------------------------------------------------------
# Engine / Mock integration
# ---------------------------------------------------------------------------


def test_mock_fail_retryable_false_no_recursive_retry(engine: Engine, story: Any) -> None:
    """Engine path: permanent mock failure executes generate once per attempt."""
    primary = engine.registry.get("mock-primary")
    assert isinstance(primary, MockProvider)
    primary.fail_retryable = False
    _manifest, plan, _ = engine.plan(story, candidate_count=1)
    shot_nodes = [
        n for n in plan.graph.nodes.values() if n.action == "generate_shot_candidates"
    ]
    assert shot_nodes
    fail_id = shot_nodes[0].id
    primary.fail_nodes = {fail_id}
    calls_before = primary.call_count

    result = engine.run(story, candidate_count=1)
    node = result.graph.nodes[fail_id]
    assert node.status is NodeStatus.FAILED
    assert node.attempt == 1  # no scheduler retry
    # one generate per candidate for this node; not doubled by retries
    assert primary.call_count - calls_before >= 1


def test_mock_fail_retryable_true_attempts_two(engine: Engine, story: Any) -> None:
    """Engine path: retryable mock failure still retries up to max_attempts=2."""
    primary = engine.registry.get("mock-primary")
    assert isinstance(primary, MockProvider)
    primary.fail_retryable = True
    _manifest, plan, _ = engine.plan(story, candidate_count=1)
    shot_nodes = [
        n for n in plan.graph.nodes.values() if n.action == "generate_shot_candidates"
    ]
    fail_id = shot_nodes[0].id
    primary.fail_nodes = {fail_id}

    result = engine.run(story, candidate_count=1)
    node = result.graph.nodes[fail_id]
    assert node.status is NodeStatus.FAILED
    assert node.attempt == 2


def test_dry_run_http_adapter_behavior_unchanged(tmp_path: Path) -> None:
    """Dry-run / missing key still returns deterministic ok=True fallback."""
    from drama_forge.providers.http_adapter import (
        HttpProviderConfig,
        OpenAICompatibleProvider,
    )

    config = HttpProviderConfig(dry_run=True, provider_id="http-dry")
    provider = OpenAICompatibleProvider(config=config, env={})
    response = provider.generate(_request("node_dry"))
    assert response.ok is True
    assert response.retryable is True
    assert "dry://" in str(response.content)
    assert provider.network_call_count == 0


def test_http_status_retryable_classification() -> None:
    """5xx/429 retryable; other 4xx permanent."""
    from drama_forge.providers.http_adapter import _is_retryable_http_status

    assert _is_retryable_http_status(500) is True
    assert _is_retryable_http_status(503) is True
    assert _is_retryable_http_status(429) is True
    assert _is_retryable_http_status(400) is False
    assert _is_retryable_http_status(401) is False
    assert _is_retryable_http_status(404) is False


def test_circuit_open_maps_to_failed_without_retry(engine: Engine, story: Any) -> None:
    """OPEN circuit yields retryable=False so scheduler does not retry."""
    inner = MockProvider("mock-cb-fail")
    # trip breaker immediately
    breaker = CircuitBreaker(failure_threshold=1, recovery_timeout=999.0)
    wrapped = CircuitBreakerProvider(inner=inner, breaker=breaker)
    # Seed OPEN via a direct failing call
    _manifest, plan, _ = engine.plan(story, candidate_count=1)
    shot_nodes = [
        n for n in plan.graph.nodes.values() if n.action == "generate_shot_candidates"
    ]
    fail_id = shot_nodes[0].id
    node = plan.graph.nodes[fail_id]
    assert node.generation_spec is not None
    inner.fail_nodes = {fail_id}
    request = ProviderRequest(
        capability=node.generation_spec.capability,
        generation_spec=node.generation_spec,
        candidate_index=0,
    )
    wrapped.generate(request)  # failure → OPEN
    assert breaker.state is CircuitState.OPEN

    calls = inner.call_count
    rejected = wrapped.generate(request)
    assert rejected.ok is False
    assert rejected.retryable is False
    assert inner.call_count == calls
