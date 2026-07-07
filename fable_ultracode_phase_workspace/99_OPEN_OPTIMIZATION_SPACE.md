# 99 OPEN OPTIMIZATION SPACE

這個檔案給 Fable / Fabo 在處理 Phase 1、Phase 2、Phase 3 時記錄額外發現。  
目的不是讓系統無限制膨脹，而是讓它有空間做更好的設計、簡化、合併與驗證。

每個額外想法都必須用以下格式記錄。

---

## Optimization Proposal Template

### Proposal ID

`OPT-YYYYMMDD-###`

### Source Phase

- Phase 1 / Phase 2 / Phase 3 / Cross-phase

### Category

- prompt_simplification
- workflow_merge
- codex_delegation
- code_invocation_efficiency
- subagent_simplification
- deterministic_script_candidate
- benchmark_candidate
- public_safety
- skill_packaging
- lower_tier_model_support
- research_skill_suite
- other

### Current Problem

說明目前問題。  
例如：某條規則可能只是舊模型補丁、某個 subagent 只增加合併成本、某個 report 每次由 LLM 從零生成太浪費。

### Proposed Change

清楚描述建議改法。

### Classification

只能選一個：

- `adopt_now`
- `patch_proposal`
- `benchmark_first`
- `defer`
- `reject`

### Expected Benefit

說明預期好處，例如：

- fewer tool calls
- lower token cost
- lower latency
- easier for Haiku/Sonnet
- safer scheduled review
- less harness bloat
- clearer AI-review / adaptive-harness boundary

### Risk

說明風險。

### Required Test

說明要怎麼測。  
如果沒有測試方法，不應該直接採用。

### Human Approval Needed?

- yes / no

### Status

- proposed
- accepted
- rejected
- benchmark_pending
- implemented
- superseded

---

## Standing Design Questions

請在三個 Phase 中持續檢查：

1. 這套系統是否越來越輕，還是越來越肥？
2. AI-review 和 adaptive-harness 是否真的共用 schema / history，而不是平行系統？
3. 哪些檢查應該改成 deterministic script？
4. 哪些判斷必須保留給 LLM？
5. 哪些任務可以交給 Haiku？
6. 哪些任務適合 Sonnet？
7. 哪些任務必須 Opus/Fable？
8. 哪些 mechanical work 適合 Codex？
9. 哪些 high-risk change 必須 human approve？
10. 哪些 proposed optimization 必須 benchmark first？

---

## Notes

請把所有額外想法記在這裡，不要直接把 scope 無限制擴大。  
Phase 3 驗收時，必須檢查這裡的 proposal 是否有被分類、是否有測試、是否有 unresolved high-risk item。

---

# Recorded proposals (Phase 1, 2026-07-06)

Source evidence: phase-1 audit workflow `wf_b5dde6df-862` (5 read-only lanes) +
first real runner runs. Full finding records: `phase1_findings.json` (REC-20260706-001..032),
ingested into `reports/ai-review/history/2026-07-06-ai-review.json`.

### OPT-20260706-001 — Register orchestration_bench files in INDEX.yaml (or document exemption)
- Source Phase: Phase 1 · Category: other (repo hygiene)
- Current Problem: 31 tracked files under `distillation/orchestration_bench/` are absent from INDEX.yaml; INDEX self-declares "every content file must appear exactly once" (MT-5). The new runner now flags this deterministically on every run (31 × P2 index_drift).
- Proposed Change: either register all 31 (mechanical — Codex-eligible per the ≥3-file tripwire) or add a documented exemption rule for bench fixtures + a matching exclusion in the runner's collector.
- Classification: `patch_proposal`
- Expected Benefit: standard_review deterministic issues drop 31→0; INDEX contract becomes truthful again.
- Risk: registering fixture files may bloat INDEX; exempting may hide real drift. Repo-owner call.
- Required Test: `python scripts/run_ai_review.py --mode standard_review --dry-run --no-home` → index_drift count 0.
- Human Approval Needed? yes (repo-owner decision between register vs exempt) · Status: proposed

