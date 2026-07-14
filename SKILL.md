---
name: fable-method-harness
description: >-
  Operating harness for working on the method-harness-compiler project (or
  reviewing its artifacts). Use when starting ANY task on that project —
  phase reviews, tool discovery, PR review, eval design, memory updates,
  runtime export, repo maintenance, or A/B test design. Routes the agent to
  a minimal per-task file set instead of whole-repo reading.
  For work on ANY OTHER project, activate only when the task is long /
  multi-step, multi-agent, expensive-if-wrong, makes a completion claim
  (done / passing / fixed / ready / safe / staged), or touches governance
  (permissions, hooks, cron, CI, routing) — the portable entry is then
  core/GLOBAL_BOOTSTRAP.md. Skip for one-line / typo / format edits and pure
  capability asks.
id: SKILL
layer: entry
purpose: Lightweight runtime wrapper — lets skill-aware runtimes (Claude Code and similar) discover and launch the harness like a skill
read_when: Auto-discovered by skill-convention runtimes; read manually when wiring the harness into a new runtime
depends_on: [BOOTSTRAP.md, ROUTES.yaml]
used_by: [ROUTE-phase-review, ROUTE-tool-discovery, ROUTE-pr-review, ROUTE-eval-design, ROUTE-memory-update, ROUTE-runtime-export, ROUTE-repo-maintenance, ROUTE-ab-test-design]
tags: [entrypoint, skill, runtime-wrapper]
retrieval_keywords: [skill entrypoint, launch harness, runtime wrapper, when to use]
---

# SKILL: fable-method-harness

This file only **launches** the harness. The rules live in the routed files.

## 1. When to use this skill

Any task touching the `method-harness-compiler` project: planning, review,
building, evaluating, releasing, or maintaining. Also when asked to "work
the way this project works."

For large or multi-agent (ultracode) tasks on any OTHER project, the
portable entry is `core/GLOBAL_BOOTSTRAP.md` (core/ only — skip section 2).

For **auditing / simplifying / benchmarking a harness itself** (CLAUDE.md,
hooks, skills, slash commands, scheduled reviews, rolling maintenance), the
entry is the adaptive-harness skill adapter:
`.claude/skills/adaptive-harness/SKILL.md`. This root file launches work ON
the mhc project; the adapter launches work ON a harness — they share the
repo but route to different file sets.

## 2. Required startup sequence

Read, in order: `context/L0_bootstrap.md` → `context/L2_current_phase.md` →
`context/L3_task_router.md` → your route's bundle in ONE call (`python
scripts/route_pack.py <task_type>`; entry-only fallback:
`scripts/route_show.py` or grep `- id: ROUTE-<...>` in `ROUTES.yaml` — do
not read it whole). (Same ladder as `BOOTSTRAP.md`.)

## 3. Route selection

Classify the task into one of the 8 task types (L3 table), load its
bundle via `scripts/route_pack.py <task_type>` (one call = entry +
start+required contents; entry-only: `route_show.py` or a grep of the
block), open `optional` only with a stated reason. Never bulk-load the
repo, never serial-read the route files one by one.

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
secrets here — the repository is PUBLIC (`docs/publication_status.md`);
every file must stay public-safe.
