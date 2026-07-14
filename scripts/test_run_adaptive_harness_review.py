#!/usr/bin/env python3
"""Tests for scripts/run_adaptive_harness_review.py + check_adaptive_harness.py.

Pins the contract:
  - every mode dry-runs to schema-core-valid JSON; dry-run writes nothing;
  - scheduled_harness_review is report-only (source=scheduled_runner,
    --ingest rejected);
  - patch_proposal renders an apply/rollback sheet and applies nothing;
  - the tier-0 validator passes on this repo and catches posture regressions.

Cross-run linkage tests moved to scripts/test_grep_history.py when the
rolling loop's state machinery was retired (applies REC-20260714-001; the
closure-verb convention itself is still pinned - there, not here).

Dual-runnable (repo convention):
    python scripts/test_run_adaptive_harness_review.py   (standalone, exit 0/1)
    python -m pytest scripts/test_run_adaptive_harness_review.py
"""

import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RUNNER = REPO_ROOT / "scripts" / "run_adaptive_harness_review.py"
VALIDATOR = REPO_ROOT / "scripts" / "check_adaptive_harness.py"

_spec = importlib.util.spec_from_file_location("run_adaptive_harness_review", RUNNER)
ahr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ahr)


def run_runner(*argv):
    return subprocess.run(
        [sys.executable, str(RUNNER)] + list(argv),
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(REPO_ROOT), timeout=300)


def make_ai_review_fixture(tmp, recs):
    """A minimal AI-review latest.json + history the runner can read."""
    out = Path(tmp) / "ai-review"
    (out / "history").mkdir(parents=True)
    report = {
        "review_id": "air-20260706-000000-harness_cleanup_review",
        "review_date": "2026-07-06T00:00:00+00:00",
        "source": "ai_review", "mode": "harness_cleanup_review",
        "files_inspected": [], "components_inspected": {},
        "issues_found": [], "obsolete_scaffolding": [],
        "inefficient_invocations": [], "recommendations": recs,
        "experiments_proposed": [], "changes_made": [],
        "unresolved_questions": [], "metrics": {}, "next_review_trigger": "n/a",
    }
    (out / "latest.json").write_text(json.dumps(report), encoding="utf-8")
    (out / "history" / "review-log.jsonl").write_text(
        json.dumps({"review_id": report["review_id"]}) + "\n", encoding="utf-8")
    return out / "latest.json"


def rec(n, name="component"):
    return {
        "recommendation_id": f"REC-20260706-{n:03d}",
        "component_name": name, "component_type": "rule", "file_path": "X.md",
        "current_purpose": "p", "evidence_it_still_helps": "none found",
        "evidence_it_may_be_obsolete": "e", "recommendation": "Simplify",
        "expected_impact": "i", "risk_if_changed": "low",
        "suggested_test": "t", "confidence": "high", "priority": "P2",
        "source_review_id": "air-20260706-000000-harness_cleanup_review",
    }


# --------------------------------------------------------------------------

def test_help_runs():
    proc = run_runner("--help")
    assert proc.returncode == 0, proc.stderr
    assert "--read-ai-review" in proc.stdout


def test_rolling_mode_is_retired():
    """applies REC-20260714-001: the mode must be gone from the CLI surface,
    and the retirement must cite the REC + the replacement helper."""
    assert "rolling_improvement_review" not in ahr.MODES
    proc = run_runner("--mode", "rolling_improvement_review", "--dry-run", "--no-home")
    assert proc.returncode == 2, "argparse must reject the retired mode"
    doc = RUNNER.read_text(encoding="utf-8")
    assert "REC-20260714-001" in doc and "grep_history.py" in doc


def test_all_modes_dry_run_valid():
    for mode in sorted(ahr.MODES):
        proc = run_runner("--mode", mode, "--dry-run", "--no-home")
        assert proc.returncode == 0, f"{mode}: {proc.stderr}"
        report = json.loads(proc.stdout)
        assert report["mode"] == mode
        assert report["dry_run"] is True
        expected_source = "scheduled_runner" if mode == "scheduled_harness_review" else "adaptive_harness"
        assert report["source"] == expected_source, mode


