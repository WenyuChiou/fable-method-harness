---
id: DOC-adoption-guide
layer: doc
purpose: User-facing guide for deciding whether to adopt the portable harness, wiring it into another project, rolling it back, and measuring its local value.
read_when: Before adding the harness pointer to another repository or explaining its controls and evidence boundary to a project owner.
depends_on: [../SETUP.md, ../docs/runtime_activation_contract.md, ../docs/codex_harness_integration.md, ../docs/evidence.md]
used_by: [README, README.zh-TW]
tags: [adoption, onboarding, codex, hermes, rollback, evidence]
retrieval_keywords: [adopt harness, integrate another project, Codex AGENTS.md, Hermes shim, rollback marker, measure local value]
---

# Adopt the harness in your project

[繁體中文](adoption-guide.zh-TW.md)

Use this guide when you want the harness to support another repository. You do
not need to copy its full instruction set into that repository. Keep this
repository as the harness root and add one generated pointer to the agent
instructions used by the target project.

## Decide first

| Your task or project | Adopt it? | Why |
|---|---:|---|
| Long or multi-step work | Yes | It classifies the task and loads only the required route. |
| Multiple agents or conflicting outputs | Yes | It adds explicit ownership, verification, and reconciliation. |
| Release, completion, security, permission, hook, CI, or governance work | Yes | A wrong completion claim is expensive. |
| Building or maintaining an AI harness | Yes | The adaptive review loop can propose measured improvements. |
| Self-contained question, lookup, typo, or one-file mechanical edit | No | The extra procedure costs more than it returns. |

It does not make a model more capable. Its purpose is to reduce unnecessary
context, route work deliberately, and make completion claims auditable.

## What you control and what stays internal

You control when it is enabled, which repository receives the pointer, and
whether a proposed change is accepted. The agent-facing layer handles route
selection, review gates, telemetry, and rule lifecycle state. You do not need
to read or edit that internal state during normal use.

| You need to know | The harness handles internally |
|---|---|
| Is this task worth activating for? | Which minimal route files to load |
| How do I install or remove it? | Conditional activation receipts and telemetry |
| What evidence supports a benefit? | Candidate/active/rollback lifecycle bookkeeping |
| Can an agent change my governance by itself? | No: high-risk proposals stop for human approval |

## Quick start

### 1. Verify the harness clone

```bash
git clone https://github.com/WenyuChiou/fable-method-harness
cd fable-method-harness
python scripts/setup_harness.py
```

The setup is idempotent and runs the integration checks. If it does not pass,
stop there; do not wire an unverified clone into another project.
It also configures this clone's Git hooks path; see [SETUP.md](../SETUP.md)
for that deliberate local side effect.

### 2. Generate the runtime wiring

```bash
python scripts/setup_harness.py --print-wiring
```

For Codex, Cursor, OpenCode, or another `AGENTS.md`-convention agent, paste the
generated pointer into the target repository's `AGENTS.md` (or your global
agent instructions). Keep the generated path unchanged: it points to this
harness clone and loads it only for qualifying work.

For Hermes, copy the target-ready `HERMES.md` shim emitted by this command into
the target repository, then add its generated router row when Hermes receives
harness-maintenance work directly. Do not paste the full harness into Hermes's
standing prompt.

### 3. Start with one qualifying task

Use a real multi-step, completion-sensitive, or governance-sensitive task.
In a fresh session, confirm that the agent classifies the task before loading
the routed bootstrap. For a routine task, confirm that it stays inactive.

## Roll back immediately

Create an empty `.fable-harness-off` file at the target repository root. The
next eligible task remains inactive without changing a global setting:

```bash
touch .fable-harness-off
```

In PowerShell, use `New-Item .fable-harness-off -ItemType File` instead.

Delete that marker to restore automatic conditional activation. Removing a
repository-level pointer from `AGENTS.md` disconnects that repository; remove
any separately installed global pointer as well.
For Hermes, removing its installed `HERMES.md` shim restores native context
precedence. See [the conditional-activation contract](runtime_activation_contract.md)
for the exact behavior.

## Measure your own value before expanding it

The published results are evidence for this repository's frozen tasks and
runtime bindings, not a promise for your project. Start with a small paired
control/treatment evaluation that measures correctness, total tokens, latency,
and actual corrective work. Keep a rule as `candidate` until the result is
complete; promote it only after it demonstrates benefit without harmful cases.

Current public evidence shows:

| Surface | What is measured | What you must not infer |
|---|---|---|
| Codex long tasks | 27% fewer input tokens, 59% fewer tool calls, and 34% less wall-clock time in this repository's 80-trial A/B | A general correctness or capability lift |
| Codex adaptive loop | 14.17% lower total tokens and 32.78% lower latency in one frozen six-pair experiment | The same benefit for another project or task mix |
| Hermes conditional activation | Correct activation/rollback behavior and 69.9% less fixed context | API-token or speed savings; the adaptive-loop result is UNSCORED |

Read [the evidence ledger](evidence.md) before making an efficiency claim in
your own repository. Publish null and failed results as well as successes.

## Extend a project-specific harness safely

Start with the portable pointer and keep your project-specific rules local.
Add a route or rule only when you can state its trigger, expected benefit,
rollback, and verification command. For hooks, permissions, settings, CI, or
governance changes, create a proposal and require human approval rather than
letting the loop self-modify.

For the operating details, continue with [Codex integration](codex_harness_integration.md)
and the [adaptive-harness skill](../.claude/skills/adaptive-harness/SKILL.md).
