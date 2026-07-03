---
id: DOC-agent-optimization-runbook
layer: doc
purpose: Day-to-day operator guide for using the Hermes / Claude Code / Codex stack with this overlay — worked examples end to end.
read_when: Onboarding to the stack, or deciding how to run a specific real task across the three surfaces.
depends_on:
  - ./agent-routing-policy.md
  - ./completion-honesty-gate.md
  - ../prompts/hermes-router.md
  - ../prompts/claude-code-debug.md
  - ../prompts/claude-code-orchestration.md
  - ../prompts/claude-code-completion-integrity.md
  - ../prompts/codex-task-brief-template.md
used_by:
  - operator-session
tags:
  - runbook
  - workflow
  - examples
  - daily-use
  - agent-stack
retrieval_keywords:
  - how do I use the stack
  - runbook
  - telegram task
  - oauth debug
  - mechanical refactor
  - benchmark report
  - release check
  - end to end example
---

# Agent optimization runbook

## 1. Purpose

Day-to-day operator guide for running real work across the operator's three
agent surfaces — **Hermes**, **Claude Code**, and **Codex** — under this
overlay. This is the "how do I actually run this task today" companion to the
policy docs; it does not restate the harness doctrines, it shows you which
surface to reach for and how to prove the work is done.

**Provenance:** this artifact encodes the operator's Hermes / Claude Code /
Codex stack (source: model-routing-benchmark
`universal_agent_optimization_prompt.md`) bound to this harness's existing
doctrines cited inline; it is NOT distilled from `method-harness-compiler`.

**Integration principle (stated once):**
[`operating_model/model_routing_policy.yaml`](../operating_model/model_routing_policy.yaml)
(id `OM-model-routing-policy`) deliberately keeps model classes ABSTRACT
(`cheap_fast | balanced | strong_reasoning`) and says concrete model bindings
belong to runtime configuration. This overlay is exactly that runtime binding.
The quality invariant is the **author-agnostic layered review gate**
([`operating_model/review_protocol.md`](../operating_model/review_protocol.md),
`OM-review-protocol`), not routing everything to the strongest surface.

**The overlay files, one line each:**

| File | Role |
|---|---|
| [`docs/agent-routing-policy.md`](./agent-routing-policy.md) (`DOC-agent-routing-policy`) | Which surface + mode for which task character |
| [`docs/completion-honesty-gate.md`](./completion-honesty-gate.md) (`DOC-completion-honesty-gate`) | When you may say "done"; artifact-mismatch checks |
| [`prompts/hermes-router.md`](../prompts/hermes-router.md) (`PROMPT-hermes-router`) | Classify + route an inbound task |
| [`prompts/claude-code-debug.md`](../prompts/claude-code-debug.md) (`PROMPT-claude-code-debug`) | Evidence-first diagnosis (Opus baseline) |
| [`prompts/claude-code-orchestration.md`](../prompts/claude-code-orchestration.md) (`PROMPT-claude-code-orchestration`) | Multi-agent / high-complexity orchestration (Opus + distilled) |
| [`prompts/claude-code-completion-integrity.md`](../prompts/claude-code-completion-integrity.md) (`PROMPT-claude-code-completion-integrity`) | Process-integrity / release lens (Fable + distilled) |
| [`prompts/codex-task-brief-template.md`](../prompts/codex-task-brief-template.md) (`PROMPT-codex-task-brief-template`) | Brief a scoped mechanical job for Codex |
| [`scripts/check_agent_artifacts.py`](../scripts/check_agent_artifacts.py) (`SCRIPT-check-agent-artifacts`) | Grep-verifies this overlay's cross-refs on disk |

> **On `used_by:` values.** Four `used_by:` markers in this overlay's frontmatter —
> `operator-session`, `hermes-runtime`, `claude-code-runtime`, `codex-runtime` — name
> external runtime *consumers*, not harness-internal ids. Unlike `DOC-*` / `PROMPT-*` /
> `ROUTE-*` ids they resolve to no file, and `grep "id: hermes-runtime"` finds nothing
> **by design**. They record which real surface loads the artifact at runtime; a drift
> sweep should treat them as informational, not as dangling references.

## 2. The loop

Five steps. Each hands off to a named artifact — follow the cross-reference,
do not improvise.

