---
id: DOC-runtime-activation-telemetry-2026-07-15
layer: doc
purpose: Executed v3 evidence for measurable Codex and Hermes conditional activation, rollback, and exact usage telemetry.
read_when: Evaluating the Codex/Hermes activation switch or citing its context and telemetry claims.
depends_on: [../benchmarks/runtime_activation/preregistration_v3.json, ../scripts/run_runtime_activation_probe.py, ./runtime_activation_contract.md]
used_by: [README, DOC-evidence]
tags: [codex, hermes, activation, telemetry, evidence, evaluation]
retrieval_keywords: [conditional activation results, Hermes context bytes, Codex exact usage, rollback, routine overtrigger]
---

# Runtime activation telemetry — 2026-07-15

Status: **executed proof-of-instrument**, not a token- or speed-superiority
A/B. The v3 design was committed before its 14 calls in
[`benchmarks/runtime_activation/preregistration_v3.json`](../benchmarks/runtime_activation/preregistration_v3.json).

## What passed

| Runtime | Trigger recall | Routine over-trigger | Actual marker rollback | Exact usage rows | Mean canonical usage | Median wall time |
|---|---:|---:|---:|---:|---:|---:|
| Hermes | 4/4 | 0/2 | 1/1 | 7/7 | 38,225 tokens/call | 13.493 s |
| Codex | 4/4 | 0/2 | 1/1 | 7/7 | 51,528 tokens/call | 13.399 s |

The seven cases cover two routine requests, four activation triggers, and one
rollback case with a real `.fable-harness-off` file. Hermes counters come from
exactly one newly created nonce-correlated session in `state.db`; Codex
counters come from `codex exec --json`. Canonical usage is
`input + cache_read + cache_write + output`; reasoning tokens are reported
separately and are not folded into that total.

The generated scorecards remain ignored local evidence:
`evals/runtime_activation/hermes_activation_v3_20260715.json` and
`evals/runtime_activation/codex_activation_v3_20260715.json`. They store
numeric counters and output digests, not raw model text.

## Separate offline context result for Hermes

An independent deterministic `hermes prompt-size --json` comparison (not one
of v3's 14 calls and no API call) used the same final
`AGENTS.md` in two temporary workspaces: baseline has no `HERMES.md`; treatment
adds the short Hermes shim.

| Fixed project context | Baseline | Shim | Change |
|---|---:|---:|---:|
| `AGENTS.md` / cwd context bytes | 5,994 B | 1,803 B | **−4,191 B (−69.9%)** |
| Complete system-prompt bytes | 41,174 B | 36,984 B | −4,190 B |

This re-runnable fixed-context byte measurement supports the claim that the
shim avoids injecting the full project instruction for routine Hermes work. It
is **not** an API-token, dollar-cost, or latency claim.

## What this does not establish

- The v3 live run has one arm per runtime; it does **not** prove API-token
  reduction or a speedup. Those require a future randomized paired A/B.
- The measured per-call usage above is a baseline for monitoring, not a claim
  that Hermes and Codex have comparable prices or tokenizers.
- v1 was invalidated before a scorecard after Windows temporary-directory
  cleanup failed. v2 is retained as a failed Hermes result (routine
  over-trigger 2/2 plus a scorer framing defect). Neither run is reused for
  the v3 claim; the v3 preregistration records both outcomes.

## Re-run

Run the deterministic checks first, then use a clean committed worktree and
the frozen v3 design:

```bash
python scripts/test_run_runtime_activation_probe.py
python scripts/run_runtime_activation_probe.py run --runtime hermes --preregistration benchmarks/runtime_activation/preregistration_v3.json --output evals/runtime_activation/hermes.json
python scripts/run_runtime_activation_probe.py run --runtime codex --preregistration benchmarks/runtime_activation/preregistration_v3.json --output evals/runtime_activation/codex.json
```

The runner rejects an external, uncommitted, staged, or drifted
preregistration before it starts a runtime call.
