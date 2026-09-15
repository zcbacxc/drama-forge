# SPDX-FileCopyrightText: 2026 zcbacxc
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Build a default ProviderRegistry from environment configuration.

Environment variables (read via ``os.environ`` unless an ``env`` mapping is
passed to :func:`build_default_registry`):

- ``DRAMA_FORGE_PROVIDER``
    Provider family/families to register. Families may be combined with
    ``+`` or ``,``:

    - ``mock`` / unset — local mocks only
    - ``openai_compatible`` (aliases: ``openai``, ``http``) — generic
      OpenAI-compatible HTTP adapter
    - ``deepseek`` — DeepSeek via OpenAI-compatible HTTP preset (Stage C)
    - ``siliconflow`` (alias: ``sf``) — SiliconFlow image provider (Stage F)
    - ``agnes`` / ``agnes-video`` — Agnes ``/v1/videos`` video provider (Stage F)
    - ``agnes-image`` — Agnes ``/v1/images/generations`` image provider (Stage F)
    - ``production`` — alias for ``deepseek+siliconflow``

- ``DRAMA_FORGE_PROVIDER_BASE_URL`` / ``DRAMA_FORGE_PROVIDER_API_KEY`` /
  ``DRAMA_FORGE_PROVIDER_API_KEY_ENV`` / ``DRAMA_FORGE_PROVIDER_MODEL`` /
  ``DRAMA_FORGE_PROVIDER_TIMEOUT`` / ``DRAMA_FORGE_PROVIDER_DRY_RUN``
    Settings for the generic OpenAI-compatible adapter. ``DRAMA_FORGE_PROVIDER_DRY_RUN``
    is global: when truthy, every HTTP-backed adapter stays offline.

- ``DRAMA_FORGE_DEEPSEEK_*`` — DeepSeek-specific overrides
  (see :func:`drama_forge.providers.deepseek.deepseek_config_from_env`).

- ``DRAMA_FORGE_SILICONFLOW_*`` — SiliconFlow image-specific overrides
  (see :func:`drama_forge.providers.siliconflow.siliconflow_config_from_env`).

