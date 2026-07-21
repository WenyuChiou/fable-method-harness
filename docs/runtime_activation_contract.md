---
id: DOC-runtime-activation-contract
layer: doc
purpose: Measurable and reversible conditional activation contract shared by Codex and Hermes.
read_when: Wiring the portable harness into Codex or Hermes; evaluating activation recall, routine over-triggering, or rollback behavior.
depends_on: [../AGENTS.md, ../HERMES.md, ../core/GLOBAL_BOOTSTRAP.md]
used_by: [DOC-codex-harness-integration, PROMPT-hermes-router, runtime-activation-probe]
tags: [codex, hermes, activation, rollback, telemetry, evaluation]
retrieval_keywords: [conditional activation, harness off, rollback, routine over-trigger, Codex Hermes probe]
---

# Conditional runtime activation

The harness is useful when a wrong answer is expensive; it is counterproductive
when every short task pays its context and procedure cost.  Both Codex and
Hermes therefore use the same task-level decision before they load the
portable bootstrap.

| Decision | Activate the harness? | Examples |
|---|---:|---|
| Explicit harness, README/evidence, or harness-maintenance request | Yes | benchmark, routing, AGENTS/HERMES/hooks/skills review |
| Long or multi-step work | Yes | a migration with discovery, edits, tests, and handoff |
| Multiple agents or reconciliation | Yes | parallel lanes, conflicting reports, shared worktree |
| Completion, release, security, permissions, hooks, CI, or governance | Yes | "is this ready?", release, allowlist, workflow edit |
| Self-contained question, lookup, typo, or one-file mechanical edit | No | explain a flag, locate a file, correct a spelling |

## Runtime behavior

- **Codex:** the repository `AGENTS.md` is its entrypoint.  Its conditional
  block decides whether to read `core/GLOBAL_BOOTSTRAP.md`; normal repository
  safety rules still apply in either state.
- **Hermes:** `HERMES.md` is intentionally a short, first-priority shim.  It
  avoids injecting the full `AGENTS.md` for routine work.  On activation it
  loads the repository-root `AGENTS.md` and then the portable bootstrap;
  otherwise it stops there.
- Neither runtime may claim the harness was applied while inactive.

## Rollback

Create an empty `.fable-harness-off` file at the target repository root.  A
candidate activation must check for it first; when present, no portable
harness material is loaded.  Delete the marker to restore `auto` behavior.
For Hermes, deleting the installed `HERMES.md` shim is a second, deterministic
rollback: Hermes resumes its native context precedence without changing global
configuration.  These are deliberately reversible filesystem changes, not a
new daemon, hook, or credential.

## Measurement contract

Activation correctness is measured with a runtime-issued JSON receipt, not a
reviewer's interpretation of prose:

```json
{"schema_version":1,"harness":"active","reason":"trigger"}
```

`FABLE_ACTIVATION_PROBE` is evaluation-only.  The runner creates the actual
per-case workspace and, for rollback, the real marker file.  The runtime may
inspect that marker only; it must not load routed material or perform task
work.  Its `FABLE_ACTIVATION_PROBE` envelope and receipt instruction are test
scaffolding, not an activation trigger: the decision is made from `TASK:`
alone.  It then returns exactly the receipt above.  The scorecard reports all
of the following separately:

1. trigger recall (active on required cases),
2. routine over-trigger count (active on simple cases),
3. rollback obedience (inactive when the actual marker exists), and
4. malformed or unavailable receipts as `UNSCORED`, never as a pass.

Exact token measurement is separate from activation correctness.  Codex emits
usage JSONL directly.  Hermes's one-shot stdout does not, but Hermes persists
provider-reported input/output/cache/reasoning counters in its local session
database.  A telemetry runner may accept those counters only when one and only
one new session can be correlated to the probe; any missing database, multiple
candidates, or zero-evidence row is `UNSCORED`.  Byte counts and bytes/4 are
context-size proxies only.

The live runner requires a committed preregistration whose frozen input hashes
match before it invokes either runtime.  Probe workspaces are under ignored
`evals/runtime_activation/workspaces/`: on Windows Hermes may retain an MCP
child's working directory after a completed call, so cleanup is best-effort
and a pending cleanup is recorded rather than turning an otherwise valid call
into an unreported crash.
