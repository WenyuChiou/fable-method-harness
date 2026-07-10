---
id: L2-current-phase
layer: context
purpose: The source project's real current phase — what is allowed and forbidden right now
read_when: Start of every task, immediately after L0 — before classifying or acting
depends_on: [context/L0_bootstrap.md]
used_by: [ROUTE-phase-review, ROUTE-tool-discovery, ROUTE-pr-review, ROUTE-eval-design, ROUTE-memory-update, ROUTE-runtime-export, ROUTE-repo-maintenance, ROUTE-ab-test-design]
tags: [phase, current-state, scope, allowed, forbidden]
retrieval_keywords: [current phase, what phase, allowed, forbidden, scope, phase 3, next milestone, paused state]
---

# L2 — Current Phase

> **MAINTENANCE RULE (per `operating_model/project_memory_policy.yaml`):
> this file MUST be updated at every phase transition.** A stale L2 is the harness's worst
> failure mode — every route reads it first. Update it in the same round
> that updates `docs/development_plan.md` in the source repo.

Snapshot as of **2026-07-06, source repo at commit `0b8e4f8`**. This file
is the HOT half: current state, allowed/forbidden, and what Phase 3 still
owes. The full milestone table, the N=2 gate narratives with per-arm
scores, and the Phase-3 deliverable chronicle live in
`context/L2_phase_history.md` (split 2026-07-09 — every route loads this
file, and ~71% of it was history; load the history file only on demand).

## Where the project actually is (summary — history file has the account)

- Phases 0–2: **DONE and gate-measured** through `91b982b`, plus both
  second-wave registry adapters, ModelRoutingPolicy in the runner, and the
  tool-fit scorer. Suite 768 passing / 2 skipped; CI green. Only OPTIONAL
  Phase-2 remainder: a full model-router (task→tier dispatch).
- **Honesty anchor (unchanged, published):** two independent blinded N=2
  gates ran → **NULL both times** (arm (a) `26d24df`; gate v2 `0b8e4f8`,
  NULL on BOTH claims). The central "compiled harness beats a naive
  prompt" claim is **NOT SUPPORTED**; the NULLs are published, not re-run.
- **AD-022 (2026-07-06, user retains veto): repositioning taken** — the
  product claim is the auditable evidence/policy BUNDLE + toolchain, NOT
  behavioral superiority; outcome-correctness (Category 7) is the REQUIRED
  axis for any future capability claim. **Phase 3 is design-only
  CONDITIONAL_GO** under frozen extraction-quality criteria.

## Current state — allowed vs forbidden (updated 2026-07-06, post-AD-022)

**Allowed (no further gate required):**

- **Phase-3 DESIGN under AD-022's frozen-criteria frame** — architecting
  the no-fabrication code-gate for evidence extraction, and drafting/
  freezing the falsifiable extraction-quality criteria BEFORE any build:
  on a pre-registered source set, machine-extracted evidence cards must
  meet the hand-authored bar — verified-ratio ≥ 0.9 on fetchable sources,
  ZERO fabricated locators under adversarial audit, 100% quote-cap and
  attribution-cap compliance. Failure on ANY criterion = extraction
  automation NO_GO again.

- Reading, auditing, and re-verifying any shipped artifact (re-run
  `scripts/run_evals.py`, `scripts/generator_gate.py`, pytest).
- Recording friction, corrections, and memory updates (append-only).
- Repo maintenance: locale sync, CI, test-suite upkeep, doc drift fixes —
  with the review gates of ROUTE-pr-review.
- The one remaining OPTIONAL Phase-2 item (full model-router, task→tier
  dispatch) — it extends a shipped, gate-measured wave.
- Designing (not running) future evals and A/B protocols —
  pre-registration artifacts are welcome; runs are not.

**Forbidden:**

- **BUILDING Phase-3 extraction automation** (source discovery,
  evidence-card builder, principle extractor, source-to-principle mapper,
  attribution classifier). The strategic decision is resolved (AD-022) and
  DESIGN is allowed, but **construction stays forbidden until the frozen
  extraction-quality criteria (above) are ratified and then PASS** on the
  pre-registered source set. History: work order `2ad438b`; arm (a) NULL
  (ARCH-1) and v2 gate NULL on both claims (`0b8e4f8`). **Do NOT design or
  run a third behavioral gate — behavioral-superiority claims are closed;
  any future capability claim must be outcome-grounded (Category 7) and
  pre-registered (AD-022 part 2).**
- Any new capability claim (in README, docs, positioning, or eval reports)
  implying the bundle is superior beyond the measured citation /
  policy-naming edge; any weakening of the published NULL language.
- Any schema edit outside a logged `CHANGELOG_STANDARD.md` revision with
  friction-ID citations and mutation regression tests.
- Hand-editing any computed scorecard; guessing any UNSCORED value.
- Executing, installing, or signing up for any discovered tool (spec 9.5).
- Fabricating evidence to fill `TODO_FILL` markers.
- Drawing capability/accuracy claims from the n=3 Category-7 pilot.

## Required outputs of the next phase (Phase 3 — design-only CONDITIONAL_GO per AD-022; do NOT build until the frozen criteria pass)

Status (full chronicle in `context/L2_phase_history.md`): design RATIFIED
(AD-023), audit instrument 0.2.0 built + calibration clean (PH-032),
source set FROZEN with held-out subject (AD-025, tag `phase3-freeze-A`),
and the extractor is BUILT end-to-end (B0–B7, suite 953, PH-034) with
fabrication failing closed at every stage. Each module stays functionally
gated — **a real GO still needs `--live` fetch + a real LLM
segmenter/proposer + the human S4 pass, none automatable, and the 3 frozen
criteria must pass on THAT run:**

- [x] Source discovery / fetch ledger — B1 M3a (`e46e470`)
- [x] Evidence card builder — B3 M3b (`4099e59`)
- [x] Principle extractor — B5 M3c (`75aab07`)
- [x] Source-to-principle mapper — B6 M3d (`857eecb`)
- [x] Attribution classifier — B4 M3e (`b95acce`)
- [x] (+ B0 skeleton, B2 V1–V9 gate, B7 binding runner)

## If your task conflicts with this file

Trust the source repo's `docs/development_plan.md` over this snapshot,
report the drift, and update this file in the same round.
