[![English](https://img.shields.io/badge/English-Packaging-blue)](PACKAGING.md)
[![简体中文](https://img.shields.io/badge/简体中文-打包-green)](PACKAGING.zh-CN.md)

# Packaging Guide

Versioning and publishing conventions for **drama-forge**.

## Version source of truth

- Package version: `pyproject.toml` → `[project] version`
- Runtime version: `src/drama_forge/version.py` (`__version__`)
- Keep them aligned in the same commit when cutting a release
- `CHANGELOG.md` must be updated in the same commit as a version bump

## Semantic versioning

| Change | Bump |
|--------|------|
| Breaking removal / incompatible CLI or public API change | MAJOR |
| Backward-compatible feature | MINOR |
| Fix / docs / internal refactor | PATCH |

While the project is `0.x`, MINOR may include breaking changes; document them clearly in CHANGELOG.

## Public surface (current)

Stable enough for early adopters, still evolving:

- `from drama_forge import Engine` and `Engine` methods used in README
- CLI: `compile` / `plan` / `run` / `status` / `inspect` / `validate` / `repair` / `doctor` / `version`
- External Production Manifest JSON (`load_manifest_file` / `dump_manifest_file`)
- `DRAMA_FORGE_*` environment variables documented in `.env.example`

Internal modules under `drama_forge.domain`, `drama_forge.runtime`, etc. may change without notice unless re-exported from the package root.

A formal stability promise document is deferred until the public API freezes (see [STABILITY](ROADMAP.md)).

## Building locally

```bash
pip install build twine
python -m build
twine check dist/*
```

Wheels and sdists land in `dist/`. Never commit `dist/`, `build/`, or `*.egg-info/`.

## Publishing via CI (recommended)

1. Bump `pyproject.toml` version (+ `version.py` if not auto-synced).
2. Update `CHANGELOG.md`.
3. Commit on a feature branch, open PR, merge to `main` after CI green.
4. Tag and push the tag **separately** from the branch push:

```bash
git tag v0.1.0
git push origin v0.1.0
```

5. `.github/workflows/publish.yml` builds, `twine check`s, publishes with OIDC Trusted Publishing, and creates a GitHub Release from CHANGELOG notes.

### Tag formats

| Tag | Target |
|-----|--------|
| `vX.Y.Z` | Production PyPI |
| `vX.Y.Z-test` | TestPyPI (prerelease GitHub Release) |

### First-time PyPI Trusted Publishing

Before the first upload, configure a **Pending Publisher** on pypi.org:

- Project name: `drama-forge`
- Owner: `zcbacxc`
- Repository: `drama-forge`
- Workflow: `publish.yml`
- Environment: *(leave empty)*

No API token is required after that.

## Manual upload (escape hatch)

```bash
python -m build
twine check dist/*
twine upload dist/*
# TestPyPI:
# twine upload --repository testpypi dist/*
```

Prefer CI + Trusted Publishing; manual upload is for emergency recovery only.

## Pre-release checklist

See the PR template and:

1. `pytest -v` green
2. `ruff check src tests` and `mypy src` green
3. CLI smoke (`doctor`, `run examples/story_sample.json`)
4. Tag matches `pyproject.toml` version
5. CHANGELOG section exists for the version

## Related

- [Contributing](CONTRIBUTING.md)
- [Roadmap](ROADMAP.md)
- [Changelog](../CHANGELOG.md)
