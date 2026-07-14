---
id: DOC-agent-routing-policy
layer: doc
purpose: Concrete routing matrix binding the harness abstract tiers to the operator three-surface stack (Hermes / Claude Code Opus baseline / Opus + distilled / Fable + distilled / Codex).
read_when: Deciding which agent surface and mode executes an incoming task; when a surface should escalate or delegate.
depends_on:
  - ../operating_model/model_routing_policy.yaml
  - ../operating_model/decision_rules.yaml
  - ../operating_model/review_protocol.md
  - ../core/portable_operating_model.md
used_by:
  - DOC-agent-optimization-runbook
  - PROMPT-hermes-router
  - operator-session
tags:
  - routing
  - agent-stack
  - hermes
  - claude-code
  - codex
  - escalation
retrieval_keywords:
  - which agent
  - routing matrix
  - hermes vs claude vs codex
  - when to escalate
  - when to delegate to codex
  - fable completion review
  - task class executor
---

# Agent Routing Policy — Concrete Surface Bindings

## 1. Purpose

Bind the harness's ABSTRACT model classes to the operator's REAL three-surface
agent stack, so an incoming task lands on the right surface and mode without
re-deriving the routing rules each time.

> **Provenance:** This artifact encodes the operator's Hermes / Claude Code / Codex
> stack (source: model-routing-benchmark `universal_agent_optimization_prompt.md`)
> bound to this harness's existing doctrines cited inline; it is NOT distilled from
> method-harness-compiler.

**Integration principle.** `operating_model/model_routing_policy.yaml`
(`OM-model-routing-policy`) deliberately keeps model classes abstract
(`cheap_fast | balanced | strong_reasoning`) and states that *"concrete model
bindings belong to runtime configuration."* This overlay IS that runtime binding.
Quality is assured by the AUTHOR-AGNOSTIC layered review gate
(`operating_model/review_protocol.md`, `OM-review-protocol`) — not by routing
everything to the strongest surface. The strongest surface is a cost, not a default.

## 2. Routing matrix

Tier column maps to `OM-model-routing-policy` tiers 0..4. Escalation is one-way
within a round (see §3), mirroring that policy's `routing_rules`.

| Task class | Primary executor + mode | Tier | Escalates to | Notes |
|---|---|---|---|---|
| Telegram/daily ops, file lookup, calendar/gmail/drive, cron, session search, memory/skills, simple *verified* edits | **Hermes** (operator/router) | 1 (cheap_fast) | Claude Opus baseline | Router + memory layer + lightweight executor + final reporter. Simple edits only when the diff is verifiable on disk (`DR-021`); anything with judgment surface escalates. |
| Clear-scope debug, OAuth-provider-plugin failures, log diagnosis, evidence-first triage | **Claude Code — Opus baseline** | 2–3 (focused) | Opus + distilled (on unclear root cause) | Evidence-first diagnosis when scope is clear. Read-only discovery first (`DR-012`); never guess a fix (`DR-002`). |
| Complex architecture, multi-phase orchestration, benchmark design, agent-routing design, release-validation plans | **Claude Code — Opus + distilled** | 3 (strong_reasoning) | Human gate / phase gate (tier 4) | Default lens for high-complexity / orchestration. Drives `CORE-workflow-orchestration-playbook`; release plans route through `operating_model/phase_gates.md`. |
| Completion honesty, artifact mismatch, process-integrity, timeout-retry-dedup ambiguity, background jobs, *"can we honestly say done?"* | **Claude Code — Fable alias + distilled** | 3 (process-integrity lens) | Human gate (tier 4) on release/permission calls | Premature-done prevention + honest-failure enforcement. Anchors `DOC-completion-honesty-gate`; halt-is-success (`DR-010`), no-silent-pass (`DR-011`), publish-own-failures (`DR-009`). |
| Mechanical multi-file edits, boilerplate, test skeletons, stable-pattern migration (clear acceptance criteria) | **Codex** (scoped executor) | 2 (balanced) | Claude Code (mandatory review on return) | Never final authority. Brief-first (`PROMPT-codex-task-brief-template`); allowed-files + out-of-scope declared; **do not commit unless explicitly asked**. |
| Harness maintenance (audit/simplify/benchmark a CLAUDE.md-AGENTS.md-hooks-skills setup; review reports; improvement loop) | **adaptive-harness system** — deterministic runners on ANY surface (stdlib CLIs; Hermes/Codex/cron may run them); semantic checklists on Claude Code Opus/Fable | 1 (runners) / 3 (checklists) | Human gate for every patch proposal | Entry per runtime: `.claude/skills/adaptive-harness/SKILL.md` §Runtime portability. Scheduled runs report-only BY CODE; high-risk changes stop at patch proposals. |

## 3. Escalation triggers

One-way escalation ladder, mirroring `OM-model-routing-policy` `routing_rules`
(*"Escalation is one-way within a round"*). **Hermes escalates up** — it never
resolves these itself:

