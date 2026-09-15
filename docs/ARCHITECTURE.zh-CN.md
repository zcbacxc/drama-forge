[![English](https://img.shields.io/badge/English-Architecture-blue)](ARCHITECTURE.md)
[![简体中文](https://img.shields.io/badge/简体中文-架构-green)](ARCHITECTURE.zh-CN.md)

# 架构

本页是**对外架构概览**，描述 Drama Forge Core Engine 的稳定核心与数据流。它不是完整实现方案，也不罗列每个模块。

## 定位

Drama Forge 把故事内容变成**可重复、可恢复、可局部修复**的生产图。

它**不**提供：

- Studio / Canvas / 可视化创作台
- SaaS 业务层（用户、会员、支付、组织、协作）
- 把 Agent 当生产 Runtime
- 把 Prompt 当核心资产
- 把某家 Provider 的 Workflow 当生产模型

## 生产闭环

```
Story Source
  → Story Compiler → Story Model / Story Graph
  → Production Spec / Manifest
  → Canonical Production Model
  → Production Graph
  → Execution Runtime
  → Capability Router → Provider
  → Artifact / Candidate
  → Quality Runtime (Validate / Evaluate / Gate / Issue / Repair)
  → Select / Partial Repair / Dirty Propagation
  → Canonical Timeline
  → Production Knowledge
```

成功标准**不是**「能不能生成一个视频」，而是生产过程是否可重复、可恢复、可局部修复、可追溯、可演进。

## 五个稳定核心

```text
┌──────────────────────────────────────────────────────────────┐
│                     Programmatic facade                      │
│                    engine.py  /  CLI                         │
└───────────┬──────────────────────────────┬───────────────────┘
            │                              │
            ▼                              ▼
┌─────────────────────┐        ┌─────────────────────┐
│   Domain Model      │        │  Production Model   │
│  Story/Asset/Shot   │───────▶│  Spec/Graph/Policy  │
└─────────┬───────────┘        └─────────┬───────────┘
          │                              │
          └──────────────┬───────────────┘
                         ▼
            ┌────────────────────────┐
            │  Execution Runtime     │
            │  Scheduler/Checkpoint  │
            └───────────┬────────────┘
                        ▼
            ┌────────────────────────┐
            │  Artifact Runtime      │
            │  Store/Provenance      │
            └───────────┬────────────┘
                        ▼
            ┌────────────────────────┐
            │  Quality Runtime       │
            │  Gate/Issue/Repair     │
            └────────────────────────┘
```

| 核心 | 职责 |
|------|------|
| **Domain Model** | Story / World / Character / Scene / Shot / Asset / Relationship / Timeline |
| **Production Model** | Manifest / Spec / Production Graph（Node + Edge + Fingerprint + Policy） |
| **Execution Runtime** | ExecutionPlan / Scheduler / Task / Worker / Checkpoint / Retry / Event / Cancel |
| **Artifact Runtime** | Typed Artifact / ArtifactStore / Provenance / 指纹缓存 |
| **Quality Runtime** | Validator / Evaluator / Gate / Issue / RepairPlanner |

## 解耦原则

> 生产定义与 Provider 解耦。  
> 生产图与执行器解耦。  
> 语义资产与实际文件解耦。  
> 质量判断与修复动作解耦。

### Canonical 中间层

Provider 的输出必须被吸收到 Drama Forge 自己的 Canonical Production Model 中；第三方 API 返回结构不得成为核心生产模型。

## 概念对

| 概念 A | 概念 B | 区别 |
|--------|--------|------|
| Asset | Artifact | 语义身份 vs 某次生成结果文件 |
| Retry | Repair | 执行失败重跑同一 Task vs 生产定义/结果不满足后局部重生产 |
| Event | Decision Record | 「发生了什么」vs「为什么这么决定」 |
| Fingerprint | Provenance | 「是否同一生产条件」vs「结果怎么来的」 |
| Provenance | Production Knowledge | 历史记录 vs 可进入下次 Spec 的稳定规则 |

## 能力与 Provider

- 生产图声明能力（`text_generation`、`image_generation` 等）。
- Provider 按能力注册；默认 Mock 可离线运行。
- 可通过 `provider_policy["by_capability"]` **在不改生产图**的前提下按能力钉选 Provider。
- 真实 Provider（OpenAI-compatible HTTP、DeepSeek、SiliconFlow、Agnes 等）挂在同一能力面下，并支持 dry-run 回退。

## 持久化

可选 SQLite 历史（`db_path`）保存生产对象、候选、执行事件、质量结果与 Production Knowledge（schema v2）。产物在本地 Artifact Store；数据库存元数据与 Provenance，不把二进制当唯一真相源。

## 入口面

```python
from drama_forge import Engine

engine = Engine(db_path="production.db")
story = engine.compile("examples/story_sample.json")
result = engine.run(story, candidate_count=2)
print(engine.inspect(result.timeline_artifact.id))
```

```bash
drama-forge compile|plan|run|status|inspect|validate|repair|doctor|version
```

## 相关文档

- [贡献指南](CONTRIBUTING.zh-CN.md)
- [路线图](ROADMAP.zh-CN.md)
- [打包与发布](PACKAGING.zh-CN.md)
- [架构决策记录](ADR.zh-CN.md)
- [LLM / Provider 指南](LLM_PROVIDERS.zh-CN.md)
