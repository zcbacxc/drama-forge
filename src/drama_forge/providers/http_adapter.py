# SPDX-FileCopyrightText: 2026 zcbacxc
# SPDX-License-Identifier: AGPL-3.0-or-later
"""HTTP provider adapter for OpenAI-compatible and generic generate endpoints.

Uses only the standard library (``urllib``). Never requires network access in
tests: when ``dry_run`` is enabled or no API key is available in the
environment, ``generate()`` returns a deterministic fallback response.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from drama_forge.providers.base import Provider, ProviderRequest, ProviderResponse

DEFAULT_CAPABILITIES: set[str] = {
    "text_generation",
    "vision_evaluation",
    "continuity_validation",
    "selection",
}

# Capability → endpoint style. Styles:
# - "chat": POST {base_url}/{chat_path} (OpenAI-compatible, default v1/chat/completions)
# - "generate": POST {base_url}/generate (generic JSON contract)
DEFAULT_CAPABILITY_MAP: dict[str, str] = {
    "text_generation": "chat",
    "vision_evaluation": "chat",
    "continuity_validation": "chat",
    "selection": "chat",
    "image_generation": "generate",
    "video_generation": "generate",
    "audio_generation": "generate",
    "timeline_assembly": "generate",
}


@dataclass(slots=True)
class HttpProviderConfig:
    """Configuration for an HTTP-backed provider adapter.

    Attributes:
        base_url: Service root, with or without a trailing ``/v1``.
        api_key_env: Environment variable name that holds the API key.
        model: Model identifier sent to the provider.
        timeout_seconds: Per-request socket timeout.
        provider_id: Registry id for this provider instance.
        capabilities: Capabilities this provider claims to support.
        capability_map: Capability name → endpoint style (``chat`` / ``generate``).
        chat_path: Relative path for chat completions. Default OpenAI style
            ``v1/chat/completions``. Set ``chat/completions`` for vendors that
            expose OpenAI-compatible chat without a ``/v1`` prefix (e.g. DeepSeek).
        max_tokens: Maximum completion tokens for chat-style calls.
        temperature: Sampling temperature for chat-style calls.
        dry_run: When True, never open a network connection.
        cost_per_1k_tokens: Optional cost model when the API omits cost.
        quality_score: Routing quality score.
        reliability: Routing reliability score.
        cost_score: Routing cost score (higher = cheaper/better).
        latency_score: Routing latency score (higher = faster/better).
        extra_headers: Additional HTTP headers merged into each request.
    """

    base_url: str = "https://api.openai.com"
    api_key_env: str = "DRAMA_FORGE_PROVIDER_API_KEY"
    model: str = "gpt-4o-mini"
    timeout_seconds: float = 30.0
    provider_id: str = "openai-compatible"
    capabilities: set[str] = field(default_factory=lambda: set(DEFAULT_CAPABILITIES))
    capability_map: dict[str, str] = field(
        default_factory=lambda: dict(DEFAULT_CAPABILITY_MAP)
    )
    chat_path: str = "v1/chat/completions"
    max_tokens: int = 1024
    temperature: float = 0.7
    dry_run: bool = False
    cost_per_1k_tokens: float = 0.0
    quality_score: float = 0.85
    reliability: float = 0.9
    cost_score: float = 0.5
    latency_score: float = 0.6
    extra_headers: dict[str, str] = field(default_factory=dict)


class OpenAICompatibleProvider(Provider):
    """Provider adapter for OpenAI-compatible chat or generic generate APIs.

    Contract:
    - Missing API key or ``dry_run=True`` 鈫?deterministic fallback response
      (``ok=True``, zero cost, no network I/O).
    - Network/HTTP/parse failures 鈫?``ok=False`` ProviderResponse with error
      text; the adapter never raises out of ``generate()``.
    - Successful responses are normalized into ``ProviderResponse`` with
      content, metadata, cost, latency, and usage.
    """

    def __init__(
        self,
        config: HttpProviderConfig | None = None,
        env: Mapping[str, str] | None = None,
    ) -> None:
        """Initialize the adapter.

        Args:
            config: HTTP provider configuration; defaults used when omitted.
            env: Optional environment mapping used to resolve the API key.
                When None, ``os.environ`` is consulted at call time.
        """
        self.config = config or HttpProviderConfig()
        self.id = self.config.provider_id
        self.capabilities = set(self.config.capabilities)
        self.quality_score = self.config.quality_score
        self.reliability = self.config.reliability
        self.cost_score = self.config.cost_score
        self.latency_score = self.config.latency_score
        self._env = env
        self.call_count = 0
        self.network_call_count = 0

    def generate(self, request: ProviderRequest) -> ProviderResponse:
        """Execute one generation request (or return a dry-run fallback)."""
        self.call_count += 1
        api_key = self._resolve_api_key()
        if self.config.dry_run or not api_key:
            reason = "dry_run" if self.config.dry_run else "missing_api_key"
            return self._fallback_response(request, reason=reason)
        return self._http_generate(request, api_key=api_key)

    def _resolve_api_key(self) -> str:
        """Read the API key from the bound env mapping or process env."""
        if self._env is not None:
            return (self._env.get(self.config.api_key_env) or "").strip()
        return (os.environ.get(self.config.api_key_env) or "").strip()

    def _endpoint(self, style: str) -> str:
        """Resolve the request URL for an endpoint style.

        Joining rules for chat:
        - default ``chat_path=v1/chat/completions`` with base ``https://api.openai.com``
          → ``https://api.openai.com/v1/chat/completions``
        - base already ending in ``/v1`` keeps that prefix; a leading ``v1/``
          in ``chat_path`` is dropped so ``/v1`` is never doubled or lost
        - DeepSeek official: base ``https://api.deepseek.com`` +
          ``chat_path=chat/completions`` → ``https://api.deepseek.com/chat/completions``
        """
        base = self.config.base_url.rstrip("/")
        if style == "generate":
            if base.endswith("/v1"):
                base = base[: -len("/v1")]
            return f"{base}/generate"
        chat_path = (self.config.chat_path or "v1/chat/completions").strip("/")
        if base.endswith("/v1") and chat_path.startswith("v1/"):
            chat_path = chat_path[3:]
        if not chat_path:
            chat_path = "chat/completions"
        return f"{base}/{chat_path}"

    def _fallback_response(
        self, request: ProviderRequest, reason: str
    ) -> ProviderResponse:
        """Build a deterministic offline response; never touches the network."""
        spec_hash = request.generation_spec.fingerprint()
        seed = f"{spec_hash}:{request.candidate_index}:{self.id}:{reason}"
        digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]
        payload: dict[str, Any] = {
            "provider": self.id,
            "mode": "dry_run_fallback",
            "reason": reason,
            "model": self.config.model,
            "capability": request.capability,
            "node_id": request.generation_spec.node_id,
            "candidate_index": request.candidate_index,
            "digest": digest,
            "content": f"dry://{request.capability}/{digest}",
        }
        content = json.dumps(payload, sort_keys=True)
        return ProviderResponse(
            ok=True,
            content=content,
            media_type="application/json",
            technical_metadata={
                "digest": digest,
                "bytes": len(content.encode("utf-8")),
                "offline": True,
            },
            provider_metadata={
                "provider": self.id,
                "model": self.config.model,
                "mode": "dry_run_fallback",
                "reason": reason,
            },
            generation_metadata={
                "spec_hash": spec_hash,
                "candidate_index": request.candidate_index,
                "seed": seed,
                "digest": digest,
            },
            cost=0.0,
            latency_ms=0.0,
            usage={"units": 0, "offline": True},
        )

    def _build_messages(self, request: ProviderRequest) -> list[dict[str, str]]:
        """Build chat messages from the canonical generation spec."""
        spec = request.generation_spec
        system = (
            "You are a generation backend for Drama Forge. "
            "Return only the requested artifact content as JSON when possible."
        )
        user_parts = [
            f"capability={request.capability}",
            f"node_id={spec.node_id}",
            f"candidate_index={request.candidate_index}",
        ]
        if spec.inputs:
            user_parts.append(f"inputs={json.dumps(spec.inputs, sort_keys=True)}")
        if spec.style_constraints:
            user_parts.append(
                f"style_constraints={json.dumps(spec.style_constraints, sort_keys=True)}"
            )
        if spec.output_requirements:
            user_parts.append(
                "output_requirements="
                f"{json.dumps(spec.output_requirements, sort_keys=True)}"
            )
        if request.policy:
            user_parts.append(f"policy={json.dumps(request.policy, sort_keys=True)}")
        return [
            {"role": "system", "content": system},
            {"role": "user", "content": "\n".join(user_parts)},
        ]

    def _build_payload(self, request: ProviderRequest, style: str) -> dict[str, Any]:
        """Build the JSON request body for the chosen endpoint style."""
        if style == "generate":
            spec = request.generation_spec
            return {
                "model": self.config.model,
                "capability": request.capability,
                "node_id": spec.node_id,
                "candidate_index": request.candidate_index,
                "inputs": spec.inputs,
                "style_constraints": spec.style_constraints,
                "output_requirements": spec.output_requirements,
                "max_tokens": self.config.max_tokens,
            }
        return {
            "model": self.config.model,
            "messages": self._build_messages(request),
            "max_tokens": self.config.max_tokens,
            "temperature": self.config.temperature,
        }

    def _http_generate(self, request: ProviderRequest, api_key: str) -> ProviderResponse:
        """Perform the HTTP call and normalize the result."""
        style = self.config.capability_map.get(request.capability, "chat")
        url = self._endpoint(style)
        payload = self._build_payload(request, style)
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {api_key}",
            "User-Agent": "drama-forge/0.1.0",
        }
        headers.update(self.config.extra_headers)
        body = json.dumps(payload).encode("utf-8")
        http_request = urllib.request.Request(
            url, data=body, headers=headers, method="POST"
        )
        started = time.perf_counter()
        try:
            self.network_call_count += 1
            with urllib.request.urlopen(
                http_request, timeout=self.config.timeout_seconds
            ) as raw:
                status = getattr(raw, "status", None) or raw.getcode()
                raw_body = raw.read()
            latency_ms = (time.perf_counter() - started) * 1000.0
        except urllib.error.HTTPError as exc:
            latency_ms = (time.perf_counter() - started) * 1000.0
            detail = ""
            try:
                detail = exc.read().decode("utf-8", errors="replace")[:500]
            except Exception:  # noqa: BLE001 - best-effort body read
                detail = ""
            return ProviderResponse(
                ok=False,
                error=f"http_{exc.code}: {exc.reason} {detail}".strip(),
                provider_metadata={"provider": self.id, "model": self.config.model},
                latency_ms=latency_ms,
            )
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
            latency_ms = (time.perf_counter() - started) * 1000.0
            return ProviderResponse(
                ok=False,
                error=f"network_error: {exc}",
                provider_metadata={"provider": self.id, "model": self.config.model},
                latency_ms=latency_ms,
            )
        except Exception as exc:  # noqa: BLE001 - adapter must never raise
            latency_ms = (time.perf_counter() - started) * 1000.0
            return ProviderResponse(
                ok=False,
                error=f"unexpected_error: {exc}",
                provider_metadata={"provider": self.id, "model": self.config.model},
                latency_ms=latency_ms,
            )

        try:
            data = json.loads(raw_body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            return ProviderResponse(
                ok=False,
                error=f"invalid_json_response: {exc}",
                technical_metadata={"http_status": status},
                provider_metadata={"provider": self.id, "model": self.config.model},
                latency_ms=latency_ms,
            )

        return self._normalize_response(data, request=request, latency_ms=latency_ms)

    def _normalize_response(
        self,
        data: dict[str, Any],
        request: ProviderRequest,
        latency_ms: float,
    ) -> ProviderResponse:
        """Normalize an OpenAI-style or generic payload into ProviderResponse."""
        content, finish_reason = self._extract_content(data)
        usage = self._extract_usage(data)
        cost = self._extract_cost(data, usage)
        return ProviderResponse(
            ok=True,
            content=content,
            media_type="application/json",
            technical_metadata={
                "finish_reason": finish_reason,
                "bytes": len(content.encode("utf-8")) if isinstance(content, str) else 0,
            },
            provider_metadata={
                "provider": self.id,
                "model": data.get("model") or self.config.model,
                "endpoint_style": self.config.capability_map.get(
                    request.capability, "chat"
                ),
            },
            generation_metadata={
                "capability": request.capability,
                "node_id": request.generation_spec.node_id,
                "candidate_index": request.candidate_index,
                "response_id": data.get("id"),
            },
            cost=cost,
            latency_ms=latency_ms,
            usage=usage,
        )

    @staticmethod
    def _extract_content(data: dict[str, Any]) -> tuple[str, str | None]:
        """Pull text content from OpenAI chat or generic response shapes.

        Reasoning models may return empty ``content`` and fill
        ``reasoning_content``; fall back to that field when present.
        """
        choices = data.get("choices")
        if isinstance(choices, list) and choices:
            first = choices[0] or {}
            message = first.get("message") or {}
            if isinstance(message, dict):
                content = message.get("content")
                if content:
                    return str(content), first.get("finish_reason")
                reasoning = message.get("reasoning_content")
                if reasoning:
                    return str(reasoning), first.get("finish_reason")
                if content is not None:
                    return str(content), first.get("finish_reason")
            if first.get("text") is not None:
                return str(first["text"]), first.get("finish_reason")
        for key in ("content", "output", "text", "result"):
            if data.get(key) is not None:
                value = data[key]
                if isinstance(value, (dict, list)):
                    return json.dumps(value, sort_keys=True), None
                return str(value), None
        return json.dumps(data, sort_keys=True), None

    @staticmethod
    def _extract_usage(data: dict[str, Any]) -> dict[str, Any]:
        """Normalize token/usage accounting fields."""
        usage_raw = data.get("usage")
        if not isinstance(usage_raw, dict):
            return {}
        normalized: dict[str, Any] = {}
        for key in (
            "prompt_tokens",
            "completion_tokens",
            "total_tokens",
            "input_tokens",
            "output_tokens",
        ):
            if usage_raw.get(key) is not None:
                try:
                    normalized[key] = int(usage_raw[key])
                except (TypeError, ValueError):
                    normalized[key] = usage_raw[key]
        return normalized

    def _extract_cost(
        self, data: dict[str, Any], usage: dict[str, Any]
    ) -> float:
        """Prefer explicit cost; otherwise estimate from token usage."""
        explicit = data.get("cost")
        if explicit is not None:
            try:
                return float(explicit)
            except (TypeError, ValueError):
                pass
        total_tokens = usage.get("total_tokens")
        if total_tokens is None:
            total_tokens = (
                int(usage.get("prompt_tokens") or 0)
                + int(usage.get("completion_tokens") or 0)
            )
        if self.config.cost_per_1k_tokens > 0 and total_tokens:
            return float(total_tokens) / 1000.0 * self.config.cost_per_1k_tokens
        return 0.0
