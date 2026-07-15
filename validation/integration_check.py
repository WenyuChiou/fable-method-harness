#!/usr/bin/env python3
"""Phase-3 integration check - the re-runnable half of docs/integration_test_matrix.md.

Executes the full deterministic verification matrix for the AI-review +
adaptive-harness system: CLI surface, all modes dry-run, JSON validity,
dry-run zero-mutation, the E2E data flow (AI-review -> adaptive runner ->
grep_history REC-id lookup; the rolling-state linkage was retired by
REC-20260714-001), scheduled report-only invariants, validators, posture,
graph build, and all eight test suites. Emits one PASS/FAIL row per check
plus a JSON blob; docs/integration_test_matrix.md records executed
snapshots of this output (computed, never hand-written).

Run:
    python validation/integration_check.py [--json]

Exit codes: 0 all rows PASS; 1 any FAIL.
"""
import io
import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PY = sys.executable
ROWS = []


def utf8():
    for n in ("stdout", "stderr"):
        s = getattr(sys, n)
        if hasattr(s, "buffer"):
            setattr(sys, n, io.TextIOWrapper(s.buffer, encoding="utf-8", errors="replace"))


def run(cmd, timeout=600):
    p = subprocess.run(cmd, cwd=str(REPO), capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=timeout)
    return p.returncode, p.stdout, p.stderr


QUIET = False       # --json: suppress ALL human rows (JSON is the output)
FAIL_ONLY = False   # --quiet: suppress PASS rows; FAIL rows print verbatim


def row(name, layer, ok, evidence, command=""):
    ROWS.append({"test": name, "layer": layer, "status": "PASS" if ok else "FAIL",
                 "evidence": evidence[:300], "command": command})
    if QUIET or (ok and FAIL_ONLY):
        return
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"  <- {evidence[:160]}"))


def git_state():
    """Mutation-detection surface. -uall expands files inside untracked dirs
    (plain porcelain collapses them to one '?? dir/' line) and
    --ignored=matching includes gitignored paths - reports/ is the runners'
    DEFAULT output dir, so without it a dry-run regression that wrote
    reports/ would pass the safety rows vacuously (2026-07-06 review-pair
    finding)."""
    rc, out, _ = run(["git", "status", "--porcelain", "-uall", "--ignored=matching"])
    return out


AI_MODES = ["standard_review", "harness_cleanup_review", "code_invocation_review",
            "codex_delegation_review", "scheduled_review", "diff_review",
            "experiment_review"]
AH_MODES = ["harness_inventory", "harness_cleanup_review", "code_invocation_review",
            "ai_review_integration", "skill_fit_review", "diff_only_review",
            "scheduled_harness_review", "experiment_design", "patch_proposal"]


