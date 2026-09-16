# SPDX-FileCopyrightText: 2026 zcbacxc
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Mock providers for local end-to-end validation (no external APIs)."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from drama_forge.providers.base import Provider, ProviderRequest, ProviderResponse


class MockProvider(Provider):
    """Deterministic mock provider for any capability.

    Content is derived from generation spec fingerprint + candidate index so
    identical production conditions reuse identical outputs, while different
    candidates differ.
    """

    def __init__(
        self,
        provider_id: str,
        capabilities: set[str] | None = None,
        quality_score: float = 0.8,
        reliability: float = 1.0,
        cost_score: float = 0.7,
        latency_score: float = 0.9,
        fail_nodes: set[str] | None = None,
        quality_bias: float = 0.0,
        fail_retryable: bool = True,
    ) -> None:
        """__init__.

        Args:
                    provider_id: str
                    capabilities: default None
                    quality_score: default 0.8
                    reliability: default 1.0
                    cost_score: default 0.7
                    latency_score: default 0.9
                    fail_nodes: default None
                    quality_bias: default 0.0
                    fail_retryable: whether fail_nodes errors are retryable
        """
        self.id = provider_id
        self.capabilities = capabilities or {
            "text_generation",
            "image_generation",
            "video_generation",
            "audio_generation",
            "vision_evaluation",
            "continuity_validation",
            "timeline_assembly",
            "selection",
        }
        self.quality_score = quality_score
        self.reliability = reliability
        self.cost_score = cost_score
        self.latency_score = latency_score
        self.fail_nodes = fail_nodes or set()
        self.quality_bias = quality_bias
        self.fail_retryable = fail_retryable
        self.call_count = 0

    def generate(self, request: ProviderRequest) -> ProviderResponse:
        """Produce a deterministic mock artifact payload.

        Args:
                    request: ProviderRequest

        Returns:
                    ProviderResponse
        """
        self.call_count += 1
        node_id = request.generation_spec.node_id
        if node_id in self.fail_nodes:
            return ProviderResponse(
                ok=False,
                error=f"mock failure for node {node_id}",
                provider_metadata={"provider": self.id},
                retryable=self.fail_retryable,
            )

        spec_hash = request.generation_spec.fingerprint()
        seed = f"{spec_hash}:{request.candidate_index}:{self.id}"
        digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]
        payload: dict[str, Any] = {
            "provider": self.id,
            "capability": request.capability,
            "node_id": node_id,
            "candidate_index": request.candidate_index,
            "digest": digest,
            "content": f"mock://{request.capability}/{digest}",
            "quality_bias": self.quality_bias,
        }
        content = json.dumps(payload, sort_keys=True)
        return ProviderResponse(
            ok=True,
            content=content,
            media_type="application/json",
            technical_metadata={
                "digest": digest,
                "bytes": len(content.encode("utf-8")),
            },
            provider_metadata={
                "provider": self.id,
                "model": f"mock-{self.id}",
            },
            generation_metadata={
                "spec_hash": spec_hash,
                "candidate_index": request.candidate_index,
                "seed": seed,
                "digest": digest,
            },
            cost=0.01 * max(1, int(request.generation_spec.candidate_count)),
            latency_ms=1.0,
            usage={"units": request.candidate_index + 1},
        )


class MockEvaluatorProvider(Provider):
    """Mock vision evaluator producing scores based on digests."""

    def __init__(self, provider_id: str = "mock-evaluator") -> None:
        """__init__.

        Args:
                    provider_id: default 'mock-evaluator'
        """
        self.id = provider_id
        self.capabilities = {"vision_evaluation", "continuity_validation"}
        self.quality_score = 0.85
        self.reliability = 1.0
        self.cost_score = 0.9
        self.latency_score = 0.95
        self.call_count = 0

    def generate(self, request: ProviderRequest) -> ProviderResponse:
        """Return evaluation scores as JSON content.

        Args:
                    request: ProviderRequest

        Returns:
                    ProviderResponse
        """
        self.call_count += 1
        inputs = request.inputs
        candidate_digests = inputs.get("candidate_digests") or []
        character_ids = request.generation_spec.continuity_constraints.get(
            "characters", []
        )
        scores = []
        for index, digest in enumerate(candidate_digests):
            # deterministic pseudo-score from digest
            value = int(digest[:2], 16) / 255.0 if digest else 0.5
            continuity = 0.6 + 0.3 * value
            if character_ids:
                continuity = min(1.0, continuity + 0.05 * len(character_ids))
            scores.append(
                {
                    "candidate_index": index,
                    "digest": digest,
                    "quality_score": round(0.5 + 0.45 * value, 4),
                    "constraint_score": round(0.55 + 0.4 * value, 4),
                    "continuity_score": round(continuity, 4),
                    "technical_score": round(0.7 + 0.25 * value, 4),
                }
            )
        payload = {"scores": scores, "provider": self.id}
        content = json.dumps(payload, sort_keys=True)
        return ProviderResponse(
            ok=True,
            content=content,
            media_type="application/json",
            technical_metadata={"candidate_count": len(scores)},
            provider_metadata={"provider": self.id, "model": "mock-vision"},
            generation_metadata={"evaluated": len(scores)},
            cost=0.001,
            latency_ms=0.5,
        )
