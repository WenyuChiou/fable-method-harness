---
id: DOC-distillation-log
layer: doc
purpose: Append-only log of working-style distillation cycles; one entry per candidate trait or negative finding, each carrying its motivating project, trace, gate label (load-bearing / baseline / quarantined / cosmetic / negative), and cross-project recurrence — the accumulation surface that turns hypotheses into traits over >=2 projects.
read_when: During a distillation cycle when recording candidates/verdicts; deciding whether a candidate has recurred across enough projects to promote.
depends_on:
  - ./setup-checklist.md
  - ./analyst-prompt.md
used_by:
  - ROUTE-distillation
tags: [distillation, living-doc, append-only, recurrence, load-bearing, working-style]
retrieval_keywords: [distillation log, candidate trait ledger, recurrence across projects, load-bearing vs cosmetic, quarantined, negative finding]
---

# Distillation Log

Append-only. Newest last. One entry per candidate trait or negative finding. **Never edit a
past entry** — supersede it with a new entry that references its id (DR-007
corrections-append-never-overwrite). This is the recurrence ledger: a candidate is promoted to a
*trait* only when it recurs across **>=2 projects** with a non-zero base-rate delta each time
(see [`setup-checklist.md`](setup-checklist.md) §2/§3). Load-bearing survivors also land on the
harness surfaces (`memory/lessons_learned.jsonl`, `datasets/edge_cases.yaml`); this log is the
cross-project index that makes recurrence visible.

## Entry template
- **id:** DL-YYYYMMDD-NN
- **project:** <the real project + whether it was git-tracked / had a base-rate arm>
- **candidate:** <one sentence — the observed working-style behaviour>
- **trace:** <exact file/row/line + the downstream decision it changed (two-level)>
- **base-rate delta:** <plain-agent's choice at the same fork vs the subject's — or "NO BASE-RATE RUN">
- **label:** load-bearing | baseline(ceiling) | quarantined | cosmetic | negative-finding
- **recurrence:** <k/N projects this has appeared in; supersedes/relates DL-ids>
- **landing:** <LL-0NN / EC-0NN / none — where it went on the harness surface, or why not>

## Entries
<!-- append below this line; do not rewrite existing entries -->

- **id:** DL-20260704-01
  - **project:** model-routing-benchmark (NOT git-tracked; NO base-rate arm — pilot, negative-findings-only per checklist §5)
  - **candidate:** honest-failure surfacing lives only in the raw-capture layer; the derived report manufactures a false all-green.
  - **trace:** `make_report.py:23` prefer-ok dedup → `canonical_results.jsonl` has 0 `ok:false`; `report_dedup.md` aggregate voice `4/4` with no timeout mention; the real timeout (240s ceiling, no elapsed — `benchmark.py:83-85`) survives only in `raw.jsonl` and is named in exactly one quoted model-output excerpt at `report.md:349`, never in a report's own aggregate voice; the 189.23s post-timeout retry is retained and averaged into the latency column.
  - **base-rate delta:** NO BASE-RATE RUN (n=1, no control arm — cannot separate subject from any agent).
  - **label:** negative-finding
  - **recurrence:** 1/1 project.
  - **landing:** appended LL-018 (`memory/lessons_learned.jsonl`) + EC-025 (`datasets/edge_cases.yaml`). Maps onto existing DR-004 / DR-009 / DR-011 + `docs/completion-honesty-gate.md` (a fresh instance, not a new rule).

- **id:** DL-20260704-02
  - **project:** person-harness-compiler (Fable session `3b07caec`, transcript-based → **clean attribution**; NO base-rate arm yet — Round-1)
  - **candidate:** Round-1 Track-1 distillation of the orchestrator's working-style from a 57-turn build+orchestration transcript.
  - **trace:** `scratchpad/distillation_design/track1_mhc/timeline.md`; workflow `wf_cbf650ca-fd5` (3 lenses → gate → adversarial audit).
  - **base-rate delta:** NO BASE-RATE RUN yet (planned: Opus session `cc8d85c0` as a weak same-task contrast + the H-A/H-B cross-project fork).
  - **label:** 1 LOAD-BEARING (L1 claim-targeted verification) + 7 HYPOTHESIS + 4 NEGATIVE; the adversarial audit demoted 3 load-bearing → 1.
  - **recurrence:** 1/1 project — every trait capped at HYPOTHESIS pending a ≥2nd-project fork.
  - **landing:** appended LL-019 (L1), LL-020 (N2), LL-021 (N4), EC-026 (N3). **N1 (code-review-verdict-not-gating) was INVESTIGATED against the full transcript and DROPPED** — the "same-turn commit / no verdict" basis did not hold; the `code-review` skill ran a real review each time (diff + reads + grep), so the verdict-gating characterization was a condensed-timeline artifact (DR-021 caught it before landing).
  - **base-rate note (superseding, `wf_02456e89-e0d`):** the planned "weak same-task contrast" (Opus session `cc8d85c0`) WAS run and, per its adversarial audit, **cannot subtract baseline** — the Opus arm was ALSO harnessed and on a DIFFERENT project (mhc, not PHC), so all candidate traits (L1/H-A/H-B/H-C) appear in it by harness rule (DR-016/DR-002/DR-009), giving ~zero discriminating information (a MATCH is expected by construction). It establishes only a floor ("none absent under harness on a different project"), not distinctiveness. **The missing instrument is a harness-OFF plain-agent run at the same forks** (setup-checklist §2: no harness, no skill, zero priming) — a harnessed second arm cannot separate harness-imposed from model-native. That experiment (`wf_...` harness-off, plain-Opus vs plain-Fable at the L1/H-B/H-C forks) is the decisive next step; run next.

