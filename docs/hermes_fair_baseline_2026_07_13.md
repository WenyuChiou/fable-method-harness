---
id: DOC-hermes-fair-baseline-2026-07-13
layer: doc
purpose: Commit-bound fair semantic A/B evidence for adopting the compact Hermes route receipt without claiming unmeasured token savings or an unsupported speedup
read_when: Auditing the fair-baseline Hermes adoption decision, semantic routing quality, protected-task safety, or paired live latency claims
depends_on:
  - ../benchmarks/hermes_router/fair_ab_preregistration.json
  - ../benchmarks/hermes_router/cases.json
  - ../scripts/run_hermes_router_benchmark.py
  - ./hermes_compact_router_2026_07_13.md
  - ./evidence.md
used_by: [DOC-evidence, operator-session]
tags: [hermes, routing, benchmark, evidence, fair-baseline, semantic-grader]
retrieval_keywords: [Hermes fair baseline, semantic route accuracy, paired latency bootstrap, protected route safety, compact receipt adoption]
---

# Hermes Fair Semantic Baseline Evidence

Status: **ADOPT B on the frozen task set.** The compact JSON arm passed every
pre-registered quality, safety, provenance, and latency no-regression gate.
The experiment does **not** support a live speedup or token-reduction claim.

## Why this follow-up exists

The earlier 40-call paired experiment remains a published hard FAIL: baseline
A returned no canonical three-line receipts, so its strict parser made the
quality and latency comparison ineligible. That result was not deleted or
regraded after seeing its outputs.

Commit `f2761d0` pre-registered a fair successor before any new live output.
It separated native format compliance from a frozen, stdout-only semantic
grader. The aliases came only from the tracked old contract, current route
schema, and cases. Prior outputs were prohibited as alias sources. Commit
`5a855e4` then implemented the runner and its fail-closed evidence gates.

## Frozen design and runtime

- 10 cases x 5 repetitions x 2 arms = 100 one-shot calls.
- 50 A and 50 B calls; 25 AB and 25 BA pairs; zero retries.
- The task text, command flags, timeout, runtime, and semantic grader were
  identical across arms. Only the standing contract and its native receipt
  instruction differed.
- Frozen runner commit: `5a855e41bac9ee75e26ca9dd9fbbabe5f0e346b7`.
- Hermes Agent: `v0.16.0 (2026.6.5)`; model `gpt-5.5`; provider
  `OpenAI Codex`.
- Start and end executable/version/model/provider/status/config fingerprints
  were available and byte-identical. Inputs were tracked, clean, and matched
  their frozen hashes.

Raw local evidence is under
`evals/hermes_router_live/hermes_fair_paired_committed_20260713/` and is
gitignored because it contains machine-local provenance and complete model
outputs. Durable integrity anchors:

| Artifact | SHA-256 |
|---|---|
| `scorecard.json` | `e91ee6a1714dc04d869e3ad3df13fd2217f51f5704d19375b0a059f9b4fd0645` |
| `manifest.json` | `370691a89c819b901e714aae997c17168cb118f3b93e5e7295df9fcf07f0b552` |
| 100 sorted trial files, concatenated | `6afdbcb5684c72b57d1bf37bb8fd1dbab65e9037c1524ebf1789b7545e91f2e9` |

## Quality and safety result

All 100 calls exited zero and were scored; none timed out or became UNSCORED.

| Metric | A: old free-form | B: compact JSON |
|---|---:|---:|
| Executed / scored / unscored | 50 / 50 / 0 | 50 / 50 / 0 |
| Native receipt parsed | 0/50 | 50/50 |
| Semantic target correct | 11/50 | 50/50 |
| Semantic exact route correct | 10/50 | 50/50 |
| Protected target correct | 0/15 | 15/15 |
| Protected exact route correct | 0/15 | 15/15 |
| Protected unresolved | 10 | 0 |
| Protected ambiguous | 1 | 0 |
| Protected misroutes | 5 | 0 |
| Median call wall time | 10.245s | 9.873s |

The arm medians are descriptive only. The pre-registered latency decision uses
the 50 within-case B/A ratios, not the ratio of those two arm medians.

## Paired latency result

| Metric | Result |
|---|---:|
| Complete paired ratios | 50/50 |
| Median paired B/A ratio | `0.9907518341071011` |
| Deterministic bootstrap resamples | 10,000 |
| 95% nearest-rank upper bound | `1.0500687010421872` |
| No-regression threshold | upper bound `< 1.1`: **PASS** |
| Speedup threshold | upper bound `< 1.0`: **FAIL / unsupported** |

The data support latency no-regression under the frozen criterion. They do not
support saying that B is faster: plausible paired-median values under the
pre-registered bootstrap extend above 1.0.

## Decision and exact limits

Every adoption gate passed, so `adopt_B=true`. Keep the compact receipt for
this measured task set: it had perfect semantic routing, perfect native JSON
compliance, and zero protected failures while satisfying the latency
no-regression bound.

Do not claim any of the following:

- live token reduction: Hermes one-shot exposed no exact per-call input or
  output usage, so token usage is explicitly `UNSCORED`;
- paired live speedup: the bootstrap upper bound was 1.05007, not below 1.0;
- broad Hermes reliability: this is ten frozen route shapes with five
  repetitions each, under one pinned runtime;
- that the earlier hard FAIL disappeared: it remains valid evidence about the
  strict native-parser design and motivated this pre-registered fair follow-up.

The separate static result still establishes a 1,402 -> 835 byte standing
contract reduction (40.44%). Bytes and bytes/4 are context-size proxies, not
measured live token usage.

## Re-run

Use a new run id; the runner refuses to overwrite an existing evidence
directory and fails closed on dirty inputs or runtime drift.

```text
python scripts/run_hermes_router_benchmark.py --live-fair-run-id <new-run-id> --json
```

The command is intentionally fixed at 100 no-retry calls. Changing the case
count, arm, repetitions, or timeout is rejected by the CLI.
