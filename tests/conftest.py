"""Shared test fixtures for Drama Forge Core Engine."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from drama_forge.engine import Engine

SAMPLE_STORY: dict[str, Any] = {
    "title": "黎明回声",
    "world": {"name": "近未来都市", "style": "neo-noir anime"},
    "characters": [
        {
            "name": "林默",
            "appearance": "黑色短发，灰色风衣",
            "personality": "冷静",
        },
        {
            "name": "苏晚",
            "appearance": "棕色长发，米色针织衫",
            "personality": "敏锐",
        },
    ],
    "props": [{"name": "旧怀表", "description": "表盖内侧刻有回声图案"}],
    "episodes": [
        {
            "title": "第一集",
            "scenes": [
                {
                    "location": "旧城区天台",
                    "description": "雨夜霓虹",
                    "characters": ["林默", "苏晚"],
                    "shots": [
                        {
                            "description": "远景对峙",
                            "camera": "wide",
                            "duration_seconds": 4.0,
                            "characters": ["林默", "苏晚"],
                        },
                        {
                            "description": "近景怀表",
                            "dialogue": "你说的回声，是什么时候开始的？",
                            "camera": "close-up",
                            "duration_seconds": 3.5,
                            "characters": ["林默"],
                        },
                    ],
                }
            ],
        }
    ],
}


@pytest.fixture
def sample_story_dict() -> dict[str, Any]:
    """Return the sample story dictionary."""
    return SAMPLE_STORY


@pytest.fixture
def engine(tmp_path: Path) -> Engine:
    """Return an engine with isolated artifact store."""
    return Engine(artifact_root=tmp_path / "artifacts")


@pytest.fixture
def story(engine: Engine, sample_story_dict: dict[str, Any]):
    """Return a compiled sample story."""
    return engine.compile(sample_story_dict)