- **id:** DL-20260704-03
  - **project:** harness-OFF base-rate experiment (decisive control for DL-20260704-02's PHC candidate traits)
  - **candidate:** do the top candidate traits (L1 claim-targeted verification / H-B eval-integrity discipline / H-C tool-failure localization) require Fable-the-model, or the harness, or neither?
  - **trace:** workflow `wf_be28f924-027`; 3 neutral self-contained forks × {plain-Opus N=5, plain-Fable N=3}, **harness-OFF, zero priming**; blind grader per trial.
  - **base-rate delta:** **DECISIVE.** plain-Opus AND plain-Fable both exhibit ALL three traits at **100%** (Opus 15/15, Fable 9/9, 0 attrition) with **no harness**.
  - **label:** all three → **UNIVERSAL FRONTIER-MODEL COMPETENCE.** NOT Fable-distinctive (plain-Opus == plain-Fable, both 100%); NOT harness-induced (harness-off, still 100%). The "Fable secret sauce" hypothesis on these traits is **refuted**; the harness does not *produce* them either.
  - **recurrence:** control arm (not a project trait).
  - **landing:** no promotion — L1/H-B/H-C move HYPOTHESIS → BASELINE(universal). LL-019 stands only as a generally-useful advisory reminder (universal, not distinctive). **Caveat:** 3 traits on neutral self-contained probes (possibly on the easy side); ceiling here is consistent with this repo's A/B ceiling finding ([[harness-ab-ceilings-on-opus]]). The durable distillation value remains the NEGATIVE findings (N2/N3/N4), not the positive traits.

- **id:** DL-20260705-01
  - **project:** orchestration_bench — Escalation Ladder (`distillation/orchestration_bench/ladder.py`), the method built to escape the A/B ceiling by scaling requirement-count N until plain-Opus drops the buried tail.
  - **candidate/question:** does plain Opus 4.8 drop buried requirements as N grows — the "doesn't sustain over length / drops the tail" failure whose ABSENCE is Fable's documented edge? If it drops at some N*, that N* is the scale where a Fable-vs-Opus contrast has signal.
  - **v1 ARTIFACT (caught, NOT landed):** the first generator was COMPRESSIBLE (`type = TYPES[i%4]`, special-rule keyed on `i%3`). Plain Opus **reverse-engineered the formula** — the N=120 build wrote a 5-line `_build_schema()` loop from "index mod 4 / mod 12" and generated every field, retaining nothing. All of N=24/60/120 scored 1.0, but this measured PATTERN-RECOGNITION, not tail-retention. Caught by READING the build code (DR-021), not by the (green) score. v1 preserved as `ladder_runs_v1_compressible/`.
  - **hardened v2:** randomized each field's (type, rule) from a seeded PRNG with NO index formula + shuffled the prose order → non-compressible (field `f097`'s type knowable only by reading `f097`'s sentence). Grader re-validated to CATCH a real drop (remove one field from a gold build → buried_rate 0.967, names the miss).
  - **RESULT (DECISIVE):** plain Opus **15/15 = buried_rate 1.0** at N=24/60/120 on the non-compressible task (5 trials each, throttled 4-concurrent after a 15-wide burst tripped a server rate-limit). Verified GENUINE literal retention: the N=120 registry has 120 literal entries, NO for/range/modulo generator, random spot-checks (`f058`→int+positive, `f070`→float+positive, `f114`→bool) match spec exactly, dict emitted in shuffled spec order (hand-transcribed field-by-field).
  - **label:** **8th consecutive ceiling — now ARTIFACT-PROOF.** On registry-transcription (retain N independent buried specs → literal dict + type-coercion + per-field special rule), plain Opus does not drop the tail up to N=120 (907-word dense shuffled spec). The Escalation-Ladder method did NOT break the ceiling.
  - **SCOPE (honest boundary):** this tests INPUT-LENGTH retention + mechanical fidelity in a SINGLE-agent build. It does NOT exercise Fable's specific documented edge — dispatching/sustaining PARALLEL SUBAGENTS over a long agentic HORIZON. The ladder grows input N, not trajectory length / tool-step count. It closes the "drops buried reqs from a long spec" sub-hypothesis decisively, but the orchestration-horizon axis remains untested by any fast fixture — exactly the regime deferred to the Fable-vs-Opus comparison (Fable quota returns ~2026-07-07) + the real-project backstop.
  - **landing:** memory [[harness-ab-ceilings-on-opus]] updated (8th ceiling + compressibility caveat); methodological lesson LL-022 (a synthetic "buried-requirements" bench MUST be non-compressible or it measures pattern-recognition — verify by reading the build code, not the score). No harness promotion (a ceiling is the decisive null per PRE_REGISTRATION program-stop logic).
