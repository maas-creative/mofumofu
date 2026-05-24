# mofumofu Tool Contracts

Last updated: 2026-05-24

This file defines the internal agent tools and future MCP tool surface. Tools must be typed, validated at runtime, logged to the session JSONL, and governed by policy.

## Common Tool Contract

Every tool has:

- `name`: stable tool id.
- `risk`: `read`, `write`, `execute`, `network`, or `external`.
- `sideEffects`: list of possible file, process, network, or state changes.
- `inputSchema`: runtime-validated schema.
- `outputSchema`: runtime-validated schema.
- `evidence`: whether the tool must create an evidence record.
- `traceable`: whether output can link to requirements or findings.

Common output envelope:

```json
{
  "ok": true,
  "tool": "mofumofu.trace.get",
  "summary": "Loaded 12 trace links.",
  "data": {},
  "evidence": ["ev_001"],
  "warnings": []
}
```

Error output envelope:

```json
{
  "ok": false,
  "tool": "mofumofu.trace.get",
  "error": {
    "code": "TRACE_NOT_FOUND",
    "message": "No trace map exists for spec example-feature."
  },
  "evidence": [],
  "warnings": []
}
```

## Spec Tools

### mofumofu.spec.discover

Risk: `read`

Input:

```json
{ "cwd": "/absolute/project/path" }
```

Output:

```json
{
  "initialized": true,
  "activeSpec": "example-feature",
  "specs": ["example-feature"],
  "steeringFiles": ["product.md", "architecture.md", "security.md"]
}
```

### mofumofu.spec.create

Risk: `write`

Input:

```json
{
  "cwd": "/absolute/project/path",
  "specId": "example-feature",
  "title": "Example feature"
}
```

Output:

```json
{
  "specId": "example-feature",
  "createdPaths": [
    ".mofumofu/specs/example-feature/requirements.md",
    ".mofumofu/specs/example-feature/design.md",
    ".mofumofu/specs/example-feature/tasks.md"
  ]
}
```

### mofumofu.spec.approve

Risk: `write`

Input:

```json
{
  "specId": "example-feature",
  "stage": "requirements",
  "approvedBy": "user"
}
```

Output:

```json
{
  "specId": "example-feature",
  "stage": "requirements",
  "status": "approved"
}
```

## Artifact Tools

### mofumofu.artifact.fetch

Risk: `network`

Input:

```json
{
  "specId": "example-feature",
  "url": "https://example.com/openapi.json",
  "kind": "openapi"
}
```

Output:

```json
{
  "artifactId": "openapi_example_20260524",
  "metadataPath": ".mofumofu/specs/example-feature/artifacts/openapi_example_20260524/metadata.json",
  "hashes": {
    "original": "sha256:...",
    "normalized": "sha256:..."
  },
  "validationStatus": "PASS"
}
```

### mofumofu.artifact.diff

Risk: `read`

Input:

```json
{
  "artifactId": "openapi_example_20260524",
  "against": "openapi_example_20260523"
}
```

Output:

```json
{
  "changed": true,
  "breakingChanges": 1,
  "nonBreakingChanges": 4,
  "diffPath": ".mofumofu/specs/example-feature/artifacts/openapi_example_20260524/diffs/20260524.json"
}
```

## Trace Tools

### mofumofu.trace.get

Risk: `read`

Input:

```json
{ "specId": "example-feature" }
```

Output:

```json
{
  "specId": "example-feature",
  "links": [],
  "orphans": {
    "requirements": [],
    "files": []
  }
}
```

### mofumofu.trace.update

Risk: `write`

Input:

```json
{
  "specId": "example-feature",
  "from": { "kind": "requirement", "id": "REQ-SPEC-001" },
  "to": { "kind": "file", "path": "src/spec-workflow.ts" },
  "relation": "implemented_by",
  "status": "PARTIAL",
  "rationale": "Creates spec directory."
}
```

Output:

```json
{ "traceId": "trace_001", "status": "PARTIAL" }
```

### mofumofu.trace.reconcile

Risk: `read`

Input:

```json
{ "specId": "example-feature" }
```

Output:

```json
{
  "status": "PARTIAL",
  "missingEvidence": [],
  "orphanRequirements": [],
  "orphanFiles": [],
  "staleLinks": []
}
```

## Analysis Tools

### mofumofu.analyze.symbols

Risk: `read`

Input:

```json
{
  "cwd": "/absolute/project/path",
  "paths": ["src"],
  "languageHints": ["typescript"]
}
```

Output:

```json
{
  "symbols": [
    {
      "name": "createSpec",
      "kind": "function",
      "path": "src/spec-workflow.ts",
      "startLine": 12,
      "endLine": 44
    }
  ]
}
```

### mofumofu.analyze.references

Risk: `read`

Input:

```json
{ "symbol": "createSpec", "paths": ["src"] }
```

Output:

```json
{
  "references": [
    {
      "path": "src/cli.ts",
      "line": 30,
      "preview": "await createSpec(...)"
    }
  ]
}
```

### mofumofu.analyze.graph

Risk: `read`

Input:

```json
{ "cwd": "/absolute/project/path", "scope": "changed-files" }
```

Output:

```json
{
  "nodes": [],
  "edges": [],
  "limitations": ["call graph unavailable for this language"]
}
```

## Context Tools

### mofumofu.context.build

Risk: `read`

Input:

```json
{
  "specId": "example-feature",
  "goal": "Implement mofu init.",
  "maxTokens": 120000
}
```

Output:

```json
{
  "contextPackId": "ctx_001",
  "path": ".mofumofu/specs/example-feature/context-pack.json",
  "estimatedTokens": 38200,
  "includedCount": 12,
  "omittedCount": 7
}
```

## Native Audit Tools

### mofumofu.audit.properties

Risk: `read`

Input:

```json
{ "specId": "example-feature" }
```

Output:

```json
{
  "propertyCount": 8,
  "path": ".mofumofu/specs/example-feature/audit/properties.json"
}
```

### mofumofu.audit.preresolve

Risk: `read`

Input:

```json
{ "specId": "example-feature" }
```

Output:

```json
{
  "resolvedWithoutModel": 2,
  "requiresProof": 5,
  "needsHumanReview": 1
}
```

### mofumofu.audit.prove

Risk: `read`

Input:

```json
{
  "specId": "example-feature",
  "propertyIds": ["prop_001"]
}
```

Output:

```json
{
  "proved": ["prop_001"],
  "disproved": [],
  "unresolved": []
}
```

### mofumofu.audit.challenge

Risk: `read`

Input:

```json
{ "specId": "example-feature" }
```

Output:

```json
{
  "challenged": 3,
  "newFindings": ["finding_001"]
}
```

### mofumofu.audit.review

Risk: `write`

Input:

```json
{
  "specId": "example-feature",
  "findingId": "finding_001",
  "decision": "accepted",
  "reason": "Reproduced with fixture."
}
```

Output:

```json
{ "findingId": "finding_001", "status": "accepted" }
```

### mofumofu.audit.ingest

Risk: `write`

Input:

```json
{
  "specId": "example-feature",
  "findings": [
    {
      "source": "external-audit",
      "severity": "high",
      "title": "Missing auth check"
    }
  ]
}
```

Output:

```json
{ "ingested": 1, "findingIds": ["finding_002"] }
```

## Validation and Security Tools

### mofumofu.security.scan

Risk: `execute`

Input:

```json
{
  "specId": "example-feature",
  "scanners": ["sast", "secrets", "dependencies"]
}
```

Output:

```json
{
  "status": "FAIL",
  "findingIds": ["finding_001"],
  "evidence": ["ev_security_scan_001"]
}
```

### mofumofu.validation.normalize

Risk: `read`

Input:

```json
{
  "source": "npm-test",
  "rawPath": ".mofumofu/tmp/test-output.txt"
}
```

Output:

```json
{
  "status": "PASS",
  "findings": [],
  "evidence": ["ev_test_001"]
}
```

## Gate and Policy Tools

### mofumofu.gate.status

Risk: `read`

Input:

```json
{ "specId": "example-feature" }
```

Output:

```json
{
  "status": "PARTIAL",
  "blockingReasons": [
    "REQ-SPEC-001 has no passing validation evidence."
  ],
  "canClaimDone": false
}
```

### mofumofu.policy.checkToolCall

Risk: `read`

Input:

```json
{
  "tool": "shell.exec",
  "risk": "execute",
  "command": "npm test"
}
```

Output:

```json
{
  "decision": "allow",
  "reason": "Read-only validation command in project directory.",
  "requiresUserApproval": false
}
```

Valid decisions:

- `allow`
- `deny`
- `require_approval`

### mofumofu.evidence.add

Risk: `write`

Input:

```json
{
  "specId": "example-feature",
  "kind": "command_output",
  "summary": "npm test passed",
  "path": ".mofumofu/specs/example-feature/evidence/test-output.txt"
}
```

Output:

```json
{
  "evidenceId": "ev_001",
  "manifestPath": ".mofumofu/specs/example-feature/evidence/manifest.jsonl"
}
```