### OPT-20260706-002 — Merge the 4 PreToolUse(Bash) hooks into one dispatcher
- Source Phase: Phase 1 · Category: code_invocation_efficiency
- Current Problem: 4 separate Python interpreters per Bash call (per-fire interpreter cost measured on the operator machine); heavy sessions accumulate minutes of dead startup (audit invocation lane; exact figures in the private dotfiles-side records).
- Proposed Change: one dispatcher hook importing the 4 checks as module functions; keep per-check tests.
- Classification: `patch_proposal` (hooks = governance surface; human approval)
- Expected Benefit: most per-Bash-call interpreter overhead removed; thousands fewer Windows forks per heavy session.
- Risk: one dispatcher bug degrades all 4 gates at once. Mitigate: import-not-rewrite + existing hooks/tests suite.
- Required Test: replay logged Bash payloads through dispatcher, assert identical allow/warn/block verdicts per hook; time 100 fires before/after.
- Human Approval Needed? yes · Status: proposed

### OPT-20260706-003 — Merge the 3 UserPromptSubmit Python hooks
- Same shape as OPT-002 (meaningful per-prompt saving). Verify multiple additionalContext entries can be concatenated safely.
- Classification: `patch_proposal` · Human Approval Needed? yes · Status: proposed

### OPT-20260706-004 — Remove statusline_pro.mjs (superseded Node relic on UserPromptSubmit '*')
- Source Phase: Phase 1 · Category: code_invocation_efficiency
- Current Problem: Node cold-start + multiple forks per prompt on a '*' matcher (the exact d5f0bde anti-pattern); superseded by a newer statusLine; output likely invisible.
- Proposed Change: unwire from settings.json (file stays in git history).
- Classification: `patch_proposal` (settings.json = human approval required)
- Expected Benefit: the majority of UserPromptSubmit hook latency removed.
- Risk: very low; one-week trial answers "did anyone miss it".
- Required Test: one-week removal trial; confirm no missing-statusline complaint and prompt latency drop in hook telemetry.
- Human Approval Needed? yes · Status: proposed

### OPT-20260706-005 — Fix cbm-session-reminder hook text (P0 dueling instructions)
- Source Phase: Phase 1 · Category: prompt_simplification
- Current Problem: every session gets two contradictory instructions: hook says "ALWAYS use codebase-memory-mcp FIRST" (no caveat); CLAUDE.md §Code Exploration says scoped/advisory/verify-load-bearing-claims. CLAUDE.md itself documents the conflict. (REC-20260706-001)
- Proposed Change: edit the 16-line hook to the scoped advisory form; then delete CLAUDE.md's counter-rule caveat sentence.
- Classification: `patch_proposal` (hook edit) · Expected Benefit: removes a standing P0 instruction conflict + ~120 tokens/session-start.
- Risk: if only the CLAUDE.md caveat is removed without fixing the hook, the unscoped form wins — sequence matters.
- Required Test: fresh session capture shows hook text matches CLAUDE.md scoping; small-single-file probe greps directly instead of indexing.
- Human Approval Needed? yes · Status: proposed

### OPT-20260706-006 — DELEGATION.md REJECT path instructs a deny-listed command
- Source Phase: Phase 1 · Category: workflow_merge
- Current Problem: DELEGATION.md:198 mandates `git checkout -- <files>` for rejecting delegate output, but `Bash(git checkout --:*)` is in settings.json permissions.deny — the documented recovery path fails exactly at recovery time. (REC-20260706-002)
- Proposed Change: one-line fix to `git restore <files>` (or `git stash push` for archive-not-delete consistency).
- Classification: `adopt_now` (one-line doc fix, no enforcement change; still routed through normal review)
- Required Test: scratch-repo replay of the REJECT sequence: deny fires on old command, new command succeeds.
- Human Approval Needed? no (doc correction; the deny-list itself is untouched) · Status: proposed

