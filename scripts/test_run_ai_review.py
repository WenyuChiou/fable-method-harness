#!/usr/bin/env python3
"""Tests for scripts/run_ai_review.py - the deterministic AI-review runner.

Pins the Phase-1 contract:
  - --help runs; every mode supports --dry-run producing schema-core-valid JSON;
  - --dry-run writes NOTHING (repo state hash-identical before/after);
  - normal runs write latest.json / latest.md / dated history / JSONL append;
  - scheduled_review reports source=scheduled_runner with empty changes_made
    (report-only doctrine carve-out);
  - --ingest validates findings against the recommendation contract and
    rejects bad enums with exit 1 (no silent merge, DR-011);
  - live fixtures: benchmark scaffold parses with >= 8 proposed cases, the
    mode-prompts doc covers all 7 modes, reports/ is gitignored.

Dual-runnable to honor the repo's no-pytest convention while staying
pytest-collectable:
    python scripts/test_run_ai_review.py   (standalone, exit 0/1)
    python -m pytest scripts/test_run_ai_review.py

Pure stdlib. Subprocess runs use --no-home so tests are hermetic (no
dependency on the operator's ~/.claude).
"""

import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RUNNER = REPO_ROOT / "scripts" / "run_ai_review.py"

_spec = importlib.util.spec_from_file_location("run_ai_review", RUNNER)
rar = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rar)


def run_runner(*argv, cwd=REPO_ROOT):
    return subprocess.run(
        [sys.executable, str(RUNNER)] + list(argv),
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(cwd), timeout=300)


def repo_state_snapshot():
    """Porcelain status + untracked list: the mutation-detection surface."""
    out = subprocess.run(["git", "status", "--porcelain"], capture_output=True,
                         text=True, cwd=str(REPO_ROOT), timeout=60)
    return out.stdout


def valid_recommendation(review_id="air-20260706-000000-standard_review"):
    return {
        "recommendation_id": "REC-20260706-001",
        "component_name": "example rule",
        "component_type": "rule",
        "file_path": "CLAUDE.md:1",
        "current_purpose": "example",
        "evidence_it_still_helps": "none found",
        "evidence_it_may_be_obsolete": "example evidence",
        "recommendation": "Simplify",
        "expected_impact": "smaller file",
        "risk_if_changed": "low",
        "suggested_test": "grep after edit",
        "confidence": "high",
        "priority": "P2",
        "source_review_id": review_id,
    }


# --------------------------------------------------------------------------
# CLI surface
# --------------------------------------------------------------------------

def test_help_runs():
    proc = run_runner("--help")
    assert proc.returncode == 0, proc.stderr
    assert "--dry-run" in proc.stdout and "--since-ref" in proc.stdout


def test_unknown_mode_rejected():
    proc = run_runner("--mode", "not_a_mode", "--dry-run")
    assert proc.returncode == 2, "argparse rejects bad choices with exit 2"


# --------------------------------------------------------------------------
# Dry-run: valid JSON per mode, and zero mutation
# --------------------------------------------------------------------------

def test_dry_run_modes_produce_valid_reports():
    for mode in ("harness_cleanup_review", "code_invocation_review",
                 "codex_delegation_review", "diff_review", "experiment_review",
                 "standard_review"):
        proc = run_runner("--mode", mode, "--dry-run", "--no-home")
        assert proc.returncode == 0, f"{mode}: {proc.stderr}"
        report = json.loads(proc.stdout)
        assert report["dry_run"] is True, mode
        assert report["mode"] == mode
        errors = rar.validate_report(report)
        assert not errors, f"{mode}: {errors}"
        # No semantic ingest -> the honest UNSCORED marker must be present.
        assert any("not executed" in q for q in report["unresolved_questions"]), mode


def test_dry_run_does_not_mutate_repo():
    before = repo_state_snapshot()
    proc = run_runner("--mode", "harness_cleanup_review", "--dry-run", "--no-home")
    assert proc.returncode == 0, proc.stderr
    after = repo_state_snapshot()
    assert before == after, "dry-run changed the repo state"


def test_scheduled_review_is_report_only():
    proc = run_runner("--mode", "scheduled_review", "--dry-run", "--no-home")
    assert proc.returncode == 0, proc.stderr
    report = json.loads(proc.stdout)
    assert report["source"] == "scheduled_runner"
    assert report["changes_made"] == [], "scheduled runner must never record applied changes"


# --------------------------------------------------------------------------
# Writing: latest + dated history + JSONL append
# --------------------------------------------------------------------------

