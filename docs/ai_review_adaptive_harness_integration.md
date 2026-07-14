---
id: DOC-ai-review-adaptive-harness-integration
layer: doc
purpose: The one-system contract between AI-review (local reviewer) and adaptive-harness (harness-review modes + patch proposals) - responsibilities, shared schemas, data flow, and the deterministic/LLM/human division of labor; cross-run linkage is on-demand via grep_history.
read_when: Changing either runner, the shared schemas, or the grep-history helper; running ai_review_integration mode; deciding where a new review capability belongs.
depends_on:
  - ../scripts/run_ai_review.py
  - ../scripts/run_adaptive_harness_review.py
  - ../scripts/grep_history.py
  - ../schemas/review_report.schema.yaml
  - ../schemas/recommendation.schema.yaml
  - ../prompts/ai-review-modes.md
  - ../.claude/skills/adaptive-harness/SKILL.md
used_by: [SKILL-adaptive-harness, SCRIPT-run-adaptive-harness-review]
tags: [doc, integration, ai-review, adaptive-harness, division-of-labor]
retrieval_keywords: [ai review adaptive harness integration, division of labor, who does what, grep history linkage, shared schema contract, repeated resolved findings, scheduled review responsibility]
---

# AI-review ↔ adaptive-harness integration

**One system, two runners, shared schemas.** AI-review reviews the current
state; adaptive-harness runs the harness-shaped review modes and renders
patch proposals. Both write `schemas/review_report.schema.yaml` reports with
`schemas/recommendation.schema.yaml` records — neither may fork the format.
Cross-run linkage is ON DEMAND, not stateful: the rolling machinery
(new/repeated/resolved tagging + `rolling_state.json` + the outcome ledger)
was retired per REC-20260714-001 — the pre-registered A/B
(`benchmarks/harness_cases.yaml` case
`ai_review_only_vs_ai_review_plus_adaptive_harness`, executed 2026-07-14)
measured recall 1.00 for plain re-derivation, so linkage questions go to
`scripts/grep_history.py` over the append-only history + git log.

## Data flow

```
run_ai_review.py --mode <m>                      (deterministic collect)
  → reports/ai-review/latest.json                (JSON + MD + JSONL history)
  → LLM answers prompts/ai-review-modes.md §<m>  (semantic judgment)
  → run_ai_review.py --ingest findings.json      (validated merge)
  → run_adaptive_harness_review.py --mode patch_proposal
       --read-ai-review reports/ai-review/latest.json
                                                 (high-risk → apply/rollback sheet)
  → human applies; the commit cites REC-id       (loop closure evidence)
  → grep_history.py --rec / --repeats / --open   (linkage on demand:
                                                  history + git log, read-only)
```

## AI-review 負責 (local reviewer)

- review current output quality; prompt / workflow quality
- review code / tool / Codex invocation efficiency
- detect local harness issues (INDEX drift, deprecated markers, stale pointers)
- produce structured findings; suggest Keep / Simplify / Remove / Replace / Experiment

## adaptive-harness 負責 (harness-shaped review + proposals)

- run the harness review modes (inventory, wiring, diff impact, scheduled scans)
- maintain the shared schemas; evolve skill / runner / routing structure
- decide checklist→script conversions; decide what needs a benchmark
- produce patch proposals for high-risk recommendations
- keep safety boundaries; prevent harness bloat; coordinate scheduled reviews

## deterministic scripts 負責

- file inventory · path/route validation · diff scan · metrics collection
- report generation (JSON→MD) · history appending
- cross-run linkage on demand (`grep_history.py`: appearances, repeats,
  open/closed via the applies/resolves commit verb or Harness-Outcome trailer)
- ingest validation (required fields, enums, REC-id pattern, high-risk flag)

## LLM 負責

- semantic judgment · tradeoff reasoning · prioritization
- deciding whether a rule is still useful · interpreting benchmark results
- proposing safe refactors — always as schema-valid records via --ingest

