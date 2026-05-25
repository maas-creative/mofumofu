# mofumofu Data Schemas

Last updated: 2026-05-24

This file defines the durable file contracts for `.mofumofu/`, machine config, and session state. Schemas should be implemented with TypeScript types and runtime validation, preferably TypeBox plus Ajv unless later implementation evidence chooses otherwise.

## Directory Layout

Project-local state:

```text
.mofumofu/
  config.toml
  policy.toml
  steering/
    product.md
    architecture.md
    security.md
  specs/
    <spec-id>/
      requirements.md
      design.md
      tasks.md
      trace-map.json
      context-pack.json
      operation-index.json
      findings.jsonl
      evidence/
        manifest.jsonl
      artifacts/
        <artifact-id>/
          original
          normalized.json
          metadata.json
          diffs/
            <timestamp>.json
      audit/
        properties.json
        proofs.jsonl
        challenges.jsonl
        reviews.jsonl
  security/
    accepted-risks.jsonl
  ledgers/
    budget.jsonl
    facts.jsonl
    worktree.json
    compaction-handoff.json
```

Machine-local config:

```text
~/.config/mofumofu/config.toml
~/.config/mofumofu/providers.toml
```

Machine-local session state:

```text
~/.local/state/mofumofu/sessions/<session-id>.jsonl
```

## Common Types

### Status

```json
{
  "enum": ["PASS", "PARTIAL", "FAIL", "NOT VERIFIED", "NOT IMPLEMENTED"]
}
```

### Severity

```json
{
  "enum": ["info", "low", "medium", "high", "critical"]
}
```

### EvidenceRef

```json
{
  "id": "ev_20260524_001",
  "kind": "command_output",
  "path": ".mofumofu/specs/auth/evidence/manifest.jsonl",
  "summary": "npm test passed",
  "hash": "sha256:...",
  "createdAt": "2026-05-24T12:00:00+09:00"
}
```

## config.toml

Purpose: project-local overrides. Machine defaults live in `~/.config/mofumofu/config.toml`.

```toml
version = 1

[model]
default_provider = "local"
default_model = "qwen3-coder-local"
analysis_model = "qwen3-coder-local"
audit_model = "hosted-strong"

[runtime]
max_tool_output_bytes = 200000
default_context_budget_tokens = 120000
allow_network = false

[spec]
active_spec = "example-feature"
require_approved_requirements = true
require_trace_for_completion = true
```

Required fields:

- `version`

Optional fields:

- `model.default_provider`
- `model.default_model`
- `model.analysis_model`
- `model.audit_model`
- `runtime.max_tool_output_bytes`
- `runtime.default_context_budget_tokens`
- `runtime.allow_network`
- `spec.active_spec`
- `spec.require_approved_requirements`
- `spec.require_trace_for_completion`

## providers.toml

Purpose: machine-local provider definitions. Secrets must be referenced by environment variable names, not stored directly.

```toml
version = 1

[[providers]]
id = "hosted-strong"
kind = "openai-compatible"
base_url = "https://api.example.com/v1"
api_key_env = "EXAMPLE_API_KEY"
default_model = "provider-default-coding-model"

[[providers]]
id = "local"
kind = "openai-compatible"
base_url = "http://127.0.0.1:11434/v1"
api_key_env = ""
default_model = "local-coding-model"
```

## provider-capabilities.json

Purpose: cached result of `mofu provider probe`.

```json
{
  "providerId": "local",
  "model": "local-coding-model",
  "probedAt": "2026-05-24T12:00:00+09:00",
  "capabilities": {
    "streaming": true,
    "toolCalling": false,
    "jsonMode": true,
    "structuredOutput": false,
    "vision": false,
    "embeddings": false,
    "contextWindowTokens": 32768,
    "maxOutputTokens": 4096
  },
  "limits": {
    "requestsPerMinute": null,
    "tokensPerMinute": null
  },
  "evidence": ["ev_provider_probe_001"]
}
```

## trace-map.json

Purpose: link specs to implementation, validation, evidence, findings, and risks.

```json
{
  "version": 1,
  "specId": "example-feature",
  "links": [
    {
      "id": "trace_001",
      "from": { "kind": "requirement", "id": "REQ-SPEC-001" },
      "to": { "kind": "file", "path": "src/spec-workflow.ts" },
      "relation": "implemented_by",
      "status": "PARTIAL",
      "rationale": "Spec directory creation starts here.",
      "evidence": ["ev_20260524_001"]
    }
  ],
  "orphans": {
    "requirements": [],
    "files": []
  }
}
```

Valid `kind` values:

- `requirement`
- `security_requirement`
- `file`
- `symbol`
- `test`
- `command`
- `artifact`
- `finding`
- `risk`
- `decision`

## context-pack.json

Purpose: deterministic context selected for a model call.

