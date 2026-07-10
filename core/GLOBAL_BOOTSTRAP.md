---
id: CORE-global-bootstrap
layer: core
purpose: Any-project entry point for the PORTABLE subset of this harness — the global config pointer references this file; it routes mhc sessions to the full harness and all other sessions to core/ only.
read_when: A session in ANY repository loads the global harness pointer; the very first core/ file to read, before anything else in this package.
depends_on:
  - ./portable_operating_model.md
  - ../BOOTSTRAP.md
  # trigger-loaded, NOT unconditional (see "Portable load — classify first" below):
  # ./workflow_orchestration_playbook.md, ./portable_decision_rules.yaml
used_by:
  - global-config-pointer
  - any-project-session
tags: [entrypoint, core, portable, project-check, scope-guard]
retrieval_keywords: [global bootstrap, any project, portable discipline, project check, do not read L1 L2, output contract, never optional rules]
---

# GLOBAL BOOTSTRAP — portable entry for any project

## What this is

The portable operating discipline distilled from an observed working method
(the `method-harness-compiler` project — 16 shipping commits,
f4c826f → 91b982b, counted by script: 15/16 carry reviewer trailers,
15/16 state suite counts, and explicit-staging assertions appear whenever
concurrent flights shared the tree).
This core/ layer extracts what transfers to ANY repo or task: the task loop,
the review pipeline, the honesty rules. It is loaded globally so large or
multi-agent (ultracode) runs inherit the discipline everywhere.

## PROJECT CHECK — do this first, it is load-bearing

**Are you working on `method-harness-compiler`?**

- **YES** → go to `../BOOTSTRAP.md` and use the FULL harness, including phase
  state (`context/L2_current_phase.md`) and the route system. Stop reading
  this file.
- **NO** → use ONLY `core/` plus the portable subset listed below. Do NOT
  read `context/L1_project_constitution.md`, `context/L2_current_phase.md`,
  `playbooks/phase*`, or `memory/` — they describe a DIFFERENT project
  (its phases, its frozen scopes, its decisions) and will mislead you into
  applying another repo's constraints to yours.

## Portable load — classify first, then load ONLY the matching set

Pinned as `ROUTE-global-orchestration` in `../ROUTES.yaml` (start = this file
only — the L0/L2/L3 ladder is project-bound and does not apply here).

**Default for EVERY non-mhc task:** `core/portable_operating_model.md` — the
task loop + review pipeline. **Nothing else loads by default.** Then pull ONLY
what your classification (the "Route triggers" block below) names — do NOT
bulk-load the set:

- Completion / done / ready / status claim → `docs/completion-honesty-gate.md`
  + `prompts/claude-code-completion-integrity.md` (REQUIRED; ROUTE-completion-integrity).
- Governance / permissions / hooks / cron / CI / routing → `docs/agent-routing-policy.md`.
- Spawning 2+ subagents → `core/workflow_orchestration_playbook.md`.
- Routing 3+ separable subtasks across model tiers (cheap bulk / strong
  judgment) → `core/model_routing_playbook.md`.
- A cited judgment call → `core/portable_decision_rules.yaml`.
- Self-checking a specific artifact type → the ONE matching rubric in `rubrics/`
  (`pr_review_rubric`, `maintainability_rubric`, `eval_quality_rubric`,
  `progressive_disclosure_rubric`) — per-artifact-type, never per-session.
- Recurring-failure / known-pitfall lookup → `datasets/failure_modes.yaml`.
- Day-to-day usage index → `docs/agent-optimization-runbook.md`.

## Route triggers (classify BEFORE you start — by your deliverable, not the prompt's wording)

The lean default above (`portable_operating_model.md` only) covers general
work; you pull anything else ONLY when a trigger here fires. Before starting —
and again if the deliverable's shape shifts mid-task — ask ONE question: **will my deliverable assert that
something is done / passing / correct / ready / safe to ship or commit — or hand
over an artifact (a status note, a report, a rename, a staged diff) as if it were
authoritative?** If yes, it is a completion-integrity task EVEN WHEN the prompt
never says "done", "verify", or "check" — take the named route and load its full
`required:` set first; do not rely on those files self-loading.

- **Completion integrity** — the deliverable is a done / passing / ready / works
  claim, a status / PR / standup / release note, a stage-or-commit, or the
  validation / reconciliation of an artifact or a delegate/lane report. It fires
  on neutral prompts that never say "done" — e.g. "add the pass rate", "note the
  test status", "stage the rename", "is this ready?", "tell me what to change" →
  **ROUTE-completion-integrity**: read `docs/completion-honesty-gate.md` +
  `prompts/claude-code-completion-integrity.md` BEFORE you write the claim
  (REQUIRED here, not optional).
- **Governance / permission safety** - the task touches settings, permissions,
  hooks, cron, CI, routing, or destructive command allowlists (for example
  `rm`, `rm -rf`, `git clean -fdx`, shell wildcards, or broad execution
  patterns). This fires even when the prompt bundles the risky change with
  safe mechanical work. Read `docs/agent-routing-policy.md`, split any safe
  mechanical edit from the governance decision, and STOP at an explicit
  approval request or patch proposal before applying the risky change. Do not
  broaden destructive permissions as a routine implementation detail.
- Benchmark / eval / grader / A-B design → **ROUTE-eval-design** or
  **ROUTE-ab-test-design** (see `docs/ab_test_protocol.md`,
  `docs/ab_skill_effect_protocol.md`).
- Post-run / postmortem / policy or memory update → **ROUTE-memory-update**.

Trigger -> action, not "load more if unsure": if the deliverable makes no such
claim and hands over no artifact, stay on the portable core and do NOT pull the
overlay.

## Output contract

Every substantive deliverable ends with four short sections:

1. **Decision** — what you concluded or produced.
2. **Risks** — what could be wrong with it, honestly stated.
3. **Required changes** — what must change as a result ("none" is valid).
4. **Next actions** — smallest concrete next steps, in order.

## Rules that are never optional

- **No whole-repo bulk load.** Needing "everything" means the task is
  misclassified or a routing gap exists — say so instead of bulk-reading.
- **Self-check before returning.** Score the draft against the applicable
  rubric; fix or disclose anything scoring below 3.
- **Honest UNSCORED/unknown over guessing.** An explicit unknown, a HALT,
  or an UNSCORED verdict is a correct output; a fabricated answer is not
  (portable_decision_rules: DR-002, DR-010, DR-011).
