---
id: BOOTSTRAP
layer: entry
purpose: Shortest possible startup file — orient a future model into the harness in under one minute of reading
read_when: The very first file any agent reads, before L0, in any runtime that does not auto-load AGENTS.md or SKILL.md
depends_on: [context/L0_bootstrap.md, ROUTES.yaml]
used_by: [ROUTE-phase-review, ROUTE-tool-discovery, ROUTE-pr-review, ROUTE-eval-design, ROUTE-memory-update, ROUTE-runtime-export, ROUTE-repo-maintenance, ROUTE-ab-test-design]
tags: [entrypoint, bootstrap, startup]
retrieval_keywords: [start here, bootstrap, how to begin, entrypoint, startup sequence, minimal entry]
---

# BOOTSTRAP — start here

This repo is a **Fable-style project operating harness**: the observable,
documented working method of the `method-harness-compiler` project, packaged
as files you load incrementally. It is not general documentation and it is
not a prompt dump. It tells you *how to work on that project*, in a way that
survives model and session changes.

> **Not working on `method-harness-compiler`?** Use the portable path
> instead: read `core/GLOBAL_BOOTSTRAP.md` (core/ only — skip the ladder below).

## Startup sequence (mandatory, in order)

1. Read `context/L0_bootstrap.md` — what this harness is and is not.
2. Read `context/L2_current_phase.md` — where the project actually stands
   right now, what is allowed, what is forbidden.
3. Read `context/L3_task_router.md` — classify the task you were given into
   one of the 8 task types.
4. Open `ROUTES.yaml` and resolve your route (`ROUTE-*`). Read its
   `required` files in full. Open `optional` files only with a stated
   one-line reason.

## Rules that are never optional

- **Do not read the whole repo.** If you feel you need everything, you have
  either misclassified the task or hit a real routing gap — say so
  explicitly instead of bulk-loading (`context/L4_progressive_disclosure_policy.md`).
- **Stay inside the current phase.** Work outside the `allowed` list in L2
  requires an explicit GO / CONDITIONAL_GO / NO_GO decision, not silence.
- **Self-check before returning.** Score your draft against the rubric(s)
  your route names. Fix what scores below 3 or disclose why you cannot.

## Output contract

Every substantive deliverable ends with four short sections:

1. **Decision** — what you concluded or produced (one paragraph or verdict).
2. **Risks** — what could be wrong with it, honestly stated.
3. **Required changes** — what must change in the project (or in this
   harness) as a result; "none" is an acceptable answer.
4. **Next actions** — the smallest concrete next steps, in order.

## After the work

If your work changed the project's direction, phase, or standing decisions,
update `memory/` per `operating_model/project_memory_policy.yaml` — append,
never overwrite. If it exposed a gap in this harness itself, record it; the
harness improves through recorded friction, exactly like the project it
distills.
