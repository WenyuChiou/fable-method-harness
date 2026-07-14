# fable-method-harness

**A portable operating harness distilled from Fable's working method — a
discipline-and-cost layer for AI-assisted work, verified on Claude and Codex
with reserved entry points for other agent runtimes. Not a capability booster.**

> **~2.5× cheaper** at equal quality (when routing is accurate) · **~4–5%** context per task · **~0** tokens for review reports · **~30** defects caught building itself · **0** capability lift, by design

## What we actually measured

Each row re-runs from its named artifact; full ledger — every negative result
included — in **[`docs/evidence.md`](docs/evidence.md)**.

| Measured | Result | Where |
|---|---|---|
| **Cost routing vs all-Opus** | Same quality (6/6 = 6/6) and same whole-workload stability (**1.00 = 1.00**, k=5) at **~40% of the cost (~2.5× cheaper)**, when routing is accurate | `docs/evidence.md`, `evals/route_ab/` |
| **Naive all-cheap baseline** | all-Haiku scores **0.00** whole-workload — it misses the subtle-honesty subtask every single time (0/5). Routing, not the cheap model alone, is what buys the stability | same |
| **Invocation fix** | activation over-load **2.84× → removed** (single-file default); the completion-honesty route self-triggered **0/10 → 4/5** | `docs/evidence.md` |
| **Context per task** | **~4–5%** of the repo loaded (~12–16k of ~303k tokens) instead of bulk-reading | `ROUTES.yaml` + file sizes |
| **Standing instructions** | a 215-line global instruction file slimmed to **96 lines (~55% less)** with identical gate behavior | dotfiles commit `ddf2872` |
| **Review reports** | **~0 LLM output tokens** — rendered deterministically from JSON | `scripts/run_ai_review.py --dry-run` |
| **Defects caught building itself** | **~30** confirmed, including two silent state-loss bugs | commit trailers `f55459d`→`0dd0cf2` |

Honest boundary: across eight experiments a frontier model was already at the
ceiling with the harness off — this is a **cost, discipline, and audit** layer,
not a capability boost.

## What you get

- **💸 Cost routing** — cheap model on the mechanical bulk, the expensive one reserved for the honesty-critical parts.
- **🛑 Honest-failure discipline** — review gates + completion-honesty checks; an explicit "unknown / HALT" beats a confident guess.
- **🪶 Context economy** — classify first, then load only the files a task needs.
- **🔍 Audit trail** — every claim cites a re-runnable artifact; negative results are published too.

## Before / after — what changes when you use it

Same task, same model — the harness changes *how* you work, not how smart the
model is. Every row below traces to the measured table above.

| | Ad-hoc (no harness) | With the harness |
|---|---|---|
| **Context per task** | bulk-read the repo (~303k tokens) | classify, then load ~4–5% (~12–16k) |
| **Cost on mixed work** | one expensive model for everything | cheap model on the mechanical bulk, expensive one reserved → **~2.5× cheaper at the same quality**, when routing is accurate |
| **A subtle-honesty slip** | can ship silently | reserved to the strong model behind a HALT/UNSCORED gate (all-cheap misses it 0/5) |
| **Review reports** | the model writes them (output tokens) | rendered from JSON (**~0 output tokens**) |
| **A "done / passing" claim** | trusted as written | a completion-honesty gate runs first |
| **Raw capability** | already at the ceiling | **unchanged — no lift, by design** |

The gain is in eliminating the left column's failure modes (blown context,
uniform cost, silent slips) — not a smarter model.

## When to use it

Use it when a mistake is expensive:

- long or multi-step work where state can drift;
- multi-agent runs where lane reports need re-checking;
- completion claims (done / passing / fixed / ready / safe / staged);
- cost-sensitive jobs where a cheap model can safely do the bulk of the work;
- governance, permissions, hooks, release, or eval changes.

**Skip it** for one-line edits, typo fixes, or pure "make the model smarter"
asks — there it adds ceremony without benefit (also measured: a forced run on a
one-typo control added overhead with no quality gain).

## Quick start

