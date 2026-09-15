# SPDX-FileCopyrightText: 2026 zcbacxc
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Agnes video provider for Stage F production access (gateway /v1/videos).

Live-verified contract against the New-API / AgnesAI gateway:

- Endpoint: ``POST {base_url}/videos`` when base ends with ``/v1``
- Auth: ``Authorization: Bearer <api-key>``
- Required body fields: ``model``, ``mode``, ``prompt``
- ``mode`` is required; gateway validation is flaky (``t2v`` / ``T2V`` /
  ``text2video`` may each be accepted or rejected intermittently).
  Default is ``t2v``; override with ``DRAMA_FORGE_AGNES_MODE``.
- Video models: ``agnes-video-2.5-flash``, ``agnes-video-2.5``, ``agnes-video-v2.0``
- These models **cannot** be used on ``/images/generations`` or chat
  (gateway returns 400 ``Use /v1/videos``)
- When upstream is busy: HTTP 429
  ``{"code":"fail_to_fetch_task","message":"当前分组上游负载已饱和..."}``

Missing key or ``dry_run`` returns a deterministic offline fallback.
Network/HTTP failures are returned as ``ok=False`` (never raised).
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

# Gateway root is deployment-specific; set DRAMA_FORGE_AGNES_BASE_URL.
AGNES_BASE_URL = "https://api.example.com/v1"
AGNES_DEFAULT_MODEL = "agnes-video-2.5-flash"
AGNES_API_KEY_ENV = "DRAMA_FORGE_AGNES_API_KEY"
AGNES_CAPABILITIES: set[str] = {"video_generation"}


@dataclass(slots=True)
class AgnesVideoConfig:
    """Agnes /v1/videos adapter configuration.

    Attributes:
        base_url: Gateway root including ``/v1``.
        api_key_env: Environment variable holding the API key.
        model: Video model id.
        mode: Generation mode (``t2v``).
        timeout_seconds: Per-request timeout.
        provider_id: Registry id.
        capabilities: Capabilities claimed by this provider.
        dry_run: When True, never open a network connection.
        cost_per_video: Optional cost model when the API omits cost.
        quality_score: Routing quality score.
        reliability: Routing reliability score.
        cost_score: Routing cost score (higher = cheaper).
        latency_score: Routing latency score (higher = faster).
        extra_headers: Extra HTTP headers merged into each request.
        extra_body: Extra JSON fields merged into the request body.
    """

    base_url: str = AGNES_BASE_URL
    api_key_env: str = AGNES_API_KEY_ENV
    model: str = AGNES_DEFAULT_MODEL
    mode: str = "t2v"
    timeout_seconds: float = 180.0
    provider_id: str = "agnes-video"
    capabilities: set[str] = field(default_factory=lambda: set(AGNES_CAPABILITIES))
    dry_run: bool = False
    cost_per_video: float = 0.0
    quality_score: float = 0.84
    reliability: float = 0.88
    cost_score: float = 0.75
    latency_score: float = 0.55
    extra_headers: dict[str, str] = field(default_factory=dict)
    extra_body: dict[str, Any] = field(default_factory=dict)