def test_write_outputs_and_history_append():
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "ai-review"
        for _ in range(2):
            proc = run_runner("--mode", "code_invocation_review", "--no-home",
                              "--output", str(out))
            assert proc.returncode == 0, proc.stderr
        assert (out / "latest.json").is_file()
        assert (out / "latest.md").is_file()
        history = out / "history"
        log_lines = (history / "review-log.jsonl").read_text(encoding="utf-8").strip().splitlines()
        assert len(log_lines) == 2, "one JSONL row per run"
        for line in log_lines:
            row = json.loads(line)
            assert row["mode"] == "code_invocation_review"
        dated_json = list(history.glob("*-ai-review.json"))
        assert dated_json, "dated history report missing"
        latest = json.loads((out / "latest.json").read_text(encoding="utf-8"))
        assert not rar.validate_report(latest)
        md = (out / "latest.md").read_text(encoding="utf-8")
        assert latest["review_id"] in md, "MD twin must reference the same review_id"


# --------------------------------------------------------------------------
# Ingest contract
# --------------------------------------------------------------------------

def test_ingest_valid_merges_recommendations():
    with tempfile.TemporaryDirectory() as tmp:
        findings = Path(tmp) / "findings.json"
        findings.write_text(json.dumps({
            "recommendations": [valid_recommendation()],
        }), encoding="utf-8")
        proc = run_runner("--mode", "standard_review", "--dry-run", "--no-home",
                          "--ingest", str(findings))
        assert proc.returncode == 0, proc.stderr
        report = json.loads(proc.stdout)
        assert len(report["recommendations"]) == 1
        assert report["recommendations"][0]["recommendation_id"] == "REC-20260706-001"


def test_ingest_invalid_enum_rejected():
    with tempfile.TemporaryDirectory() as tmp:
        bad = valid_recommendation()
        bad["recommendation"] = "Nuke"          # not in enum
        bad.pop("suggested_test")               # missing required field
        findings = Path(tmp) / "findings.json"
        findings.write_text(json.dumps({"recommendations": [bad]}), encoding="utf-8")
        proc = run_runner("--mode", "standard_review", "--dry-run", "--no-home",
                          "--ingest", str(findings))
        assert proc.returncode == 1
        assert "failed validation" in proc.stderr
        assert "Nuke" in proc.stderr and "suggested_test" in proc.stderr


def test_validate_report_catches_missing_field():
    report = {"review_id": "x"}
    errors = rar.validate_report(report)
    assert any("mode" in e for e in errors)
    assert any("metrics" in e for e in errors)


def test_ingest_issues_found_validated():
    """Review finding (2026-07-06 pair, blocking): issues_found was an
    unvalidated ingest side door - malformed entries crashed the writer."""
    with tempfile.TemporaryDirectory() as tmp:
        findings = Path(tmp) / "bad_issues.json"
        findings.write_text(json.dumps({"issues_found": [{"foo": "bar"}]}), encoding="utf-8")
        proc = run_runner("--mode", "code_invocation_review", "--dry-run", "--no-home",
                          "--ingest", str(findings))
        assert proc.returncode == 1, "malformed issues_found must be rejected"
        assert "issues_found[0]" in proc.stderr
        good = Path(tmp) / "good_issues.json"
        good.write_text(json.dumps({"issues_found": [
            {"id": "LLM-001", "severity": "P2", "category": "manual",
             "description": "example", "source": "ingest"}]}), encoding="utf-8")
        proc2 = run_runner("--mode", "code_invocation_review", "--dry-run", "--no-home",
                           "--ingest", str(good))
        assert proc2.returncode == 0, proc2.stderr
        report = json.loads(proc2.stdout)
        assert any(i["id"] == "LLM-001" for i in report["issues_found"])


def test_scheduled_review_rejects_ingest():
    """Review finding: report-only invariant must be code, not prose."""
    with tempfile.TemporaryDirectory() as tmp:
        findings = Path(tmp) / "f.json"
        findings.write_text(json.dumps({"changes_made": ["should never land"]}), encoding="utf-8")
        proc = run_runner("--mode", "scheduled_review", "--dry-run", "--no-home",
                          "--ingest", str(findings))
        assert proc.returncode == 1
        assert "scheduled_review" in proc.stderr


def test_experiment_review_merges_ingested_cases():
    """Review finding: ingested experiments were silently dropped whenever
    the benchmark collector found cases."""
    with tempfile.TemporaryDirectory() as tmp:
        findings = Path(tmp) / "exp.json"
        findings.write_text(json.dumps({"experiments_proposed": [
            {"case_name": "brand_new_ingested_case", "status": "proposed",
             "linked_recommendation_id": "REC-20260706-099"}]}), encoding="utf-8")
        proc = run_runner("--mode", "experiment_review", "--dry-run", "--no-home",
                          "--ingest", str(findings))
        assert proc.returncode == 0, proc.stderr
        report = json.loads(proc.stdout)
        names = [c.get("case_name") for c in report["experiments_proposed"]]
        assert "brand_new_ingested_case" in names, "validated ingest must never be silently dropped"
        assert len(names) >= 9, "benchmark-file cases must also survive the merge"


