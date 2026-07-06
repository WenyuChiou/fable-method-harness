# Pre-registration — Orchestration-Distillation Loop (Phase 0 minimal-viable)

> **STATUS: DRAFT — not yet frozen.** This must be git-committed with a hash *before the first
> Fable call* (the anti-p-hack anchor). Until `frozen_sha` below is filled + committed, no candidate
> is measured. Full plan: `scratchpad/distillation_design/orch_plan/` (audit.md = final tightened).

## Purpose
Test, empirically and honestly, whether a harness change that Fable proposes for ONE orchestration
dimension raises **plain Opus 4.8's** orchestration quality on **complex** tasks — and commit only
changes that measurably do. The loop: Fable proposes text → Opus measures (A₀ current-HEAD vs A₁
HEAD+edit) → observable-artifact feedback → Fable revises (≤3) → DONE (commit) or NULL (log).

## Honest prior (why this is a measurement, not a guaranteed win)
`distillation-log.md` DL-20260704-03 already showed the top candidate traits are **universal
frontier-model competence** (plain-Opus == plain-Fable, 100% harness-off on easy probes). So the
prior is that most Fable-specific controls will NOT transfer to Opus. **Expected yield: 0–2 DONEs,
several decisive nulls, one durable instrument. A clean net-zero is a valid, publishable result.**

## Pilot scope (minimal-viable — start with the cleanest dimension, expand only on signal)
| id | dimension | Fable behaviour (Round-1) | harness section it edits | status |
|---|---|---|---|---|
| **O-CLAIM** | claim-targeted verification — falsify the round's *actual deliverable claim*, not "tests pass"; read past truncation | `core/workflow_orchestration_playbook.md` §4 + §8 | **PILOT (Round-1's only gate-survivor, cleanest binary metric)** |
| O-GROUND | convert a soft goal into a falsifiable mechanism (pre-registered gate + mandated friction field) | §2 work-order / a new checklist | on-deck (H-A, the "strongest distillable idea") |
| O-HARDEN | pin anti-fabrication discipline INTO the delegated work-order | §2 | on-deck (H-B) |

Others (O-DECOMP/O-ALLOC/O-ELAB/O-LONG/O-CONTAM) deferred; add only if the pilot shows signal.

## Metrics (objective-dominant; the composite is capped by two vetoes)
- **M1** requirement-coverage · **M2** decomposition = *any valid topological order of the pinned
  dependency key* (NOT edit-distance to one canonical plan) · **M3** delegation-appropriateness
  (poison-leg delegated → **veto 0**) · **M4** parallel-coordination integrity · **M5**
  delegate-verification (objective trap-catch boolean + blind 1–5 claim-quality) · **M6** end-to-end
  success (**trap sprung AND shipped → veto 0**) · **M7** efficiency (paired cost, **never a maximand**).
- **Composite** = mean(M1..M6); M7 reported alongside; either veto caps the score.
- **O-CLAIM primary metric = M5 trap-catch (binary)**, guard = M6 no-false-done.

## The A/B (paired, blind, calibrated)
- **A₀** = current-HEAD harness + Opus (the control — nothing is provable without it).
- **A₁** = HEAD + the one dimension edit.
- **A_c** = ceremony placebo (format-matched, content-null) — **TRIGGERED only** when 0 < A₁−A₀ < 2·MME
  (sparse, load-bearing for budget). Admissible as evidence only after the placebo-neutrality pre-check passes.
- Paired per-task diffs on identical fixtures; transcripts arm-stripped + shuffled before grading.
- **[moving-baseline fix] Re-calibrate each dimension's task set against the CURRENT HEAD immediately
  before that dimension's window** (every committed DONE raises HEAD; a set calibrated once goes stale).
  Keep only tasks where current-HEAD plain-Opus lands in **[0.15, 0.85]** (prefer 0.3–0.7). Ceiling
  (>0.85) → log `baseline(ceiling)`, skip before any Fable call. Floor (<0.25 both arms) → set
  mis-specified, rebuild.

