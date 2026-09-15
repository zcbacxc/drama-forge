"""Enhanced provider-layer tests: factory, HTTP adapter, router, cost tracker."""

from __future__ import annotations

import json

from drama_forge.domain.production import CanonicalGenerationSpec
from drama_forge.providers.adapters import MockEvaluatorProvider, MockProvider
from drama_forge.providers.base import ProviderRequest, ProviderResponse
from drama_forge.providers.cost import CostTracker
from drama_forge.providers.factory import build_default_registry, http_config_from_env
from drama_forge.providers.http_adapter import HttpProviderConfig, OpenAICompatibleProvider
from drama_forge.providers.registry import ProviderRegistry
from drama_forge.providers.router import ProviderRouter


def _spec(node_id: str = "n1", capability: str = "text_generation") -> CanonicalGenerationSpec:
    return CanonicalGenerationSpec(node_id=node_id, capability=capability)


def _request(
    capability: str = "text_generation", candidate_index: int = 0
) -> ProviderRequest:
    return ProviderRequest(
        capability=capability,
        generation_spec=_spec(capability=capability),
        candidate_index=candidate_index,
    )


# --- factory -----------------------------------------------------------------


def test_factory_defaults_to_mocks() -> None:
    """Empty env and enable_mock=True yields the standard mock set only."""
    registry = build_default_registry(env={})
    ids = {p.id for p in registry.all()}
    assert ids == {"mock-primary", "mock-economy", "mock-evaluator"}
    assert registry.get("mock-primary") is not None
    assert isinstance(registry.get("mock-primary"), MockProvider)
    assert isinstance(registry.get("mock-evaluator"), MockEvaluatorProvider)
    # no HTTP provider without configuration
    assert registry.get("openai-compatible") is None


def test_factory_disable_mock_empty_registry() -> None:
    """enable_mock=False with no HTTP config returns an empty registry."""
    registry = build_default_registry(env={}, enable_mock=False)
    assert registry.all() == []


def test_factory_registers_http_when_configured() -> None:
    """DRAMA_FORGE_PROVIDER=openai_compatible registers mocks + HTTP adapter."""
    env = {
        "DRAMA_FORGE_PROVIDER": "openai_compatible",
        "DRAMA_FORGE_PROVIDER_BASE_URL": "https://example.test",
        "DRAMA_FORGE_PROVIDER_API_KEY": "test-key",
        "DRAMA_FORGE_PROVIDER_MODEL": "test-model",
    }
    registry = build_default_registry(env=env)
    ids = {p.id for p in registry.all()}
    assert "mock-primary" in ids
    assert "openai-compatible" in ids
    http = registry.get("openai-compatible")
    assert isinstance(http, OpenAICompatibleProvider)
    assert http.config.base_url == "https://example.test"
    assert http.config.model == "test-model"
    assert http.supports("text_generation")


def test_factory_http_without_mock() -> None:
    """enable_mock=False still registers the HTTP provider when configured."""
    env = {
        "DRAMA_FORGE_PROVIDER": "http",
        "DRAMA_FORGE_PROVIDER_DRY_RUN": "true",
    }
    registry = build_default_registry(env=env, enable_mock=False)
    ids = {p.id for p in registry.all()}
    assert ids == {"openai-compatible"}


def test_http_config_from_env_defaults() -> None:
    """http_config_from_env fills safe defaults from an empty mapping."""
    config = http_config_from_env({})
    assert config.base_url == "https://api.openai.com"
    assert config.api_key_env == "DRAMA_FORGE_PROVIDER_API_KEY"
    assert config.model == "gpt-4o-mini"
    assert config.dry_run is False


def test_http_config_api_key_env_override() -> None:
    """DRAMA_FORGE_PROVIDER_API_KEY_ENV retargets the secret variable name."""
    config = http_config_from_env({"DRAMA_FORGE_PROVIDER_API_KEY_ENV": "VENDOR_KEY"})
    assert config.api_key_env == "VENDOR_KEY"


# --- HTTP adapter (offline) --------------------------------------------------


def test_http_provider_dry_run_fallback_no_network() -> None:
    """dry_run=True never opens a network socket and is deterministic."""
    provider = OpenAICompatibleProvider(
        HttpProviderConfig(dry_run=True, provider_id="http-dry"),
        env={},
    )
    assert provider.network_call_count == 0
    r1 = provider.generate(_request())
    r2 = provider.generate(_request())
    assert provider.network_call_count == 0
    assert r1.ok and r2.ok
    assert r1.error is None
    assert r1.cost == 0.0
    assert r1.generation_metadata["digest"] == r2.generation_metadata["digest"]
    assert provider.network_call_count == 0
    payload = json.loads(r1.content)
    assert payload["mode"] == "dry_run_fallback"
    assert payload["provider"] == "http-dry"


def test_http_provider_missing_api_key_fallback() -> None:
    """No API key in env → deterministic fallback, no network."""
    provider = OpenAICompatibleProvider(
        HttpProviderConfig(provider_id="http-nokey"),
        env={},  # isolated: no API key present
    )
    response = provider.generate(_request(capability="image_generation"))
    assert response.ok
    assert provider.network_call_count == 0
    assert response.provider_metadata["reason"] == "missing_api_key"
    assert response.technical_metadata["offline"] is True


def test_http_provider_fallback_differs_by_candidate() -> None:
    """Different candidate indexes produce different fallback digests."""
    provider = OpenAICompatibleProvider(HttpProviderConfig(dry_run=True), env={})
    a = provider.generate(_request(candidate_index=0))
    b = provider.generate(_request(candidate_index=1))
    assert a.generation_metadata["digest"] != b.generation_metadata["digest"]


