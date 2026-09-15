[![English](https://img.shields.io/badge/English-README-blue)](README.md)
[![简体中文](https://img.shields.io/badge/简体中文-README-green)](README.zh-CN.md)

# Drama Forge

![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![License](https://img.shields.io/badge/license-AGPL--3.0--or--later-blue)
![CI](https://github.com/zcbacxc/drama-forge/actions/workflows/ci.yml/badge.svg)
![PyPI](https://img.shields.io/pypi/v/drama-forge)

> Core Engine for productized AI drama production

Drama Forge turns story content into a **repeatable, recoverable, repairable** production graph. It is **not** a Studio UI, SaaS layer, or prompt library.

```
Story → Compiler → Production Spec / Manifest → Production Graph
  → Execution Runtime → Capability / Provider
  → Artifact / Candidate → Quality Gate → Select / Repair
  → Canonical Timeline → Provenance → Production History (SQLite)
```

## Features

- Domain kernel: Story / Character / Scene / Shot / Asset / Artifact / Production Graph / Fingerprint
- Story compiler and production-spec planner
- Execution runtime with checkpoint, retry, parallel scheduler, cooperative cancel
- Provider decoupling: mock, OpenAI-compatible HTTP, DeepSeek, SiliconFlow, Agnes
- Per-capability routing via `provider_policy["by_capability"]`
- Typed artifact store with provenance and fingerprint cache
- Quality runtime: validators, evaluators, gates, repair planner
- Production Knowledge harvest / merge / continuity injection
- Canonical timeline model and renderer
- SQLite persistence (schema v2) and verification CLI
- Nine core engineering validations covered by tests

## Requirements

- Python 3.11+

## Install

### From PyPI

```bash
pip install drama-forge
```

### From source

```bash
git clone https://github.com/zcbacxc/drama-forge.git
cd drama-forge
pip install -e ".[dev]"
```

## Quick start

### Programmatic API

```python
from drama_forge import Engine

engine = Engine(db_path="production.db")  # optional SQLite history
story = engine.compile("examples/story_sample.json")
result = engine.run(story, candidate_count=2)
print(result.status, result.timeline_artifact.id)
print(engine.inspect(result.timeline_artifact.id))
```

### CLI

```bash
drama-forge version
drama-forge doctor
drama-forge compile examples/story_sample.json
drama-forge run examples/story_sample.json
drama-forge status <execution-id>
drama-forge inspect <artifact-id>
drama-forge validate <execution-id>
drama-forge repair <execution-id> examples/story_sample.json
```

Installed console script `drama-forge` is equivalent to `python -m drama_forge.cli.main`.

## Provider configuration

Local mock providers work with zero config. Configuration is loaded from
`DRAMA_FORGE_*` environment variables, project `.env`, and user-level
`~/.drama-forge/.env` (auto-created from `.env.example` on first run).

```bash
cp .env.example .env   # or edit ~/.drama-forge/.env
# then set keys / DRAMA_FORGE_PROVIDER
```

OpenAI-compatible HTTP provider:

```bash
export DRAMA_FORGE_PROVIDER=openai_compatible
export DRAMA_FORGE_PROVIDER_BASE_URL=https://api.openai.com
export DRAMA_FORGE_PROVIDER_API_KEY=sk-...
export DRAMA_FORGE_PROVIDER_MODEL=gpt-4o-mini
export DRAMA_FORGE_PROVIDER_DRY_RUN=1   # offline fallback, no network
```

Production providers (Stage C/F):

```bash
export DRAMA_FORGE_PROVIDER=production          # or deepseek+siliconflow
export DRAMA_FORGE_DEEPSEEK_API_KEY=sk-...
export DRAMA_FORGE_SILICONFLOW_API_KEY=sk-...
# optional: export DRAMA_FORGE_PROVIDER_DRY_RUN=1  # force offline fallbacks
```

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

## Package layout

```
src/drama_forge/
  domain/         # story, asset, production, quality, continuity, knowledge
  compiler/       # parser, story graph, production spec, manifest
  runtime/        # scheduler, worker, checkpoint, events, cancellation
  providers/      # registry, router, factory, mock + HTTP adapters
  capabilities/   # capability registry, character/scene consistency, audio
  timeline/       # canonical timeline model + renderer
  artifacts/      # typed artifact store + provenance
  quality/        # validators, evaluators, gates, repair
  persistence/    # SQLite database + repositories
  engine.py       # programmatic facade
  cli/            # verification CLI
```

## Documentation

- [docs/index.md](docs/index.md) — architecture, contributing, roadmap, packaging, ADR, providers
- [ARCHITECTURE.md](docs/ARCHITECTURE.md) · [架构](docs/ARCHITECTURE.zh-CN.md)
- [CONTRIBUTING.md](docs/CONTRIBUTING.md) · [贡献指南](docs/CONTRIBUTING.zh-CN.md)
- [ROADMAP.md](docs/ROADMAP.md) · [路线图](docs/ROADMAP.zh-CN.md)
- [PACKAGING.md](docs/PACKAGING.md) · [打包](docs/PACKAGING.zh-CN.md)

## Development

```bash
pip install -e ".[dev]"
python -m pytest -v
ruff check src tests
mypy src
```

## Security

See [SECURITY.md](SECURITY.md). Please report vulnerabilities privately via GitHub Security Advisories.

## License

[AGPL-3.0-or-later](LICENSE)

## Changelog

See [CHANGELOG.md](CHANGELOG.md).
