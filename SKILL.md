---
name: fable-style-project-harness
description: >-
  Operating harness for working on the method-harness-compiler project (or
  reviewing its artifacts). Use when starting ANY task on that project —
  phase reviews, tool discovery, PR review, eval design, memory updates,
  runtime export, repo maintenance, or A/B test design. Routes the agent to
  a minimal per-task file set instead of whole-repo reading.
id: SKILL
layer: entry
purpose: Lightweight runtime wrapper — lets skill-aware runtimes (Claude Code and similar) discover and launch the harness like a skill
read_when: Auto-discovered by skill-convention runtimes; read manually when wiring the harness into a new runtime
depends_on: [BOOTSTRAP.md, ROUTES.yaml]
used_by: [ROUTE-phase-review, ROUTE-tool-discovery, ROUTE-pr-review, ROUTE-eval-design, ROUTE-memory-update, ROUTE-runtime-export, ROUTE-repo-maintenance, ROUTE-ab-test-design]
tags: [entrypoint, skill, runtime-wrapper]
retrieval_keywords: [skill entrypoint, launch harness, runtime wrapper, when to use]
---

# SKILL: fable-style-project-harness

This file only **launches** the harness. The rules live in the routed files.

## 1. When to use this skill

Any task touching the `method-harness-compiler` project: planning, review,
building, evaluating, releasing, or maintaining. Also when asked to "work
the way this project works."

For large or multi-agent (ultracode) tasks on any OTHER project, the
portable entry is `core/GLOBAL_BOOTSTRAP.md` (core/ only — skip section 2).

## 2. Required startup sequence

Read, in order: `context/L0_bootstrap.md` → `context/L2_current_phase.md` →
`context/L3_task_router.md` → `ROUTES.yaml`. (Same ladder as `BOOTSTRAP.md`.)

## 3. Route selection

Classify the task into one of the 8 task types (L3 table), resolve its
`ROUTE-*` entry in `ROUTES.yaml`, read the `required` list in full,
open `optional` only with a stated reason. Never bulk-load the repo.

## 4. Required output style

End every substantive deliverable with: **Decision / Risks / Required
changes / Next actions**. Phase-gate questions get an explicit
**GO / CONDITIONAL_GO / NO_GO**.

## 5. Self-check

Before returning, score the draft 1–5 against the rubric(s) your route
names; fix or disclose anything below 3. Use the matching checklist under
`validation/self_checklists/` when one exists.

## 6. Project memory update

If the work changed direction, phase, or standing decisions: append to the
`memory/` files per `operating_model/project_memory_policy.yaml`. Append,
never overwrite; cite the grounding artifact or commit.

## 7. What not to do

Do not read the whole repo first. Do not work outside the L2 `allowed`
list without an explicit gate decision. Do not fabricate citations, data,
or transcripts. Do not execute or install discovered tools. Do not put
secrets here. Do not make this repository public.
