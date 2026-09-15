[![English](https://img.shields.io/badge/English-AI_Guide-blue)](AI_GUIDE.md)
[![简体中文](https://img.shields.io/badge/简体中文-AI指南-green)](AI_GUIDE.zh-CN.md)

# AI 编程助手指南

> 面向 AI 编程工具（Claude Code、Codex、Cursor、Copilot 等）的导航索引。正文在对应文档中，本页只做路由。

## 从这里开始

| 主题 | 文档 |
|------|------|
| 概览与安装 | [README.zh-CN](../README.zh-CN.md) |
| 英文 README | [README](../README.md) |
| 架构（五核、闭环） | [ARCHITECTURE.zh-CN.md](ARCHITECTURE.zh-CN.md) |
| 贡献规则 | [CONTRIBUTING.zh-CN.md](CONTRIBUTING.zh-CN.md) |

## 设计决策

| 主题 | 文档 |
|------|------|
| ADR 索引与模板 | [ADR.zh-CN.md](ADR.zh-CN.md) |
| Provider 指南 | [LLM_PROVIDERS.zh-CN.md](LLM_PROVIDERS.zh-CN.md) |
| 版本与 PyPI | [PACKAGING.zh-CN.md](PACKAGING.zh-CN.md) |
| 已发布 / 计划主题 | [ROADMAP.zh-CN.md](ROADMAP.zh-CN.md) |

## 编辑时的硬约束

1. 只做 Core Engine —— 不引入 Studio / SaaS / Agent-as-Runtime 范围蔓延
2. Provider 细节不得进入 Domain / Canonical 模型
3. 公开文档与 commit 中不得出现内部追踪码（EP*、WP*、NA-M* 等）
4. 对外双语保持结构对齐（`.md` + `.zh-CN.md`）
5. 本地设计文档（`PROJECT_POSITIONING.md`、`docs-nocommit/`）**不得**提交或复制进 `docs/`
6. 用户可见变更更新 CHANGELOG；版本以 `pyproject.toml` 为唯一来源

## CLI 速查

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

## 仅本地（不要外发）

| 文件 | 职责 |
|------|------|
| `PROJECT_POSITIONING.md` | 定位 / 不做清单（gitignore） |
| `docs-nocommit/confirmed/IMPLEMENTATION_PLAN.md` | 完整工程方案（gitignore） |
| `.claude/rules/` | 路径级 agent 规则（gitignore） |
