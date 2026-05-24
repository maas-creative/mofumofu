# mofu CLI Reference

Last updated: 2026-05-24

`mofu` is the daily-use CLI for mofumofu. `mofumofu` may exist as an alias, but implementation and documentation should prefer `mofu`.

## Global Contract

Command shape:

```text
mofu <command> [subcommand] [options]
```

Global options:

- `--cwd <path>`: run against a project directory.
- `--config <path>`: load an additional config file.
- `--json`: emit machine-readable JSON.
- `--no-color`: disable color.
- `--verbose`: include debug metadata.
- `--dry-run`: show intended writes without changing files, where supported.

Exit codes:

- `0`: success.
- `1`: generic failure.
- `2`: invalid CLI input.
- `3`: validation, gate, or policy failure.
- `4`: missing approval or permission.
- `5`: provider, MCP, or network failure.

Output rules:

- Human output must be concise and status-oriented.
- `--json` output must match documented schemas.
- Commands that mutate files must print changed paths.
- Commands that affect completion gates must print gate status.

## Commands

### mofu init

Create `.mofumofu/` in the current project.

```text
mofu init [--force] [--template <name>]
```

Writes:

- `.mofumofu/config.toml`
- `.mofumofu/policy.toml`
- `.mofumofu/steering/product.md`
- `.mofumofu/steering/architecture.md`
- `.mofumofu/steering/security.md`

Acceptance:

- Safe to run repeatedly.
- Does not overwrite user-edited files unless `--force` is provided.

### mofu status

Show project, active spec, provider, gate, and worktree state.

```text
mofu status [--json]
```

Required output:

- active spec id or `none`
- current provider and model
- config source summary
- gate status
- dirty worktree summary
- latest session id, if present

### mofu config

Inspect or update effective configuration.

```text
mofu config get <key> [--json]
mofu config set <key> <value> [--global|--project]
mofu config explain [--json]
```

Rules:

- `--global` writes to `~/.config/mofumofu/config.toml`.
- `--project` writes to `.mofumofu/config.toml`.
- Secrets must be configured as environment variable names, not literal secret values.

### mofu provider

Manage and probe providers.

```text
mofu provider list [--json]
mofu provider probe <provider-id> [--model <model>] [--json]
mofu provider default <provider-id> [--model <model>] [--global|--project]
```

Writes:

- `.mofumofu/provider-capabilities.json` for project-local probe evidence, or an equivalent cache path.

Acceptance:

- Probe reports capabilities and limitations without assuming provider identity.

### mofu spec

Manage spec-driven development state.

```text
mofu spec init
mofu spec new <spec-id> [--title <title>]
mofu spec status [<spec-id>] [--json]
mofu spec approve <spec-id> --stage requirements|design|tasks
mofu spec active <spec-id>
```

Writes:

- `.mofumofu/specs/<spec-id>/requirements.md`
- `.mofumofu/specs/<spec-id>/design.md`
- `.mofumofu/specs/<spec-id>/tasks.md`
- `.mofumofu/specs/<spec-id>/trace-map.json`

Acceptance:

- Approval state is explicit.
- Active spec is visible through `mofu status`.

### mofu artifact

Fetch, validate, list, and diff external specification artifacts.

```text
mofu artifact fetch <url> --kind openapi|asyncapi|graphql|json-schema [--spec <spec-id>]
mofu artifact list [--spec <spec-id>] [--json]
mofu artifact diff <artifact-id> [--against <artifact-id>] [--json]
```

Writes:

- `.mofumofu/specs/<spec-id>/artifacts/<artifact-id>/original`
- `.mofumofu/specs/<spec-id>/artifacts/<artifact-id>/normalized.json`
- `.mofumofu/specs/<spec-id>/artifacts/<artifact-id>/metadata.json`

Acceptance:

- Every fetch records source metadata and hashes.
- Re-fetch creates a diff record when content changes.

### mofu trace

Inspect and reconcile requirement-to-code trace links.

```text
mofu trace get [--spec <spec-id>] [--json]
mofu trace update --from <kind:id> --to <kind:id-or-path> --relation <relation> [--status <status>]
mofu trace reconcile [--spec <spec-id>] [--json]
```

Acceptance:

- Reconciliation reports orphaned requirements, orphaned files, stale links, and missing evidence.

### mofu analyze

Run local codebase analysis.

```text
mofu analyze symbols [--path <path>] [--json]
mofu analyze references <symbol> [--json]
mofu analyze graph [--json]
mofu analyze drift [--spec <spec-id>] [--json]
```

MVP behavior:

- Use fast local search and parsers first.
- Prefer deterministic output over model-only analysis.

### mofu context

Build and inspect model context packs.

```text
mofu context pack --spec <spec-id> [--goal <text>] [--json]
mofu context explain <context-pack-id> [--json]
mofu context trim <context-pack-id> --max-tokens <n> [--json]
```

Acceptance:

- Output records included files, omitted files, reasons, and token estimates.

### mofu audit

Run native provider-neutral spec/code audit.

```text
mofu audit properties --spec <spec-id> [--json]
mofu audit preresolve --spec <spec-id> [--json]
mofu audit prove --spec <spec-id> [--json]
mofu audit challenge --spec <spec-id> [--json]
mofu audit review --spec <spec-id> [--json]
mofu audit ingest <finding-file> --spec <spec-id> [--json]
```

Acceptance:

- Does not depend on SPECA backend, Claude Code, or Anthropic.
- Stores properties, proofs, challenges, reviews, and findings in `.mofumofu/`.

### mofu security

Run product and generated-code security checks.

```text
mofu security scan [--spec <spec-id>] [--json]
mofu security risks [--json]
mofu security accept-risk <finding-id> --reason <text> [--expires <date>]
```

MVP scanner classes:

- SAST
- secret scan
- dependency vulnerability scan
- optional container/IaC scan where applicable

### mofu gate

Evaluate completion gates.

```text
mofu gate status [--spec <spec-id>] [--json]
mofu gate explain [--spec <spec-id>] [--json]
```

Gate inputs:

- trace map
- validation findings
- audit findings
- security findings
- accepted risks
- worktree ledger
- budget ledger
- compaction handoff state

### mofu budget

Show budget and context consumption.

```text
mofu budget status [--json]
mofu budget explain [--json]
```

### mofu worktree

Show user, agent, generated, and untracked changes.

```text
mofu worktree status [--json]
```

### mofu mcp serve

Start the mofumofu MCP server over stdio.

```text
mofu mcp serve [--stdio]
```

Acceptance:

- Exposes only documented tools from [Tool Contracts](tool-contracts.md).
- Logs MCP calls as external tool interactions.
