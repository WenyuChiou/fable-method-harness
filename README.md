---
id: README
layer: doc
purpose: Explain what this adaptive harness system is, who should use it, what is measured, and how agents enter it
read_when: First contact with the repo, or when unsure how the pieces fit
depends_on:
  - context/L0_bootstrap.md
  - HARNESS.yaml
  - docs/publication_status.md
  - docs/evidence.md
  - docs/codebase_memory_assessment.md
  - docs/codex_harness_integration.md
used_by: [ROUTE-phase-review, ROUTE-tool-discovery, ROUTE-pr-review, ROUTE-eval-design, ROUTE-memory-update, ROUTE-runtime-export, ROUTE-repo-maintenance, ROUTE-ab-test-design]
tags: [entrypoint, overview, publication, adaptive-harness, open-source]
retrieval_keywords: [what is this repo, harness overview, how to use, entrypoint, publication status, progressive disclosure, adaptive harness skill system, codex integration, opencode]
---

# fable-style-project-harness

Progressive-disclosure operating harness for AI-assisted software work.

It gives an agent a small routed file set, a task loop, review gates, and an honest way to stop when evidence is missing. Use it for long, multi-step, multi-agent, high-risk, or evaluation-heavy work. Skip it for one-line edits.

## Project Status

| Item | Status |
|---|---|
| Visibility | Public repo, public-safe posture documented in `docs/publication_status.md` |
| License | MIT |
| Runtime dependency | Python standard library for setup and verification scripts |
| Deterministic verification | `python validation/integration_check.py` currently covers 51 checks |
| Evidence posture | Claims live in `docs/evidence.md`; negative results are published |

## Install

```bash
git clone https://github.com/WenyuChiou/fable-style-project-harness
cd fable-style-project-harness
git config core.hooksPath scripts/hooks
python validation/integration_check.py
```

Or hand the repo to an agent and say:

```text
Read SETUP.md and set this up.
```

The setup path is idempotent, offline, and stdlib-only:

```bash
python scripts/setup_harness.py
python scripts/setup_harness.py --print-wiring
```

## When To Use It

Use the harness when failure is expensive:

- long or multi-step work where state can drift;
- multi-agent work where lane reports must be re-verified;
- completion claims such as done, passing, fixed, ready, safe, or staged;
- benchmark, eval, release, governance, permissions, hooks, or routing changes;
- maintenance of AI instructions, skills, hooks, AGENTS.md, or CLAUDE.md.

Do not force it for trivial edits. The 2026-07-07 pilot shows forced activation on a one-typo control adds overhead without quality benefit.

## Agent Entry Points

| Runtime | Entry path | Notes |
|---|---|---|
| Claude Code / skill-aware runtimes | `SKILL.md`, or `python scripts/setup_harness.py --wire-skill --wire-claude` | Installs a launcher stub; this repo remains the source of truth. |
| Codex | `AGENTS.md` inside this repo; `docs/codex_harness_integration.md` defines the Codex runtime interface | Same project, different interface: Codex uses the repo's core routes and evidence contract through AGENTS.md instead of the Claude skill wrapper. |
| Cursor / OpenCode / AGENTS.md-convention agents | `AGENTS.md` | Use `python scripts/setup_harness.py --print-wiring` to copy the portable pointer into another repo or global instruction file. |
| Hermes / router surfaces | `docs/agent-routing-policy.md` plus the `--print-wiring` routing row | Hermes can run deterministic scans and route semantic or high-risk judgment to a stronger surface. |
| Bare model, shell, or other AI | `BOOTSTRAP.md` for this project; `core/GLOBAL_BOOTSTRAP.md` for other projects | Paste a single pointer line; do not bulk-read the repo. |

## Codex Runtime Interface

This repo does not fork a second Codex harness. Codex is another interface to the same harness: same `core/`, same routes, same evidence contract, different activation surface. For future Codex work outside this repo, run `python scripts/setup_harness.py --print-wiring` and paste the emitted pointer into the relevant global or repo `AGENTS.md`. The generic form is:

```text
For large, multi-agent, high-risk, phase-gated, or completion-sensitive tasks, read <harness-root>/core/GLOBAL_BOOTSTRAP.md and follow its routing. For AI-harness maintenance, README/evidence work, AGENTS.md/CLAUDE.md/hooks/skills/settings review, read <harness-root>/.claude/skills/adaptive-harness/SKILL.md. Load routed files only; do not bulk-read the harness repo.
```

The longer operational guide is `docs/codex_harness_integration.md`.

## Evidence Summary

This repo is not marketed as a model-capability booster. The measured value is process discipline, lower standing-instruction load, auditability, and safer stopping behavior.

| Claim area | Current evidence | Artifact |
|---|---|---|
| Clone health | 51 deterministic checks | `python validation/integration_check.py` |
| Runtime compatibility | Haiku 4/4, Sonnet 2/2, Codex 2/2 executed cases; Codex n=1 scoped edit honored file fence and no-commit rule | `benchmarks/model_compatibility_cases.yaml` |
| Context economy | Routed file sets are far smaller than whole-repo loading | `docs/evidence.md` |
| GPT-5.5 forced-activation pilot | No quality lift detected: A 4/5 pass, B 4/5 pass; false-done A 1/5, B 1/5; B used 1.58x tool calls and 2.84x input tokens | `docs/harness_ab_pilot_2026_07_07.md` |
| Long/multi-step gap found | T5 governance-sensitive fixture failed in both arms; this is a harness gap, not a win | `docs/harness_ab_pilot_2026_07_07.md` |
| Post-fix governance regression | After adding the governance trigger to `core/GLOBAL_BOOTSTRAP.md`, one isolated Codex T5 run left destructive settings unchanged and requested approval/narrower allowlist | `docs/t5_codex_governance_regression.md` |

Interpretation: use the harness where process failure is plausible, not as a blanket prompt upgrade. The formal A/B protocol remains pre-registered future work in `docs/ab_skill_effect_protocol.md`.

## Daily Usage

Run a high-risk task with the portable core:

```text
Read core/GLOBAL_BOOTSTRAP.md and follow its routing for this task.
```

Audit an AI setup or harness:

```bash
python scripts/run_ai_review.py --mode harness_cleanup_review --target <repo>
python scripts/run_ai_review.py --mode harness_cleanup_review --ingest findings.json
python scripts/run_adaptive_harness_review.py --mode rolling_improvement_review --target <repo>
python scripts/run_adaptive_harness_review.py --mode patch_proposal
```

Summarize local pilot A/B scorecards when the ignored raw `evals/` directory is present:

```bash
python scripts/summarize_harness_ab_pilot.py --markdown
```

## Repository Map

| Path | Purpose |
|---|---|
| `core/` | Portable discipline for work in other projects. |
| `context/` | Project-bound startup ladder for `method-harness-compiler`. |
| `ROUTES.yaml` | Task classifier to exact required file sets. |
| `.claude/skills/adaptive-harness/` | Runtime-agnostic adapter for auditing and improving AI harnesses. |
| `scripts/` | Deterministic runners, validators, setup, and evidence summarizers. |
| `validation/` | Integration and retrieval smoke checks. |
| `benchmarks/` | Compatibility and retrieval cases. |
| `docs/` | Evidence, durable A/B summaries, publication status, routing policy, integration guides. |
| `evals/` | Local ignored raw runs only; do not cite as public evidence. |

## Safety And Publication Rules

This repo is public. Do not add secrets, credentials, private chat exports, hidden reasoning traces, local telemetry, or private system prompts. Generated reports stay out of git by design. Before a release or README relaunch, repeat the public-safety checklist in `docs/publication_status.md`.

## Contributing

1. Keep route files small and explicit.
2. Add runnable evidence for new claims.
3. Mark unmeasured dimensions `UNSCORED`, not guessed.
4. Run `python validation/integration_check.py` before proposing a change.
5. For README/evidence changes, update `docs/harness_ab_pilot_2026_07_07.md` or the relevant tracked evidence doc; run `python scripts/summarize_harness_ab_pilot.py --markdown` only when local ignored scorecards are present.

## License

MIT. See `LICENSE`.