### OPT-20260706-007 — CLAUDE.md slim (merge dual review-gates, one threshold, gemini residue → 1 tombstone/file)
- Source Phase: Phase 1 · Category: prompt_simplification
- Current Problem: two review-gate sections = 43% of CLAUDE.md with ~70% trigger overlap; 4 inconsistent file-count thresholds (≥2/≥3/50-LOC-only); 45 Gemini lines / 16 tombstones. (REC-20260706-004/005/006/015)
- Proposed Change: single merged gate + one canonical threshold + one tombstone per file + per-repo content relocated; target ~140-155 lines.
- Classification: `benchmark_first` — MUST pass `claude_md_eval.py` incl. the 6-incident replay suite before shipping (benchmark case `legacy_claude_md_vs_pointer_based_slim`).
- Risk: dropping a trigger condition recreates the incident class it guards; the edit itself is trigger-#5 governance.
- Required Test: benchmarks/ai_review_cases.yaml case `legacy_claude_md_vs_pointer_based_slim` (STANDALONE terminal only).
- Human Approval Needed? yes · Status: **implemented 2026-07-06** — eval run 20260706-223951 graded PASS (grader agent, 24 samples, quotes spot-checked); landed as dotfiles ddf2872 (215→96 lines)

### OPT-20260706-008 — deprecated_markers collector counts doctrine MENTIONS of TODO_FILL
- Source Phase: Phase 1 · Category: deterministic_script_candidate
- Current Problem: core doctrine text ("uncertainty emits TODO_FILL stubs") is counted as a stub, producing 1 permanent phantom issue per report.
- Proposed Change: none yet — tolerate the known 1-line noise; revisit if it grows (e.g. exclude `core/` + `operating_model/` from the marker scan).
- Classification: `defer` · Required Test: report todo_fill_count stays ≤ doctrine-mention baseline.
- Human Approval Needed? no · Status: proposed

### OPT-20260706-009 — reports/ gitignored (observability vs public-repo privacy)
- Source Phase: Phase 1 · Category: public_safety
- Decision taken: `reports/` is GITIGNORED. Rationale: (a) repo is public — reports embed telemetry harvested from the operator's private ~/.claude; (b) repo precedent (orchestration_bench: findings live in tracked logs, generated runs ignored). Durable findings land in tracked memory/ + the workspace findings JSON + ~/.claude/audits (git-tracked privately).
- Classification: `adopt_now` (already applied in Phase 1 .gitignore)
- Risk: local-only history is lost on clone — acceptable; the JSONL is regenerable and the durable trail is the proposals ledger + audits.
- Required Test: `git check-ignore reports/ai-review/latest.json` exits 0.
- Human Approval Needed? no (reversible one-line ignore) · Status: implemented

### OPT-20260706-011 — LICENSE decision for the now-public repo
- Source Phase: Phase 2 · Category: public_safety
- Current Problem: the repo is PUBLIC with no LICENSE file (= all-rights-reserved default). `memory/project_state.md` records MIT + NOTICE-carve-out intent for the source project; this repo needs its own deliberate choice. `docs/publication_status.md` carries this as an outstanding checklist item.
- Proposed Change: human picks a license (MIT + NOTICE carve-out is the recorded precedent) and commits LICENSE; the publication checklist box then closes.
- Classification: `patch_proposal` (legal/ownership decision — agents must not choose)
- Expected Benefit: closes the "License decided" checklist item; makes reuse terms explicit.
- Risk: none from deciding; risk is only in NOT deciding (ambiguous reuse terms on a public repo).
- Required Test: `test -f LICENSE` + publication checklist review.
- Human Approval Needed? yes · Status: proposed