## Statistics (frozen)
- Wilcoxon signed-rank on paired diffs; pseudo-median shift + 95% CI; paired Cliff's delta.
- **MME (minimum meaningful effect): ≥0.08 composite / ≥0.20 binary.**
- **Hard floor n = 24** decisive-contrast tasks (a pilot may RAISE, never lower).
- **k schedule:** screening/calibration k=1; decisive contrast k=3 median, run in randomized order under a
  **sequential test — stop as soon as the paired CI excludes the MME (positive) or crosses the
  pre-registered futility boundary (null).** Only ambiguous dimensions pay the full 24×k×3-arm cost.
- Per-dimension 4-task panels are **descriptive, never inferential**; only the pooled decisive contrast earns an inferential claim.

## DONE / NULL / STOP
- **DONE (commit) iff ALL:** (1) decisive positive (A₁ beats A₀ on the primary, delta ≥ MME, CI excludes 0,
  at n=24); (2) **held-out confirmation** on the fresh 2-variant set authored after the edit froze;
  (3) no guard-metric regression (false-done / on-disk-verify rate, every round); (4) **survives A_c**
  (a lift ≈ A_c is a null — the win was words).
- **[anti-thrash] Shared-section regression lock:** when a new dimension edits a section a prior DONE also
  touched, re-run every prior DONE's decisive contrast against the new combined text; a regression below
  its MME → REQUEST_CHANGES to Fable or abandon the new dimension.
- **ABANDONED → NULL iff:** k=3 revises without lift · `baseline(ceiling)` · floor.
- **[program stop]** If the top-3 leverage dimensions (O-CLAIM, O-GROUND, O-HARDEN) all null decisively →
  **STOP**; the harness is orchestration-mature; ship the negative via `ROUTE-memory-update`. Net-zero is success, not a failure to fix.
- **Hard program budget:** ≤ N committed DONEs per window + a max-rounds-per-window cap; hitting either forces a postmortem before more edits.

## Feedback to Fable (refusal-safe — observable artifacts ONLY)
A bug-report against the text Fable shipped: metric delta + CI + n (runner-computed, never hand-asserted)
+ the failure as **observable artifact deltas only** — "on k/N tasks the required tool call was absent /
the file diff was wrong / the consumer test went red" — **NEVER a narration of the lane's reasoning**
(that edges into the reasoning-extraction refusal Anthropic warns of). Plus the counter-example that worked.
Never contains: distill / working-style / introspect / explain-your-reasoning / be-rigorous-careful-honest.
Never load the distilled skill onto Fable.

## Guards (nothing commits untested)
- Commit-gated-by-scorecard: an edit commit is admissible only with a sha-bound
  `orchestration_scorecard_computed.yaml` proving A₁>A₀ at the floor on iterate AND held-out, passing the
  regression lock. (Runner-computed; no hand-typed verdict — the runner does not exist yet, build it in Phase 0.)
- Pre-registration hash freeze: the cited scorecard must reference `frozen_sha`; any metric change re-freezes + re-runs from scratch.
- DONE edits go to `core/workflow_orchestration_playbook.md` / `prompts/claude-code-orchestration.md`
  (playbook layer) — **NEVER `core/portable_*`** (always-loaded layer). Nulls → append-only
  `distillation/distillation-log.md` + `datasets/failure_modes.yaml`. Governance `code-reviewer` round + independent re-verification per DONE.

## Freeze block (fill + commit before the first Fable call)
```
frozen_sha: TODO_FILL_AT_FREEZE
frozen_date: TODO
runner_built_and_tested: false      # BLOCKING: no measurement until true
placebo_neutrality_checked: false   # BLOCKING for A_c admissibility
tasks_calibrated_in_band: []        # per-dimension, against current HEAD
```
