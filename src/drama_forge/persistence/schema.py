# SPDX-FileCopyrightText: 2026 zcbacxc
# SPDX-License-Identifier: AGPL-3.0-or-later
"""SQLite DDL for Drama Forge Core Engine persistence.

Schema version is tracked via ``PRAGMA user_version``. Column intent is
documented with SQL comments so the schema stays readable without external
docs.
"""

from __future__ import annotations

# Target schema version applied by Database.migrate().
SCHEMA_VERSION = 2

# Each entry is (version, list_of_sql_statements). Applied in order until
# PRAGMA user_version reaches SCHEMA_VERSION.
MIGRATIONS: list[tuple[int, list[str]]] = [
    (
        1,
        [
            """
            CREATE TABLE IF NOT EXISTS stories (
                id TEXT PRIMARY KEY,
                -- Human-readable story title.
                title TEXT NOT NULL,
                -- Monotonic story content version.
                version INTEGER NOT NULL DEFAULT 1,
                -- Content fingerprint for reuse / cache checks.
                fingerprint TEXT NOT NULL DEFAULT '',
                -- Full story object serialized as a JSON blob.
                payload TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_stories_fingerprint
                ON stories (fingerprint)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_stories_title
                ON stories (title)
            """,
            """
            CREATE TABLE IF NOT EXISTS production_manifests (
                id TEXT PRIMARY KEY,
                -- Story identity this manifest produces.
                story_id TEXT NOT NULL,
                story_version INTEGER NOT NULL DEFAULT 1,
                -- ProductionSpec identity used to plan the run.
                production_spec_id TEXT NOT NULL,
                -- ProductionGraph identity bound to this contract.
                graph_id TEXT NOT NULL,
                capability_policy TEXT NOT NULL DEFAULT '{}',
                provider_policy TEXT NOT NULL DEFAULT '{}',
                selection_policy TEXT NOT NULL DEFAULT '{}',
                quality_policy TEXT NOT NULL DEFAULT '{}',
                output_policy TEXT NOT NULL DEFAULT '{}',
                -- JSON map of asset_id -> expected version.
                asset_versions TEXT NOT NULL DEFAULT '{}',
                schema_version TEXT NOT NULL DEFAULT '1.0',
                -- Contract fingerprint of policies + story/graph bindings.
                fingerprint TEXT NOT NULL DEFAULT '',
                metadata TEXT NOT NULL DEFAULT '{}',
                -- Full optional manifest payload for round-trip fidelity.
                payload TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL
            )
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_manifests_story_id
                ON production_manifests (story_id)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_manifests_graph_id
                ON production_manifests (graph_id)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_manifests_fingerprint
                ON production_manifests (fingerprint)
            """,
            """
            CREATE TABLE IF NOT EXISTS production_graphs (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                version INTEGER NOT NULL DEFAULT 1,
                -- JSON list/object of graph nodes (including fingerprints).
                nodes TEXT NOT NULL DEFAULT '[]',
                -- JSON list of dependency edges.
                edges TEXT NOT NULL DEFAULT '[]',
                policy TEXT NOT NULL DEFAULT '{}',
                metadata TEXT NOT NULL DEFAULT '{}',
                -- Structural fingerprint of nodes + edges.
                fingerprint TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_graphs_fingerprint
                ON production_graphs (fingerprint)
            """,
            """
            CREATE TABLE IF NOT EXISTS executions (
                id TEXT PRIMARY KEY,
                -- Production graph executed in this run.
                graph_id TEXT NOT NULL,
                -- ExecutionStatus value (PENDING/RUNNING/SUCCEEDED/...).
                status TEXT NOT NULL DEFAULT 'PENDING',
                -- Fingerprint of the production graph definition.
                graph_fingerprint TEXT NOT NULL DEFAULT '',
                -- Fingerprint of run inputs (story/spec/config).
                input_fingerprint TEXT NOT NULL DEFAULT '',
                -- Scheduler / engine configuration snapshot (JSON).
                config TEXT NOT NULL DEFAULT '{}',
                -- Compact outcome summary (counts, timeline ref, errors).
                result_summary TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_executions_graph_id
                ON executions (graph_id)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_executions_graph_fingerprint
                ON executions (graph_fingerprint)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_executions_input_fingerprint
                ON executions (input_fingerprint)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_executions_status
                ON executions (status)
            """,
            """
            CREATE TABLE IF NOT EXISTS checkpoints (
                -- One checkpoint per execution (interrupt/resume snapshot).
                execution_id TEXT PRIMARY KEY,
                graph_id TEXT NOT NULL,
                graph_fingerprint TEXT NOT NULL DEFAULT '',
                input_fingerprint TEXT NOT NULL DEFAULT '',
                -- JSON list of succeeded node ids.
                completed_nodes TEXT NOT NULL DEFAULT '[]',
                -- JSON map node_id -> node output payload.
                node_outputs TEXT NOT NULL DEFAULT '{}',
                -- JSON map node_id -> NodeStatus value.
                node_status TEXT NOT NULL DEFAULT '{}',
                -- JSON map node_id -> artifact id list.
                artifact_refs TEXT NOT NULL DEFAULT '{}',
                -- JSON map node_id -> candidate id list.
                candidate_refs TEXT NOT NULL DEFAULT '{}',
                execution_status TEXT NOT NULL DEFAULT 'RUNNING',
                failure_state TEXT NOT NULL DEFAULT '{}',
                updated_at TEXT NOT NULL
            )
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_checkpoints_graph_id
                ON checkpoints (graph_id)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_checkpoints_graph_fingerprint
                ON checkpoints (graph_fingerprint)
            """,
            """
            CREATE TABLE IF NOT EXISTS artifacts (
                id TEXT PRIMARY KEY,
                -- ArtifactType value (image/video/json/...).
                artifact_type TEXT NOT NULL,
                -- Locator of media/bytes; content itself is not stored here.
                content_reference TEXT NOT NULL DEFAULT '',
                source_node TEXT,
                asset_id TEXT,
                schema_version TEXT NOT NULL DEFAULT '1.0',
                technical_metadata TEXT NOT NULL DEFAULT '{}',
                provider_metadata TEXT NOT NULL DEFAULT '{}',
                generation_metadata TEXT NOT NULL DEFAULT '{}',
                quality_state TEXT NOT NULL DEFAULT 'UNEVALUATED',
                -- Production-condition fingerprint (not content hash).
                fingerprint TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            )
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_artifacts_fingerprint
                ON artifacts (fingerprint)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_artifacts_source_node
                ON artifacts (source_node)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_artifacts_asset_id
                ON artifacts (asset_id)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_artifacts_quality_state
                ON artifacts (quality_state)
            """,
            """
            CREATE TABLE IF NOT EXISTS artifact_provenance (
                -- 1:1 provenance trace for an artifact.
                artifact_id TEXT PRIMARY KEY,
                story_id TEXT,
                story_version INTEGER,
                -- JSON list of semantic asset ids.
                asset_ids TEXT NOT NULL DEFAULT '[]',
                graph_node_id TEXT,
                execution_id TEXT,
                generation_spec_hash TEXT,
                provider_id TEXT,
                model_id TEXT,
                candidate_id TEXT,
                -- JSON list of quality result ids.
                quality_results TEXT NOT NULL DEFAULT '[]',
                -- JSON list of repair plan ids.
                repair_history TEXT NOT NULL DEFAULT '[]',
                -- JSON map of input name -> artifact/content ref.
                inputs TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL
            )
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_provenance_execution_id
                ON artifact_provenance (execution_id)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_provenance_graph_node_id
                ON artifact_provenance (graph_node_id)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_provenance_story_id
                ON artifact_provenance (story_id)
            """,
            """
            CREATE TABLE IF NOT EXISTS decision_records (
                id TEXT PRIMARY KEY,
                -- routing | selection | gate | other.
                decision_type TEXT NOT NULL,
                subject TEXT NOT NULL,
                -- JSON list of candidate ids considered.
                candidates TEXT NOT NULL DEFAULT '[]',
                policy TEXT NOT NULL DEFAULT '{}',
                selected TEXT,
                reason TEXT NOT NULL DEFAULT '',
                evidence TEXT NOT NULL DEFAULT '{}',
                execution_id TEXT,
                created_at TEXT NOT NULL
            )
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_decisions_execution_id
                ON decision_records (execution_id)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_decisions_subject
                ON decision_records (subject)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_decisions_type
                ON decision_records (decision_type)
            """,
            """
            CREATE TABLE IF NOT EXISTS quality_results (
                id TEXT PRIMARY KEY,
                -- Subject under evaluation (artifact id / node id / ...).
                subject_id TEXT NOT NULL,
                -- GateResult value: PASS | WARN | BLOCK.
                gate TEXT NOT NULL,
                scores TEXT NOT NULL DEFAULT '{}',
                evidence TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL
            )
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_quality_results_subject_id
                ON quality_results (subject_id)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_quality_results_gate
                ON quality_results (gate)
            """,
            """
            CREATE TABLE IF NOT EXISTS quality_issues (
                id TEXT PRIMARY KEY,
                -- Optional parent quality result.
                quality_result_id TEXT,
                -- IssueType value.
                issue_type TEXT NOT NULL,
                -- Severity value.
                severity TEXT NOT NULL,
                node_id TEXT,
                asset_id TEXT,
                message TEXT NOT NULL DEFAULT '',
                evidence TEXT NOT NULL DEFAULT '{}',
                -- JSON list of node ids suggested for repair scope.
                suggested_scope TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL
            )
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_quality_issues_result_id
                ON quality_issues (quality_result_id)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_quality_issues_node_id
                ON quality_issues (node_id)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_quality_issues_asset_id
                ON quality_issues (asset_id)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_quality_issues_type
                ON quality_issues (issue_type)
            """,
            """
            CREATE TABLE IF NOT EXISTS repair_plans (
                id TEXT PRIMARY KEY,
                -- RepairKind value: PREFLIGHT | POST_GENERATION.
                kind TEXT NOT NULL,
                -- JSON list of issue ids this plan addresses.
                issues TEXT NOT NULL DEFAULT '[]',
                invalidate_node_ids TEXT NOT NULL DEFAULT '[]',
                keep_node_ids TEXT NOT NULL DEFAULT '[]',
                -- JSON list of RepairAction-like objects.
                actions TEXT NOT NULL DEFAULT '[]',
                rationale TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            )
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_repair_plans_kind
                ON repair_plans (kind)
            """,
        ],
    ),
    (
        2,
        [
            """
            CREATE TABLE IF NOT EXISTS production_knowledge (
                id TEXT PRIMARY KEY,
                story_id TEXT NOT NULL,
                version INTEGER NOT NULL DEFAULT 1,
                fingerprint TEXT NOT NULL DEFAULT '',
                -- Full ProductionKnowledge JSON payload.
                payload TEXT NOT NULL DEFAULT '{}',
                source_refs TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_knowledge_story_id
                ON production_knowledge (story_id)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_knowledge_fingerprint
                ON production_knowledge (fingerprint)
            """,
            """
            CREATE TABLE IF NOT EXISTS candidates (
                id TEXT PRIMARY KEY,
                node_id TEXT NOT NULL,
                artifact_id TEXT NOT NULL DEFAULT '',
                selected INTEGER NOT NULL DEFAULT 0,
                score REAL NOT NULL DEFAULT 0.0,
                quality_state TEXT NOT NULL DEFAULT 'UNEVALUATED',
                execution_id TEXT,
                payload TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL
            )
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_candidates_node_id
                ON candidates (node_id)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_candidates_execution_id
                ON candidates (execution_id)
            """,
            """
            CREATE TABLE IF NOT EXISTS execution_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                execution_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                subject TEXT NOT NULL DEFAULT '',
                payload TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL
            )
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_events_execution_id
                ON execution_events (execution_id)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_events_type
                ON execution_events (event_type)
            """,
        ],
    ),
]
