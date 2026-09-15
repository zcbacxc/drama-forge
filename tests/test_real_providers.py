# SPDX-FileCopyrightText: 2026 zcbacxc
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Offline contract tests for DeepSeek and SiliconFlow production providers."""

from __future__ import annotations

import io
import json
import urllib.error
from typing import Any

import pytest

from drama_forge.domain.production import CanonicalGenerationSpec
from drama_forge.providers.base import ProviderRequest
from drama_forge.providers.deepseek import deepseek_config_from_env
from drama_forge.providers.factory import build_default_registry
from drama_forge.providers.http_adapter import HttpProviderConfig, OpenAICompatibleProvider
from drama_forge.providers.registry import ProviderRegistry
from drama_forge.providers.router import ProviderRouter
from drama_forge.providers.siliconflow import (
    SiliconFlowConfig,
    SiliconFlowImageProvider,
    siliconflow_config_from_env,
)


def _deepseek_provider(env: dict[str, str] | None = None) -> OpenAICompatibleProvider:
    """OpenAI-compatible provider wired to the DeepSeek preset."""
    config = deepseek_config_from_env({}).to_http_config()
    if env is not None and "DRAMA_FORGE_DEEPSEEK_MODEL" in env:
        config.model = env["DRAMA_FORGE_DEEPSEEK_MODEL"]
    return OpenAICompatibleProvider(config=config, env=env or {})


def _spec(
    node_id: str = "n1",
    capability: str = "text_generation",
    *,
    inputs: dict[str, Any] | None = None,
    style: dict[str, Any] | None = None,
) -> CanonicalGenerationSpec:
    return CanonicalGenerationSpec(
        node_id=node_id,
        capability=capability,
        inputs=inputs or {"description": "test prompt"},
        style_constraints=style or {},
    )


def _request(
    capability: str = "text_generation",
    candidate_index: int = 0,
    inputs: dict[str, Any] | None = None,
) -> ProviderRequest:
    return ProviderRequest(
        capability=capability,
        generation_spec=_spec(capability=capability, inputs=inputs),
        candidate_index=candidate_index,
    )


class _FakeHTTPResponse:
    """Minimal urllib response double."""

    def __init__(self, body: bytes, status: int = 200, headers: dict[str, str] | None = None):
        self._body = body
        self.status = status
        self.headers = headers or {"Content-Type": "application/json"}

    def read(self) -> bytes:
        return self._body

    def getcode(self) -> int:
        return self.status

    def __enter__(self) -> _FakeHTTPResponse:
        return self

    def __exit__(self, *args: object) -> None:
        return None


# --- DeepSeek (OpenAI-compatible preset) --------------------------------------


def test_deepseek_config_from_env_defaults() -> None:
    config = deepseek_config_from_env({})
    assert config.base_url == "https://api.deepseek.com"
    assert config.chat_path == "chat/completions"
    assert config.model == "deepseek-flash"
    assert config.api_key_env == "DRAMA_FORGE_DEEPSEEK_API_KEY"
    assert config.provider_id == "deepseek"
    assert "text_generation" in config.capabilities
    assert "continuity_validation" in config.capabilities
    assert config.dry_run is False


def test_deepseek_config_from_env_overrides() -> None:
    config = deepseek_config_from_env(
        {
            "DRAMA_FORGE_DEEPSEEK_MODEL": "deepseek-v4-pro",
            "DRAMA_FORGE_DEEPSEEK_BASE_URL": "https://api.deepseek.com/v1",
            "DRAMA_FORGE_PROVIDER_DRY_RUN": "1",
            "DRAMA_FORGE_DEEPSEEK_ID": "ds-prod",
        }
    )
    assert config.model == "deepseek-v4-pro"
    assert config.base_url == "https://api.deepseek.com/v1"
    assert config.dry_run is True
    assert config.provider_id == "ds-prod"


def test_deepseek_preset_to_http_config_chat_path() -> None:
    http = deepseek_config_from_env({}).to_http_config()
    assert http.chat_path == "chat/completions"
    assert http.provider_id == "deepseek"
    assert http.model == "deepseek-flash"
    assert "image_generation" not in http.capabilities


def test_openai_compatible_chat_path_keeps_v1_on_base() -> None:
    provider = OpenAICompatibleProvider(
        HttpProviderConfig(
            base_url="https://gateway.example.com/v1",
            chat_path="v1/chat/completions",
            provider_id="gateway",
        ),
        env={},
    )
    assert provider._endpoint("chat") == "https://gateway.example.com/v1/chat/completions"


def test_openai_compatible_chat_path_no_v1_on_base() -> None:
    provider = OpenAICompatibleProvider(
        HttpProviderConfig(
            base_url="https://api.openai.com",
            provider_id="openai",
        ),
        env={},
    )
    assert provider._endpoint("chat") == "https://api.openai.com/v1/chat/completions"


def test_deepseek_dry_run_is_deterministic_and_offline() -> None:
    provider = OpenAICompatibleProvider(
        deepseek_config_from_env({"DRAMA_FORGE_PROVIDER_DRY_RUN": "1"}).to_http_config(),
        env={},
    )
    r1 = provider.generate(_request())
    r2 = provider.generate(_request())
    assert provider.network_call_count == 0
    assert r1.ok and r2.ok
    assert r1.generation_metadata["digest"] == r2.generation_metadata["digest"]
    assert r1.provider_metadata["mode"] == "dry_run_fallback"
    assert r1.provider_metadata["provider"] == "deepseek"


def test_deepseek_missing_key_fallback() -> None:
    config = deepseek_config_from_env({}).to_http_config()
    config.provider_id = "ds-nokey"
    provider = OpenAICompatibleProvider(config, env={})
    response = provider.generate(_request(capability="continuity_validation"))
    assert response.ok
    assert provider.network_call_count == 0
    assert response.provider_metadata["reason"] == "missing_api_key"


def test_deepseek_endpoint_and_normalize_chat_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Live-shaped chat completion is absorbed into ProviderResponse."""
    captured: dict[str, Any] = {}

    def fake_urlopen(req: Any, timeout: float | None = None) -> _FakeHTTPResponse:
        captured["url"] = req.full_url
        captured["headers"] = dict(req.header_items())
        captured["body"] = json.loads(req.data.decode("utf-8"))
        payload = {
            "id": "chatcmpl-123",
            "model": "deepseek-flash",
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": '{"ok": true}',
                        "reasoning_content": "",
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 12,
                "completion_tokens": 8,
                "total_tokens": 20,
            },
        }
        return _FakeHTTPResponse(json.dumps(payload).encode("utf-8"))

    monkeypatch.setattr(
        "drama_forge.providers.http_adapter.urllib.request.urlopen", fake_urlopen
    )
    config = deepseek_config_from_env({}).to_http_config()
    config.api_key_env = "DS_KEY"
    provider = OpenAICompatibleProvider(config, env={"DS_KEY": "sk-test"})
    response = provider.generate(_request(capability="selection"))
    assert response.ok
    assert provider.network_call_count == 1
    assert captured["url"] == "https://api.deepseek.com/chat/completions"
    assert captured["headers"].get("Authorization") == "Bearer sk-test"
    assert captured["body"]["model"] == "deepseek-flash"
    assert captured["body"]["messages"][0]["role"] == "system"
    assert response.content == '{"ok": true}'
    assert response.usage["total_tokens"] == 20
    assert response.provider_metadata["provider"] == "deepseek"
    assert response.provider_metadata["model"] == "deepseek-flash"


