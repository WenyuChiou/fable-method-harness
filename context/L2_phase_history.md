---
id: L2-phase-history
layer: context
purpose: The COLD half of L2 — full milestone table, the two N=2 NULL gate narratives with per-arm scores, and the Phase-3 deliverable chronicle; split out 2026-07-09 so the per-task start ladder loads only L2's hot state (audit: 71% of L2 was history read by every route).
read_when: You need the full historical account — how a milestone shipped, the exact N=2 gate arms/scores, or the Phase-3 build chronology. NOT part of any route's start ladder; L2_current_phase.md carries the load-bearing summary.
depends_on: [context/L2_current_phase.md]
used_by: [ROUTE-phase-review]
tags: [phase, history, milestones, gates, cold-reference]
retrieval_keywords: [phase history, milestone table, N=2 gate story, gate v2 null, arm scores, phase 3 chronicle, what shipped when, project history]
---

# L2 — Phase History (cold reference)

Split from `L2_current_phase.md` (2026-07-09): every route's start ladder
reads L2, and ~71% of it was this history. The HOT file keeps the
load-bearing summary and the honesty anchors; the full account lives here
and loads only on demand.

Snapshot provenance: as of **2026-07-06, source repo at commit `0b8e4f8`**
(verified against the source repo's git log; reconciled from the retired
old-clone worktree plus records PH-019..PH-028). The AD-022 repositioning
(record PH-030) was decided 2026-07-06 by Fable under explicit user delegation
「做你認為最好的」; **user retains veto**. Source-repo decision record: the
repositioning ADR in `method-harness-compiler` (landed in the 2026-07-06
orchestrated round, Lane 1).

## Milestone table

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
| **Phase 3 — evidence and methodology extraction** | **RE-GATED (AD-022, 2026-07-06): design-only CONDITIONAL_GO.** (History: work order `2ad438b`; its original CONDITIONAL_GO collapsed when arm (a) failed (ARCH-1); v2 gate also NULL.) |

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

## The N=2 gate story — two independent blinded NULLs

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

## Phase-3 deliverable chronicle (design-only CONDITIONAL_GO era)

**Design deliverables COMMITTED 2026-07-07 (mhc `c316113`, CI green;
PH-031):** `docs/design/phase3_evidence_extraction_design.md` (S0–S5
pure-code gates, V1–V9), `phase3_source_set_protocol.md` (commit-A
freeze, no-swap), `phase3_adversarial_audit_harness.md` (check 0 + A–D,
C_raw/C_shipped population pins). Twice adversarially reviewed; 3 P1 +
7 sentence-level findings all closed. **RATIFIED by user 2026-07-07
(AD-023). Audit instrument 0.2.0 BUILT + calibration CLEAN (mhc
`d687dec`, CI green; PH-032): 17/17 §10.2 assertions, zero
fabrication-class false positives, criterion 1 UNSCORED by design →
NO_GO, no GO claimed. Spec-vs-spec collision resolved strict (AD-024
machine-readable-verbatim convention). SOURCE SET FROZEN 2026-07-07
(commit A `d0fb3ef`, tag `phase3-freeze-A`, CI green; AD-025/PH-033):
held-out subject Jeff Bezos, 35 sources (cal 22 + Bezos 13, 10F/3U),
every I1 probe orchestrator-run via real WebFetch; NO-SWAP binding.
EXTRACTOR BUILT end-to-end 2026-07-07 (build plan v2 mhc `a3ef65a`;
B0–B7 all shipped, code-reviewer APPROVE + CI green each; PH-034/LL-024;
suite 792→953; B7 tip `36bc5b6`). The whole pipeline runs, produces a
correct verdict, and fabrication fails closed at every stage; an
automated run → NO_GO (used_for still TODO_FILL), a simulated human
S4-clear → BUILD_GATE PASS (NO_GO is package-quality-driven, not
hardwired).**

Observable entry expectations, from how Phases 1–2 were run: an architect
work order BEFORE execution (exists: `2ad438b`); a falsifiable gate defined
BEFORE automation (the Phase-2 precedent is the fixture-regeneration gate —
deterministic coverage metrics against the 3 shipped packages, floors
pinned as regression tests); generators emit `.generated.yaml` DRAFTS with
`TODO_FILL`, never fabricated content; every claim about a source cited to
a fetched URL with honest unverified/unreachable ledgers.
