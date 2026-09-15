# SPDX-FileCopyrightText: 2026 zcbacxc
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Offline contract tests for Agnes /v1/videos video provider."""

from __future__ import annotations

import json
from typing import Any

import pytest

from drama_forge.domain.production import CanonicalGenerationSpec
from drama_forge.providers.agnes_video import (
    AgnesVideoConfig,
    AgnesVideoProvider,
    agnes_video_config_from_env,
)
from drama_forge.providers.base import ProviderRequest
from drama_forge.providers.factory import build_default_registry


def _request(
    capability: str = "video_generation",
    candidate_index: int = 0,
    inputs: dict[str, Any] | None = None,
) -> ProviderRequest:
    return ProviderRequest(
        capability=capability,
        generation_spec=CanonicalGenerationSpec(
            node_id="shot-1",
            capability=capability,
            inputs=inputs
            or {
                "description": "远景：两人在天台对峙",
                "characters": ["林默", "苏晚"],
                "location": "旧城区天台",
                "duration_seconds": 4.0,
            },
            camera_spec={"shot": "wide"},
            style_constraints={"style": "neo-noir anime"},
        ),
        candidate_index=candidate_index,
    )


class _FakeHTTPResponse:
    def __init__(self, body: bytes, status: int = 200):
        self._body = body
        self.status = status
        self.headers = {"Content-Type": "application/json"}

    def read(self) -> bytes:
        return self._body

    def getcode(self) -> int:
        return self.status

    def __enter__(self) -> _FakeHTTPResponse:
        return self

    def __exit__(self, *args: object) -> None:
        return None


def test_agnes_config_from_env_defaults() -> None:
    config = agnes_video_config_from_env({})
    assert config.model == "agnes-video-2.5-flash"
    assert config.mode == "t2v"
    assert config.provider_id == "agnes-video"
    assert config.capabilities == {"video_generation"}
    assert config.dry_run is False


def test_agnes_dry_run_offline_and_deterministic() -> None:
    provider = AgnesVideoProvider(AgnesVideoConfig(dry_run=True), env={})
    a = provider.generate(_request(candidate_index=0))
    b = provider.generate(_request(candidate_index=0))
    c = provider.generate(_request(candidate_index=1))
    assert provider.network_call_count == 0
    assert a.ok and b.ok and c.ok
    assert a.generation_metadata["digest"] == b.generation_metadata["digest"]
    assert a.generation_metadata["digest"] != c.generation_metadata["digest"]
    payload = json.loads(a.content)
    assert payload["mode"] == "dry_run_fallback"
    assert payload["video_url"].startswith("dry://video_generation/")


def test_agnes_missing_key_fallback() -> None:
    provider = AgnesVideoProvider(AgnesVideoConfig(), env={})
    response = provider.generate(_request())
    assert response.ok
    assert provider.network_call_count == 0
    assert response.provider_metadata["reason"] == "missing_api_key"


def test_agnes_builds_prompt_and_payload() -> None:
    provider = AgnesVideoProvider(AgnesVideoConfig(dry_run=True), env={})
    payload = provider._build_payload(_request())
    assert payload["model"] == "agnes-video-2.5-flash"
    assert payload["mode"] == "t2v"
    assert "天台" in payload["prompt"]
    assert "neo-noir anime" in payload["prompt"]
    assert "wide" in payload["prompt"]


def test_agnes_endpoint_uses_videos() -> None:
    provider = AgnesVideoProvider(
        AgnesVideoConfig(base_url="http://gateway:12580/v1", dry_run=True), env={}
    )
    assert provider._endpoint() == "http://gateway:12580/v1/videos"


def test_agnes_normalizes_video_url_response(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def fake_urlopen(req: Any, timeout: float | None = None) -> _FakeHTTPResponse:
        captured["url"] = req.full_url
        captured["body"] = json.loads(req.data.decode("utf-8"))
        payload = {
            "id": "task-123",
            "status": "succeeded",
            "url": "https://cdn.example.com/out.mp4",
        }
        return _FakeHTTPResponse(json.dumps(payload).encode("utf-8"))

    monkeypatch.setattr(
        "drama_forge.providers.agnes_video.urllib.request.urlopen", fake_urlopen
    )
    provider = AgnesVideoProvider(
        AgnesVideoConfig(api_key_env="AGNES_KEY", base_url="http://gw/v1"),
        env={"AGNES_KEY": "sk-test"},
    )
    response = provider.generate(_request())
    assert response.ok
    assert captured["url"] == "http://gw/v1/videos"
    assert captured["body"]["mode"] == "t2v"
    assert captured["body"]["prompt"]
    canonical = json.loads(response.content)
    assert canonical["video_url"] == "https://cdn.example.com/out.mp4"
    assert canonical["provider"] == "agnes-video"
    assert response.generation_metadata["digest"]


def test_agnes_saturation_error_is_ok_false(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(req: Any, timeout: float | None = None) -> _FakeHTTPResponse:
        raise __import__("urllib.error", fromlist=["HTTPError"]).HTTPError(
            url=req.full_url,
            code=429,
            msg="Too Many Requests",
            hdrs=None,  # type: ignore[arg-type]
            fp=__import__("io").BytesIO(
                json.dumps(
                    {
                        "code": "fail_to_fetch_task",
                        "message": "当前分组上游负载已饱和，请稍后再试",
                    }
                ).encode("utf-8")
            ),
        )

    monkeypatch.setattr(
        "drama_forge.providers.agnes_video.urllib.request.urlopen", fake_urlopen
    )
    provider = AgnesVideoProvider(
        AgnesVideoConfig(api_key_env="AGNES_KEY"), env={"AGNES_KEY": "sk"}
    )
    response = provider.generate(_request())
    assert response.ok is False
    assert response.error is not None
    assert "http_429" in response.error
    assert "fail_to_fetch_task" in response.error


def test_factory_registers_agnes_video() -> None:
    registry = build_default_registry(
        env={
            "DRAMA_FORGE_PROVIDER": "agnes",
            "DRAMA_FORGE_PROVIDER_DRY_RUN": "1",
        },
        enable_mock=False,
    )
    ids = {p.id for p in registry.all()}
    assert ids == {"agnes-video"}
    provider = registry.get("agnes-video")
    assert isinstance(provider, AgnesVideoProvider)
    assert provider.supports("video_generation")
    assert not provider.supports("image_generation")


def test_factory_combined_includes_agnes() -> None:
    registry = build_default_registry(
        env={
            "DRAMA_FORGE_PROVIDER": "deepseek+agnes",
            "DRAMA_FORGE_PROVIDER_DRY_RUN": "1",
        },
        enable_mock=False,
    )
    ids = {p.id for p in registry.all()}
    assert ids == {"deepseek", "agnes-video"}
