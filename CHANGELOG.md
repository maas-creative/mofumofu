# Changelog

## 0.1.0 - 2026-05-24

Initial release candidate.

- Wraps the vendored pi coding-agent runtime as `mofu-agent` while exposing mofumofu product identity.
- Adds the Python `mofu` / `mofumofu` control-plane CLI.
- Implements provider registry, LM Studio/OpenAI-compatible local provider E2E, spec workflow, trace, context packs, validation normalization, native audit loop, security scanner, generated-code security E2E, gate engine, and MCP stdio tool contracts.
- Adds release-spec task gating under `.mofumofu/specs/product-release-baseline/tasks.md`.
- Verifies the product release baseline with unit tests, vendored pi build, security checks, dependency audit, and release gate status.
