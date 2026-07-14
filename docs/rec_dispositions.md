---
id: DOC-rec-dispositions
layer: doc
purpose: Append-only operator disposition log for audit recommendations (REC ids) - each line records a human decision; the commit that adds a line carries the closure verb grep_history.py greps for.
read_when: Checking why a REC is closed, or recording a new human disposition (approve-keep, resolve-as-answered, reject).
depends_on:
  - ../scripts/grep_history.py
used_by: [operator-session]
tags: [doc, dispositions, adaptive-harness, append-only]
retrieval_keywords: [rec disposition log, closed recommendations, keep approved, resolved as answered, rejected recommendation]
---

# REC disposition log (append-only)

One line per human disposition. The COMMIT adding a line is the durable
closure record — its subject carries the `applies` / `resolves` verb (or a
`Harness-Outcome:` trailer) that `scripts/grep_history.py` treats as
closure. Bare mentions here close nothing; the log line without its verb
commit is not a closure.

| Date | REC | Disposition | Ground |
|---|---|---|---|
| 2026-07-14 | REC-20260706-034 | RESOLVED (question answered) | The rolling improvement loop's value question was answered by its own suggested test — the round-4 A/B (`benchmarks/harness_cases.yaml` case `ai_review_only_vs_ai_review_plus_adaptive_harness`, executed 2026-07-14, B-loses); the consequence shipped as REC-20260714-001 (linkage machinery retired, grep-history replaces it). Nothing left for this REC to decide. |
| 2026-07-14 | REC-20260706-014 | KEEP APPROVED | Operator affirmed the runner's Keep recommendation for the incident-born gate core (release trigger, scope assertion, stdout-redirect, orphan-pytest, staged-filecount rules in the operator harness). No file changes — approval closes the review question; the rules stay. |
| 2026-07-14 | REC-20260706-016 | KEEP APPROVED | Operator affirmed the runner's Keep recommendation for the F14 blocking PreToolUse hook (check_codex_skill_routing.py in the operator harness). No file changes — approval closes the review question; the hook stays. |
| 2026-07-14 | REC-20260706-025 | APPLIED (explicit reversal of the 2026-07-06 keep-as-is) | DELEGATION.md codex deep-dive compressed 264→216 lines in the operator harness (dotfiles commit c51ef3d): incident-derived output rules + 4 unique residual items + the F14 hook's 5 escape hatches + skill-reference pointers; zero unique content lost (verified item-by-item pre-edit). The operator's earlier keep-as-is ledger disposition was surfaced before deciding; reversal confirmed on evidence postdating it (micro-contract −27% confirmed 2026-07-10). Ledger row updated in the same dotfiles commit. |
| 2026-07-14 | REC-20260706-013 | ANNOTATED, KEPT OPEN (not a closure) | Hypothesis-grade evidence-status line added to the operator CLAUDE.md routing section (dotfiles commit c51ef3d) per the REC's own expected_impact; the REC stays open pending the Arm-C self-load probe. |
| 2026-07-14 | REC-20260706-012, -022, -023 | KEPT OPEN (explicit operator deferral) | 012: A/B needs a real ≥2-delegate round; 022: mechanical guard deferred to a dedicated session; 023: constants dedup deferred (ledger note 2026-07-06: acceptable, revisit on drift). No closures. |
