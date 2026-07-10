---
id: DOC-multi-delegate-route
layer: doc
purpose: ADAPTER for multi-delegate rounds — names the external file contracts (.coord/plan.yml, .ai task/result files, reconciliation, acceptance) and the single-gate rule, so a session coordinates 2+ delegate lanes from a ~2k-token pointer instead of loading the external skills' full prose (~16k tokens measured).
read_when: A round needs 2+ delegate lanes (codex / claude-cheap / parallel codex) coordinated through file contracts; or a delegate round just finished and you must decide which single gate to run.
depends_on:
  - ../core/model_routing_playbook.md
  - ../core/workflow_orchestration_playbook.md
  - ./codex-delegation-policy.md
used_by:
  - ROUTE-global-orchestration
tags: [doc, multi-delegate, adapter, contracts, coordination, single-gate]
retrieval_keywords: [multi delegate route, plan.yml contract, task file contract, coord directory, reconciliation acceptance gate, splitter adapter, two delegates one round, single gate rule]
---

# Multi-delegate route (adapter — contracts, not vendored prose)

Coordinating 2+ delegate lanes in one round is executed by the external
`agent-collab-workspace` skills (source:
`github.com/WenyuChiou/agent-collab-skills`, v0.3.0+). This adapter names
their FILE CONTRACTS so a session here plans and gates against them
without loading the skills' full instruction prose (~16k tokens, measured
in the 2026-07-09 operator audit: splitter skill prose plus the
operator-side delegation reference, bytes/4; this file is ~2k). The
contracts are the interface; the skills are the implementation.

## When this route applies

- ≥ 2 delegate lanes in one round (codex + claude-cheap, 2× codex, ...)
  → the splitter contract below is MANDATORY (hand-rolled briefs drift;
  measured F11 incident class).
- 1 delegate → skip this file; use `docs/codex-delegation-policy.md`
  (codex) or `core/model_routing_playbook.md` §2 (claude-cheap) directly.
- 0 delegates (all inline/Workflow lanes) →
  `core/workflow_orchestration_playbook.md` alone.

## The file contracts (what each artifact is, who writes it)

| Artifact | Writer | Contract |
|---|---|---|
| `.coord/plan.yml` | splitter (orchestrator session) | The DAG: tasks with `id` (T1..), `agent` (`codex` / `claude` / `claude-cheap`; `gemini` parse-only legacy), optional `model`, `slug`, `depends_on`, `files_in_scope` / `files_out_of_scope` (disjoint partition), `success_criteria` (runnable checks) |
| `.ai/codex_task_<NNN>_<slug>.md` | splitter | Codex brief: scope-confirmation block first, acceptance checks, result path |
| `.ai/claude_task_<NNN>_<slug>.md` | splitter | Cheap-Claude brief (same shape as codex briefs); executed via `Agent(model="haiku")` per `core/model_routing_playbook.md` guardrails |
| `.ai/<agent>_result_<NNN>_<slug>.md` | the delegate | ≤250-word summary; raw logs stay in `.ai/*_log_*` capped at 10 MB |
| `.ai/<agent>_log_<NNN>_<slug>.txt.result.json` | the delegate wrapper | machine fields (status / risks / files_changed / tests_run); double extension BY DESIGN — appended to the LOG path, not the result-md path (the reconciler and gate look for exactly this name) |
| `.coord/reconciliation_<NNN>.md` | reconciler | Per-task summaries, cross-task conflict section, aggregated risks, recommended action |
| `.coord/acceptance_<NNN>.md` | the single gate (below) | PASS / CONDITIONAL / FAIL against plan.yml `success_criteria` |

Routing WITHIN the round follows `core/model_routing_playbook.md`:
mechanical → cheap tiers, honesty-critical → strong, classification
pinned to the orchestrator, every return re-verified.

## The single-gate rule (kills the triple-ceremony overlap)

Measured overlap: acceptance-gate + a code-reviewer subagent + this
repo's review gate ran three overlapping passes per round. The rule:

**After a multi-delegate round, run ONE gate — this repo's review
discipline (code-reviewer on the merged diff) EXTENDED with the
acceptance checklist inputs** (plan.yml `success_criteria` re-run,
`result.json` risks aggregated, reconciliation conflicts resolved-or-
skipped-with-reason). Record the verdict once in
`.coord/acceptance_<NNN>.md` AND cite it in the commit body
(`Co-Reviewed-By: ... (single gate, round <N>)`). Do not run a separate
standalone acceptance ceremony on top of the review gate — same checks,
one pass, one artifact.

**Exception that never folds away:** if the round trips one of the
MANDATORY acceptance-gate presets (multi-locale mirror sync, catalog
entry add, frontier-model fact-check — per `agent-acceptance-gate`),
that preset's codified checks still run — their output feeds the same
`.coord/acceptance_<NNN>.md`, but the preset is never skipped because
"a review already covered it" (that substitution IS the documented F14
incident).

What never collapses into the single gate: the orchestrator's own
re-verification of each delegate return (that happens BEFORE the gate,
per `core/workflow_orchestration_playbook.md` §4 — the gate assumes
verified inputs, it does not replace verification).

## Honest status

- The contracts above are exercised in the skills' own dogfood (splitter
  measured ~12-14x token saving vs hand-rolled briefs, 2026-05-14) and
  the claude-cheap lane's routing basis is this repo's
  `benchmarks/route_cost_ab/` (k=3, blind router). The single-gate rule
  is a documented merge of overlapping ceremonies, NOT yet A/B-measured
  end-to-end — case `task_splitter_vs_handrolled_multi_delegate` in
  `benchmarks/harness_cases.yaml` remains the pre-registered vehicle.
- This file is a POINTER: if it drifts from the skills' contracts, the
  skills win — fix this file, and say so in the commit.
