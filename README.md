# fable-style-project-harness

**A discipline-and-cost layer for AI-assisted software work — not a capability booster.**

It won't make the model smarter (we measured that — it doesn't). What it does is
cut the cost of multi-step work, catch expensive mistakes before they ship, and
keep an honest audit trail. Its sharpest single lever is **cost routing — comparable
quality at roughly 2.5× lower cost when the routing is accurate.**

## What we actually measured

The numbers first — nothing here is aspirational, and each row re-runs from its
named artifact. Full ledger, including every negative result, in
**[`docs/evidence.md`](docs/evidence.md)**.

| Measured | Result | Where |
|---|---|---|
| **Cost routing vs all-Opus** | Same quality (6/6 = 6/6) and same whole-workload stability (**1.00 = 1.00**, k=5) at **~40% of the cost (~2.5× cheaper)**, when routing is accurate | `docs/evidence.md`, `evals/route_ab/` |
| **Naive all-cheap baseline** | all-Haiku scores **0.00** whole-workload — it misses the subtle-honesty subtask every single time (0/5). Routing, not the cheap model alone, is what buys the stability | same |
| **Invocation fix** | activation over-load **2.84× → removed** (single-file default); the completion-honesty route self-triggered **0/10 → 4/5** | `docs/evidence.md` |
| **Context per task** | **~4–5%** of the repo loaded (~12–16k of ~303k tokens) instead of bulk-reading | `ROUTES.yaml` + file sizes |
| **Standing instructions** | a 215-line global instruction file slimmed to **96 lines (~55% less)** with identical gate behavior | dotfiles commit `ddf2872` |
| **Review reports** | **~0 LLM output tokens** — rendered deterministically from JSON | `scripts/run_ai_review.py --dry-run` |
| **Defects caught building itself** | **~30** confirmed, including two silent state-loss bugs | commit trailers `f55459d`→`0dd0cf2` |

And the honest boundary: across eight experiments a frontier model was already at
the ceiling with the harness off — so this is a **cost, discipline, and audit**
layer, not a capability boost.

## What you get

- **💸 Cost routing** — put a cheap model on the mechanical majority of a job and
  reserve the expensive one for the honesty-critical parts. Measured: the same
  quality *and* stability as all-Opus (1.00 = 1.00 across 6 subtasks, k=5) at
  ~40% of the cost — when the routing is accurate.
- **🛑 Honest-failure discipline** — review gates, completion-honesty checks, and
  a rule that an explicit "unknown / HALT" beats a confident guess. Measured:
  caught ~30 real defects while building itself; refused an unsafe eval run
  instead of faking a result.
- **🪶 Context economy** — classify first, then load only the files a task needs
  (~4–5% of the repo) instead of dumping everything into context.
- **🔍 Audit trail** — every claim in `docs/evidence.md` cites a re-runnable
  artifact, and negative results are published — including the measured fact
  that it does *not* boost capability.

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
git clone https://github.com/WenyuChiou/fable-style-project-harness
cd fable-style-project-harness
git config core.hooksPath scripts/hooks
python validation/integration_check.py   # 53 checks, ~3 min
```

Or hand the repo to an agent:

> Read `SETUP.md` and set this up.

Then, for a real task:

> Read `core/GLOBAL_BOOTSTRAP.md` and follow its routing for this task.

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