- **Architecture judgment** — any design/boundary/trade-off call → Opus + distilled.
- **Unclear root cause** — Opus baseline cannot pin the cause from evidence → Opus + distilled.
- **Benchmark / report artifacts disagree** — a derived report contradicts source
  data → Fable + distilled (do NOT trust the derived report as proof; `DR-021`).
- **High-risk completion claim** — anything asserting "done / fixed / shipped" on a
  critical path → Fable + distilled completion review (§5).
- **Multi-agent reconciliation** — 2+ delegate outputs to merge/adjudicate →
  Opus + distilled (`CORE-workflow-orchestration-playbook`).
- **Large mechanical edit better delegated** — stable-pattern bulk with no
  security/governance surface → delegate to Codex (§4); size increases the case for delegation.

Ladder shape: **Hermes (t1) → Claude Opus baseline (t2–3) → Opus + distilled (t3) →
Fable + distilled (t3 gate lens) → human / phase gate (t4)**. Tier 3 → tier 4 on
release, permissions, or language/judgment calls (`OM-model-routing-policy` tier 4).

## 4. When to delegate to Codex

Delegate mechanical, scoped, stable-pattern work; keep judgment on Claude Code.

- **Brief-first.** Write the brief before delegating — see
  `PROMPT-codex-task-brief-template`. No brief, no delegation.
- **Scoped.** Declare **allowed-files** and an explicit **out-of-scope** list. Codex
  edits only inside the allowed set.
- **No commit unless authorized.** Codex must not `git commit`/`git push` unless the
  brief explicitly says so; **do not commit unless explicitly asked** is a standing rule.
- **Computed artifacts only via runners** (`DR-004`) — Codex regenerates via the
  documented runner, never hand-edits a computed output.
- **Review on return.** A delegate-returned diff is a MANDATORY review trigger:
  Claude Code reviews the diff through `operating_model/review_protocol.md`
  (`OM-review-protocol`) before anything ships. Verify the delegate's on-disk
  observations (`DR-021`); a contract change ships with its regression net (`DR-014`).

**Do NOT delegate to Codex:** ambiguous root-cause, security/governance decisions,
release gates, completion claims, or final verification authority.

## 5. When to trigger Fable-method completion review

Route to the **Claude Fable alias + distilled** completion-integrity lens whenever a
task is about to claim done, or when an artifact and its evidence may disagree.

- Trigger conditions, checklist, and pass/fail bar: `DOC-completion-honesty-gate`.
- Copy-paste prompt + stop conditions: `PROMPT-claude-code-completion-integrity`.
- Enforces: halt-is-success (`DR-010`), no-silent-pass (`DR-011`),
  publish-own-failures (`DR-009`), never-guess-on-uncertainty (`DR-002`).

Fire it on: high-risk completion claims, artifact/report mismatch, timeout-retry-dedup
ambiguity, background-job "did it actually finish?" checks, and any *"can we honestly
say done?"* moment.

## 6. Anti-patterns

| Anti-pattern | Why it fails | Do instead |
|---|---|---|
| Treating **Codex** as final verification authority | Codex is a scoped executor, not a gate; it has no completion authority | Claude Code review on return (`OM-review-protocol`); tier-4 human on release |
| Reclassifying mechanical bulk as "judgment" to avoid delegating | Hoards cheap work on the strongest surface; the reflex to reclassify IS the signal to delegate | Delegate stable-pattern bulk to Codex (§4); size increases the case for delegation |
| Shipping ANY surface's output ungated | The quality invariant is the AUTHOR-AGNOSTIC gate, not the author | Route every diff through `operating_model/review_protocol.md` before ship |
| **Hermes** making architecture / root-cause / governance calls | Tier-1 router lacks the strong-reasoning lens; silent wrong-call risk | Escalate to Opus + distilled (§3); Hermes routes, it does not decide |
| Trusting a derived report / benchmark artifact as proof of done | Derived reports can drift from source; `DR-021` requires on-disk verification | Fable + distilled completion review; verify against source (`DOC-completion-honesty-gate`) |
| Codex (or any delegate) committing before Claude reviews | Pushing-then-reviewing defeats the gate | **Do not commit unless explicitly asked**; review diff first, then a reviewed commit |

---

### Output contract (per `core/` convention)

- **Decision:** Route each incoming task by its class in §2, at the lowest tier that
  passes the quality threshold; escalate one-way (§3), never sideways or down.
- **Risks:** Over-routing to the strongest surface (cost, bottleneck); under-routing a
  judgment task to Hermes/Codex (silent wrong-call); ungated ship of any surface's output.
- **Required changes:** Keep this matrix in sync with `OM-model-routing-policy` tiers
  and with the new anchors (`DOC-completion-honesty-gate`,
  `PROMPT-codex-task-brief-template`) as they evolve; do not fork the tier definitions here.
- **Next actions:** For an incoming task — classify (§2) → pick surface + mode →
  if delegating, brief-first (§4) → on any done-claim, run completion review (§5) →
  review through `OM-review-protocol` before ship. **Do not commit unless explicitly asked.**
