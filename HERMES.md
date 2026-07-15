# Fable conditional harness switch for Hermes

This small file is Hermes's first-priority project context.  It selects whether
to enter the harness; it is not the full harness.

Classify the user's request before reading more harness material.

- **Activate** for an explicit harness request; long or multi-step work;
  multiple agents; benchmark/evidence design; a completion, release, safety,
  permission, hook, CI, or governance claim; or a request to change routing.
- **Stay inactive** for a self-contained question, lookup, one-file mechanical
  edit, typo, or other routine verified task.  Do not load the full harness
  merely because this file exists.
- **When active**, first check whether `.fable-harness-off` exists at the
  repository root.  If it exists, stay inactive: it is the local rollback
  switch.  Otherwise read the repository-root `AGENTS.md`, then
  `core/GLOBAL_BOOTSTRAP.md`, and load only the route it selects.
- **When inactive**, use normal Hermes behavior.  Do not claim that the
  harness was applied.

For a prompt beginning `FABLE_ACTIVATION_PROBE`, inspect only the
repository-root `.fable-harness-off` marker; do not load routed material or do
task work.  Then return only this JSON object:
`{"schema_version":1,"harness":"active|inactive","reason":"trigger|routine|rollback"}`.
If the marker exists, return `inactive` with reason `rollback`.

Removing this file returns Hermes to its normal `AGENTS.md` / `CLAUDE.md`
context precedence.  The marker is a per-repository rollback that requires no
global configuration change.
