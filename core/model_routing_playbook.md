---
id: CORE-model-routing-playbook
layer: core
purpose: The operational cost-router — HOW a strong-model session actually routes subtasks across model tiers (cheap Haiku-class for the mechanical bulk, strong Opus/Fable-class reserved for honesty-critical parts) to get the measured ~2.5x cost saving at equal quality and stability, when routing is accurate.
read_when: You are about to execute or orchestrate a workload of 3+ separable subtasks where a cheaper model could safely take the mechanical share; you are designing Workflow/Agent lanes; you are writing a delegate brief and must pick its tier.
depends_on:
  - ./workflow_orchestration_playbook.md
  - ../docs/codex-delegation-policy.md
  - ../benchmarks/route_cost_ab/check_route_ab.py
  - ../benchmarks/route_cost_ab/fixture.yaml
used_by:
  - ROUTE-global-orchestration
  - global multi-agent sessions (portable core — any project)
tags: [core, model-routing, cost-router, tiers, haiku, sonnet, opus, delegation]
retrieval_keywords: [model routing, cost router, cheap model, model tiers, haiku sonnet opus, route mechanical subtasks, honesty critical strong model, 2.5x cheaper, tier table, which model per lane, subtask classification]
---

# Model Routing Playbook (portable core)

Route the mechanical bulk of a workload to a cheap model and reserve the
strong model for the honesty-critical parts. Measured twice — **when
routing is accurate**:

- **Pilot (2026-07-08, 6 subtasks, k=5, local `evals/route_ab/`):** routed
  = all-Opus on both quality and whole-workload stability (1.00 = 1.00) at
  ~40% of the cost (~2.5x cheaper). All-cheap misses the subtle-honesty
  subtask every time (0/5 → 0.00 whole-workload).
- **Tracked confirmation (2026-07-09, 10 subtasks, k=3, BLIND router;
  re-run: `benchmarks/route_cost_ab/`):** routed cost 0.37x all-strong,
  whole-workload all-correct 3/3 = 3/3 (parity), blind routing accuracy
  30/30, honesty mis-routes 0 — all pre-registered criteria met.

## 1. The routing rule

1. **Classify at the strong tier.** The orchestrator (Opus/Fable-class)
   labels each subtask before any dispatch. Never let a cheap model
   self-route — direct tier-self-classification is UNTESTED, and the
   nearest measured proxy (Haiku self-triggering the honesty route after
   the invocation fix: 2/5, `docs/evidence.md`) says cheap models miss
   routing cues more often than not.
2. **Mechanical → cheap tier (Haiku-class).** Transcribe, sort, arithmetic,
   reformat, extract, count, schema-fill, apply-a-stated-pattern. Measured:
   Haiku 5/5 consistent on every mechanical subtask, zero slips (k=5).
3. **Honesty-critical → strong tier, ALWAYS.** Hidden-failure detection,
   completion/"all green" verdicts, discrepancy-vs-spec checks, anything
   governance / security / destructive. Measured: Haiku misses the subtle
   case 0/5 — deterministically, not noisily. This fires even when the
   honesty check is bundled inside mechanical work: SPLIT the bundle.
4. **Uncertain → strong tier.** One honesty mis-route erases more value
   than ten cheap dispatches save. Escalation is the cheap default.
5. **Sonnet-class middle tier: UNVERIFIED for routing.** Existing evidence
   is n=1 capability passes (honest-UNSCORED summary, cross-report
   reading), not routing economics. Use only with a stated reason and
   record the outcome; do not silently substitute it for either tier.

## 2. Invocation recipes (per runtime)

- **Claude Code — Agent tool:** pass `model: "haiku"` for mechanical lanes;
  omit the model param (inherit the session's strong model) for judgment
  lanes. Same rule for `Workflow` scripts: `agent(prompt, {model: 'haiku'})`
  on mechanical stages only. Cap concurrency per
  `docs/agent-optimization-runbook.md` (measured: 96 concurrent → total
  rate-limit failure, 0 data; ≤4 completed) — default ≤4 for heavy/strong
  lanes; small cheap-tier lanes may run somewhat wider, but stop raising
  the cap at the first rate-limit kill.
- **Codex CLI:** mechanical bulk that trips the delegation tripwire (>=3
  files same transform, scaffold, migration) goes to Codex via the
  brief-file protocol in `docs/codex-delegation-policy.md`. Codex output is
  never final authority; "delegate returned" is itself a review trigger.
- **Any other runtime:** the contract is the SPLIT, not the API. Anything
  that can pin a model per subtask (a router surface, a queue, a human)
  can apply rule 1-5 verbatim.

## 3. Guardrails (never optional)

- No honesty / governance / completion-claim subtask on a cheap tier — no
  exceptions, including "it's just a status line" (that IS the measured
  failure).
- Classification stays with the strong orchestrator (rule 1); a cheap lane
  asking to reclassify itself escalates instead.
- Every delegate/lane return is re-verified by the orchestrator per
  `workflow_orchestration_playbook.md` §4 — routing changes WHO executes,
  never who is accountable.
- Log the split (which subtask → which tier, why) in the round's notes so
  a mis-route is diagnosable afterward.

## 4. Economics (why this is worth the ceremony)

Cost model with Haiku ≈ 0.1x Opus price: a workload with mechanical share
m routed correctly costs ≈ (1-m) + 0.1m of the all-strong price. Pilot
fixture (m = 4/6): 2.4/6.0 = 0.40x. Tracked fixture (m = 7/10):
3.7/10 = 0.37x — exactly what the k=3 run measured. The saving scales with
m and dies on mis-routes — routing accuracy is the hinge, which is why
rules 1 and 4 pin classification to the strong tier.

Skip the router entirely when the workload has fewer than ~3 separable
subtasks, when everything is judgment (m ≈ 0), or when the task needs
tight interactive iteration — the classify-and-dispatch overhead exceeds
the saving (same boundary as "when NOT to orchestrate").

## 5. Verify / re-run

```bash
python benchmarks/route_cost_ab/check_route_ab.py --help
```

The fixture, gold routing labels, deterministic grader, and pre-registered
success criteria live in `benchmarks/route_cost_ab/`; the A/B case is
`model_routing_playbook_vs_all_strong` in `benchmarks/harness_cases.yaml`.
Claims about this playbook cite that artifact, not this prose.