def test_deepseek_prefers_reasoning_content_when_content_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_urlopen(req: Any, timeout: float | None = None) -> _FakeHTTPResponse:
        payload = {
            "id": "chatcmpl-reason",
            "model": "deepseek-flash",
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "",
                        "reasoning_content": "thinking... OK",
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {"total_tokens": 40},
        }
        return _FakeHTTPResponse(json.dumps(payload).encode("utf-8"))

    monkeypatch.setattr(
        "drama_forge.providers.http_adapter.urllib.request.urlopen", fake_urlopen
    )
    config = deepseek_config_from_env({}).to_http_config()
    config.api_key_env = "DS_KEY"
    provider = OpenAICompatibleProvider(config, env={"DS_KEY": "sk-test"})
    response = provider.generate(_request())
    assert response.ok
    assert response.content == "thinking... OK"


def test_deepseek_http_error_returns_not_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_urlopen(req: Any, timeout: float | None = None) -> _FakeHTTPResponse:
        raise urllib.error.HTTPError(
            url=req.full_url,
            code=401,
            msg="Unauthorized",
            hdrs=None,  # type: ignore[arg-type]
            fp=io.BytesIO(b'{"error":"invalid api key"}'),
        )

    monkeypatch.setattr(
        "drama_forge.providers.http_adapter.urllib.request.urlopen", fake_urlopen
    )
    config = deepseek_config_from_env({}).to_http_config()
    config.api_key_env = "DS_KEY"
    provider = OpenAICompatibleProvider(config, env={"DS_KEY": "bad"})
    response = provider.generate(_request())
    assert response.ok is False
    assert response.error is not None
    assert "http_401" in response.error


