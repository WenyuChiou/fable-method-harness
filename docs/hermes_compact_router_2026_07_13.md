---
id: DOC-hermes-compact-router-2026-07-13
layer: doc
purpose: Commit-bound static and live evidence for the compact Hermes route-receipt contract, including the failed full paired gate
read_when: Checking whether the Hermes compact router reduces standing context or improves route receipt quality and safety
depends_on:
  - ../prompts/hermes-router.md
  - ../scripts/run_hermes_router_benchmark.py
  - ../benchmarks/hermes_router/cases.json
  - ./agent-routing-policy.md
  - ./evidence.md
used_by: [DOC-evidence, operator-session]
tags: [hermes, routing, benchmark, evidence, prompt-economy]
retrieval_keywords: [Hermes compact router, route receipt, paired live benchmark, protected misroute, standing prompt bytes]
---

# Hermes Compact Router Evidence

Status: static economy gate passed; live B quality gate passed; the initial
strict paired experiment remains a hard FAIL. A later pre-registered fair
semantic follow-up passed its adoption and latency no-regression gates, without
supporting a speedup or live token-reduction claim.

## Change under test

The old standing prompt used a 1,402-byte free-form routing contract. Commits
`7e94269` and `137d315` replaced it with an explicit private JSON receipt and a
live runner. Commit `b56a1a3` added a fail-closed, case-paired A/B time gate.

The final standing contract is 835 bytes. It lists exactly eight classes and an
unambiguous `class>target,mode` mapping. Production writes receipts to private
router metadata/session trace; evaluation mode may request the receipt as output.

## Unknown unknowns found before the formal run

- A static 10/10 initially tested a hard-coded classifier against matching
  keywords. Review rejected it as circular; it is now only mapping coverage.
- The first live smoke interpreted `daily>hermes/direct` as target
  `hermes/direct`. The contract now separates target and mode with a comma.
- Strict receipt validation initially hid malformed protected misroutes. Safety
  extraction is now permissive while canonical grading remains strict.
- Process timeout, CLI-spawn, path-containment, Python 3.8 compatibility, and
  dirty/unavailable provenance paths all gained fail-closed regression tests.

## Static contract result

Re-run:

```text
python scripts/run_hermes_router_benchmark.py --iterations 5000 --json
```

| Metric | Result |
|---|---|
| Baseline standing bytes | 1,402 |
| Compact standing bytes | 835 |
| Compact / baseline | 59.56% |
| Standing-byte reduction | 40.44% |
| Estimated standing tokens (`bytes/4`) | 351 -> 209 (estimate only) |
| Schema/policy mapping coverage | 10/10 |
| Protected mapping misroutes | 0 |

This proves standing-contract economy and deterministic schema coverage. It is
not live token usage or model classification evidence.

## Commit-bound live B result

Raw local run:
`evals/hermes_router_live/hermes_router_live_committed_20260713/`
(gitignored).

| Metric | Result |
|---|---|
| Frozen commit | `137d315acb99eb62675699cc93488dcbdfb4e1a3` |
| Inputs tracked at frozen SHA | true |
| Executed / scored / unscored | 10 / 10 / 0 |
| Strict receipts parsed | 10/10 |
| Routes correct | 10/10 |
| Protected completion/governance misroutes | 0/3 |
| Median wall time | 10.896 seconds |
| Non-empty stderr / nonzero exits | 0 / 0 |

This supports live classification and receipt quality for ten paraphrased
fixtures on Hermes Agent 0.16.0, model `gpt-5.5`, provider `OpenAI Codex`. It
does not establish reliability beyond this task set.

## Formal paired A/B result

Raw local run:
`evals/hermes_router_live/hermes_router_paired_committed_20260713/`
(gitignored).

Design: two repetitions; every case runs once AB and once BA; 40 calls total.
The manifest froze the schedule before execution and required tracked inputs
plus available model/provider/version/status/config fingerprints.

| Metric | A: old free-form | B: compact JSON |
|---|---:|---:|
| Executed / scored | 20 / 20 | 20 / 20 |
| Canonical receipts parsed | 0/20 | 20/20 |
| Canonical routes correct | 0/20 | 20/20 |
| Protected misroutes | 3 | 0 |
| Median wall time | 11.467s | 10.416s |

Additional facts:

- frozen commit: `b56a1a30310d7d24bb305ac0bdfc1a65cc3a4020`;
- provenance eligible: true;
- exact A/B pairs: 20;
- observed median case-paired B/A wall-time ratio: 0.9303;
- non-empty stderr / nonzero exits: 0 / 0;
- full paired `passed`: **false**.

The observed ratio is descriptive only. The pre-registered time claim remains
withheld because the fail-closed paired gate required both variants to be fully
parseable, and A was 0/20. We did not normalize A's post-hoc vocabulary or
rerun it to manufacture a pass.

## Supported decision and limits

Keep the compact receipt contract for the measured 40.44% standing-byte
reduction, B's 10/10 live route accuracy, parse yield improvement from 0% to
100%, and protected-misroute improvement from 3 to 0 in the paired sample.

Do **not** claim live token savings, a statistically established latency lift,
broad Hermes reliability, or that the earlier strict paired gate passed.

## Pre-registered fair semantic follow-up

The strict paired failure above is preserved. It motivated, but was not used to
post-hoc tune, a new stdout-only semantic grader frozen in commit `f2761d0`.
The committed runner `5a855e4` then executed 100 no-retry calls with 25 AB and
25 BA pairs.

Compact B scored 50/50 semantic targets and exact routes, parsed 50/50 native
JSON receipts, and passed all 15 protected cases with zero unresolved,
ambiguous, or misrouted outputs. The 50-pair median B/A ratio was 0.99075 and
the pre-registered 95% bootstrap upper bound was 1.05007. Therefore B passed
the `<1.1` no-regression gate and `adopt_B=true`, but it did not pass the `<1.0`
speedup gate. Exact token usage remained unavailable and UNSCORED.

Full design, hashes, gate results, and limits are in the
[fair semantic follow-up](./hermes_fair_baseline_2026_07_13.md).
