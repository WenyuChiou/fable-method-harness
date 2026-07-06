---
id: PROMPT-ai-review-modes
layer: prompt
purpose: The semantic (LLM-side) checklists for each AI-review mode - the judgment half of the contract whose deterministic half is scripts/run_ai_review.py; findings return as JSON validated against schemas/recommendation.schema.yaml via --ingest.
read_when: An LLM session (the /ai-review slash command, the adaptive-harness skill, or any reviewer) is executing a review mode and needs the mode's judgment checklist and output contract.
depends_on:
  - ../scripts/run_ai_review.py
  - ../schemas/recommendation.schema.yaml
  - ../schemas/review_report.schema.yaml
  - ../docs/codex-delegation-policy.md
used_by:
  - SCRIPT-run-ai-review
  - global /ai-review slash command (~/.claude/commands/ai-review.md)
tags: [prompt, ai-review, modes, checklist, semantic-judgment, ingest]
retrieval_keywords: [ai review modes, harness cleanup checklist, invocation efficiency questions, codex delegation review, diff review, experiment review, scheduled review, ingest findings json, keep simplify remove replace experiment]
---

# AI-review modes — semantic checklists

**Contract.** `scripts/run_ai_review.py` does the deterministic work (inventory,
integrity scans, telemetry harvest, report/history writing). This file holds the
judgment questions per mode. An LLM session answers them **with cited evidence**
(file:line, telemetry numbers, incident ids), writes findings as JSON records per
`schemas/recommendation.schema.yaml` (the runner enforces required fields,
enums, the REC id pattern, and the human-approval flag on high-risk
Remove/Replace records — not full JSON-Schema validation), and hands them
back via:

```bash
python scripts/run_ai_review.py --mode <mode> --ingest findings.json
```

Rules that never bend: evidence or `UNVERIFIED:` (never guess); findings are
recommendations, not commands; anything touching prompts/subagents/hooks
deletion, permissions, `settings.json`, or CI sets `requires_human_approval: true`
and travels as a patch proposal only. An unanswered checklist stays UNSCORED in
`unresolved_questions` — that is a correct output.

