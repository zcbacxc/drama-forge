[![English](https://img.shields.io/badge/English-Roadmap-blue)](ROADMAP.md)
[![简体中文](https://img.shields.io/badge/简体中文-路线图-green)](ROADMAP.zh-CN.md)

# 路线图

> 单版本细节见 [CHANGELOG.md](../CHANGELOG.md)。本页只汇总已发布主题与近期待办。

## 规划原则

1. 只服务 **Core Engine** 定位 —— 不做 Studio、SaaS、Agent-as-Runtime。
2. 优先工程属性（可重复 / 可恢复 / 可局部修复 / 可追溯 / 可换 Provider），而不是一次性 Demo。
3. 用户可见能力与基础设施加固交替推进。
4. 九项核心工程验证全部通过前，**不得**宣称「生产可用 Core Engine」。

## 已发布

| 版本 | 主题 |
|------|------|
| 0.1.0 | 领域内核、编译器、执行运行时、能力路由、Mock + HTTP Provider、Artifact/Provenance、质量/修复、Stage F 能力、Timeline、SQLite 持久化、CLI、核心验证测试、CI + 发布工作流 |

## 近期计划

主题按工程风险排序，不是营销里程碑。

### 公开文档与打包

- 双语 `docs/` 套件（本批）
- 具备条件后的首个 PyPI Trusted Publishing 发布
- API 参考量上来后再考虑 mkdocs 站点

### 运行时深化

- 更强的脏传播与局部再生产路径
- 运维工具中的失败语义更完整
- Production Knowledge 注入 continuity 的路径加固

### 能力 / Provider

- 同一 OpenAI-compatible 适配器下接入更多端点
- 图像 / 能力契约加固与 live smoke 扩展
- 成本与用量记账进入执行元数据

### 质量

- continuity 与候选排序相关的更多 validator / evaluator
- 把 Issue 映射为最小图失效范围的 Repair Plan

## 明确不做

| 不属于 Drama Forge Core | 原因 |
|-------------------------|------|
| Studio / Canvas UI | 独立产品层 |
| SaaS 账号、计费、组织 | 独立产品层 |
| 把 Agent 当唯一生产 Runtime | 不得绕过 Graph / Contract / Checkpoint / Provenance |
| 以 Prompt 为核心资产的商店 | Prompt 是输入，不是生产模型 |
| 插件市场 | 能力扩展留在代码内或显式适配器 |

## 如何影响路线图

- 提 [Feature Request](https://github.com/zcbacxc/drama-forge/issues/new?template=feature_request.md)，说明它如何服务生产闭环
- 实现讨论请用 [Discussions](https://github.com/zcbacxc/drama-forge/discussions)
- 当前稳定核心见 [ARCHITECTURE.zh-CN.md](ARCHITECTURE.zh-CN.md)
