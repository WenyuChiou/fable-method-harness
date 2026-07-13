#!/usr/bin/env python3
"""Fail-closed freshness sentinel for a codebase-memory MCP graph.

The worktree AST is authoritative. A bare ``index_status=ready`` or successful
incremental index is not proof that graph symbols, locations, and snippets match
the tracked source. The runner emits canonical JSON and exits 0 only for FRESH,
1 for a proven STALE graph, and 2 when the check is UNSCORED/unavailable.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import re
import statistics
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path


REPO = Path(__file__).resolve().parent.parent
DEFAULT_CASES = REPO / "benchmarks" / "codebase_memory_freshness" / "cases.json"
SCHEMA_VERSION = 1
FRESH, STALE, UNSCORED = "FRESH", "STALE", "UNSCORED"


class CliFailure(RuntimeError):
    """The external CLI could not produce a trustworthy JSON result."""

    def __init__(self, reason: str, detail: str = ""):
        super().__init__(reason)
        self.reason = reason
        self.detail = detail


def normalize_source(source: str) -> str:
    return source.replace("\r\n", "\n").replace("\r", "\n").strip()


def source_hash(source: str) -> str:
    return hashlib.sha256(normalize_source(source).encode("utf-8")).hexdigest()


def normalize_graph_path(value: str, repo: Path) -> str:
    raw = str(value or "").replace("\\", "/")
    candidate = Path(raw)
    if candidate.is_absolute():
        try:
            return candidate.resolve().relative_to(repo.resolve()).as_posix()
        except ValueError:
            return raw
    return raw.lstrip("./")


def contained_path(repo: Path, relative: str) -> Path:
    candidate = Path(relative)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise ValueError("probe file must stay relative to the repository")
    resolved = (repo / candidate).resolve()
    try:
        resolved.relative_to(repo.resolve())
    except ValueError as exc:
        raise ValueError("probe file escapes the repository") from exc
    return resolved


def local_symbol(repo: Path, probe: dict) -> dict:
    file_path = contained_path(repo, probe["file"])
    expected_present = bool(probe.get("expected_present", True))
    if not file_path.is_file():
        if expected_present:
            raise ValueError("expected probe file is missing: {}".format(probe["file"]))
        return {"present": False, "file": probe["file"]}
    text = file_path.read_text(encoding="utf-8")
    tree = ast.parse(text, filename=str(file_path))
    matches = [
        node for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        and node.name == probe["symbol"]
    ]
    if len(matches) > 1:
        raise ValueError("probe symbol is ambiguous in source: {}".format(probe["symbol"]))
    if not matches:
        if expected_present:
            raise ValueError("expected probe symbol is missing: {}".format(probe["symbol"]))
        return {"present": False, "file": probe["file"]}
    if not expected_present:
        raise ValueError("deleted-symbol probe still exists locally: {}".format(probe["symbol"]))
    node = matches[0]
    if not getattr(node, "end_lineno", None):
        raise ValueError("cannot derive complete source span for {}".format(probe["symbol"]))
    decorator_lines = [item.lineno for item in getattr(node, "decorator_list", [])]
    start_line = min([node.lineno] + decorator_lines)
    source = "\n".join(text.splitlines()[start_line - 1:node.end_lineno])
    return {
        "present": True,
        "file": probe["file"],
        "start_line": start_line,
        "end_line": node.end_lineno,
        "source_sha256": source_hash(source),
        "source": normalize_source(source),
    }


def project_name(repo: Path) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "-", str(repo.resolve())).strip("-")


def decode_cli_result(tool: str, returncode: int, stdout: str, stderr: str) -> dict:
    if returncode != 0:
        raise CliFailure("{}_nonzero_exit".format(tool), "exit={}".format(returncode))
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise CliFailure("{}_malformed_json".format(tool), str(exc)) from exc
    if not isinstance(payload, dict):
        raise CliFailure("{}_non_object_json".format(tool))
    return payload


def invoke_cli(cli: str, tool: str, payload: dict, timeout: int) -> dict:
    try:
        proc = subprocess.run(
            [cli, "cli", tool, json.dumps(payload, separators=(",", ":"))],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except FileNotFoundError as exc:
        raise CliFailure("cli_not_found", str(exc)) from exc
    except subprocess.TimeoutExpired as exc:
        raise CliFailure("{}_timeout".format(tool), "timeout={}s".format(timeout)) from exc
    return decode_cli_result(tool, proc.returncode, proc.stdout, proc.stderr)


def read_cli_version(cli: str, timeout: int) -> str:
    try:
        proc = subprocess.run(
            [cli, "--version"], capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=timeout)
    except FileNotFoundError as exc:
        raise CliFailure("cli_not_found", str(exc)) from exc
    except subprocess.TimeoutExpired as exc:
        raise CliFailure("cli_version_timeout", "timeout={}s".format(timeout)) from exc
    if proc.returncode != 0 or not proc.stdout.strip():
        raise CliFailure("cli_version_unavailable", "exit={}".format(proc.returncode))
    return proc.stdout.strip().splitlines()[0]


def graph_results_by_probe(repo: Path, probes: list[dict], search: dict) -> dict[str, list[dict]]:
    if search.get("error"):
        raise CliFailure("search_graph_error", str(search.get("error")))
    results = search.get("results")
    if not isinstance(results, list):
        raise CliFailure("search_graph_missing_results")
    if search.get("has_more") or int(search.get("total", len(results))) > len(results):
        raise CliFailure("search_graph_truncated")
    grouped = {probe["id"]: [] for probe in probes}
    for result in results:
        if not isinstance(result, dict):
            raise CliFailure("search_graph_invalid_result")
        for probe in probes:
            if (result.get("name") == probe["symbol"]
                    and normalize_graph_path(result.get("file_path", ""), repo) == probe["file"]):
                grouped[probe["id"]].append(result)
    return grouped


def evaluate_probe(repo: Path, probe: dict, local: dict,
                   graph_matches: list[dict], snippet: dict | None) -> dict:
    result = {
        "id": probe["id"],
        "symbol": probe["symbol"],
        "file": probe["file"],
        "expected_present": bool(probe.get("expected_present", True)),
        "local_present": local["present"],
        "graph_match_count": len(graph_matches),
        "state": FRESH,
        "reasons": [],
    }
    if not probe.get("expected_present", True):
        if graph_matches:
            result["state"] = STALE
            result["reasons"].append("deleted_symbol_still_in_graph")
        return result
    result["local"] = {
        "start_line": local["start_line"],
        "end_line": local["end_line"],
        "source_sha256": local["source_sha256"],
    }
    if len(graph_matches) == 0:
        result["state"] = STALE
        result["reasons"].append("symbol_missing_from_graph")
        return result
    if len(graph_matches) != 1:
        result["state"] = STALE
        result["reasons"].append("symbol_ambiguous_in_graph")
        return result
    if not isinstance(snippet, dict) or snippet.get("error"):
        result["state"] = STALE
        result["reasons"].append("graph_snippet_unavailable")
        return result
    graph_source = normalize_source(str(snippet.get("source", "")))
    graph = {
        "start_line": snippet.get("start_line"),
        "end_line": snippet.get("end_line"),
        "source_sha256": source_hash(graph_source),
    }
    result["graph"] = graph
    if normalize_graph_path(snippet.get("file_path", ""), repo) != probe["file"]:
        result["reasons"].append("snippet_file_mismatch")
    if graph["start_line"] != local["start_line"] or graph["end_line"] != local["end_line"]:
        result["reasons"].append("line_span_mismatch")
    if graph["source_sha256"] != local["source_sha256"]:
        result["reasons"].append("source_mismatch")
    if result["reasons"]:
        result["state"] = STALE
    return result


def run_once(repo: Path, project: str, probes: list[dict], cli: str, timeout: int,
             invoke=invoke_cli) -> dict:
    started = time.perf_counter()
    status = invoke(cli, "index_status", {"project": project}, timeout)
    if status.get("error") or status.get("status") != "ready":
        raise CliFailure("index_status_not_ready", str(status.get("error") or status.get("status")))
    pattern = "^(?:{})$".format("|".join(re.escape(p["symbol"]) for p in probes))
    search = invoke(cli, "search_graph", {
        "project": project, "name_pattern": pattern,
        "limit": max(20, len(probes) * 4),
    }, timeout)
    grouped = graph_results_by_probe(repo, probes, search)
    locals_by_id = {probe["id"]: local_symbol(repo, probe) for probe in probes}
    snippets = {}
    for probe in probes:
        matches = grouped[probe["id"]]
        if len(matches) == 1 and probe.get("expected_present", True):
            qn = matches[0].get("qualified_name")
            if not isinstance(qn, str) or not qn:
                snippets[probe["id"]] = {"error": "qualified_name_missing"}
            else:
                snippets[probe["id"]] = invoke(cli, "get_code_snippet", {
                    "project": project, "qualified_name": qn, "include_neighbors": False,
                }, timeout)
    results = [
        evaluate_probe(repo, probe, locals_by_id[probe["id"]],
                       grouped[probe["id"]], snippets.get(probe["id"]))
        for probe in probes
    ]
    state = STALE if any(item["state"] == STALE for item in results) else FRESH
    return {
        "status": state,
        "index_status": status.get("status"),
        "graph_nodes": status.get("nodes"),
        "graph_edges": status.get("edges"),
        "duration_seconds": round(time.perf_counter() - started, 4),
        "probes": results,
    }


def load_cases(path: Path) -> tuple[list[dict], str]:
    raw = path.read_bytes()
    payload = json.loads(raw.decode("utf-8"))
    probes = payload.get("probes")
    if payload.get("schema_version") != SCHEMA_VERSION or not isinstance(probes, list) or not probes:
        raise ValueError("freshness cases must be a non-empty schema-v1 probe list")
    seen = set()
    for probe in probes:
        if not isinstance(probe, dict) or not all(
                isinstance(probe.get(key), str) and probe[key] for key in ("id", "symbol", "file")):
            raise ValueError("each freshness probe requires non-empty id, symbol, and file")
        if probe["id"] in seen:
            raise ValueError("freshness probe ids must be unique")
        seen.add(probe["id"])
    return probes, hashlib.sha256(raw).hexdigest()


def git_head(repo: Path) -> str:
    proc = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True,
        text=True, encoding="ascii", errors="replace")
    if proc.returncode != 0 or not re.fullmatch(r"[0-9a-f]{40,64}", proc.stdout.strip()):
        raise CliFailure("git_head_unavailable", "exit={}".format(proc.returncode))
    return proc.stdout.strip()


def input_provenance(repo: Path, paths: list[Path]) -> list[dict]:
    records = []
    for path in paths:
        resolved = path.resolve()
        try:
            relative = resolved.relative_to(repo.resolve()).as_posix()
        except ValueError:
            records.append({"path": str(resolved), "tracked_at_head": False,
                            "sha256": None, "reason": "outside_repository"})
            continue
        exists = resolved.is_file()
        cat = subprocess.run(
            ["git", "cat-file", "-e", "HEAD:{}".format(relative)], cwd=repo,
            capture_output=True, text=True, encoding="utf-8", errors="replace")
        diff = subprocess.run(
            ["git", "diff", "--quiet", "HEAD", "--", relative], cwd=repo,
            capture_output=True, text=True, encoding="utf-8", errors="replace")
        tracked = exists and cat.returncode == 0 and diff.returncode == 0
        records.append({
            "path": relative,
            "tracked_at_head": tracked,
            "sha256": hashlib.sha256(resolved.read_bytes()).hexdigest() if exists else None,
            "reason": "" if tracked else "missing_untracked_or_dirty",
        })
    return records


def write_scorecard(path: Path, repo: Path, scorecard: dict) -> None:
    repo_root = repo.resolve()
    allowed_root = (repo_root / "evals" / "codebase_memory_freshness").resolve()
    resolved = path.resolve()
    try:
        allowed_root.relative_to(repo_root)
        resolved.relative_to(allowed_root)
    except ValueError as exc:
        raise ValueError(
            "--output must stay inside evals/codebase_memory_freshness without symlink escape") from exc
    if resolved == allowed_root or resolved.suffix.lower() != ".json":
        raise ValueError("--output must be a JSON file below evals/codebase_memory_freshness")
    resolved.parent.mkdir(parents=True, exist_ok=True)
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=resolved.parent,
                prefix=".freshness-", suffix=".tmp", delete=False) as handle:
            temp_path = Path(handle.name)
            handle.write(json.dumps(scorecard, indent=2, ensure_ascii=False) + "\n")
        os.replace(temp_path, resolved)
        temp_path = None
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def main(argv: list[str] | None = None, invoke=invoke_cli,
         version_reader=read_cli_version) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--project")
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--cli", default="codebase-memory-mcp")
    parser.add_argument("--timeout", type=int, default=15)
    parser.add_argument("--repetitions", type=int, default=1)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    if args.timeout < 1:
        parser.error("--timeout must be positive")
    if not 1 <= args.repetitions <= 20:
        parser.error("--repetitions must be between 1 and 20")
    repo = args.repo.resolve()
    try:
        probes, manifest_hash = load_cases(args.cases.resolve())
        head = git_head(repo)
        project = args.project or project_name(repo)
        input_paths = [Path(__file__).resolve(), args.cases.resolve()]
        input_paths.extend(contained_path(repo, probe["file"]) for probe in probes)
        provenance = input_provenance(repo, list(dict.fromkeys(input_paths)))
        runs = []
        failure = None
        version = None
        try:
            version = version_reader(args.cli, args.timeout)
        except CliFailure as exc:
            failure = {"reason": exc.reason, "detail": exc.detail}
        for _ in range(args.repetitions if not failure else 0):
            try:
                runs.append(run_once(
                    repo, project, probes, args.cli, args.timeout, invoke=invoke))
            except CliFailure as exc:
                failure = {"reason": exc.reason, "detail": exc.detail}
                break
        if failure:
            overall = UNSCORED
        elif any(run["status"] == STALE for run in runs):
            overall = STALE
        else:
            overall = FRESH
        scorecard = {
            "schema_version": SCHEMA_VERSION,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "repo_head": head,
            "project": project,
            "cli_version": version,
            "case_manifest_sha256": manifest_hash,
            "input_provenance": provenance,
            "inputs_tracked_at_head": all(item["tracked_at_head"] for item in provenance),
            "requested_repetitions": args.repetitions,
            "completed_repetitions": len(runs),
            "status": overall,
            "fallback_required": overall != FRESH,
            "median_duration_seconds": (
                round(statistics.median(run["duration_seconds"] for run in runs), 4)
                if runs else None),
            "failure": failure,
            "runs": runs,
        }
        scorecard["gates"] = {
            "decisive_status": overall in (FRESH, STALE),
            "all_repetitions_completed": len(runs) == args.repetitions,
            "median_within_2_seconds": (
                scorecard["median_duration_seconds"] is not None
                and scorecard["median_duration_seconds"] <= 2.0),
            "all_probe_results_present": (
                len(runs) == args.repetitions
                and all(len(run.get("probes", [])) == len(probes) for run in runs)),
            "inputs_tracked_at_head": scorecard["inputs_tracked_at_head"],
        }
        scorecard["sentinel_evidence_valid"] = all(scorecard["gates"].values())
        exit_code = {FRESH: 0, STALE: 1, UNSCORED: 2}[overall]
        scorecard["exit_code"] = exit_code
        if args.output:
            write_scorecard(args.output, repo, scorecard)
        print(json.dumps(scorecard, indent=2, ensure_ascii=False))
        return exit_code
    except (OSError, ValueError, json.JSONDecodeError, CliFailure) as exc:
        scorecard = {
            "schema_version": SCHEMA_VERSION,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "status": UNSCORED,
            "fallback_required": True,
            "failure": {"reason": type(exc).__name__, "detail": str(exc)},
            "runs": [],
            "exit_code": 2,
        }
        if args.output:
            try:
                write_scorecard(args.output, repo, scorecard)
            except (OSError, ValueError):
                pass
        print(json.dumps(scorecard, indent=2, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
