---
id: DOC-adaptive-outcome-ledger-2026-07-13
layer: doc
purpose: Commit-bound correctness and overhead evidence for the persistent, evidence-aware rolling outcome ledger
read_when: Checking whether adaptive-review recommendations close only on evidence and remain resolved or reopen correctly across later runs
depends_on:
  - ../scripts/run_adaptive_harness_review.py
  - ../scripts/test_run_adaptive_harness_review.py
  - ../benchmarks/harness_cases.yaml
  - ./evidence.md
used_by: [DOC-evidence, operator-session]
tags: [adaptive, learning-loop, outcomes, benchmark, evidence]
retrieval_keywords: [Harness-Outcome, rolling outcome ledger, false closure, reopened recommendation, adaptive learning]
---

# Adaptive Outcome Ledger Evidence

Status: the pre-registered integrity and overhead gate passed at commit
`d8fe0e85ebd5ecf6c2cbf1402a7312a3ae731a9d`.

> **RETIRED 2026-07-14** (applies REC-20260714-001): the outcome-ledger
> CODE this document validated was removed together with the rolling
> linkage machinery after the round-4 A/B came back B-loses — it had fired
> live 0 times. The `Harness-Outcome:` trailer + applies/resolves verb
> CONVENTION survives as a dormant convention: `scripts/grep_history.py`
> honors both as closure without any stateful runner. This document is
> retained as the historical evidence record for the gates that passed at
> the commit above.

## Problem under test

The old rolling review searched free-form commit prose for `applies` or
`resolves`. A partial-evidence note followed by `no closure intended` could
therefore look resolved, while real outcomes lived only in the latest derived
report and could be lost or repeated on later runs.

The replacement accepts only:

- an exact legacy commit subject ending in `applies REC-*` or `resolves REC-*`;
- a structured `Harness-Outcome` trailer whose evidence path is a tracked file
  in the same commit.

It distinguishes applied-but-unvalidated work from validated or rejected
closure, persists the newest outcome, and lets a later evidence-backed
`reopened` event return the recommendation to the active queue.

## Pre-registered result

| Criterion | Result |
|---|---:|
| Adversarial free-form messages falsely closed | 0/5 |
| Valid closure forms accepted | 2/2 |
| Validated outcome survived later stale-input runs | 3/3 |
| Carried-open regression | unchanged |
| Evidence-backed reopen returned to active queue | pass |
| Adaptive tests | 20/20 |
| Interleaved timing samples | 15 per arm |
| Reported steady-state overhead ratio | 1.028x baseline |
| Pre-registered overhead ceiling | <=1.2x |

The commit-bound timing record reports medians of 435 ms and 423 ms and the
1.028x ratio. This establishes that the integrity checks stayed within the
overhead budget. It is not a speedup claim.

## Unknown unknowns found by review

- A cache keyed only by Git HEAD misses an older recommendation introduced by
  a newer review at the same commit. The cache key now includes REC-ID coverage.
- A transient Git scan failure could otherwise advance the cache and suppress
  the retry. Failed scans now remain visible, emit a P1, and do not advance it.
- Evidence added in a later commit must not validate a trailer retroactively;
  the evidence file must exist in the declaring commit.
- Conflicting outcome trailers in one commit now fail closed as unverified.
- The cache fast path could not assume a normal loose branch ref. It now
  resolves `.git` directories or worktree pointers, detached HEAD, and loose
  or packed refs without a Git fork, with `git rev-parse` as a fallback. The
  regression test explicitly pins detached HEAD behavior; packed refs and
  worktree pointers are implemented support, not separately measured claims.

## Supported decision and limits

Keep the ledger because the measured regression set eliminates the tested
false-closure class, preserves outcomes across repeated runs, supports explicit
reopening, and stays within the 1.2x overhead budget.

Do not treat a trailer as proof that the underlying engineering change works.
The ledger proves that evidence is commit-bound and state transitions are
auditable; the referenced evidence still requires its own acceptance gate.
