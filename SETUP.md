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

This enables the repo's pre-commit gates and runs the 53-check integration
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

## 4. Verify and report

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