```json
{
  "version": 1,
  "specId": "example-feature",
  "createdAt": "2026-05-24T12:00:00+09:00",
  "goal": "Implement spec init command.",
  "budget": {
    "maxTokens": 120000,
    "estimatedTokens": 38200
  },
  "included": [
    {
      "path": "src/cli.ts",
      "reason": "CLI entry point",
      "selection": "whole_file",
      "hash": "sha256:..."
    }
  ],
  "omitted": [
    {
      "path": "docs/requirements.md",
      "reason": "Canonical requirements were already covered by the trace map."
    }
  ],
  "traceLinks": ["trace_001"]
}
```

## operation-index.json

Purpose: describe planned or completed operations in a spec.

```json
{
  "version": 1,
  "specId": "example-feature",
  "operations": [
    {
      "id": "op_001",
      "title": "Create CLI init command",
      "status": "PARTIAL",
      "requirements": ["REQ-SPEC-001"],
      "files": ["src/cli.ts"],
      "validations": ["cmd_test_cli_init"]
    }
  ]
}
```

## findings.jsonl

Purpose: normalized validation, audit, and security findings.

Each line:

```json
{
  "id": "finding_001",
  "source": "semgrep",
  "kind": "sast",
  "severity": "high",
  "title": "Command injection risk",
  "message": "Untrusted input reaches shell command.",
  "location": {
    "path": "src/run.ts",
    "startLine": 42,
    "endLine": 43
  },
  "requirements": ["GEN-SR-005"],
  "status": "open",
  "evidence": ["ev_scan_001"],
  "createdAt": "2026-05-24T12:00:00+09:00"
}
```

Valid finding status:

- `open`
- `fixed`
- `accepted`
- `false_positive`
- `unresolved`

## artifacts/<artifact-id>/metadata.json

Purpose: persistent downloaded specification artifact metadata.

```json
{
  "version": 1,
  "artifactId": "openapi_payments_20260524",
  "kind": "openapi",
  "source": {
    "url": "https://example.com/openapi.json",
    "method": "GET",
    "retrievedAt": "2026-05-24T12:00:00+09:00",
    "retrievedBy": "mofu artifact fetch"
  },
  "mediaType": "application/json",
  "originalPath": "original",
  "normalizedPath": "normalized.json",
  "hashes": {
    "original": "sha256:...",
    "normalized": "sha256:..."
  },
  "validation": {
    "status": "PASS",
    "tool": "@apidevtools/swagger-parser",
    "evidence": ["ev_openapi_validate_001"]
  },
  "traceLinks": ["trace_001"]
}
```

## audit/properties.json

Purpose: native audit properties extracted from specs and code.

```json
{
  "version": 1,
  "specId": "example-feature",
  "properties": [
    {
      "id": "prop_001",
      "source": "REQ-SPEC-001",
      "statement": "mofu init creates .mofumofu/ with required subdirectories.",
      "kind": "functional",
      "severity": "medium",
      "status": "unproved",
      "evidence": []
    }
  ]
}
```

Valid property status:

- `unproved`
- `proved`
- `disproved`
- `needs_human_review`
- `not_applicable`

## security/accepted-risks.jsonl

Purpose: explicit record of accepted security or quality risks.

Each line:

```json
{
  "id": "risk_001",
  "title": "Local model lacks tool calling",
  "severity": "medium",
  "scope": "REQ-PROVIDER-002",
  "reason": "MVP supports fallback text protocol for local model.",
  "acceptedBy": "user",
  "acceptedAt": "2026-05-24T12:00:00+09:00",
  "expiresAt": "2026-08-24T00:00:00+09:00",
  "linkedFindings": ["finding_001"]
}
```

## Session JSONL

Purpose: append-only durable session state.

Each line:

```json
{
  "id": "evt_001",
  "sessionId": "sess_20260524_001",
  "timestamp": "2026-05-24T12:00:00+09:00",
  "actor": "agent",
  "type": "tool_call",
  "payload": {
    "tool": "mofumofu.trace.update",
    "inputHash": "sha256:...",
    "outputHash": "sha256:..."
  },
  "traceLinks": ["trace_001"],
  "evidence": ["ev_tool_001"]
}
```

Valid event types:

- `user_message`
- `assistant_message`
- `tool_call`
- `tool_result`
- `validation`
- `audit`
- `compaction`
- `handoff`
- `final_claim`
- `error`

## ledgers/compaction-handoff.json

Purpose: durable resume state after compaction.

```json
{
  "version": 1,
  "sessionId": "sess_20260524_001",
  "createdAt": "2026-05-24T12:00:00+09:00",
  "goal": "Implement CLI init command.",
  "activeSpec": "example-feature",
  "openTasks": ["op_001"],
  "changedFiles": ["src/cli.ts"],
  "pendingValidations": ["npm test"],
  "knownRisks": ["risk_001"],
  "nextAction": "Run CLI fixture test.",
  "worktreeHash": "sha256:..."
}
```
