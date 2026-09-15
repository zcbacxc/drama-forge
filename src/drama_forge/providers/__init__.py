# SPDX-FileCopyrightText: 2026 zcbacxc
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Provider package: registry, router, factory, HTTP adapter, mocks, cost."""

from drama_forge.providers.adapters import MockEvaluatorProvider, MockProvider
from drama_forge.providers.agnes_video import (
    AgnesVideoConfig,
    AgnesVideoProvider,
    agnes_video_config_from_env,
)
from drama_forge.providers.base import Provider, ProviderRequest, ProviderResponse
from drama_forge.providers.cost import CostTracker, ExecutionCostSummary
from drama_forge.providers.deepseek import (
    DeepSeekPreset,
    deepseek_config_from_env,
)
from drama_forge.providers.factory import (
    build_default_registry,
    http_config_from_env,
    register_agnes_image_provider,
    register_agnes_video_provider,
    register_deepseek_provider,
    register_siliconflow_provider,
)
from drama_forge.providers.http_adapter import HttpProviderConfig, OpenAICompatibleProvider
from drama_forge.providers.registry import ProviderRegistry
from drama_forge.providers.router import ProviderRouter
from drama_forge.providers.siliconflow import (
    SiliconFlowConfig,
    SiliconFlowImageProvider,
    siliconflow_config_from_env,
)

__all__ = [
    "Provider",
    "ProviderRequest",
    "ProviderResponse",
    "ProviderRegistry",
    "ProviderRouter",
    "MockProvider",
    "MockEvaluatorProvider",
    "HttpProviderConfig",
    "OpenAICompatibleProvider",
    "DeepSeekPreset",
    "deepseek_config_from_env",
    "SiliconFlowConfig",
    "SiliconFlowImageProvider",
    "siliconflow_config_from_env",
    "CostTracker",
    "ExecutionCostSummary",
    "build_default_registry",
    "http_config_from_env",
    "register_deepseek_provider",
    "register_siliconflow_provider",
    "register_agnes_video_provider",
    "register_agnes_image_provider",
    "AgnesVideoConfig",
    "AgnesVideoProvider",
    "agnes_video_config_from_env",
]
