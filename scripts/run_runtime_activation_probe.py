#!/usr/bin/env python3
"""Live Codex/Hermes conditional-activation probe with strict usage evidence.

The runner is deliberately fail-closed.  It measures receipt correctness for
trigger/routine/rollback cases and extracts provider-reported counters only
when it can associate exactly one newly created Hermes session with a unique
probe nonce.  It never converts bytes to tokens.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import signal
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parent.parent
CASES = REPO / "benchmarks" / "runtime_activation" / "cases.json"
LIVE_OUTPUT_ROOT = REPO / "evals" / "runtime_activation"
RECEIPT_KEYS = {"schema_version", "harness", "reason"}
REASONS = {"trigger", "routine", "rollback"}
POST_KILL_TIMEOUT = 10


def load_cases(path: Path = CASES) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    cases = payload.get("cases")
    if payload.get("schema_version") != 1 or not isinstance(cases, list) or len(cases) != 7:
        raise ValueError("activation fixture must be schema-v1 with seven cases")
    seen: set[str] = set()
    for case in cases:
        expected = case.get("expected", {})
        if (not isinstance(case.get("id"), str) or case["id"] in seen
                or case.get("kind") not in REASONS
                or not isinstance(case.get("marker_present"), bool)
                or expected.get("harness") not in {"active", "inactive"}
                or expected.get("reason") not in REASONS):
            raise ValueError(f"invalid activation case: {case!r}")
        if (case["kind"] == "rollback") != case["marker_present"]:
            raise ValueError(f"rollback marker mismatch: {case['id']}")
        expected_by_kind = {
            "trigger": {"harness": "active", "reason": "trigger"},
            "routine": {"harness": "inactive", "reason": "routine"},
            "rollback": {"harness": "inactive", "reason": "rollback"},
        }
        if expected != expected_by_kind[case["kind"]]:
            raise ValueError(f"activation expectation mismatch: {case['id']}")
        seen.add(case["id"])
    if {case["kind"] for case in cases} != REASONS:
        raise ValueError("fixture must cover trigger, routine, and rollback")
    return cases


def build_prompt(case: dict[str, Any], nonce: str) -> str:
    return (
        "FABLE_ACTIVATION_PROBE\n"
        f"probe_nonce: {nonce}\n"
        f"case_id: {case['id']}\n"
        "Evaluation only: inspect only the rollback marker in this workspace; "
        "do not execute the task or load routed material.\n"
        f"TASK: {case['task']}\n"
        "Return only the required JSON receipt.")


def parse_receipt(stdout: str) -> dict[str, Any]:
    payload = json.loads(stdout.strip())
    if not isinstance(payload, dict) or set(payload) != RECEIPT_KEYS:
        raise ValueError("receipt must have exactly schema_version,harness,reason")
    if (payload.get("schema_version") != 1
            or payload.get("harness") not in {"active", "inactive"}
            or payload.get("reason") not in REASONS):
        raise ValueError("receipt values are invalid")
    return payload


def codex_command(final_message: Path, workspace: Path) -> list[str]:
    base = ["codex", "exec", "--json", "--ephemeral", "--skip-git-repo-check",
            "-C", str(workspace), "-s", "read-only",
            "-o", str(final_message), "-"]
    return ["cmd", "/c", *base] if os.name == "nt" else base


def as_text(value: str | bytes | None) -> str:
    return value.decode("utf-8", "replace") if isinstance(value, bytes) else (value or "")


def run_process(command: list[str], prompt: str, timeout: int, workspace: Path) -> tuple[str, str, int | None, str, float]:
    """Run an agent and terminate its complete process tree on timeout."""
    started = time.monotonic()
    start_new_session = os.name != "nt"
    creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
    try:
        proc = subprocess.Popen(command, cwd=str(workspace), stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                encoding="utf-8", errors="replace",
                                start_new_session=start_new_session, creationflags=creationflags)
    except OSError as exc:
        return "", "", None, f"spawn_{type(exc).__name__}", time.monotonic() - started
    try:
        stdout, stderr = proc.communicate(input=prompt, timeout=timeout)
        return stdout, stderr, proc.returncode, "", time.monotonic() - started
    except subprocess.TimeoutExpired as exc:
        notes: list[str] = []
        try:
            if os.name == "nt":
                killed = subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                                        capture_output=True, text=True, timeout=POST_KILL_TIMEOUT)
                if killed.returncode != 0:
                    notes.append(f"taskkill_exit_{killed.returncode}")
                    proc.kill()
            else:
                os.killpg(proc.pid, signal.SIGKILL)
        except (OSError, subprocess.TimeoutExpired, ProcessLookupError) as kill_exc:
            notes.append(f"tree_kill_failed:{type(kill_exc).__name__}")
            with contextlib.suppress(OSError):
                proc.kill()
        try:
            stdout, stderr = proc.communicate(timeout=POST_KILL_TIMEOUT)
        except subprocess.TimeoutExpired:
            notes.append("post_kill_wait_timeout")
            with contextlib.suppress(OSError):
                proc.kill()
            stdout, stderr = as_text(exc.stdout), as_text(exc.stderr)
            for stream in (proc.stdin, proc.stdout, proc.stderr):
                if stream is not None:
                    with contextlib.suppress(OSError):
                        stream.close()
        stderr = (as_text(stderr) or as_text(exc.stderr)) + f"\nTIMEOUT after {timeout} seconds"
        if notes:
            stderr += "\nTERMINATION: " + ",".join(notes)
        return as_text(stdout) or as_text(exc.stdout), stderr, None, f"timeout_{timeout}s", time.monotonic() - started


def walk_values(value: Any):
    if isinstance(value, dict):
        for key, item in value.items():
            yield key, item
            yield from walk_values(item)
    elif isinstance(value, list):
        for item in value:
            yield from walk_values(item)


def extract_codex_usage(stdout: str) -> dict[str, Any]:
    aliases = {
        "input_tokens": {"input_tokens", "inputTokens"},
        "output_tokens": {"output_tokens", "outputTokens"},
        "cache_read_tokens": {"cache_read_tokens", "cachedInputTokens"},
        "cache_write_tokens": {"cache_write_tokens", "cacheWriteTokens"},
        "reasoning_tokens": {"reasoning_tokens", "reasoningOutputTokens"},
    }
    usage = {key: 0 for key in aliases}
    observed = False
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        for key, value in walk_values(event):
            if not isinstance(value, int) or value < 0:
                continue
            for canonical, names in aliases.items():
                if key in names:
                    usage[canonical] = max(usage[canonical], value)
                    observed = True
    usage["total_tokens"] = (usage["input_tokens"] + usage["output_tokens"]
                             + usage["cache_read_tokens"] + usage["cache_write_tokens"])
    usage["status"] = "EXACT" if observed else "UNSCORED"
    usage["reason"] = "" if observed else "codex_usage_missing"
    return usage


def default_hermes_state_db() -> Path | None:
    explicit = os.environ.get("HERMES_STATE_DB")
    if explicit:
        return Path(explicit)
    home = os.environ.get("HERMES_HOME")
    candidates = ([Path(home) / "state.db"] if home else [])
    local = os.environ.get("LOCALAPPDATA")
    if local:
        candidates.append(Path(local) / "hermes" / "state.db")
    candidates.append(Path.home() / ".hermes" / "state.db")
    return next((path for path in candidates if path.is_file()), None)


def snapshot_session_ids(path: Path | None) -> set[str]:
    if path is None or not path.is_file():
        return set()
    conn = None
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        return {str(row[0]) for row in conn.execute("SELECT id FROM sessions")}
    except sqlite3.Error:
        return set()
    finally:
        if conn is not None:
            conn.close()


def correlate_hermes_usage(path: Path | None, before: set[str], nonce: str) -> dict[str, Any]:
    empty = {"status": "UNSCORED", "reason": "hermes_state_db_unavailable"}
    if path is None or not path.is_file():
        return empty
    conn = None
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        rows = conn.execute(
            """
            SELECT s.id, s.input_tokens, s.output_tokens, s.cache_read_tokens,
                   s.cache_write_tokens, s.reasoning_tokens, s.api_call_count
            FROM sessions AS s
            JOIN messages AS m ON m.session_id = s.id
            WHERE instr(COALESCE(m.content, ''), ?) > 0
            GROUP BY s.id
            """, (nonce,)).fetchall()
    except sqlite3.Error:
        return {"status": "UNSCORED", "reason": "hermes_state_db_query_failed"}
    finally:
        if conn is not None:
            conn.close()
    rows = [row for row in rows if str(row[0]) not in before]
    if len(rows) != 1:
        return {"status": "UNSCORED", "reason": f"hermes_session_candidates_{len(rows)}"}
    _, input_tokens, output_tokens, cache_read_tokens, cache_write_tokens, reasoning_tokens, api_calls = rows[0]
    if not isinstance(api_calls, int) or api_calls < 1:
        return {"status": "UNSCORED", "reason": "hermes_usage_not_persisted"}
    values = (input_tokens, output_tokens, cache_read_tokens, cache_write_tokens, reasoning_tokens)
    if not all(isinstance(value, int) and value >= 0 for value in values):
        return {"status": "UNSCORED", "reason": "hermes_usage_non_integer"}
    if input_tokens == output_tokens == cache_read_tokens == cache_write_tokens == reasoning_tokens == 0:
        return {"status": "UNSCORED", "reason": "hermes_usage_all_zero"}
    return {
        "status": "EXACT", "reason": "", "input_tokens": input_tokens,
        "output_tokens": output_tokens, "cache_read_tokens": cache_read_tokens,
        "cache_write_tokens": cache_write_tokens, "reasoning_tokens": reasoning_tokens,
        "total_tokens": input_tokens + output_tokens + cache_read_tokens + cache_write_tokens,
        "api_call_count": api_calls,
    }


def prepare_workspace(path: Path, marker_present: bool) -> None:
    """Create the smallest real workspace needed to test the entrypoint switch."""
    for name in ("AGENTS.md", "HERMES.md"):
        shutil.copyfile(REPO / name, path / name)
    if marker_present:
        (path / ".fable-harness-off").touch()


def output_path(path: Path) -> Path:
    root = LIVE_OUTPUT_ROOT.resolve()
    candidate = path.resolve()
    if root not in candidate.parents or candidate.suffix.lower() != ".json":
        raise ValueError(f"--output must be a .json file below {root}")
    return candidate


def output_digest(value: str) -> dict[str, Any]:
    raw = value.encode("utf-8", errors="replace")
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def run_case(runtime: str, case: dict[str, Any], timeout: int, state_db: Path | None) -> dict[str, Any]:
    nonce = uuid.uuid4().hex
    prompt = build_prompt(case, nonce)
    before = snapshot_session_ids(state_db) if runtime == "hermes" else set()
    with tempfile.TemporaryDirectory(prefix="fable-runtime-activation-") as tmp:
        workspace = Path(tmp) / "workspace"
        workspace.mkdir()
        prepare_workspace(workspace, case["marker_present"])
        final_message = workspace / "codex-final.txt"
        command = ["hermes", "-z", prompt] if runtime == "hermes" else codex_command(final_message, workspace)
        stdin = "" if runtime == "hermes" else prompt
        stdout, stderr, exit_code, process_reason, duration = run_process(command, stdin, timeout, workspace)
        receipt_text = stdout if runtime == "hermes" else (
            final_message.read_text(encoding="utf-8", errors="replace") if final_message.is_file() else "")
    result: dict[str, Any] = {
        "id": case["id"], "kind": case["kind"], "expected": case["expected"],
        "exit_code": exit_code, "duration_seconds": round(duration, 6),
        "process_reason": process_reason, "marker_present": case["marker_present"],
        "receipt_output": output_digest(receipt_text), "process_stderr": output_digest(stderr),
    }
    if runtime == "hermes":
        result["usage"] = correlate_hermes_usage(state_db, before, nonce)
    else:
        result["usage"] = extract_codex_usage(stdout)
    if exit_code != 0 or process_reason:
        result.update(receipt=None, receipt_error="process_unscored", correct=None)
        return result
    try:
        receipt = parse_receipt(receipt_text)
    except (json.JSONDecodeError, ValueError) as exc:
        result.update(receipt=None, receipt_error=type(exc).__name__, correct=False)
        return result
    result.update(receipt=receipt, receipt_error="", correct=receipt == case["expected"])
    return result


def score(results: list[dict[str, Any]]) -> dict[str, Any]:
    by_kind = {kind: [row for row in results if row["kind"] == kind] for kind in REASONS}
    trigger = by_kind["trigger"]
    routine = by_kind["routine"]
    rollback = by_kind["rollback"]
    trigger_correct = sum(row.get("correct") is True for row in trigger)
    routine_overtrigger = sum((row.get("receipt") or {}).get("harness") == "active" for row in routine)
    rollback_correct = sum(row.get("correct") is True for row in rollback)
    unscored = sum(row.get("correct") is None for row in results)
    incorrect = sum(row.get("correct") is False for row in results)
    exact_usage = sum(row["usage"].get("status") == "EXACT" for row in results)
    return {
        "trigger_recall": f"{trigger_correct}/{len(trigger)}",
        "routine_overtrigger": f"{routine_overtrigger}/{len(routine)}",
        "rollback_obedience": f"{rollback_correct}/{len(rollback)}",
        "unscored_receipts": unscored,
        "incorrect_receipts": incorrect,
        "exact_usage_rows": f"{exact_usage}/{len(results)}",
        "passed": (trigger_correct == len(trigger) and routine_overtrigger == 0
                   and rollback_correct == len(rollback) and unscored == 0 and incorrect == 0),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate", help="validate the tracked fixture without calling a runtime")
    run = sub.add_parser("run", help="run live activation probes and write canonical JSON")
    run.add_argument("--runtime", choices=("codex", "hermes"), required=True)
    run.add_argument("--output", type=Path, required=True)
    run.add_argument("--timeout", type=int, default=180)
    run.add_argument("--hermes-state-db", type=Path)
    args = parser.parse_args(argv)
    cases = load_cases()
    if args.command == "validate":
        print(f"activation cases valid: {len(cases)}")
        return 0
    try:
        destination = output_path(args.output)
    except ValueError as exc:
        parser.error(str(exc))
    if shutil.which("hermes" if args.runtime == "hermes" else "codex") is None:
        print(f"UNSCORED: {args.runtime} executable unavailable", file=sys.stderr)
        return 2
    state_db = args.hermes_state_db if args.runtime == "hermes" else None
    if args.runtime == "hermes" and state_db is None:
        state_db = default_hermes_state_db()
    results = [run_case(args.runtime, case, args.timeout, state_db) for case in cases]
    scorecard = {"schema_version": 1, "runtime": args.runtime, "results": results, "metrics": score(results)}
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(scorecard, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(scorecard["metrics"], sort_keys=True))
    return 0 if scorecard["metrics"]["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