def test_dry_run_does_not_mutate_repo():
    before = subprocess.run(["git", "status", "--porcelain"], capture_output=True,
                            text=True, cwd=str(REPO_ROOT), timeout=60).stdout
    proc = run_runner("--mode", "scheduled_harness_review", "--dry-run", "--no-home")
    assert proc.returncode == 0, proc.stderr
    after = subprocess.run(["git", "status", "--porcelain"], capture_output=True,
                           text=True, cwd=str(REPO_ROOT), timeout=60).stdout
    assert before == after


def test_scheduled_rejects_ingest():
    with tempfile.TemporaryDirectory() as tmp:
        f = Path(tmp) / "f.json"
        f.write_text("{}", encoding="utf-8")
        proc = run_runner("--mode", "scheduled_harness_review", "--dry-run",
                          "--no-home", "--ingest", str(f))
        assert proc.returncode == 1
        assert "report-only" in proc.stderr


def test_history_stem_no_same_second_collision():
    """Review finding (2026-07-06 pair): two same-second runs of different
    modes must not overwrite each other's dated history files."""
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "harness"
        for mode in ("harness_inventory", "skill_fit_review", "experiment_design"):
            proc = run_runner("--mode", mode, "--no-home", "--output", str(out))
            assert proc.returncode == 0, proc.stderr
        history_json = list((out / "history").glob("*.json"))
        log_lines = (out / "history" / "review-log.jsonl").read_text(encoding="utf-8").strip().splitlines()
        assert len(history_json) == len(log_lines) == 3, \
            f"every run must keep its own history file: {len(history_json)} files vs {len(log_lines)} log rows"


def test_patch_proposal_renders_high_risk_only():
    with tempfile.TemporaryDirectory() as tmp:
        high = rec(104, "dangerous-hook")
        high.update({"recommendation": "Remove", "component_type": "hook",
                     "priority": "P0", "requires_human_approval": True})
        low = rec(105, "minor-wording")
        latest = make_ai_review_fixture(tmp, [high, low])
        out = Path(tmp) / "harness"
        proc = run_runner("--mode", "patch_proposal", "--no-home",
                          "--read-ai-review", str(latest), "--output", str(out))
        assert proc.returncode == 0, proc.stderr
        proposals = list((out / "proposals").glob("PATCH-PROPOSALS-*.md"))
        assert len(proposals) == 1
        text = proposals[0].read_text(encoding="utf-8")
        assert "REC-20260706-104" in text and "rollback" in text
        assert "REC-20260706-105" not in text, "low-risk items do not become patch proposals"


def test_patch_proposal_still_reads_legacy_rolling_state():
    """The retired loop's last rolling_state.json is READ (never written) so
    its pending high-risk items cannot vanish from proposal sheets."""
    with tempfile.TemporaryDirectory() as tmp:
        latest = make_ai_review_fixture(tmp, [])
        out = Path(tmp) / "harness"
        out.mkdir()
        legacy = rec(106, "legacy-pending-hook")
        legacy.update({"recommendation": "Remove", "component_type": "hook",
                       "priority": "P0", "requires_human_approval": True})
        state = out / "rolling_state.json"
        state.write_text(json.dumps({"recommendations": [legacy]}), encoding="utf-8")
        state_bytes = state.read_bytes()
        proc = run_runner("--mode", "patch_proposal", "--no-home",
                          "--read-ai-review", str(latest), "--output", str(out))
        assert proc.returncode == 0, proc.stderr
        proposals = list((out / "proposals").glob("PATCH-PROPOSALS-*.md"))
        assert len(proposals) == 1
        assert "REC-20260706-106" in proposals[0].read_text(encoding="utf-8")
        assert state.read_bytes() == state_bytes, "legacy state must never be rewritten"


def test_render_patch_proposals_empty():
    md = ahr.render_patch_proposals([], "ahr-test")
    assert "No high-risk recommendations pending" in md


def test_integration_wiring_collector_all_present():
    result = ahr.collect_integration_wiring({"target": REPO_ROOT})
    assert result["missing"] == [], result
    assert result["root_skill_documents_adapter"] is True


def test_validator_passes_on_repo():
    proc = subprocess.run([sys.executable, str(VALIDATOR)], capture_output=True,
                          text=True, encoding="utf-8", cwd=str(REPO_ROOT), timeout=120)
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_validator_catches_posture_regression():
    spec = importlib.util.spec_from_file_location("check_adaptive_harness", VALIDATOR)
    cah = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cah)
    assert "stays private" in cah.FORBIDDEN_POSTURE
    assert any("publication_status" in p for p in cah.REQUIRED)


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