| # | Step | Do this | Cross-reference |
|---|---|---|---|
| 1 | **Classify** | Run the inbound task through the router to get a route + surface hint | `PROMPT-hermes-router` (mirrors `PROMPT-task-router`, the 8-route classifier) |
| 2 | **Route** | Map route → surface + mode from the binding table | `DOC-agent-routing-policy` (binds abstract tiers of `OM-model-routing-policy`) |
| 3 | **Execute** | Run with the surface's own prompt; Codex work is brief-first | the four `PROMPT-claude-code-*` / `PROMPT-codex-task-brief-template` files |
| 4 | **Verify** | Prove completion on disk, not from a report; check for artifact mismatch | `DOC-completion-honesty-gate` + `PROMPT-self-check` + `OM-review-protocol` |
| 5 | **Report** | Hermes returns a concise result: what shipped, what is UNSCORED, what is next | `CORE-portable-operating-model` honest-failure doctrine |

The invariant across every route: **nothing ships ungated**, and the gate is
the same regardless of which surface wrote it
([`operating_model/decision_rules.yaml`](../operating_model/decision_rules.yaml),
`DR-011` no-silent-pass; `DR-020` single-source-of-truth-for-checks).

## 3. Worked examples

### (a) Small Telegram task → Hermes, direct + verify

- **Scenario:** operator sends a one-line request from Telegram — "grep the
  session log for the last release tag and paste it back", or a small file
  edit with an unambiguous target.
- **Surface + mode:** **Hermes** (tier 1 `cheap_fast` operator/router). No
  escalation; it has memory, terminal, file access, session search.
- **What runs:** Hermes classifies with `PROMPT-hermes-router`, sees the task
  is small + low-risk + unambiguous, executes directly (read/grep/single
  edit), and reports back in the same Telegram thread.
- **How completion is verified:** Hermes re-reads the touched file / re-runs
  the query and shows the actual output — never "done" off intent
  (`DR-021` verify-agent-observations-on-disk). If any uncertainty appears
  mid-task it stops and records a TODO rather than guessing
  (`DR-002` todo-on-uncertainty-never-guess).

### (b) OAuth / provider / plugin debug → Claude Opus baseline via `PROMPT-claude-code-debug`

- **Scenario:** an **OAuth** callback returns 401 in one provider only, a
  plugin auth flow intermittently fails, or a token refresh path throws. Scope
  is clear (which surface is broken is known) but the root cause is not.
- **Surface + mode:** **Claude Code — "Claude Opus baseline"** (tier 2–3
  focused, evidence-first diagnosis). Not Codex: root cause is ambiguous, which
  is explicitly off-limits for Codex.
- **What runs:** load `PROMPT-claude-code-debug`. Reproduce → isolate the
  failing layer → read the actual request/response and the provider config →
  form one hypothesis, test it, then fix. Discovery stays read-only until the
  cause is proven (`DR-012` read-only-discovery-never-execute).
- **How completion is verified:** the fix is demonstrated against the failing
  case (the **OAuth** flow now returns a token), and a regression check ships
  with the contract change (`DR-014` regression-net-ships-with-contract-change).
  Preliminary conclusions are labeled preliminary until reproduced.

### (c) Multi-file mechanical refactor → Codex via `PROMPT-codex-task-brief-template`

- **Scenario:** rename a symbol across 12 files, migrate a call signature with
  a stable pattern, or scaffold test skeletons — a clear **refactor** with
  acceptance criteria and no security/governance surface.
- **Surface + mode:** **Codex** (tier 2 `balanced` mechanical executor).
  Delegation is mandatory here per the tripwire (≥3 files, same mechanical
  transform).
- **What runs:** write the brief first using `PROMPT-codex-task-brief-template`
  (goal, exact file list, transform pattern, acceptance criteria, out-of-scope
  list). Codex executes the scoped edits. **Codex does not commit** — this
  overlay's standing rule: do not commit unless explicitly asked, and a
  delegate never holds final authority. Codex returns the diff.
- **How completion is verified:** Claude Code reviews the returned diff before
  anything lands (`DR-021` verify-agent-observations-on-disk; the acceptance
  gate is author-agnostic). Explicit-path staging with a count assertion at
  commit time (`DR-006`), never `git add -A` on a delegate's working tree.

### (d) Benchmark / report generation → Claude Opus + distilled orchestration via `PROMPT-claude-code-orchestration`

- **Scenario:** produce a **benchmark** comparison or a synthesized report that
  spans multiple runs, files, or sub-agents — default high-complexity
  orchestration.
- **Surface + mode:** **Claude Code — "Claude Opus + distilled"** (tier 3
  `strong_reasoning` orchestration).
- **What runs:** load `PROMPT-claude-code-orchestration`. Plan the DAG, dispatch
  mechanical legs to Codex if any, reconcile, and assemble. All numeric results
  come from a runner's actual output — **computed, not claimed**
  (`DR-004` computed-artifacts-only-via-runners). Frozen transcripts stay
  immutable (`DR-005`).