class AgnesVideoProvider(Provider):
    """Video generation adapter for Agnes ``/v1/videos``.

    Contract:
    - Missing API key or ``dry_run=True`` → deterministic fallback
      (``ok=True``, zero cost, no network I/O).
    - HTTP/network/parse failures → ``ok=False`` ProviderResponse.
    - Successful responses normalize into Canonical JSON with video URL
      (or task id) and generation metadata.
    """

    def __init__(
        self,
        config: AgnesVideoConfig | None = None,
        env: Mapping[str, str] | None = None,
    ) -> None:
        """Initialize the adapter.

        Args:
            config: Agnes video configuration; defaults used when omitted.
            env: Optional environment mapping used to resolve the API key.
        """
        self.config = config or AgnesVideoConfig()
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
        """Execute one video generation request (or return a dry-run fallback)."""
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

    def _endpoint(self) -> str:
        """Resolve POST /videos URL."""
        base = self.config.base_url.rstrip("/")
        if base.endswith("/v1"):
            return f"{base}/videos"
        return f"{base}/v1/videos"

    def _build_prompt(self, request: ProviderRequest) -> str:
        """Build a video prompt from the canonical generation spec."""
        spec = request.generation_spec
        inputs = spec.inputs or {}
        parts: list[str] = []
        description = inputs.get("description") or inputs.get("shot_description")
        if description:
            parts.append(str(description))
        characters = inputs.get("characters") or inputs.get("character_names")
        if characters:
            if isinstance(characters, (list, tuple)):
                parts.append("characters: " + ", ".join(str(c) for c in characters))
            else:
                parts.append(f"characters: {characters}")
        location = inputs.get("location") or inputs.get("scene")
        if location:
            parts.append(f"location: {location}")
        camera = spec.camera_spec or {}
        if camera.get("shot") or camera.get("angle"):
            parts.append(
                "camera: "
                + ", ".join(f"{k}={camera[k]}" for k in ("shot", "angle") if camera.get(k))
            )
        style = spec.style_constraints or {}
        if style.get("style"):
            parts.append(f"style: {style['style']}")
        duration = inputs.get("duration_seconds") or spec.output_requirements.get(
            "duration_seconds"
        )
        if duration:
            parts.append(f"duration: {duration}s")
        if not parts:
            parts.append(f"generate video for node {spec.node_id}")
        return "; ".join(parts)

    def _build_payload(self, request: ProviderRequest) -> dict[str, Any]:
        """Build the JSON request body for /videos."""
        payload: dict[str, Any] = {
            "model": self.config.model,
            "mode": self.config.mode,
            "prompt": self._build_prompt(request),
        }
        payload.update(self.config.extra_body)
        return payload

    def _fallback_response(
        self, request: ProviderRequest, reason: str
    ) -> ProviderResponse:
        """Build a deterministic offline response; never touches the network."""
        payload = self._build_payload(request)
        spec_hash = request.generation_spec.fingerprint()
        seed = f"{spec_hash}:{request.candidate_index}:{self.id}:{reason}"
        digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]
        canonical: dict[str, Any] = {
            "provider": self.id,
            "mode": "dry_run_fallback",
            "reason": reason,
            "model": self.config.model,
            "capability": request.capability,
            "node_id": request.generation_spec.node_id,
            "candidate_index": request.candidate_index,
            "digest": digest,
            "video_url": f"dry://video_generation/{digest}",
            "prompt": payload.get("prompt"),
            "gen_mode": payload.get("mode"),
        }
        content = json.dumps(canonical, sort_keys=True)
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
                "video_url": canonical["video_url"],
            },
            cost=0.0,
            latency_ms=0.0,
            usage={"units": 0, "offline": True},
        )

    def _http_generate(self, request: ProviderRequest, api_key: str) -> ProviderResponse:
        """Perform the HTTP call and normalize the result."""
        url = self._endpoint()
        payload = self._build_payload(request)
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {api_key}",
            "User-Agent": "drama-forge/0.1",
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
                provider_metadata={
                    "provider": self.id,
                    "model": self.config.model,
                },
                latency_ms=latency_ms,
            )
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
            latency_ms = (time.perf_counter() - started) * 1000.0
            return ProviderResponse(
                ok=False,
                error=f"network_error: {exc}",
                provider_metadata={
                    "provider": self.id,
                    "model": self.config.model,
                },
                latency_ms=latency_ms,
            )
        except Exception as exc:  # noqa: BLE001 - adapter must never raise
            latency_ms = (time.perf_counter() - started) * 1000.0
            return ProviderResponse(
                ok=False,
                error=f"unexpected_error: {exc}",
                provider_metadata={
                    "provider": self.id,
                    "model": self.config.model,
                },
                latency_ms=latency_ms,
            )

        try:
            data = json.loads(raw_body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            return ProviderResponse(
                ok=False,
                error=f"invalid_json_response: {exc}",
                technical_metadata={"http_status": status},
                provider_metadata={
                    "provider": self.id,
                    "model": self.config.model,
                },
                latency_ms=latency_ms,
            )

        return self._normalize_response(
            data,
            request=request,
            latency_ms=latency_ms,
            http_status=status,
            request_payload=payload,
        )

    def _normalize_response(
        self,
        data: dict[str, Any],
        request: ProviderRequest,
        latency_ms: float,
        http_status: int,
        request_payload: dict[str, Any],
    ) -> ProviderResponse:
        """Normalize Agnes /videos payload into ProviderResponse."""
        # Nested error envelopes (fail_to_fetch_task etc.)
        if data.get("code") in {"fail_to_fetch_task", "invalid_request"} and data.get(
            "message"
        ):
            return ProviderResponse(
                ok=False,
                error=str(data.get("message")),
                technical_metadata={"http_status": http_status},
                provider_metadata={
                    "provider": self.id,
                    "model": self.config.model,
                },
                latency_ms=latency_ms,
            )

        video_url, task_id = self._extract_video_refs(data)
        if not video_url and not task_id:
            return ProviderResponse(
                ok=False,
                error="missing_video_url_or_task_id",
                technical_metadata={"http_status": http_status, "raw_keys": sorted(data)},
                provider_metadata={
                    "provider": self.id,
                    "model": self.config.model,
                },
                latency_ms=latency_ms,
            )

        spec_hash = request.generation_spec.fingerprint()
        seed_value = task_id or video_url or ""
        digest = hashlib.sha256(
            f"{spec_hash}:{request.candidate_index}:{seed_value}".encode()
        ).hexdigest()[:16]
        canonical = {
            "provider": self.id,
            "model": self.config.model,
            "capability": request.capability,
            "node_id": request.generation_spec.node_id,
            "candidate_index": request.candidate_index,
            "digest": digest,
            "video_url": video_url,
            "task_id": task_id,
            "mode": request_payload.get("mode"),
        }
        content = json.dumps(canonical, sort_keys=True)
        return ProviderResponse(
            ok=True,
            content=content,
            media_type="application/json",
            technical_metadata={
                "http_status": http_status,
                "video_url": video_url,
                "task_id": task_id,
                "digest": digest,
                "bytes": len(content.encode("utf-8")),
            },
            provider_metadata={
                "provider": self.id,
                "model": self.config.model,
                "endpoint_style": "videos",
            },
            generation_metadata={
                "capability": request.capability,
                "node_id": request.generation_spec.node_id,
                "candidate_index": request.candidate_index,
                "spec_hash": spec_hash,
                "digest": digest,
                "video_url": video_url,
                "task_id": task_id,
            },
            cost=self.config.cost_per_video,
            latency_ms=latency_ms,
            usage={"videos": 1},
        )

    @staticmethod
    def _extract_video_refs(data: dict[str, Any]) -> tuple[str, str]:
        """Best-effort extraction of (video_url, task_id) from response shapes."""
        video_url = ""
        task_id = ""

        def walk(obj: Any) -> None:
            nonlocal video_url, task_id
            if isinstance(obj, dict):
                for key, value in obj.items():
                    lk = str(key).lower()
                    if not video_url and lk in {
                        "video_url",
                        "video",
                        "url",
                        "output",
                        "result",
                        "mp4",
                    }:
                        if isinstance(value, str) and (
                            value.startswith("http")
                            or value.startswith("dry://")
                            or value.endswith(".mp4")
                        ):
                            video_url = value
                    if not task_id and lk in {"task_id", "taskid", "id", "request_id"}:
                        if isinstance(value, str) and value:
                            # avoid treating short completion ids as tasks when url exists
                            task_id = value
                    walk(value)
            elif isinstance(obj, list):
                for item in obj:
                    walk(item)

        walk(data)
        # Prefer explicit nested video fields over generic id
        if isinstance(data.get("data"), dict):
            inner = data["data"]
            for key in ("video_url", "url", "video"):
                value = inner.get(key)
                if isinstance(value, str) and value:
                    video_url = value
                    break
            if inner.get("task_id"):
                task_id = str(inner["task_id"])
        return video_url, task_id


def agnes_video_config_from_env(env: Mapping[str, str] | None = None) -> AgnesVideoConfig:
    """Build AgnesVideoConfig from environment variables.

    Recognized keys:
    - ``DRAMA_FORGE_AGNES_BASE_URL`` (default gateway ``/v1`` root)
    - ``DRAMA_FORGE_AGNES_API_KEY`` / ``DRAMA_FORGE_AGNES_API_KEY_ENV``
    - ``DRAMA_FORGE_AGNES_MODEL`` (default ``agnes-video-2.5-flash``)
    - ``DRAMA_FORGE_AGNES_MODE`` (default ``t2v``)
    - ``DRAMA_FORGE_AGNES_TIMEOUT`` (default ``180``)
    - ``DRAMA_FORGE_AGNES_ID`` (registry id, default ``agnes-video``)
    - ``DRAMA_FORGE_PROVIDER_DRY_RUN`` (global dry-run)

    Args:
        env: Environment mapping; defaults to ``os.environ``.

    Returns:
        An AgnesVideoConfig ready for adapter construction.
    """
    resolved: Mapping[str, str] = os.environ if env is None else env

    def _get(key: str, default: str = "") -> str:
        value = resolved.get(key)
        if value is None:
            return default
        return str(value).strip()

    def _bool(key: str) -> bool:
        return _get(key).lower() in {"1", "true", "yes", "on"}

    def _float(key: str, default: float) -> float:
        raw = _get(key)
        if not raw:
            return default
        try:
            return float(raw)
        except ValueError:
            return default

    api_key_env = _get("DRAMA_FORGE_AGNES_API_KEY_ENV") or AGNES_API_KEY_ENV
    return AgnesVideoConfig(
        base_url=_get("DRAMA_FORGE_AGNES_BASE_URL", AGNES_BASE_URL),
        api_key_env=api_key_env,
        model=_get("DRAMA_FORGE_AGNES_MODEL", AGNES_DEFAULT_MODEL),
        mode=_get("DRAMA_FORGE_AGNES_MODE", "t2v"),
        timeout_seconds=_float("DRAMA_FORGE_AGNES_TIMEOUT", 180.0),
        provider_id=_get("DRAMA_FORGE_AGNES_ID", "agnes-video"),
        dry_run=_bool("DRAMA_FORGE_PROVIDER_DRY_RUN")
        or _bool("DRAMA_FORGE_AGNES_DRY_RUN"),
    )
