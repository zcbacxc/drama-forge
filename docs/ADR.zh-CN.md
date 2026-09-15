[![English](https://img.shields.io/badge/English-ADR-blue)](ADR.md)
[![简体中文](https://img.shields.io/badge/简体中文-架构决策记录-green)](ADR.zh-CN.md)

# 架构决策记录

本文件记录 **Drama Forge** 的重要架构决策。每条 ADR 短小、自包含；一旦 Accepted 即不可改写——若决策变更，应新增 ADR 替换旧记录。

## 决策索引

| ID | 标题 | 状态 |
|----|------|------|
| [ADR-001](#adr-001-canonical-中间层) | Canonical 中间层 | Accepted |
| [ADR-002](#adr-002-provider-解耦与能力路由) | Provider 解耦与能力路由 | Accepted |
| [ADR-003](#adr-003-mock-优先与-dry-run-回退) | Mock 优先与 dry-run 回退 | Accepted |
| [ADR-004](#adr-004-持久化-sqlite-与本地-artifact-store) | 持久化：SQLite + 本地 Artifact Store | Accepted |
| [ADR-005](#adr-005-编程门面与-cli-作为主入口) | 编程门面与 CLI 作为主入口 | Accepted |
| [ADR-006](#adr-006-agpl-30-or-later-许可) | AGPL-3.0-or-later 许可 | Accepted |

---

## ADR-001: Canonical 中间层

**Status:** Accepted

### Context

LLM / 图像 / 视频 Provider 各自返回不同的 JSON 形状。若这些形状渗入核心模型，每次适配器变更都会变成领域变更。

### Decision

将所有 Provider 输出吸收到 Drama Forge 的 **Canonical Production Model**（Story / Asset / Spec / Graph / Artifact / Candidate）。Provider 专有载荷留在适配器之后。

### Consequences

- 换 Provider 时 Domain 与 Quality 层保持稳定
- 适配器承担规范化成本
- 未映射到 Canonical 字段或 Provenance 元数据的专有字段可能被丢弃

---

## ADR-002: Provider 解耦与能力路由

**Status:** Accepted

### Context

把生产图绑死在单一厂商会阻碍替换、测试与成本路由。

### Decision

- 生产图声明**能力**（`text_generation`、`image_generation` 等），而不是厂商 API
- Provider 按能力注册
- 可选 `provider_policy["by_capability"]` **在不改写生产图**的前提下钉选 Provider

### Consequences

- 同一生产图可跑在 Mock、OpenAI-compatible HTTP、DeepSeek、SiliconFlow、Agnes 等
- 路由策略是配置，不是 Spec 分叉
- 能力名成为契约面，重命名需谨慎

---

## ADR-003: Mock 优先与 dry-run 回退

**Status:** Accepted

### Context

CI 与首次运行不应依赖付费 API Key。真实调用是可选验证，不是默认路径。

### Decision

- 默认 Provider family 为 **mock**（确定性、离线）
- HTTP 适配器在缺 Key 或设置 `DRAMA_FORGE_PROVIDER_DRY_RUN` 时提供 **dry-run** 确定性回退
- Live smoke 测试需显式开启（`DRAMA_FORGE_LIVE_SMOKE=1`）

### Consequences

- 九项核心验证与单元测试可离线跑
- Mock 保真度必须足以覆盖图 / 运行时 / 质量逻辑
- Live 行为差异被限制在适配器测试内

---

## ADR-004: 持久化：SQLite + 本地 Artifact Store

**Status:** Accepted

### Context

Core Engine 需要可恢复历史与 Provenance，但不应强制分布式数据库。

### Decision

- 可选 SQLite（`db_path`）保存生产对象、候选、事件、质量结果、Knowledge
- 二进制在本地 Artifact Store；库内存元数据、指纹与 Provenance 引用
- Schema 带版本（当前 v2）并提供迁移

### Consequences

- 零运维的本地可恢复、可检视
- 不是多租户 SaaS 存储；这明确不在范围内
- 未来远程存储可替换 repository 层而不改 Domain

---

## ADR-005: 编程门面与 CLI 作为主入口

**Status:** Accepted

### Context

产品化引擎需要可嵌入 API 与验证 CLI。HTTP 服务属于另一条产品边界。

### Decision

主入口为：

- `drama_forge.Engine`（Python 门面）
- `drama-forge` 控制台脚本 / `python -m drama_forge.cli.main`

Core Engine 范围内没有一等 HTTP API。

### Consequences

- 嵌入方与测试走同一条路径
- Studio / SaaS 层（若有）在本仓库之外
- CLI 是验证面，不是完整产品 UI

---

## ADR-006: AGPL-3.0-or-later 许可

**Status:** Accepted

### Context

网络 copyleft 在有人提供托管服务时保护引擎，同时仍是 OSI 批准协议。

### Decision

- 协议：**AGPL-3.0-or-later**（SPDX；不用已废弃的 `AGPL-3.0`）
- `pyproject.toml` 使用 PEP 639 字符串形式；不加 license trove classifier
- `src/drama_forge/` 下源文件带 SPDX 头

### Consequences

- 下游闭源商业分叉需自行做合规评估
- 第三方生成内容的授权由最终用户自负

---

## 新 ADR 模板

```markdown
## ADR-NNN: 短标题

**Status:** Proposed | Accepted | Superseded by ADR-MMM

### Context
什么力量迫使决策？

### Decision
选择了什么？

### Consequences
什么变容易 / 变困难？
```

1. 取下一个编号
2. 在下方增加章节
3. 在决策索引中追加一行
4. 记录必须基于本仓库真实代码，不得虚构架构