def test_partial_ingest_marks_remaining_sections_unscored():
    """Review finding: UNSCORED marking was all-or-nothing; one filled section
    silently 'passed' the others."""
    with tempfile.TemporaryDirectory() as tmp:
        findings = Path(tmp) / "partial.json"
        findings.write_text(json.dumps({"recommendations": [valid_recommendation()]}),
                            encoding="utf-8")
        proc = run_runner("--mode", "harness_cleanup_review", "--dry-run", "--no-home",
                          "--ingest", str(findings))
        assert proc.returncode == 0, proc.stderr
        report = json.loads(proc.stdout)
        marker = [q for q in report["unresolved_questions"] if "not executed" in q]
        assert marker, "empty semantic sections must stay marked UNSCORED"
        assert "inefficient_invocations" in marker[0]
        assert "recommendations" not in marker[0], "filled section must not be listed as unscored"


def test_high_risk_remove_requires_approval_flag():
    """Review finding: Remove/Replace on hook/subagent/prompt/command/skill
    must carry requires_human_approval: true."""
    bad = valid_recommendation()
    bad["recommendation"] = "Remove"
    bad["component_type"] = "hook"
    errors = []
    rar.validate_recommendation(bad, errors, "t")
    assert any("requires_human_approval" in e for e in errors)
    bad["requires_human_approval"] = True
    errors2 = []
    rar.validate_recommendation(bad, errors2, "t")
    assert not errors2, errors2


def test_recommendation_id_pattern_enforced():
    bad = valid_recommendation()
    bad["recommendation_id"] = "not-a-rec-id"
    errors = []
    rar.validate_recommendation(bad, errors, "t")
    assert any("REC-YYYYMMDD-NNN" in e for e in errors)


def test_unquote_git_path_cjk_and_spaces():
    """Review finding: git C-quoted paths (CJK octal escapes) were mangled."""
    quoted = '"prompts/\\344\\270\\255\\346\\226\\207.md"'
    assert rar.unquote_git_path(quoted) == "prompts/中文.md"
    assert rar.unquote_git_path("plain/path.md") == "plain/path.md"
    assert rar.unquote_git_path('"a\\"b.md"') == 'a"b.md'


def test_collect_diff_handles_cjk_filenames():
    """End-to-end: a fixture repo with a CJK filename survives collect_diff."""
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        def g(*args):
            return subprocess.run(["git"] + list(args), cwd=str(repo),
                                  capture_output=True, text=True, encoding="utf-8")
        if g("init").returncode != 0:
            print("ok (skipped: git init unavailable)")
            return
        g("config", "user.email", "t@t"); g("config", "user.name", "t")
        cjk = repo / "中文檔案.md"
        cjk.write_text("v1", encoding="utf-8")
        g("add", "-A"); g("commit", "-m", "seed")
        cjk.write_text("v2", encoding="utf-8")
        diff = rar.collect_diff(repo, "HEAD")
        assert diff["status"] == "ok", diff
        paths = [c["path"] for c in diff["changed"]]
        assert "中文檔案.md" in paths, paths


# --------------------------------------------------------------------------
# Live fixtures (assert the Phase-1 artifacts stay wired)
# --------------------------------------------------------------------------

def test_benchmark_scaffold_parses_with_cases():
    bench = REPO_ROOT / "benchmarks" / "ai_review_cases.yaml"
    assert bench.is_file(), "benchmarks/ai_review_cases.yaml missing"
    cases = rar.parse_benchmark_cases(bench.read_text(encoding="utf-8"),
                                      "benchmarks/ai_review_cases.yaml")
    assert len(cases) >= 8, f"expected >=8 benchmark cases, got {len(cases)}"
    for c in cases:
        assert c.get("status") in rar.EXPERIMENT_STATUS_ENUM, c
        assert "variant_a" in c and "variant_b" in c, c
        assert "linked_recommendation_id" in c, c


def test_mode_prompts_doc_covers_all_modes():
    doc = REPO_ROOT / "prompts" / "ai-review-modes.md"
    assert doc.is_file(), "prompts/ai-review-modes.md missing"
    text = doc.read_text(encoding="utf-8")
    for mode in rar.MODES:
        assert mode in text, f"mode '{mode}' missing from ai-review-modes.md"


def test_codex_policy_doc_exists():
    assert (REPO_ROOT / "docs" / "codex-delegation-policy.md").is_file()


def test_reports_dir_is_gitignored():
    gitignore = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "reports/" in gitignore, "reports/ must be gitignored (generated + private telemetry)"


TESTS = [v for k, v in sorted(globals().items()) if k.startswith("test_")]


def main():
    passed = failed = 0
    for fn in TESTS:
        try:
            fn()
            print("ok {}".format(fn.__name__))
            passed += 1
        except AssertionError as exc:
            print("FAIL {}: {}".format(fn.__name__, exc))
            failed += 1
        except Exception as exc:  # noqa: BLE001 - a crash is a failure, reported not raised
            print("FAIL {} (error): {!r}".format(fn.__name__, exc))
            failed += 1
    print("{} passed, {} failed".format(passed, failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
