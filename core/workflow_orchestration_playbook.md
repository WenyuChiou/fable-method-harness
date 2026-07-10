---
id: CORE-workflow-orchestration-playbook
layer: core
purpose: Portable multi-agent (Workflow/ultracode) orchestration discipline distilled from the observed practice of method-harness-compiler — 11 shipping commits carry Executed-By trailers of 4-9 workflow subagents each, all gated by the same phase/lane/review/fixer pattern.
read_when: You are about to spawn 2+ subagents for one goal in ANY project; you are designing a Workflow-tool run; a delegate just returned and you must decide what the orchestrator still owes.
depends_on:
  - ../operating_model/review_protocol.md
  - ../operating_model/operating_model.md
  - ../memory/lessons_learned.jsonl
  - ../datasets/failure_modes.yaml
  - ./model_routing_playbook.md
used_by:
  - ROUTE-pr-review
  - ROUTE-repo-maintenance
  - global multi-agent sessions (portable core — any project)
tags: [core, orchestration, multi-agent, workflow, lanes, adversarial-review, fixer]
retrieval_keywords: workflow orchestration, ultracode, subagent lanes, parallel agents, pinned work order, flat return schema, adversarial review pair, gate honesty reviewer, fixer loop, orchestrator duties, concurrency guard, disjoint file sets, when not to orchestrate
---

# Workflow Orchestration Playbook (portable core)

This is the multi-agent discipline actually run in the source repo: every
shipping round from 046d0e3 (9 subagents) through 91b982b (6 subagents)
executed as parallel lanes, was re-verified by the orchestrator, and shipped
only through the layered review gate. Nothing here is aspiration — each rule
cites the commit or ledger entry that forced it.

## 1. Goal

Turn one large task into parallel subagent lanes WITHOUT losing the
single-owner guarantees (verified state, honest numbers, one coherent
commit). The orchestrator multiplies throughput; it never delegates
accountability.

### When NOT to orchestrate

- Conversational turns, Q&A, or advice — answer directly.
- Single-file trivial edits (typo, one-line fix) — a workflow costs more
  than it saves.
- Tasks needing tight user iteration or live-state debugging — a
  context-blind lane would be worse than direct work.
- Anything whose whole value is judgment on THIS session's context.

## 2. Allowed

- **Model tier per lane — route, don't inherit.** Every lane silently
  inheriting the orchestrator's strong model is the measured ~2.5x
  overspend. At lane-design time classify each lane per
  `core/model_routing_playbook.md`: mechanical lanes → cheap tier
  (`model: 'haiku'` on Agent/Workflow calls; concurrency caps per
  `docs/agent-optimization-runbook.md`);
  honesty-critical / review / governance lanes → strong tier, always;
  classification stays with the orchestrator. Measured basis + guardrails
  live in that playbook — this section is the trigger, not the detail.
- **Phase design**: parallel build lanes → an integrate step → an
  adversarial review PAIR → a conditional fixer. Observed at every scale:
  4 lanes (1c4a77f, 490470d), 5-7 (510b79f, bd32614, 9532648, e7f0fc6),
  8-9 (f8740f8, d7603e3, 046d0e3, 7134227).
- **Lane partitioning by disjoint file sets.** When two flights share one
  tree, add an explicit concurrency guard: 490470d excluded the in-flight
  M2a workflow's files by name from its commit ("concurrently in flight on
  disjoint files and is excluded from this commit").
