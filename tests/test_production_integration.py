# SPDX-FileCopyrightText: 2026 zcbacxc
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Stage C/F production integration: DeepSeek + SiliconFlow on a live graph.

These tests never require network. They force real-provider adapters in
dry-run mode and prove:
- production graph is unchanged when swapping mock → real adapters
- per-capability routing pins DeepSeek to text/eval and SiliconFlow to image
- artifacts absorb Canonical payloads from the real adapters
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from drama_forge.engine import Engine
from drama_forge.providers.factory import build_default_registry
from drama_forge.providers.router import ProviderRouter

PRODUCTION_ENV: dict[str, str] = {
    "DRAMA_FORGE_PROVIDER": "production",
    "DRAMA_FORGE_PROVIDER_DRY_RUN": "1",
}

PRODUCTION_POLICY: dict[str, Any] = {
    "strategy": "balanced",
    "by_capability": {
        "text_generation": {"provider_id": "deepseek"},
        "vision_evaluation": {"provider_id": "deepseek"},
        "continuity_validation": {"provider_id": "deepseek"},
        "selection": {"provider_id": "deepseek"},
        "image_generation": {"provider_id": "siliconflow-image"},
    },
}


@pytest.fixture
def production_engine(tmp_path: Path) -> Engine:
    """Engine with DeepSeek + SiliconFlow dry-run adapters plus mocks."""
    registry = build_default_registry(env=dict(PRODUCTION_ENV), enable_mock=True)
    return Engine(artifact_root=tmp_path / "artifacts", registry=registry)


def test_router_resolves_per_capability_policy() -> None:
    resolved = ProviderRouter.resolve_policy(
        "image_generation",
        {
            "strategy": "balanced",
            "by_capability": {
                "image_generation": {"provider_id": "siliconflow-image"},
            },
        },
    )
    assert resolved == {
        "strategy": "balanced",
        "provider_id": "siliconflow-image",
    }
    text = ProviderRouter.resolve_policy(
        "text_generation",
        {
            "strategy": "quality_first",
            "by_capability": {
                "image_generation": {"provider_id": "siliconflow-image"},
            },
        },
    )
    assert text == {"strategy": "quality_first"}


def test_production_registry_covers_graph_capabilities() -> None:
    registry = build_default_registry(env=dict(PRODUCTION_ENV), enable_mock=False)
    # Real providers cover the Stage C critical path.
    assert registry.get("deepseek") is not None
    assert registry.get("siliconflow-image") is not None
    assert registry.candidates_for("text_generation")
    assert registry.candidates_for("image_generation")
    assert registry.candidates_for("continuity_validation")
    # Media still not claimed by real adapters alone.
    assert not registry.candidates_for("video_generation")


def test_engine_run_with_real_providers_dry_run(
    production_engine: Engine,
    sample_story_dict: dict[str, Any],
) -> None:
    """Full graph runs with DeepSeek + SiliconFlow forced on their capabilities."""
    story = production_engine.compile(sample_story_dict)
    result = production_engine.run(
        story,
        candidate_count=1,
        provider_policy=PRODUCTION_POLICY,
    )
    assert result.status.value == "SUCCEEDED"
    assert result.timeline_artifact is not None
    assert result.artifacts()

    # Dry-run real adapters must have been invoked (call_count).
    deepseek = production_engine.registry.get("deepseek")
    siliconflow = production_engine.registry.get("siliconflow-image")
    assert deepseek is not None and deepseek.call_count >= 1
    assert siliconflow is not None and siliconflow.call_count >= 1
    assert deepseek.network_call_count == 0
    assert siliconflow.network_call_count == 0

    # Provider metadata on artifacts from siliconflow should mark the provider.
    sf_artifacts = [
        a
        for a in result.artifacts()
        if a.provider_metadata.get("provider") == "siliconflow-image"
    ]
    assert sf_artifacts, "expected at least one artifact from siliconflow-image"
    sample = sf_artifacts[0]
    assert sample.provider_metadata.get("model") == "Kwai-Kolors/Kolors"
    # Content is canonical JSON, not a raw third-party response envelope.
    assert sample.content_reference
    payload = json.loads(Path(sample.content_reference).read_text(encoding="utf-8"))
    assert payload["provider"] == "siliconflow-image"
    assert payload["image_url"].startswith("dry://image_generation/")


def test_provider_swap_keeps_same_graph_topology(
    tmp_path: Path,
    sample_story_dict: dict[str, Any],
) -> None:
    """Mock-only run and production-provider run plan the same node set."""
    mock_engine = Engine(artifact_root=tmp_path / "mock")
    mock_story = mock_engine.compile(sample_story_dict)
    mock_manifest, mock_plan, _ = mock_engine.plan(mock_story, candidate_count=1)
    mock_nodes = sorted(mock_plan.graph.nodes)

    prod_registry = build_default_registry(env=dict(PRODUCTION_ENV), enable_mock=True)
    prod_engine = Engine(artifact_root=tmp_path / "prod", registry=prod_registry)
    prod_story = prod_engine.compile(sample_story_dict)
    prod_manifest, prod_plan, _ = prod_engine.plan(prod_story, candidate_count=1)
    prod_nodes = sorted(prod_plan.graph.nodes)

    assert mock_nodes == prod_nodes
    assert mock_story.fingerprint() == prod_story.fingerprint()
    # Manifest capability policy fields stay provider-agnostic.
    assert "image_generation" in {
        n.generation_spec.capability
        for n in prod_plan.graph.nodes.values()
        if n.generation_spec
    }


def test_siliconflow_canonical_digest_stable_across_candidates() -> None:
    """Same production conditions + different candidates → different digests."""
    from drama_forge.domain.production import CanonicalGenerationSpec
    from drama_forge.providers.base import ProviderRequest
    from drama_forge.providers.siliconflow import SiliconFlowConfig, SiliconFlowImageProvider

    provider = SiliconFlowImageProvider(SiliconFlowConfig(dry_run=True), env={})
    spec = CanonicalGenerationSpec(
        node_id="n",
        capability="image_generation",
        inputs={"description": "a rooftop at night"},
    )

    def digests(index: int) -> str:
        response = provider.generate(
            ProviderRequest(
                capability="image_generation",
                generation_spec=spec,
                candidate_index=index,
            )
        )
        assert response.ok
        return str(response.generation_metadata["digest"])

    assert digests(0) != digests(1)
    assert digests(0) == digests(0)
