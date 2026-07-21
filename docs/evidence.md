---
id: DOC-evidence
layer: doc
purpose: The honest evidence ledger - what this system is MEASURED to do, what it is measured NOT to do, and what remains untested; every claim cites a re-runnable artifact.
read_when: Deciding whether to adopt this system, telling someone else about it, or checking whether a claim about it is supported.
depends_on:
  - ./integration_test_matrix.md
  - ./model_compatibility_test_plan.md
  - ../benchmarks/model_compatibility_cases.yaml
  - ../distillation/distillation-log.md
used_when_citing: every claim below names its artifact; if you cannot re-derive a claim from its artifact, treat the claim as broken and file a finding.
used_by: [README, ROUTE-repo-maintenance]
tags: [doc, evidence, evaluation, honest-failure, negative-results]
retrieval_keywords: [is this useful, evidence ledger, measured results, negative results, what was tested, ceiling experiments, token savings measured, adoption decision]
---

# Evidence ledger — what this system does and does not do

This project's core discipline is *computed, not claimed*. This file applies
that discipline to the project itself. Three sections: measured-positive,
measured-negative, and untested. The negative section is not an apology —
publishing it is the feature.

## Measured: what it does

| Claim | Result | Artifact (re-run it) |
|---|---|---|
| Same gate behavior at ~55% less standing instruction context | An operator's 215-line global CLAUDE.md was slimmed (a 98-line candidate passed the swap eval; 96 lines landed after stripping two review-annotation comments). Grading over the 24 samples: review-gate adherence 3/3 vs 3/3, governance-routing 3/3 vs 3/3, codex-routing better in the slim arm (2/3 tripwire-decisive vs 0/3); a byte-identical control prompt calibrated adherence noise to ~zero | eval run `20260706-223951` produced the 24 raw samples (its own verdict field stays `pending-human` BY TOOL DESIGN); the per-sample grades and the landing decision are recorded in the operator's dotfiles commit `ddf2872`, which is the citable verdict artifact |
| ~90–98% less context loaded per task vs bulk-reading | Whole-repo content ≈ 303k tokens (recomputed 2026-07-07 after the tree grew); a route's start+required set spans 6.4k–31.6k (typical ~12–16k ≈ 4–5%) | compute from `ROUTES.yaml` + `git ls-files` sizes (bytes/4); figures re-derived by an independent fact-check pass before this file landed |
| Cheap models can operate the deterministic layer | Real Haiku agents 4/4: exact-command route selection reading ONE file; schema filling that passed the runner's own validator; script execution; escalation of a planted judgment question. Real Sonnet agents 2/2: honest UNSCORED summary; cross-report reading that flagged a real data-layout mismatch instead of guessing | `benchmarks/model_compatibility_cases.yaml` mc01–mc05, mc10 (executed 2026-07-06); re-run recipe in `docs/model_compatibility_test_plan.md` |
| Report generation costs ~0 LLM output tokens | Review reports (~10k tokens each) are rendered deterministically from JSON; the LLM only supplies schema-validated findings | `scripts/run_ai_review.py` (render_markdown); any `--dry-run` run |
| Findings never silently disappear | 37 tracked findings → 17 auto-resolved with the exact resolving commit sha attached, 20 carried into ledger tracking, 0 lost (historical: the one live run of the stateful rolling linkage, 2026-07-06). The machinery behind that run was retired 2026-07-14 after its pre-registered A/B came back B-loses (see the what-it-does-NOT-do table); the never-lost property now rests on the append-only history plus on-demand queries — same closure convention, no state to lose | append-only `reports/*/history/`; `python scripts/grep_history.py --open` / `--rec REC-...`; closure convention: commit says `applies REC-YYYYMMDD-NNN` (applies REC-20260714-001) |
| The system catches real defects in real work | During its own construction: 4 defect-finding adversarial review rounds (plus one approve-with-suggestions round) produced ~30 confirmed defects strictly counted (~35 including nit/hygiene items), including two silent state-loss bugs in the rolling loop and a parity survivor during a privacy remediation (the leak itself was self-identified and human-dispositioned; the reviewer caught the incomplete fix). Separately, the eval tool's session-guard refused an unsafe run and emitted a prepare bundle instead of a result | commit trailers on `f55459d`→`0dd0cf2` (finding counts enumerated per commit body); refusal artifact: the operator-side prepare bundle `eval_runs/20260706-223321` |
| Installation is verifiable, and the history is clean | 59/59 integration checks on any clone; full-history secret scan clean (gitleaks 8.30.1 at its run date — point-in-time, the tree has grown since; re-run at each release gate) | `python validation/integration_check.py`; scan record in `docs/publication_status.md` |
| **As a cost router, it matches all-Opus quality at ~2.5x lower cost (2026-07-08).** | An Opus "router" triaged 6 subtasks — 4 mechanical (transcribe / sort / arithmetic / reformat) → Haiku, 2 hidden-failure honesty tasks → Opus — at 100% routing accuracy. The routed run scored 6/6, EQUAL to all-Opus 6/6, at ~40% of all-Opus execution cost (Haiku ≈ 0.1× Opus price proxy) = ~2.5x cheaper. The saving scales with the mechanical share of the workload and HINGES on routing accuracy — a mis-route of an honesty task to Haiku would drop quality. Stability MEASURED (k=5/subtask): whole-workload "all 6 correct" was Fable-routed 1.00 = all-Opus 1.00 (EQUAL — not more stable than Opus), vs naive all-Haiku 0.00 (which every time misses the subtle-honesty subtask). Haiku is perfectly consistent on the 4 mechanical subtasks (5/5, no slips) and deterministically misses the subtle-honesty one (0/5) — so routing offloads the former safely and reserves Opus for the latter. Net: Opus-level quality AND stability at ~40% of Opus cost, when routing is accurate. CONFIRMED 2026-07-09 on the tracked, pre-registered 10-subtask benchmark at k=3 with a BLIND router (gold labels never shown): routed cost **0.37x** all-strong, whole-workload all-correct 3/3 = 3/3 (parity), blind routing accuracy 30/30, honesty mis-routes 0 — all three pre-registered success criteria met. The operational playbook this validates is `core/model_routing_playbook.md`. | Re-runnable: `benchmarks/route_cost_ab/` (fixture + gold labels + deterministic grader; case `model_routing_playbook_vs_all_strong` in `benchmarks/harness_cases.yaml`); raw runs local in `evals/route_cost_ab_20260709/` (gitignored) |
| **The Codex micro-contract cuts long-task cost — confirmed at 5 trials/cell (2026-07-10).** | Four-arm confirmatory run (80 executed): the inline micro-contract arm used **27% fewer input tokens, 59% fewer tool calls, 34% less wall-clock** than plain Codex — and beat the decisive pointer-control confound by 41%/62% (a neutral pointer is actually MORE expensive than baseline), while a flat context dump cost 2.2x the micro-contract for no correctness gain. Progressive disclosure beats flat dumping, measured. Efficiency means over all 20 executed trials/arm; 41% arm-uniform infrastructure attrition disclosed in the doc (operator-env contamination, not trial content). | `docs/codex_long_task_ab.md` §2026-07-10 (regenerate: `python scripts/run_long_codex_ab.py grade --run-dir evals/long_codex_ab/codex_confirmatory_20260710_t5 --markdown`) |
| **The earlier 2.84x activation tax + 0/10 routing was a BROKEN invocation, not the discipline — now fixed (2026-07-08).** | Activation force-read a fixed 4-file bulk (the over-load) while the completion route self-triggered 0/10. Fix = classify-first lean load + a portable-regime trigger. Re-test: Opus self-routed to the honesty gate 4/5 (was 0/10), Haiku 2/5; the demoted triad loaded 0/6 (bulk gone); trivial typo tasks over-triggered 0/6 (no new tax). Every earlier single-model A/B null was thus run against the broken (expensive, inert) invocation. | `fix-invocation-lean-load` branch commit `8ae8dbe`; re-test data in `evals/` (local) |
| **One-call route orientation (`route_pack.py`) beats free orientation on LIVE total cost — 0.72x, first frozen bar met in a 3-round series (2026-07-11).** | Three same-day pre-registered live A/Bs (k=3/arm, sonnet, identical or matched tasks, deterministic sanity gates 18/18, quality identical in all three rounds — the ceiling doctrine held live throughout). Rounds 1-2 (serial route_show + per-file reads): content-read reliably cut (0.65-0.73x, complete separation) but **each missed its own frozen 0.70 bar** — round 1 on TOTAL cost (0.84x), round 2 on CONTENT-READ (0.73x; its total, a report-only secondary, merely broke even at 1.00x); diagnosis: ~8 extra turns of standing-context replay ate the reading savings. Round 3 (new `scripts/route_pack.py`: route entry + all start+required contents in ONE call, plus batched greps): total cost **0.72x vs bar <=0.85 — MET**, content-read 0.67x, turns FLIPPED to fewer-than-free (11.3 vs 16.0), tight variance. Honest limits: one task family, sonnet-tier, k=3/arm; the 0.85 bar is looser than rounds 1-2's 0.70. | Operator-side (git-tracked): `audits/harness-optimization-2026-07/route-live-ab{,-heavy,-packed}-20260711/` (pre-registrations frozen before each run + RESULTS); tool: `scripts/route_pack.py` |
| **A third cheap-executor lane (Antigravity CLI) passed its pre-registered k=5 reliability gate (2026-07-11).** | 5/5 PASS on a frozen-criteria probe: fresh sandbox git repo per trial; scoped edit applied exactly; an identical-content decoy file byte-unchanged; a planted judgment question ESCALATED verbatim and never acted on; zero git operations — every trial, deterministic grader, no self-grading. Consequence (frozen before the run): the `antigravity-delegate` lane was promoted from explicit-ask-only to orchestrator-routed, with cheap-tier guardrails unchanged (never reviews, completion verdicts, governance, or anything ambiguous). Scope honesty: k=5 on ONE fixture shape — this measures reliability of the mc11 capability, not breadth; new task shapes still get an n=1 probe first. | `benchmarks/model_compatibility_cases.yaml` mc12 (mc11 = the n=1 capability probe, 2026-07-10); pre-registration + raw grader output operator-side in `audits/harness-optimization-2026-07/agy-k5-20260711/` |
| **Codex benchmark trials no longer inherit tested operator config contamination (2026-07-13).** | The runner now creates an auth-only home per trial. Deterministic gates: invalid inherited config excluded, auth continuity preserved, and 0/5 sequential homes leaked. One commit-bound live smoke was scored, passed, checked canonical evidence, and removed its home. This proves the isolation mechanism and targeted recovery, not elimination of the earlier 41% attrition or a token/speed lift. | `docs/codex_clean_home_isolation_2026_07_13.md` (implementation `e950be8`, gates `7f3d702`) |
| **The compact Hermes contract reduces standing context and passed a pre-registered fair semantic adoption gate (2026-07-13).** | Standing contract 1,402 -> 835 bytes (**40.44% lower**; bytes/4 remains an estimate). In the later 100-call fair A/B, B scored native parse, semantic target, and exact route 50/50, plus protected target/exact 15/15 with zero unresolved, ambiguous, or misroutes. All provenance gates passed. The paired B/A median was 0.99075 and bootstrap 95% upper 1.05007: latency no-regression passed (<1.1), but speedup did not (<1.0). `adopt_B=true` on this frozen task set. | `docs/hermes_fair_baseline_2026_07_13.md` (pre-registration `f2761d0`, runner `5a855e4`); earlier strict hard FAIL retained in `docs/hermes_compact_router_2026_07_13.md` |
| **Codex and Hermes conditional activation now has exact live telemetry and a real rollback check (2026-07-15).** | Fresh v3 probe: each runtime passed trigger recall **4/4**, routine over-trigger **0/2**, and actual-marker rollback **1/1**, with exact provider usage **7/7**. Separately, a deterministic no-API `hermes prompt-size` measurement found the final short shim reduced fixed project context from **5,994 B to 1,803 B (−69.9%)**. Hermes mean canonical usage was 38,225 tokens/call; Codex 51,528. The live run is deliberately single-arm: those are monitoring baselines, not a cost or speed comparison. | `docs/runtime_activation_telemetry_2026_07_15.md`; frozen live design `benchmarks/runtime_activation/preregistration_v3.json`; ignored local scorecards under `evals/runtime_activation/` |
| **The adaptive lifecycle has one eligible Codex result and one honest Hermes non-result (2026-07-18).** | Under the frozen six-pair binding, Codex treatment prevented **1** initial defect and **1** corrective invocation, with 17,898 corrective tokens avoided; exact total-token ratio **0.858288** and latency ratio **0.672159**. Its rule becomes active only for Codex. Hermes recorded process errors on all 12 pair-sides, so its correctness and token endpoints remain **UNSCORED** and its rule remains candidate. The historical envelope-trigger negative control preserves Hermes v2's 7 incorrect receipts beside the v3 7/7 correction; historical development rework is UNSCORED because no redacted session aggregate was available. This is a frozen-binding result, not a cross-runtime or general capability claim. | `benchmarks/adaptive_loop/evidence_v1.json`; frozen binding `benchmarks/adaptive_loop/final_binding_v1.json`; raw observations and scorecards remain local under ignored `evals/adaptive_loop/` |
| **The adaptive loop now preserves evidence-backed outcomes instead of inferring closure from loose prose (2026-07-13).** | Regression gates: 0/5 adversarial prose false closures; 2/2 valid closure forms; one validated outcome survived 3/3 later stale-input runs; reopen evidence restored it to the active queue; carried-open behavior remained pinned. A 15-sample interleaved overhead check reported 1.028x baseline, inside the pre-registered <=1.2x budget. | `docs/adaptive_outcome_ledger_2026_07_13.md` (implementation `d8fe0e8`) |
| **The codebase-memory freshness sentinel rejects a ready-but-stale graph with low deterministic overhead (2026-07-13).** | The 15/15 regression suite covers three stale forms, one exact fresh fixture, unavailable/malformed CLI paths, provenance, and safe output. A commit-bound live run classified the graph STALE in 5/5 repetitions while `index_status=ready`; median three-probe time was 0.0595s and every evidence gate passed. This is a completion-integrity improvement, not a token-saving claim. | `docs/codebase_memory_freshness_2026_07_13.md` (pre-registration `a077c79`, implementation `8e0f44d`) |

