"""SQLite persistence layer tests."""

from __future__ import annotations

from pathlib import Path

from drama_forge.persistence import (
    SCHEMA_VERSION,
    ArtifactRepository,
    CheckpointRepository,
    Database,
    DecisionRepository,
    ExecutionRepository,
    GraphRepository,
    QualityRepository,
    RepairRepository,
    StoryRepository,
)
from drama_forge.runtime.checkpoint import Checkpoint


def _migrated_db() -> Database:
    db = Database(":memory:")
    db.migrate()
    return db


def test_migrate_in_memory_db() -> None:
    """Database.migrate creates schema and sets user_version."""
    db = _migrated_db()
    assert db.schema_version() == SCHEMA_VERSION
    tables = {
        row["name"]
        for row in db.connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    expected = {
        "stories",
        "production_manifests",
        "production_graphs",
        "executions",
        "checkpoints",
        "artifacts",
        "artifact_provenance",
        "decision_records",
        "quality_results",
        "quality_issues",
        "repair_plans",
    }
    assert expected.issubset(tables)
    db.close()


def test_migrate_is_idempotent(tmp_path: Path) -> None:
    """Re-running migrate does not change schema version."""
    path = tmp_path / "df.db"
    db = Database(path)
    assert db.migrate() == SCHEMA_VERSION
    assert db.migrate() == SCHEMA_VERSION
    db.close()


def test_story_roundtrip_and_fingerprint_lookup() -> None:
    """Stories round-trip payload and support fingerprint lookup."""
    db = _migrated_db()
    repo = StoryRepository(db)
    payload = {
        "title": "黎明回声",
        "characters": [{"name": "林默"}, {"name": "苏晚"}],
        "episodes": [{"title": "第一集", "scenes": [{"shots": [1, 2]}]}],
    }
    repo.save("story_a", "黎明回声", 2, payload, fingerprint="fp_story_a")
    loaded = repo.get("story_a")
    assert loaded is not None
    assert loaded["title"] == "黎明回声"
    assert loaded["version"] == 2
    assert loaded["payload"] == payload
    by_fp = repo.find_by_fingerprint("fp_story_a")
    assert by_fp is not None
    assert by_fp["id"] == "story_a"
    assert repo.get("missing") is None
    assert repo.delete("story_a") is True
    assert repo.get("story_a") is None
    db.close()


def test_manifest_and_graph_roundtrip() -> None:
    """Manifests and graphs persist policies, nodes, and fingerprints."""
    db = _migrated_db()
    repo = GraphRepository(db)
    repo.save_manifest(
        "man_1",
        story_id="story_a",
        story_version=1,
        production_spec_id="spec_1",
        graph_id="graph_1",
        provider_policy={"prefer": ["mock-primary"]},
        asset_versions={"asset_x": 3},
        fingerprint="fp_man_1",
        payload={"extra": True},
    )
    manifest = repo.get_manifest("man_1")
    assert manifest is not None
    assert manifest["story_id"] == "story_a"
    assert manifest["provider_policy"] == {"prefer": ["mock-primary"]}
    assert manifest["asset_versions"] == {"asset_x": 3}
    assert manifest["payload"] == {"extra": True}
    assert repo.find_manifest_by_fingerprint("fp_man_1")["id"] == "man_1"  # type: ignore[index]

    nodes = [
        {"id": "n1", "name": "char_ref", "action": "build_character_reference"},
        {"id": "n2", "name": "shot", "action": "generate_shot_candidates"},
    ]
    edges = [{"source_id": "n1", "target_id": "n2", "kind": "depends_on"}]
    repo.save_graph(
        "graph_1",
        name="episode-1",
        version=1,
        nodes=nodes,
        edges=edges,
        policy={"candidate_count": 2},
        fingerprint="fp_graph_1",
    )
    graph = repo.get_graph("graph_1")
    assert graph is not None
    assert graph["name"] == "episode-1"
    assert graph["nodes"] == nodes
    assert graph["edges"] == edges
    assert graph["policy"] == {"candidate_count": 2}
    assert repo.find_graph_by_fingerprint("fp_graph_1")["id"] == "graph_1"  # type: ignore[index]
    assert [m["id"] for m in repo.list_manifests_by_story("story_a")] == ["man_1"]
    db.close()


def test_execution_fingerprint_lookups() -> None:
    """Executions store status and are findable by fingerprints."""
    db = _migrated_db()
    repo = ExecutionRepository(db)
    repo.save(
        "exec_1",
        graph_id="graph_1",
        status="RUNNING",
        graph_fingerprint="fp_graph",
        input_fingerprint="fp_input",
        config={"enable_fingerprint_reuse": True},
    )
    repo.save(
        "exec_2",
        graph_id="graph_1",
        status="SUCCEEDED",
        graph_fingerprint="fp_graph",
        input_fingerprint="fp_input_other",
        result_summary={"nodes": 8},
    )
    assert repo.get("exec_1")["status"] == "RUNNING"  # type: ignore[index]
    assert repo.update_status("exec_1", "SUCCEEDED", result_summary={"ok": True}) is True
    loaded = repo.get("exec_1")
    assert loaded is not None
    assert loaded["status"] == "SUCCEEDED"
    assert loaded["result_summary"] == {"ok": True}
    assert loaded["config"] == {"enable_fingerprint_reuse": True}
    by_graph_fp = repo.find_by_graph_fingerprint("fp_graph")
    assert {e["id"] for e in by_graph_fp} == {"exec_1", "exec_2"}
    by_input_fp = repo.find_by_input_fingerprint("fp_input")
    assert [e["id"] for e in by_input_fp] == ["exec_1"]
    assert {e["id"] for e in repo.list_by_status("SUCCEEDED")} == {"exec_1", "exec_2"}
    assert len(repo.list_by_graph("graph_1")) == 2
    assert repo.update_status("missing", "FAILED") is False
    db.close()


def test_checkpoint_roundtrip() -> None:
    """Checkpoints round-trip through the repository as Checkpoint objects."""
    db = _migrated_db()
    repo = CheckpointRepository(db)
    checkpoint = Checkpoint(
        graph_id="graph_1",
        execution_id="exec_1",
        graph_fingerprint="fp_graph",
        input_fingerprint="fp_input",
        completed_nodes=["n1", "n2"],
        node_outputs={"n1": {"artifact_id": "art_1"}},
        node_status={"n1": "SUCCEEDED", "n2": "RUNNING"},
        artifact_refs={"n1": ["art_1"]},
        candidate_refs={"n2": ["cand_1", "cand_2"]},
        execution_status="RUNNING",
        failure_state={"last_error": None},
    )
    repo.save(checkpoint)
    loaded = repo.load("exec_1")
    assert loaded is not None
    assert loaded.to_dict() == checkpoint.to_dict()
    raw = repo.get("exec_1")
    assert raw is not None
    assert raw["completed_nodes"] == ["n1", "n2"]
    assert raw["node_outputs"]["n1"]["artifact_id"] == "art_1"
    # overwrite with updated state
    checkpoint.execution_status = "SUCCEEDED"
    checkpoint.completed_nodes = ["n1", "n2"]
    repo.save(checkpoint)
    again = repo.load("exec_1")
    assert again is not None
    assert again.execution_status == "SUCCEEDED"
    assert repo.delete("exec_1") is True
    assert repo.load("exec_1") is None
    db.close()


def test_artifact_and_provenance_roundtrip() -> None:
    """Artifacts store metadata + provenance, not media bytes."""
    db = _migrated_db()
    repo = ArtifactRepository(db)
    provenance = {
        "story_id": "story_a",
        "story_version": 1,
        "asset_ids": ["asset_char"],
        "graph_node_id": "node_1",
        "execution_id": "exec_1",
        "generation_spec_hash": "spec_hash",
        "provider_id": "mock-primary",
        "model_id": "mock",
        "candidate_id": "cand_1",
        "quality_results": ["qr_1"],
        "repair_history": [],
        "inputs": {"reference": "art_0"},
        "created_at": "2026-01-01T00:00:00+00:00",
    }
    repo.save(
        "art_1",
        artifact_type="image",
        content_reference="file:///artifacts/art_1.png",
        fingerprint="fp_art_1",
        source_node="node_1",
        asset_id="asset_char",
        technical_metadata={"width": 1024, "height": 576},
        quality_state="SELECTED",
        provenance=provenance,
    )
    art = repo.get("art_1")
    assert art is not None
    assert art["artifact_type"] == "image"
    assert art["content_reference"] == "file:///artifacts/art_1.png"
    assert art["technical_metadata"] == {"width": 1024, "height": 576}
    assert art["quality_state"] == "SELECTED"
    assert repo.find_by_fingerprint("fp_art_1")["id"] == "art_1"  # type: ignore[index]
    prov = repo.get_provenance("art_1")
    assert prov is not None
    assert prov["provider_id"] == "mock-primary"
    assert prov["asset_ids"] == ["asset_char"]
    assert prov["inputs"] == {"reference": "art_0"}
    assert [a["id"] for a in repo.list_by_node("node_1")] == ["art_1"]
    assert [a["id"] for a in repo.list_by_asset("asset_char")] == ["art_1"]
    assert [a["id"] for a in repo.list_by_execution("exec_1")] == ["art_1"]
    db.close()


def test_decision_record_roundtrip() -> None:
    """Decision records preserve candidates, policy, and evidence."""
    db = _migrated_db()
    repo = DecisionRepository(db)
    repo.save(
        "dec_1",
        decision_type="selection",
        subject="node_shot_1",
        candidates=["cand_a", "cand_b"],
        policy={"weights": {"quality": 0.35}},
        selected="cand_a",
        reason="highest continuity",
        evidence={"scores": {"cand_a": 0.91, "cand_b": 0.72}},
        execution_id="exec_1",
    )
    record = repo.get("dec_1")
    assert record is not None
    assert record["decision_type"] == "selection"
    assert record["candidates"] == ["cand_a", "cand_b"]
    assert record["selected"] == "cand_a"
    assert record["policy"] == {"weights": {"quality": 0.35}}
    assert record["evidence"]["scores"]["cand_a"] == 0.91
    assert [d["id"] for d in repo.list_by_execution("exec_1")] == ["dec_1"]
    assert [d["id"] for d in repo.list_by_subject("node_shot_1")] == ["dec_1"]
    assert [d["id"] for d in repo.list_by_type("selection")] == ["dec_1"]
    db.close()


def test_quality_result_and_issues_roundtrip() -> None:
    """Quality results and issues persist with nested relationship."""
    db = _migrated_db()
    repo = QualityRepository(db)
    repo.save_result(
        "qr_1",
        subject_id="art_1",
        gate="WARN",
        scores={"continuity": 0.7, "technical": 0.95},
        evidence={"evaluator": "mock"},
        issues=[
            {
                "id": "issue_1",
                "issue_type": "CHARACTER_CONTINUITY",
                "severity": "MEDIUM",
                "node_id": "node_1",
                "asset_id": "asset_char",
                "message": "costume drift",
                "evidence": {"frame": 12},
                "suggested_scope": ["node_1", "node_2"],
            }
        ],
    )
    result = repo.get_result("qr_1")
    assert result is not None
    assert result["gate"] == "WARN"
    assert result["scores"] == {"continuity": 0.7, "technical": 0.95}
    issues = repo.list_issues_by_result("qr_1")
    assert len(issues) == 1
    assert issues[0]["issue_type"] == "CHARACTER_CONTINUITY"
    assert issues[0]["suggested_scope"] == ["node_1", "node_2"]
    assert [i["id"] for i in repo.list_issues_by_node("node_1")] == ["issue_1"]
    assert [i["id"] for i in repo.list_issues_by_asset("asset_char")] == ["issue_1"]

    repo.save_issue(
        "issue_2",
        issue_type="TECHNICAL_VALIDATION",
        severity="LOW",
        node_id="node_2",
        message="decode warning",
    )
    assert repo.get_issue("issue_2")["message"] == "decode warning"  # type: ignore[index]
    assert [r["id"] for r in repo.list_results_by_subject("art_1")] == ["qr_1"]
    db.close()


def test_repair_plan_roundtrip() -> None:
    """Repair plans persist invalidate/keep lists and actions."""
    db = _migrated_db()
    repo = RepairRepository(db)
    repo.save(
        "repair_1",
        kind="POST_GENERATION",
        issues=["issue_1"],
        invalidate_node_ids=["node_1"],
        keep_node_ids=["node_0"],
        actions=[{"node_id": "node_1", "action": "regenerate", "reason": "costume drift"}],
        rationale="local re-production only",
    )
    plan = repo.get("repair_1")
    assert plan is not None
    assert plan["kind"] == "POST_GENERATION"
    assert plan["issues"] == ["issue_1"]
    assert plan["invalidate_node_ids"] == ["node_1"]
    assert plan["keep_node_ids"] == ["node_0"]
    assert plan["actions"][0]["action"] == "regenerate"
    assert [p["id"] for p in repo.list_by_kind("POST_GENERATION")] == ["repair_1"]
    db.close()


def test_file_database_persists_across_connections(tmp_path: Path) -> None:
    """File-backed database keeps data after close/reopen."""
    path = tmp_path / "store" / "drama.db"
    db = Database(path)
    db.migrate()
    StoryRepository(db).save(
        "story_file",
        "持久化",
        1,
        {"title": "持久化"},
        fingerprint="fp_file",
    )
    db.close()

    reopened = Database(path)
    reopened.migrate()
    loaded = StoryRepository(reopened).get("story_file")
    assert loaded is not None
    assert loaded["title"] == "持久化"
    assert loaded["payload"]["title"] == "持久化"
    reopened.close()
