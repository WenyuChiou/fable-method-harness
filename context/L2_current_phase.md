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

Snapshot as of **2026-07-06, source repo at commit `0b8e4f8`** (verified
against the source repo's git log; reconciled from the retired old-clone
worktree plus records PH-019..PH-028). **Major events since the previous
committed snapshot: N=2 gate arm (a) RAN — NULL (`26d24df`) — AND the
revised gate v2 RAN — NULL on BOTH claims (`0b8e4f8`).**

> **UPDATE 2026-07-06 (later round) — the strategic decision is RESOLVED
> (AD-022 / PH-030).** The former TOP-priority "strategic decision pending
> the human" is closed via REPOSITIONING: the product claim is the
> auditable evidence/policy BUNDLE + toolchain (package standard, `phc
> validate/eval/audit`, provenance discipline, computed scorecards) — NOT
> behavioral superiority of harness structure over prompts; the "expert
> packs you can audit" wedge (design review 2026-07-01, B9) becomes primary
> positioning. Outcome-correctness (evaluation_framework Category 7) is
> now the REQUIRED axis for any future capability claim. Phase 3 is
> RE-GATED to **design-only CONDITIONAL_GO** (criteria below). Provenance:
> decided 2026-07-06 by Fable under explicit user delegation
> 「做你認為最好的」; **user retains veto**. Source-repo decision record:
> the repositioning ADR in `method-harness-compiler` (lands in this same
> 2026-07-06 orchestrated round, Lane 1). Honesty bound: the two NULLs
> below remain published and stated AS-IS — the repositioning claims
> nothing beyond the measured citation/policy-naming edge.

## Where the project actually is

| Milestone | Status |
|---|---|
| Phase 0 — spec-first package standard | DONE (Day 1, commit `f4c826f`) |
| M1a — installable plugin + computed scorecard + transcripts | DONE (2026-07-01) |
| M1b — second demo, N=2 zero-schema-edit gate | DONE, arm (b) PASS (`docs/n2_gate_report.md`) |
| M1c — grader v2 + `phc` CLI + external audit wedge | DONE |
| M1d — Category-7 retracted-paper outcome eval | EXECUTED AS PILOT (proof-of-instrument, no accuracy claim) |
| N=3 — third demo via `phc new` dogfood, zero schema edits | DONE |
| M2a — tool-discovery research (27 sources scored, metadata-only) | DONE (2026-07-02, commit `510b79f`) |
| M2b — first-wave builder primitives + fixture-regeneration gate | SHIPPED, gate-measured (commit `91b982b`) |
| **Phase 3 — evidence and methodology extraction** | **RE-GATED (AD-022, 2026-07-06): design-only CONDITIONAL_GO — DESIGN allowed under the frozen extraction-quality criteria; BUILDING stays forbidden until the criteria pass.** (History: work order `2ad438b`; its original CONDITIONAL_GO collapsed when arm (a) failed (ARCH-1); v2 gate also NULL.) |

Phases 0–2 are done *through the first-wave builder primitives at
`91b982b`*, plus **BOTH second-wave registry adapters SHIPPED**
(`FindSkillsAdapter` `b1310b5` + `GitHubSkillSearchAdapter` `41842ce`;
recommender consumes `ALL_ADAPTERS`; url-never-fabricated,
safety_label/zero-curation → no-credit, token-gated-graceful-degrade,
public-repos-only discipline), **ModelRoutingPolicy wired into the runner**
(`89e503b`: eval-time schema + S1 five-tiers / S2 escalation-terminus / S3
unambiguous-routing in `run_static`, `build_scorecard`, `phc validate`,
external audit), and **tool-fit-scorer refinement SHIPPED** (`571e9de`:
per-card `fit` block — capability_relevance / permission_fit
[over_privileged Tier-4 flag] / risk_posture / source_trust). **ALL
unblocked Phase-2 items are done**; the only remaining Phase-2 candidate is
an OPTIONAL full model-router (task→tier dispatch). Suite: **768 passing,
2 skipped** (`571e9de`); CI green.

**The N=2 gate story — two independent blinded NULLs:**

- **Arm (a) RAN 2026-07-03** under its pre-registered protocol → **NULL,
  gate NOT passed** (`26d24df`, `docs/evals/n2_arm_a_runs/report.md`):
  harness 6/6 but persona 5/6 — the ≤2/6 persona assumption was
  miscalibrated; arms tie on 5 of 6 tests, differing only on t04
  evidence-citation.
- The revision was designed (`521aab5`), its freeze artifacts drafted
  (`75f503b`), thresholds **owner-ratified** (`38b1748`), and **gate v2
  RAN 2026-07-04 → NULL on BOTH claims** (`0b8e4f8`,
  `docs/evals/n2_gate_v2_runs/report.md`): PRODUCT (C vs A) Δ=0.33 < 0.7;
  STRUCTURE (C vs B) Δ=0.17 < 0.3 — persona + the SAME evidence list scores
  1.83 vs harness 2.00 (means A=1.67 / B=1.83 / C=2.00), i.e. the harness
  is empirically "data + packaging, not structure". No veto fired.

Per the phase-gate doctrine both NULLs are **published, not re-run**. The
central "compiled harness beats a naive prompt" claim is **NOT SUPPORTED**
by two independent blinded evals. The honest next step was **STRATEGIC, not
a third behavioral gate**: (a) reposition around the evidence/policy bundle
the harness demonstrably provides, (b) test a different value axis the
behavioral gates don't reach (outcome correctness / auditability at scale /
consistency across authors), or (c) accept the null.

**RESOLVED 2026-07-06 (AD-022): option (a) — repositioning — was taken,
with (b)'s outcome-correctness axis adopted as the mandatory bar for any
future capability claim.** The NULL results themselves stand unchanged.

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

## Required outputs of the next phase (Phase 3, per `development_plan.md` — design-only CONDITIONAL_GO per AD-022; do NOT build until the frozen criteria pass)

- [ ] Source discovery
- [ ] Evidence card builder
- [ ] Principle extractor
- [ ] Source-to-principle mapper
- [ ] Attribution classifier

Observable entry expectations, from how Phases 1–2 were run: an architect
work order BEFORE execution (exists: `2ad438b`); a falsifiable gate defined
BEFORE automation (the Phase-2 precedent is the fixture-regeneration gate —
deterministic coverage metrics against the 3 shipped packages, floors
pinned as regression tests); generators emit `.generated.yaml` DRAFTS with
`TODO_FILL`, never fabricated content; every claim about a source cited to
a fetched URL with honest unverified/unreachable ledgers.

## If your task conflicts with this file

Trust the source repo's `docs/development_plan.md` over this snapshot,
report the drift, and update this file in the same round.
