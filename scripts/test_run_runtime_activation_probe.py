#!/usr/bin/env python3
"""Regression tests for the fail-closed runtime activation probe."""

import importlib.util
import hashlib
import json
import sqlite3
import sys
import tempfile
from pathlib import Path
from unittest import mock


REPO = Path(__file__).resolve().parent.parent
RUNNER = REPO / "scripts" / "run_runtime_activation_probe.py"
PREREGISTRATION = REPO / "benchmarks" / "runtime_activation" / "preregistration.json"
spec = importlib.util.spec_from_file_location("runtime_activation_probe", RUNNER)
runner = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = runner
spec.loader.exec_module(runner)


def test_fixture_is_complete_and_valid():
    cases = runner.load_cases()
    assert len(cases) == 7
    assert [case["kind"] for case in cases].count("routine") == 2
    assert [case["kind"] for case in cases].count("trigger") == 4
    assert [case["kind"] for case in cases].count("rollback") == 1


def test_preregistration_freezes_the_live_inputs_and_claim_boundary():
    payload = json.loads(PREREGISTRATION.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 1 and payload["frozen_before_new_live_outputs"] is True
    assert payload["design"]["total_live_calls"] == 14 and payload["design"]["retries"] == 0
    assert "not an API token or latency claim" in payload["offline_context_measurement"]["claim_boundary"]
    for relative, expected in payload["frozen_input_sha256"].items():
        actual = hashlib.sha256((REPO / relative).read_bytes()).hexdigest()
        assert actual == expected, f"frozen input drifted: {relative}"


def test_receipt_parser_rejects_extra_or_invalid_values():
    assert runner.parse_receipt('{"schema_version":1,"harness":"active","reason":"trigger"}')["harness"] == "active"
    for raw in ('{}', '{"schema_version":1,"harness":"active","reason":"wrong"}',
                '{"schema_version":1,"harness":"active","reason":"trigger","extra":true}'):
        try:
            runner.parse_receipt(raw)
        except ValueError:
            pass
        else:
            raise AssertionError(f"accepted invalid receipt: {raw}")


def test_codex_usage_uses_reported_json_not_byte_estimates():
    events = ('{"type":"turn.completed","usage":{"input_tokens":12,"output_tokens":5,'
              '"cachedInputTokens":3,"cacheWriteTokens":2}}\n')
    usage = runner.extract_codex_usage(events)
    assert usage == {"input_tokens": 12, "output_tokens": 5, "cache_read_tokens": 3,
                     "cache_write_tokens": 2, "reasoning_tokens": 0, "total_tokens": 22,
                     "status": "EXACT", "reason": ""}
    assert runner.extract_codex_usage("not json")["status"] == "UNSCORED"


def test_codex_command_writes_the_final_message_separately_from_jsonl_events():
    target = Path("C:/fixture/final.txt")
    command = runner.codex_command(target, Path("C:/fixture/work"))
    assert "--json" in command and "-o" in command and "--skip-git-repo-check" in command
    assert command[command.index("-o") + 1] == str(target)


def make_db(path: Path, nonce: str, session_id: str = "s1", api_calls: int = 1):
    conn = sqlite3.connect(path)
    try:
        conn.executescript("""
            CREATE TABLE sessions (id TEXT PRIMARY KEY, input_tokens INTEGER, output_tokens INTEGER,
                cache_read_tokens INTEGER, cache_write_tokens INTEGER, reasoning_tokens INTEGER, api_call_count INTEGER);
            CREATE TABLE messages (session_id TEXT, content TEXT);
        """)
        conn.execute("INSERT INTO sessions VALUES (?, 120, 30, 4, 10, 9, ?)", (session_id, api_calls))
        conn.execute("INSERT INTO messages VALUES (?, ?)", (session_id, "probe " + nonce))
        conn.commit()
    finally:
        conn.close()


def test_hermes_usage_requires_exactly_one_new_nonce_matched_session():
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "state.db"
        make_db(db, "abc")
        usage = runner.correlate_hermes_usage(db, set(), "abc")
        assert usage["status"] == "EXACT" and usage["total_tokens"] == 164
        assert runner.correlate_hermes_usage(db, {"s1"}, "abc")["reason"] == "hermes_session_candidates_0"
        conn = sqlite3.connect(db)
        try:
            conn.execute("INSERT INTO sessions VALUES ('s2', 1, 1, 0, 0, 0, 1)")
            conn.execute("INSERT INTO messages VALUES ('s2', 'abc')")
            conn.commit()
        finally:
            conn.close()
        assert runner.correlate_hermes_usage(db, set(), "abc")["reason"] == "hermes_session_candidates_2"


def test_workspace_uses_an_actual_marker_and_output_stays_local():
    with tempfile.TemporaryDirectory() as tmp:
        workspace = Path(tmp)
        runner.prepare_workspace(workspace, marker_present=True)
        assert (workspace / "AGENTS.md").is_file()
        assert (workspace / "HERMES.md").is_file()
        assert (workspace / ".fable-harness-off").is_file()
    allowed = runner.LIVE_OUTPUT_ROOT / "fixture.json"
    assert runner.output_path(allowed) == allowed.resolve()
    for invalid in (runner.LIVE_OUTPUT_ROOT, runner.LIVE_OUTPUT_ROOT / "plain.txt",
                    Path(tempfile.gettempdir()) / "outside.json"):
        try:
            runner.output_path(invalid)
        except ValueError:
            pass
        else:
            raise AssertionError(f"accepted invalid scorecard path: {invalid}")


def test_invalid_output_fails_before_any_runtime_invocation():
    with mock.patch.object(runner, "run_case") as run_case:
        try:
            runner.main(["run", "--runtime", "codex", "--output", str(Path(tempfile.gettempdir()) / "bad.json")])
        except SystemExit as exc:
            assert exc.code == 2
        else:
            raise AssertionError("accepted output outside ignored local root")
        run_case.assert_not_called()


def test_scorecard_keeps_digests_not_raw_agent_output():
    digest = runner.output_digest("private agent response")
    assert digest["bytes"] == 22 and len(digest["sha256"]) == 64
    assert "private agent response" not in json.dumps(digest)


def test_score_rejects_routine_overtrigger_and_unscored_rows():
    rows = []
    for case in runner.load_cases():
        receipt = dict(case["expected"])
        rows.append({"kind": case["kind"], "expected": case["expected"], "receipt": receipt,
                     "correct": True, "usage": {"status": "EXACT"}})
    assert runner.score(rows)["passed"] is True
    rows[0].update(receipt={"harness": "active"}, correct=False)
    assert runner.score(rows)["routine_overtrigger"] == "1/2"
    rows[0]["correct"] = None
    assert runner.score(rows)["passed"] is False
    rows[0].update(receipt={"harness": "inactive", "reason": "trigger"}, correct=False)
    assert runner.score(rows)["passed"] is False


TESTS = [value for name, value in sorted(globals().items()) if name.startswith("test_")]


def main() -> int:
    failed = 0
    for test in TESTS:
        try:
            test()
            print(f"ok {test.__name__}")
        except Exception as exc:  # noqa: BLE001
            print(f"FAIL {test.__name__}: {exc}")
            failed += 1
    print(f"{len(TESTS) - failed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
