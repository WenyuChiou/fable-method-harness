---
id: L3-task-router
layer: context
purpose: Classify an incoming task into one of the 8 pinned routes
read_when: After L0 and L2, before opening any route or reference file
depends_on: [context/L2_current_phase.md, ROUTES.yaml]
used_by: [ROUTE-phase-review, ROUTE-tool-discovery, ROUTE-pr-review, ROUTE-eval-design, ROUTE-memory-update, ROUTE-runtime-export, ROUTE-repo-maintenance, ROUTE-ab-test-design]
tags: [router, classification, task-type, routes]
retrieval_keywords: [which route, classify task, task router, route table, ROUTE ids]
---

# L3 — Task Router

> **Working on a project OTHER than `method-harness-compiler`?** →
> `ROUTE-global-orchestration` (`core/` only: start at
> `core/GLOBAL_BOOTSTRAP.md`; do NOT load the project-bound layers —
> `context/L1`/`L2`, `playbooks/phase*`, `memory/`). Everything below this
> line is for mhc sessions only.

Classify the task FIRST (restate it in one sentence, name the phase it
touches, check L2's allowed/forbidden list), THEN pick exactly one route
below, THEN open `ROUTES.yaml` for that route's file list. Do not open
rubric/playbook/example files the route does not list.

## Route table

| Task type | Route | Classification hint (1 line) |
|---|---|---|
| Phase/milestone gate check, "are we ready to advance", GO/NO_GO decision, development-plan status audit | `ROUTE-phase-review` | Mentions phases, milestones, gates, acceptance criteria, N=2/N=3, or `development_plan.md` |
| Researching/scoring tool sources, MCP registries, skill catalogs; drafting ToolCards; adapter design; reviewing a discovery plan or report for boundary/citation integrity | `ROUTE-tool-discovery` | Mentions registries, MCP servers, skills marketplaces, `tool_sources.yaml`, risk/permission proxies — and must stay metadata-only. A review OF discovery work routes here (subject beats verb), not to `ROUTE-phase-review`, unless it is a gate/GO-NO_GO decision |
| Reviewing a diff, commit range, or PR before merge; staging and commit hygiene | `ROUTE-pr-review` | Mentions diff, commit, review verdict, staged files, explicit-path staging, CI watch |
| Designing an eval, grader, scorecard, pre-registration, outcome eval, or gate metric | `ROUTE-eval-design` | Mentions graders, pass criteria, UNSCORED, pre-register, keyword families, blinded grading, regression floors |
| Recording corrections, friction reports, standard-changelog entries, memory-file updates | `ROUTE-memory-update` | Mentions friction IDs (F#/N3-F#), corrections, JSONL memory, `CHANGELOG_STANDARD.md`, append-only |
| Exporting/installing packages into runtimes; plugin manifests; install verification | `ROUTE-runtime-export` | Mentions plugin.json, marketplace.json, `phc export`, install smoke, fresh-user E2E, SKILL.md pointer |
| Repo hygiene: locale mirror sync, CI config, test-suite upkeep, README/doc drift, gitignore | `ROUTE-repo-maintenance` | Mentions 3-locale READMEs, CI workflow, asset-hygiene tests, drift fixes, cleanup |
| Designing a baseline comparison or A/B experiment (arms, corpus, grading protocol) | `ROUTE-ab-test-design` | Mentions arms, baseline vs harness, persona-prompt comparison, leakage probes, contamination controls |

## Tie-breakers (observable precedents)

- **Review beats build.** If a task both produces a diff and reviews one,
  the review discipline of `ROUTE-pr-review` applies on top of the build
  route — in the source repo nothing ships ungated (every feat commit
  carries `Co-Reviewed-By` trailers).
- **Design beats run.** Designing an eval or A/B protocol is
  `ROUTE-eval-design` / `ROUTE-ab-test-design`; actually RUNNING one is
  gated by L2 (pre-registration must exist BEFORE any model call — the
  Category-7 precedent).
- **Friction found mid-task** → finish the task on its own route, then
  record the friction via `ROUTE-memory-update` (append, never absorb).
- **No route fits** → do not improvise. Halt, state which routes were
  considered and why each fails, and ask. Halt is a success (L1 #10).

## After classifying

Open `ROUTES.yaml`, load ONLY the files listed under your route, and follow
`context/L4_progressive_disclosure_policy.md` for any escalation beyond
that list.
