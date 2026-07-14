---
id: SETUP
layer: entry
purpose: AI-executable post-clone setup runbook - a user hands this file to ANY agent (Claude Code, Codex, Cursor, OpenCode, Hermes, a shell) and says "set it up"; the agent runs one idempotent script and reports.
read_when: Immediately after cloning, on any machine, by whichever agent the user has.
depends_on: [scripts/setup_harness.py, README.md]
used_by: [any-agent-post-clone]
tags: [entrypoint, setup, onboarding, ai-runbook, cross-runtime]
retrieval_keywords: [setup after clone, install harness, ai setup runbook, wire skill, codex opencode hermes setup, new machine]
---

# SETUP — for the AI that was just told "set this up"

You (the agent reading this) can complete the entire setup with one script.
It is idempotent (safe to re-run), stdlib-Python, offline, and does nothing
destructive. Do these steps in order and report each result to your user.

## 1. Baseline (always)

```bash
python scripts/setup_harness.py
```

This enables the repo's pre-commit gates and runs the 59-check integration
verification. All-PASS = the clone works on this machine. If Python ≥3.8 is
missing, stop and tell the user — that is the only prerequisite.

## 2. Wire YOUR runtime (pick the one you are)

- **Claude Code** — install global auto-discovery + the CLAUDE.md pointer:
  ```bash
  python scripts/setup_harness.py --wire-skill --wire-claude
  ```
  (Idempotent: existing pointers are detected and skipped, never duplicated.)
- **Codex CLI / Cursor / OpenCode / any AGENTS.md-convention agent** —
  nothing to install inside this clone: this repo's `AGENTS.md` is the
  entrypoint. To use the harness from OTHER repos, run
  `python scripts/setup_harness.py --print-wiring` and add the printed
  AGENTS.md snippet where your user keeps agent instructions. That snippet
  is the full future-work integration path: large/high-risk tasks enter
  `core/GLOBAL_BOOTSTRAP.md`; AI-harness maintenance enters
  `.claude/skills/adaptive-harness/SKILL.md`. Boundary you must honor: you
  may run the runners and draft findings, but you are never final authority
  (`docs/codex-delegation-policy.md`).
- **Hermes / router surfaces** — `--print-wiring` prints the routing row to
  add: deterministic scans you run directly; semantic checklists route to a
  strong-reasoning surface.

## 3. Optional: hands-off weekly report

```bash
python scripts/setup_harness.py --schedule
```

Windows: registers the weekly Mon 09:05 report-only scan. Other OS: prints
the crontab line for your user to approve. This scan is report-only BY CODE
— it structurally cannot modify anything.

## 4. Day-1 usage + your own improvement loop

Two things your user gets from the first session onward:

**Efficiency (day 1).** For any real task, classify it first, then load the
route bundle in ONE call — `python scripts/route_pack.py <task_type>` —
never the repo wholesale (live A/B 2026-07-11: 0.72x total cost vs free
orientation on its met, pre-registered bar; `docs/evidence.md` has the full
series including the two rounds that missed their bars). Model-tier
savings: `core/model_routing_playbook.md` (0.37x, confirmed). Codex
delegation savings: evidence in `docs/codex_long_task_ab.md` §2026-07-10
(−27% input tokens, confirmed); the operational wrapper it validates is
`core/CODEX_LONG_TASK_BOOTSTRAP.md`.

**Continuous optimization (week 1+, on YOUR project).** The improvement
loop is in this repo, not in anyone's personal setup:

```bash
python scripts/run_ai_review.py --mode scheduled_review   # report-only heartbeat
python scripts/grep_history.py --repeats                  # cross-run linkage on demand
python scripts/grep_history.py --open                     # what is still unapplied
```

Run the scan on a cadence (the §3 schedule covers the report-only
heartbeat). History is append-only, so findings are never silently lost; a
finding closes only when a commit says `applies REC-YYYYMMDD-NNN` — that
verb is exactly what `grep_history.py` treats as closure. The loop is
propose-only by design — your user dispositions, agents never self-approve.
Honest lineage: a stateful rolling-linkage mode used to do the cross-run
tagging automatically (its one live run auto-resolved 17 of 37 findings
with commit shas, 0 lost); its own pre-registered A/B (2026-07-14) then
showed plain re-derivation matches its recall at 1.00, so the state
machinery was retired (`applies REC-20260714-001`; `docs/evidence.md`
carries the B-loses row).

Honest portability note: the maintainer's own setup adds a personal layer
on top — correction-phrase mining hooks and a curated incident-rule vault
(personal tooling, NOT documented in this repo and not required), plus a
weekly /ai-review command whose sequencing with this loop IS documented in
`docs/ai_review_adaptive_harness_integration.md`. The in-repo loop above
works without any of them.

## 5. Verify and report

Tell your user, honestly: which steps ran, the integration-check result
line, and — if anything failed — the exact error. Then point them at
`README.md` §Quickstart for the two daily usage patterns and
`docs/evidence.md` for what this system is (and is not) proven to do.

## Notes for the agent

- Never run the raw `codex exec` path for shipping work from inside this
  repo's workflows; use the documented wrappers and briefs.
- `reports/` outputs are machine-local and gitignored by design; do not
  commit them.
- If your user asks "is this useful?", answer from `docs/evidence.md` —
  including its negative results — not from enthusiasm.
- Pushes to the canonical remote (`WenyuChiou/fable-method-harness`) are
  blocked by a `scripts/hooks/pre-push` guard so an autonomous session cannot
  push by accident. For an intentional push, run
  `FABLE_HARNESS_ALLOW_PUSH=1 git push ...`. Pushing your own fork is unaffected.
