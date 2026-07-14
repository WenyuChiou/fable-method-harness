---
name: adaptive-harness
description: >-
  Use this skill when auditing, simplifying, benchmarking, or refactoring an
  AI/agent project harness, including CLAUDE.md, AGENTS.md, slash commands,
  skills, subagents, hooks, tool routing, scheduled reviews, AI-review
  reports, benchmark scaffolds, and rolling harness maintenance. Not for
  ordinary code review of application code (use code-review) or for running
  the method-harness-compiler project (use the root harness ladder).
id: SKILL-adaptive-harness
layer: entry
purpose: Skill-runtime adapter for the adaptive harness system - maps the 9 review modes onto the two deterministic runners plus the semantic checklists, under the report-only / patch-proposal safety posture; linkage queries go to the grep-history helper.
read_when: A skill-aware runtime (Claude Code and similar) invokes adaptive-harness; or when wiring the improvement loop into a new project.
depends_on:
  - ../../../scripts/run_adaptive_harness_review.py
  - ../../../scripts/run_ai_review.py
  - ../../../scripts/grep_history.py
  - ../../../prompts/ai-review-modes.md
  - ../../../docs/ai_review_adaptive_harness_integration.md
  - ../../../schemas/review_report.schema.yaml
  - ../../../schemas/recommendation.schema.yaml
used_by: [claude-code-skill-runtime, AGENTS, PROMPT-hermes-router]
tags: [entrypoint, skill, adaptive-harness, ai-review, report-only]
retrieval_keywords: [adaptive harness skill, improvement loop, grep history linkage, harness inventory, skill fit review, patch proposal mode, scheduled harness review, ai review integration, harness cleanup]
---

# SKILL: adaptive-harness

