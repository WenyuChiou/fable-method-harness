---
id: DOC-codebase-memory-freshness-2026-07-13
layer: doc
purpose: Commit-bound evidence for the fail-closed codebase-memory freshness sentinel and the unresolved ready-but-stale local graph
read_when: Deciding whether codebase-memory graph results are current enough for code discovery, or auditing the fallback decision
depends_on:
  - ../scripts/check_codebase_memory_freshness.py
  - ../scripts/test_check_codebase_memory_freshness.py
  - ../benchmarks/codebase_memory_freshness/cases.json
  - ./codebase_memory_indexing.md
  - ./evidence.md
used_by: [DOC-evidence, ROUTE-repo-maintenance]
tags: [codebase-memory, freshness, sentinel, evidence, negative-result]
retrieval_keywords: [ready but stale graph, freshness sentinel, codebase memory fallback, source hash mismatch]
---

# Codebase-memory Freshness Sentinel Evidence

Status: the sentinel passed every pre-registered gate; the local MCP graph
remains stale and therefore still requires direct-file fallback.

## Frozen design

Case `codebase_memory_freshness_sentinel_vs_ready_status` was pre-registered in
commit `a077c79` before any graph deletion or rebuild. Variant A trusted
`index_status=ready`. Variant B required exact agreement between the tracked
worktree AST and MCP results for symbol identity, file, decorator-inclusive
line span, and source hash.

Implementation commit: `8e0f44d`.

## Deterministic result

Re-run:

```text
python scripts/test_check_codebase_memory_freshness.py
```

Result: 15 passed, 0 failed. The suite proves:

- 0/3 missing, misaligned, or deleted-symbol fixtures are labeled FRESH;
- 1/1 exact fixture is FRESH;
- missing, nonzero, malformed, truncated, and timed-out CLI evidence is
  canonical `UNSCORED`, nonzero, and requires fallback;
- provenance excludes dirty or untracked inputs from formal evidence;
- output cannot target source, cases, the repository root, or paths outside
  the allowed evidence subtree, including a predictable-temp symlink/hardlink
  regression.

## Commit-bound live result

Command:

```text
python scripts/check_codebase_memory_freshness.py --repetitions 5 --output evals/codebase_memory_freshness/committed_stale_20260713/scorecard.json
```

The raw scorecard is intentionally gitignored because generated evaluations
can contain machine-local paths. Its SHA-256 is
`3c14694a6449713f8cf838e356d6c0bd57009af1082fa5474bd13130124c0468`.

| Gate | Result |
|---|---:|
| Frozen repository head | `8e0f44dd4852b4cb406772ee11d673f0926fcd56` |
| CLI | `codebase-memory-mcp 0.8.1` |
| Repetitions | 5/5 |
| Final status | `STALE` |
| `index_status` observed | `ready` in every repetition |
| Graph size observed | 1,650 nodes / 2,207 edges |
| Median three-probe duration | 0.0595 seconds |
| Inputs tracked at HEAD | true |
| Evidence valid | true |
| Fallback required | true |

Every repetition found the same three defects:

1. `scan_outcome_evidence` was present in the worktree and absent from the graph.
2. `collect_rolling_state` resolved to the wrong line span and source hash.
3. `run_live` was present in the worktree and absent from the graph.

## Repair attempt and honest failure

After pre-registration, the MCP `delete_project` operation failed with
`Permission denied`. A full `index_repository` call subsequently completed but
left the same 1,650-node / 2,207-edge graph and the same stale probe outcomes.
The rebuild attempt therefore did not repair freshness.

## Supported decision

Keep the sentinel because it converts silent stale retrieval into an explicit,
fast fallback decision. Before load-bearing code discovery, use the graph only
after exit 0 / `FRESH`; on exit 1 / `STALE` or exit 2 / `UNSCORED`, use direct
file reads and ripgrep.

This evidence supports better completion integrity at a measured 0.0595-second
median check cost. It does not support a token-saving claim, a repaired-MCP
claim, or broad performance conclusions beyond this three-probe local run.
