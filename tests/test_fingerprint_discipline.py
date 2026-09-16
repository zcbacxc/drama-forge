# SPDX-FileCopyrightText: 2026 zcbacxc
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Fingerprint discipline: tunables stay out of production identity (W1)."""

from __future__ import annotations

from drama_forge.domain.production import (
    SELECTION_POLICY_FINGERPRINT_KEYS,
    CanonicalGenerationSpec,
    GraphNode,
    ProductionGraph,
    stable_selection_policy,
)


def test_selection_policy_weights_do_not_change_fingerprint() -> None:
    """Changing only weights leaves the generation-spec fingerprint stable."""
    base = CanonicalGenerationSpec(
        node_id="n1",
        capability="selection",
        selection_policy={
            "strategy": "highest_total_score",
            "min_technical_score": 0.6,
            "require_pass_gate": True,
            "weights": {"technical": 0.4, "continuity": 0.3, "style": 0.2, "cost": 0.1},
        },
    )
    retuned = CanonicalGenerationSpec(
        node_id="n1",
        capability="selection",
        selection_policy={
            "strategy": "highest_total_score",
            "min_technical_score": 0.6,
            "require_pass_gate": True,
            "weights": {"technical": 0.1, "continuity": 0.1, "style": 0.1, "cost": 0.7},
        },
    )
    assert base.fingerprint() == retuned.fingerprint()


def test_selection_policy_stable_keys_do_change_fingerprint() -> None:
    """Strategy / gate-related stable keys still change the fingerprint."""
    base = CanonicalGenerationSpec(
        node_id="n1",
        capability="selection",
        selection_policy={"strategy": "highest_total_score", "weights": {"a": 1.0}},
    )
    other_strategy = CanonicalGenerationSpec(
        node_id="n1",
        capability="selection",
        selection_policy={"strategy": "cost_first", "weights": {"a": 1.0}},
    )
    other_gate = CanonicalGenerationSpec(
        node_id="n1",
        capability="selection",
        selection_policy={
            "strategy": "highest_total_score",
            "require_pass_gate": False,
            "weights": {"a": 1.0},
        },
    )
    assert base.fingerprint() != other_strategy.fingerprint()
    assert base.fingerprint() != other_gate.fingerprint()


def test_style_constraints_and_candidate_count_change_fingerprint() -> None:
    """Production-defining fields still invalidate the fingerprint."""
    base = CanonicalGenerationSpec(
        node_id="n1",
        capability="video_generation",
        style_constraints={"style": "neo-noir anime"},
        candidate_count=2,
        selection_policy={"strategy": "highest_total_score", "weights": {"a": 1.0}},
    )
    style_changed = CanonicalGenerationSpec(
        node_id="n1",
        capability="video_generation",
        style_constraints={"style": "watercolor"},
        candidate_count=2,
        selection_policy={"strategy": "highest_total_score", "weights": {"a": 1.0}},
    )
    count_changed = CanonicalGenerationSpec(
        node_id="n1",
        capability="video_generation",
        style_constraints={"style": "neo-noir anime"},
        candidate_count=3,
        selection_policy={"strategy": "highest_total_score", "weights": {"a": 1.0}},
    )
    assert base.fingerprint() != style_changed.fingerprint()
    assert base.fingerprint() != count_changed.fingerprint()


def test_stable_selection_policy_whitelist() -> None:
    """Whitelist projects only stable keys and drops tunables like weights."""
    projected = stable_selection_policy(
        {
            "strategy": "highest_total_score",
            "min_technical_score": 0.5,
            "require_pass_gate": True,
            "weights": {"a": 0.5, "b": 0.5},
            "temperature": 0.7,
        }
    )
    assert set(projected) == set(SELECTION_POLICY_FINGERPRINT_KEYS)
    assert "weights" not in projected
    assert "temperature" not in projected
    assert projected["strategy"] == "highest_total_score"


def test_node_fingerprint_ignores_scheduler_runtime_params() -> None:
    """Lock F2/F28: scheduling params and ExecutionContext.provider_policy stay out.

    Production recompute uses ``graph.policy`` (default empty), not the
    ExecutionContext provider policy. max_workers / max_attempts are Scheduler
    constructor-only and never enter the node hash.
    """
    from drama_forge.runtime.scheduler import Scheduler

    node = GraphNode.create(
        name="shot_gen:1.1",
        action="generate_shot_candidates",
        generation_spec=CanonicalGenerationSpec(
            node_id="pending",
            capability="video_generation",
            style_constraints={"style": "neo-noir anime"},
            candidate_count=2,
        ),
    )
    graph = ProductionGraph.create(name="fingerprint-discipline")
    graph.add_node(node)
    # Production compile path leaves graph.policy as {}.
    assert graph.policy == {}
    graph.recompute_all_fingerprints()
    baseline = node.fingerprint
    assert baseline

    # Different Scheduler runtime knobs must not rewrite the definition hash.
    _serial = Scheduler(executor=None, max_workers=1, max_attempts=2)  # type: ignore[arg-type]
    _parallel = Scheduler(executor=None, max_workers=4, max_attempts=5)  # type: ignore[arg-type]
    assert node.fingerprint == baseline

    # Recompute path still uses graph.policy, not a context provider policy.
    graph.recompute_all_fingerprints()
    assert node.fingerprint == baseline
    assert node.compute_fingerprint(graph.policy) == baseline
