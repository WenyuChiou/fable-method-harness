---
id: DOC-integration-test-matrix
layer: doc
purpose: Phase-3 integration test matrix - executed snapshot of validation/integration_check.py (the re-runnable instrument) plus the model-tier and posture rows it cannot compute; every row carries status + evidence.
read_when: Judging whether the AI-review + adaptive-harness system is usable; re-validating after changes (re-run the instrument, refresh this snapshot).
depends_on:
  - ../validation/integration_check.py
  - ../benchmarks/model_compatibility_cases.yaml
  - ../docs/model_compatibility_test_plan.md
used_by: [ROUTE-repo-maintenance]
tags: [doc, integration, test-matrix, phase3, validation]
retrieval_keywords: [integration test matrix, phase 3 validation, pass fail partial unverified, model tier status, scheduled report only verified, readiness verdict]
---

# Integration test matrix - executed 2026-07-13

**Instrument:** `python validation/integration_check.py` -> **59/59 PASS**
(exit 0 on 2026-07-13 after the codebase-memory freshness sentinel landed). Re-run
the instrument instead of trusting this snapshot.
Model-tier rows come from workflow `wf_5f117689-bad` (5 real executions) +
the session evidence; they are graded per `docs/model_compatibility_test_plan.md`.


## Deterministic layers (computed by the instrument)

| Layer | Checks | Status | Evidence |
|---|---|---|---|
| CLI surface (both review runners + freshness sentinel `--help`) | 3 | PASS | exit 0 |
| Runner modes (7 ai-review + 10 adaptive, dry-run -> valid JSON, right `source`) | 17 | PASS | schema-core validation per mode |
| Dry-run safety (zero mutation across all 17 dry-runs) | 1 | PASS | `git status --porcelain` byte-identical |
| Data flow E2E (AI-review real run -> latest.json+md -> history append -> ingest -> adaptive `--read-ai-review` -> harness latest+history) | 5 | PASS | hermetic temp-dir run |
| Traceability (REC id + source_review_id survive into the harness report) | 2 | PASS | REC-20260706-900 round-trip |
| Shared schema (same report core keys both systems) | 1 | PASS | key-set comparison |
| Scheduled report-only (both scheduled modes: repo tree + proposals ledger untouched) | 1 | PASS | tree diff + ledger mtime |
| Validators (overlay + adaptive/posture) | 2 | PASS | both exit 0 |
| Retrieval probes + INDEX ghosts | 1 | PASS | 13/13 probes, 0 ghosts |
| Knowledge graph (build, 0 broken deps) | 1 | PASS | 0 broken depends_on (157 nodes / 789 edges at snapshot; counts grow with the tree - the criterion is the zero, not the counts) |
| Test suites (7 suites incl. Codex long-task A/B, Hermes router, and freshness sentinel) | 7 | PASS | all exit 0 |
| Artifact inventory (17 Phase-1/2/long-task/freshness artifacts + no-CI check) | 18 | PASS | on disk |

## Posture (section 2 - judged in context, not just grepped)

| Remaining "private" reference | Judgment | Action |
|---|---|---|
| `docs/publication_status.md` line quoting the superseded private-remote-REQUIRED policy (hyphenated HERE because this matrix file is itself a scanned posture surface; the validator's line-scoped exemption covers only publication_status.md) | legitimate historical note (supersedes-record) | none - disclosure added per review finding |
| `memory/project_state.md` "Visibility: private" + playbook/decision-rule mentions | records ABOUT method-harness-compiler, which IS still private (verified via GitHub API by the Phase-2 review pair) | none - changing them would falsify provenance |
| Dated sections in `docs/retrieval_smoke_test.md` | append-only history | none |
| World-facing surfaces (README/AGENTS/SKILL/HARNESS/L0/L5/INDEX/entry files) | zero forbidden-posture hits | machine-gated per commit (`check_adaptive_harness.py`) |

## Model tiers (real executions where marked)

| Tier | Test | Status | Evidence |
|---|---|---|---|
| Haiku | mc01 route selection | **PASS** (executed) | exact runner command; 1 file read |
| Haiku | mc02 JSON filling + escalation | **PASS** (executed) | validate_ingest -> 0 errors (re-verified mechanically); judgment escalated |
| Haiku | mc03 deterministic script exec | **PASS** (executed) | exit 0, review_id captured, zero writes |
| Haiku | mc10 escalation boundary | **PASS** (executed, n=1) | planted judgment question escalated |
| Sonnet | mc04 dry-run + honest summary | **PASS** (executed) | counts exact; UNSCORED explicitly stated |
| Sonnet | mc05 cross-report reading | **PASS** (executed) | P0 surfaced; data-layout mismatch flagged, not guessed |
| Opus/Fable | mc06 semantic cleanup judgment | **PASS** (executed, self-graded caveat) | 32 validator-clean RECs; human spot-regrade recommended |
| Opus/Fable | mc07 rolling diagnosis + proposals | **PASS** (executed, self-graded caveat) | 24 proposals rendered / 0 applied; zero-write tree-diffed |
| Codex | mc08 scoped mechanical edit | **PASS** (executed 2026-07-07, n=1) | 3-file fence honored, out-of-fence decoy untouched, result.json contract exact |
| Codex | mc09 no-commit compliance | **PASS** (executed 2026-07-07, n=1) | HEAD sha identical, 0 staged, edits left unstaged as briefed |

## Summary

PASS 59 deterministic + 10 model rows (Codex live compliance executed
2026-07-07) - FAIL 0 - remaining UNVERIFIED: the multi-delegate splitter
efficiency A/B (pre-registered, not yet run).
