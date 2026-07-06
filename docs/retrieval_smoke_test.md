---
id: DOC-retrieval-smoke-test
layer: doc
purpose: Post-edit verification that the routing and retrieval surface still works
read_when: After any edit round, after re-indexing, and as a gate item before any public flip
depends_on: [ROUTES.yaml, context/L3_task_router.md, docs/codebase_memory_indexing.md]
used_by: [ROUTE-repo-maintenance]
tags: [smoke-test, validation, retrieval, routing]
retrieval_keywords: [smoke test, retrieval test, probe queries, expected files, verify routing]
---

# Retrieval Smoke Test

A falsifiable check that the harness's retrieval surface (frontmatter +
`ROUTES.yaml` + stable IDs) actually routes a fresh agent to the right
files. Run it after every edit round and after every re-index. This is the
harness's own "regenerate-the-fixtures" gate: measured, not claimed.

## Procedure

1. **Re-index first** (if using codebase-memory MCP;
   `docs/codebase_memory_indexing.md` §2). If grepping, skip to step 2.
2. **Run the probe set below** — each probe is a realistic query phrase.
   Record, for each probe, the top files returned (index search) or the
   files whose frontmatter matches (grep on `retrieval_keywords` / IDs).
3. **Compare against the expected file set.** A probe PASSES iff every
   expected file appears in its results. Partial credit is a FAIL.
4. **Route-list existence check:** for each of the 8 routes in
   `ROUTES.yaml`, verify every listed file exists on disk (a dangling
   route entry is an automatic FAIL — the dangling-reference class of bug
   the source project hit at N=2 friction F4).
