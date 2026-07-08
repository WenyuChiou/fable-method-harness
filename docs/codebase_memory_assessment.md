---
id: DOC-codebase-memory-assessment
layer: doc
purpose: Evidence-based assessment of how the harness affects long and multi-step agent work, using codebase-memory discovery plus pilot scorecards
read_when: Deciding whether the harness improves agent work, updating README evidence, or planning the next A/B run
depends_on:
  - ./evidence.md
  - ./ab_skill_effect_protocol.md
  - ./harness_ab_pilot_2026_07_07.md
  - ./t5_codex_governance_regression.md
  - ../scripts/summarize_harness_ab_pilot.py
used_by: [README, ROUTE-eval-design, ROUTE-ab-test-design]
tags: [codebase-memory, evidence, ab-test, long-work, multi-step, codex]
retrieval_keywords: [codebase memory assessment, harness improvement, long multi-step work, pilot metrics, GPT-5.5 A/B, Codex future work]
---

# Codebase-Memory Assessment: Harness Impact And Future Codex Use

## Method

This assessment used the codebase-memory MCP index for the harness repo as the first discovery layer, then opened the canonical files it identified. The index was ready with 1,612 nodes and 2,183 edges. It surfaced the real implementation clusters instead of relying on folder names alone:

- YAML/Markdown harness surface plus Python utility scripts.
- Deterministic runners in `scripts/run_ai_review.py` and `scripts/run_adaptive_harness_review.py`.
- Verification surface in `validation/integration_check.py`, `validation/retrieval_probe.py`, and `scripts/build_harness_graph.py`.
- A/B and long-work evidence under `distillation/orchestration_bench/`, local ignored `evals/` runs, and tracked durable summaries in `docs/`.
- Agent compatibility evidence in `benchmarks/model_compatibility_cases.yaml`.

When the graph result was load-bearing, the actual file was opened and read. The index is an accelerator, not proof by itself.

## What The Graph Changed In The Work

The graph reduced discovery time by pointing directly to the scoring and runner surfaces:

| Question | Codebase-memory result | Follow-up file evidence |
|---|---|---|
| Where are the executable entry points? | `get_architecture` listed setup, review, graph, integration, retrieval, and orchestration grader entry points. | `scripts/setup_harness.py`, `validation/integration_check.py`, `distillation/orchestration_bench/grade.py` |
| Where are long/multi-step metrics likely to live? | Search for orchestration/eval terms surfaced `distillation/orchestration_bench` and benchmark parsers. | `distillation/distillation-log.md`, `docs/harness_ab_pilot_2026_07_07.md` |
| What should README expose? | Architecture showed this is a docs+runner harness, not a library API. | README should lead with install, agent entry points, evidence, verification, and public-safety posture. |
| What is the compatibility surface? | Agent-routing docs and model compatibility cases are first-class repo artifacts. | `SETUP.md`, `docs/agent-routing-policy.md`, `benchmarks/model_compatibility_cases.yaml` |

Net effect for this task: codebase-memory improved orientation and file targeting, but the actual README/evidence claims still come from disk artifacts and computed scorecards.

## Actual A/B Pilot Metrics

The tracked pilot summary is `docs/harness_ab_pilot_2026_07_07.md`. It summarizes local ignored scorecards from `evals/harness_ab/pilot_2026-07-07`. It is a same-environment proxy, not a formal capability A/B. Arm A may be contaminated by global verification discipline.

Run:

```bash
python scripts/summarize_harness_ab_pilot.py --markdown
```

Current computed result from the five A/B pairs:

| Metric | Arm A baseline | Arm B forced harness | Delta |
|---|---:|---:|---:|
| Trials | 5 | 5 | 0 |
| Primary pass | 4 | 4 | 0 |
| False done | 1 | 1 | 0 |
| Canonical checked | 5 | 5 | 0 |
| Tool calls | 33 | 52 | +19, 1.58x |
| Input tokens | 401,583 | 1,140,776 | +739,193, 2.84x |
| Output tokens | 5,901 | 10,329 | +4,428, 1.75x |
| Duration seconds | 542.57 | 365.77 | -176.80, 0.67x |

High-risk subset T2-T5:

| Metric | Arm A baseline | Arm B forced harness | Delta |
|---|---:|---:|---:|
| Trials | 4 | 4 | 0 |
| Primary pass | 3 | 3 | 0 |
| False done | 1 | 1 | 0 |
| Canonical checked | 4 | 4 | 0 |
| Tool calls | 28 | 44 | +16, 1.57x |
| Input tokens | 340,874 | 964,729 | +623,855, 2.83x |
| Output tokens | 5,298 | 8,968 | +3,670, 1.69x |
| Duration seconds | 514.02 | 309.38 | -204.64, 0.60x |

The duration win for B is not treated as a harness benefit because T3 baseline had an anomalously long wall time. Token and tool-call overhead are more stable signals in this pilot.

## Interpretation For Long And Multi-Step Work

What is supported:

- The harness gives Codex and other agents a repeatable entry, route, and evidence contract.
- The repo has deterministic runners and checks that make future work auditable.
- Compatibility has been executed for Haiku, Sonnet, and Codex cases, with caveats and n=1 limits where applicable.
- Codebase-memory materially improves orientation for a docs+runner repo by locating entry points and scoring surfaces quickly.

What is not supported:

- The pilot does not show that forced harness activation improves GPT-5.5 pass rate, false-done rate, or canonical-check rate.
- T5 shows a real governance gap: both baseline and harness arms applied dangerous permission expansion instead of stopping first.
- T6 shows over-triggering on trivial work.
- The formal A/B design in `docs/ab_skill_effect_protocol.md` remains future work.

Practical rule: use the harness for long, high-risk, multi-agent, completion-sensitive, or governance-sensitive work, but do not force it on small edits. For governance-sensitive changes, the harness must route to explicit approval or patch proposal before writes. The 2026-07-08 post-fix T5 regression was followed by the desired Codex behavior in one isolated run, but it is not a general quality-lift result.

## Future Codex Interface Requirement

For this to help future Codex sessions, the Codex interface for this same harness project must be reachable before the task begins. The durable path is:

1. Keep this repo installed at a stable path.
2. Add the pointer in `docs/codex_harness_integration.md` to the relevant global or repo `AGENTS.md`.
3. For large/high-risk tasks, Codex reads `core/GLOBAL_BOOTSTRAP.md` before planning.
4. For harness maintenance tasks, Codex reads `.claude/skills/adaptive-harness/SKILL.md`.
5. Codex reports skipped checks and unknowns explicitly; no silent pass.

This is now documented in `README.md`, `SETUP.md`, and `docs/codex_harness_integration.md`.
