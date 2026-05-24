# mofumofu Product Philosophy

Last updated: 2026-05-24

## Goal

mofumofu is a high-performance coding agent for long-running software work where the primary measure of quality is not how much code it writes, but how reliably it keeps implementation, specifications, and verification evidence aligned.

The product should be fork-derived from `earendil-works/pi`'s coding agent: a small, extensible terminal-first harness with model/provider flexibility, session continuity, context files, skills, extensions, prompt templates, and programmatic modes. mofumofu's differentiation is to make spec-code consistency a first-class runtime loop rather than an after-the-fact review step.

## Product Beliefs

1. Specifications are executable authority.
   The agent must treat requirements, design notes, acceptance criteria, threat models, and bug bounty scope files as active constraints. A task is not complete until the relevant spec claims, code changes, and verification artifacts agree.

2. Autonomy requires memory with boundaries.
   Long work should survive context pressure through native model compaction where available, plus explicit workspace state files that record current goals, open questions, file ownership, completed checks, and unresolved risks. Compaction should preserve direction; state files should preserve auditability.

3. The agent should prefer proof over confidence.
   Claims such as "implemented", "fixed", "compatible", or "safe" must point to concrete evidence: tests, traces, diffs, screenshots, generated reports, or a declared unverified status.

4. Bug auditing belongs inside the development loop.
   mofumofu must provide SPECA-class specification-driven bug and security auditing natively, without depending on the SPECA backend or Claude. The product should match the useful behavior: derive properties from specs, map them to code, attempt proofs, challenge assumptions, review findings, and feed results into release gates.

5. Model choice is an environment-level concern.
   Model configuration must be shared by every mofumofu session on the same machine. Individual project sessions may request constraints, but the active provider/model defaults, reasoning profile, budget policy, and fallback chain should come from one machine-local configuration authority. The runtime must be provider-neutral: hosted frontier models, local models, and open-weight models should be selectable through the same interface when they meet the task's capability requirements.

6. Minimal core, strong extension points.
   The core agent loop should stay small: conversation state, tools, policy, compaction, config, and event streaming. Higher-level behaviors such as spec auditing, plan maintenance, PR review, UI verification, and release gates should be implemented as skills/extensions with typed contracts.

## Non-Goals

- Do not build only a chat UI around code edits.
- Do not treat tests passing as sufficient when the spec remains inconsistent.
- Do not depend on SPECA, Claude Code, or a provider-specific audit backend for core bug auditing.
- Do not keep model settings only in per-session flags or shell history.
- Do not hide uncertainty. Unknown, partial, and not-verified states are valid output states.
- Do not make Claude, OpenAI, or any single model provider mandatory for the core product.

## Reference Signals

- `earendil-works/pi` exposes a coding-agent package with terminal, print, JSON, RPC, and SDK modes, plus skills, extensions, prompt templates, settings, sessions, branching, and compaction.
- OpenAI's current Responses API agent guidance is useful for hosted-provider implementations of bounded tool output, concurrent execution, filesystem/container context, and native compaction, but it is one provider strategy rather than the product's only runtime.
- SPECA is a reference point for the target audit capability: typed property generation from specs, proof-attempt reasoning against code, false-positive review, and finding navigation.