## Measured: what it does NOT do

| Non-claim | Evidence |
|---|---|
| **It does not make a frontier model smarter.** Eight consecutive experiments tried to construct tasks where the harness (or a distilled skill) would raise plain-Opus quality — every one hit a ceiling (plain model at 88–100%, up to N=120 buried requirements retained with zero drops, harness OFF) | `distillation/distillation-log.md` (8 ceiling entries incl. the artifact-proof N=120 run); `distillation/orchestration_bench/PRE_REGISTRATION.md` states the resulting prior openly |
| The traits it was distilled from are not model-exclusive | The distillation research found candidate "source-model-distinctive" traits present at 100% in plain models of two different families, harness off — labeled UNIVERSAL FRONTIER-MODEL COMPETENCE, not secret sauce | `distillation/distillation-log.md` (base-rate arm entries) |
| **Forced GPT-5.5 harness activation has not shown a reliability lift in the 2026-07-07 proxy pilot.** | Same-environment GPT-5.5 pilot: A 4/5 pass, B 4/5 pass; false-done A 1/5, B 1/5; canonical checks 5/5 both. B used 52 vs 33 tool calls (1.58x) and 1,140,776 vs 401,583 input tokens (2.84x). High-risk T2-T5: A 3/4, B 3/4; T5 failed in both arms on governance-sensitive permissions. | `docs/harness_ab_pilot_2026_07_07.md` |
| **The T5 governance gap has a targeted post-fix Codex regression pass, not a broad A/B win.** | After adding the governance / permission safety trigger to `core/GLOBAL_BOOTSTRAP.md`, one isolated `codex exec` T5 run added safe helper docstrings, left `settings.json` unchanged, did not apply `Bash(rm -rf:*)` or `Bash(git clean -fdx:*)`, and requested explicit approval or a narrower allowlist. This is n=1 regression evidence only. | `docs/t5_codex_governance_regression.md` |
| **Hermes API-token reduction and paired speedup are still not established.** | Exact per-call Hermes usage is now available for the conditional-activation probe (7/7 rows), but it has one arm and therefore cannot show a reduction. The earlier strict paired run remains `passed=false`; its fair successor supports adoption and latency no-regression, but not speedup: the 50-pair median was 0.99075 and the bootstrap 95% upper 1.05007, above 1.0. Standing context bytes are not API tokens. | `docs/runtime_activation_telemetry_2026_07_15.md`; `docs/hermes_fair_baseline_2026_07_13.md`; prior failure in `docs/hermes_compact_router_2026_07_13.md` |
| **The local codebase-memory graph was not repaired by the attempted rebuild.** | `delete_project` returned permission denied; the subsequent full index still reported the same 1,650 nodes / 2,207 edges and the commit-bound sentinel found all three probes stale. `ready` remains advisory and direct-file fallback remains mandatory until a later valid FRESH scorecard exists. | `docs/codebase_memory_freshness_2026_07_13.md` |
| **The Codex micro-contract's CORRECTNESS lift is still not established** (its efficiency lift IS — see the positive table). | Confirmatory run 2026-07-10 (4 arms x 4 scenarios x 5 trials): the micro-contract arm was the only one at zero false-done and 100% scored pass, but Fisher one-sided vs baseline gives p = 0.28 at the scored n (13 vs 11 after arm-uniform infrastructure attrition, disclosed in the doc) — direction positive, not separable. Do not cite a correctness lift. | `docs/codex_long_task_ab.md` §2026-07-10; raw run local in `evals/long_codex_ab/codex_confirmatory_20260710_t5/` |
| **The rolling loop's REC-linkage machinery does not out-track manual re-derivation — the load-bearing Phase-2 A/B came back B-LOSES (2026-07-14).** | Frozen replay pre-registration executed same-day: k=3 sonnet agents re-derived new/repeated/resolved from linkage-stripped sequences of the 5 real rolling reports and scored repeated-finding recall **1.00/1.00/1.00** on 85 instances (1.00 even on strict first-seen matching; 0 false-repeated, 0 false-resolved) vs the frozen <0.90 bar — the linkage's mechanical recall advantage does not exist at the history's actual shape (recs carried verbatim). What DOES survive is the emitter economics: manual re-derivation cost **11.3x** the per-run brief read (marginal content basis; 66x full-transcript) — the value sits in the deterministic report+brief emitter, not the ledger linkage. Resolved-detection was untestable (zero resolved events in the window; the outcome ledger has fired live 0 times). Disclosed threats: verbatim-carry makes replay matching easier than a fresh-LLM-text counterfactual; 5 runs/8 days; k=3 sonnet, one fixture family. Consequence per frozen criteria: simplification REC opened, human decides. | `benchmarks/harness_cases.yaml` case `ai_review_only_vs_ai_review_plus_adaptive_harness` (EXECUTED notes); REC: `docs/rolling_loop_simplification_rec_2026_07_14.md`; fixture, deterministic grader + grades operator-side in `audits/harness-optimization-2026-07/rolling-loop-ab-round4/` |

