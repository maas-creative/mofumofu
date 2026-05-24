# mofumofu Implementation Plan

Last updated: 2026-05-24

This plan is the implementation order for the first mofumofu product baseline. It is intentionally sliced so each step has a clear dependency boundary, acceptance criteria, and verification path.

## Plan Rules

- Use `earendil-works/pi/packages/coding-agent` as the fork base, preserving required MIT notices.
- Do not expose legacy `pi`, `.pi/`, or `~/.pi/` in the mofumofu product surface after the migration layer is complete.
- Do not depend on SPECA backend, Claude Code, or Anthropic.
- Support hosted providers and local/open-model providers through the same provider contract.
- Treat security and generated-code security as release-gating.
- Store downloaded external schemas and OpenAPI artifacts durably.
- A slice is complete only when acceptance criteria pass and evidence is linked.

## Slice 0: Repository Scaffold

Goal: create the initial fork-derived implementation workspace.

Depends on:

- Current documentation baseline.

Deliverables:

- Imported fork base from `earendil-works/pi/packages/coding-agent` or a repository layout that can track it.
- Package manager config.
- TypeScript project config.
- Lint, format, test runner.
- Source directories for CLI, core runtime, schemas, providers, tools, audit, and MCP.
- `THIRD_PARTY_NOTICES.md` or equivalent upstream MIT notice preservation.
- Initial rename map from pi names/paths to mofumofu names/paths.

Acceptance criteria:

- `mofu --version` can be built or run in dev mode.
- Test command executes with at least one smoke test.
- Upstream license notice is present.
- Legacy product-surface names are either absent from user-facing paths or listed in the temporary migration inventory.

Verification:

- product-surface rename inventory check
- `rg "pi|\\.pi|~/.pi" src package.json packages` after implementation paths exist, with only documented internal migration exceptions allowed
- test runner smoke test

## Slice 1: Config, State, and Session Runtime

Goal: implement config precedence and durable session JSONL.

Depends on:

- Slice 0.
- [Data Schemas](data-schemas.md).

Deliverables:

- Machine config loader.
- Project config loader.
- Effective config explanation.
- Session JSONL writer and reader.
- Stop reason model.

Acceptance criteria:

- `mofu config get`, `mofu config set`, and `mofu config explain` work.
- Two projects share machine defaults.
- Session logs can be resumed from disk.

Verification:

- config precedence tests
- session resume fixture

## Slice 2: CLI Foundation

Goal: implement the stable CLI shell.

Depends on:

- Slice 1.
- [CLI Reference](cli-reference.md).

Deliverables:

- `mofu init`
- `mofu status`
- `mofu config`
- common `--json`, `--cwd`, `--verbose`, and exit-code handling

Acceptance criteria:

- `mofu init` creates `.mofumofu/` safely and idempotently.
- Human and JSON outputs are stable.
- Mutating commands report changed paths.

Verification:

- CLI fixture tests
- idempotent init test

## Slice 3: Provider Registry

Goal: support provider-neutral hosted and local/open-model execution.

Depends on:

- Slice 1.

Deliverables:

- Provider interface.
- OpenAI-compatible provider adapter.
- Provider capability schema and probe command.
- Local endpoint fixture for Ollama, LM Studio, and vLLM style APIs.

Acceptance criteria:

- `mofu provider list` and `mofu provider probe` work.
- Runtime branches on capability flags, not provider name.
- Local/open-model fixture runs without hosted API keys.

Verification:

- provider conformance tests
- mocked local endpoint test

## Slice 4: Tool Runtime and Control Plane

Goal: execute tools through typed contracts and policy checks.

Depends on:

- Slice 1.
- [Tool Contracts](tool-contracts.md).
- [Security Requirements](security-requirements.md).

Deliverables:

- Tool registry.
- Runtime input/output validation.
- Risk tier and side-effect model.
- Policy check hook.
- Tool output bounding and evidence hooks.

Acceptance criteria:

- Invalid tool input is rejected before execution.
- Risky tools can be denied or approval-gated.
- Tool calls are recorded in session JSONL.

Verification:

- policy allow/deny/approval tests
- output bound tests

## Slice 5: Spec Workflow and Trace Map

Goal: make `.mofumofu/specs/` the authority for implementation work.

Depends on:

- Slice 2.
- Slice 4.

Deliverables:

- `mofu spec init`, `new`, `status`, `approve`, and `active`.
- Trace map reader/writer.
- Trace reconciliation.
- Approval state.

Acceptance criteria:

- Agent can identify active spec before code edits.
- Unapproved specs are visible as gated.
- Trace reconciliation reports orphaned requirements and files.

Verification:

- spec lifecycle fixture
- trace reconciliation fixture

## Slice 6: Specification Artifact Cache

Goal: persist downloaded OpenAPI/schema artifacts.

