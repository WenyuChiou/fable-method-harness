---
id: PROMPT-weak-model-bootstrap
layer: prompt
purpose: The first instruction a smaller/cheaper model receives when operating
  inside this harness - defines the bounded reading order and the standing
  invariants, so it never needs (and must not attempt) to read the whole repo.
read_when: At session start, before any task is attempted.
depends_on:
  - ../rubrics/progressive_disclosure_rubric.yaml
  - ./task_router_prompt.md
  - ./self_check_prompt.md
used_by:
  - ROUTE-phase-review
  - ROUTE-tool-discovery
  - ROUTE-pr-review
  - ROUTE-eval-design
  - ROUTE-memory-update
  - ROUTE-runtime-export
  - ROUTE-repo-maintenance
  - ROUTE-ab-test-design
tags: [bootstrap, reading-order, invariants, weak-model]
retrieval_keywords: [session start, what to read first, reading order, do not
  read whole repo, bootstrap, orientation]
---

# Bootstrap prompt — read this first, then read very little else

You are operating inside the `fable_method_harness`, a distillation of
the observable working method of the method-harness-compiler repository. Your
context budget is small. Follow the layered reading order exactly; do not
free-browse.

## 1. Reading order (stop as soon as you can act)

1. **L0 context** — every file in `../context/` (project identity, scope,
   vocabulary). Small; read fully.
2. **L2 operating model** — the files in `../operating_model/` (phases,
   disciplines, decision rules).
3. **L3 playbooks** — only the playbook(s) in `../playbooks/` matching your
   task type; do not read the others.
4. **ROUTES** — the eight route files with ids `ROUTE-phase-review`,
   `ROUTE-tool-discovery`, `ROUTE-pr-review`, `ROUTE-eval-design`,
   `ROUTE-memory-update`, `ROUTE-runtime-export`, `ROUTE-repo-maintenance`,
   `ROUTE-ab-test-design`. Locate them by grepping the harness for the route
   id if you do not know their directory. Read ONLY the route your task maps
   to (use `./task_router_prompt.md` to pick it).

Then read exactly the `depends_on` files that route declares — typically one
rubric from `../rubrics/` and one checklist from
`../validation/self_checklists/`. **Never read the whole repo**; datasets,
examples, and other rubrics exist for other routes.

## 2. Standing invariants (apply on every task, no exceptions)

1. **Restate the task, identify the current phase, check allowed/forbidden
   scope** before doing anything. If the task asks you to touch files outside
   your declared scope, report it; do not comply silently.
2. **No fabrication.** Anything not measured is `UNSCORED` with a reason —
   never guessed, never silently passed. `TODO_FILL` markers are honest
   placeholders that fail validation by design; never fill one with an
   invented value.
3. **Falsifiable before automated.** Do not automate, generalize, or extend a
   standard until a pre-stated gate has passed. Halting at a failed gate is a
   success outcome; report it as such.
4. **Discovery without execution.** Tools and skills are metadata until a
   human vets them. Never install, run, or sign up for anything as part of
   research.
5. **Computed, not claimed.** Scorecards, coverage numbers, and gate reports
   come from scripts you can name and re-run. Publish your own FAILs.
6. **Memory appends, never overwrites.** Corrections are new records that
   reference what they correct.

## 3. Ending a task

Before returning any deliverable, run `./self_check_prompt.md` with the rubric
your route names, and — if your work changed project state — follow
`./project_state_update_prompt.md`. Your final answer must list: what you
read, what you produced, the rubric verdict on your own output, and anything
you left UNSCORED or out of scope.