### OPT-20260706-012 — Full-history secret scan before next release
- Source Phase: Phase 2 · Category: public_safety
- Current Problem: the repo went public without a recorded full-history secret scan; `docs/publication_status.md` marks it UNVERIFIED.
- Proposed Change: run a history-wide scanner (e.g. gitleaks/trufflehog) at the next release gate; record the result in the publication doc.
- Classification: `adopt_now` (read-only scan; human runs or approves the tool choice)
- Required Test: scanner exit 0 over `git log --all`; result recorded in docs/publication_status.md.
- Human Approval Needed? yes (tool execution on the operator machine) · Status: proposed

### OPT-20260706-014 — system_prompts_leaks as external design reference (user-requested assessment)
- Source Phase: Phase 3 (user interjection) · Category: other (external reference)
- Current Problem: assessed https://github.com/asgeirtj/system_prompts_leaks (51.5k stars, CC0-1.0, actively maintained through 2026-07; ~50 products incl. Anthropic Fable 5/Opus 4.8/Claude Code, OpenAI GPT-5.5/Codex, tool JSON specs). Question: can it serve the adaptive harness?
- Proposed Change: SPLIT verdict —
  (a) Vendoring any content into this PUBLIC repo: **reject** — violates docs/publication_status.md never-include ("proprietary/private system prompts, hidden internals of any model or agent product"), regardless of the leak repo's own CC0 claim (its license cannot launder provenance).
  (b) External READ-ONLY reference for reviews: **adopt_now** — usage rules: consult during `harness_cleanup_review` Q5 (tool-format currency) and `codex_delegation_review` (how Codex-class models are natively instructed — feeds the universal-entry work); treat all content as UNVERIFIED-by-default point-in-time evidence, cite as "external reference, unverified" never as ground truth; links live operator-private (memory/workspace), never in public repo docs.
  (c) Change-signal: when the repo's Claude Code prompt updates materially, trigger a `diff_only_review`-style harness assumption check: **defer** (manual for now; automating would need a watcher).
- Expected Benefit: real-world comparison corpus for prompt/tool-format decisions; Codex-native instruction phrasing for the universal entry.
- Risk: treating leaked snapshots as authoritative (they may be partial/stale/wrong); reputational/posture risk if linked from the public repo — mitigated by keeping references operator-private.
- Required Test: none for (b) (read-only); for (c) a watcher would need its own proposal.
- Human Approval Needed? no for (b); yes if anyone proposes (a) — which this entry pre-rejects · Status: proposed

### OPT-20260706-013 — Standardize the mixed depends_on path convention
- Source Phase: Overlay 04 · Category: other (repo hygiene)
- Current Problem: frontmatter `depends_on` uses TWO conventions - file-relative (overlay family, `../operating_model/...`) and repo-root-relative (context/ ladder, `context/L0_bootstrap.md`). The graph builder resolves both (file-relative first, root fallback) and counts 17 root-relative edges; check_agent_artifacts resolves only file-relative (works because its 8 files all use that form).
- Proposed Change: pick ONE convention (file-relative matches the machine-checked overlay set) and sweep the 17 root-relative entries; or document the dual convention as sanctioned in AGENTS.md.
- Classification: `defer` (zero broken refs today; the builder makes the mix visible via `root_relative_depends_on_count` - act if the count grows or a resolution bug appears)
- Required Test: `python scripts/build_harness_graph.py` → root_relative_depends_on_count == 0 (if standardized).
- Human Approval Needed? no (mechanical sweep, Codex-eligible if adopted) · Status: proposed

### OPT-20260706-010 — Rotate/bound the hook-events telemetry log (multi-MB tail-read per tool call)
- Source Phase: Phase 1 · Category: code_invocation_efficiency
- Current Problem: correlate_brain_evidence.py (PostToolUse '*') tail-reads a growing multi-MB JSONL every tool call.
- Proposed Change: marker-file early-bail + size-based rotation (keep last N MB; hook_stats reads rotated set).
- Classification: `patch_proposal` (hook + telemetry contract change)
- Required Test: hook_stats.py --days 30 output identical across rotation boundary; per-fire time before/after.
- Human Approval Needed? yes · Status: proposed
