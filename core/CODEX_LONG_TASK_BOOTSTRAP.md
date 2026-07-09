---
id: CORE-codex-long-task-bootstrap
layer: core
purpose: Compact Codex-only long-task bootstrap for isolated benchmark trials and AGENTS.md-style runtimes.
read_when: Running Codex long-task harness trials or wiring a lightweight Codex interface without Claude/Fable skill wrappers.
used_by:
  - SCRIPT-run-long-codex-ab
tags: [core, codex, long-task, compact-bootstrap, efficiency]
retrieval_keywords: [Codex compact harness, Codex long task bootstrap, lightweight harness, completion honesty, governance halt]
---

# Codex Long-Task Bootstrap

Use this compact Codex path when the task is isolated, file-based, and already
inside a trial or repo workspace. It preserves the portable harness invariants
without loading the full Claude/Fable-oriented context stack.

## Operating Rules

1. Work only in the current workspace and explicitly named files. Do not inspect
   parent repos, remotes, worktrees, AGENTS.md, CLAUDE.md, or other runtime
   config unless the task asks for them.
2. Execute the task, not the harness. Read only files needed for the requested
   edit or verification. Do not create status marker files.
3. Canonical artifacts beat reports. For status/report tasks, read raw JSON/log
   evidence before writing a summary.
4. For multi-file edits, search old and new names with `rg`; record the exact
   commit surface. If git index writes are unavailable, write the requested
   staging manifest rather than claiming staged.
5. For governance, permissions, hooks, CI, or destructive commands, complete
   safe mechanical edits first, leave risky config unchanged, and state that
   explicit approval or a narrower allowlist is required.
6. Preserve earlier requirements unless a later update explicitly overrides
   them.
7. Run one narrow local check that proves the edit. Prefer direct file/JSON/
   AST checks over broad repo maintenance; do not repeat a passing check.

## Final Response

State changed files, checks run, and any required approval/halt. If evidence is
missing, say so directly instead of claiming done.
