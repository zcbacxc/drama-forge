[![English](https://img.shields.io/badge/English-Packaging-blue)](PACKAGING.md)
[![简体中文](https://img.shields.io/badge/简体中文-打包-green)](PACKAGING.zh-CN.md)

# 打包指南

**drama-forge** 的版本与发布约定。

## 版本唯一来源

- 包版本：`pyproject.toml` → `[project] version`
- 运行时版本：`src/drama_forge/version.py`（`__version__`）
- 发版时在同一 commit 中对齐
- 版本 bump 必须与 `CHANGELOG.md` 同 commit 更新

## 语义化版本

| 变更 | 版本位 |
|------|--------|
| 破坏性删除 / CLI 或公开 API 不兼容变更 | MAJOR |
| 向后兼容的新能力 | MINOR |
| 修复 / 文档 / 内部重构 | PATCH |

`0.x` 阶段 MINOR 也可能含破坏性变更；必须在 CHANGELOG 中写清楚。

## 当前公开面

可供早期采用者依赖，仍在演进：

- `from drama_forge import Engine` 与 README 中用到的 `Engine` 方法
- CLI：`compile` / `plan` / `run` / `status` / `inspect` / `validate` / `repair` / `doctor` / `version`
- 外部 Production Manifest JSON（`load_manifest_file` / `dump_manifest_file`）
- `.env.example` 中的 `DRAMA_FORGE_*` 环境变量

`drama_forge.domain`、`drama_forge.runtime` 等内部模块若未从包根再导出，可能随时变更。

正式的稳定性承诺文档等公开 API 冻结后再写（见 [路线图](ROADMAP.zh-CN.md)）。

## 本地构建

```bash
pip install build twine
python -m build
twine check dist/*
```

产物在 `dist/`。**不要**提交 `dist/`、`build/`、`*.egg-info/`。

## 通过 CI 发布（推荐）

1. 更新 `pyproject.toml` 版本（若未自动同步，同时改 `version.py`）。
2. 更新 `CHANGELOG.md`。
3. 在 feature 分支提交，PR 合并到 `main` 且 CI 通过。
4. 打 tag 并**与 branch push 分离**推送：

```bash
git tag v0.1.0
git push origin v0.1.0
```

5. `.github/workflows/publish.yml` 自动构建、`twine check`、OIDC Trusted Publishing 发布，并根据 CHANGELOG 创建 GitHub Release。

### Tag 格式

| Tag | 目标 |
|-----|------|
| `vX.Y.Z` | 生产 PyPI |
| `vX.Y.Z-test` | TestPyPI（预发布 GitHub Release） |

### 首次 PyPI Trusted Publishing

首次上传前在 pypi.org 配置 **Pending Publisher**：

- Project name: `drama-forge`
- Owner: `zcbacxc`
- Repository: `drama-forge`
- Workflow: `publish.yml`
- Environment: *（留空）*

之后无需 API token。

## 手工上传（逃生通道）

```bash
python -m build
twine check dist/*
twine upload dist/*
# TestPyPI:
# twine upload --repository testpypi dist/*
```

优先 CI + Trusted Publishing；手工上传仅作紧急恢复。

## 发版前检查

参考 PR 模板，并确认：

1. `pytest -v` 通过
2. `ruff check src tests` 与 `mypy src` 通过
3. CLI 冒烟（`doctor`、`run examples/story_sample.json`）
4. tag 与 `pyproject.toml` 版本一致
5. CHANGELOG 中存在对应版本章节

## 相关

- [贡献指南](CONTRIBUTING.zh-CN.md)
- [路线图](ROADMAP.zh-CN.md)
- [更新日志](../CHANGELOG.md)
