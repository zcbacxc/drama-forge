[![English](https://img.shields.io/badge/English-Security-blue)](SECURITY.md)
[![简体中文](https://img.shields.io/badge/简体中文-安全策略-green)](SECURITY.zh-CN.md)

# Security Policy

## Supported Versions

Only the latest release receives security updates.

| Version | Supported          |
|---------|--------------------|
| latest  | :white_check_mark: |
| < latest| :x:                |

## Reporting a Vulnerability

If you discover a security vulnerability, please **do not** open a public issue.

Instead, report it privately:

1. Go to the [Security Advisories](https://github.com/zcbacxc/drama-forge/security/advisories/new) tab
2. Click "Report a vulnerability"
3. Provide a clear description and steps to reproduce

You can also email: zcbacxc@users.noreply.github.com

### Response timeline

- **Acknowledgement**: within 48 hours
- **Initial assessment**: within 1 week
- **Fix or mitigation**: target 2 weeks for critical issues

## Scope

This policy covers the `drama-forge` core engine package (`src/drama_forge/`).

## Out of scope

- API key leakage in user configurations (user responsibility)
- Third-party provider / model API vulnerabilities and their generated content
- Issues in optional dependencies not installed by default

## License

This project is licensed under **AGPL-3.0-or-later**. See [LICENSE](LICENSE).
