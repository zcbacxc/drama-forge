# SPDX-FileCopyrightText: 2026 zcbacxc
# SPDX-License-Identifier: AGPL-3.0-or-later
"""SiliconFlow image-generation provider for Stage C/F production access.

Contract (https://docs.siliconflow.cn/cn/api-reference/images/images-generations):
- Base URL: ``https://api.siliconflow.cn``
- Endpoint: ``POST /v1/images/generations``
- Auth: ``Authorization: Bearer <api-key>``
- Request body (OpenAI Images-compatible subset + SiliconFlow extras):

  .. code-block:: json

     {
       "model": "Kwai-Kolors/Kolors",
       "prompt": "...",
       "negative_prompt": "...",
       "image_size": "1024x1024",
       "batch_size": 1,
       "seed": 42,
       "num_inference_steps": 20,
       "guidance_scale": 7.5
     }

- Response body:

  .. code-block:: json

     {
       "images": [{"url": "https://..."}],
       "timings": {"inference": 1.23},
       "seed": 42
     }

Missing key or ``dry_run`` returns a deterministic offline fallback (no
network). Live responses are absorbed into a Canonical JSON artifact that
carries the image URL and generation metadata — the third-party response
shape never leaks into the production model.
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

SILICONFLOW_BASE_URL = "https://api.siliconflow.cn"
SILICONFLOW_DEFAULT_IMAGE_MODEL = "Kwai-Kolors/Kolors"
SILICONFLOW_DEFAULT_IMAGE_SIZE = "1024x1024"
SILICONFLOW_API_KEY_ENV = "DRAMA_FORGE_SILICONFLOW_API_KEY"
SILICONFLOW_CAPABILITIES: set[str] = {"image_generation"}


@dataclass(slots=True)
class SiliconFlowConfig:
    """SiliconFlow image adapter configuration.

    Attributes:
        base_url: SiliconFlow API root.
        api_key_env: Environment variable holding the API key.
        image_model: Image model id (e.g. ``Kwai-Kolors/Kolors``).
        image_size: Requested image size, e.g. ``1024x1024``.
        timeout_seconds: Per-request timeout.
        provider_id: Registry id.
        capabilities: Capabilities claimed by this provider.
        dry_run: When True, never open a network connection.
        fetch_image_bytes: When True and not dry-run, download the image
            URL into artifact bytes; otherwise store canonical URL JSON.
        cost_per_image: Optional cost model when the API omits cost.
        quality_score: Routing quality score.
        reliability: Routing reliability score.
        cost_score: Routing cost score (higher = cheaper).
        latency_score: Routing latency score (higher = faster).
        extra_headers: Extra HTTP headers merged into each request.
        extra_body: Extra JSON fields merged into the request body.
    """

    base_url: str = SILICONFLOW_BASE_URL
    api_key_env: str = SILICONFLOW_API_KEY_ENV
    image_model: str = SILICONFLOW_DEFAULT_IMAGE_MODEL
    image_size: str = SILICONFLOW_DEFAULT_IMAGE_SIZE
    timeout_seconds: float = 120.0
    provider_id: str = "siliconflow-image"
    capabilities: set[str] = field(default_factory=lambda: set(SILICONFLOW_CAPABILITIES))
    dry_run: bool = False
    fetch_image_bytes: bool = False
    cost_per_image: float = 0.0
    quality_score: float = 0.86
    reliability: float = 0.9
    cost_score: float = 0.8
    latency_score: float = 0.7
    extra_headers: dict[str, str] = field(default_factory=dict)
    extra_body: dict[str, Any] = field(default_factory=dict)


class SiliconFlowImageProvider(Provider):
    """Image generation adapter for SiliconFlow ``/v1/images/generations``.

    Contract:
    - Missing API key or ``dry_run=True`` → deterministic fallback
      (``ok=True``, zero cost, no network I/O).
    - Network/HTTP/parse failures → ``ok=False`` ProviderResponse; the
      adapter never raises out of ``generate()``.
    - Successful responses normalize into a Canonical JSON payload with
      image URL, seed, timings, and generation metadata.
    """

    def __init__(
        self,
        config: SiliconFlowConfig | None = None,
        env: Mapping[str, str] | None = None,
    ) -> None:
        """Initialize the adapter.

        Args:
            config: SiliconFlow configuration; defaults used when omitted.
            env: Optional environment mapping used to resolve the API key.
        """
        self.config = config or SiliconFlowConfig()
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
        """Execute one image generation request (or return a dry-run fallback).

        Args:
                    request: ProviderRequest

        Returns:
                    ProviderResponse
        """
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
        """Resolve the images generations URL."""
        base = self.config.base_url.rstrip("/")
        if base.endswith("/v1"):
            return f"{base}/images/generations"
        return f"{base}/v1/images/generations"

    def _build_prompt(self, request: ProviderRequest) -> tuple[str, str]:
        """Build positive and negative prompts from the canonical generation spec.

        Returns:
            Tuple of (prompt, negative_prompt).
        """
        spec = request.generation_spec
        parts: list[str] = []
        inputs = spec.inputs or {}

        description = inputs.get("description") or inputs.get("shot_description")
        if description:
            parts.append(str(description))

        characters = inputs.get("characters") or inputs.get("character_names")
        if characters:
            if isinstance(characters, (list, tuple)):
                names = ", ".join(str(c) for c in characters)
            else:
                names = str(characters)
            parts.append(f"characters: {names}")

        appearance = inputs.get("appearance") or inputs.get("character_appearance")
        if appearance:
            parts.append(f"appearance: {appearance}")

        location = inputs.get("location") or inputs.get("scene")
        if location:
            parts.append(f"location: {location}")

        style = spec.style_constraints or {}
        style_bits: list[str] = []
        for key in ("style", "palette", "mood", "render"):
            if style.get(key):
                style_bits.append(f"{key}={style[key]}")
        if style_bits:
            parts.append("style: " + ", ".join(style_bits))

        camera = spec.camera_spec or {}
        if camera.get("shot") or camera.get("angle"):
            parts.append(
                "camera: "
                + ", ".join(
                    f"{k}={camera[k]}" for k in ("shot", "angle") if camera.get(k)
                )
            )

        if not parts:
            parts.append(f"generate image for node {spec.node_id}")

        negative_parts: list[str] = []
        negative = style.get("negative") or spec.output_requirements.get("negative_prompt")
        if negative:
            negative_parts.append(str(negative))
        negative_parts.append("lowres, blurry, watermark, text artifacts, deformed hands")

        return "; ".join(parts), ", ".join(negative_parts)

    def _build_payload(self, request: ProviderRequest) -> dict[str, Any]:
        """Build the JSON request body for images/generations."""
        prompt, negative_prompt = self._build_prompt(request)
        spec = request.generation_spec
        output = spec.output_requirements or {}
        image_size = str(
            output.get("image_size")
            or self.config.extra_body.get("image_size")
            or self.config.image_size
        )
        payload: dict[str, Any] = {
            "model": self.config.image_model,
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "image_size": image_size,
            "batch_size": 1,
        }
        # Deterministic seed per candidate so re-runs with same conditions
        # map to the same seed when the provider honors it.
        seed_source = f"{spec.fingerprint()}:{request.candidate_index}:{self.id}"
        seed = int(hashlib.sha256(seed_source.encode("utf-8")).hexdigest()[:8], 16)
        payload["seed"] = seed
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
            "model": self.config.image_model,
            "capability": request.capability,
            "node_id": request.generation_spec.node_id,
            "candidate_index": request.candidate_index,
            "digest": digest,
            "image_url": f"dry://image_generation/{digest}",
            "image_size": payload.get("image_size"),
            "prompt": payload.get("prompt"),
            "seed": payload.get("seed"),
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
                "image_size": canonical["image_size"],
            },
            provider_metadata={
                "provider": self.id,
                "model": self.config.image_model,
                "mode": "dry_run_fallback",
                "reason": reason,
            },
            generation_metadata={
                "spec_hash": spec_hash,
                "candidate_index": request.candidate_index,
                "seed": seed,
                "digest": digest,
                "image_url": canonical["image_url"],
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
                provider_metadata={
                    "provider": self.id,
                    "model": self.config.image_model,
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
                    "model": self.config.image_model,
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
                    "model": self.config.image_model,
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
                    "model": self.config.image_model,
                },
                latency_ms=latency_ms,
            )

        return self._normalize_response(
            data,
            request=request,
            latency_ms=latency_ms,
            request_payload=payload,
            http_status=status,
        )

    def _normalize_response(
        self,
        data: dict[str, Any],
        request: ProviderRequest,
        latency_ms: float,
        request_payload: dict[str, Any],
        http_status: int,
    ) -> ProviderResponse:
        """Normalize SiliconFlow or OpenAI-style images payload into ProviderResponse."""
        image_url = self._extract_image_url(data)
        if not image_url:
            return ProviderResponse(
                ok=False,
                error="missing_image_url_in_response",
                technical_metadata={"http_status": http_status},
                provider_metadata={
                    "provider": self.id,
                    "model": self.config.image_model,
                },
                latency_ms=latency_ms,
            )

        spec_hash = request.generation_spec.fingerprint()
        seed_value = data.get("seed", request_payload.get("seed"))
        digest_source = f"{spec_hash}:{request.candidate_index}:{image_url}:{seed_value}"
        digest = hashlib.sha256(digest_source.encode("utf-8")).hexdigest()[:16]

        content: bytes | str
        media_type = "application/json"
        technical: dict[str, Any] = {
            "http_status": http_status,
            "image_url": image_url,
            "image_size": request_payload.get("image_size"),
            "seed": seed_value,
            "digest": digest,
        }
        if self.config.fetch_image_bytes:
            fetched = self._download_image(image_url)
            if fetched is not None:
                content, media_type = fetched
                technical["bytes"] = len(content)
                technical["fetched"] = True
            else:
                content = self._canonical_payload(
                    image_url=image_url,
                    digest=digest,
                    seed=seed_value,
                    request=request,
                    data=data,
                )
                technical["bytes"] = len(content.encode("utf-8"))
                technical["fetched"] = False
        else:
            content = self._canonical_payload(
                image_url=image_url,
                digest=digest,
                seed=seed_value,
                request=request,
                data=data,
            )
            technical["bytes"] = len(content.encode("utf-8"))
            technical["fetched"] = False

        usage: dict[str, Any] = {"images": 1}
        if isinstance(data.get("timings"), dict):
            usage["inference_seconds"] = data["timings"].get("inference")

        cost = self.config.cost_per_image
        if data.get("cost") is not None:
            try:
                cost = float(data["cost"])
            except (TypeError, ValueError):
                pass

        return ProviderResponse(
            ok=True,
            content=content,
            media_type=media_type,
            technical_metadata=technical,
            provider_metadata={
                "provider": self.id,
                "model": self.config.image_model,
                "endpoint_style": "images_generations",
            },
            generation_metadata={
                "capability": request.capability,
                "node_id": request.generation_spec.node_id,
                "candidate_index": request.candidate_index,
                "spec_hash": spec_hash,
                "seed": seed_value,
                "digest": digest,
                "image_url": image_url,
            },
            cost=cost,
            latency_ms=latency_ms,
            usage=usage,
        )

    @staticmethod
    def _extract_image_url(data: dict[str, Any]) -> str:
        """Extract image URL from SiliconFlow or OpenAI Images response shapes."""
        # SiliconFlow: {"images": [{"url": "..."}]}
        images = data.get("images")
        if isinstance(images, list) and images:
            first = images[0] or {}
            if isinstance(first, dict):
                url = str(first.get("url") or first.get("image_url") or "")
                if url:
                    return url
            elif isinstance(first, str):
                return first
        # OpenAI Images: {"data": [{"url": "..."}]}
        items = data.get("data")
        if isinstance(items, list) and items:
            first = items[0] or {}
            if isinstance(first, dict):
                url = str(first.get("url") or "")
                if url:
                    return url
            elif isinstance(first, str):
                return first
        return str(data.get("url") or data.get("image_url") or "")

    def _canonical_payload(
        self,
        *,
        image_url: str,
        digest: str,
        seed: Any,
        request: ProviderRequest,
        data: dict[str, Any],
    ) -> str:
        """Build the Canonical Production Model JSON artifact body."""
        canonical: dict[str, Any] = {
            "provider": self.id,
            "model": self.config.image_model,
            "capability": request.capability,
            "node_id": request.generation_spec.node_id,
            "candidate_index": request.candidate_index,
            "digest": digest,
            "image_url": image_url,
            "seed": seed,
        }
        if isinstance(data.get("timings"), dict):
            canonical["timings"] = data["timings"]
        return json.dumps(canonical, sort_keys=True)

    def _download_image(self, url: str) -> tuple[bytes, str] | None:
        """Best-effort image download; returns None on any failure."""
        try:
            req = urllib.request.Request(url, method="GET")
            req.add_header("User-Agent", "drama-forge/0.1.0")
            with urllib.request.urlopen(req, timeout=self.config.timeout_seconds) as raw:
                body = raw.read()
                content_type = (raw.headers.get("Content-Type") or "image/png").split(";")[0]
            return body, content_type
        except Exception:  # noqa: BLE001 - optional enhancement only
            return None


def siliconflow_config_from_env(env: Mapping[str, str] | None = None) -> SiliconFlowConfig:
    """Build SiliconFlowConfig from environment variables.

    Recognized keys:
    - ``DRAMA_FORGE_SILICONFLOW_BASE_URL`` (default ``https://api.siliconflow.cn``)
    - ``DRAMA_FORGE_SILICONFLOW_API_KEY`` / ``DRAMA_FORGE_SILICONFLOW_API_KEY_ENV``
    - ``DRAMA_FORGE_SILICONFLOW_IMAGE_MODEL`` (default ``Kwai-Kolors/Kolors``)
    - ``DRAMA_FORGE_SILICONFLOW_IMAGE_SIZE`` (default ``1024x1024``)
    - ``DRAMA_FORGE_SILICONFLOW_TIMEOUT`` (default ``120``)
    - ``DRAMA_FORGE_SILICONFLOW_ID`` (registry id, default ``siliconflow-image``)
    - ``DRAMA_FORGE_SILICONFLOW_FETCH_BYTES`` (download image bytes when set)
    - ``DRAMA_FORGE_PROVIDER_DRY_RUN`` (global dry-run)

    Args:
        env: Environment mapping; defaults to ``os.environ``.

    Returns:
        A SiliconFlowConfig ready for adapter construction.
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

    api_key_env = _get("DRAMA_FORGE_SILICONFLOW_API_KEY_ENV") or SILICONFLOW_API_KEY_ENV
    return SiliconFlowConfig(
        base_url=_get("DRAMA_FORGE_SILICONFLOW_BASE_URL", SILICONFLOW_BASE_URL),
        api_key_env=api_key_env,
        image_model=_get(
            "DRAMA_FORGE_SILICONFLOW_IMAGE_MODEL", SILICONFLOW_DEFAULT_IMAGE_MODEL
        ),
        image_size=_get(
            "DRAMA_FORGE_SILICONFLOW_IMAGE_SIZE", SILICONFLOW_DEFAULT_IMAGE_SIZE
        ),
        timeout_seconds=_float("DRAMA_FORGE_SILICONFLOW_TIMEOUT", 120.0),
        provider_id=_get("DRAMA_FORGE_SILICONFLOW_ID", "siliconflow-image"),
        dry_run=_bool("DRAMA_FORGE_PROVIDER_DRY_RUN")
        or _bool("DRAMA_FORGE_SILICONFLOW_DRY_RUN"),
        fetch_image_bytes=_bool("DRAMA_FORGE_SILICONFLOW_FETCH_BYTES"),
    )
