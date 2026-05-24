# mofumofu Requirements

Last updated: 2026-05-24

This file defines the implementation requirements for mofumofu. Security requirements are defined separately in [Security Requirements](security-requirements.md) and are release-gating.

## Status Vocabulary

- `PASS`: implemented, verified, and linked to evidence.
- `PARTIAL`: implemented or specified only in part.
- `FAIL`: implemented behavior contradicts the requirement.
- `NOT VERIFIED`: implementation exists but evidence is missing.
- `NOT IMPLEMENTED`: no implementation exists.

## Identity and Scope

### REQ-ID-001 Product Identity

mofumofu must be built as a fork-derived product from `earendil-works/pi/packages/coding-agent`, while exposing its own product identity: `mofumofu`, `mofu`, `.mofumofu/`, `~/.config/mofumofu/`, and `~/.local/state/mofumofu/`.

Acceptance criteria:

- The fork preserves required upstream MIT license notices.
- No user-facing command, config path, session path, package name, or generated artifact requires legacy `pi`, `.pi/`, or `~/.pi/`.
- Any remaining upstream names are either removed, renamed, or isolated behind a temporary migration/internal compatibility layer.

Verification:

- Static search for legacy product-surface names in CLI, generated files, package names, docs intended for users, and config/session paths.
- CLI smoke test for `mofu --version`, `mofu init`, and `mofu status`.
- License notice check for fork-derived code.

### REQ-ID-002 Provider-Neutral Product

mofumofu must not require OpenAI, Anthropic, Claude Code, SPECA, or any single hosted provider to operate.

Acceptance criteria:

- At least one hosted provider and one local/open-model provider can be registered through the same provider interface.
- Missing provider features are represented as capability flags, not hidden assumptions.

Verification:

- Provider probe fixtures for hosted and local providers.
- Capability degradation tests for models without tool calling or large context windows.

## Configuration and State

### REQ-CFG-001 Shared Machine Model Configuration

All mofumofu sessions on the same machine must share model defaults from `~/.config/mofumofu/config.toml`.

Acceptance criteria:

- A new session reads the same default model and provider settings unless a project override is present.
- Configuration changes are reflected in later sessions without editing each project.

Verification:

- Start two isolated project sessions and confirm shared defaults.

### REQ-CFG-002 Project Override Precedence

Project-local settings in `.mofumofu/config.toml` may override machine defaults only for the current project.

Acceptance criteria:

- Effective config is explainable with source paths and precedence.
- Sensitive values are never written into project config by default.

Verification:

- `mofu config explain` fixture with global-only, project-only, and mixed config.

### REQ-SESSION-001 Durable Session Log

mofumofu must write a resumable JSONL session log for prompts, assistant actions, tool calls, observations, compaction events, validations, and final claims.

Acceptance criteria:

- Session entries are append-only.
- Each entry has an id, timestamp, type, actor, payload, and optional trace links.
- Sessions can be resumed after process restart.

Verification:

- Resume test from a recorded JSONL fixture.

### REQ-SESSION-002 Explicit Stop Reasons

Every agent stop must report a machine-readable stop reason.

Acceptance criteria:

- Stop reasons include at least: `done`, `needs_approval`, `blocked`, `budget_exceeded`, `context_limit`, `tool_denied`, `validation_failed`, and `error`.
- Final messages cannot claim completion when the stop reason is not `done`.

Verification:

- Stop reason fixtures for each terminal state.

## Providers and Models

### REQ-PROVIDER-001 Provider Registry

mofumofu must expose a provider registry with common generation, streaming, tool-call, embedding, and capability-probe contracts.

Acceptance criteria:

- Providers declare capabilities before a task starts.
- Runtime chooses strategies based on capabilities, not provider name.

Verification:

- Provider conformance test suite.

### REQ-PROVIDER-002 Local/Open-Model Support

mofumofu must support local/open-model runtimes through OpenAI-compatible endpoints where possible.

Acceptance criteria:

- Ollama, LM Studio, and vLLM style endpoints can be represented by the provider schema.
- The runtime can run without hosted API keys for tasks that fit local model capabilities.

Verification:

- Mock OpenAI-compatible local endpoint fixture.

## Tool Runtime and MCP

### REQ-TOOL-001 Typed Tool Runtime

All agent tools must have typed input, typed output, risk tier, side-effect declaration, and output-size bounds.

Acceptance criteria:

- Tool calls are validated before execution.
- Tool outputs include enough metadata for trace and evidence.

Verification:

- Invalid input rejection tests.
- Oversized output truncation and evidence-link tests.

### REQ-MCP-001 MCP Client Boundary

MCP servers must be treated as external trust boundaries.

Acceptance criteria:

- MCP tools are registered with risk tiers and permission policy.
- Networked MCP servers require explicit configuration.
- MCP tool calls are logged as external observations.

Verification:

- MCP fixture with allow, deny, and approval-required tools.

### REQ-MCP-002 mofumofu MCP Server

mofumofu must eventually expose its own MCP server for spec, trace, audit, and evidence operations.

Acceptance criteria:

- MCP server exports only typed, documented tools from [Tool Contracts](tool-contracts.md).
- The server can run over stdio for local agent integration.

Verification:

- MCP client conformance smoke test.

## Specification Workflow

### REQ-SPEC-001 Spec Authority Directory

Each project must use `.mofumofu/` as the durable specification authority directory.

Acceptance criteria:

- `.mofumofu/steering/` stores long-lived product and architecture steering.
- `.mofumofu/specs/<spec-id>/` stores requirements, design, tasks, trace, and evidence for a feature or change.
- Agent actions must identify the active spec before modifying code, unless the user explicitly requests exploratory work.

Verification:

- `mofu init` and `mofu spec new` directory fixture.

### REQ-SPEC-002 Spec Approval Gates

Spec-driven changes must move through explicit requirement, design, task, implementation, validation, and completion states.

Acceptance criteria:

- Code edits are blocked or marked exploratory when requirements are not approved.
- Completion cannot pass without trace and evidence reconciliation.

Verification:

- Gate tests for unapproved, partially approved, and fully approved specs.

### REQ-SPEC-003 Specification Artifact Cache

Downloaded OpenAPI, AsyncAPI, GraphQL, JSON Schema, and similar artifacts must be cached with metadata, hashes, diffs, and trace links.

Acceptance criteria:

- Artifact fetch records source URL, method, timestamp, content hash, normalized hash, media type, and retrieval tool.
- Updated artifacts produce a diff record.
- Generated types or client code link back to the cached artifact version.

Verification:

- OpenAPI fixture fetch and diff test.

## Trace, Analysis, and Context

### REQ-TRACE-001 Trace Map

mofumofu must maintain a trace map linking requirements, files, symbols, tests, commands, evidence, security findings, and accepted risks.

Acceptance criteria:

- Trace links have direction, rationale, status, and verification evidence.
- Orphaned code and orphaned requirements are reported.

Verification:

- Trace reconciliation fixture.

### REQ-ANALYSIS-001 Codebase Analysis Provider

mofumofu must provide repository analysis using fast local tools first.

Acceptance criteria:

- MVP includes file search, symbol extraction, dependency hints, and changed-file analysis.
- Later adapters may include LSP, tree-sitter, call graph, route graph, and graph-backed indexes.

Verification:

- Multi-language fixture with symbol and reference queries.

### REQ-CONTEXT-001 Deterministic Context Packs

Before asking a model to change code, mofumofu must build a deterministic context pack from specs, trace links, symbols, neighboring code, and validation history.

Acceptance criteria:

- Context packs list included and omitted files with reasons.
- Token budget decisions are visible.
- Whole-symbol inclusion is preferred over arbitrary snippets when feasible.

Verification:

- Snapshot tests for context-pack construction.

## Compaction and Memory

### REQ-COMPACT-001 Handoff State

Compaction must produce durable handoff state, not only conversational summaries.

Acceptance criteria:

- Handoff records current goal, active spec, open tasks, changed files, pending validations, evidence, risks, and next command.
- Resume validates the handoff against current worktree state.

Verification:

- Compact/resume fixture with changed worktree detection.

### REQ-COMPACT-002 Architectural Memory

mofumofu must preserve project-level architectural decisions separately from transient session summaries.

Acceptance criteria:

- Architectural memory entries include decision, rationale, scope, source, and supersession status.
- Memory entries can be cited into context packs.

Verification:

- Decision supersession fixture.

## Validation, Audit, and Gates

### REQ-VALIDATION-001 Validation Oracle

mofumofu must normalize test, typecheck, lint, format, SAST, dependency scan, secret scan, schema validation, and audit outputs into a common finding format.

Acceptance criteria:

- Findings have severity, source, location, requirement links, evidence links, and status.
- Validation failures block completion unless explicitly accepted as risk.

Verification:

- Mixed validation fixture from test runner, Semgrep-compatible scanner, secret scanner, and dependency scanner.

### REQ-AUDIT-001 Native SPECA-Class Audit

mofumofu must provide a native provider-neutral audit loop with comparable function to SPECA, without depending on SPECA backend, Claude, Claude Code, or Anthropic.

Acceptance criteria:

- Audit loop supports property extraction, pre-resolution checks, proof attempts, challenge review, human review, and finding ingestion.
- Audit properties and findings are stored in mofumofu schemas.
- Provider capability limits are explicit.

Verification:

- Audit fixture where one real bug, one false positive, and one unresolved issue are handled distinctly.

### REQ-GATE-001 Completion Gate

mofumofu must prevent false completion claims by checking trace, validation, security, audit, budget, and worktree state before final response.

Acceptance criteria:

- Final response includes completion state consistent with gate result.
- `PASS`, `PARTIAL`, `FAIL`, and `NOT VERIFIED` are not collapsed into vague success language.

Verification:

- Final-claim fixture with blocked and passing gates.

## Practicality Ledgers

### REQ-PRACTICAL-001 Budget and Context Ledgers

mofumofu must track token, cost, context-window, and validation budget consumption during a task.

Acceptance criteria:

- Agent can explain remaining budget and why context was trimmed.
- Budget exhaustion stops with `budget_exceeded`, not silent degradation.

Verification:

- Budget exhaustion fixture.

### REQ-PRACTICAL-002 Fact Ledger

Claims based on external facts, downloaded specs, or current ecosystem behavior must be recorded with source and freshness metadata.

Acceptance criteria:

- Drift-prone facts can be marked stale.
- Fact-check gates can block claims that require current verification.

Verification:

- Stale fact fixture.

### REQ-PRACTICAL-003 Worktree Ledger

mofumofu must distinguish user changes, agent changes, generated artifacts, and untracked files.

Acceptance criteria:

- Agent does not revert user changes unless explicitly asked.
- Final output reports touched files and verification state.

Verification:

- Dirty worktree fixture with overlapping changes.