Consequence, stated plainly: **use this for discipline, economy, and audit
trail — not for capability.** Its own routing guidance says to skip the
ceremony on simple tasks; the measured value concentrates where mistakes
are expensive, work is long, or several agents run at once. The clearest
positive lever measured so far is **cost-routing**: put a cheap model on the
mechanical majority of subtasks and reserve the expensive one for the few
honesty-critical parts — comparable quality at ~2.5x lower cost *when the
routing is accurate*. Once the invocation was fixed, a properly-routed
discipline still showed no quality lift on a strong model (ceiling) and only
a weak, routing-limited lift on a weak one (Haiku bare 0/6 → routed 1/6 on a
hidden-failure task) — so the value remains cost and trust, not raw quality.

## Untested (pre-registered, criteria frozen, not yet run)

- The remaining pre-registered A/B benchmark cases (`benchmarks/*.yaml`;
  count changes as cases execute — `model_routing_playbook_vs_all_strong`
  completed 2026-07-09). ~~The load-bearing one: does the rolling loop
  justify its complexity vs standalone review
  (`ai_review_only_vs_ai_review_plus_adaptive_harness`)?~~ — EXECUTED
  2026-07-14, **B-loses** (see the what-it-does-NOT-do table above;
  simplification REC opened). All remaining cases carry pre-stated success
  criteria and known ceiling-risk warnings.
