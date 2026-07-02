---
id: DOC-codebase-memory-indexing
layer: doc
purpose: How to index and search this harness with the codebase-memory MCP
read_when: Setting up retrieval for a new session, after an edit round, or when grep feels too slow
depends_on: [context/L4_progressive_disclosure_policy.md, ROUTES.yaml]
used_by: [ROUTE-repo-maintenance, ROUTE-memory-update]
tags: [indexing, retrieval, mcp, codebase-memory, search]
retrieval_keywords: [index repository, codebase memory, re-index, search by id, retrieval keywords, frontmatter search]
---

# Indexing This Harness with codebase-memory MCP

This repo is designed to be searched, not read. The frontmatter block on
every important `.md` file (`id / layer / purpose / read_when / depends_on /
used_by / tags / retrieval_keywords`) IS the retrieval surface — treat it
as the index schema.

## 1. Initial indexing

- Run `index_repository` on **this repo's root**
  (`agent_harness/fable_style_project_harness/`), NOT on the parent
  `method-harness-compiler` root. The parent repo gitignores this
  directory; indexing the parent will not pick these files up, and mixing
  the two corpora blurs provenance.
- Verify with `index_status` / a probe query, but do NOT trust a bare
  `"ready"` status as proof of freshness — confirm with one known-ID
  lookup (e.g. search `L2-current-phase` and check the returned path).

## 2. Re-index after edits — always

The index is stale-by-default. **Re-index after every edit round before
querying**, especially after:

- a phase transition (L2 is rewritten — a stale L2 hit is the worst
  possible retrieval failure);
- appending dataset records (new `TE-###`/`FM-###`/`EC-###`/`RE-###` IDs
  don't exist in the old index);
- route-list changes in `ROUTES.yaml`.

## 3. How to search — prefer stable IDs and retrieval_keywords

Priority order:

1. **Exact stable ID** (`FM-007`, `TE-012`, `RUBRIC-pr-review`,
   `PLAYBOOK-phase-gate`, `ROUTE-eval-design`) — unambiguous, one hit.
2. **`retrieval_keywords` phrases** — every important file lists the
   phrases it should be found by (e.g. "current phase", "which route",
   "make public"). Query with those phrases verbatim.
3. **Frontmatter fields** — `layer:` and `used_by:` support faceted
   lookup: "all files used_by ROUTE-eval-design", "all layer: rubric
   files".
4. Free-text semantic search — last resort; verify hits by opening the
   file, since semantic matches can land on prose that merely mentions a
   term.

## 4. Results are advisory

Index results are ADVISORY, never authoritative (known failure modes:
stale-by-default, parse degradation, CJK/cp950 mojibake). For any
load-bearing decision:

- open the actual file/record and read the specific lines;
- for dataset records, confirm the `source_artifact` field resolves;
- when index and file disagree, the file wins — then re-index.

## 5. Fallback without the MCP

Plain `grep`/ripgrep over this repo is fully sufficient (the repo is
small by design): grep the stable ID, or grep `retrieval_keywords` lines.
`ROUTES.yaml` + frontmatter were written so that no semantic index is
strictly required — the MCP is an accelerator, not a dependency.

## 5a. Entry files — how a session actually starts

For a large task, wire the harness into the session through whichever
entry the runtime supports (all three converge on the same startup ladder;
see `ROUTES.yaml` `entrypoints:`):

1. **Skill-aware runtime (Claude Code class):** `SKILL.md` carries
   `name`/`description` frontmatter, so the runtime can surface the harness
   as an invocable capability without any human explanation.
2. **AGENTS.md-convention agents (Codex/Cursor class):** `AGENTS.md` is
   auto-read at session start; the 8 rules there force the L0→L2→L3→ROUTES
   ladder before any work.
3. **Anything else (incl. a bare model + this index):** paste one line —
   *"Read `BOOTSTRAP.md` in the fable-style-project-harness repo and follow
   it"* — or let the codebase-memory search land on `BOOTSTRAP` via its
   `retrieval_keywords` (`start here`, `bootstrap`, `entrypoint`).

Recommended first query for a fresh session with this repo indexed:
search `bootstrap startup sequence` → open `BOOTSTRAP.md` → follow the
ladder. Total pre-task reading stays under five files by design.

**Global usage (portable core, non-mhc projects):** index this harness repo
ONCE (its own root, per §1) and reuse that index from any project — the
harness is wired globally precisely so large/multi-agent sessions elsewhere
can reach it. For a session in a project OTHER than
`method-harness-compiler`, the first query is `global bootstrap portable` →
open `core/GLOBAL_BOOTSTRAP.md` and follow its PROJECT CHECK: non-mhc
sessions resolve `ROUTE-global-orchestration` (the `core/` files plus the
portable rubrics it names) and never load the project-bound layers
(`context/L1`/`L2`, `playbooks/phase*`, `memory/`).

## 6. Smoke-test the retrieval surface

After any indexing or frontmatter change, run the procedure in
`docs/retrieval_smoke_test.md`. A probe query that misses its expected
file means the frontmatter `retrieval_keywords` need improving — fix the
file, re-index, re-run. Do not paper over misses by widening queries.
