# mofumofu Specification Index

Last updated: 2026-05-24

This is the canonical map for the current mofumofu specification set. Use this file first when deciding what to implement or validate.

## Status

Current state: `IMPLEMENTATION SPEC BASELINE`

The repository now contains a canonical implementation specification set. It is ready to start Slice 0 implementation, but no product code is implemented yet.

## Source-of-Truth Order

1. [Product Philosophy](product-philosophy.md)
   Defines product identity, non-goals, provider-neutral policy, SPECA-as-benchmark only, and the core belief that spec-code-evidence alignment is the product's value.

2. [Security Requirements](security-requirements.md)
   Defines release-gating security requirements for the mofumofu product and generated code.

3. [Architecture Principles](architecture-principles.md)
   Defines runtime responsibilities, config policy, spec-code loop, native audit, and high-level slices.

4. [Requirements](requirements.md)
   Defines stable `REQ-*` product requirements for runtime, provider, spec workflow, trace, audit, validation, gates, and practical operation.

5. [Data Schemas](data-schemas.md)
   Defines machine config, project state, session logs, trace maps, artifact cache, audit records, findings, and ledgers.

6. [CLI Reference](cli-reference.md)
   Defines the `mofu` CLI contract, command outputs, mutating behavior, and exit codes.

7. [Tool Contracts](tool-contracts.md)
   Defines internal agent tools and future MCP tool contracts.

8. [Implementation Plan](implementation-plan.md)
   Defines implementation slices, dependencies, acceptance criteria, and verification approach.

## Reference Documents

These documents are design inputs, not higher authority than the source-of-truth set above.

- [Implementation Research](implementation-research.md)
- [Fork Methodology](pi-customization-methodology.md)
- [Research Basis](research-basis.md)
- [Technology Candidates](technology-candidates.md)
- [Coding-Agent Pain Points](competitor-pain-points.md)
- [Implementation Readiness Research](implementation-readiness-research.md)

## Stable Product Decisions

- Product name: `mofumofu`
- CLI command: `mofu` or `mofumofu`, with `mofu` preferred for daily use.
- Project state directory: `.mofumofu/`
- Machine config: `~/.config/mofumofu/config.toml`
- Session state: `~/.local/state/mofumofu/sessions/`
- Provider policy: provider-neutral, with hosted and local/open-weight models supported.
- SPECA policy: benchmark only, not a runtime dependency.
- pi policy: fork base; rename and harden the product surface to `mofumofu`, `mofu`, `.mofumofu/`, and mofumofu config/session paths.
- Completion policy: final claims require trace-to-evidence reconciliation.
- Security policy: product security and generated-code security are release-gating.

## Required Core Subsystems

1. `ProviderRuntime`
   Provider registry, local/open model support, capability declarations, fallback/degrade behavior.

2. `SessionRuntime`
   JSONL event log, resumable sessions, branch/fork/import later, stop reasons.

3. `ToolRuntime`
   Typed read/write/edit/search/shell tools, MCP bridge, bounded outputs, permission policy.

4. `SpecWorkflow`
   `.mofumofu/steering`, `.mofumofu/specs`, approvals, requirements/design/tasks lifecycle.

5. `TraceMap`
   Links spec clauses to files, tests, commands, artifacts, audit findings, and status.

6. `AnalysisProvider`
   ripgrep, tree-sitter, LSP, dependency graph, route graph, call graph, and future graph-backed indexes.

7. `ContextPackBuilder`
   Deterministic whole-symbol retrieval and token-bounded model context packs.

8. `SpecArtifactCache`
   Persistent OpenAPI/AsyncAPI/GraphQL/schema artifact storage with metadata, hashes, diffs, and trace links.

9. `ValidationOracle`
   Normalized test, typecheck, lint, SAST, dependency scan, secret scan, schema, and audit feedback.

10. `NativeAudit`
   Provider-neutral property generation, pre-resolution, proof attempt, challenge, review, and finding ingestion.

11. `ControlPlane`
   Risk-tier tool policy, consent evidence, config attack-surface checks, stop conditions.

12. `PracticalityLedgers`
   Budget, context, facts, compaction state, stop reasons, and worktree state.

13. `GateEngine`
   Completion gates for trace, verification, security, audit, and accepted risk.

## Current Gaps Before Product Completion

- Product code has not been scaffolded.
- Runtime schemas are specified but not yet enforced by code.
- CLI contract is specified but not yet implemented.
- Tool contracts are specified but not yet registered in a runtime.
- Security scanners and native audit loop are specified but not yet integrated.
- Provider capability degradation is specified but not yet proven against real providers.
- End-to-end fixtures are specified in the implementation plan but not yet created.

Resolved in this specification baseline:

- stable `REQ-*` product requirements
- `.mofumofu/` schema baseline
- CLI command reference
- internal tool and MCP-facing contracts
- native audit property/finding shape
- trace, evidence, artifact, and ledger schemas
- MECE implementation slices with acceptance criteria

## Next Implementation Step

Start [Implementation Plan](implementation-plan.md) Slice 0: Repository Scaffold.

## Consistency Check

Current result: `PASS FOR DOCUMENTATION BASELINE`

The canonical documents are internally consistent:

- provider-neutral policy is consistent across the set
- SPECA is no longer a backend dependency
- pi is the fork base, while pi naming is excluded from the mofumofu product surface
- security is now separated into product security and generated-code security
- downloaded OpenAPI/schema artifacts are captured as durable specs
- implementation order maps to requirements, schemas, CLI, tools, and gates

Remaining issue:

This is a specification baseline, not an implementation. Product readiness remains blocked until the implementation slices are completed and verified.
