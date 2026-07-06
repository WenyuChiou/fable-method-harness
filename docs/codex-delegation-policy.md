---
id: DOC-codex-delegation-policy
layer: doc
purpose: The single canonical Codex delegation policy - when to delegate, when not to, the non-negotiable mechanics, and the one tripwire number - so CLAUDE.md and the codex-delegate skill can point here instead of restating (and drifting).
read_when: Deciding whether to delegate a task to Codex; running codex_delegation_review; resolving a conflict between delegation statements in other files.
depends_on:
  - ../prompts/codex-task-brief-template.md
  - ../prompts/ai-review-modes.md
used_by:
  - PROMPT-ai-review-modes
  - SCRIPT-run-ai-review
  - global /ai-review slash command (~/.claude/commands/ai-review.md)
tags: [doc, codex, delegation, policy, routing, tripwire, canonical]
retrieval_keywords: [codex delegation policy, when to delegate codex, tripwire threshold three files, brief first, allowed files scope fence, acceptance criteria, codex never commits, review before ship, mechanical multi-file]
---

# Codex delegation policy (canonical)

**One-line rule.** Delegate to Codex **iff** (a) the transform is
mechanical / stable-pattern, (b) it spans **≥ 3 files** or is pure
boilerplate/scaffold/migration, (c) it touches no security, governance,
or judgment-bearing-CJK surface, and (d) you can write a one-shot brief
with an Only-modify scope fence and a runnable acceptance command.
Otherwise Claude-direct. Either way Claude reviews the diff and commits —
the author-agnostic review gate is the invariant, whoever wrote the code.

**The canonical tripwire number is ≥ 3 files.** Statements of "≥ 5 files"
anywhere (e.g. older skill snippets) are stale and should be corrected to
point here. Catching yourself reclassifying clearly-mechanical bulk as
"judgment" to keep it IS the delegation signal.

Measured reality (dogfood data, codex-delegate skill): single-file < 50
lines ≈ 1× (don't bother); 8-file mirror sync = 17-22×; > 10-file rename
≈ 3×; > 20-file sweep ≈ 7×. The 3-5 file band is unmeasured — treat the
tripwire as a floor for *mandatory* delegation, not a claim of measured
speedup at exactly 3 files (benchmark case
`codex_delegation_vs_main_agent_mechanical` covers this gap).

## Codex is suitable for

- Mechanical multi-file transforms with one stable pattern: batch edits,
  terminology/rename sweeps, path fixes.
- Boilerplate / scaffold: test skeletons, config files, doc templates,
  migrations with a clear pattern.
- Bulk mechanical CJK: find-replace, byte-stable mirror edits, multi-locale
  mirror sync (measured 17-22× saving).
- Adding type hints / docstrings / logging en masse; generating unit tests
  from existing implementations.
- Data-pipeline or analysis scripts from precise specs (input path, output,
  tests all stated).
- Second-opinion review of a Claude draft, as an independent pass (input,
  never verdict).

Litmus: *the brief can be written in one shot AND the diff can be reviewed
objectively.*

## Codex is NOT suitable for

- Architecture / design decisions, API contracts, dependency choices.
- Ambiguous root cause, live-state debugging, anything needing this
  session's context or tight user iteration.
- Research direction.
- Security-sensitive code: auth, input validation, secrets, permissions.
- Governance surface: CLAUDE.md, AGENTS.md, settings/hooks, the harness
  itself, memory files. (Any statement elsewhere that routes "governance
  changes" to Codex is stale and superseded by this policy.)
- Judgment-bearing CJK: translation, 語感, tone.
- Final verification authority, release decisions, or any "done" claim.

## Codex MUST (non-negotiable mechanics)

1. **Brief-first, on disk** (`.ai/codex_task_<NN>_<slug>.md`), following
   prompts/codex-task-brief-template.md: Context / Goal / In scope /
   Out of scope / **Files allowed (Only-modify fence)** / Constraints /
   **runnable Acceptance criteria** / Verification commands / Output contract.
2. **Explicit allowed-files and out-of-scope lists.** Writes outside the
   fence ⇒ reject the diff.
3. **Invoke via the codex-delegate skill wrapper**, never raw `codex exec`
   for shipping work (the F14 hook blocks raw invocations for a measured
   reason: 99% bypass rate before it existed).
4. **Sandbox pinned**: `--sandbox workspace-write`; deprecated flags
   (`--full-auto`) and stale models are hook-blocked.
5. **Never commit or push** — not in the brief, not "helpfully". One commit
   per agent boundary, made by Claude after review. (Known gap, tracked as
   an Experiment: the prohibition is prose-only; a wrapper HEAD-sha
   assertion would make it mechanical.)
6. **Return diff for review.** Claude reads the result contract
   (`.result.json`), reviews the diff, runs the acceptance commands, fixes
   < 20-line gaps, and only then commits (review trigger #4:
   "delegate just returned" always fires).
7. **Bounded output capture only** — wrapper contract or `-o/--output-schema`;
   never raw stdout redirects (the 7 GB incident).

## Fallbacks

- Codex quota / failure ⇒ Claude takes the task over directly; the brief is
  already the spec.
- Gemini lane is DEPRECATED (2026-06-18, fails closed): judgment-bearing CJK
  → Claude-direct; bulk mechanical CJK → Codex. Any remaining "route to
  gemini" row anywhere is stale and superseded by this paragraph.

## Review integration

`codex_delegation_review` mode (prompts/ai-review-modes.md) audits practice
against this file. Deterministic signals: F14 hook block telemetry, this
file's existence + reference integrity (`run_ai_review.py --mode
codex_delegation_review`), deprecated-lane mention counts. Semantic audit:
brief quality, tripwire drift, post-delegate review compliance.