# --- SiliconFlow --------------------------------------------------------------


def test_siliconflow_config_from_env_defaults() -> None:
    config = siliconflow_config_from_env({})
    assert config.base_url == "https://api.siliconflow.cn"
    assert config.image_model == "Kwai-Kolors/Kolors"
    assert config.image_size == "1024x1024"
    assert config.provider_id == "siliconflow-image"
    assert config.capabilities == {"image_generation"}
    assert config.dry_run is False


def test_siliconflow_dry_run_is_deterministic_and_offline() -> None:
    provider = SiliconFlowImageProvider(SiliconFlowConfig(dry_run=True), env={})
    a = provider.generate(_request("image_generation", candidate_index=0))
    b = provider.generate(_request("image_generation", candidate_index=0))
    c = provider.generate(_request("image_generation", candidate_index=1))
    assert provider.network_call_count == 0
    assert a.ok and b.ok and c.ok
    assert a.generation_metadata["digest"] == b.generation_metadata["digest"]
    assert a.generation_metadata["digest"] != c.generation_metadata["digest"]
    payload = json.loads(a.content)
    assert payload["mode"] == "dry_run_fallback"
    assert payload["image_url"].startswith("dry://image_generation/")
    assert payload["model"] == "Kwai-Kolors/Kolors"


def test_siliconflow_builds_prompt_from_canonical_spec() -> None:
    provider = SiliconFlowImageProvider(SiliconFlowConfig(dry_run=True), env={})
    request = ProviderRequest(
        capability="image_generation",
        generation_spec=CanonicalGenerationSpec(
            node_id="shot-1",
            capability="image_generation",
            inputs={
                "description": "远景：两人在天台对峙",
                "characters": ["林默", "苏晚"],
                "location": "旧城区天台",
            },
            style_constraints={"style": "neo-noir anime"},
            camera_spec={"shot": "wide"},
        ),
    )
    payload = provider._build_payload(request)
    prompt = payload["prompt"]
    assert "天台" in prompt
    assert "林默" in prompt
    assert "neo-noir anime" in prompt
    assert "wide" in prompt
    assert payload["model"] == "Kwai-Kolors/Kolors"
    assert "seed" in payload


