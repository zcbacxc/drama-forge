# SPDX-FileCopyrightText: 2026 zcbacxc
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Cross-instance checkpoint resume via durable DB (W1 / F27)."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import pytest

from drama_forge.domain.common import ExecutionStatus
from drama_forge.engine import Engine


def _make_engine(tmp_path: Path, tag: str, db_name: str = "history.db") -> Engine:
    return Engine(
        artifact_root=tmp_path / f"artifacts-{tag}",
        db_path=tmp_path / db_name,
    )


def test_resume_across_new_engine_from_db(
    tmp_path: Path, sample_story_dict: dict[str, Any]
) -> None:
    """A brand-new Engine with the same db_path can resume the checkpoint."""
    engine_a = _make_engine(tmp_path, "a")
    story_a = engine_a.compile(sample_story_dict)
    first = engine_a.run(story_a, candidate_count=1)
    assert first.status == ExecutionStatus.SUCCEEDED

    # Durable checkpoint exists after run (not only in memory).
    db_cp = engine_a._repos["checkpoint"].load(first.execution_id)
    assert db_cp is not None
    assert db_cp.completed_nodes

    engine_b = _make_engine(tmp_path, "b")
    story_b = engine_b.compile(sample_story_dict)
    assert engine_b.checkpoint_store.load(first.execution_id) is not None

    resumed = engine_b.run(
        story_b, candidate_count=1, resume_execution_id=first.execution_id
    )
    assert resumed.status == ExecutionStatus.SUCCEEDED
    # F14 decision B: resume keeps fingerprint reuse enabled.
    assert resumed.context.config.get("enable_fingerprint_reuse") is True
    # Restored completed nodes stay SUCCEEDED (equivalent skip).
    for nid in db_cp.completed_nodes:
        assert resumed.graph.nodes[nid].status.value == "SUCCEEDED"


def test_resume_miss_raises_key_error(
    tmp_path: Path, sample_story_dict: dict[str, Any]
) -> None:
    """Unknown resume ids fail loudly instead of silently starting a new run."""
    engine = _make_engine(tmp_path, "miss")
    story = engine.compile(sample_story_dict)
    with pytest.raises(KeyError, match="unknown execution for resume"):
        engine.run(story, candidate_count=1, resume_execution_id="exec_does_not_exist")


def test_resume_miss_raises_on_fresh_engine_without_db_row(
    tmp_path: Path, sample_story_dict: dict[str, Any]
) -> None:
    """Memory-only miss on a different Engine also raises when DB has no row."""
    engine_a = _make_engine(tmp_path, "a")
    story_a = engine_a.compile(sample_story_dict)
    first = engine_a.run(story_a, candidate_count=1)
    assert first.status == ExecutionStatus.SUCCEEDED

    engine_b = Engine(artifact_root=tmp_path / "artifacts-b")  # no db_path
    story_b = engine_b.compile(sample_story_dict)
    with pytest.raises(KeyError, match="unknown execution for resume"):
        engine_b.run(
            story_b, candidate_count=1, resume_execution_id=first.execution_id
        )


def test_resume_graph_fingerprint_mismatch_rejected(
    tmp_path: Path, sample_story_dict: dict[str, Any]
) -> None:
    """Different production definition (candidate_count) rejects resume."""
    engine_a = _make_engine(tmp_path, "a")
    story_a = engine_a.compile(sample_story_dict)
    first = engine_a.run(story_a, candidate_count=1)
    assert first.status == ExecutionStatus.SUCCEEDED

    engine_b = _make_engine(tmp_path, "b")
    story_b = engine_b.compile(sample_story_dict)
    with pytest.raises(ValueError, match="graph fingerprint mismatch"):
        engine_b.run(
            story_b, candidate_count=2, resume_execution_id=first.execution_id
        )


def test_resume_input_fingerprint_mismatch_rejected(
    tmp_path: Path, sample_story_dict: dict[str, Any]
) -> None:
    """Different story content rejects resume via input fingerprint."""
    engine_a = _make_engine(tmp_path, "a")
    story_a = engine_a.compile(sample_story_dict)
    first = engine_a.run(story_a, candidate_count=1)
    assert first.status == ExecutionStatus.SUCCEEDED

    altered = copy.deepcopy(sample_story_dict)
    altered["title"] = "黎明回声·改写"
    altered["characters"][0]["appearance"] = "银色长发，黑色作战服"

    engine_b = _make_engine(tmp_path, "b")
    story_b = engine_b.compile(altered)
    with pytest.raises(ValueError, match="fingerprint mismatch"):
        engine_b.run(
            story_b, candidate_count=1, resume_execution_id=first.execution_id
        )


def test_status_falls_back_to_db_on_new_engine(
    tmp_path: Path, sample_story_dict: dict[str, Any]
) -> None:
    """status() resolves a prior execution from durable history."""
    engine_a = _make_engine(tmp_path, "a")
    story_a = engine_a.compile(sample_story_dict)
    first = engine_a.run(story_a, candidate_count=1)
    assert first.status == ExecutionStatus.SUCCEEDED

    engine_b = _make_engine(tmp_path, "b")
    status = engine_b.status(first.execution_id)
    assert status is not None
    assert status["status"] == "SUCCEEDED"
    assert status["completed_nodes"]