Mock providers (``mock-primary``, ``mock-economy``, ``mock-evaluator``) are
always registered when ``enable_mock=True`` so local/dev runs work with zero
configuration and without network access.
"""

from __future__ import annotations

import os
from collections.abc import Mapping

from drama_forge.providers.adapters import MockEvaluatorProvider, MockProvider
from drama_forge.providers.agnes_video import (
    AgnesVideoProvider,
    agnes_video_config_from_env,
)
from drama_forge.providers.deepseek import deepseek_config_from_env
from drama_forge.providers.http_adapter import HttpProviderConfig, OpenAICompatibleProvider
from drama_forge.providers.registry import ProviderRegistry
from drama_forge.providers.siliconflow import (
    SiliconFlowImageProvider,
    siliconflow_config_from_env,
)

_TRUTHY = {"1", "true", "yes", "on"}
_HTTP_KINDS = {"openai_compatible", "openai", "http", "openai-compatible"}
_MOCK_KINDS = {"", "mock", "local", "none"}
_DEEPSEEK_KINDS = {"deepseek", "ds"}
_SILICONFLOW_KINDS = {"siliconflow", "sf", "siliconflow-image"}
_AGNES_KINDS = {"agnes", "agnes-video", "agnes_video"}
_AGNES_IMAGE_KINDS = {"agnes-image", "agnes_image", "agnes-img"}
_PRODUCTION_ALIASES = {
    "production",
    "prod",
    "deepseek+siliconflow",
    "siliconflow+deepseek",
}


def _env_get(env: Mapping[str, str], key: str, default: str = "") -> str:
    value = env.get(key)
    if value is None:
        return default
    return str(value).strip()


def _env_bool(env: Mapping[str, str], key: str) -> bool:
    return _env_get(env, key).lower() in _TRUTHY


def _env_float(env: Mapping[str, str], key: str, default: float) -> float:
    raw = _env_get(env, key)
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _split_families(kind: str) -> list[str]:
    """Split a provider family expression into normalized tokens."""
    raw = kind.strip().lower()
    if raw in _PRODUCTION_ALIASES:
        return ["deepseek", "siliconflow"]
    known_single = (
        _MOCK_KINDS
        | _HTTP_KINDS
        | _DEEPSEEK_KINDS
        | _SILICONFLOW_KINDS
        | _AGNES_KINDS
        | _AGNES_IMAGE_KINDS
    )
    if raw in known_single:
        return [raw] if raw else ["mock"]
    if "+" in raw or "," in raw:
        parts = [p.strip() for p in raw.replace(",", "+").split("+") if p.strip()]
        return parts
    return [raw]


def register_mock_providers(registry: ProviderRegistry) -> None:
    """Register the standard local mock provider set.

    Args:
            registry: ProviderRegistry

    Returns:
            None
    """
    registry.register(MockProvider("mock-primary", quality_score=0.9))
    registry.register(
        MockProvider(
            "mock-economy",
            quality_score=0.6,
            cost_score=0.95,
            latency_score=0.95,
        )
    )
    registry.register(MockEvaluatorProvider())


def http_config_from_env(env: Mapping[str, str]) -> HttpProviderConfig:
    """Build HttpProviderConfig from environment variables.

    Args:
            env: Mapping[str, str]

    Returns:
            HttpProviderConfig
    """
    api_key_env = _env_get(env, "DRAMA_FORGE_PROVIDER_API_KEY_ENV")
    if not api_key_env:
        api_key_env = "DRAMA_FORGE_PROVIDER_API_KEY"
    return HttpProviderConfig(
        base_url=_env_get(
            env, "DRAMA_FORGE_PROVIDER_BASE_URL", "https://api.openai.com"
        ),
        api_key_env=api_key_env,
        model=_env_get(env, "DRAMA_FORGE_PROVIDER_MODEL", "gpt-4o-mini"),
        timeout_seconds=_env_float(env, "DRAMA_FORGE_PROVIDER_TIMEOUT", 30.0),
        provider_id=_env_get(env, "DRAMA_FORGE_PROVIDER_ID", "openai-compatible"),
        dry_run=_env_bool(env, "DRAMA_FORGE_PROVIDER_DRY_RUN"),
    )


def register_deepseek_provider(
    registry: ProviderRegistry, env: Mapping[str, str]
) -> OpenAICompatibleProvider:
    """Register DeepSeek via the shared OpenAI-compatible HTTP adapter.

    Args:
            registry: ProviderRegistry
            env: Mapping[str, str]

    Returns:
            OpenAICompatibleProvider
    """
    config = deepseek_config_from_env(env).to_http_config()
    provider = OpenAICompatibleProvider(config=config, env=dict(env))
    registry.register(provider)
    return provider


def register_siliconflow_provider(
    registry: ProviderRegistry, env: Mapping[str, str]
) -> SiliconFlowImageProvider:
    """Register the SiliconFlow image provider from env configuration.

    Args:
            registry: ProviderRegistry
            env: Mapping[str, str]

    Returns:
            SiliconFlowImageProvider
    """
    config = siliconflow_config_from_env(env)
    provider = SiliconFlowImageProvider(config=config, env=dict(env))
    registry.register(provider)
    return provider


def register_agnes_video_provider(
    registry: ProviderRegistry, env: Mapping[str, str]
) -> AgnesVideoProvider:
    """Register the Agnes /v1/videos provider from env configuration.

    Args:
            registry: ProviderRegistry
            env: Mapping[str, str]

    Returns:
            AgnesVideoProvider
    """
    config = agnes_video_config_from_env(env)
    provider = AgnesVideoProvider(config=config, env=dict(env))
    registry.register(provider)
    return provider


def register_agnes_image_provider(
    registry: ProviderRegistry, env: Mapping[str, str]
) -> SiliconFlowImageProvider:
    """Register Agnes image generation via the shared images HTTP adapter.

    Args:
            registry: ProviderRegistry
            env: Mapping[str, str]

    Returns:
            SiliconFlowImageProvider
    """
    from drama_forge.providers.siliconflow import SiliconFlowConfig

    def _get(key: str, default: str = "") -> str:
        value = env.get(key)
        if value is None:
            return default
        return str(value).strip()

    def _bool(key: str) -> bool:
        return _get(key).lower() in _TRUTHY

    api_key_env = _get("DRAMA_FORGE_AGNES_API_KEY_ENV") or "DRAMA_FORGE_AGNES_API_KEY"
    config = SiliconFlowConfig(
        base_url=_get("DRAMA_FORGE_AGNES_BASE_URL", "https://api.example.com/v1"),
        api_key_env=api_key_env,
        image_model=_get("DRAMA_FORGE_AGNES_IMAGE_MODEL", "agnes-image-2.0-flash"),
        image_size=_get("DRAMA_FORGE_AGNES_IMAGE_SIZE", "1024x1024"),
        provider_id=_get("DRAMA_FORGE_AGNES_IMAGE_ID", "agnes-image"),
        dry_run=_bool("DRAMA_FORGE_PROVIDER_DRY_RUN")
        or _bool("DRAMA_FORGE_AGNES_DRY_RUN")
        or _bool("DRAMA_FORGE_AGNES_IMAGE_DRY_RUN"),
    )
    provider = SiliconFlowImageProvider(config=config, env=dict(env))
    registry.register(provider)
    return provider


def build_default_registry(
    env: dict[str, str] | None = None,
    enable_mock: bool = True,
    http_config: HttpProviderConfig | None = None,
) -> ProviderRegistry:
    """Build a ProviderRegistry from environment configuration.

    Args:
        env: Environment mapping; defaults to ``os.environ``.
        enable_mock: When True, always register local mock providers.
        http_config: Optional explicit HTTP config; overrides env-derived
            HTTP settings when the env requests an HTTP provider.

    Returns:
        A registry with mocks (optional) and any requested real providers.
    """
    resolved_env: Mapping[str, str] = os.environ if env is None else env
    registry = ProviderRegistry()
    if enable_mock:
        register_mock_providers(registry)

    kind = _env_get(resolved_env, "DRAMA_FORGE_PROVIDER").lower()
    for family in _split_families(kind):
        if family in _MOCK_KINDS:
            continue
        if family in _HTTP_KINDS:
            config = http_config or http_config_from_env(resolved_env)
            registry.register(
                OpenAICompatibleProvider(config=config, env=dict(resolved_env))
            )
            continue
        if family in _DEEPSEEK_KINDS:
            register_deepseek_provider(registry, resolved_env)
            continue
        if family in _SILICONFLOW_KINDS:
            register_siliconflow_provider(registry, resolved_env)
            continue
        if family in _AGNES_KINDS:
            register_agnes_video_provider(registry, resolved_env)
            continue
        if family in _AGNES_IMAGE_KINDS:
            register_agnes_image_provider(registry, resolved_env)
            continue
        # Unknown family token: keep previously registered providers.
    return registry
