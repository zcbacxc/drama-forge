[![English](https://img.shields.io/badge/English-README-blue)](README.md)
[![简体中文](https://img.shields.io/badge/简体中文-README-green)](README.zh-CN.md)

# Drama Forge

![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![License](https://img.shields.io/badge/license-AGPL--3.0--or--later-blue)
![CI](https://github.com/zcbacxc/drama-forge/actions/workflows/ci.yml/badge.svg)
![PyPI](https://img.shields.io/pypi/v/drama-forge)

> 产品化 AI 漫剧生成的核心引擎（Core Engine）

Drama Forge 把故事内容变成**可重复、可恢复、可局部修复**的生产图。它**不是** Studio 工作台、SaaS 业务层，也不是 Prompt 库。

```
Story → Compiler → Production Spec / Manifest → Production Graph
  → Execution Runtime → Capability / Provider
  → Artifact / Candidate → Quality Gate → Select / Repair
  → Canonical Timeline → Provenance → Production History (SQLite)
```

## 能力

- 领域内核：Story / Character / Scene / Shot / Asset / Artifact / Production Graph / Fingerprint
- 故事编译器与生产规格规划
- 执行运行时：checkpoint、retry、并行调度、协作式取消
- Provider 解耦：Mock、OpenAI-compatible HTTP、DeepSeek、SiliconFlow、Agnes
- 通过 `provider_policy["by_capability"]` 做能力级路由
- 带 Provenance 与指纹缓存的类型化 Artifact 存储
- 质量运行时：validator、evaluator、gate、repair planner
- Production Knowledge 的 harvest / merge / continuity 注入
- Canonical Timeline 模型与渲染器
- SQLite 持久化（schema v2）与验证 CLI
- 九项核心工程验证由测试覆盖

## 环境要求

- Python 3.11+

## 安装

### 从 PyPI

```bash
pip install drama-forge
```

### 从源码

```bash
git clone https://github.com/zcbacxc/drama-forge.git
cd drama-forge
pip install -e ".[dev]"
```

## 快速开始

### 编程 API

```python
from drama_forge import Engine

engine = Engine(db_path="production.db")  # 可选 SQLite 历史
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

安装后的控制台命令 `drama-forge` 与 `python -m drama_forge.cli.main` 等价。

## Provider 配置

本地 Mock Provider 零配置可用。配置来源：`DRAMA_FORGE_*` 环境变量、项目 `.env`、用户级 `~/.drama-forge/.env`（首次运行会从 `.env.example` 自动创建）。

```bash
cp .env.example .env
# 然后设置密钥 / DRAMA_FORGE_PROVIDER
```

生产 Provider（Stage C/F）：

```bash
export DRAMA_FORGE_PROVIDER=production
export DRAMA_FORGE_DEEPSEEK_API_KEY=sk-...
export DRAMA_FORGE_SILICONFLOW_API_KEY=sk-...
```

## 文档

- [docs/index.md](docs/index.md) — 架构、贡献、路线图、打包、ADR、Provider
- [ARCHITECTURE.zh-CN.md](docs/ARCHITECTURE.zh-CN.md) · [Architecture](docs/ARCHITECTURE.md)
- [CONTRIBUTING.zh-CN.md](docs/CONTRIBUTING.zh-CN.md) · [Contributing](docs/CONTRIBUTING.md)
- [ROADMAP.zh-CN.md](docs/ROADMAP.zh-CN.md) · [Roadmap](docs/ROADMAP.md)
- [PACKAGING.zh-CN.md](docs/PACKAGING.zh-CN.md) · [Packaging](docs/PACKAGING.md)

## 开发

```bash
pip install -e ".[dev]"
python -m pytest -v
ruff check src tests
mypy src
```

## 安全

见 [SECURITY.zh-CN.md](SECURITY.zh-CN.md)。漏洞请通过 GitHub Security Advisories 私下报告。

## 许可证

[AGPL-3.0-or-later](LICENSE)

## 更新日志

见 [CHANGELOG.md](CHANGELOG.md)。
