# SPDX-FileCopyrightText: 2026 zcbacxc
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Repository classes over the SQLite persistence schema."""

from __future__ import annotations

from typing import Any

from drama_forge.persistence.db import Database, dumps, loads, row_to_dict


class StoryRepository:
    """Persist and load compiled stories as JSON payloads."""

    def __init__(self, db: Database) -> None:
        """__init__.

        Args:
                    db: Database
        """
        self.db = db

    def save(
        self,
        story_id: str,
        title: str,
        version: int,
        payload: dict[str, Any],
        *,
        fingerprint: str = "",
        created_at: str = "",
        updated_at: str = "",
    ) -> None:
        """Insert or replace a story row.

        Args:
                    story_id: str
                    title: str
                    version: int
                    payload: dict[str, Any]
                    fingerprint: str (keyword-only)
                    created_at: str (keyword-only)
                    updated_at: str (keyword-only)

        Returns:
                    None
        """
        from drama_forge.domain.asset import utc_now_iso

        now = utc_now_iso()
        created = created_at or now
        updated = updated_at or created
        conn = self.db.connection
        with conn:
            conn.execute(
                """
                INSERT INTO stories (
                    id, title, version, fingerprint, payload,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    title = excluded.title,
                    version = excluded.version,
                    fingerprint = excluded.fingerprint,
                    payload = excluded.payload,
                    updated_at = excluded.updated_at
                """,
                (
                    story_id,
                    title,
                    int(version),
                    fingerprint,
                    dumps(payload),
                    created,
                    updated,
                ),
            )

    def get(self, story_id: str) -> dict[str, Any] | None:
        """Load a story by id, decoding the JSON payload.

        Args:
            story_id: Story identity.

        Returns:
            Story row dict with decoded ``payload``, or None.
        """
        row = self.db.connection.execute(
            "SELECT * FROM stories WHERE id = ?",
            (story_id,),
        ).fetchone()
        record = row_to_dict(row)
        if record is None:
            return None
        record["payload"] = loads(record.get("payload"), default={})
        return record

    def find_by_fingerprint(self, fingerprint: str) -> dict[str, Any] | None:
        """Find a story by content fingerprint.

        Args:
            fingerprint: Story content fingerprint.

        Returns:
            Decoded story row dict, or None.
        """
        row = self.db.connection.execute(
            "SELECT id FROM stories WHERE fingerprint = ? ORDER BY updated_at DESC LIMIT 1",
            (fingerprint,),
        ).fetchone()
        if row is None:
            return None
        return self.get(row["id"])

    def list_all(self) -> list[dict[str, Any]]:
        """List all stories with decoded payloads.

        Returns:
                    list[dict[str, Any]]
        """
        rows = self.db.connection.execute(
            "SELECT id FROM stories ORDER BY updated_at DESC"
        ).fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            record = self.get(row["id"])
            if record is not None:
                result.append(record)
        return result

    def delete(self, story_id: str) -> bool:
        """Delete a story by id.

        Args:
                    story_id: str

        Returns:
                    bool
        """
        conn = self.db.connection
        with conn:
            cur = conn.execute("DELETE FROM stories WHERE id = ?", (story_id,))
        return cur.rowcount > 0


class GraphRepository:
    """Persist production manifests and production graphs."""

    def __init__(self, db: Database) -> None:
        """__init__.

        Args:
                    db: Database
        """
        self.db = db

    def save_manifest(
        self,
        manifest_id: str,
        story_id: str,
        story_version: int,
        production_spec_id: str,
        graph_id: str,
        *,
        capability_policy: dict[str, Any] | None = None,
        provider_policy: dict[str, Any] | None = None,
        selection_policy: dict[str, Any] | None = None,
        quality_policy: dict[str, Any] | None = None,
        output_policy: dict[str, Any] | None = None,
        asset_versions: dict[str, int] | None = None,
        schema_version: str = "1.0",
        fingerprint: str = "",
        metadata: dict[str, Any] | None = None,
        payload: dict[str, Any] | None = None,
        created_at: str = "",
    ) -> None:
        """Insert or replace a production manifest row.

        Args:
                    manifest_id: str
                    story_id: str
                    story_version: int
                    production_spec_id: str
                    graph_id: str
                    capability_policy: dict[str, Any] | None (keyword-only)
                    provider_policy: dict[str, Any] | None (keyword-only)
                    selection_policy: dict[str, Any] | None (keyword-only)
                    quality_policy: dict[str, Any] | None (keyword-only)
                    output_policy: dict[str, Any] | None (keyword-only)
                    asset_versions: dict[str, int] | None (keyword-only)
                    schema_version: str (keyword-only)
                    fingerprint: str (keyword-only)
                    metadata: dict[str, Any] | None (keyword-only)
                    payload: dict[str, Any] | None (keyword-only)
                    created_at: str (keyword-only)

        Returns:
                    None
        """
        from drama_forge.domain.asset import utc_now_iso

        created = created_at or utc_now_iso()
        conn = self.db.connection
        with conn:
            conn.execute(
                """
                INSERT INTO production_manifests (
                    id, story_id, story_version, production_spec_id, graph_id,
                    capability_policy, provider_policy, selection_policy,
                    quality_policy, output_policy, asset_versions,
                    schema_version, fingerprint, metadata, payload, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    story_id = excluded.story_id,
                    story_version = excluded.story_version,
                    production_spec_id = excluded.production_spec_id,
                    graph_id = excluded.graph_id,
                    capability_policy = excluded.capability_policy,
                    provider_policy = excluded.provider_policy,
                    selection_policy = excluded.selection_policy,
                    quality_policy = excluded.quality_policy,
                    output_policy = excluded.output_policy,
                    asset_versions = excluded.asset_versions,
                    schema_version = excluded.schema_version,
                    fingerprint = excluded.fingerprint,
                    metadata = excluded.metadata,
                    payload = excluded.payload
                """,
                (
                    manifest_id,
                    story_id,
                    int(story_version),
                    production_spec_id,
                    graph_id,
                    dumps(capability_policy or {}),
                    dumps(provider_policy or {}),
                    dumps(selection_policy or {}),
                    dumps(quality_policy or {}),
                    dumps(output_policy or {}),
                    dumps(asset_versions or {}),
                    schema_version,
                    fingerprint,
                    dumps(metadata or {}),
                    dumps(payload or {}),
                    created,
                ),
            )

    def get_manifest(self, manifest_id: str) -> dict[str, Any] | None:
        """Load a production manifest by id with JSON fields decoded.

        Args:
                    manifest_id: str

        Returns:
                    dict[str, Any] | None
        """
        row = self.db.connection.execute(
            "SELECT * FROM production_manifests WHERE id = ?",
            (manifest_id,),
        ).fetchone()
        return self._decode_manifest(row)

    def find_manifest_by_fingerprint(self, fingerprint: str) -> dict[str, Any] | None:
        """Find a manifest by contract fingerprint.

        Args:
                    fingerprint: str

        Returns:
                    dict[str, Any] | None
        """
        row = self.db.connection.execute(
            "SELECT id FROM production_manifests WHERE fingerprint = ? LIMIT 1",
            (fingerprint,),
        ).fetchone()
        if row is None:
            return None
        return self.get_manifest(row["id"])

    def list_manifests_by_story(self, story_id: str) -> list[dict[str, Any]]:
        """List manifests bound to a story id.

        Args:
                    story_id: str

        Returns:
                    list[dict[str, Any]]
        """
        rows = self.db.connection.execute(
            "SELECT id FROM production_manifests WHERE story_id = ? ORDER BY created_at DESC",
            (story_id,),
        ).fetchall()
        return [m for row in rows if (m := self.get_manifest(row["id"])) is not None]

    def save_graph(
        self,
        graph_id: str,
        name: str,
        version: int,
        nodes: list[dict[str, Any]] | dict[str, Any],
        edges: list[dict[str, Any]],
        *,
        policy: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        fingerprint: str = "",
        created_at: str = "",
        updated_at: str = "",
    ) -> None:
        """Insert or replace a production graph row.

        Args:
                    graph_id: str
                    name: str
                    version: int
                    nodes: list[dict[str, Any]] | dict[str, Any]
                    edges: list[dict[str, Any]]
                    policy: dict[str, Any] | None (keyword-only)
                    metadata: dict[str, Any] | None (keyword-only)
                    fingerprint: str (keyword-only)
                    created_at: str (keyword-only)
                    updated_at: str (keyword-only)

        Returns:
                    None
        """
        from drama_forge.domain.asset import utc_now_iso

        now = utc_now_iso()
        created = created_at or now
        updated = updated_at or created
        conn = self.db.connection
        with conn:
            conn.execute(
                """
                INSERT INTO production_graphs (
                    id, name, version, nodes, edges, policy, metadata,
                    fingerprint, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    version = excluded.version,
                    nodes = excluded.nodes,
                    edges = excluded.edges,
                    policy = excluded.policy,
                    metadata = excluded.metadata,
                    fingerprint = excluded.fingerprint,
                    updated_at = excluded.updated_at
                """,
                (
                    graph_id,
                    name,
                    int(version),
                    dumps(nodes),
                    dumps(edges),
                    dumps(policy or {}),
                    dumps(metadata or {}),
                    fingerprint,
                    created,
                    updated,
                ),
            )

    def get_graph(self, graph_id: str) -> dict[str, Any] | None:
        """Load a production graph with nodes/edges decoded.

        Args:
                    graph_id: str

        Returns:
                    dict[str, Any] | None
        """
        row = self.db.connection.execute(
            "SELECT * FROM production_graphs WHERE id = ?",
            (graph_id,),
        ).fetchone()
        record = row_to_dict(row)
        if record is None:
            return None
        record["nodes"] = loads(record.get("nodes"), default=[])
        record["edges"] = loads(record.get("edges"), default=[])
        record["policy"] = loads(record.get("policy"), default={})
        record["metadata"] = loads(record.get("metadata"), default={})
        return record

    def find_graph_by_fingerprint(self, fingerprint: str) -> dict[str, Any] | None:
        """Find a graph by structural fingerprint.

        Args:
                    fingerprint: str

        Returns:
                    dict[str, Any] | None
        """
        row = self.db.connection.execute(
            "SELECT id FROM production_graphs WHERE fingerprint = ? LIMIT 1",
            (fingerprint,),
        ).fetchone()
        if row is None:
            return None
        return self.get_graph(row["id"])

    @staticmethod
    def _decode_manifest(row: Any) -> dict[str, Any] | None:
        record = row_to_dict(row)
        if record is None:
            return None
        for key in (
            "capability_policy",
            "provider_policy",
            "selection_policy",
            "quality_policy",
            "output_policy",
            "asset_versions",
            "metadata",
            "payload",
        ):
            default: Any = [] if key == "asset_versions" else {}
            record[key] = loads(record.get(key), default=default)
        return record


class ExecutionRepository:
    """Persist execution runs and fingerprint lookups."""

    def __init__(self, db: Database) -> None:
        """__init__.

        Args:
                    db: Database
        """
        self.db = db

    def save(
        self,
        execution_id: str,
        graph_id: str,
        status: str,
        *,
        graph_fingerprint: str = "",
        input_fingerprint: str = "",
        config: dict[str, Any] | None = None,
        result_summary: dict[str, Any] | None = None,
        created_at: str = "",
        updated_at: str = "",
    ) -> None:
        """Insert or replace an execution row.

        Args:
                    execution_id: str
                    graph_id: str
                    status: str
                    graph_fingerprint: str (keyword-only)
                    input_fingerprint: str (keyword-only)
                    config: dict[str, Any] | None (keyword-only)
                    result_summary: dict[str, Any] | None (keyword-only)
                    created_at: str (keyword-only)
                    updated_at: str (keyword-only)

        Returns:
                    None
        """
        from drama_forge.domain.asset import utc_now_iso

        now = utc_now_iso()
        created = created_at or now
        updated = updated_at or created
        conn = self.db.connection
        with conn:
            conn.execute(
                """
                INSERT INTO executions (
                    id, graph_id, status, graph_fingerprint, input_fingerprint,
                    config, result_summary, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    graph_id = excluded.graph_id,
                    status = excluded.status,
                    graph_fingerprint = excluded.graph_fingerprint,
                    input_fingerprint = excluded.input_fingerprint,
                    config = excluded.config,
                    result_summary = excluded.result_summary,
                    updated_at = excluded.updated_at
                """,
                (
                    execution_id,
                    graph_id,
                    status,
                    graph_fingerprint,
                    input_fingerprint,
                    dumps(config or {}),
                    dumps(result_summary or {}),
                    created,
                    updated,
                ),
            )

    def get(self, execution_id: str) -> dict[str, Any] | None:
        """Load an execution by id with JSON fields decoded.

        Args:
                    execution_id: str

        Returns:
                    dict[str, Any] | None
        """
        row = self.db.connection.execute(
            "SELECT * FROM executions WHERE id = ?",
            (execution_id,),
        ).fetchone()
        return self._decode(row)

    def update_status(
        self,
        execution_id: str,
        status: str,
        *,
        result_summary: dict[str, Any] | None = None,
        updated_at: str = "",
    ) -> bool:
        """Update execution status (and optional summary).

        Args:
            execution_id: Execution identity.
            status: New ExecutionStatus value.
            result_summary: Optional summary to store.
            updated_at: ISO timestamp; defaults to now.

        Returns:
            True if the row existed and was updated.
        """
        from drama_forge.domain.asset import utc_now_iso

        updated = updated_at or utc_now_iso()
        conn = self.db.connection
        with conn:
            if result_summary is None:
                cur = conn.execute(
                    "UPDATE executions SET status = ?, updated_at = ? WHERE id = ?",
                    (status, updated, execution_id),
                )
            else:
                cur = conn.execute(
                    """
                    UPDATE executions
                    SET status = ?, result_summary = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (status, dumps(result_summary), updated, execution_id),
                )
        return cur.rowcount > 0

    def list_by_graph(self, graph_id: str) -> list[dict[str, Any]]:
        """List executions for a production graph.

        Args:
                    graph_id: str

        Returns:
                    list[dict[str, Any]]
        """
        rows = self.db.connection.execute(
            "SELECT * FROM executions WHERE graph_id = ? ORDER BY created_at DESC",
            (graph_id,),
        ).fetchall()
        return [rec for row in rows if (rec := self._decode(row)) is not None]

    def list_by_status(self, status: str) -> list[dict[str, Any]]:
        """List executions with the given status.

        Args:
                    status: str

        Returns:
                    list[dict[str, Any]]
        """
        rows = self.db.connection.execute(
            "SELECT * FROM executions WHERE status = ? ORDER BY created_at DESC",
            (status,),
        ).fetchall()
        return [rec for row in rows if (rec := self._decode(row)) is not None]

    def find_by_graph_fingerprint(self, fingerprint: str) -> list[dict[str, Any]]:
        """List executions sharing a graph fingerprint.

        Args:
                    fingerprint: str

        Returns:
                    list[dict[str, Any]]
        """
        rows = self.db.connection.execute(
            """
            SELECT * FROM executions
            WHERE graph_fingerprint = ?
            ORDER BY created_at DESC
            """,
            (fingerprint,),
        ).fetchall()
        return [rec for row in rows if (rec := self._decode(row)) is not None]

    def find_by_input_fingerprint(self, fingerprint: str) -> list[dict[str, Any]]:
        """List executions sharing an input fingerprint.

        Args:
                    fingerprint: str

        Returns:
                    list[dict[str, Any]]
        """
        rows = self.db.connection.execute(
            """
            SELECT * FROM executions
            WHERE input_fingerprint = ?
            ORDER BY created_at DESC
            """,
            (fingerprint,),
        ).fetchall()
        return [rec for row in rows if (rec := self._decode(row)) is not None]

    @staticmethod
    def _decode(row: Any) -> dict[str, Any] | None:
        record = row_to_dict(row)
        if record is None:
            return None
        record["config"] = loads(record.get("config"), default={})
        record["result_summary"] = loads(record.get("result_summary"), default={})
        return record


class CheckpointRepository:
    """Persist interrupt/resume checkpoints for executions."""

    def __init__(self, db: Database) -> None:
        """__init__.

        Args:
                    db: Database
        """
        self.db = db

    def save(self, checkpoint: Any) -> None:
        """Persist a checkpoint (Checkpoint dataclass or dict).

        Args:
                    checkpoint: Any

        Returns:
                    None
        """
        from drama_forge.runtime.checkpoint import Checkpoint

        data = checkpoint.to_dict() if isinstance(checkpoint, Checkpoint) else dict(checkpoint)
        from drama_forge.domain.asset import utc_now_iso

        updated = utc_now_iso()
        conn = self.db.connection
        with conn:
            conn.execute(
                """
                INSERT INTO checkpoints (
                    execution_id, graph_id, graph_fingerprint, input_fingerprint,
                    completed_nodes, node_outputs, node_status, artifact_refs,
                    candidate_refs, execution_status, failure_state, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(execution_id) DO UPDATE SET
                    graph_id = excluded.graph_id,
                    graph_fingerprint = excluded.graph_fingerprint,
                    input_fingerprint = excluded.input_fingerprint,
                    completed_nodes = excluded.completed_nodes,
                    node_outputs = excluded.node_outputs,
                    node_status = excluded.node_status,
                    artifact_refs = excluded.artifact_refs,
                    candidate_refs = excluded.candidate_refs,
                    execution_status = excluded.execution_status,
                    failure_state = excluded.failure_state,
                    updated_at = excluded.updated_at
                """,
                (
                    data.get("execution_id", ""),
                    data.get("graph_id", ""),
                    data.get("graph_fingerprint", ""),
                    data.get("input_fingerprint", ""),
                    dumps(data.get("completed_nodes") or []),
                    dumps(data.get("node_outputs") or {}),
                    dumps(data.get("node_status") or {}),
                    dumps(data.get("artifact_refs") or {}),
                    dumps(data.get("candidate_refs") or {}),
                    data.get("execution_status", "RUNNING"),
                    dumps(data.get("failure_state") or {}),
                    updated,
                ),
            )

    def load(self, execution_id: str) -> Any | None:
        """Load a checkpoint as a Checkpoint dataclass.

        Args:
            execution_id: Execution identity.

        Returns:
            Checkpoint instance, or None when absent.
        """
        from drama_forge.runtime.checkpoint import Checkpoint

        record = self.get(execution_id)
        if record is None:
            return None
        record.pop("updated_at", None)
        return Checkpoint.from_dict(record)

    def get(self, execution_id: str) -> dict[str, Any] | None:
        """Load a raw checkpoint row dict with JSON fields decoded.

        Args:
            execution_id: Execution identity.

        Returns:
            Decoded checkpoint dict, or None.
        """
        row = self.db.connection.execute(
            "SELECT * FROM checkpoints WHERE execution_id = ?",
            (execution_id,),
        ).fetchone()
        record = row_to_dict(row)
        if record is None:
            return None
        record["completed_nodes"] = loads(record.get("completed_nodes"), default=[])
        record["node_outputs"] = loads(record.get("node_outputs"), default={})
        record["node_status"] = loads(record.get("node_status"), default={})
        record["artifact_refs"] = loads(record.get("artifact_refs"), default={})
        record["candidate_refs"] = loads(record.get("candidate_refs"), default={})
        record["failure_state"] = loads(record.get("failure_state"), default={})
        return record

    def delete(self, execution_id: str) -> bool:
        """Delete a checkpoint by execution id.

        Args:
                    execution_id: str

        Returns:
                    bool
        """
        conn = self.db.connection
        with conn:
            cur = conn.execute(
                "DELETE FROM checkpoints WHERE execution_id = ?",
                (execution_id,),
            )
        return cur.rowcount > 0


class ArtifactRepository:
    """Persist artifact metadata and provenance (not media bytes)."""

    def __init__(self, db: Database) -> None:
        """__init__.

        Args:
                    db: Database
        """
        self.db = db

    def save(
        self,
        artifact_id: str,
        artifact_type: str,
        content_reference: str,
        *,
        fingerprint: str = "",
        source_node: str | None = None,
        asset_id: str | None = None,
        schema_version: str = "1.0",
        technical_metadata: dict[str, Any] | None = None,
        provider_metadata: dict[str, Any] | None = None,
        generation_metadata: dict[str, Any] | None = None,
        quality_state: str = "UNEVALUATED",
        provenance: dict[str, Any] | None = None,
        created_at: str = "",
    ) -> None:
        """Insert or replace artifact metadata and optional provenance.

        Args:
                    artifact_id: str
                    artifact_type: str
                    content_reference: str
                    fingerprint: str (keyword-only)
                    source_node: str | None (keyword-only)
                    asset_id: str | None (keyword-only)
                    schema_version: str (keyword-only)
                    technical_metadata: dict[str, Any] | None (keyword-only)
                    provider_metadata: dict[str, Any] | None (keyword-only)
                    generation_metadata: dict[str, Any] | None (keyword-only)
                    quality_state: str (keyword-only)
                    provenance: dict[str, Any] | None (keyword-only)
                    created_at: str (keyword-only)

        Returns:
                    None
        """
        from drama_forge.domain.asset import utc_now_iso

        created = created_at or utc_now_iso()
        conn = self.db.connection
        with conn:
            conn.execute(
                """
                INSERT INTO artifacts (
                    id, artifact_type, content_reference, source_node, asset_id,
                    schema_version, technical_metadata, provider_metadata,
                    generation_metadata, quality_state, fingerprint, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    artifact_type = excluded.artifact_type,
                    content_reference = excluded.content_reference,
                    source_node = excluded.source_node,
                    asset_id = excluded.asset_id,
                    schema_version = excluded.schema_version,
                    technical_metadata = excluded.technical_metadata,
                    provider_metadata = excluded.provider_metadata,
                    generation_metadata = excluded.generation_metadata,
                    quality_state = excluded.quality_state,
                    fingerprint = excluded.fingerprint
                """,
                (
                    artifact_id,
                    artifact_type,
                    content_reference,
                    source_node,
                    asset_id,
                    schema_version,
                    dumps(technical_metadata or {}),
                    dumps(provider_metadata or {}),
                    dumps(generation_metadata or {}),
                    quality_state,
                    fingerprint,
                    created,
                ),
            )
            if provenance is not None:
                self._save_provenance(conn, artifact_id, provenance, created)

    def _save_provenance(
        self,
        conn: Any,
        artifact_id: str,
        provenance: dict[str, Any],
        created_at: str,
    ) -> None:
        conn.execute(
            """
            INSERT INTO artifact_provenance (
                artifact_id, story_id, story_version, asset_ids,
                graph_node_id, execution_id, generation_spec_hash,
                provider_id, model_id, candidate_id,
                quality_results, repair_history, inputs, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(artifact_id) DO UPDATE SET
                story_id = excluded.story_id,
                story_version = excluded.story_version,
                asset_ids = excluded.asset_ids,
                graph_node_id = excluded.graph_node_id,
                execution_id = excluded.execution_id,
                generation_spec_hash = excluded.generation_spec_hash,
                provider_id = excluded.provider_id,
                model_id = excluded.model_id,
                candidate_id = excluded.candidate_id,
                quality_results = excluded.quality_results,
                repair_history = excluded.repair_history,
                inputs = excluded.inputs
            """,
            (
                artifact_id,
                provenance.get("story_id"),
                provenance.get("story_version"),
                dumps(provenance.get("asset_ids") or []),
                provenance.get("graph_node_id"),
                provenance.get("execution_id"),
                provenance.get("generation_spec_hash"),
                provenance.get("provider_id"),
                provenance.get("model_id"),
                provenance.get("candidate_id"),
                dumps(provenance.get("quality_results") or []),
                dumps(provenance.get("repair_history") or []),
                dumps(provenance.get("inputs") or {}),
                provenance.get("created_at") or created_at,
            ),
        )

    def get(self, artifact_id: str) -> dict[str, Any] | None:
        """Load artifact metadata with JSON fields decoded.

        Args:
                    artifact_id: str

        Returns:
                    dict[str, Any] | None
        """
        row = self.db.connection.execute(
            "SELECT * FROM artifacts WHERE id = ?",
            (artifact_id,),
        ).fetchone()
        return self._decode(row)

    def get_provenance(self, artifact_id: str) -> dict[str, Any] | None:
        """Load provenance trace for an artifact.

        Args:
                    artifact_id: str

        Returns:
                    dict[str, Any] | None
        """
        row = self.db.connection.execute(
            "SELECT * FROM artifact_provenance WHERE artifact_id = ?",
            (artifact_id,),
        ).fetchone()
        record = row_to_dict(row)
        if record is None:
            return None
        record["asset_ids"] = loads(record.get("asset_ids"), default=[])
        record["quality_results"] = loads(record.get("quality_results"), default=[])
        record["repair_history"] = loads(record.get("repair_history"), default=[])
        record["inputs"] = loads(record.get("inputs"), default={})
        return record

    def find_by_fingerprint(self, fingerprint: str) -> dict[str, Any] | None:
        """Find an artifact by production-condition fingerprint.

        Args:
                    fingerprint: str

        Returns:
                    dict[str, Any] | None
        """
        row = self.db.connection.execute(
            "SELECT id FROM artifacts WHERE fingerprint = ? LIMIT 1",
            (fingerprint,),
        ).fetchone()
        if row is None:
            return None
        return self.get(row["id"])

    def list_by_node(self, source_node: str) -> list[dict[str, Any]]:
        """List artifacts produced by a graph node.

        Args:
                    source_node: str

        Returns:
                    list[dict[str, Any]]
        """
        rows = self.db.connection.execute(
            "SELECT * FROM artifacts WHERE source_node = ? ORDER BY created_at",
            (source_node,),
        ).fetchall()
        return [rec for row in rows if (rec := self._decode(row)) is not None]

    def list_by_asset(self, asset_id: str) -> list[dict[str, Any]]:
        """List artifacts bound to a semantic asset.

        Args:
                    asset_id: str

        Returns:
                    list[dict[str, Any]]
        """
        rows = self.db.connection.execute(
            "SELECT * FROM artifacts WHERE asset_id = ? ORDER BY created_at",
            (asset_id,),
        ).fetchall()
        return [rec for row in rows if (rec := self._decode(row)) is not None]

    def list_by_execution(self, execution_id: str) -> list[dict[str, Any]]:
        """List artifacts whose provenance points at an execution.

        Args:
                    execution_id: str

        Returns:
                    list[dict[str, Any]]
        """
        rows = self.db.connection.execute(
            """
            SELECT a.* FROM artifacts a
            JOIN artifact_provenance p ON p.artifact_id = a.id
            WHERE p.execution_id = ?
            ORDER BY a.created_at
            """,
            (execution_id,),
        ).fetchall()
        return [rec for row in rows if (rec := self._decode(row)) is not None]

    @staticmethod
    def _decode(row: Any) -> dict[str, Any] | None:
        record = row_to_dict(row)
        if record is None:
            return None
        record["technical_metadata"] = loads(record.get("technical_metadata"), default={})
        record["provider_metadata"] = loads(record.get("provider_metadata"), default={})
        record["generation_metadata"] = loads(record.get("generation_metadata"), default={})
        return record


class DecisionRepository:
    """Persist decision records (why a choice was made)."""

    def __init__(self, db: Database) -> None:
        """__init__.

        Args:
                    db: Database
        """
        self.db = db

    def save(
        self,
        decision_id: str,
        decision_type: str,
        subject: str,
        *,
        candidates: list[str] | None = None,
        policy: dict[str, Any] | None = None,
        selected: str | None = None,
        reason: str = "",
        evidence: dict[str, Any] | None = None,
        execution_id: str | None = None,
        created_at: str = "",
    ) -> None:
        """Insert or replace a decision record.

        Args:
                    decision_id: str
                    decision_type: str
                    subject: str
                    candidates: list[str] | None (keyword-only)
                    policy: dict[str, Any] | None (keyword-only)
                    selected: str | None (keyword-only)
                    reason: str (keyword-only)
                    evidence: dict[str, Any] | None (keyword-only)
                    execution_id: str | None (keyword-only)
                    created_at: str (keyword-only)

        Returns:
                    None
        """
        from drama_forge.domain.asset import utc_now_iso

        created = created_at or utc_now_iso()
        conn = self.db.connection
        with conn:
            conn.execute(
                """
                INSERT INTO decision_records (
                    id, decision_type, subject, candidates, policy,
                    selected, reason, evidence, execution_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    decision_type = excluded.decision_type,
                    subject = excluded.subject,
                    candidates = excluded.candidates,
                    policy = excluded.policy,
                    selected = excluded.selected,
                    reason = excluded.reason,
                    evidence = excluded.evidence,
                    execution_id = excluded.execution_id
                """,
                (
                    decision_id,
                    decision_type,
                    subject,
                    dumps(candidates or []),
                    dumps(policy or {}),
                    selected,
                    reason,
                    dumps(evidence or {}),
                    execution_id,
                    created,
                ),
            )

    def get(self, decision_id: str) -> dict[str, Any] | None:
        """Load a decision record with JSON fields decoded.

        Args:
                    decision_id: str

        Returns:
                    dict[str, Any] | None
        """
        row = self.db.connection.execute(
            "SELECT * FROM decision_records WHERE id = ?",
            (decision_id,),
        ).fetchone()
        return self._decode(row)

    def list_by_execution(self, execution_id: str) -> list[dict[str, Any]]:
        """List decisions recorded during an execution.

        Args:
                    execution_id: str

        Returns:
                    list[dict[str, Any]]
        """
        rows = self.db.connection.execute(
            "SELECT * FROM decision_records WHERE execution_id = ? ORDER BY created_at",
            (execution_id,),
        ).fetchall()
        return [rec for row in rows if (rec := self._decode(row)) is not None]

    def list_by_subject(self, subject: str) -> list[dict[str, Any]]:
        """List decisions about a given subject.

        Args:
                    subject: str

        Returns:
                    list[dict[str, Any]]
        """
        rows = self.db.connection.execute(
            "SELECT * FROM decision_records WHERE subject = ? ORDER BY created_at",
            (subject,),
        ).fetchall()
        return [rec for row in rows if (rec := self._decode(row)) is not None]

    def list_by_type(self, decision_type: str) -> list[dict[str, Any]]:
        """List decisions of a given type.

        Args:
                    decision_type: str

        Returns:
                    list[dict[str, Any]]
        """
        rows = self.db.connection.execute(
            "SELECT * FROM decision_records WHERE decision_type = ? ORDER BY created_at",
            (decision_type,),
        ).fetchall()
        return [rec for row in rows if (rec := self._decode(row)) is not None]

    @staticmethod
    def _decode(row: Any) -> dict[str, Any] | None:
        record = row_to_dict(row)
        if record is None:
            return None
        record["candidates"] = loads(record.get("candidates"), default=[])
        record["policy"] = loads(record.get("policy"), default={})
        record["evidence"] = loads(record.get("evidence"), default={})
        return record


class QualityRepository:
    """Persist quality results and structured issues."""

    def __init__(self, db: Database) -> None:
        """__init__.

        Args:
                    db: Database
        """
        self.db = db

    def save_result(
        self,
        result_id: str,
        subject_id: str,
        gate: str,
        *,
        scores: dict[str, float] | None = None,
        evidence: dict[str, Any] | None = None,
        issues: list[dict[str, Any]] | None = None,
        created_at: str = "",
    ) -> None:
        """Insert or replace a quality result and optional nested issues.

        Args:
                    result_id: str
                    subject_id: str
                    gate: str
                    scores: dict[str, float] | None (keyword-only)
                    evidence: dict[str, Any] | None (keyword-only)
                    issues: list[dict[str, Any]] | None (keyword-only)
                    created_at: str (keyword-only)

        Returns:
                    None
        """
        from drama_forge.domain.asset import utc_now_iso

        created = created_at or utc_now_iso()
        conn = self.db.connection
        with conn:
            conn.execute(
                """
                INSERT INTO quality_results (
                    id, subject_id, gate, scores, evidence, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    subject_id = excluded.subject_id,
                    gate = excluded.gate,
                    scores = excluded.scores,
                    evidence = excluded.evidence
                """,
                (
                    result_id,
                    subject_id,
                    gate,
                    dumps(scores or {}),
                    dumps(evidence or {}),
                    created,
                ),
            )
            if issues:
                for issue in issues:
                    self._save_issue_row(
                        conn,
                        issue_id=issue.get("id", ""),
                        issue_type=issue.get("issue_type", ""),
                        severity=issue.get("severity", ""),
                        quality_result_id=result_id,
                        node_id=issue.get("node_id"),
                        asset_id=issue.get("asset_id"),
                        message=issue.get("message", ""),
                        evidence=issue.get("evidence") or {},
                        suggested_scope=issue.get("suggested_scope") or [],
                        created_at=issue.get("created_at") or created,
                    )

    def save_issue(
        self,
        issue_id: str,
        issue_type: str,
        severity: str,
        *,
        quality_result_id: str | None = None,
        node_id: str | None = None,
        asset_id: str | None = None,
        message: str = "",
        evidence: dict[str, Any] | None = None,
        suggested_scope: list[str] | None = None,
        created_at: str = "",
    ) -> None:
        """Insert or replace a standalone quality issue.

        Args:
                    issue_id: str
                    issue_type: str
                    severity: str
                    quality_result_id: str | None (keyword-only)
                    node_id: str | None (keyword-only)
                    asset_id: str | None (keyword-only)
                    message: str (keyword-only)
                    evidence: dict[str, Any] | None (keyword-only)
                    suggested_scope: list[str] | None (keyword-only)
                    created_at: str (keyword-only)

        Returns:
                    None
        """
        from drama_forge.domain.asset import utc_now_iso

        created = created_at or utc_now_iso()
        conn = self.db.connection
        with conn:
            self._save_issue_row(
                conn,
                issue_id=issue_id,
                issue_type=issue_type,
                severity=severity,
                quality_result_id=quality_result_id,
                node_id=node_id,
                asset_id=asset_id,
                message=message,
                evidence=evidence or {},
                suggested_scope=suggested_scope or [],
                created_at=created,
            )

    def _save_issue_row(
        self,
        conn: Any,
        *,
        issue_id: str,
        issue_type: str,
        severity: str,
        quality_result_id: str | None,
        node_id: str | None,
        asset_id: str | None,
        message: str,
        evidence: dict[str, Any],
        suggested_scope: list[str],
        created_at: str,
    ) -> None:
        conn.execute(
            """
            INSERT INTO quality_issues (
                id, quality_result_id, issue_type, severity, node_id, asset_id,
                message, evidence, suggested_scope, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                quality_result_id = excluded.quality_result_id,
                issue_type = excluded.issue_type,
                severity = excluded.severity,
                node_id = excluded.node_id,
                asset_id = excluded.asset_id,
                message = excluded.message,
                evidence = excluded.evidence,
                suggested_scope = excluded.suggested_scope
            """,
            (
                issue_id,
                quality_result_id,
                issue_type,
                severity,
                node_id,
                asset_id,
                message,
                dumps(evidence),
                dumps(suggested_scope),
                created_at,
            ),
        )

    def get_result(self, result_id: str) -> dict[str, Any] | None:
        """Load a quality result with JSON fields decoded.

        Args:
                    result_id: str

        Returns:
                    dict[str, Any] | None
        """
        row = self.db.connection.execute(
            "SELECT * FROM quality_results WHERE id = ?",
            (result_id,),
        ).fetchone()
        record = row_to_dict(row)
        if record is None:
            return None
        record["scores"] = loads(record.get("scores"), default={})
        record["evidence"] = loads(record.get("evidence"), default={})
        return record

    def list_results_by_subject(self, subject_id: str) -> list[dict[str, Any]]:
        """List quality results for a subject.

        Args:
                    subject_id: str

        Returns:
                    list[dict[str, Any]]
        """
        rows = self.db.connection.execute(
            "SELECT * FROM quality_results WHERE subject_id = ? ORDER BY created_at",
            (subject_id,),
        ).fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            record = row_to_dict(row)
            if record is None:
                continue
            record["scores"] = loads(record.get("scores"), default={})
            record["evidence"] = loads(record.get("evidence"), default={})
            result.append(record)
        return result

    def get_issue(self, issue_id: str) -> dict[str, Any] | None:
        """Load a quality issue with JSON fields decoded.

        Args:
                    issue_id: str

        Returns:
                    dict[str, Any] | None
        """
        row = self.db.connection.execute(
            "SELECT * FROM quality_issues WHERE id = ?",
            (issue_id,),
        ).fetchone()
        return self._decode_issue(row)

    def list_issues_by_result(self, result_id: str) -> list[dict[str, Any]]:
        """List issues attached to a quality result.

        Args:
                    result_id: str

        Returns:
                    list[dict[str, Any]]
        """
        rows = self.db.connection.execute(
            "SELECT * FROM quality_issues WHERE quality_result_id = ? ORDER BY created_at",
            (result_id,),
        ).fetchall()
        return [rec for row in rows if (rec := self._decode_issue(row)) is not None]

    def list_issues_by_node(self, node_id: str) -> list[dict[str, Any]]:
        """List issues targeting a production node.

        Args:
                    node_id: str

        Returns:
                    list[dict[str, Any]]
        """
        rows = self.db.connection.execute(
            "SELECT * FROM quality_issues WHERE node_id = ? ORDER BY created_at",
            (node_id,),
        ).fetchall()
        return [rec for row in rows if (rec := self._decode_issue(row)) is not None]

    def list_issues_by_asset(self, asset_id: str) -> list[dict[str, Any]]:
        """List issues targeting an asset.

        Args:
                    asset_id: str

        Returns:
                    list[dict[str, Any]]
        """
        rows = self.db.connection.execute(
            "SELECT * FROM quality_issues WHERE asset_id = ? ORDER BY created_at",
            (asset_id,),
        ).fetchall()
        return [rec for row in rows if (rec := self._decode_issue(row)) is not None]

    @staticmethod
    def _decode_issue(row: Any) -> dict[str, Any] | None:
        record = row_to_dict(row)
        if record is None:
            return None
        record["evidence"] = loads(record.get("evidence"), default={})
        record["suggested_scope"] = loads(record.get("suggested_scope"), default=[])
        return record


class RepairRepository:
    """Persist repair plans for local re-production."""

    def __init__(self, db: Database) -> None:
        """__init__.

        Args:
                    db: Database
        """
        self.db = db

    def save(
        self,
        plan_id: str,
        kind: str,
        *,
        issues: list[str] | None = None,
        invalidate_node_ids: list[str] | None = None,
        keep_node_ids: list[str] | None = None,
        actions: list[dict[str, Any]] | None = None,
        rationale: str = "",
        created_at: str = "",
    ) -> None:
        """Insert or replace a repair plan.

        Args:
                    plan_id: str
                    kind: str
                    issues: list[str] | None (keyword-only)
                    invalidate_node_ids: list[str] | None (keyword-only)
                    keep_node_ids: list[str] | None (keyword-only)
                    actions: list[dict[str, Any]] | None (keyword-only)
                    rationale: str (keyword-only)
                    created_at: str (keyword-only)

        Returns:
                    None
        """
        from drama_forge.domain.asset import utc_now_iso

        created = created_at or utc_now_iso()
        conn = self.db.connection
        with conn:
            conn.execute(
                """
                INSERT INTO repair_plans (
                    id, kind, issues, invalidate_node_ids, keep_node_ids,
                    actions, rationale, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    kind = excluded.kind,
                    issues = excluded.issues,
                    invalidate_node_ids = excluded.invalidate_node_ids,
                    keep_node_ids = excluded.keep_node_ids,
                    actions = excluded.actions,
                    rationale = excluded.rationale
                """,
                (
                    plan_id,
                    kind,
                    dumps(issues or []),
                    dumps(invalidate_node_ids or []),
                    dumps(keep_node_ids or []),
                    dumps(actions or []),
                    rationale,
                    created,
                ),
            )

    def get(self, plan_id: str) -> dict[str, Any] | None:
        """Load a repair plan with JSON fields decoded.

        Args:
                    plan_id: str

        Returns:
                    dict[str, Any] | None
        """
        row = self.db.connection.execute(
            "SELECT * FROM repair_plans WHERE id = ?",
            (plan_id,),
        ).fetchone()
        record = row_to_dict(row)
        if record is None:
            return None
        record["issues"] = loads(record.get("issues"), default=[])
        record["invalidate_node_ids"] = loads(record.get("invalidate_node_ids"), default=[])
        record["keep_node_ids"] = loads(record.get("keep_node_ids"), default=[])
        record["actions"] = loads(record.get("actions"), default=[])
        return record

    def list_by_kind(self, kind: str) -> list[dict[str, Any]]:
        """List repair plans of a given kind.

        Args:
                    kind: str

        Returns:
                    list[dict[str, Any]]
        """
        rows = self.db.connection.execute(
            "SELECT * FROM repair_plans WHERE kind = ? ORDER BY created_at DESC",
            (kind,),
        ).fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            record = row_to_dict(row)
            if record is None:
                continue
            record["issues"] = loads(record.get("issues"), default=[])
            record["invalidate_node_ids"] = loads(record.get("invalidate_node_ids"), default=[])
            record["keep_node_ids"] = loads(record.get("keep_node_ids"), default=[])
            record["actions"] = loads(record.get("actions"), default=[])
            result.append(record)
        return result


class KnowledgeRepository:
    """Persist Production Knowledge bundles."""

    def __init__(self, db: Database) -> None:
        """__init__.

        Args:
                    db: Database
        """
        self.db = db

    def save(self, knowledge: Any) -> None:
        """Insert or replace a knowledge bundle.

        Args:
                    knowledge: Any

        Returns:
                    None
        """
        from drama_forge.domain.asset import utc_now_iso

        now = utc_now_iso()
        payload = knowledge.to_dict()
        self.db.connection.execute(
            """
            INSERT INTO production_knowledge (
                id, story_id, version, fingerprint, payload, source_refs,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                story_id = excluded.story_id,
                version = excluded.version,
                fingerprint = excluded.fingerprint,
                payload = excluded.payload,
                source_refs = excluded.source_refs,
                updated_at = excluded.updated_at
            """,
            (
                knowledge.id,
                knowledge.story_id,
                knowledge.version,
                knowledge.fingerprint,
                dumps(payload),
                dumps(list(knowledge.source_refs)),
                now,
                now,
            ),
        )
        self.db.connection.commit()

    def get(self, knowledge_id: str) -> dict[str, Any] | None:
        """Load one knowledge payload dict.

        Args:
                    knowledge_id: str

        Returns:
                    dict[str, Any] | None
        """
        row = self.db.connection.execute(
            "SELECT * FROM production_knowledge WHERE id = ?",
            (knowledge_id,),
        ).fetchone()
        record = row_to_dict(row)
        if record is None:
            return None
        record["payload"] = loads(record.get("payload"), default={})
        record["source_refs"] = loads(record.get("source_refs"), default=[])
        return record

    def latest_for_story(self, story_id: str) -> dict[str, Any] | None:
        """Load the highest-version knowledge for a story.

        Args:
                    story_id: str

        Returns:
                    dict[str, Any] | None
        """
        row = self.db.connection.execute(
            """
            SELECT * FROM production_knowledge
            WHERE story_id = ?
            ORDER BY version DESC, updated_at DESC
            LIMIT 1
            """,
            (story_id,),
        ).fetchone()
        record = row_to_dict(row)
        if record is None:
            return None
        record["payload"] = loads(record.get("payload"), default={})
        record["source_refs"] = loads(record.get("source_refs"), default=[])
        return record


class CandidateRepository:
    """Persist shot candidates produced during an execution."""

    def __init__(self, db: Database) -> None:
        """__init__.

        Args:
                    db: Database
        """
        self.db = db

    def save(
        self,
        candidate_id: str,
        node_id: str,
        *,
        artifact_id: str = "",
        selected: bool = False,
        score: float = 0.0,
        quality_state: str = "UNEVALUATED",
        execution_id: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        """Insert or replace a candidate row.

        Args:
                    candidate_id: str
                    node_id: str
                    artifact_id: str (keyword-only)
                    selected: bool (keyword-only)
                    score: float (keyword-only)
                    quality_state: str (keyword-only)
                    execution_id: str | None (keyword-only)
                    payload: dict[str, Any] | None (keyword-only)

        Returns:
                    None
        """
        from drama_forge.domain.asset import utc_now_iso

        self.db.connection.execute(
            """
            INSERT INTO candidates (
                id, node_id, artifact_id, selected, score, quality_state,
                execution_id, payload, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                node_id = excluded.node_id,
                artifact_id = excluded.artifact_id,
                selected = excluded.selected,
                score = excluded.score,
                quality_state = excluded.quality_state,
                execution_id = excluded.execution_id,
                payload = excluded.payload
            """,
            (
                candidate_id,
                node_id,
                artifact_id,
                1 if selected else 0,
                score,
                quality_state,
                execution_id,
                dumps(payload or {}),
                utc_now_iso(),
            ),
        )
        self.db.connection.commit()

    def list_by_node(self, node_id: str) -> list[dict[str, Any]]:
        """List candidates for a production node.

        Args:
                    node_id: str

        Returns:
                    list[dict[str, Any]]
        """
        rows = self.db.connection.execute(
            "SELECT * FROM candidates WHERE node_id = ? ORDER BY created_at",
            (node_id,),
        ).fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            record = row_to_dict(row)
            if record is None:
                continue
            record["selected"] = bool(record.get("selected"))
            record["payload"] = loads(record.get("payload"), default={})
            result.append(record)
        return result


class EventRepository:
    """Persist structured execution events."""

    def __init__(self, db: Database) -> None:
        """__init__.

        Args:
                    db: Database
        """
        self.db = db

    def append(
        self,
        execution_id: str,
        event_type: str,
        subject: str = "",
        payload: dict[str, Any] | None = None,
        created_at: str = "",
    ) -> None:
        """Append one execution event.

        Args:
                    execution_id: str
                    event_type: str
                    subject: default ''
                    payload: default None
                    created_at: default ''

        Returns:
                    None
        """
        from drama_forge.domain.asset import utc_now_iso

        self.db.connection.execute(
            """
            INSERT INTO execution_events (
                execution_id, event_type, subject, payload, created_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                execution_id,
                event_type,
                subject,
                dumps(payload or {}),
                created_at or utc_now_iso(),
            ),
        )
        self.db.connection.commit()

    def list_by_execution(self, execution_id: str) -> list[dict[str, Any]]:
        """List events for one execution in order.

        Args:
                    execution_id: str

        Returns:
                    list[dict[str, Any]]
        """
        rows = self.db.connection.execute(
            """
            SELECT * FROM execution_events
            WHERE execution_id = ?
            ORDER BY id
            """,
            (execution_id,),
        ).fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            record = row_to_dict(row)
            if record is None:
                continue
            record["payload"] = loads(record.get("payload"), default={})
            result.append(record)
        return result