- **Pinned work orders.** The architect pins ID systems, record shapes, and
  disciplines BEFORE execution (the operating model's "pin plan / pinned
  ids" step); misspelled-id drift is caught by pinned-id discipline, not by
  the machine (FM-028). Generic discipline (review rules, no-fabrication,
  encoding) may be referenced by harness route/file id instead of re-pasted
  into every work order.
- **Flat return schemas for open-ended research lanes**: `files_written`
  (list of paths) + `notes` (prose). The tool-discovery research lanes
  (510b79f) returned reports plus honest unverified/unreachable ledgers as
  files, not nested data. Never force deep nested schemas on web-research
  agents — findings they cannot fit get dropped or mangled.
- **Adversarial review pairs with orthogonal lenses**, plus a dedicated
  gate-honesty / authenticity reviewer whenever numbers or transcripts are
  produced: "gate-honesty" + "correctness" (91b982b), "fresh-eyes" +
  "consistency" (7134227), "v0.6 consistency" + "transcript authenticity"
  (f8740f8), "pre-registration honesty" (2917804). One lens's
  REQUEST_CHANGES outweighs the others' APPROVEs.
- **Fixer loop**: feed the fixer the blocking findings VERBATIM, with the
  right to verify-on-disk first and to skip-with-reason when a finding is
  wrong. Reviewer findings are hypotheses until confirmed on disk (the
  passive-voice evasion was "confirmed on disk" before fixing, 9532648).

## 3. Forbidden

- Delegating the orchestrator's own duties (section 4).
- Two lanes writing the same file, or two parallel pytest-to-green loops on
  one tree — tree-wide green has exactly ONE owner per round.
- Trusting a lane's report about shared state: cross-agent observations go
  stale or conflict; adjudicate on disk (LL-005).
- Shipping delegate output without review — "delegate returned" is itself a
  mandatory review trigger (review_protocol.md, FM-005).
- `git add -A` with concurrent workstreams in the tree (FM-024).
- Letting a lane commit or push; commits are the orchestrator's.

## 4. Orchestrator duties — never delegated

Observed in every round's commit body:

1. **Independent re-verification.** Re-run the tests/scripts/greps
   personally: byte-identical scorecard re-runs (f8740f8), hand re-derived
   package numbers (91b982b), repo-wide grep-old-value after renames,
   on-disk counts to settle agent conflicts (490470d).
2. **Synthesis across lanes.** Orthogonal reviewers "run independently and
   synthesized by the orchestrator"; apparent verdict conflict is usually
   partition, not contradiction.
3. **Commit gating.** The code-review verdict gates the commit; the trigger
   fired is recorded in the commit body (every commit f4c826f→91b982b).
4. **Explicit-path staging** with a count assertion ("6 files asserted",
   510b79f) and named exclusion of concurrent flights' files.
5. **Human-gate reads** of prose artifacts a machine check cannot cover
   (1c4a77f, e7f0fc6).

## 5. Required outputs

- A phase plan naming lanes, their disjoint file sets, and the concurrency
  guard if any other flight shares the tree.
- Pinned work orders (IDs, shapes, disciplines) written before lanes start.
- Per-lane returns in the flat schema (`files_written` + `notes`).
- Review-pair verdicts + the fixer's fixed/skipped-with-reason ledger.
- A commit body recording `Executed-By: N workflow subagents (wf_...)` and
  `Co-Reviewed-By:` with what each lens caught — the trailers ARE the audit
  trail this playbook is distilled from.

## 6. Acceptance criteria

- Every blocking finding is fixed or skipped WITH a written reason; fixes
  land before the commit, never after the push.
- The orchestrator personally re-ran the suite / validators after the fixer
  finished (lane-reported green does not count).
- Staged file count asserted; no concurrent flight's files rode along.
- Numbers in any report were re-derived or spot-checked by the
  orchestrator, not copied from a lane's summary.
- Mirror/translation artifacts got a human-gate read before commit.

## 7. Common failure modes (all real)

| Failure | Counter-rule | Evidence |
|---|---|---|
| Stale cross-lane observations (agents disagree whether zh-TW README still had mermaid) | Verify on disk before acting: 0/0/0 mermaid, 6/6/6 fences counted directly | LL-005; 490470d |
| Instruction leakage into translated artifacts (work-order text shipped inside zh-CN README) | Human gate on every non-English mirror; grep mirrors for instruction-register phrases | LL-017; FM-005; 1c4a77f |
| Parallel pytest-to-green loops on one tree fighting each other | Single owner of tree-wide green; lanes report, one integrator runs the suite | corollary of LL-005 + FM-024 (disjoint-file + explicit-staging discipline) |
| Reviewer finding is simply wrong | Fixer verifies on disk first; skip-with-reason is a right, not insubordination — but confirmed findings get pinned fixtures | 9532648 (evasion confirmed on disk before fix) |
| Unrelated in-flight files ride into the commit | Explicit-path staging + count assertion + named exclusions | FM-024; 510b79f; 490470d |
| Lane self-reports success nothing computed | No-silent-pass: ask what process wrote each number | FM-001; LL-008 |

## 8. Self-check before closing an orchestrated round

- [ ] Did I re-run (not re-read) the verification myself?
- [ ] Any two lanes touch the same file? If yes — why did the guard fail?
- [ ] Every REQUEST_CHANGES finding: fixed, or skipped with a written reason?
- [ ] Staged count asserted against the expected list?
- [ ] Numbers/transcripts produced this round: did a gate-honesty or
      authenticity lens review them?
- [ ] Commit body carries Executed-By + Co-Reviewed-By trailers?
- [ ] Would this task have been cheaper done directly? Record that too.