Depends on:

- Slice 5.

Deliverables:

- `mofu artifact fetch`
- artifact metadata and hash writer
- normalization pipeline
- diff command
- trace link integration

Acceptance criteria:

- Downloaded artifacts are never only transient context.
- Changed external artifacts produce diff evidence.
- Generated code can link to artifact version.

Verification:

- OpenAPI fixture fetch, validate, re-fetch, and diff test

## Slice 7: Analysis Provider and Context Packs

Goal: build deterministic code context for model calls.

Depends on:

- Slice 5.

Deliverables:

- file search adapter
- symbol extraction MVP
- reference search MVP
- `mofu analyze`
- `mofu context pack`
- included/omitted reason model

Acceptance criteria:

- Context packs include specs, trace links, relevant files, and validation history.
- Token budget decisions are visible.
- Whole-symbol retrieval is preferred when available.

Verification:

- context-pack snapshot tests
- symbol/reference fixture

## Slice 8: Validation Oracle and Security Scanner MVP

Goal: normalize validation and security feedback.

Depends on:

- Slice 4.
- Slice 5.

Deliverables:

- validation result normalizer
- SAST scanner adapter
- secret scanner adapter
- dependency scanner adapter
- `mofu security scan`
- accepted-risk ledger

Acceptance criteria:

- Findings use a common schema.
- `MF-SR-*` and `GEN-SR-*` requirements can be linked to findings.
- Unresolved high or critical findings block completion unless accepted.

Verification:

- mixed scanner fixture
- accepted-risk expiry test

## Slice 9: Native SPECA-Class Audit

Goal: implement provider-neutral audit capability without SPECA backend.

Depends on:

- Slice 3.
- Slice 7.
- Slice 8.

Deliverables:

- property extraction
- pre-resolution checks
- proof attempt
- challenge pass
- review and finding ingestion
- `mofu audit`

Acceptance criteria:

- Real bug, false positive, and unresolved issue are represented distinctly.
- Audit works with hosted provider and degrades explicitly with local models.
- No Claude, Claude Code, Anthropic, or SPECA runtime dependency.

Verification:

- audit fixture with seeded bug
- provider capability degradation test

## Slice 10: Compaction and Practicality Ledgers

Goal: preserve autonomy across long-running sessions.

Depends on:

- Slice 1.
- Slice 7.

Deliverables:

- compaction handoff writer
- resume validator
- budget ledger
- context ledger
- fact ledger
- worktree ledger

Acceptance criteria:

- Resume detects changed worktree state.
- Budget and context exhaustion produce explicit stop reasons.
- Drift-prone facts can be marked stale.

Verification:

- compact/resume fixture
- budget exhaustion fixture
- dirty worktree fixture

## Slice 11: Gate Engine

Goal: prevent false completion claims.

Depends on:

- Slice 5.
- Slice 8.
- Slice 9.
- Slice 10.

Deliverables:

- `mofu gate status`
- `mofu gate explain`
- final-claim consistency checker
- gate integration with trace, validation, security, audit, budget, context, and worktree ledgers

Acceptance criteria:

- `PASS`, `PARTIAL`, `FAIL`, and `NOT VERIFIED` remain distinct.
- Final responses cannot claim done when gates fail.
- Gate output gives actionable blockers.

Verification:

- blocked final-claim fixture
- passing final-claim fixture

## Slice 12: MCP Server

Goal: expose mofumofu capabilities to external agents.

Depends on:

- Slice 4.
- Slice 11.

Deliverables:

- `mofu mcp serve --stdio`
- MCP tool registration for documented tool contracts
- MCP call logging
- MCP trust-boundary policy

Acceptance criteria:

- MCP clients can call spec, trace, artifact, audit, security, and gate tools.
- External MCP calls are logged and policy-checked.

Verification:

- MCP client smoke test
- deny/allow fixture for external calls

## Slice 13: Agent Runtime Integration

Goal: connect providers, tools, context, audit, validation, and gates into a coding-agent loop.

Depends on:

- Slice 3 through Slice 12.

Deliverables:

- session runtime facade
- model loop
- tool-call loop
- validation loop
- final response gate
- SDK/RPC boundary for future UI or integrations

Acceptance criteria:

- Agent can complete a small spec-driven code change end to end.
- Agent can stop safely when approval, budget, context, validation, or security blocks progress.
- Evidence is linked from final status.

Verification:

- end-to-end fixture repository
- provider-neutral run with hosted model
- local/open-model degraded run

## Release Gate for Baseline

Baseline release requires:

- All Slice 0-13 acceptance criteria pass.
- `MF-SR-*` and `GEN-SR-*` requirements are traced.
- No unaccepted critical or high security findings.
- Documentation and implementation trace reconciliation passes.
- Final status is generated through `mofu gate status`, not informal judgment.