- ~~Codex live scoped-edit compliance (mc08/mc09)~~ — EXECUTED 2026-07-07,
  both PASS n=1 (fence honored incl. an out-of-fence decoy; HEAD/staging
  untouched); see `benchmarks/model_compatibility_cases.yaml`. Still
  untested: the multi-delegate splitter pipeline efficiency A/B
  (`docs/model_compatibility_test_plan.md` §4).
- Longitudinal value: no multi-week usage data yet (drift caught per month,
  rework avoided). The scheduled report-only scan exists to start
  accumulating exactly this.

## Known limits of the evidence itself

- The "catches real defects" row is **self-referential**: the defects were
  caught while building this system. No third-party project data yet.
- Model-tier passes are **n=1 per test** — capability existence, not
  reliability statistics.
- The strongest-model rows were executed and graded by the same model
  family (disclosed in `benchmarks/model_compatibility_cases.yaml` mc06/mc07);
  an independent human spot-regrade is the honest closure.
- Token figures use bytes/4 ≈ tokens; treat as estimates with ~±20%.

## If you want to verify any of this yourself

```bash
git clone https://github.com/WenyuChiou/fable-method-harness
cd fable-method-harness
python validation/integration_check.py     # 59 checks, ~3 min
python validation/retrieval_probe.py       # retrieval surface probes
python scripts/build_harness_graph.py --dry-run   # 0 broken dependencies
```

A claim in this file that you cannot re-derive from its named artifact is a
bug: open a finding against `DOC-evidence`.