**Relationship to the root `SKILL.md`:** the root file is the repo-level
launcher for working ON the method-harness-compiler project (the L0→L3
ladder). THIS adapter is the skill-aware runtime entry for the **adaptive
harness system** — the improvement loop that keeps a harness (this repo's or
the operator's global one) reviewed, simplified, and benchmarkable over time.
AI-review is the local reviewer; adaptive-harness runs the harness-shaped
review modes over its findings. One system, shared schemas, two runners.
Cross-run linkage (which findings repeat, which are closed) is answered
on demand by `scripts/grep_history.py` — the stateful rolling machinery was
retired per REC-20260714-001 after the pre-registered A/B measured no recall
advantage over re-derivation (a B-loses result that shipped to
`docs/evidence.md`).

## The loop you are operating

1. **Observe** — run AI-review (`python scripts/run_ai_review.py --mode <m>`)
   and, for harness-shaped scans, the adaptive runner modes below. For
   cross-run questions: `python scripts/grep_history.py --repeats` / `--open`
   / `--rec REC-YYYYMMDD-NNN` (read-only; append-only history + git log).
2. **Diagnose** — answer the mode's semantic checklist in
   `prompts/ai-review-modes.md` with cited evidence.
3. **Classify** — every finding gets Keep / Simplify / Remove / Replace /
   Merge / Cache / Experiment per `schemas/recommendation.schema.yaml`.
4. **Act safely** — low-risk docs drift may be edited only when the human
   explicitly allowed it THIS session; high-risk (hooks, subagents, prompts,
   permissions, settings, CI) ⇒ `--mode patch_proposal` renders an
   apply/rollback sheet and STOPS; uncertain value ⇒ add a case to
   `benchmarks/harness_cases.yaml` (pre-registered, never self-graded).
5. **Record** — findings enter via `--ingest findings.json` (validated);
   the runner appends JSONL history and renders JSON→MD deterministically.
   Never hand-write report numbers.
6. **Schedule next** — the report's `next_review_trigger` names the cadence;
   scheduled runs stay report-only.

## Modes

| Mode | Runner call | Semantic checklist |
|---|---|---|
| `harness_inventory` | `run_adaptive_harness_review.py --mode harness_inventory` | none (deterministic) |
| `harness_cleanup_review` | `--mode harness_cleanup_review` | ai-review-modes.md §harness_cleanup_review |
| `code_invocation_review` | `--mode code_invocation_review` | §code_invocation_review |
| `ai_review_integration` | `--mode ai_review_integration` | integration doc checklist |
| `skill_fit_review` | `--mode skill_fit_review` | do skill descriptions still match usage? dead skills? mis-triggering? |
| `diff_only_review` | `--mode diff_only_review --since-ref <ref>` | §diff_review |
| `scheduled_harness_review` | `--mode scheduled_harness_review` | NONE by design (report-only) |
| `experiment_design` | `--mode experiment_design` | §experiment_review |
| `patch_proposal` | `--mode patch_proposal` | render only; human applies |

(`rolling_improvement_review` was retired — applies REC-20260714-001;
linkage queries: `scripts/grep_history.py`.)

## Safety boundaries

Enforced BY CODE (runner invariants, regression-pinned):

- Scheduled runs are report-only: `--ingest` rejected, `source=
  scheduled_runner`, `changes_made` must be empty, zero writes outside
  `--output`.
- `--dry-run` writes nothing.
- Ingest findings are validated (required fields, enums, REC-id pattern,
  human-approval flag on high-risk Remove/Replace) or rejected.
- `grep_history.py` is read-only by construction; a legacy
  `rolling_state.json` (from the retired loop) is still READ by
  `patch_proposal` so pending items never vanish, but nothing writes it.

Operating POLICY (this skill's instructions to the agent — not machine-
enforced; violating them is a harness-governance violation):

- Findings are recommendations; the human decides what merges.
- Deleting prompts / subagents / hooks, changing permissions,
  `.claude/settings.json`, or CI: patch proposal + human approval, always.
- No self-modifying loop: never edit this SKILL.md, the runners, or the
  schemas without a human-reviewed commit.
- Loop-closure convention: a commit that applies a recommendation says
  `applies REC-YYYYMMDD-NNN` (or `resolves ...`) in its message; a revert
  says `reverts REC-...`; anything else must not bare-cite REC ids — the
  applies/resolves verb is what `grep_history.py` treats as closure.

## Model tiers

Deterministic runners + `grep_history.py`: any tier (code — Haiku or cron
can invoke).
`skill_fit_review` / `diff_only_review` semantic passes: Sonnet-capable.
`harness_cleanup_review` interpretation and
`patch_proposal` judgment: Opus/Fable-class. Codex: mechanical scoped work
only, never final authority (docs/codex-delegation-policy.md).
Executed tier evidence: `benchmarks/model_compatibility_cases.yaml` (Haiku
4/4, Sonnet 2/2 real runs; Codex live compliance UNVERIFIED — plan in
`docs/model_compatibility_test_plan.md`).

## Runtime portability (this skill is NOT Claude-Code-only)

The system's contracts are plain files + stdlib-Python CLIs; the skill
format is just one discovery wrapper. Entry per runtime:

| Runtime | Entry | Notes |
|---|---|---|
| Claude Code | this SKILL.md via the skill system | full loop incl. semantic checklists |
| Codex / Cursor / AGENTS.md-convention agents | `AGENTS.md` §Harness-maintenance path → this file as markdown | may RUN runners, draft findings JSON, execute scoped mechanical fixes under docs/codex-delegation-policy.md; NEVER final authority, never applies proposals |
| Hermes (or any router surface) | `prompts/hermes-router.md` routing row "harness maintenance" | runs deterministic scans directly; routes semantic checklist work to a strong reasoning surface |
| Human / cron / any shell | the CLIs directly | `python scripts/run_ai_review.py --mode … `; scheduled = report-only by code |

What travels with any runtime: the runners (stdlib, offline), the schemas
(`--ingest` validation is runtime-blind), the checklists (markdown), the
safety invariants (coded in the runners, not in this wrapper).

## Scenario matrix (適用不同場景)

| Scenario | Invocation | What degrades gracefully |
|---|---|---|
| This repo self-audit (default) | runners with no flags | nothing — full collector set |
| Any OTHER repo / project harness | `--target <repo-path>` | INDEX/ROUTES/benchmark collectors mark `skipped` when those files don't exist; report stays schema-valid |
| Operator's global harness (~/.claude) | default `--home` telemetry collectors; target stays a repo | missing ~/.claude scripts mark `unavailable`, never fabricated |
| Headless / scheduled | `--mode scheduled_review` / `scheduled_harness_review` | report-only BY CODE: --ingest rejected, no ledger writes, no proposals |
| Hermetic / CI | `--no-home --dry-run` | zero machine-specific dependencies, zero writes |
