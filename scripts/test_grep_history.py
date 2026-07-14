#!/usr/bin/env python3
"""Tests for scripts/grep_history.py - the rolling loop's replacement
(applies REC-20260714-001).

Pins the linkage semantics that moved here from the retired state machinery:
  - a commit closes a REC only via the application verb in its subject
    ('applies REC-...' / 'resolves REC-...') or a Harness-Outcome trailer;
  - a bare mention NEVER closes;
  - a later 'reverts REC-...' or reopened trailer restores OPEN;
  - --repeats derives recurrence from the append-only history alone;
  - --open lists the newest report's unclosed REC ids;
  - the script is read-only (no files created or modified anywhere it scans).

Dual-runnable (repo convention):
    python scripts/test_grep_history.py
    python -m pytest scripts/test_grep_history.py
"""

import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "grep_history.py"

_spec = importlib.util.spec_from_file_location("grep_history", SCRIPT)
gh = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gh)


def run_script(*argv, cwd=None):
    return subprocess.run(
        [sys.executable, str(SCRIPT)] + list(argv),
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(cwd or REPO_ROOT), timeout=120)


def git(repo, *argv):
    proc = subprocess.run(["git"] + list(argv), cwd=str(repo),
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=60)
    assert proc.returncode == 0, f"git {argv}: {proc.stderr}"
    return proc.stdout


def make_repo_with_history(tmp):
    """A throwaway git repo with two history reports and closure commits."""
    repo = Path(tmp) / "repo"
    hist = repo / "reports" / "harness" / "history"
    hist.mkdir(parents=True)
    git(repo, "init", "-q")
    git(repo, "config", "user.email", "t@t")
    git(repo, "config", "user.name", "t")

    def report(name, date, rec_ids):
        (hist / name).write_text(json.dumps({
            "review_id": f"ahr-{name}", "review_date": date,
            "mode": "scheduled_harness_review",
            "recommendations": [{"recommendation_id": r} for r in rec_ids],
        }), encoding="utf-8")

    report("r1.json", "2026-07-01T00:00:00+00:00",
           ["REC-20260701-001", "REC-20260701-002", "REC-20260701-003"])
    report("r2.json", "2026-07-08T00:00:00+00:00",
           ["REC-20260701-001", "REC-20260701-002", "REC-20260701-004"])

    (repo / "a.txt").write_text("1", encoding="utf-8")
    git(repo, "add", "a.txt")
    git(repo, "commit", "-qm", "applies REC-20260701-001")
    (repo / "b.txt").write_text("2", encoding="utf-8")
    git(repo, "add", "b.txt")
    # bare mention - must NOT close
    git(repo, "commit", "-qm", "docs: discuss REC-20260701-002 without applying it")
    (repo / "c.txt").write_text("3", encoding="utf-8")
    git(repo, "add", "c.txt")
    git(repo, "commit", "-qm", "fix: unrelated",
        "-m", "Harness-Outcome: REC-20260701-004 validated; evidence=c.txt")
    return repo


def snapshot(root):
    return sorted((p.as_posix(), p.stat().st_mtime_ns)
                  for p in Path(root).rglob("*") if p.is_file())


# --------------------------------------------------------------------------

def test_application_verb_closes():
    with tempfile.TemporaryDirectory() as tmp:
        repo = make_repo_with_history(tmp)
        proc = run_script("--target", str(repo), "--rec", "REC-20260701-001")
        assert proc.returncode == 0, proc.stderr
        assert "status: CLOSED" in proc.stdout
        assert "2 appearance(s)" in proc.stdout


def test_bare_mention_does_not_close():
    with tempfile.TemporaryDirectory() as tmp:
        repo = make_repo_with_history(tmp)
        proc = run_script("--target", str(repo), "--rec", "REC-20260701-002")
        assert proc.returncode == 0, proc.stderr
        assert "status: OPEN" in proc.stdout


def test_outcome_trailer_closes():
    with tempfile.TemporaryDirectory() as tmp:
        repo = make_repo_with_history(tmp)
        proc = run_script("--target", str(repo), "--rec", "REC-20260701-004")
        assert proc.returncode == 0, proc.stderr
        assert "status: CLOSED" in proc.stdout


def test_revert_reopens():
    with tempfile.TemporaryDirectory() as tmp:
        repo = make_repo_with_history(tmp)
        (repo / "d.txt").write_text("4", encoding="utf-8")
        git(repo, "add", "d.txt")
        git(repo, "commit", "-qm", "reverts REC-20260701-001")
        proc = run_script("--target", str(repo), "--rec", "REC-20260701-001")
        assert proc.returncode == 0, proc.stderr
        assert "status: OPEN" in proc.stdout


def test_repeats_lists_recurring_ids_only():
    with tempfile.TemporaryDirectory() as tmp:
        repo = make_repo_with_history(tmp)
        proc = run_script("--target", str(repo), "--repeats")
        assert proc.returncode == 0, proc.stderr
        assert "REC-20260701-001" in proc.stdout
        assert "REC-20260701-002" in proc.stdout
        assert "REC-20260701-003" not in proc.stdout, "single-appearance id is not a repeat"
        assert "REC-20260701-004" not in proc.stdout


def test_open_lists_unclosed_from_newest_report():
    with tempfile.TemporaryDirectory() as tmp:
        repo = make_repo_with_history(tmp)
        proc = run_script("--target", str(repo), "--open")
        assert proc.returncode == 0, proc.stderr
        assert "OPEN REC-20260701-002" in proc.stdout
        assert "OPEN REC-20260701-001" not in proc.stdout, "closed by applies-verb"
        assert "OPEN REC-20260701-004" not in proc.stdout, "closed by trailer"
        assert "REC-20260701-003" not in proc.stdout, "not in the newest report"


def test_read_only():
    with tempfile.TemporaryDirectory() as tmp:
        repo = make_repo_with_history(tmp)
        before = snapshot(repo / "reports")
        for argv in (["--rec", "REC-20260701-001"], ["--repeats"], ["--open"]):
            proc = run_script("--target", str(repo), *argv)
            assert proc.returncode == 0, proc.stderr
        assert snapshot(repo / "reports") == before


def test_rejects_malformed_rec_id():
    proc = run_script("--rec", "REC-BOGUS")
    assert proc.returncode == 2
    assert "not a REC id" in proc.stderr


def test_runs_on_this_repo():
    """Smoke on the real repo: the executed round-4 case's REC must resolve
    (whether OPEN or CLOSED depends on repo state - only the query must work)."""
    proc = run_script("--rec", "REC-20260706-034")
    assert proc.returncode == 0, proc.stderr
    assert "status:" in proc.stdout


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
