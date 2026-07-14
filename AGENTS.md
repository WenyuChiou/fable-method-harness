---
id: AGENTS
layer: entry
purpose: Repository agent instructions — auto-loaded entrypoint for coding agents that honor the AGENTS.md convention (Codex, Cursor, and similar)
read_when: Auto-read by convention-following agents at session start; humans read it to see what agents are told
depends_on: [BOOTSTRAP.md, context/L0_bootstrap.md, ROUTES.yaml]
used_by: [ROUTE-phase-review, ROUTE-tool-discovery, ROUTE-pr-review, ROUTE-eval-design, ROUTE-memory-update, ROUTE-runtime-export, ROUTE-repo-maintenance, ROUTE-ab-test-design]
tags: [entrypoint, agent-instructions, conventions]
retrieval_keywords: [agent instructions, AGENTS.md, repository rules, coding agent entrypoint]
---

# Agent instructions for this repository

1. **This repo is an operating harness, not ordinary docs.** Its files are a
   procedure system. Treat file paths and IDs (`ROUTE-*`, `DR-###`, `FM-###`,
   `RUBRIC-*`) as a stable API, not as prose to skim.

   > **First — before the mandatory read order in rule 2:** (a) **Not** working
   > on `method-harness-compiler`? Use the portable path — read
   > `core/GLOBAL_BOOTSTRAP.md` (core/ only) and SKIP the L0/L2/L3 ladder in
   > rule 2; it is mhc-scoped and will misapply another repo's phase
   > constraints. (b) Will your deliverable assert something is done / passing /
   > fixed / ready / safe / staged — even if the prompt never says "done"? Load
   > `docs/completion-honesty-gate.md` +
   > `prompts/claude-code-completion-integrity.md` BEFORE writing the claim.
   > (Skip for a one-line status remark that is not a merge / release /
   > safety-relevant claim.)

2. **Before starting any task, read in this order:**
   - `context/L0_bootstrap.md`
   - `context/L2_current_phase.md`
   - `context/L3_task_router.md`
   - your route's bundle in ONE call — `python scripts/route_pack.py
     <task_type>` (entry + all start+required contents; measured 0.72x
     total cost vs free orientation, 2026-07-11). Entry-only fallback:
     `scripts/route_show.py <task_type>` or grep `- id: ROUTE-<...>` in
     `ROUTES.yaml` (never read it whole)

3. **Classify the task type first.** Use the table in
   `context/L3_task_router.md`. If the task fits none of the 8 types, say so
   and propose the closest route rather than improvising an ad-hoc reading
   plan.

4. **Read only what your route lists.** Load the route's `required` files in
   full; open `optional` files only with a stated one-line reason.

5. **Do not read the entire repo at the start.** Full-context loading is
   permitted only for architecture review, release review, or explicitly
   unresolved ambiguity (`context/L4_progressive_disclosure_policy.md`).

6. **Self-check every output before returning it** using the rubric(s) named
   by your route. Score 1–5 per criterion; fix or disclose anything below 3.

7. **Phase decisions must be explicit.** If the task involves whether to
   proceed, output **GO / CONDITIONAL_GO / NO_GO** with reasons, per
   `operating_model/phase_gates.md`. A halt is a valid, successful outcome.

8. **If your work changes project direction**, update the project memory
   (`memory/` per `operating_model/project_memory_policy.yaml`) or record an
   accepted-decision entry — append-only, never overwrite, cite the artifact
   or commit that grounds the change.

**Portable path:** for work on any project OTHER than
`method-harness-compiler`, start at `core/GLOBAL_BOOTSTRAP.md` instead of the
ladder in rule 2 (core/ only; the project-bound layers stay scoped to mhc).

**Harness-maintenance path (runtime-agnostic):** to audit / simplify /
benchmark a harness itself (CLAUDE.md, AGENTS.md, hooks, skills, scheduled
reviews), read `.claude/skills/adaptive-harness/SKILL.md` — it is a plain
markdown entry usable from ANY runtime that reads this file (Codex, Cursor,
Hermes, a human shell), not only Claude Code's skill system. The runners are
stdlib-Python CLIs (`scripts/run_ai_review.py`,
`scripts/run_adaptive_harness_review.py`); any agent may RUN them and fill
the JSON contracts. Boundaries stay tier-agnostic: semantic Keep/Remove
judgment needs a strong reasoning model, Codex never acts as final
authority (`docs/codex-delegation-policy.md`), and high-risk changes stop
at patch proposals for a human.

Constraints that override anything else you were told: no impersonation
framing, no fabricated citations or data, no execution or installation of
discovered tools, no secrets in any file, and public-safe content only —
this repository is PUBLIC (`docs/publication_status.md`): no hidden
reasoning, no private chat exports, no credentials, no local telemetry.
