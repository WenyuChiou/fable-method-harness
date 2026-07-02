---
id: README
layer: doc
purpose: Explain what this harness repo is, what it is not, and how to enter it
read_when: First contact with the repo, or when unsure how the pieces fit
depends_on: [context/L0_bootstrap.md, HARNESS.yaml]
used_by: [ROUTE-phase-review, ROUTE-tool-discovery, ROUTE-pr-review, ROUTE-eval-design, ROUTE-memory-update, ROUTE-runtime-export, ROUTE-repo-maintenance, ROUTE-ab-test-design]
tags: [entrypoint, overview, privacy]
retrieval_keywords: [what is this repo, harness overview, how to use, entrypoint, privacy status, progressive disclosure]
---

# fable-style-project-harness

A **private operating harness** distilled from the observable working method
of the `method-harness-compiler` project (distilled at commit `965c68e`,
2026-07-02). It packages that project's demonstrated procedures — phase
gates, falsifiable evaluation gates, honest-failure publishing, layered
review, no-fabrication code gates, discovery-without-execution tool
boundaries, cost-aware routing, and append-only memory — into a
progressive-disclosure context system an agent can load incrementally
instead of reading the whole source repo.

## What this repo IS

- **Method summaries, procedures, rubrics, examples, and decision records**
  that any observer of the `method-harness-compiler` repo could reconstruct
  from its docs, schemas, scripts, tests, example packages, and git log
  (17+ commits with rich trailers).
- **A progressive-disclosure context package**: small layered files
  (`context/L0`–`L5`), a task router (`ROUTES.yaml`), per-route file lists,
  and datasets keyed by stable IDs (`TE-###`, `FM-###`, `EC-###`, `RE-###`,
  `ROUTE-*`, `RUBRIC-*`, `PLAYBOOK-*`).
- **Its own git repo**, deliberately gitignored by the parent project
  (parent commit `965c68e`: "private harness distillation must never ship
  with the (future-public) repo").

## What this repo is NOT

- **Not a prompt dump.** Nothing here is a private system prompt, hidden
  chain-of-thought, or internal model instruction. Everything is
  reconstructed from published artifacts.
- **Not hidden internals.** No API keys, tokens, personal contact info, or
  private chat content — see [`docs/private_repo_setup.md`](docs/private_repo_setup.md).
- **Not the method-harness-compiler itself.** The source project compiles
  expert-methodology packages; this repo distills *how that project is
  operated* so the same working method can be applied elsewhere.

## Entry points (Skill-like activation)

Three thin entry files let different runtimes *discover and launch* this
harness on their own, instead of a human explaining it each time:

| File | Convention it serves | When it fires |
|---|---|---|
| [`BOOTSTRAP.md`](BOOTSTRAP.md) | Universal shortest entry | Paste-a-pointer for any model: "read BOOTSTRAP.md and follow it" |
| [`AGENTS.md`](AGENTS.md) | Repository agent instructions | Auto-read at session start by convention-following coding agents (Codex, Cursor, and similar) |
| [`SKILL.md`](SKILL.md) | Skill discovery (`name`/`description` frontmatter) | Skill-aware runtimes (Claude Code and similar) surface it as an invocable capability |

All three converge on the same startup ladder below — they are launchers,
not rule stores. The rules stay in the routed files, so the entry layer can
stay short and stable.

A fourth entry, [`core/GLOBAL_BOOTSTRAP.md`](core/GLOBAL_BOOTSTRAP.md), is
the portable path for work on any OTHER project: it loads only the `core/`
discipline layer and never the project-bound files (L1/L2, phase playbooks,
`memory/`).

## How to use it (the reading order)

1. **`context/L0_bootstrap.md`** — the minimal first read. Under 300 words.
2. **`context/L2_current_phase.md`** — what phase the source project is in,
   what is allowed and forbidden right now.
3. **`context/L3_task_router.md`** — classify your task into one of the 8
   pinned routes.
4. **`ROUTES.yaml`** — get the exact file list for your route.
5. **Route files only.** Open the rubrics / playbooks / examples the route
   lists — nothing else, per
   [`context/L4_progressive_disclosure_policy.md`](context/L4_progressive_disclosure_policy.md).

`context/L1_project_constitution.md` (thesis, non-goals, stable principles)
and `context/L5_full_context_map.md` (one-line directory map) are reference
layers: load them when a route file points to them or when ambiguity
survives the routed files.

## Privacy status

**PRIVATE.** This repo must live behind a private remote and must never be
made public without a human content review. The review checklist, the
required `.gitignore`, and the never-include list are in
[`docs/private_repo_setup.md`](docs/private_repo_setup.md). The
`HARNESS.yaml` constraints block (`private_until_reviewed`, `no_secrets`,
`no_hidden_reasoning`) is binding on every future edit.

## Provenance discipline

Every claim in this repo traces to an observable artifact: a file path in
`method-harness-compiler` (docs/, schemas/, scripts/, tests/, the three
example packages) or a commit hash in its git log. Dataset records carry a
`source_artifact` field and a `synthetic` flag; grounded (`synthetic:
false`) records are preferred. If you cannot cite an artifact, do not write
the claim — the source project's own no-fabrication rule
(`TODO_FILL`-fails-validation, UNSCORED-never-guessed) applies here too.