def test_siliconflow_normalizes_images_generations_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    def fake_urlopen(req: Any, timeout: float | None = None) -> _FakeHTTPResponse:
        captured["url"] = req.full_url
        captured["headers"] = dict(req.header_items())
        captured["body"] = json.loads(req.data.decode("utf-8"))
        payload = {
            "images": [
                {
                    "url": "https://cdn.siliconflow.cn/img/abc.png",
                }
            ],
            "timings": {"inference": 1.25},
            "seed": captured["body"]["seed"],
        }
        return _FakeHTTPResponse(json.dumps(payload).encode("utf-8"))

    monkeypatch.setattr(
        "drama_forge.providers.siliconflow.urllib.request.urlopen", fake_urlopen
    )
    provider = SiliconFlowImageProvider(
        SiliconFlowConfig(api_key_env="SF_KEY", cost_per_image=0.02),
        env={"SF_KEY": "sk-sf"},
    )
    response = provider.generate(_request("image_generation"))
    assert response.ok
    assert captured["url"] == "https://api.siliconflow.cn/v1/images/generations"
    assert captured["headers"].get("Authorization") == "Bearer sk-sf"
    assert captured["body"]["model"] == "Kwai-Kolors/Kolors"
    assert response.cost == 0.02
    assert response.media_type == "application/json"
    canonical = json.loads(response.content)
    assert canonical["image_url"] == "https://cdn.siliconflow.cn/img/abc.png"
    assert canonical["provider"] == "siliconflow-image"
    assert response.generation_metadata["digest"]
    assert response.technical_metadata["image_url"].endswith("abc.png")


def test_siliconflow_missing_image_url_is_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_urlopen(req: Any, timeout: float | None = None) -> _FakeHTTPResponse:
        return _FakeHTTPResponse(json.dumps({"images": []}).encode("utf-8"))

    monkeypatch.setattr(
        "drama_forge.providers.siliconflow.urllib.request.urlopen", fake_urlopen
    )
    provider = SiliconFlowImageProvider(
        SiliconFlowConfig(api_key_env="SF_KEY"), env={"SF_KEY": "sk"}
    )
    response = provider.generate(_request("image_generation"))
    assert response.ok is False
    assert response.error == "missing_image_url_in_response"


