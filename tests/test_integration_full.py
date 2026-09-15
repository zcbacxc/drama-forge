"""Integration tests for Engine + SQLite persistence and full-stack features."""

from __future__ import annotations

from pathlib import Path

from drama_forge.engine import Engine


def test_engine_with_sqlite_persistence(tmp_path: Path, sample_story_dict: dict) -> None:
    """Engine run persists execution history into SQLite."""
    db_path = tmp_path / "history.db"
    engine = Engine(artifact_root=tmp_path / "artifacts", db_path=db_path)
    story = engine.compile(sample_story_dict)
    result = engine.run(story, candidate_count=1)
    assert result.status.value == "SUCCEEDED"

    assert engine.db is not None
    exec_row = engine._repos["execution"].get(result.execution_id)
    assert exec_row is not None
    assert exec_row["status"] == "SUCCEEDED"

    story_row = engine._repos["story"].get(story.id)
    assert story_row is not None
    assert story_row["title"] == story.title

    assert engine.artifact_store.all()
    decisions = engine._repos["decision"].list_by_execution(result.execution_id)
    assert decisions


def test_timeline_dialogue_audio_nodes(sample_story_dict: dict, tmp_path: Path) -> None:
    """Shots with dialogue produce dialogue audio nodes and audio artifacts."""
    engine = Engine(artifact_root=tmp_path / "artifacts")
    story = engine.compile(sample_story_dict)
    result = engine.run(story, candidate_count=1)
    actions = {n.action for n in result.graph.nodes.values()}
    assert "generate_dialogue_audio" in actions
    audio_artifacts = [
        a
        for a in result.artifacts()
        if a.artifact_type.value == "audio"
    ]
    assert audio_artifacts


def test_cli_version() -> None:
    """CLI version command reports package version."""
    from drama_forge.cli.main import main

    assert main(["version"]) == 0
