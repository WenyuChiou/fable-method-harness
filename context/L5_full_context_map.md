---
id: L5-full-context-map
layer: context
purpose: One-line map of every directory — for targeted lookup, not sequential reading
read_when: You know WHAT you need but not WHERE it lives; or during a sanctioned full-context load
depends_on: [context/L4_progressive_disclosure_policy.md]
used_by: [ROUTE-phase-review, ROUTE-tool-discovery, ROUTE-pr-review, ROUTE-eval-design, ROUTE-memory-update, ROUTE-runtime-export, ROUTE-repo-maintenance, ROUTE-ab-test-design]
tags: [map, directory, layout, where-is]
retrieval_keywords: [directory map, where is, repo layout, file locations, full context map]
---

# L5 — Full Context Map

One line per location. Use this to jump to the right directory, then grep
by stable ID — do not walk it top to bottom (L4 rule 1).

| Location | What lives there / when to use it |
|---|---|
| `README.md` | What this repo is / is not; the reading order; privacy status. First contact only. |
| `HARNESS.yaml` | Package manifest: name, version, entrypoint, provenance, layers, routes, portability targets, constraints. Use for machine consumption or provenance checks. |
| `ROUTES.yaml` | The 8 route definitions with per-route file lists. Use after every L3 classification — load one entry via `scripts/route_show.py`, not the whole file. |
| `context/` | L0–L5 progressive-disclosure layers (this directory). L0 bootstrap → L1 constitution → L2 current phase → L3 router → L4 disclosure policy → L5 this map. |
| `operating_model/` | The distilled method skeleton: `operating_model.md` (the core loop), `decision_rules.yaml`, `phase_gates.md`, `review_protocol.md`, `model_routing_policy.yaml`, `project_memory_policy.yaml`. Use when a route file cites an operating-model section. |
| `playbooks/` | Step-by-step per-phase procedures (`PLAYBOOK-*`): `phase0_static_package_standard.md` through `phase7_public_release.md` — how to run each phase's work the way the source repo demonstrably ran it. Use when executing, not deciding. |
| `rubrics/` | Scoring and review rubrics (`RUBRIC-*`): `pr_review_rubric.yaml`, `eval_quality_rubric.yaml`, `harness_quality_rubric.yaml`, `tool_discovery_rubric.yaml`, `tool_boundary_rubric.yaml`, `architecture_review_rubric.yaml`, `maintainability_rubric.yaml`, `progressive_disclosure_rubric.yaml`. Use when judging an artifact. |
| `examples/` | `examples/golden/` — golden artifacts grounded in real source-repo episodes (good phase review, good GO/NO_GO decision, good PR review, good eval spec, good tool-discovery report, good HARNESS.yaml, good project-state update). Use when a procedure is ambiguous in the abstract. |
| `datasets/` | JSONL records, one per line: teacher examples (`TE-###`), failure modes (`FM-###`), edge cases (`EC-###`), routing examples (`RE-###`). Retrieval-by-ID only — never bulk-read (L4 rule 4). |
| `prompts/` | Reusable prompt fragments distilled from observable work orders and command frontmatter (task router, phase review, PR review, tool discovery, boundary review, weak-model bootstrap). Never hidden internals. |
| `validation/` | Smoke tests and consistency checks for THIS harness (frontmatter shape, route-file existence, dataset record shape, retrieval smoke test). Run after edits. |
| `memory/` | `project_state.md` (the living state record, updated per `operating_model/project_memory_policy.yaml`) plus append-only correction and friction records. Corrections append, never overwrite (L1 #2, #9). |
| `schemas/` | Record shapes: dataset record schemas, required frontmatter fields. Use when writing new records. |
| `docs/` | Meta-documentation: `publication_status.md` (PUBLIC status + public-safety review checklist), `codebase_memory_indexing.md` (how to index/search this repo), `retrieval_smoke_test.md` (post-edit retrieval verification), `ab_test_protocol.md` (future-work A/B design), `codex-delegation-policy.md` (canonical delegation policy), `ai_review_adaptive_harness_integration.md` (the adaptive layer's contract). |
| `.gitignore` | The required ignore set (secrets, env files, caches, OS junk, scratch). Never weaken it. |

Directories may be populated incrementally by later distillation rounds; a
listed directory that does not exist yet means that layer has no content
yet — record the gap via `ROUTE-memory-update` if a route needs it.

Source-repo pointers (outside this repo, read-only): the observable
artifacts everything here is distilled from live at
`method-harness-compiler/` — `docs/`, `schemas/`, `scripts/`, `tests/`,
`examples/`, and `git log` (distillation baseline: commit `965c68e`).
