#!/usr/bin/env python3
"""Pure-stdlib regression tests for the codebase-memory freshness sentinel."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import tempfile
from pathlib import Path


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location(
    "freshness", HERE / "check_codebase_memory_freshness.py")
freshness = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(freshness)


def probe(expected_present=True):
    return {
        "id": "p1", "symbol": "target", "file": "sample.py",
        "expected_present": expected_present,
    }


def local(source="def target():\n    return 1", start=1, end=2, present=True):
    if not present:
        return {"present": False, "file": "sample.py"}
    return {
        "present": True, "file": "sample.py", "start_line": start,
        "end_line": end, "source_sha256": freshness.source_hash(source),
        "source": freshness.normalize_source(source),
    }


def match():
    return {
        "name": "target", "file_path": "sample.py",
        "qualified_name": "project.sample.target",
    }


def snippet(source="def target():\n    return 1", start=1, end=2):
    return {
        "name": "target", "file_path": "sample.py",
        "start_line": start, "end_line": end, "source": source,
    }


def test_missing_symbol_is_stale():
    result = freshness.evaluate_probe(Path.cwd(), probe(), local(), [], None)
    assert result["state"] == freshness.STALE
    assert result["reasons"] == ["symbol_missing_from_graph"]


def test_misaligned_source_is_stale():
    result = freshness.evaluate_probe(
        Path.cwd(), probe(), local(), [match()],
        snippet("def other():\n    return 2", 8, 9))
    assert result["state"] == freshness.STALE
    assert "line_span_mismatch" in result["reasons"]
    assert "source_mismatch" in result["reasons"]


def test_deleted_symbol_ghost_is_stale():
    result = freshness.evaluate_probe(
        Path.cwd(), probe(False), local(present=False), [match()], None)
    assert result["state"] == freshness.STALE
    assert result["reasons"] == ["deleted_symbol_still_in_graph"]


def test_exact_fixture_is_fresh():
    result = freshness.evaluate_probe(
        Path.cwd(), probe(), local(), [match()], snippet())
    assert result["state"] == freshness.FRESH
    assert not result["reasons"]


def test_nonzero_and_malformed_cli_are_unscored_failures():
    for returncode, stdout, expected in (
            (1, "{}", "search_graph_nonzero_exit"),
            (0, "not-json", "search_graph_malformed_json")):
        try:
            freshness.decode_cli_result("search_graph", returncode, stdout, "diagnostic")
        except freshness.CliFailure as exc:
            assert exc.reason == expected
        else:
            raise AssertionError("invalid CLI response did not fail closed")


def test_grouping_rejects_truncated_search():
    try:
        freshness.graph_results_by_probe(Path.cwd(), [probe()], {
            "total": 2, "results": [match()], "has_more": True,
        })
    except freshness.CliFailure as exc:
        assert exc.reason == "search_graph_truncated"
    else:
        raise AssertionError("truncated graph search did not fail closed")


def test_local_symbol_and_path_containment():
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        (repo / "sample.py").write_text(
            "def target():\n    return 1\n", encoding="utf-8")
        found = freshness.local_symbol(repo, probe())
        assert found["start_line"] == 1 and found["end_line"] == 2
        escaped = dict(probe(), file="../outside.py")
        try:
            freshness.local_symbol(repo, escaped)
        except ValueError as exc:
            assert "relative" in str(exc) or "escapes" in str(exc)
        else:
            raise AssertionError("path escape was accepted")


def test_decorator_is_inside_local_span_and_hash():
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        file_path = repo / "sample.py"
        file_path.write_text(
            "@policy('old')\ndef target():\n    return 1\n", encoding="utf-8")
        before = freshness.local_symbol(repo, probe())
        assert before["start_line"] == 1 and before["end_line"] == 3
        file_path.write_text(
            "@policy('new')\ndef target():\n    return 1\n", encoding="utf-8")
        after = freshness.local_symbol(repo, probe())
        assert before["source_sha256"] != after["source_sha256"]


def test_input_provenance_requires_clean_committed_files():
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        tracked = repo / "tracked.py"
        tracked.write_text("x = 1\n", encoding="utf-8")
        subprocess.run(["git", "init"], cwd=repo, capture_output=True)
        subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=repo)
        subprocess.run(["git", "config", "user.name", "t"], cwd=repo)
        subprocess.run(["git", "add", "tracked.py"], cwd=repo)
        subprocess.run(["git", "commit", "-m", "fixture"], cwd=repo, capture_output=True)
        clean = freshness.input_provenance(repo, [tracked])[0]
        assert clean["tracked_at_head"] is True
        tracked.write_text("x = 2\n", encoding="utf-8")
        dirty = freshness.input_provenance(repo, [tracked])[0]
        assert dirty["tracked_at_head"] is False


def test_run_once_aggregates_fresh_fixture():
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        (repo / "sample.py").write_text(
            "def target():\n    return 1\n", encoding="utf-8")

        def fake_invoke(cli, tool, payload, timeout):
            if tool == "index_status":
                return {"status": "ready", "nodes": 1, "edges": 0}
            if tool == "search_graph":
                return {"total": 1, "results": [match()], "has_more": False}
            if tool == "get_code_snippet":
                return snippet()
            raise AssertionError(tool)

        result = freshness.run_once(
            repo, "project", [probe()], "ignored", 1, invoke=fake_invoke)
        assert result["status"] == freshness.FRESH
        assert result["probes"][0]["state"] == freshness.FRESH


def test_missing_cli_writes_unscored_canonical_json():
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        (repo / "sample.py").write_text(
            "def target():\n    return 1\n", encoding="utf-8")
        subprocess.run(["git", "init"], cwd=repo, capture_output=True)
        subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=repo)
        subprocess.run(["git", "config", "user.name", "t"], cwd=repo)
        subprocess.run(["git", "add", "sample.py"], cwd=repo)
        subprocess.run(["git", "commit", "-m", "fixture"], cwd=repo, capture_output=True)
        cases = repo / "cases.json"
        cases.write_text(json.dumps({"schema_version": 1, "probes": [probe()]}), encoding="utf-8")
        output = repo / "evals" / "codebase_memory_freshness" / "scorecard.json"
        rc = freshness.main([
            "--repo", str(repo), "--cases", str(cases),
            "--cli", "definitely-missing-codebase-memory-cli", "--output", str(output),
        ])
        assert rc == 2 and output.is_file()
        payload = json.loads(output.read_text(encoding="utf-8"))
        assert payload["status"] == freshness.UNSCORED
        assert payload["fallback_required"] is True
        assert payload["failure"]["reason"] == "cli_not_found"


def test_main_cli_failures_write_canonical_unscored():
    for reason in ("search_graph_malformed_json", "search_graph_timeout"):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            (repo / "sample.py").write_text(
                "def target():\n    return 1\n", encoding="utf-8")
            subprocess.run(["git", "init"], cwd=repo, capture_output=True)
            subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=repo)
            subprocess.run(["git", "config", "user.name", "t"], cwd=repo)
            cases = repo / "cases.json"
            cases.write_text(json.dumps({"schema_version": 1, "probes": [probe()]}), encoding="utf-8")
            subprocess.run(["git", "add", "sample.py", "cases.json"], cwd=repo)
            subprocess.run(["git", "commit", "-m", "fixture"], cwd=repo, capture_output=True)
            output = repo / "evals" / "codebase_memory_freshness" / (reason + ".json")

            def failing_invoke(cli, tool, payload, timeout):
                if tool == "index_status":
                    return {"status": "ready", "nodes": 1, "edges": 0}
                raise freshness.CliFailure(reason, "injected regression fixture")

            rc = freshness.main(
                ["--repo", str(repo), "--cases", str(cases), "--output", str(output)],
                invoke=failing_invoke, version_reader=lambda cli, timeout: "fixture 1.0")
            payload = json.loads(output.read_text(encoding="utf-8"))
            assert rc == 2 and payload["status"] == freshness.UNSCORED
            assert payload["failure"]["reason"] == reason
            assert payload["fallback_required"] is True


def test_output_must_stay_inside_repo():
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        repo.mkdir()
        source = repo / "sample.py"
        cases = repo / "cases.json"
        source.write_text("x = 1\n", encoding="utf-8")
        cases.write_text("{}\n", encoding="utf-8")
        before = {path: path.read_bytes() for path in (source, cases)}
        allowed_root = repo / "evals" / "codebase_memory_freshness"
        for forbidden in (Path(tmp) / "outside.json", source, cases, allowed_root):
            try:
                freshness.write_scorecard(forbidden, repo, {"status": "x"})
            except ValueError as exc:
                assert "codebase_memory_freshness" in str(exc)
            else:
                raise AssertionError("forbidden output path was accepted: {}".format(forbidden))
        assert all(path.read_bytes() == content for path, content in before.items())
        assert not (repo / "evals" / "codebase_memory_freshness.tmp").exists()


def test_preexisting_predictable_temp_link_cannot_touch_source():
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        source = repo / "source.py"
        source.write_text("sentinel = 'unchanged'\n", encoding="utf-8")
        before = source.read_bytes()
        allowed = repo / "evals" / "codebase_memory_freshness"
        allowed.mkdir(parents=True)
        output = allowed / "safe.json"
        old_predictable_temp = allowed / "safe.json.tmp"
        try:
            old_predictable_temp.symlink_to(source)
        except OSError:
            os.link(source, old_predictable_temp)
        freshness.write_scorecard(output, repo, {"status": "STALE"})
        assert source.read_bytes() == before
        assert json.loads(output.read_text(encoding="utf-8"))["status"] == "STALE"


def test_help_runs():
    proc = subprocess.run(
        ["python", str(HERE / "check_codebase_memory_freshness.py"), "--help"],
        capture_output=True, text=True, encoding="utf-8")
    assert proc.returncode == 0, proc.stderr


def main():
    tests = [
        value for name, value in sorted(globals().items())
        if name.startswith("test_") and callable(value)]
    failures = 0
    for test in tests:
        try:
            test()
            print("ok {}".format(test.__name__))
        except Exception as exc:
            failures += 1
            print("FAIL {}: {}".format(test.__name__, exc))
    print("{} passed, {} failed".format(len(tests) - failures, failures))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