5. **Record the result** — PASS/FAIL per probe, appended to `memory/`
   (never overwrite a previous run's record). On any FAIL: fix the
   file's `retrieval_keywords` or the route list, re-index, re-run the
   FAILED probes. Never fix a miss by weakening the expectation.

## Probe set and expected files

| # | Probe query | Expected file(s) |
|---|---|---|
| P1 | "start here / how do I use this repo" | `context/L0_bootstrap.md`, `README.md` |
| P2 | "what phase are we in / what is forbidden right now" | `context/L2_current_phase.md` |
| P3 | "which route does my task take" | `context/L3_task_router.md`, `ROUTES.yaml` |
| P4 | "how much of the repo may I read / full context load" | `context/L4_progressive_disclosure_policy.md` |
| P5 | "project non-goals / no impersonation principle" | `context/L1_project_constitution.md` |
| P6 | "where does X live / directory map" | `context/L5_full_context_map.md` |
| P7 | "make this repo public / review checklist" | `docs/private_repo_setup.md` |
| P8 | "index this repo / re-index after edits" | `docs/codebase_memory_indexing.md` |
| P9 | "A/B experiment arms / research question" | `docs/ab_test_protocol.md` |
| P10 | an exact stable ID from each dataset (`TE-001`, `FM-001`, `EC-001`, `RE-001`) | the corresponding `datasets/*.jsonl` record |
| P11 | one `ROUTE-*` id (rotate through all 8 across runs) | its entry in `ROUTES.yaml` + the route's own file if one exists |
| P12 | "phase gate GO NO_GO procedure" | the phase-review playbook/rubric listed by `ROUTE-phase-review` in `ROUTES.yaml` |

Probes P10–P12 reference files owned by other distillation lanes; if a
target does not exist yet, record the probe as **UNSCORED (target absent)**
— never as PASS. UNSCORED-never-guessed is the source project's rule and
it applies to this harness verbatim.

## Pass bar

- **PASS:** all present-target probes pass and zero route entries dangle.
- **CONDITIONAL:** only UNSCORED absences remain (lanes not yet written).
- **FAIL:** any present-target probe misses, or any route entry dangles —
  the harness must not be relied on (or published) in this state.

---

## Executed 2026-07-02 — route-resolution smoke run (SPEC §8)

**Scope:** simulated a fresh model asked to *"review a Phase 1 tool
discovery plan"*, following only the on-disk progressive-disclosure rules
(L0 → L2 → L3 → `ROUTES.yaml` → route resolution). Route-list existence
(procedure step 4) was run for **all 8 routes**. The P1–P12 probe grid was
**NOT RUN** this round and is recorded as such — not claimed.

### Resolution walk (ROUTE-tool-discovery)

| Order | File | Tier | Why it is read |
|---|---|---|---|
| 1 | `context/L0_bootstrap.md` | first | L0 is the pinned entrypoint; gives the read-next ladder and the do-not-read-the-whole-repo contract |
| 2 | `context/L2_current_phase.md` | first | L0 step 1; confirms discovery work is metadata-only and tool execution is forbidden (spec 9.5) |
| 3 | `context/L3_task_router.md` | first | L0 step 2; classifies the task → `ROUTE-tool-discovery` |
| 4 | `ROUTES.yaml` | first | L0 step 3; the exact file list — never improvised |
| 5 | `playbooks/phase1_tool_discovery.md` | required | the procedure the plan under review must follow (allowed/forbidden work, acceptance criteria) |
| 6 | `rubrics/tool_discovery_rubric.yaml` | required | TD-1..TD-6 scoring criteria for the plan's citation/ledger discipline |
| 7 | `rubrics/tool_boundary_rubric.yaml` | required | TB-1..TB-6 execution-boundary criteria (discovery-without-execution, computed risk) |
| 8 | `examples/golden/good_tool_discovery_report.md` | required | calibration anchor — what a passing deliverable looks like |
| 9 | `prompts/tool_discovery_prompt.md` | required | the per-run script the plan should be consistent with |
| 10 | `validation/self_checklists/tool_discovery_checklist.md` | required | CHECK-tool-discovery must complete before returning |
| — | `datasets/failure_modes.yaml`, `datasets/edge_cases.yaml`, `examples/bad/…`, `examples/critiques/…`, `prompts/boundary_review_prompt.md`, `playbooks/pr_review_playbook.md`, `operating_model/model_routing_policy.yaml` | optional | open only with a stated one-line reason (L4 rule 3) |

### Checks — first pass

| Check | Result | Finding |
|---|---|---|
| (a) resolved set vs SPEC expected set | **FAIL** | `datasets/edge_cases.yaml` missing from the route's optional list, despite the SPEC expecting it AND `edge_cases.yaml` itself declaring `used_by: ROUTE-tool-discovery` (asymmetric link) |
| (b) every referenced path real on disk | **PASS** | all listed paths existed |
| (c) completable without off-route reads | **FAIL** | `phase1_tool_discovery.md` acceptance criteria force a chase to `./pr_review_playbook.md` (independent live re-verification procedure) — outside the resolved set; also in its frontmatter `depends_on` |

### Fixes applied (same round)

1. `ROUTES.yaml` / ROUTE-tool-discovery optional: **added
   `datasets/edge_cases.yaml`** (fixes a) and **added
   `playbooks/pr_review_playbook.md`** (fixes c — the forced chase now has
   a sanctioned optional slot).
2. `ROUTES.yaml` / ROUTE-pr-review optional: **added
   `playbooks/phase6_evaluation_runner.md`** (same dangling-dependency
   class, found in the spot-run: `pr_review_playbook.md` points to it for
   the grader-beneficiary separation rule and lists it in `depends_on`).
3. `context/L3_task_router.md`: the ROUTE-tool-discovery row now names
   *reviewing* a discovery plan/report explicitly ("subject beats verb"),
   because "review a Phase 1 … plan" carried a real misclassification risk
   toward `ROUTE-phase-review` on the "phase"/"plan" keywords alone.

### Checks — re-run after fixes

| Check | ROUTE-tool-discovery | ROUTE-pr-review (spot-run) |
|---|---|---|
| (a) matches expected set | **PASS** — SPEC set fully contained in the correct tiers (route also carries its own prompt/checklist/bad-example extras, all frontmatter-linked within the route) | **PASS** — set matches the route's declared list |
| (b) paths real on disk | **PASS** — YAML-parsed sweep, all 8 routes, 0 dangling entries | **PASS** (same sweep) |
| (c) no forced off-route reads | **PASS** — remaining out-of-set pointers are non-blocking: `phase0_static_package_standard.md` (ancestry only; B12 summarized inline), `context/L4…` (escalation policy; operative rule inlined in L0/ROUTES), source-repo artifacts (provenance citations, not reading requirements) | **PASS** — grader-separation rule stated inline; elaboration pointer now sanctioned as optional |

### Verdict: **PASS** (route-resolution scope) — after 3 fixes, this round.

### Noted, non-blocking (for the next ROUTE-repo-maintenance round)

- `examples/golden/good_tool_discovery_report.md` frontmatter `depends_on`
  points at a directory (`../../playbooks`), not a file — imprecise though
  not dangling.
- Procedure step 5 says results append to `memory/`; no dedicated smoke-run
  memory log exists yet, so this dated section is the append-only record of
  this run (friction noted, not silently absorbed).
- P1–P12 probe grid still owed a full run before any public flip.

---

## Executed 2026-07-02 — portable-core global-entry probe (core/ wiring round)

**Scope:** simulated *"Opus starts a large multi-agent (ultracode) task in
the research-hub repo, with this harness indexed globally"*. Resolution path
under test: global pointer → `core/GLOBAL_BOOTSTRAP.md` → PROJECT CHECK
(non-mhc) → `ROUTE-global-orchestration` in `ROUTES.yaml`. Checks were
COMPUTED by a script (52 assertions), not claimed; the P1–P12 mhc probe grid
was NOT RUN this round and is recorded as such.

### Resolution walk (ROUTE-global-orchestration)

| Order | File | Tier |
|---|---|---|
| 1 | `core/GLOBAL_BOOTSTRAP.md` | entry (route `start`; the ONLY start file — L0/L2/L3 ladder deliberately not loaded) |
| 2 | `ROUTES.yaml` | route resolution (`ROUTE-global-orchestration` entry) |
| 3 | `core/portable_operating_model.md` | required |
| 4 | `core/workflow_orchestration_playbook.md` | required |
| 5 | `core/portable_decision_rules.yaml` | required |
| — | 4 portable rubrics (`pr_review`, `maintainability`, `eval_quality`, `progressive_disclosure`) + `datasets/failure_modes.yaml` | optional — open only with a stated one-line reason |

### Checks

| Check | Result | Detail |
|---|---|---|
| (a) every referenced path exists on disk | **PASS** | 9/9 start+required+optional paths real |
| (b) reading set excludes ALL project-bound files (`context/L1`, `context/L2`, `playbooks/`, `phase*`, `memory/`) | **PASS** | zero matches in required AND optional tiers |
| (c) total required reading ≤ 6 files | **PASS** | 5 files (entry + ROUTES.yaml + 3 required) |
| (d) entrypoints list carries `core/GLOBAL_BOOTSTRAP.md` (`global_portable_entry`) | **PASS** | 4th entrypoint alongside BOOTSTRAP/AGENTS/SKILL |
| (e) all 9 routes conform to `schemas/route.schema.yaml`; zero dangling entries | **PASS** | schema extended this round (see fix 1) |
| (f) INDEX.yaml lists each core/ file exactly once, `layer: core`; all INDEX paths exist | **PASS** | 4 new entries |
| (g) core/ frontmatter carries all 8 keys | **PASS** | 3 md files + comment-style yaml |
| (h) UTF-8, no tabs, YAML parse on every edited file | **PASS** | 11 files |

### Fixes applied (same round)

1. `schemas/route.schema.yaml`: without a change, the new route would have
   FAILED its own declared validation (`task_type` enum lacked
   `global_orchestration`; `start` demanded `minItems: 3`). Extended
   additively — enum gains one value; `start` gains a `oneOf`
   (3-item ladder | exactly `["core/GLOBAL_BOOTSTRAP.md"]`) so the
   project-bound constraint is NOT loosened for the other 8 routes.
2. `core/GLOBAL_BOOTSTRAP.md`: added the back-reference naming
   `ROUTE-global-orchestration`, so the GLOBAL_BOOTSTRAP → route resolution
   is an on-disk link, not an implied one.
3. `HARNESS.yaml`: pinned route list and `layers:` were going stale
   (manifest omitted the new route and the `core` layer) — synced
   additively, per MT-5 index-matches-disk discipline.

### Verdict: **PASS** (portable-core scope) — 52/52 computed checks green.

### Noted, non-blocking

- The global wiring itself (the pointer in the user's global config that
  loads `core/GLOBAL_BOOTSTRAP.md`) lives OUTSIDE this repo and is
  UNVERIFIED by this probe — the probe verifies the harness side only.
- `datasets/failure_modes.yaml` sits in the route's optional tier; its
  records cite mhc artifacts, which is acceptable (provenance citations are
  not reading requirements — same class as the 2026-07-02 route-resolution
  run's check (c) note).

---

## Executed 2026-07-06 — Phase-1 AI-review surface probe (scoped)

**Scope:** the edit round adding the AI-review runner surface (2 schemas,
runner + test, mode prompts, codex policy, benchmark scaffold, 7 INDEX
entries). Checks COMPUTED by script (scratchpad smoke_probe.py — grep on
retrieval_keywords/content terms + INDEX ghost sweep), not claimed. The
P1–P12 mhc probe grid was NOT RUN this round (unchanged surface) and is
recorded as such.

### Checks

| Check | Result | Detail |
|---|---|---|
| 6 new-surface probes ("codex delegation policy tripwire", "ai review modes checklist ingest", "review report schema shared contract", "recommendation finding schema traceability", "ai review benchmark cases ab test", "ai review runner report-only") | **PASS 6/6** | every probe's expected file matched on all terms |
| INDEX.yaml ghost sweep (124 entries) | **PASS** | 0 entries point at missing files |
| ROUTES.yaml path references | **PASS** | via scripts/check_agent_artifacts.py, exit 0 (no route edits this round) |
| INDEX-matches-disk (reverse direction) | **KNOWN GAP** | 31 pre-existing unregistered files under distillation/orchestration_bench/ — now machine-detected every run by scripts/run_ai_review.py (index_drift); disposition tracked as OPT-20260706-001 (patch_proposal, human decision) |

### Verdict: **PASS** (scoped) — with the pre-existing orchestration_bench
INDEX gap explicitly carried as an open OPT item, not silently absorbed.