def main():
    utf8()
    import argparse
    global QUIET, FAIL_ONLY
    ap = argparse.ArgumentParser(prog="integration_check.py",
                                 description="Phase-3 integration instrument (computed check count).")
    ap.add_argument("--json", action="store_true",
                    help="Emit ONLY the JSON blob on stdout (human rows suppressed).")
    ap.add_argument("--quiet", action="store_true",
                    help="Suppress PASS rows; FAIL rows + final summary print verbatim. "
                         "For in-session runs where success noise re-enters agent context. "
                         "--json takes precedence when both are passed (all rows go to the JSON blob).")
    args = ap.parse_args()
    as_json = args.json
    QUIET = as_json
    FAIL_ONLY = args.quiet

    # 1. CLI surface
    for script in ("scripts/run_ai_review.py", "scripts/run_adaptive_harness_review.py",
                   "scripts/check_codebase_memory_freshness.py"):
        rc, out, err = run([PY, script, "--help"])
        row(f"{script} --help", "CLI", rc == 0, err or "exit 0",
            f"python {script} --help")

    # 2. Every mode dry-runs to valid JSON, dry_run flag true, correct source
    before = git_state()
    for script, modes, sched in (
            ("scripts/run_ai_review.py", AI_MODES, "scheduled_review"),
            ("scripts/run_adaptive_harness_review.py", AH_MODES, "scheduled_harness_review")):
        for mode in modes:
            rc, out, err = run([PY, script, "--mode", mode, "--dry-run", "--no-home"])
            ok, ev = rc == 0, f"exit {rc}"
            if ok:
                try:
                    r = json.loads(out)
                    ok = (r["dry_run"] is True and r["mode"] == mode
                          and r["source"] == ("scheduled_runner" if mode == sched
                                              else ("ai_review" if "ai_review" in script
                                                    else "adaptive_harness")))
                    ev = f"json ok; source={r['source']}"
                except (json.JSONDecodeError, KeyError) as exc:
                    ok, ev = False, f"bad JSON: {exc}"
            row(f"dry-run {mode}", "runner-modes", ok, ev,
                f"python {script} --mode {mode} --dry-run --no-home")
    row("dry-run zero mutation (all modes above)", "dry-run-safety",
        git_state() == before,
        f"git status identical before/after {len(AI_MODES) + len(AH_MODES)} dry-runs")

    # 3. E2E data flow in a hermetic temp output
    with tempfile.TemporaryDirectory() as tmp:
        air_out = Path(tmp) / "ai-review"
        rc, out, err = run([PY, "scripts/run_ai_review.py", "--mode",
                            "harness_cleanup_review", "--no-home",
                            "--output", str(air_out)])
        latest = air_out / "latest.json"
        ok = rc == 0 and latest.is_file() and (air_out / "latest.md").is_file()
        row("AI-review real run writes latest.json+md", "data-flow", ok, f"exit {rc}")
        hist = air_out / "history" / "review-log.jsonl"
        row("AI-review history JSONL appended", "data-flow",
            hist.is_file() and len(hist.read_text(encoding='utf-8').splitlines()) == 1,
            "1 row after 1 run")
        # feed findings so linkage is testable
        finding = {
            "recommendation_id": "REC-20260706-900", "component_name": "e2e-probe",
            "component_type": "rule", "file_path": "X.md", "current_purpose": "p",
            "evidence_it_still_helps": "none found", "evidence_it_may_be_obsolete": "e",
            "recommendation": "Simplify", "expected_impact": "i",
            "risk_if_changed": "low", "suggested_test": "t", "confidence": "high",
            "priority": "P2", "source_review_id": "pending"}
        air_report = json.loads(latest.read_text(encoding="utf-8"))
        finding["source_review_id"] = air_report["review_id"]
        fpath = Path(tmp) / "f.json"
        fpath.write_text(json.dumps({"recommendations": [finding]}), encoding="utf-8")
        rc, out, err = run([PY, "scripts/run_ai_review.py", "--mode",
                            "harness_cleanup_review", "--no-home",
                            "--output", str(air_out), "--ingest", str(fpath)])
        row("AI-review ingest merges validated findings", "data-flow", rc == 0, f"exit {rc}")

        ah_out = Path(tmp) / "harness"
        rc, out, err = run([PY, "scripts/run_adaptive_harness_review.py", "--mode",
                            "ai_review_integration", "--no-home",
                            "--read-ai-review", str(latest), "--output", str(ah_out)])
        ah_latest = ah_out / "latest.json"
        ok = rc == 0 and ah_latest.is_file() and (ah_out / "latest.md").is_file()
        row("adaptive-harness reads AI-review + writes latest.json+md", "data-flow", ok, f"exit {rc}")
        if ok:
            ah_report = json.loads(ah_latest.read_text(encoding="utf-8"))
            row("shared schema: same required keys in both reports", "shared-schema",
                all(k in ah_report and k in air_report for k in
                    ("review_id", "source", "mode", "recommendations", "metrics",
                     "next_review_trigger", "unresolved_questions")),
                "review_report core keys present in both")
            row("adaptive-harness history JSONL appended", "data-flow",
                (ah_out / "history" / "review-log.jsonl").is_file(), "history exists")
        # linkage is on-demand now (REC-20260714-001): grep_history must find
        # the ingested REC in the AI-review history and report it OPEN (no
        # applies-commit exists for it in this repo's log).
        rc, out, err = run([PY, "scripts/grep_history.py", "--target", str(REPO),
                            "--history-dir", str(air_out / "history"),
                            "--rec", "REC-20260706-900"])
        row("grep_history finds the ingested REC across history", "data-flow",
            rc == 0 and "1 appearance(s)" in out and "status: OPEN" in out,
            out.strip().splitlines()[-1] if out.strip() else f"exit {rc}",
            "python scripts/grep_history.py --rec REC-20260706-900")

        # scheduled real runs: report-only (repo untouched, ledger untouched).
        # The ledger guard must not go vacuous when the ledger is absent
        # (fresh machine): existence-state must be unchanged either way.
        ledger = Path.home() / ".claude" / "audits" / "proposals.jsonl"
        ledger_existed = ledger.is_file()
        ledger_mtime = ledger.stat().st_mtime if ledger_existed else None
        pre = git_state()
        rc1, _, _ = run([PY, "scripts/run_ai_review.py", "--mode", "scheduled_review",
                         "--output", str(Path(tmp) / "s1")])
        rc2, _, _ = run([PY, "scripts/run_adaptive_harness_review.py", "--mode",
                         "scheduled_harness_review", "--output", str(Path(tmp) / "s2")])
        ok = rc1 == 0 and rc2 == 0 and git_state() == pre
        ok = ok and ledger.is_file() == ledger_existed
        if ledger_existed:
            ok = ok and ledger.stat().st_mtime == ledger_mtime
            ledger_ev = "proposals.jsonl mtime unchanged"
        else:
            ledger_ev = "proposals.jsonl absent before AND after (not created)"
        row("scheduled modes: report-only (repo + ledger untouched)", "scheduled-safety",
            ok, f"exit 0 both; tree unchanged; {ledger_ev}")

    # 4. Validators, probes, graph
    for name, cmd, layer in (
            ("check_agent_artifacts", [PY, "scripts/check_agent_artifacts.py"], "validators"),
            ("check_adaptive_harness (incl. posture)", [PY, "scripts/check_adaptive_harness.py"], "validators"),
            ("retrieval_probe", [PY, "validation/retrieval_probe.py"], "retrieval"),
            ("harness graph build (0 broken deps)", [PY, "scripts/build_harness_graph.py", "--dry-run"], "knowledge-graph")):
        rc, out, err = run(cmd)
        row(name, layer, rc == 0, (out + err).strip().splitlines()[-1] if (out or err) else f"exit {rc}",
            " ".join(c if c != PY else "python" for c in cmd))

    # 5. Test suites
    for suite in ("scripts/test_run_ai_review.py", "scripts/test_run_adaptive_harness_review.py",
                  "scripts/test_grep_history.py",
                  "scripts/test_build_harness_graph.py", "scripts/test_check_agent_artifacts.py",
                  "scripts/test_run_long_codex_ab.py",
                  "scripts/test_run_hermes_router_benchmark.py",
                  "scripts/test_runtime_activation_contract.py",
                  "scripts/test_run_runtime_activation_probe.py",
                  "scripts/test_check_codebase_memory_freshness.py"):
        rc, out, err = run([PY, suite])
        last = out.strip().splitlines()[-1] if out.strip() else err[:100]
        row(f"suite {suite}", "tests", rc == 0, last, f"python {suite}")

    # 6. Artifact presence inventory (Phase-3 section 1)
    for path in (".claude/skills/adaptive-harness/SKILL.md", "SKILL.md", "HERMES.md",
                 "docs/runtime_activation_contract.md",
                 "scripts/run_ai_review.py", "scripts/run_adaptive_harness_review.py",
                 "scripts/grep_history.py",
                 "scripts/run_long_codex_ab.py",
                 "scripts/run_runtime_activation_probe.py",
                 "scripts/test_runtime_activation_contract.py",
                 "scripts/test_run_runtime_activation_probe.py",
                 "scripts/check_codebase_memory_freshness.py",
                 "scripts/test_check_codebase_memory_freshness.py",
                 "schemas/review_report.schema.yaml", "schemas/recommendation.schema.yaml",
                 "benchmarks/ai_review_cases.yaml", "benchmarks/harness_cases.yaml",
                 "benchmarks/codebase_memory_freshness/cases.json",
                 "benchmarks/retrieval_cases.yaml", "docs/codex-delegation-policy.md",
                 "docs/ai_review_adaptive_harness_integration.md",
                 "docs/publication_status.md", "prompts/ai-review-modes.md"):
        row(f"exists {path}", "inventory", (REPO / path).is_file(), "on disk")
    # CI posture flipped 2026-07-14 (user-approved application of
    # fable_ultracode_phase_workspace/patches/github-actions-ci-proposal.md):
    # the sanctioned workflow is validate.yml ONLY, and it must pin the
    # token read-only. The invariant now asserts exactly that — any OTHER
    # workflow file, or a validate.yml without the read-only pin, fails.
    wf_dir = REPO / ".github" / "workflows"
    wf_files = sorted(p.name for p in wf_dir.glob("*.yml")) if wf_dir.is_dir() else []
    _v = REPO / ".github" / "workflows" / "validate.yml"
    _v_text = _v.read_text(encoding="utf-8") if _v.is_file() else ""
    ci_ok = (wf_files == ["validate.yml"]
             and "permissions:" in _v_text and "contents: read" in _v_text
             and "secrets." not in _v_text)
    row("CI is the single sanctioned read-only workflow (validate.yml, contents: read, no secrets)",
        "scheduled-safety", ci_ok,
        "workflows present: {} - read-only pin {}".format(
            wf_files or "none",
            "found" if "contents: read" in _v_text else "MISSING"))

    passed = sum(1 for r in ROWS if r["status"] == "PASS")
    if as_json:
        print(json.dumps({"rows": ROWS, "passed": passed, "total": len(ROWS)},
                         indent=1, ensure_ascii=False))
    else:
        print(f"\n{passed}/{len(ROWS)} checks PASS")
    return 0 if passed == len(ROWS) else 1


if __name__ == "__main__":
    sys.exit(main())
