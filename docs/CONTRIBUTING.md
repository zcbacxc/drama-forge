[![English](https://img.shields.io/badge/English-Contributing-blue)](CONTRIBUTING.md)
[![简体中文](https://img.shields.io/badge/简体中文-贡献指南-green)](CONTRIBUTING.zh-CN.md)

# Contributing

Thanks for your interest in Drama Forge.

## Scope reminder

Drama Forge is a **Core Engine** for productized AI drama production. It is **not** a Studio UI, SaaS layer, Agent runtime, or prompt library. Before opening a PR or feature request, check that the change serves:

```
Story → Compiler → Spec / Manifest → Production Graph
  → Execution → Provider → Artifact / Candidate
  → Quality Gate → Select / Repair
  → Timeline → Provenance → Knowledge
```

## Development setup

```bash
git clone https://github.com/zcbacxc/drama-forge.git
cd drama-forge
python -m venv venv
# Windows: venv\Scripts\activate
source venv/bin/activate
pip install -e ".[dev]"
```

## Project structure

```
drama-forge/
├── src/drama_forge/
│   ├── domain/         # story, asset, production, quality, continuity, knowledge
│   ├── compiler/       # parser, story graph, production spec, manifest
│   ├── runtime/        # scheduler, worker, checkpoint, events, cancellation
│   ├── providers/      # registry, router, factory, mock + HTTP adapters
│   ├── capabilities/   # capability registry, consistency, audio
│   ├── timeline/       # canonical timeline model + renderer
│   ├── artifacts/      # typed artifact store + provenance
│   ├── quality/        # validators, evaluators, gates, repair
│   ├── persistence/    # SQLite database + repositories
│   ├── engine.py       # programmatic facade
│   └── cli/            # verification CLI
├── tests/
├── docs/
└── examples/
```

## Running tests

```bash
python -m pytest -v
ruff check src tests
mypy src
```

CLI smoke (mock providers, no external API):

```bash
drama-forge doctor
drama-forge compile examples/story_sample.json
drama-forge run examples/story_sample.json
```

## Code style

- Type annotations first; Google-style docstrings on public API
- Do not introduce internal tracking codes (EP*, WP*, NA-M*, etc.) in code, comments, or docs
- Keep provider details out of Domain / Canonical model layers
- Prefer editing existing modules over adding new abstraction layers

## Branch and commit

- Branch model: `feature/*`, `hotfix/*` → PR → `main`
- Do not push directly to `main`
- Commit prefixes: `feat:` / `fix:` / `docs:` / `chore:` / `refactor:`

## Documentation

- User-facing docs live in `docs/` as English + Chinese pairs (`.md` / `.zh-CN.md`) with matching structure
- Do **not** commit local design docs (`PROJECT_POSITIONING.md`, `docs-nocommit/`)
- Update `CHANGELOG.md` for user-facing changes
- Update `docs/ROADMAP.md` only for shipped or firmly planned themes

## Pull requests

Use the PR template. Before requesting review:

1. `pytest -v` passes
2. `ruff check src tests` and `mypy src` pass
3. CHANGELOG updated when the change is user-facing
4. Scope still matches Core Engine positioning

## License

By contributing, you agree that your contributions are licensed under **AGPL-3.0-or-later**. See [LICENSE](../LICENSE).
