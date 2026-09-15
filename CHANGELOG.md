# Changelog

All notable changes to Drama Forge Core Engine are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- DeepSeek as an OpenAI-compatible HTTP preset (`chat/completions` path, `deepseek-flash` default model)
- SiliconFlow image provider adapter (`siliconflow-image`) for `/v1/images/generations`
- Agnes image via shared images adapter (`agnes-image`, default `agnes-image-2.0-flash`; OpenAI `data[].url` live-verified)
- Agnes video provider adapter (`agnes-video`) for gateway `POST /v1/videos` (`mode=T2V`; models `agnes-video-2.5-flash` / `2.5` / `v2.0`)
- Factory families: `deepseek`, `siliconflow`/`sf`, `agnes`/`agnes-video`, `agnes-image`, `production` (= `deepseek+siliconflow`), and `a+b` combinations
- Per-capability provider routing via `provider_policy["by_capability"]`
- Configurable `HttpProviderConfig.chat_path` and `reasoning_content` fallback in the shared adapter
- Offline contract tests and optional live smoke (`DRAMA_FORGE_LIVE_SMOKE=1`)

### Fixed
- `.gitignore` root-scoped `artifacts/` so `src/drama_forge/artifacts/` is tracked
- OpenAI-compatible chat endpoint joining when `base_url` already ends with `/v1`

## [0.1.0] - 2026-09-15

Initial release of the Core Engine implementation plan (stages A–F).

### Added
- Domain kernel: Story / Character / Scene / Shot / Asset / Artifact / Candidate / Production Graph / Fingerprint
- Story compiler: parser, story graph, production spec, production graph planner
- Execution runtime: scheduler, worker, retry, checkpoint, events, fingerprint reuse
- Capability routing: registry, strategy router (including `reliability_first`), decision records
- Providers: local mock set, OpenAI-compatible HTTP adapter (dry-run safe), env-driven factory, CostTracker
- Typed artifact store with provenance and fingerprint cache
- Quality runtime: validators, evaluators, gates, repair planner, dirty propagation
- Stage F capabilities: capability registry, character/scene consistency, dialogue audio planning
- Timeline package: canonical timeline model and renderer with audio alignment and segment substitution
- Domain continuity models (rules, findings, report)
- SQLite persistence layer (11 tables, migrations, 8 repositories) wired into Engine via `db_path`
- Programmatic `Engine` facade and verification CLI (`compile` / `plan` / `run` / `status` / `inspect` / `validate` / `repair` / `doctor` / `version`)
- Nine core engineering validations covered by tests
- GitHub Actions CI (lint, tests, CLI smoke) and tag release gate

[Unreleased]: https://github.com/example/drama-forge/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/example/drama-forge/releases/tag/v0.1.0