- **How completion is verified:** every headline number in the **benchmark**
  traces to a runner artifact on disk; the report distinguishes measured from
  synthesized rows. Self-scored before return (`PROMPT-self-check`), and no
  "done" is claimed off a derived report — that is a
  [`docs/completion-honesty-gate.md`](./completion-honesty-gate.md)
  (`DOC-completion-honesty-gate`) violation.

### (e) Release / completion check → Claude Fable + distilled via `PROMPT-claude-code-completion-integrity` + `DOC-completion-honesty-gate`

- **Scenario:** a **release** gate, a "is this actually done?" check, or a
  suspected artifact-vs-claim mismatch (the report says green, the disk says
  otherwise).
- **Surface + mode:** **Claude Code — "Claude Fable alias + distilled"**
  (tier 3 process-integrity / gate lens): completion honesty, premature-done
  prevention.
- **What runs:** load `PROMPT-claude-code-completion-integrity` and walk
  `DOC-completion-honesty-gate`. Cross-check the claimed deliverable against the
  files on disk, the phase-gate ladder
  ([`operating_model/phase_gates.md`](../operating_model/phase_gates.md)), and
  the review layers (`OM-review-protocol`).
- **How completion is verified:** a **release** is GO only when the gate passes
  on committed state; a halt is a valid, published outcome
  (`DR-010` halt-is-success; `DR-009` publish-own-failures). Grader/gate fixes
  land separately from the change under review (`DR-003`).

## 4. Verification habit

After **any** edit to this overlay (a doc, a prompt, or a cross-reference),
run the on-disk verifier before you consider the change done:

```bash
python scripts/check_agent_artifacts.py
```

- For each overlay file it checks: the file exists, it contains its `must_contain`
  literals, and every `depends_on:` path in its frontmatter resolves on disk — the
  single source of truth for these checks (`DR-020` single-source-of-truth-for-checks).
- **A nonzero exit blocks.** Treat a nonzero exit exactly like a failed test:
  do not commit, do not report "done", fix the broken reference and re-run
  until it exits 0. This is the overlay-local form of
  `DR-011` no-silent-pass and `DR-021` verify-agent-observations-on-disk.
- **Automate it as a git gate (recommended):** this repo ships a versioned
  pre-commit hook at
  [`scripts/hooks/pre-commit`](../scripts/hooks/pre-commit)
  (`HOOK-pre-commit-overlay`) that runs the validator and blocks the commit on
  any gap. Enable it once per clone — the hook is versioned but `core.hooksPath`
  is a local git setting, so a fresh clone (or a restored machine) must opt in:

  ```bash
  git config core.hooksPath scripts/hooks
  ```

  Bypass a specific commit with `git commit --no-verify` (justify it in the body).

## 5. Anti-patterns

| ❌ Anti-pattern | ✓ Instead | Anchor |
|---|---|---|
| Handing Codex a task with no brief ("just refactor these") | Write `PROMPT-codex-task-brief-template` first: file list + transform + acceptance criteria + out-of-scope | example (c) |
| Letting a delegate commit / push its own work | Delegate returns the diff; Claude Code reviews, then the operator stages with a count assertion. Do not commit unless explicitly asked | `DR-006`, `DR-021` |
| Claiming "done" off a derived **benchmark** or report | Trace every headline number to a runner artifact; results computed not claimed | `DR-004`, `DOC-completion-honesty-gate` |
| Over-orchestrating a trivial task (spinning up a DAG + sub-agents for a one-file edit) | Run it directly on Hermes / Opus baseline; see [`core/workflow_orchestration_playbook.md`](../core/workflow_orchestration_playbook.md) **"When NOT to orchestrate"** | `CORE-workflow-orchestration-playbook` |
| Routing everything to the strongest surface "to be safe" | Route by task character; the author-agnostic gate assures quality, not the surface | `DOC-agent-routing-policy`, `OM-review-protocol` |

---

**Decision:** Adopt this runbook as the operator's day-to-day guide for the
Hermes / Claude Code / Codex stack; it binds the abstract tiers of
`OM-model-routing-policy` to the three real surfaces via `DOC-agent-routing-policy`.

**Risks:** the surface bindings drift if the operator's stack changes (e.g. a
mode is renamed) — the runbook then points at a stale mode label; and the five
worked examples are illustrative, not exhaustive, so edge tasks may need a
judgment call at step 2.

**Required changes:** none to existing harness doctrines — this overlay only
cross-references them.

**Next actions:** (1) run `python scripts/check_agent_artifacts.py` after this
file and its sibling overlay files land, and confirm exit 0; (2) confirm the
five sibling prompt files and the two sibling docs exist so every `depends_on`
resolves.
