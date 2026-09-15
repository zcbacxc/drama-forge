[![English](https://img.shields.io/badge/English-Security-blue)](SECURITY.md)
[![简体中文](https://img.shields.io/badge/简体中文-安全策略-green)](SECURITY.zh-CN.md)

# 安全策略

## 受支持的版本

仅最新发布版本接收安全更新。

| 版本 | 是否支持 |
|------|----------|
| latest | ✅ |
| < latest | ❌ |

## 报告漏洞

如果你发现了安全漏洞，请**不要**公开提交 Issue。

请通过私密渠道报告：

1. 前往 [Security Advisories](https://github.com/zcbacxc/drama-forge/security/advisories/new) 页面
2. 点击 "Report a vulnerability"
3. 提供清晰的描述与复现步骤

你也可以发送邮件至：zcbacxc@users.noreply.github.com

### 响应时间线

- **确认收悉**：48 小时内
- **初步评估**：1 周内
- **修复或缓解**：关键问题目标 2 周

## 适用范围

本策略覆盖 `drama-forge` 核心引擎包（`src/drama_forge/`）。

## 不适用范围

- 用户配置中的 API 密钥泄露（用户责任）
- 第三方 Provider / 模型 API 的漏洞及其生成内容
- 非默认安装的可选依赖中的问题

## 开源协议

本项目采用 **AGPL-3.0-or-later**。详见 [LICENSE](LICENSE)。
