# SPDX-FileCopyrightText: 2026 zcbacxc
# SPDX-License-Identifier: AGPL-3.0-or-later
"""External Production Manifest contract (JSON).

Decision: use JSON (not YAML) for the external Manifest file so Core Engine
stays zero-third-party-dependency. The in-memory ProductionManifest remains
the canonical model; this module only serializes the stable contract fields.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from drama_forge.domain.common import MetadataBag
from drama_forge.domain.production import ProductionManifest

MANIFEST_SCHEMA_VERSION = "1.0"


def manifest_to_contract(manifest: ProductionManifest) -> dict[str, Any]:
    """Serialize a ProductionManifest to the stable external contract dict.

    Args:
            manifest: ProductionManifest

    Returns:
            dict[str, Any]
    """
    return {
        "schema_version": manifest.schema_version or MANIFEST_SCHEMA_VERSION,
        "id": manifest.id,
        "story_id": manifest.story_id,
        "story_version": manifest.story_version,
        "production_spec_id": manifest.production_spec_id,
        "graph_id": manifest.graph_id,
        "capability_policy": dict(manifest.capability_policy),
        "provider_policy": dict(manifest.provider_policy),
        "selection_policy": dict(manifest.selection_policy),
        "quality_policy": dict(manifest.quality_policy),
        "output_policy": dict(manifest.output_policy),
        "asset_versions": dict(manifest.asset_versions),
        "metadata": dict(manifest.metadata.data),
    }


def manifest_from_contract(data: dict[str, Any]) -> ProductionManifest:
    """Build a ProductionManifest from an external contract dict.

    Args:
            data: dict[str, Any]

    Returns:
            ProductionManifest
    """
    required = ("story_id", "production_spec_id", "graph_id")
    missing = [key for key in required if not data.get(key)]
    if missing:
        raise ValueError(f"manifest missing required fields: {missing}")
    schema_version = str(data.get("schema_version") or MANIFEST_SCHEMA_VERSION)
    # Reject unknown major schema versions.
    major = schema_version.split(".", 1)[0]
    if major != MANIFEST_SCHEMA_VERSION.split(".", 1)[0]:
        raise ValueError(f"unsupported manifest schema_version: {schema_version}")
    meta = data.get("metadata") or {}
    return ProductionManifest(
        id=str(data.get("id") or "man_external"),
        story_id=str(data["story_id"]),
        story_version=int(data.get("story_version") or 1),
        production_spec_id=str(data["production_spec_id"]),
        graph_id=str(data["graph_id"]),
        capability_policy=dict(data.get("capability_policy") or {}),
        provider_policy=dict(data.get("provider_policy") or {}),
        selection_policy=dict(data.get("selection_policy") or {}),
        quality_policy=dict(data.get("quality_policy") or {}),
        output_policy=dict(data.get("output_policy") or {}),
        asset_versions={
            str(k): int(v) for k, v in (data.get("asset_versions") or {}).items()
        },
        schema_version=schema_version,
        metadata=MetadataBag(data=dict(meta)),
    )


def dump_manifest_file(manifest: ProductionManifest, path: str | Path) -> Path:
    """Write a ProductionManifest contract JSON file.

    Args:
        manifest: In-memory manifest.
        path: Destination path.

    Returns:
        The path written.
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = manifest_to_contract(manifest)
    target.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return target


def load_manifest_file(path: str | Path) -> ProductionManifest:
    """Load a ProductionManifest from a JSON contract file.

    Args:
        path: Source path.

    Returns:
        Reconstructed ProductionManifest.

    Raises:
        ValueError: On invalid JSON structure or missing fields.
    """
    raw = Path(path).read_text(encoding="utf-8")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid manifest JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("manifest JSON root must be an object")
    manifest = manifest_from_contract(data)
    errors = manifest.validate()
    if errors:
        raise ValueError(f"manifest failed validation: {errors}")
    return manifest
