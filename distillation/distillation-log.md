---
id: DOC-distillation-log
layer: doc
purpose: Append-only log of working-style distillation cycles; one entry per candidate trait or negative finding, each carrying its motivating project, trace, gate label (load-bearing / baseline / quarantined / cosmetic / negative), and cross-project recurrence — the accumulation surface that turns hypotheses into traits over >=2 projects.
read_when: During a distillation cycle when recording candidates/verdicts; deciding whether a candidate has recurred across enough projects to promote.
depends_on:
  - ./setup-checklist.md
  - ./analyst-prompt.md
used_by:
  - ROUTE-distillation
tags: [distillation, living-doc, append-only, recurrence, load-bearing, working-style]
retrieval_keywords: [distillation log, candidate trait ledger, recurrence across projects, load-bearing vs cosmetic, quarantined, negative finding]
---

# Distillation Log

Append-only. Newest last. One entry per candidate trait or negative finding. **Never edit a
past entry** — supersede it with a new entry that references its id (DR-007
corrections-append-never-overwrite). This is the recurrence ledger: a candidate is promoted to a
*trait* only when it recurs across **>=2 projects** with a non-zero base-rate delta each time
(see [`setup-checklist.md`](setup-checklist.md) §2/§3). Load-bearing survivors also land on the
harness surfaces (`memory/lessons_learned.jsonl`, `datasets/edge_cases.yaml`); this log is the
cross-project index that makes recurrence visible.

## Entry template
- **id:** DL-YYYYMMDD-NN
- **project:** <the real project + whether it was git-tracked / had a base-rate arm>
- **candidate:** <one sentence — the observed working-style behaviour>
- **trace:** <exact file/row/line + the downstream decision it changed (two-level)>
- **base-rate delta:** <plain-agent's choice at the same fork vs the subject's — or "NO BASE-RATE RUN">
- **label:** load-bearing | baseline(ceiling) | quarantined | cosmetic | negative-finding
- **recurrence:** <k/N projects this has appeared in; supersedes/relates DL-ids>
- **landing:** <LL-0NN / EC-0NN / none — where it went on the harness surface, or why not>

## Entries
<!-- append below this line; do not rewrite existing entries -->

- **id:** DL-20260704-01
  - **project:** model-routing-benchmark (NOT git-tracked; NO base-rate arm — pilot, negative-findings-only per checklist §5)
  - **candidate:** honest-failure surfacing lives only in the raw-capture layer; the derived report manufactures a false all-green.
  - **trace:** `make_report.py:23` prefer-ok dedup → `canonical_results.jsonl` has 0 `ok:false`; `report_dedup.md` aggregate voice `4/4` with no timeout mention; the real timeout (240s ceiling, no elapsed — `benchmark.py:83-85`) survives only in `raw.jsonl` and is named in exactly one quoted model-output excerpt at `report.md:349`, never in a report's own aggregate voice; the 189.23s post-timeout retry is retained and averaged into the latency column.
  - **base-rate delta:** NO BASE-RATE RUN (n=1, no control arm — cannot separate subject from any agent).
  - **label:** negative-finding
  - **recurrence:** 1/1 project.
  - **landing:** appended LL-018 (`memory/lessons_learned.jsonl`) + EC-025 (`datasets/edge_cases.yaml`). Maps onto existing DR-004 / DR-009 / DR-011 + `docs/completion-honesty-gate.md` (a fresh instance, not a new rule).
