"""Provider base contracts."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from drama_forge.domain.production import CanonicalGenerationSpec


@dataclass(slots=True)
class ProviderRequest:
    """Normalized request sent to a provider adapter."""

    capability: str
    generation_spec: CanonicalGenerationSpec
    inputs: dict[str, Any] = field(default_factory=dict)
    policy: dict[str, Any] = field(default_factory=dict)
    candidate_index: int = 0


@dataclass(slots=True)
class ProviderResponse:
    """Normalized response absorbed into Canonical Result."""

    ok: bool
    content: bytes | str = ""
    media_type: str = "application/json"
    technical_metadata: dict[str, Any] = field(default_factory=dict)
    provider_metadata: dict[str, Any] = field(default_factory=dict)
    generation_metadata: dict[str, Any] = field(default_factory=dict)
    cost: float = 0.0
    latency_ms: float = 0.0
    usage: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


class Provider(ABC):
    """External generation service adapter."""

    id: str
    capabilities: set[str]
    quality_score: float = 1.0
    reliability: float = 1.0
    cost_score: float = 1.0
    latency_score: float = 1.0

    @abstractmethod
    def generate(self, request: ProviderRequest) -> ProviderResponse:
        """Execute one generation request."""
        raise NotImplementedError

    def supports(self, capability: str) -> bool:
        """Whether this provider can handle the capability."""
        return capability in self.capabilities
