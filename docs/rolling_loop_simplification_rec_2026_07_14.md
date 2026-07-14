# REC-20260714-001 — Simplify the rolling loop's linkage machinery (propose-only)

- **Status:** proposed — `requires_human_approval: true`. Nothing is
  dismantled by this document; closure follows the repo convention
  (a commit whose message says `applies REC-20260714-001`).
- **Opened by:** the frozen consequence of the round-4 A/B
  (`ai_review_only_vs_ai_review_plus_adaptive_harness`, executed
  2026-07-14, **B-loses**). Pre-registration and raw grades are
  operator-side in `audits/harness-optimization-2026-07/rolling-loop-ab-round4/`;
  the executed summary is in `benchmarks/harness_cases.yaml` and the
  `docs/evidence.md` what-it-does-NOT-do table.
- **Supersedes scope of:** REC-20260706-034 (which asked for exactly this
  measurement).

## What was measured

The load-bearing Phase-2 question: does the
`rolling_improvement_review` REC-linkage machinery (new/repeated/resolved
tagging + rolling-state carry in `scripts/run_adaptive_harness_review.py`)
beat manual tracking? Frozen criteria required BOTH: (1) manual replay
recall < 0.90, and (2) manual re-derivation cost > 2x the brief read.

Result: (1) failed at recall **1.00/1.00/1.00** (k=3 sonnet, 85 finding
instances, strict first-seen matching included, deterministic grader);
(2) held at **11.3x** (marginal) / 66x (full transcript). The
pre-registration's own words applied: "if A ≈ 1.00 too, the loop is
over-engineered."

## Proposal (the frozen consequence, verbatim intent)

Reduce the rolling loop to:

1. **Keep** the deterministic report + brief emitter
   (`scripts/run_ai_review.py`, including `latest-brief.json`) — this is
   where the measured value lives (brief read ≈ 1.3k tok/run vs 15–89k
   re-derivation).
2. **Replace** the linkage machinery (new/repeated/resolved tagging,
   `rolling_state.json` recommendation carry) with a grep-history helper —
   linkage questions are answerable from `reports/harness/history/` +
   `git log --grep "applies REC-"` on demand.
3. **Human decision required on the outcome ledger** (`d8fe0e8`,
   2026-07-13): its regression gates passed synthetically, but it has fired
   live **0 times** (outcomes array empty; zero `applies REC-` commits
   exist). Options: retire with the linkage machinery, or keep as a
   dormant convention (the commit-verb closure grep needs no runner).

## Honest caveats that travel with this REC

- **Verbatim-carry threat:** the loop stores rec text verbatim, which made
  replay matching easy. A no-loop world with fresh LLM reviews each run
  would paraphrase findings and could be harder to track manually. The
  criteria were frozen before the run and are not loosened in either
  direction post-hoc — but if the operator moves to fresh-LLM-authored
  reviews per run, this case deserves a re-run on drifted text before the
  simplification is treated as permanent.
- **Resolved-detection untested:** the fixture window contained zero
  resolution events, so the auto-resolve-by-commit-sha feature was not
  measured — it was simply never exercised live in the window either.
- Window: 5 runs / 8 days; k=3, sonnet, one fixture family.
