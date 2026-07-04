---
id: DOC-distillation-setup-checklist
layer: doc
purpose: Phase-1 pre-run checklist that instruments a project so a working-style distillation cycle can yield load-bearing signal (git-from-commit-0, base-rate control arm, >=2 projects, non-priming task sourcing); the go/no-go gate to run BEFORE observing.
read_when: Before starting any working-style distillation cycle on a project; deciding whether a project is distillable or only negative-findings-capable.
depends_on:
  - ./analyst-prompt.md
  - ./distillation-log.md
  - ../operating_model/decision_rules.yaml
used_by:
  - ROUTE-distillation
tags: [distillation, checklist, setup, base-rate, non-priming, working-style]
retrieval_keywords: [distillation setup, pre-run checklist, base-rate control arm, git from commit 0, non-priming, instrument the project, go no-go gate]
---

# Phase 1 — Pre-run setup checklist (do this BEFORE a distillation cycle starts)

**The distillation cycle** is: **(1) this checklist** → **(2) observe + analyse** with
[`analyst-prompt.md`](analyst-prompt.md) (Track-1 pure observation of the project's traces,
gated) → **(3) land** survivors + negatives into [`distillation-log.md`](distillation-log.md)
and the harness `memory/` + `datasets/` surfaces. This file is step 1.

**Purpose.** A project is only distillable if it is *instrumented for it up front*. This is the
"prepare the raw material" step. If a box is unchecked, the setup is not fixed — you will get the
2026-07-04 pilot's result (ceiling behaviours + attribution confounds + **zero** load-bearing
traits, only negative findings). Run this at project kickoff, not after.

**The two non-negotiables are §1 (git) and §2 (base-rate arm).** Without both, do not start a
distillation cycle — you will only reproduce the `model-routing-benchmark` pilot (n=1, untracked,
operator-authored tasks → nothing provably the subject's).

---

## §1 — Version control from commit 0  (gives you TIMELINE + ATTRIBUTION)
- [ ] The project is its **own git repo**, not nested under a parent.
      *Verify:* `git -C <proj> rev-parse --show-toplevel` resolves to the project dir itself.
      *Pilot failure:* it resolved to the home dir; `git ls-files` = 0 → the work was invisible to git.
- [ ] **Commit 0 exists before the subject starts working** — a clean baseline (scaffold/README),
      not the finished artifacts dumped in one commit.
- [ ] The subject's work lands in commits **as it goes**, so decision *ordering* is recoverable.
      *Pilot failure:* we could not tell if the failure-recovery was planned or reactive — no timeline.
- [ ] Operator edits are, where possible, in **separate commits** (or a commit trailer) so
      subject-authored vs operator-steered is distinguishable.
      *Prevents:* "ordering unprovable + can't separate model from operator" — the pilot's biggest killer.

## §2 — Base-rate control arm  (THE placebo — the one that makes anything provable)
- [ ] The **decision forks** you care about are named up front (where a working-style choice happens:
      how it recovers from a failure, how it routes/sequences work, what it chooses to verify, where it
      improvises past the obvious path).
- [ ] For each fork, a **plain-agent control is runnable**: same task, same inputs, **no harness, no
      distilled skill, zero priming** (this is literally Arm A from the A/B).
- [ ] The forks + comparison are **pre-registered** (decided before you see the subject's output) —
      no picking the flattering forks after the fact.
- [ ] The metric is defined: **distillable delta = subject's choice - plain-agent's choice**. If they
      coincide → it's a *shared default*, drop it.
      *Prevents:* mistaking generic competence for the subject's "style" — the ceiling problem, and the
      single reason the pilot found nothing distinctive.

## §3 — Recurrence across >=2 projects  (turns a hypothesis into a trait)
- [ ] For anything you intend to **promote to a trait**, this is project **#2 or later** (a first
      project yields hypotheses only).
- [ ] An **append-only cross-project log** ([`distillation-log.md`](distillation-log.md)) tracks
      candidate traits so recurrence is visible over time.
      *Prevents:* promoting an n=1 anecdote (the pilot's strongest candidate was capped at HYPOTHESIS for exactly this).

## §4 — Non-invasive task sourcing  (no priming / no observer effect)
- [ ] The task is the project's **own real next step** (from the actual backlog), not a task invented
      to expose behaviour.
- [ ] **Zero meta-vocabulary** reaches the subject — banned in everything it reads incl. the system
      prompt: *verify, check, confirm, make sure, rigorous, honest, careful, working style, thinking,
      we're studying, be thorough, ready to ship/commit, is it done, explain your approach, why did you.*
- [ ] The subject is **not told** a distillation is happening, and gets **no clean isolated "probe"**
      after a long session (a suspiciously clean task IS a tell). Harvest-first: prefer continuations
      the operator would send anyway.
- [ ] The only requested deliverable is **ordinary work output**; reasoning is recovered from the
      transcript/traces afterward, **never solicited.**
      *Prevents:* performance-instead-of-trace (the proxy/observer effect that wrecked the first A/B).

---

## §5 — The go/no-go gate
- [ ] §1 and §2 both fully checked → **GO** (a real cycle can yield load-bearing traits).
- [ ] §1 or §2 missing → **NO-GO for trait distillation.** You may still run the cycle, but label it
      "negative-findings-only" up front (like the pilot) — do not present its ceiling behaviours as findings.
- [ ] §3, §4 partially met → proceed, but cap outputs at HYPOTHESIS (§3) / mark attribution-uncertain (§4).

**One-line test:** *"If a plain agent, under version control, did the same thing at the same fork —
would I still call it the subject's?"* If you can't answer that, §1 or §2 isn't done.
