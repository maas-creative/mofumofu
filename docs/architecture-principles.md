# mofumofu Architecture Principles

Last updated: 2026-05-24

## Core Runtime

mofumofu should be organized around a compact agent runtime with these responsibilities:

1. Session orchestration
   - interactive terminal sessions
   - non-interactive print/JSON mode
   - RPC/SDK mode for embedding
   - resumable session event log

2. Tool execution
   - typed read/write/edit/shell tools
   - bounded output by default
   - concurrent independent tool calls
   - clear permission policy
   - reproducible command transcripts

3. Context management
   - provider-native compaction when a model provider supports it
   - local summarization and state snapshots for providers without native compaction
   - explicit handoff summaries before compaction-sensitive phases
   - durable workspace state under `.mofumofu/state/`
   - context-file discovery with size limits and targeted loading

4. Shared machine configuration
   - one machine-local config file such as `~/.config/mofumofu/config.toml`
   - optional project-local overrides under `.mofumofu/config.toml`
   - deterministic precedence: CLI flag, environment variable, project override, machine config, built-in default
   - model settings shared by all sessions on the same machine unless explicitly overridden

## Suggested Machine Config Shape

```toml
[model]
provider = "openai"
model = "provider-default-coding-model"
reasoning_effort = "high"
compaction = "server"
compaction_threshold = 0.75

[fallback]
models = ["anthropic/provider-coding-model", "ollama/local-coding-model", "lmstudio/local-coding-model"]

[providers.ollama]
base_url = "http://localhost:11434"

[providers.lmstudio]
base_url = "http://localhost:1234/v1"

[budget]
daily_usd = 50
per_task_usd = 10

[tools]
default = ["read", "write", "edit", "bash"]
```

## Spec-Code Alignment Loop

Every implementation task should run through a small closed loop:

1. Discover authority
   Identify source-of-truth specs, task files, acceptance criteria, and scope documents.

2. Build a trace map
   Link spec clauses to files, tests, commands, and expected evidence.

3. Edit code
   Keep changes scoped to the trace map.

4. Verify
   Run tests and checks that correspond to the spec clauses, not only generic build checks.

5. Reconcile
   Update trace state with `PASS`, `FAIL`, `PARTIAL`, or `NOT VERIFIED`.

6. Report
   Final answers must distinguish implemented behavior from verified behavior.

## Native Spec Audit

mofumofu must provide a native provider-neutral audit engine with SPECA-class behavior. It should run on hosted or open-weight models without depending on the SPECA backend:

1. Property generation
   Derive typed properties from authority specs, threat models, acceptance criteria, and trust boundaries.

2. Code pre-resolution
   Use deterministic local analyzers first: ripgrep, language servers, tree-sitter, dependency graphs, call graphs, and test maps.

3. Proof attempt
   Ask the configured model to prove each property against bounded code context and require structured evidence references.

4. Adversarial review
   Run an independent challenge pass, preferably with a different model/provider when configured.

5. Verdict calibration
   Emit `CONFIRMED`, `DISPUTED`, `FALSE_POSITIVE`, `INSUFFICIENT_EVIDENCE`, or `OUT_OF_SCOPE`, then map those verdicts into mofumofu gate status.

For open-weight models, the backend should use stricter context bounding, deterministic retrieval, schema validation, and multi-pass review because the model may be weaker than hosted frontier models.

## Implementation Slices

1. Bootstrap
   Create CLI skeleton, config loading, session event log, and basic read/write/edit/bash tools.

2. Machine model settings
   Implement shared config read/write commands and prove settings are reused across separate sessions.

3. Context and compaction
   Add provider-aware compaction support and durable handoff/state files.

4. Spec authority
   Add source-of-truth discovery, trace map schema, and completion-state vocabulary.

5. Native audit backend
   Add provider-neutral property generation, code pre-resolution, proof attempts, adversarial review, and verdict ingestion.

6. Verification gates
   Add task completion rules that require spec trace reconciliation before success claims.