```bash
git clone https://github.com/WenyuChiou/fable-method-harness
cd fable-method-harness
git config core.hooksPath scripts/hooks
python validation/integration_check.py   # 59 checks, ~3 min
```

Or hand the repo to an agent:

> Read `SETUP.md` and set this up.

Then, for a real task:

> Read `core/GLOBAL_BOOTSTRAP.md` and follow its routing for this task.

And to make it improve with use — the rolling improvement loop is in the
repo, portable, and propose-only (you disposition, agents never
self-approve):

```bash
python scripts/run_adaptive_harness_review.py --mode rolling_improvement_review --no-home
```

`SETUP.md` §4 covers day-1 usage plus this loop, including the honest
boundary between what the repo ships and what stays a documented pattern.

## How agents enter it

Same harness, one portable pointer per runtime. The **Status** column is honest
about what is actually verified versus what is wired but untested — reserved
slots are placeholders, not compatibility claims.

| Runtime | Entry | Status |
|---|---|---|
| Claude Code | `SKILL.md` (auto-discovered) | verified — Haiku + Sonnet cases (n=1 per case) |
| Codex | `AGENTS.md` · `docs/codex_harness_integration.md` | verified — scoped-edit cases (n=1) |
| Cursor · opencode · any AGENTS.md agent | `AGENTS.md` (convention) | enters by convention; not separately benchmarked |
| Hermes · router surfaces | `docs/agent-routing-policy.md` | router only — deterministic scan, then route judgment onward |
| Antigravity CLI · other agent CLIs | `core/GLOBAL_BOOTSTRAP.md` pointer | reserved — wiring defined, not yet verified |
| Bare model or shell | `BOOTSTRAP.md` · `core/GLOBAL_BOOTSTRAP.md` | portable pointer |

One rule for all of them: **classify the task, load only the routed files, do
not bulk-read the repo.** `python scripts/setup_harness.py --print-wiring` prints
the pointer to drop into another repo.

## Is it actually useful? (the honest version)

Yes — for **cost, discipline, and audit; not for capability.** We tried hard to
show a capability lift and could not: across eight experiments a frontier model
was already at the ceiling with the harness off. What survives measurement is the
table at the top. The full ledger — every positive, every negative, and the
artifact to re-run each one — is in **[`docs/evidence.md`](docs/evidence.md)**.
Read it before adopting.

The load-bearing rolling-loop claim was **measured on 2026-07-14 and the
loop LOST**: replaying the real 5-run history with linkage stripped, k=3
agents re-derived every repeated finding at recall 1.00 (vs the frozen
<0.90 bar the linkage machinery needed to justify itself), so the
REC-linkage complexity is not earning its keep — though manual
re-derivation cost 11–66x the brief read per run, so the deterministic
report + brief **emitter** is what carries the value. As promised, the
negative result ships: see the case's EXECUTED notes in
[`benchmarks/harness_cases.yaml`](benchmarks/harness_cases.yaml), the row
in [`docs/evidence.md`](docs/evidence.md), and the propose-only
simplification REC in
[`docs/rolling_loop_simplification_rec_2026_07_14.md`](docs/rolling_loop_simplification_rec_2026_07_14.md).

## Repository map

| Path | What's there |
|---|---|
| `core/` | Portable discipline for any project |
| `ROUTES.yaml` | Task type → exact required file set |
| `.claude/skills/adaptive-harness/` | Runtime-agnostic harness-audit adapter |
| `scripts/`, `validation/` | Deterministic runners and checks |
| `docs/` | Evidence, routing policy, publication status, operator runbook |
| `benchmarks/`, `evals/` | Public cases · local-only raw runs (gitignored) |

## Safety

Public repo. No secrets, private chat exports, hidden reasoning, or telemetry.
Generated reports stay out of git by design. Re-run the checklist in
`docs/publication_status.md` before any release.

## Contributing

- Every new claim needs a re-runnable artifact; mark unmeasured dimensions
  `UNSCORED`, not guessed.
- Keep route files small and explicit.
- Run `python validation/integration_check.py` before proposing a change.

## License

MIT. See `LICENSE`.
