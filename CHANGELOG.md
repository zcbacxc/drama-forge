# Changelog

All notable changes to Drama Forge Core Engine are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

_Nothing yet._

## [0.2.0] - 2026-09-15

### Added
- Stage F capabilities package: capability registry, character/scene consistency, dialogue audio planning
- Timeline package: canonical timeline model and renderer with audio alignment and segment substitution
- Domain continuity models (rules, findings, report)
- SQLite persistence layer (11 tables, migrations, 8 repositories) wired into Engine via `db_path`
- Enhanced providers: OpenAI-compatible HTTP adapter (dry-run safe), env-driven factory, CostTracker, `reliability_first` routing
- CLI: `version` command and `--db` persistence flag; doctor reports version and persistence state
- GitHub Actions CI (lint, tests, CLI smoke) and tag release gate
- CHANGELOG and release process documentation

### Changed
- Engine registers providers through `build_default_registry` for consistent mock/HTTP behavior
- Production graph adds `generate_dialogue_audio` nodes for shots with dialogue
- Timeline assembly uses CanonicalTimelineBuilder + TimelineRenderer

## [0.1.0] - 2026-09-15

### Added
- Domain kernel: Story / Character / Scene / Shot / Asset / Artifact / Candidate / Production Graph
- Story compiler: parser, story graph, production spec, production graph planner
- Execution runtime: scheduler, worker, retry, checkpoint, events, fingerprint reuse
- Capability routing: registry, strategy router, decision records, mock providers
- Artifact store with provenance and fingerprint cache
- Quality runtime: validators, evaluators, gates, repair planner, dirty propagation
- Programmatic `Engine` facade and verification CLI
- Nine core engineering validations covered by tests

[Unreleased]: https://github.com/example/drama-forge/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/example/drama-forge/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/example/drama-forge/releases/tag/v0.1.0