## human 負責

- approving high-risk changes; deleting prompts / subagents / hooks
- changing permissions / settings.json / CI; merging patch proposals
- public release decisions

## Retrieval / graph support (overlay 04)

The harness graph already exists explicitly (frontmatter `depends_on`/
`used_by`, INDEX.yaml, ROUTES.yaml). `scripts/build_harness_graph.py`
EXPORTS it to `reports/index/knowledge_graph.json` (gitignored, regenerable),
validates every frontmatter dependency repo-wide (previously only the 8
overlay artifacts were machine-checked), and answers impact queries
(`--since-ref` / `--impact`: changed files → transitive dependents +
member routes). The adaptive runner's `diff_only_review` mode
consumes it as the `graph_impact` collector; broken dependencies surface as P1 issues. The codebase-memory
MCP stays what CLAUDE.md says it is — an ADVISORY code-exploration index —
and is neither duplicated nor treated as truth. Source of truth remains
the repo files. Pre-registered retrieval queries:
`benchmarks/retrieval_cases.yaml`.

## Model-tier routing

| Tier | Safe for | Not for |
|---|---|---|
| Haiku / low | run any deterministic script (runners, builder, validators, probes); graph/JSON lookups (grep_history queries, knowledge_graph.json); fill schema-valid JSON fields; mark UNVERIFIED and escalate | judging whether a rule should be deleted; interpreting benchmarks; any high-risk change |
| Sonnet / mid | summaries over retrieved files; dry-run comparisons of AI-review vs harness reports; obvious drift / stale-ref triage; low-risk cleanup proposals; `standard_review` / `diff_review` semantic checklists | harness refactors; safety-boundary decisions |
| Opus / Fable | semantic judgment, tradeoff reasoning, harness simplification, benchmark interpretation, cross-run diagnosis, safety-boundary decisions, `harness_cleanup_review` / `codex_delegation_review` checklists | — |
| Codex | scoped mechanical edits under docs/codex-delegation-policy.md (brief-first, fence, never commits); graph/index regeneration scripts; test scaffolds | any final authority, review verdicts, "done" claims |

## Design decisions (recorded)

1. **AI-review does not call adaptive-harness** (and vice versa) at the
   process level — coupling is through the report files, so either can run
   alone, any tier can invoke either, and a failure in one cannot corrupt
   the other. The LLM session (or the /ai-review command) sequences them.
2. **Scheduled reviews**: BOTH runners have a scheduled mode; each owns its
   own output dir. The ~/.claude nudge pipeline (ClaudeAiReviewDue → flag →
   SessionStart hook) remains the only summoner of humans; scheduled runs
   are machine reports awaiting a present human, never actors.
3. **Phase-1 scripts are the engine** — `run_adaptive_harness_review.py`
   imports collectors/validators/writers from `run_ai_review.py`
   (importlib, no package). The Phase-2 prompt's `harness_inventory.py`,
   `invocation_audit.py`, `report_writer.py` were deliberately NOT created
   as separate files: their functions are the shared engine's
   `collect_inventory`, `code_invocation_review` mode, and
   `render_markdown`/`write_outputs` respectively — one implementation,
   no parallel tooling (DR-020).
4. **reports/ stays gitignored** (public repo; reports embed local
   telemetry). Durable outcomes live in commits citing REC-ids, the
   proposals ledger (~/.claude/audits), and benchmark case statuses.
5. **Resolution is commit-cited with an application verb**: a recommendation
   is closed only when a commit message says `applies REC-...` or
   `resolves REC-...` (or carries a `Harness-Outcome:` trailer) — a bare
   mention (rejection note, proposal listing) does not count, and reverts say
   `reverts REC-...` so undoing a change can never read as applying it.
   `grep_history.py --open` lists what is still open; a finding that stops
   being reported remains visible in the append-only history and stays OPEN
   there until a closing commit exists (retirement of the stateful carry:
   REC-20260714-001).
