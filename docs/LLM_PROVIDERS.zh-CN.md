[![English](https://img.shields.io/badge/English-LLM_Providers-blue)](LLM_PROVIDERS.md)
[![简体中文](https://img.shields.io/badge/简体中文-LLM_Providers-green)](LLM_PROVIDERS.zh-CN.md)

# LLM / Provider 指南

Drama Forge 通过**能力面**访问 Provider，而不是把生产图绑在具体厂商 API 上。本目录说明各后端如何配置。

| 指南 | 能力重点 | 说明 |
|------|----------|------|
| [Mock（默认）](#mock默认) | 全部 | 离线、确定性、零配置 |
| [OpenAI-compatible](llm-providers/openai-compatible.zh-CN.md) | 文本 | 通用 HTTP chat completions |
| [DeepSeek](llm-providers/deepseek.zh-CN.md) | 文本 | OpenAI-compatible 预设（`chat/completions`） |
| [SiliconFlow](llm-providers/siliconflow.zh-CN.md) | 图像 | `/v1/images/generations` |
| [Agnes](llm-providers/agnes.zh-CN.md) | 图像 + 视频 | 网关图像 + `POST /v1/videos` |

## Mock（默认）

```bash
# 不设置 DRAMA_FORGE_PROVIDER，或：
export DRAMA_FORGE_PROVIDER=mock
```

无密钥、无网络。适合测试、CI，以及调试图 / 运行时逻辑。

## 选择 Provider family

```bash
export DRAMA_FORGE_PROVIDER=deepseek
export DRAMA_FORGE_DEEPSEEK_API_KEY=sk-...

# 文本 + 图像生产预设
export DRAMA_FORGE_PROVIDER=production
export DRAMA_FORGE_DEEPSEEK_API_KEY=sk-...
export DRAMA_FORGE_SILICONFLOW_API_KEY=sk-...

# a+b 组合 family
export DRAMA_FORGE_PROVIDER=deepseek+siliconflow
```

### 离线安全

```bash
export DRAMA_FORGE_PROVIDER_DRY_RUN=1
```

开启 dry-run 或缺少凭据时，HTTP 适配器回退为确定性离线结果。

### 按能力钉选（不改生产图）

```python
policy = {
    "strategy": "balanced",
    "by_capability": {
        "text_generation": {"provider_id": "deepseek"},
        "image_generation": {"provider_id": "siliconflow-image"},
    },
}
result = engine.run(story, provider_policy=policy)
```

## 配置位置

优先级（从高到低）：

1. 进程环境变量（`DRAMA_FORGE_*`）
2. 项目 `.env`
3. 用户级 `~/.drama-forge/.env`（首次运行从 `.env.example` 自动创建）

模板见仓库根目录 `.env.example`。故事内容**不在**这里配置——使用 story JSON / Manifest。

## 相关

- [架构 — 能力与 Provider](ARCHITECTURE.zh-CN.md#能力与-provider)
- [贡献指南](CONTRIBUTING.zh-CN.md)
