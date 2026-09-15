# SPDX-FileCopyrightText: 2026 zcbacxc
# SPDX-License-Identifier: AGPL-3.0-or-later
"""SQLite persistence package: Database handle and repositories."""

from drama_forge.persistence.db import Database, dumps, loads, row_to_dict
from drama_forge.persistence.repositories import (
    ArtifactRepository,
    CandidateRepository,
    CheckpointRepository,
    DecisionRepository,
    EventRepository,
    ExecutionRepository,
    GraphRepository,
    KnowledgeRepository,
    QualityRepository,
    RepairRepository,
    StoryRepository,
)
from drama_forge.persistence.schema import SCHEMA_VERSION

__all__ = [
    "SCHEMA_VERSION",
    "Database",
    "dumps",
    "loads",
    "row_to_dict",
    "StoryRepository",
    "GraphRepository",
    "ExecutionRepository",
    "CheckpointRepository",
    "ArtifactRepository",
    "DecisionRepository",
    "QualityRepository",
    "RepairRepository",
    "KnowledgeRepository",
    "CandidateRepository",
    "EventRepository",
]