def test_http_provider_unsupported_capability_not_claimed() -> None:
    """Default HTTP adapter does not claim video generation."""
    provider = OpenAICompatibleProvider(HttpProviderConfig(dry_run=True), env={})
    assert not provider.supports("video_generation")
    assert provider.supports("text_generation")


# --- router reliability strategy ---------------------------------------------


def test_router_reliability_first() -> None:
    """reliability_first prefers the more reliable provider."""
    registry = ProviderRegistry()
    registry.register(
        MockProvider(
            "flaky",
            quality_score=0.95,
            reliability=0.2,
            latency_score=0.9,
            cost_score=0.9,
        )
    )
    registry.register(
        MockProvider(
            "steady",
            quality_score=0.7,
            reliability=0.99,
            latency_score=0.8,
            cost_score=0.5,
        )
    )
    router = ProviderRouter(registry)
    provider, decision = router.select(
        "text_generation", {"strategy": "reliability_first"}, subject="rel"
    )
    assert provider.id == "steady"
    assert decision.selected == "steady"
    assert "reliability_first" in decision.reason
    assert "steady" in decision.evidence["scores"]


def test_router_balanced_still_latency_aware() -> None:
    """Balanced strategy still factors latency_score (regression-safe)."""
    registry = ProviderRegistry()
    # equal quality/reliability/cost — latency breaks the tie
    registry.register(
        MockProvider("slow", quality_score=0.8, reliability=1.0, cost_score=0.7, latency_score=0.1)
    )
    registry.register(
        MockProvider("fast", quality_score=0.8, reliability=1.0, cost_score=0.7, latency_score=1.0)
    )
    router = ProviderRouter(registry)
    provider, _ = router.select("text_generation", {"strategy": "balanced"})
    assert provider.id == "fast"


def test_router_forced_provider_still_works() -> None:
    """Forced provider_id overrides strategy (regression)."""
    registry = ProviderRegistry()
    registry.register(MockProvider("a", quality_score=0.9))
    registry.register(MockProvider("b", quality_score=0.1))
    router = ProviderRouter(registry)
    provider, decision = router.select(
        "text_generation", {"strategy": "quality_first", "provider_id": "b"}
    )
    assert provider.id == "b"
    assert decision.reason == "forced by provider policy"


# --- cost tracker ------------------------------------------------------------


def test_cost_tracker_accumulates_by_execution() -> None:
    """CostTracker sums cost and usage per execution and per provider."""
    tracker = CostTracker()
    tracker.record(
        "exec-1",
        ProviderResponse(
            ok=True,
            cost=0.05,
            usage={"prompt_tokens": 10, "completion_tokens": 20},
            provider_metadata={"provider": "p1"},
        ),
        capability="text_generation",
    )
    tracker.record(
        "exec-1",
        ProviderResponse(
            ok=True,
            cost=0.02,
            usage={"prompt_tokens": 5},
            provider_metadata={"provider": "p2"},
        ),
        capability="image_generation",
    )
    tracker.record(
        "exec-1",
        ProviderResponse(ok=False, error="boom", provider_metadata={"provider": "p1"}),
        capability="text_generation",
    )

    summary = tracker.summary("exec-1")
    assert summary.call_count == 3
    assert summary.failed_calls == 1
    assert summary.total_cost == 0.07
    assert summary.usage["prompt_tokens"] == 15.0
    assert summary.usage["completion_tokens"] == 20.0
    assert summary.by_provider["p1"] == 0.05
    assert summary.by_provider["p2"] == 0.02
    assert summary.by_capability["text_generation"] == 0.05
    assert tracker.total_cost("exec-1") == 0.07
    assert tracker.executions() == ["exec-1"]


def test_cost_tracker_isolates_executions_and_resets() -> None:
    """Executions are independent; reset clears one or all."""
    tracker = CostTracker()
    tracker.record("e1", cost=1.0)
    tracker.record("e2", cost=2.0)
    assert tracker.total_cost("e1") == 1.0
    assert tracker.total_cost("e2") == 2.0
    tracker.reset("e1")
    assert tracker.total_cost("e1") == 0.0
    assert tracker.total_cost("e2") == 2.0
    tracker.reset()
    assert tracker.executions() == []


def test_cost_tracker_unknown_execution_summary() -> None:
    """Unknown execution returns a zeroed summary, not an error."""
    tracker = CostTracker()
    summary = tracker.summary("missing")
    assert summary.total_cost == 0.0
    assert summary.call_count == 0
    assert summary.to_dict()["execution_id"] == "missing"


# --- mock determinism regression ---------------------------------------------


def test_mock_determinism_still_holds() -> None:
    """MockProvider remains deterministic after factory/router extensions."""
    provider = MockProvider("p1")
    spec = _spec(capability="image_generation")
    r1 = provider.generate(
        ProviderRequest(capability="image_generation", generation_spec=spec)
    )
    r2 = provider.generate(
        ProviderRequest(capability="image_generation", generation_spec=spec)
    )
    assert r1.ok and r2.ok
    assert r1.generation_metadata["digest"] == r2.generation_metadata["digest"]


def test_factory_mocks_support_engine_capabilities() -> None:
    """Factory-registered mocks cover the capabilities Engine relies on."""
    registry = build_default_registry(env={})
    for capability in (
        "text_generation",
        "image_generation",
        "video_generation",
        "vision_evaluation",
    ):
        assert registry.candidates_for(capability), f"missing mock for {capability}"
