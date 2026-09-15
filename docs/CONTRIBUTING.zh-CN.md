[![English](https://img.shields.io/badge/English-Contributing-blue)](CONTRIBUTING.md)
[![简体中文](https://img.shields.io/badge/简体中文-贡献指南-green)](CONTRIBUTING.zh-CN.md)

# 贡献指南

感谢关注 Drama Forge。

## 定位提醒

Drama Forge 是**产品化 AI 漫剧生成的 Core Engine**。它**不是** Studio 工作台、SaaS 业务层、Agent Runtime 或 Prompt 库。提交 PR / 需求前请确认变更服务于：

```
Story → Compiler → Spec / Manifest → Production Graph
  → Execution → Provider → Artifact / Candidate
  → Quality Gate → Select / Repair
  → Timeline → Provenance → Knowledge
```

## 开发环境

```bash
git clone https://github.com/zcbacxc/drama-forge.git
cd drama-forge
python -m venv venv
# Windows: venv\Scripts\activate
source venv/bin/activate
pip install -e ".[dev]"
```

## 项目结构

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

## 运行测试

```bash
python -m pytest -v
ruff check src tests
mypy src
```

CLI 冒烟（Mock Provider，不依赖外部 API）：

```bash
drama-forge doctor
drama-forge compile examples/story_sample.json
drama-forge run examples/story_sample.json
```

## 代码风格

- 优先类型注解；公共 API 使用 Google-style docstring
- 禁止在代码、注释、文档中引入内部追踪码（EP*、WP*、NA-M* 等）
- Provider 细节不要写进 Domain / Canonical 模型层
- 优先改现有模块，避免提前抽象

## 分支与提交

- 分支模型：`feature/*`、`hotfix/*` → PR → `main`
- 禁止直推 `main`
- Commit 前缀：`feat:` / `fix:` / `docs:` / `chore:` / `refactor:`

## 文档

- 用户向文档放在 `docs/`，英文 + 中文成对（`.md` / `.zh-CN.md`），结构对齐
- **不要**提交本地设计文档（`PROJECT_POSITIONING.md`、`docs-nocommit/`）
- 用户可见变更更新 `CHANGELOG.md`
- 仅对已落地或明确规划的主题更新 `docs/ROADMAP.md`

## Pull Request

使用 PR 模板。请求评审前请确认：

1. `pytest -v` 通过
2. `ruff check src tests` 与 `mypy src` 通过
3. 用户可见变更已写 CHANGELOG
4. 范围仍符合 Core Engine 定位

## 许可证

贡献内容以 **AGPL-3.0-or-later** 授权。见 [LICENSE](../LICENSE)。