**Model tiers.** Deterministic runner: any tier (it is code — Haiku, Codex, or
cron can invoke it). Semantic checklists below: `standard_review` /
`diff_review` are Sonnet-capable; `harness_cleanup_review`,
`codex_delegation_review`, `code_invocation_review`, and `experiment_review`
interpretation should run on Opus/Fable-class models (judgment about deleting
guardrails is exactly where a weak model's false confidence is expensive).
Codex must not run any semantic mode as final authority — it may draft, never
decide (see docs/codex-delegation-policy.md).

---

## standard_review

General quality pass. Read the runner's deterministic report first (latest.json),
then judge:

1. Do any deterministic issues (`issues_found`) point at a deeper pattern
   (repeated INDEX drift → missing automation; recurring .bak files → missing
   hygiene habit)?
2. Are governance line counts trending up? Against which budget (CLAUDE.md
   high-signal budget is 120 lines)? What single extraction would help most?
3. Any new component (hook/skill/command/subagent) added since the last review
   with no stated purpose or no test?
4. Sample 2-3 recent sessions/commits: did the harness rules actually change
   behavior, or were they routed around?

## harness_cleanup_review

The bidirectional ratchet — "what can I stop doing?". For EVERY candidate
component (prompt rule, forced planning/todo step, context reset, handoff,
subagent, tool format, hook):

1. Is this constraint still raising success rate, or is it inertia?
2. Is this forced planning/todo step still preventing drift, or just slowing
   the model down?
3. Is this context reset / handoff still avoiding errors, or is it now
   interrupting long-range reasoning the current model handles?
4. Does this subagent genuinely raise quality, or only add merge/review cost?
5. Is this tool format still what current models are most reliable with?
6. Does this Codex delegation actually save main-agent cost, or does the
   brief+review overhead exceed the saving? (see docs/codex-delegation-policy.md)
7. Is any rule here only a patch for an old model, an old limit, or an old
   incident whose recurrence is now impossible?
8. Are any two rules duplicated, conflicting, or so conservative the model
   can't complete tasks naturally?
9. For each: Keep / Simplify / Remove / Replace / Experiment — with evidence on
   BOTH sides (`evidence_it_still_helps` / `evidence_it_may_be_obsolete`).

Incident-born gates (named incident, telemetry showing real catches) are
Keep-by-default: removing one requires an Experiment recommendation with a
falsifiable test, never a direct Remove.

## code_invocation_review

Efficiency of every invocation surface (script / shell / tool / subagent /
Codex / hook / LLM-only step). Use the runner's `home_telemetry` (hook_stats)
numbers. Per invocation, fill the `inefficient_invocations` record shape:

1. Does anything scan the whole repo where changed-files-only would do?
2. Repeated file reads or repeated tool calls a cache would eliminate?
3. Checks that are LLM-driven today but deterministically scriptable?
   (JSON→template report writing is the canonical example — never have an LLM
   rewrite a report from scratch.)
4. The reverse: deterministic checks that actually need semantic judgment?
5. Hooks: per-fire cost × fire frequency (Windows fork cost is real —
   Python ≈ 65-70 ms, Node ≈ 240 ms+). High-frequency '*' matchers carrying
   heavyweight processes are P1 findings.
6. Subagents that only add merge cost; missing subagents where isolation
   would pay.
7. Anything assigned to Codex that needs judgment; anything mechanical the
   main agent grinds through that Codex should take (see the tripwire in
   docs/codex-delegation-policy.md).

## codex_delegation_review

Audit delegation policy vs practice against docs/codex-delegation-policy.md:

1. Are the suitable/unsuitable boundaries being respected in recent sessions?
   (Check F14 hook block telemetry in `home_telemetry`.)
2. Is exactly ONE canonical tripwire threshold stated everywhere? Any drift
   between CLAUDE.md, DELEGATION.md, and the codex-delegate skill?
3. Do briefs follow the template (scope fence, runnable acceptance)? Sample one.
4. Is every delegate return followed by a Claude review before commit
   (trigger #4)? Any mechanical enforcement gap worth an Experiment?
5. Any deprecated-lane (Gemini) residue still routing or confusing? Count it.
6. Does anything let a delegate act as final authority or commit? That is a
   P0 finding.

## scheduled_review

Headless. **No semantic checklist runs here by design** — the runner produces
deterministic scans only, tagged `source: scheduled_runner`, and every semantic
section stays UNSCORED. Doctrine: the review's consumer is a present human;
a passive cron must summon one, not impersonate one. The scheduled report is
input for the next human-triggered session. Never: ledger writes, proposal
generation, application of anything, main-branch mutation.

## diff_review

Scope: only files changed since `--since-ref`. Judge:

1. Did this change add harness surface (new rule/hook/skill)? Is it registered
   (INDEX), tested, and purposeful?
2. Did it duplicate or contradict an existing rule?
3. Should anything it touched have been simplified instead of extended?
4. If it edited a gate/check: did the fix land separately from the change that
   benefits from it (DR-003)?

## experiment_review

For every recommendation where value is uncertain (`recommendation: Experiment`)
and every benchmark case not yet `completed`:

1. Is the A/B design falsifiable (pre-stated success criteria, metrics named
   before running)?
2. Is the case still worth running, or has reality resolved it (component
   deleted, model upgraded)? Mark rejected with reason if so.
3. Interpret completed cases: adopt / reject / iterate — the LLM interprets,
   the numbers come from the runner (DR-004).
4. Keep `benchmarks/ai_review_cases.yaml` statuses current and every case
   linked to its `linked_recommendation_id`.

---

## Output contract (all modes)

One JSON file:

```json
{
  "recommendations": [ { ...recommendation.schema records... } ],
  "obsolete_scaffolding": [ ... ],
  "inefficient_invocations": [ ... ],
  "codex_delegation_findings": [ ... ],
  "experiments_proposed": [ {"case_name": "...", "status": "proposed", "linked_recommendation_id": "REC-..."} ],
  "unresolved_questions": [ "UNVERIFIED: ..." ],
  "changes_made": []
}
```

Then `--ingest` it. Validation failures mean YOUR record is malformed — fix the
record, do not bypass the runner.
