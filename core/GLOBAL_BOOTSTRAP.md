---
id: CORE-global-bootstrap
layer: core
purpose: Any-project entry point for the PORTABLE subset of this harness — the global config pointer references this file; it routes mhc sessions to the full harness and all other sessions to core/ only.
read_when: A session in ANY repository loads the global harness pointer; the very first core/ file to read, before anything else in this package.
depends_on:
  - ./portable_operating_model.md
  - ./workflow_orchestration_playbook.md
  - ./portable_decision_rules.yaml
  - ../BOOTSTRAP.md
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

## Portable reading set (non-mhc sessions)

This set is pinned as `ROUTE-global-orchestration` in `../ROUTES.yaml`
(start = this file only — the L0/L2/L3 ladder is project-bound and does
not apply here).

1. `core/portable_operating_model.md` — the task loop + review pipeline.
2. `core/workflow_orchestration_playbook.md` — running multi-agent rounds.
3. `core/portable_decision_rules.yaml` — standing judgment-call rules.
4. Rubrics, when self-checking the matching artifact type:
   - `rubrics/pr_review_rubric.yaml`
   - `rubrics/maintainability_rubric.yaml`
   - `rubrics/eval_quality_rubric.yaml`
   - `rubrics/progressive_disclosure_rubric.yaml`

Read only what the task needs; the rubrics are per-artifact-type, not
per-session.

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
