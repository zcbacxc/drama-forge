# SPDX-FileCopyrightText: 2026 zcbacxc
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Optional live smoke tests for OpenAI-compatible production providers.

Skipped automatically when ``DRAMA_FORGE_LIVE_SMOKE`` is not enabled.
DeepSeek is exercised through the shared OpenAI-compatible HTTP adapter
(no vendor-specific adapter). SiliconFlow image smoke requires its own key.

Example:

    export DRAMA_FORGE_DEEPSEEK_API_KEY=sk-...
    export DRAMA_FORGE_LIVE_SMOKE=1
    pytest tests/test_live_provider_smoke.py -v
"""

from __future__ import annotations

import os

import pytest

from drama_forge.providers.base import ProviderRequest
from drama_forge.providers.deepseek import deepseek_config_from_env
from drama_forge.providers.http_adapter import OpenAICompatibleProvider
from drama_forge.providers.siliconflow import (
    SiliconFlowConfig,
    SiliconFlowImageProvider,
)

pytestmark = pytest.mark.skipif(
    os.environ.get("DRAMA_FORGE_LIVE_SMOKE", "").lower() not in {"1", "true", "yes", "on"},
    reason="live smoke disabled; set DRAMA_FORGE_LIVE_SMOKE=1",
)


def _request(capability: str, text: str = "Say OK"):
    from drama_forge.domain.production import CanonicalGenerationSpec

    return ProviderRequest(
        capability=capability,
        generation_spec=CanonicalGenerationSpec(
            node_id="live-smoke",
            capability=capability,
            inputs={"description": text, "prompt": text},
        ),
    )


def test_deepseek_live_chat() -> None:
    if not os.environ.get("DRAMA_FORGE_DEEPSEEK_API_KEY"):
        pytest.skip("DRAMA_FORGE_DEEPSEEK_API_KEY not set")
    provider = OpenAICompatibleProvider(deepseek_config_from_env({}).to_http_config())
    response = provider.generate(
        _request("text_generation", "Reply with the single word OK")
    )
    assert response.ok, response.error
    assert response.content
    assert provider.network_call_count == 1
    assert response.provider_metadata.get("provider") == "deepseek"
    assert response.provider_metadata.get("model")


def test_siliconflow_live_image() -> None:
    if not os.environ.get("DRAMA_FORGE_SILICONFLOW_API_KEY"):
        pytest.skip("DRAMA_FORGE_SILICONFLOW_API_KEY not set")
    provider = SiliconFlowImageProvider(
        SiliconFlowConfig(
            image_model=os.environ.get(
                "DRAMA_FORGE_SILICONFLOW_IMAGE_MODEL", "Kwai-Kolors/Kolors"
            ),
            image_size=os.environ.get("DRAMA_FORGE_SILICONFLOW_IMAGE_SIZE", "1024x1024"),
        )
    )
    response = provider.generate(
        _request("image_generation", "neo-noir rooftop at night, anime style")
    )
    assert response.ok, response.error
    assert response.generation_metadata.get("image_url")
    assert provider.network_call_count == 1


def test_agnes_live_image() -> None:
    if not os.environ.get("DRAMA_FORGE_AGNES_API_KEY"):
        pytest.skip("DRAMA_FORGE_AGNES_API_KEY not set")
    from drama_forge.providers.factory import register_agnes_image_provider
    from drama_forge.providers.registry import ProviderRegistry

    registry = ProviderRegistry()
    register_agnes_image_provider(registry, dict(os.environ))
    provider = registry.get("agnes-image")
    assert provider is not None
    response = provider.generate(
        _request("image_generation", "neo-noir rooftop at night, anime style")
    )
    if not response.ok and response.error and "http_429" in response.error:
        pytest.skip(f"agnes image upstream saturated: {response.error[:120]}")
    assert response.ok, response.error
    assert response.generation_metadata.get("image_url")
    assert provider.network_call_count == 1
    print("image_url:", response.generation_metadata.get("image_url"))


def test_agnes_live_video() -> None:
    if not os.environ.get("DRAMA_FORGE_AGNES_API_KEY"):
        pytest.skip("DRAMA_FORGE_AGNES_API_KEY not set")
    from drama_forge.providers.agnes_video import (
        AgnesVideoProvider,
        agnes_video_config_from_env,
    )

    provider = AgnesVideoProvider(agnes_video_config_from_env())
    response = provider.generate(
        _request(
            "video_generation",
            "neo-noir rooftop at night, anime style, short clip",
        )
    )
    if not response.ok and response.error:
        if "http_429" in response.error or "invalid mode" in response.error:
            pytest.skip(f"agnes video upstream not ready: {response.error[:140]}")
    assert response.ok, response.error
    assert response.generation_metadata.get("video_url") or response.generation_metadata.get(
        "task_id"
    )
    assert provider.network_call_count == 1
