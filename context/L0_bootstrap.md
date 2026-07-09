---
id: L0-bootstrap
layer: context
purpose: Minimal first read — orient in under 300 words, then route
read_when: Start of every session in this repo, before anything else
depends_on: []
used_by: [ROUTE-phase-review, ROUTE-tool-discovery, ROUTE-pr-review, ROUTE-eval-design, ROUTE-memory-update, ROUTE-runtime-export, ROUTE-repo-maintenance, ROUTE-ab-test-design]
tags: [bootstrap, entrypoint, first-read]
retrieval_keywords: [start here, bootstrap, first read, orientation, session start]
---

# L0 — Bootstrap

You are inside **fable-method-harness**: an operating harness
distilled from the observable working method of the
`method-harness-compiler` repo (docs, schemas, scripts, tests, example
packages, git log — nothing hidden, nothing invented), plus an adaptive
review layer that keeps the harness itself maintained.

**What it is:** procedures, rubrics, worked examples, and decision records
for running that project's method — phase gates, falsifiable eval gates,
honest-failure publishing, layered review, no-fabrication code gates.

**What it is not:** a prompt dump, hidden internals, or secrets. The repo
is PUBLIC under a public-safe posture (`docs/publication_status.md`) —
write every file as world-readable.

## Read next — in this order, nothing more

1. `context/L2_current_phase.md` — what the source project's current phase
   allows and forbids.
2. `context/L3_task_router.md` — classify your task into one of the 8
   routes (`ROUTE-*`).
3. `ROUTES.yaml` — the exact file list for that route. Open only those
   files.

## Rules

- **DO NOT read the whole repo.** Progressive disclosure is the contract:
  load a layer only when the shallower layer is insufficient
  (`context/L4_progressive_disclosure_policy.md`).
- **Use `ROUTES.yaml`** for every task — never improvise a file list.
- **Stay within the current phase.** If the task asks for work L2 marks
  forbidden (e.g. Phase-3 automation before its gate), halt and say so —
  halt is a success, not a failure.
- Look things up by stable ID (`TE-###`, `FM-###`, `EC-###`, `RE-###`,
  `RUBRIC-*`, `PLAYBOOK-*`) rather than reading files end to end.
