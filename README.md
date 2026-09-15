# Drama Forge

Core Engine for productized AI drama production.

## What this is

Drama Forge turns story content into a repeatable, recoverable, repairable production graph:

```
Story → Compiler → Production Spec / Manifest → Production Graph
  → Execution Runtime → Capability / Provider
  → Artifact / Candidate → Quality Gate → Select / Repair
  → Canonical Timeline → Provenance → Production History (SQLite)
```

It is **not** a Studio UI, SaaS layer, or prompt library.

## Requirements

- Python 3.11+

## Install

```bash
pip install -e ".[dev]"
```

## Programmatic API

```python
from drama_forge import Engine

engine = Engine(db_path="production.db")  # optional SQLite history
story = engine.compile("examples/story_sample.json")
result = engine.run(story, candidate_count=2)
print(result.status, result.timeline_artifact.id)
print(engine.inspect(result.timeline_artifact.id))
```

## CLI

```bash
python -m drama_forge.cli.main version
python -m drama_forge.cli.main doctor
python -m drama_forge.cli.main --db prod.db compile examples/story_sample.json
python -m drama_forge.cli.main --db prod.db run examples/story_sample.json
python -m drama_forge.cli.main run examples/story_sample.json --inject-continuity-issue
python -m drama_forge.cli.main status <execution-id>
python -m drama_forge.cli.main inspect <artifact-id>
python -m drama_forge.cli.main validate <execution-id>
python -m drama_forge.cli.main repair <execution-id> examples/story_sample.json
```

## Provider configuration

Local mock providers work with zero config. Configuration is loaded from
`DRAMA_FORGE_*` environment variables, project `.env`, and user-level
`~/.drama-forge/.env` (auto-created from `.env.example` on first run).

```bash
cp .env.example .env   # or edit ~/.drama-forge/.env
# then set keys / DRAMA_FORGE_PROVIDER
```

To attach an OpenAI-compatible HTTP provider:

```bash
export DRAMA_FORGE_PROVIDER=openai_compatible
export DRAMA_FORGE_PROVIDER_BASE_URL=https://api.openai.com
export DRAMA_FORGE_PROVIDER_API_KEY=sk-...
export DRAMA_FORGE_PROVIDER_MODEL=gpt-4o-mini
export DRAMA_FORGE_PROVIDER_DRY_RUN=1   # offline fallback, no network
```

### Production providers (Stage C/F)

DeepSeek is used via the shared **OpenAI-compatible** adapter (no vendor-specific adapter).
SiliconFlow covers image generation.

```bash
export DRAMA_FORGE_PROVIDER=production          # or deepseek+siliconflow
export DRAMA_FORGE_DEEPSEEK_API_KEY=sk-...
export DRAMA_FORGE_SILICONFLOW_API_KEY=sk-...
# optional: export DRAMA_FORGE_PROVIDER_DRY_RUN=1  # force offline fallbacks
```

DeepSeek preset notes (live-verified):
- chat path is `chat/completions` (not `/v1/chat/completions`)
- default model is `deepseek-flash` (override with `DRAMA_FORGE_DEEPSEEK_MODEL`)

Pin providers per capability without changing the production graph:

```python
policy = {
    "strategy": "balanced",
    "by_capability": {
        "text_generation": {"provider_id": "deepseek"},
        "image_generation": {"provider_id": "siliconflow-image"},
    },
}
result = engine.run(story, provider_policy=policy)
```

Live smoke (optional, requires keys):

```bash
export DRAMA_FORGE_LIVE_SMOKE=1
pytest tests/test_live_provider_smoke.py -v
```

## Tests

```bash
python -m pytest -v
ruff check src tests
```

## Package layout

```
src/drama_forge/
  domain/         # story, asset, production, quality, continuity
  compiler/       # parser, story graph, production spec
  runtime/        # scheduler, worker, checkpoint, events
  providers/      # registry, router, factory, mock + HTTP adapters
  capabilities/   # capability registry, character/scene consistency, audio
  timeline/       # canonical timeline model + renderer
  artifacts/      # typed artifact store + provenance
  quality/        # validators, evaluators, gates, repair
  persistence/    # SQLite database + repositories
  engine.py       # programmatic facade
  cli/            # verification CLI
```

## Release

See `docs-nocommit/in-progress/release-process.md` (local) and `CHANGELOG.md`.
CI runs lint + tests + CLI smoke; tags require matching `pyproject.toml` version.