def test_image_provider_accepts_openai_data_shape(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """OpenAI Images-style data[].url (e.g. Agnes) is absorbed."""

    def fake_urlopen(req: Any, timeout: float | None = None) -> _FakeHTTPResponse:
        payload = {
            "data": [{"url": "https://cdn.example.com/out.png", "b64_json": ""}],
            "created": 1,
            "task_id": "task-abc",
        }
        return _FakeHTTPResponse(json.dumps(payload).encode("utf-8"))

    monkeypatch.setattr(
        "drama_forge.providers.siliconflow.urllib.request.urlopen", fake_urlopen
    )
    provider = SiliconFlowImageProvider(
        SiliconFlowConfig(api_key_env="AGNES_KEY", provider_id="agnes-image"),
        env={"AGNES_KEY": "sk"},
    )
    response = provider.generate(_request("image_generation"))
    assert response.ok
    canonical = json.loads(response.content)
    assert canonical["image_url"] == "https://cdn.example.com/out.png"
    assert canonical["provider"] == "agnes-image"


def test_factory_registers_agnes_image() -> None:
    registry = build_default_registry(
        env={
            "DRAMA_FORGE_PROVIDER": "agnes-image",
            "DRAMA_FORGE_PROVIDER_DRY_RUN": "1",
            "DRAMA_FORGE_AGNES_BASE_URL": "https://gw.example.com/v1",
        },
        enable_mock=False,
    )
    provider = registry.get("agnes-image")
    assert provider is not None
    assert provider.supports("image_generation")
    assert provider.config.image_model == "agnes-image-2.0-flash"
    assert provider.config.base_url == "https://gw.example.com/v1"


# --- Factory + routing --------------------------------------------------------


def test_factory_registers_deepseek_only() -> None:
    registry = build_default_registry(
        env={"DRAMA_FORGE_PROVIDER": "deepseek", "DRAMA_FORGE_PROVIDER_DRY_RUN": "1"}
    )
    ids = {p.id for p in registry.all()}
    assert "deepseek" in ids
    assert "siliconflow-image" not in ids
    assert "mock-primary" in ids
    deepseek = registry.get("deepseek")
    assert isinstance(deepseek, OpenAICompatibleProvider)
    assert deepseek.supports("text_generation")
    assert deepseek.supports("continuity_validation")
    assert not deepseek.supports("image_generation")
    assert deepseek.config.chat_path == "chat/completions"


def test_factory_registers_siliconflow_only() -> None:
    registry = build_default_registry(
        env={"DRAMA_FORGE_PROVIDER": "siliconflow", "DRAMA_FORGE_PROVIDER_DRY_RUN": "true"}
    )
    ids = {p.id for p in registry.all()}
    assert "siliconflow-image" in ids
    assert "deepseek" not in ids
    sf = registry.get("siliconflow-image")
    assert isinstance(sf, SiliconFlowImageProvider)
    assert sf.supports("image_generation")


def test_factory_production_alias_registers_both() -> None:
    registry = build_default_registry(
        env={"DRAMA_FORGE_PROVIDER": "production", "DRAMA_FORGE_PROVIDER_DRY_RUN": "1"}
    )
    ids = {p.id for p in registry.all()}
    assert "deepseek" in ids
    assert "siliconflow-image" in ids
    assert "mock-primary" in ids


def test_factory_combined_expression_registers_both() -> None:
    registry = build_default_registry(
        env={"DRAMA_FORGE_PROVIDER": "deepseek+siliconflow", "DRAMA_FORGE_PROVIDER_DRY_RUN": "1"}
    )
    ids = {p.id for p in registry.all()}
    assert ids >= {
        "deepseek",
        "siliconflow-image",
        "mock-primary",
        "mock-economy",
        "mock-evaluator",
    }


def test_factory_production_without_mock() -> None:
    registry = build_default_registry(
        env={"DRAMA_FORGE_PROVIDER": "production", "DRAMA_FORGE_PROVIDER_DRY_RUN": "1"},
        enable_mock=False,
    )
    ids = {p.id for p in registry.all()}
    assert ids == {"deepseek", "siliconflow-image"}


def test_router_prefers_deepseek_for_text_over_mock_when_forced() -> None:
    registry = build_default_registry(
        env={
            "DRAMA_FORGE_PROVIDER": "production",
            "DRAMA_FORGE_PROVIDER_DRY_RUN": "1",
        },
        enable_mock=False,
    )
    router = ProviderRouter(registry)
    provider, decision = router.select(
        "text_generation", policy={"provider_id": "deepseek"}
    )
    assert provider.id == "deepseek"
    assert decision.selected == "deepseek"


def test_router_prefers_siliconflow_for_image_when_forced() -> None:
    registry = build_default_registry(
        env={"DRAMA_FORGE_PROVIDER": "production", "DRAMA_FORGE_PROVIDER_DRY_RUN": "1"},
        enable_mock=False,
    )
    router = ProviderRouter(registry)
    provider, decision = router.select(
        "image_generation", policy={"provider_id": "siliconflow-image"}
    )
    assert provider.id == "siliconflow-image"
    assert decision.selected == "siliconflow-image"


def test_router_balanced_selects_siliconflow_for_image_without_mocks() -> None:
    registry = build_default_registry(
        env={"DRAMA_FORGE_PROVIDER": "siliconflow", "DRAMA_FORGE_PROVIDER_DRY_RUN": "1"},
        enable_mock=False,
    )
    router = ProviderRouter(registry)
    provider, _decision = router.select("image_generation")
    assert provider.id == "siliconflow-image"


def test_registry_candidates_for_image_generation() -> None:
    registry = ProviderRegistry()
    registry.register(
        OpenAICompatibleProvider(deepseek_config_from_env({}).to_http_config(), env={})
    )
    registry.register(
        SiliconFlowImageProvider(SiliconFlowConfig(dry_run=True), env={})
    )
    image_providers = registry.candidates_for("image_generation")
    text_providers = registry.candidates_for("text_generation")
    assert [p.id for p in image_providers] == ["siliconflow-image"]
    assert [p.id for p in text_providers] == ["deepseek"]
