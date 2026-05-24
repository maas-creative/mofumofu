# mofumofu Security Requirements

Last updated: 2026-05-24

This document defines security requirements for two separate scopes:

1. mofumofu product security
2. security requirements for code generated or modified by mofumofu

These requirements are release-gating. A task is not complete when relevant security requirements are `FAIL`, `PARTIAL`, or `NOT VERIFIED`.

## Scope A: mofumofu Product Security

These requirements protect users, repositories, credentials, local machines, model connections, MCP servers, and session artifacts.

### MF-SR-001: Provider-Neutral Secret Handling

Requirement:
mofumofu must never persist API keys, OAuth tokens, local model secrets, repository credentials, or MCP credentials in session logs, trace maps, context packs, evidence bundles, or handoff summaries.

Acceptance criteria:

- Secrets are loaded from approved secret stores or environment variables.
- Logs and artifacts redact known secret patterns before persistence.
- `.mofumofu/` files never contain raw provider credentials.
- Secret redaction is tested against representative OpenAI, Anthropic, GitHub, npm, SSH, and cloud key formats.

Verification:

- secret-scan `.mofumofu/`, session logs, and evidence artifacts
- unit tests for redaction
- integration test with mocked provider credentials

### MF-SR-002: Tool Permission Control

Requirement:
mofumofu must classify every tool call by risk tier before execution and enforce policy before risky actions.

Risk tiers:

- safe read
- generated artifact write
- ordinary source edit
- spec/config/instruction edit
- destructive command
- credential/security-sensitive operation

Acceptance criteria:

- Risk tier is recorded for every tool call.
- High-risk actions require durable consent evidence unless policy explicitly allows them.
- Destructive commands and credential operations are denied by default.
- Policy decisions are auditable.

Verification:

- tests for destructive command blocking
- tests for `.env`, credential, and config path protection
- consent evidence inspection

### MF-SR-003: Agent Configuration Integrity

Requirement:
Model settings, MCP server definitions, tool permissions, hooks, prompts, skills, and instruction files must be treated as security-sensitive configuration.

Acceptance criteria:

- mofumofu detects changes to security-sensitive config before the next autonomous loop.
- Changed config is summarized and requires explicit acceptance when it increases risk.
- Config changes are linked to task/evidence IDs.
- Untrusted project config cannot silently override machine-level safety policy.

Verification:

- config diff tests
- policy precedence tests
- tampered MCP server definition tests

### MF-SR-004: MCP Server Trust Boundary

Requirement:
mofumofu must treat MCP servers as untrusted external capability providers unless explicitly marked trusted.

Acceptance criteria:

- MCP tool schemas, server command paths, environment variables, and network endpoints are recorded.
- New or changed MCP servers require review before they can execute write, shell, credential, or network actions.
- Tool outputs from MCP servers are treated as untrusted input.
- Prompt injection content from MCP outputs cannot change system policy.

Verification:

- malicious MCP output tests
- untrusted server registration tests
- prompt-injection regression tests

### MF-SR-005: Context and Evidence Data Minimization

Requirement:
mofumofu must minimize sensitive data entering model context and persisted evidence.

Acceptance criteria:

- Context packs include only task-relevant specs, code, test output, and evidence.
- Large artifacts are stored by path with summaries instead of pasted wholesale.
- Sensitive files require explicit allowlist before model exposure.
- ContextLedger shows sensitive or high-volume contributors.

Verification:

- context pack snapshot tests
- sensitive path allowlist tests
- artifact summary tests

### MF-SR-006: Compaction and Handoff Integrity

Requirement:
Compaction and handoff must not become an unaudited source of authority.

Acceptance criteria:

- Before compaction, mofumofu writes local handoff state.
- After compaction, mofumofu reloads task, trace, open questions, and gate state.
- Completion claims are blocked until relevant gates are rechecked.
- Handoff summaries cite evidence IDs for factual claims.

Verification:

- compaction resume tests
- gate recheck tests
- handoff evidence-link tests

### MF-SR-007: Session and Artifact Integrity

Requirement:
Session logs, trace maps, spec artifacts, context packs, and evidence bundles must be tamper-evident enough for local audit.

Acceptance criteria:

- Important artifacts include content hashes.
- Refreshed external specs are diffed against prior saved versions.
- Evidence artifacts reference the command/tool that created them.
- Trace entries link spec clauses, files, commands, and evidence.

Verification:

- artifact hash tests
- OpenAPI refresh diff tests
- trace/evidence consistency checks

### MF-SR-008: Network and External Fetch Control

Requirement:
Network access must be explicit, cached where possible, and reproducible.

Acceptance criteria:

- Downloaded OpenAPI/AsyncAPI/GraphQL/schema artifacts are saved under `.mofumofu/specs-artifacts/`.
- Fetch metadata includes source URL/path, time, hash, and requester.
- Deterministic verification uses cached artifacts unless refresh is requested.
- Network fetch failures do not silently fall back to stale assumptions.

Verification:

- spec artifact cache tests
- offline deterministic audit tests
- stale spec warning tests

## Scope B: Security Requirements for Generated Code

These requirements apply to code mofumofu creates or modifies. They are enforced by `NativeAudit`, `ValidationOracle`, and `GateEngine`.

### GEN-SR-001: Secure-by-Default Authentication and Authorization

Requirement:
Generated code must not introduce unauthenticated or unauthorized access to protected resources.

Acceptance criteria:

- New routes, commands, jobs, and APIs declare their authentication and authorization model.
- Access control checks are linked to requirement IDs or threat properties.
- Privilege escalation paths are reviewed for high-risk changes.

Verification:

- route/API authorization tests
- static route map inspection
- native audit property checks

### GEN-SR-002: Input Validation and Output Encoding

Requirement:
Generated code must validate untrusted input and encode or escape output according to context.

Acceptance criteria:

- Request bodies, query params, path params, file inputs, webhooks, and tool/MCP inputs have schemas or validators.
- Generated UI/server output avoids injection-prone string concatenation where framework-safe APIs exist.
- Validation failures are safe and observable.

Verification:

- schema validation tests
- injection-focused audit properties
- framework-specific lint/static checks

### GEN-SR-003: Secret and Credential Safety

Requirement:
Generated code must not hardcode secrets, log secrets, expose credentials in client bundles, or weaken existing secret handling.

Acceptance criteria:

- Secrets are read from approved runtime configuration.
- Client-side code cannot access server-only secrets.
- Logs redact credentials and tokens.
- Generated examples use placeholders, not real-looking keys.

Verification:

- secret scan
- client bundle/env exposure tests
- log redaction tests

### GEN-SR-004: Dependency and Supply-Chain Safety

Requirement:
Generated code must not add dependencies or scripts without a security and maintenance reason.

Acceptance criteria:

- New dependencies include rationale and source.
- Install scripts, postinstall hooks, and binary downloads are flagged.
- Lockfile changes are reviewed.
- Known vulnerable dependencies block completion unless risk is accepted.

Verification:

- dependency diff review
- vulnerability scan where available
- lockfile inspection

### GEN-SR-005: Safe File, Shell, and Process Handling

Requirement:
Generated code must avoid command injection, unsafe path traversal, and unsafe temporary-file handling.

Acceptance criteria:

- Shell execution uses argument arrays or safe APIs.
- User-controlled paths are normalized and constrained.
- Temporary files use safe OS APIs.
- File writes do not cross trust boundaries without checks.

Verification:

- static analysis
- path traversal tests
- command injection audit properties

### GEN-SR-006: Data Protection and Privacy

Requirement:
Generated code must protect sensitive data in storage, transit, logs, analytics, and model/tool calls.

Acceptance criteria:

- Sensitive fields are identified.
- Storage and transport protections are documented.
- Logs avoid PII/secrets unless explicitly approved and redacted.
- Model/tool calls do not receive sensitive data without allowlist and purpose.

Verification:

- data-flow review
- logging tests
- context/evidence inspection

### GEN-SR-007: Error Handling Without Information Leakage

Requirement:
Generated code must expose safe errors to users while preserving enough internal diagnostics for operators.

Acceptance criteria:

- User-facing errors do not include stack traces, secrets, SQL, filesystem paths, or internal URLs.
- Internal logs preserve trace IDs and enough diagnostic detail.
- Security-sensitive failures have rate-limited or structured logs.

Verification:

- error response tests
- log snapshot tests
- native audit checks

### GEN-SR-008: Security Regression Gates

Requirement:
mofumofu must not mark generated code complete until applicable security checks have been run or explicitly marked `NOT VERIFIED`.

Acceptance criteria:

- Trace map links generated code to relevant security requirements.
- `NativeAudit` generates security properties for relevant changes.
- `ValidationOracle` records tests/static checks/scans.
- `GateEngine` blocks unresolved high-severity findings.

Verification:

- gate tests
- trace completeness checks
- audit finding ingestion tests

## Required Security Artifacts

```text
.mofumofu/
  security/
    requirements.json
    threat-model.md
    policy.toml
    findings.jsonl
    accepted-risks.jsonl
  evidence/
    consent.jsonl
    security-checks/
```

## Status Vocabulary

Security requirement status must use:

- `PASS`
- `FAIL`
- `PARTIAL`
- `NOT VERIFIED`
- `ACCEPTED RISK`

`ACCEPTED RISK` requires:

- reason
- owner
- date
- expiry or review date
- affected requirement IDs
- evidence links

