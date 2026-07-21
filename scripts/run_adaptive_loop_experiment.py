#!/usr/bin/env python3
"""Run the preregistered paired Codex/Hermes adaptive-rule experiment.

The instrument has three phases: commit this deterministic runner, generate and
commit an environment binding without calling a model, then run one runtime at
a time.  Progress is checkpointed before every call so a crash is measured as
UNSCORED rather than silently retried.
"""

from __future__ import annotations

import argparse
import base64
import contextlib
import hmac
import hashlib
import importlib.util
import json
import math
import os
import random
import re
import shutil
import secrets
import stat
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
CASES = REPO / "benchmarks" / "adaptive_loop" / "cases_v1.json"
DESIGN = REPO / "benchmarks" / "adaptive_loop" / "preregistration_design_v1.json"
RULES = REPO / "benchmarks" / "adaptive_loop" / "rules_v1.json"
LIFECYCLE = REPO / "scripts" / "adaptive_rule_lifecycle.py"
BASE_RUNNER = REPO / "scripts" / "run_runtime_activation_probe.py"
RUNNER = Path(__file__).resolve()
EVAL_ROOT = REPO / "evals" / "adaptive_loop"
WORKSPACE_ROOT = (
    Path(os.environ.get("PUBLIC", "C:/Users/Public")) / "fable-adaptive-loop-v1-workspaces"
    if os.name == "nt"
    else Path(tempfile.gettempdir()) / "fable-adaptive-loop-v1-workspaces"
)
INSTRUMENT_OUTPUT_ROOT = WORKSPACE_ROOT / "_instrument_outputs"
PRIVATE_RUNTIME_ROOT = (
    Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    / "fable-adaptive-loop-v1-private"
    if os.name == "nt"
    else Path.home() / ".local" / "share" / "fable-adaptive-loop-v1-private"
)
RUNTIME_HOME_ROOT = PRIVATE_RUNTIME_ROOT / "runtime-homes"
CHECKPOINT_STATE_ROOT = PRIVATE_RUNTIME_ROOT / "checkpoint-state"
CROSS_RUNTIME_HOME_NAME = "_cross-runtime-home-disabled"
RUNTIMES = ("codex", "hermes")
ARMS = ("control", "treatment")
REASONS = {"trigger", "routine", "rollback"}
AMBIENT_RULE_FILES = (
    "AGENTS.md", "AGENTS.override.md", ".hermes.md", "HERMES.md", "SOUL.md",
    "CLAUDE.md", ".cursorrules")
SCHEMA_VERSION = 1
EXPECTED_CODEX_MODEL = "gpt-5.6-sol"
EXPECTED_CODEX_DISABLED_FEATURES = ("shell_tool",)
EXPECTED_HERMES_MODEL = "gpt-5.6-luna"
EXPECTED_HERMES_PROVIDER = "openai-codex"
EXPECTED_HERMES_TOOLSETS = "context_engine"
RUNTIME_ENV_PREFIXES = ("CODEX_", "HERMES_")
PROVIDER_ENV_PREFIXES = ("OPENAI_", "AZURE_OPENAI_")
TRANSPORT_OVERRIDE_ENV = (
    "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY",
    "http_proxy", "https_proxy", "all_proxy", "no_proxy",
    "SSL_CERT_FILE", "REQUESTS_CA_BUNDLE",
    "PYTHONPATH", "PYTHONHOME", "PYTHONSTARTUP", "PYTHONINSPECT",
    "NODE_OPTIONS", "NODE_PATH", "VIRTUAL_ENV", "CONDA_PREFIX",
    "TERMINAL_CWD", "MESSAGING_CWD",
)
REBUILT_ENVIRONMENT = {
    "PATH": "verified-runtime-bin-plus-os-system",
    "PYTHONNOUSERSITE": "1",
    "PYTHONSAFEPATH": "1",
}
HERMES_IGNORED_PROJECT_FALLBACKS = ("cli-config.yaml", ".env")
WINDOWS_REPARSE_POINT_ATTRIBUTE = getattr(
    stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x0400)
PROMPT_TEMPLATE = (
    "FABLE_ACTIVATION_PROBE\n"
    "probe_nonce: {nonce}\n"
    "case_id: {case_id}\n"
    "rollback_marker_at_repository_root: {marker_state}\n"
    "Evaluation only: the runner has already observed and frozen the marker "
    "state above; do not use tools, execute the task, or load routed material.\n"
    "TASK: {task}\n"
    "Return only the required JSON receipt."
)
CORRECTIVE_SUFFIX = "\nrework_attempt: 2\nprior_receipt_rejected: true"
TOKEN_SEMANTICS = {
    "canonical_total": "noncached_input + cache_read + cache_write + output",
    "codex_cached_input": "cached_input_tokens is a subset of raw input_tokens and is subtracted before canonical summation",
    "hermes": "state.db stores noncached input and cache buckets separately",
    "reasoning_tokens": "reported descriptively and not added because they are a subset of output",
    "missing_or_ambiguous": "UNSCORED",
}
WORKSPACE_POLICY = {
    "location": "fresh external directory whose parents contain no agent rule files",
    "parent_rule_files": "forbidden",
    "entrypoints": "only frozen AGENTS.md and HERMES.md git blobs",
    "marker_evidence": "frozen workspace marker state is echoed in the prompt",
    "runtime_homes": "fresh per-invocation credential-only homes outside episode workspaces",
    "corrective_continuity": "same workspace, fresh process, same nonce",
}
PROGRESS_POLICY = {
    "checkpoint_before_each_call": True,
    "uncertain_started_call": "mark interrupted and never retry",
    "raw_output": "digests only",
}
FROZEN_INPUTS = (
    "benchmarks/adaptive_loop/cases_v1.json",
    "benchmarks/adaptive_loop/preregistration_design_v1.json",
    "benchmarks/adaptive_loop/rules_v1.json",
    "scripts/adaptive_rule_lifecycle.py",
    "scripts/run_adaptive_loop_experiment.py",
    "scripts/run_runtime_activation_probe.py",
)
BINDING_FIELDS = {
    "schema_version", "experiment_id", "status", "frozen_before_new_live_outputs",
    "instrument_commit", "instrument_python", "case_set_id", "frozen_input_sha256",
    "arm_entrypoints", "schedule_seed", "schedule", "schedule_sha256",
    "prompt_template_sha256", "corrective_suffix_sha256", "timeout_seconds_per_call",
    "infrastructure_retries", "runtime_bindings", "token_semantics", "workspace_policy",
    "progress_policy", "parity_fingerprints", "binding_fingerprint",
}
HEX64 = re.compile(r"[0-9a-f]{64}")
HEX40 = re.compile(r"[0-9a-f]{40}")
WINDOWS_ABSOLUTE_PATH = re.compile(
    r"(?:^|[\s\"'=(:])(?:[A-Za-z]:[\\/]|\\\\[^\\\s]+[\\/])")
POSIX_ABSOLUTE_PATH = re.compile(r"(?:^|[\s\"'=(:])/(?![\s/])")

_base_spec = importlib.util.spec_from_file_location("runtime_activation_base", BASE_RUNNER)
base = importlib.util.module_from_spec(_base_spec)
_base_spec.loader.exec_module(base)


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def iter_strings(value: Any):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, child in value.items():
            yield from iter_strings(key)
            yield from iter_strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from iter_strings(child)


def validate_public_binding_strings(binding: dict[str, Any]) -> None:
    if any(WINDOWS_ABSOLUTE_PATH.search(value) or POSIX_ABSOLUTE_PATH.search(value)
           for value in iter_strings(binding)):
        raise ValueError("binding contains an absolute local path")


def atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", text=True)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(value, indent=2, ensure_ascii=False) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.close(descriptor)
        temporary.unlink(missing_ok=True)
        raise


def read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: root must be an object")
    return value


def cases_from_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    cases = payload.get("cases")
    if payload.get("schema_version") != SCHEMA_VERSION or not isinstance(cases, list) or len(cases) != 6:
        raise ValueError("adaptive fixture must be schema-v1 with six cases")
    seen: set[str] = set()
    expected_by_kind = {
        "trigger": {"harness": "active", "reason": "trigger"},
        "routine": {"harness": "inactive", "reason": "routine"},
        "rollback": {"harness": "inactive", "reason": "rollback"},
    }
    for case in cases:
        expected = case.get("expected") if isinstance(case, dict) else None
        if (not isinstance(case, dict) or not isinstance(case.get("id"), str)
                or case["id"] in seen or case.get("kind") not in REASONS
                or not isinstance(case.get("task"), str) or not case["task"]
                or not isinstance(case.get("marker_present"), bool)
                or expected != expected_by_kind.get(case.get("kind"))
                or (case["kind"] == "rollback") != case["marker_present"]):
            raise ValueError(f"invalid adaptive case: {case!r}")
        seen.add(case["id"])
    if {case["kind"] for case in cases} != REASONS:
        raise ValueError("fixture must cover routine, trigger, and rollback")
    return cases


def load_cases(path: Path = CASES) -> list[dict[str, Any]]:
    return cases_from_payload(read_object(path))


def build_prompt(case: dict[str, Any], nonce: str, *, corrective: bool = False) -> str:
    marker_state = "present" if case["marker_present"] else "absent"
    prompt = PROMPT_TEMPLATE.format(
        nonce=nonce, case_id=case["id"], marker_state=marker_state, task=case["task"])
    return prompt + CORRECTIVE_SUFFIX if corrective else prompt


def build_schedule(cases: list[dict[str, Any]], seed: str,
                   runtimes: tuple[str, ...] = RUNTIMES) -> list[dict[str, Any]]:
    if not isinstance(seed, str) or not seed:
        raise ValueError("schedule seed is required")
    unknown = set(runtimes) - set(RUNTIMES)
    if unknown:
        raise ValueError(f"unsupported schedule runtimes: {sorted(unknown)}")
    seed_number = int.from_bytes(hashlib.sha256(seed.encode("utf-8")).digest(), "big")
    generator = random.Random(seed_number)
    units = [(runtime, case["id"]) for runtime in runtimes for case in cases]
    generator.shuffle(units)
    schedule = []
    for runtime, case_id in units:
        arms = list(ARMS)
        generator.shuffle(arms)
        for arm in arms:
            index = len(schedule)
            schedule.append({
                "index": index,
                "schedule_id": f"S{index + 1:02d}-{runtime}-{case_id}-{arm}",
                "runtime": runtime,
                "case_id": case_id,
                "arm": arm,
            })
    return schedule


def git_bytes(*args: str) -> bytes:
    proc = subprocess.run(
        ["git", *args], cwd=REPO, capture_output=True, timeout=30)
    if proc.returncode != 0:
        message = proc.stderr.decode("utf-8", errors="replace").strip()
        raise ValueError(f"git {' '.join(args)} failed: {message}")
    return proc.stdout


def git_text(*args: str) -> str:
    return git_bytes(*args).decode("utf-8", errors="strict").strip()


def require_clean_repository() -> None:
    status = git_text("status", "--porcelain", "--untracked-files=normal")
    if status:
        raise ValueError("repository worktree and index must be clean before binding or live calls")


def require_tracked_at_head(path: Path) -> str:
    try:
        relative = path.resolve().relative_to(REPO.resolve()).as_posix()
    except ValueError as exc:
        raise ValueError(f"tracked input is outside repository: {path}") from exc
    git_bytes("cat-file", "-e", f"HEAD:{relative}")
    if git_bytes("show", f"HEAD:{relative}") != path.read_bytes():
        raise ValueError(f"tracked input differs from HEAD: {relative}")
    return relative


def design_from_payload(design: dict[str, Any]) -> dict[str, Any]:
    confirmatory = design.get("confirmatory_design", {})
    if (design.get("schema_version") != SCHEMA_VERSION
            or design.get("frozen_before_new_live_outputs") is not True
            or confirmatory.get("pairs_per_runtime") != 6
            or confirmatory.get("infrastructure_retries") != 0
            or confirmatory.get("timeout_seconds_per_call") != 180):
        raise ValueError("adaptive preregistration design drifted")
    return design


def load_design(path: Path = DESIGN) -> dict[str, Any]:
    return design_from_payload(read_object(path))


def frozen_input_bytes(binding: dict[str, Any], relative: str) -> bytes:
    if relative not in FROZEN_INPUTS:
        raise ValueError(f"input is not frozen by the binding: {relative}")
    content = git_bytes("show", f"{binding['instrument_commit']}:{relative}")
    if sha256_bytes(content) != binding["frozen_input_sha256"].get(relative):
        raise ValueError(f"immutable frozen input differs from binding: {relative}")
    return content


def frozen_object(binding: dict[str, Any], relative: str) -> dict[str, Any]:
    try:
        value = json.loads(frozen_input_bytes(binding, relative).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"immutable frozen input is invalid JSON: {relative}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"immutable frozen input root is not an object: {relative}")
    return value


def load_frozen_cases(binding: dict[str, Any]) -> list[dict[str, Any]]:
    return cases_from_payload(frozen_object(
        binding, "benchmarks/adaptive_loop/cases_v1.json"))


def load_frozen_design(binding: dict[str, Any]) -> dict[str, Any]:
    return design_from_payload(frozen_object(
        binding, "benchmarks/adaptive_loop/preregistration_design_v1.json"))


def load_arm_entrypoints(design: dict[str, Any], arm: str) -> dict[str, bytes]:
    if arm not in ARMS:
        raise ValueError(f"unsupported arm: {arm}")
    arm_design = design["confirmatory_design"]["arms"][arm]
    commit = arm_design["git_commit"]
    blobs = {name: git_bytes("show", f"{commit}:{name}") for name in ("AGENTS.md", "HERMES.md")}
    for name, content in blobs.items():
        if sha256_bytes(content) != arm_design["sha256"][name]:
            raise ValueError(f"{arm} {name} does not match preregistered git blob")
    return blobs


def assert_workspace_isolated(path: Path) -> None:
    resolved = path.resolve()
    if resolved == REPO.resolve() or REPO.resolve() in resolved.parents:
        raise ValueError("experiment workspace must be outside the repository to prevent arm leakage")
    for parent in resolved.parents:
        for name in AMBIENT_RULE_FILES:
            if (parent / name).is_file():
                raise ValueError(f"workspace parent contains an ambient rule file: {name}")


def validate_episode_workspace(path: Path) -> Path:
    resolved = path.resolve()
    root = WORKSPACE_ROOT.resolve()
    if resolved == root or root not in resolved.parents:
        raise ValueError("episode workspace escapes the dedicated external workspace root")
    assert_workspace_isolated(resolved)
    return resolved


def prepare_workspace(path: Path, entrypoints: dict[str, bytes], marker_present: bool) -> None:
    path = validate_episode_workspace(path)
    path.mkdir(parents=True, exist_ok=False)
    for name in ("AGENTS.md", "HERMES.md"):
        (path / name).write_bytes(entrypoints[name])
    if marker_present:
        (path / ".fable-harness-off").touch()


def workspace_matches(path: Path, entrypoints: dict[str, bytes], marker_present: bool) -> bool:
    try:
        path = validate_episode_workspace(path)
    except ValueError:
        return False
    expected_names = {"AGENTS.md", "HERMES.md"}
    if marker_present:
        expected_names.add(".fable-harness-off")
    try:
        if {child.name for child in path.iterdir()} != expected_names:
            return False
    except OSError:
        return False
    if any((path / name).is_symlink() or not (path / name).is_file()
           or (path / name).read_bytes() != entrypoints[name]
           for name in ("AGENTS.md", "HERMES.md")):
        return False
    marker = path / ".fable-harness-off"
    return ((marker.is_file() and not marker.is_symlink() and marker.stat().st_size == 0)
            if marker_present else not marker.exists())


def walk_values(value: Any):
    if isinstance(value, dict):
        for key, child in value.items():
            yield key, child
            yield from walk_values(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_values(child)


def extract_codex_usage(stdout: str) -> dict[str, Any]:
    aliases = {
        "raw_input": {"input_tokens", "inputTokens"},
        "output": {"output_tokens", "outputTokens"},
        "cached_subset": {"cached_input_tokens", "cachedInputTokens"},
        "cache_separate": {"cache_read_tokens", "cacheReadTokens"},
        "cache_write": {"cache_write_tokens", "cacheWriteTokens"},
        "reasoning": {"reasoning_tokens", "reasoningOutputTokens"},
    }
    terminal_usage: list[Any] = []
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict) and event.get("type") == "turn.completed" and "usage" in event:
            terminal_usage.append(event["usage"])
    if len(terminal_usage) != 1:
        reason = ("codex_multiple_terminal_usage_events" if len(terminal_usage) > 1
                  else "codex_terminal_usage_missing")
        return {"status": "UNSCORED", "reason": reason}
    collected = {key: [] for key in aliases}
    for key, value in walk_values(terminal_usage[0]):
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            continue
        for canonical, names in aliases.items():
            if key in names:
                collected[canonical].append(value)
    if any(len(set(items)) > 1 for items in collected.values()):
        return {"status": "UNSCORED", "reason": "codex_duplicate_usage_conflict"}
    values = {key: (items[0] if items else 0) for key, items in collected.items()}
    observed = {key: bool(items) for key, items in collected.items()}
    if not observed["raw_input"] or not observed["output"]:
        return {"status": "UNSCORED", "reason": "codex_required_usage_missing"}
    if (observed["cached_subset"] and observed["cache_separate"]
            and values["cached_subset"] != values["cache_separate"]):
        return {"status": "UNSCORED", "reason": "codex_cache_schema_conflict"}
    if observed["cached_subset"]:
        if values["cached_subset"] > values["raw_input"]:
            return {"status": "UNSCORED", "reason": "codex_cached_input_exceeds_raw_input"}
        input_tokens = values["raw_input"] - values["cached_subset"]
        cache_read = values["cached_subset"]
        semantics = "raw_input_includes_cached_subset"
    else:
        input_tokens = values["raw_input"]
        cache_read = values["cache_separate"]
        semantics = "input_and_cache_are_separate"
    total = input_tokens + cache_read + values["cache_write"] + values["output"]
    return {
        "status": "EXACT",
        "reason": "",
        "input_tokens": input_tokens,
        "output_tokens": values["output"],
        "cache_read_tokens": cache_read,
        "cache_write_tokens": values["cache_write"],
        "reasoning_tokens": values["reasoning"],
        "total_tokens": total,
        "input_semantics": semantics,
    }


def runtime_version_output(executable: str, resolved_path: Path | None = None) -> str:
    path = resolved_path or Path(shutil.which(executable) or "")
    if not path.is_file():
        raise ValueError(f"{executable} version probe launcher is unavailable")
    path = path.resolve()
    prefix = codex_launch_prefix(path) if executable == "codex" else (path,)
    command = [*(str(item) for item in prefix), "--version"]
    proc = subprocess.run(command, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=20,
                           env=sanitized_child_environment(executable, path, prefix))
    if proc.returncode != 0:
        raise ValueError(f"{executable} version probe failed")
    return proc.stdout + "\n" + proc.stderr


def stable_version_output(executable: str, raw_output: str | None = None) -> str:
    raw_output = runtime_version_output(executable) if raw_output is None else raw_output
    lines = []
    for line in raw_output.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(("Update available:", "Project:")):
            continue
        lines.append(stripped)
    if not lines:
        raise ValueError(f"{executable} version probe returned no stable lines")
    return "\n".join(lines)


def git_output(repository: Path, *args: str) -> bytes:
    proc = subprocess.run(
        ["git", "-C", str(repository), *args], capture_output=True, timeout=60)
    if proc.returncode != 0:
        raise ValueError(f"Hermes source git probe failed: {' '.join(args)}")
    return proc.stdout


def nul_git_paths(payload: bytes) -> set[str]:
    return {
        item.decode("utf-8", errors="surrogateescape")
        for item in payload.split(b"\0") if item
    }


def hash_changed_entry(root: Path, relative: str) -> dict[str, Any]:
    parts = Path(relative.replace("/", os.sep)).parts
    if not parts or Path(relative).is_absolute() or ".." in parts:
        raise ValueError("Hermes git reported an unsafe worktree path")
    candidate = root.joinpath(*parts)
    if candidate.is_symlink():
        target = os.readlink(candidate)
        return {"kind": "symlink", "target_sha256": sha256_bytes(os.fsencode(target))}
    if candidate.is_file():
        return {
            "kind": "file", "size_bytes": candidate.stat().st_size,
            "sha256": sha256_file(candidate),
        }
    if candidate.is_dir():
        nested = subprocess.run(
            ["git", "-C", str(candidate), "rev-parse", "HEAD"], capture_output=True,
            text=True, encoding="utf-8", errors="replace", timeout=30)
        return {
            "kind": "directory",
            "git_head": nested.stdout.strip() if nested.returncode == 0 else "UNAVAILABLE",
        }
    return {"kind": "missing"}


def git_worktree_identity(project: Path) -> dict[str, Any]:
    root = Path(git_output(project, "rev-parse", "--show-toplevel").decode(
        "utf-8", errors="surrogateescape").strip()).resolve(strict=True)
    head = git_output(root, "rev-parse", "HEAD").decode("ascii").strip()
    if not HEX40.fullmatch(head):
        raise ValueError("Hermes source HEAD is not a full git commit")
    status = git_output(root, "status", "--porcelain=v2", "-z", "--untracked-files=all")
    modified = nul_git_paths(git_output(root, "ls-files", "-z", "--modified", "--deleted"))
    staged = nul_git_paths(git_output(
        root, "diff", "--cached", "--name-only", "-z", "--diff-filter=ACDMRTUXB"))
    untracked = nul_git_paths(git_output(
        root, "ls-files", "-z", "--others", "--exclude-standard"))
    changed_paths = sorted(modified | staged | untracked)
    changed_digest = hashlib.sha256()
    for relative in changed_paths:
        entry = hash_changed_entry(root, relative)
        changed_digest.update(relative.encode("utf-8", errors="surrogateescape"))
        changed_digest.update(b"\0")
        changed_digest.update(canonical_json(entry).encode("utf-8"))
        changed_digest.update(b"\0")
    payload = {
        "git_head": head,
        "git_status_sha256": sha256_bytes(status),
        "changed_content_sha256": changed_digest.hexdigest(),
        "changed_entry_count": len(changed_paths),
        "untracked_entry_count": len(untracked),
        "dirty": bool(status),
    }
    payload["worktree_fingerprint"] = sha256_bytes(
        canonical_json(payload).encode("utf-8"))
    return payload


def python_environment_identity(python_executable: Path) -> dict[str, Any]:
    if not python_executable.is_file():
        raise ValueError("Hermes environment Python is unavailable")
    script = (
        "import importlib.metadata as m,json,re;"
        "rows=sorted((re.sub(r'[-_.]+','-',(d.metadata.get('Name') or '').lower()),"
        "d.version) for d in m.distributions());"
        "print(json.dumps(rows,separators=(',',':')))"
    )
    proc = subprocess.run(
        [str(python_executable), "-I", "-c", script], capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=60)
    if proc.returncode != 0:
        raise ValueError("Hermes Python environment probe failed")
    try:
        rows = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise ValueError("Hermes Python environment probe was malformed") from exc
    if not isinstance(rows, list) or any(
            not isinstance(row, list) or len(row) != 2
            or not all(isinstance(item, str) and item for item in row) for row in rows):
        raise ValueError("Hermes Python distribution set was malformed")
    return {
        "distribution_count": len(rows),
        "distribution_set_sha256": sha256_bytes(canonical_json(rows).encode("utf-8")),
        "python_sha256": sha256_file(python_executable),
        "python_size_bytes": python_executable.stat().st_size,
    }


def directory_tree_identity(root: Path) -> dict[str, Any]:
    root = root.resolve(strict=True)
    if not root.is_dir():
        raise ValueError("runtime package root is not a directory")
    digest = hashlib.sha256()
    file_count = total_bytes = 0
    for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            entry = {"kind": "symlink", "target_sha256": sha256_bytes(os.fsencode(os.readlink(path)))}
        elif path.is_file():
            size = path.stat().st_size
            entry = {"kind": "file", "size_bytes": size, "sha256": sha256_file(path)}
            file_count += 1
            total_bytes += size
        elif path.is_dir():
            continue
        else:
            entry = {"kind": "other"}
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(canonical_json(entry).encode("utf-8"))
        digest.update(b"\0")
    if file_count == 0:
        raise ValueError("runtime package tree contains no files")
    return {
        "file_count": file_count,
        "total_bytes": total_bytes,
        "tree_sha256": digest.hexdigest(),
    }


def codex_package_root(executable: Path) -> Path:
    candidates = [
        executable.parent / "node_modules" / "@openai" / "codex",
        executable.parent.parent if executable.parent.name == "bin" else executable.parent,
    ]
    package_root = next(
        (candidate.resolve() for candidate in candidates
         if (candidate / "package.json").is_file()), None)
    if package_root is None:
        raise ValueError("Codex npm package root is unavailable")
    return package_root


def codex_node_executable(executable: Path) -> Path:
    local_node = executable.parent / ("node.exe" if os.name == "nt" else "node")
    node_candidate = local_node if local_node.is_file() else Path(shutil.which("node") or "")
    if not node_candidate.is_file():
        raise ValueError("Node executable for Codex is unavailable")
    return node_candidate.resolve()


def codex_launch_prefix(executable: Path) -> tuple[Path, Path]:
    package_root = codex_package_root(executable)
    script = package_root / "bin" / "codex.js"
    if not script.is_file():
        raise ValueError("Codex JavaScript launcher is unavailable")
    return codex_node_executable(executable), script.resolve()


def codex_runtime_source_identity(executable: Path) -> dict[str, Any]:
    package_root = codex_package_root(executable)
    package = read_object(package_root / "package.json")
    if package.get("name") != "@openai/codex" or not isinstance(package.get("version"), str):
        raise ValueError("Codex npm package metadata is invalid")
    node = codex_node_executable(executable)
    return {
        "install_mode": "npm_package",
        "package_name": package["name"],
        "package_version": package["version"],
        "package_tree": directory_tree_identity(package_root),
        "node": {
            "basename": node.name,
            "sha256": sha256_file(node),
            "size_bytes": node.stat().st_size,
        },
    }


def assert_hermes_project_fallbacks_absent(project: Path) -> None:
    if any((project / name).exists() or (project / name).is_symlink()
           for name in HERMES_IGNORED_PROJECT_FALLBACKS):
        raise ValueError("Hermes ignored project config fallback must be absent")


def hermes_runtime_source_identity(raw_version: str, executable: Path) -> dict[str, Any]:
    project_match = re.search(r"^\s*Project:\s*(.+?)\s*$", raw_version, flags=re.MULTILINE)
    if project_match is None:
        raise ValueError("Hermes version probe did not disclose its editable source project")
    project = Path(project_match.group(1)).resolve(strict=True)
    if not project.is_dir():
        raise ValueError("Hermes source project is not a directory")
    assert_hermes_project_fallbacks_absent(project)
    python_name = "python.exe" if os.name == "nt" else "python"
    python_executable = executable.parent / python_name
    return {
        "install_mode": "editable_project",
        "ignored_project_fallbacks_absent": list(HERMES_IGNORED_PROJECT_FALLBACKS),
        "project_git": git_worktree_identity(project),
        "python_environment": python_environment_identity(python_executable),
    }


def executable_identity(name: str) -> dict[str, Any]:
    resolved = shutil.which(name)
    if resolved is None:
        raise ValueError(f"runtime executable unavailable: {name}")
    path = Path(resolved).resolve()
    raw_version = runtime_version_output(name, path)
    identity = {
        "executable": name,
        "resolved_basename": path.name,
        "resolved_sha256": sha256_file(path),
        "resolved_size_bytes": path.stat().st_size,
        "version": stable_version_output(name, raw_version),
    }
    if name == "codex":
        identity["runtime_source"] = codex_runtime_source_identity(path)
    elif name == "hermes":
        identity["runtime_source"] = hermes_runtime_source_identity(raw_version, path)
    return identity


@contextlib.contextmanager
def temporary_final_message():
    assert_workspace_isolated(INSTRUMENT_OUTPUT_ROOT / "isolation-probe")
    INSTRUMENT_OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    path = INSTRUMENT_OUTPUT_ROOT / f"codex-final-{uuid.uuid4().hex}.txt"
    try:
        yield path
    finally:
        path.unlink(missing_ok=True)


def runtime_home_source(runtime: str) -> Path:
    if runtime == "codex":
        return Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")).resolve()
    if runtime == "hermes":
        return Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes")).resolve()
    raise ValueError(f"unsupported runtime: {runtime}")


def stable_openai_account_claims(access_token: Any) -> dict[str, str]:
    if not isinstance(access_token, str) or not access_token:
        raise ValueError("OpenAI credential lacks an access token")
    parts = access_token.split(".")
    if len(parts) != 3:
        raise ValueError("OpenAI access token is not a JWT")
    try:
        encoded = parts[1] + "=" * (-len(parts[1]) % 4)
        claims = json.loads(base64.urlsafe_b64decode(encoded).decode("utf-8"))
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("OpenAI access token has invalid JWT claims") from exc
    auth = claims.get("https://api.openai.com/auth") if isinstance(claims, dict) else None
    subject = claims.get("sub") if isinstance(claims, dict) else None
    account_id = auth.get("chatgpt_account_id") if isinstance(auth, dict) else None
    if (not isinstance(subject, str) or not subject
            or not isinstance(account_id, str) or not account_id):
        raise ValueError("OpenAI JWT lacks stable subject/account claims")
    return {"subject": subject, "chatgpt_account_id": account_id}


def credential_identity_fingerprint(
        runtime: str, experiment_id: str, provider: str | None = None,
        *, auth_path: Path | None = None) -> str:
    """Bind a stable account identity without retaining credential material.

    Access and refresh tokens are deliberately excluded because a legitimate
    refresh must not invalidate a long experiment.  The experiment id scopes
    the digest so the public binding cannot be used to correlate the same
    credential across unrelated experiments.
    """
    if not experiment_id:
        raise ValueError("credential identity requires an experiment id")
    auth = auth_path or (runtime_home_source(runtime) / "auth.json")
    if auth.is_symlink() or not auth.is_file():
        raise ValueError(f"{runtime} auth.json is unavailable for isolated execution")
    try:
        document = json.loads(auth.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{runtime} auth.json is not a readable JSON object") from exc
    if not isinstance(document, dict):
        raise ValueError(f"{runtime} auth.json is not a JSON object")

    if runtime == "codex":
        tokens = document.get("tokens")
        auth_mode = document.get("auth_mode")
        account_id = tokens.get("account_id") if isinstance(tokens, dict) else None
        token_claims = stable_openai_account_claims(
            tokens.get("access_token") if isinstance(tokens, dict) else None)
        if (not isinstance(auth_mode, str) or not auth_mode
                or not isinstance(account_id, str) or not account_id):
            raise ValueError("Codex auth lacks a stable auth_mode/account_id identity")
        if account_id != token_claims["chatgpt_account_id"]:
            raise ValueError("Codex auth account_id differs from its signed-token claim")
        stable_identity: dict[str, Any] = {
            "auth_mode": auth_mode,
            "account_id": account_id,
            "token_account_claims": token_claims,
        }
    elif runtime == "hermes":
        if not isinstance(provider, str) or not provider:
            raise ValueError("Hermes credential identity requires the frozen provider")
        pool = document.get("credential_pool")
        credentials = pool.get(provider) if isinstance(pool, dict) else None
        if not isinstance(credentials, list) or not credentials:
            raise ValueError(f"Hermes auth lacks credentials for provider: {provider}")
        stable_credentials = []
        for position, credential in enumerate(credentials):
            if not isinstance(credential, dict):
                raise ValueError("Hermes credential pool contains a non-object entry")
            identifier = credential.get("id")
            auth_type = credential.get("auth_type")
            priority = credential.get("priority")
            source = credential.get("source")
            if (not isinstance(identifier, str) or not identifier
                    or not isinstance(auth_type, str) or not auth_type
                    or not isinstance(priority, int) or isinstance(priority, bool)
                    or not isinstance(source, str) or not source):
                raise ValueError("Hermes credential lacks stable id/type/priority/source identity")
            stable_credentials.append({
                "position": position,
                "id": identifier,
                "auth_type": auth_type,
                "priority": priority,
                "source": source,
                "base_url": credential.get("base_url"),
                "token_account_claims": stable_openai_account_claims(
                    credential.get("access_token")),
            })
        stable_identity = {
            "provider": provider,
            "credentials": stable_credentials,
        }
    else:
        raise ValueError(f"unsupported runtime: {runtime}")

    scoped = {
        "experiment_id": experiment_id,
        "runtime": runtime,
        "stable_identity": stable_identity,
    }
    return sha256_bytes(canonical_json(scoped).encode("utf-8"))


def runtime_home_binding(
        runtime: str, experiment_id: str, provider: str | None = None) -> dict[str, Any]:
    source = runtime_home_source(runtime)
    auth = source / "auth.json"
    if auth.is_symlink() or not auth.is_file():
        raise ValueError(f"{runtime} auth.json is unavailable for isolated execution")
    initial_files = ["auth.json"] + (["SOUL.md"] if runtime == "hermes" else [])
    return {
        "policy": "per-invocation-clean-auth-only",
        "environment_variable": "CODEX_HOME" if runtime == "codex" else "HERMES_HOME",
        "credential_source": "auth.json",
        "credential_identity_method": "experiment-scoped-stable-account-sha256",
        "credential_identity_sha256": credential_identity_fingerprint(
            runtime, experiment_id, provider, auth_path=auth),
        "cleared_environment_prefixes": [
            *RUNTIME_ENV_PREFIXES, *PROVIDER_ENV_PREFIXES],
        "cleared_environment_variables": list(TRANSPORT_OVERRIDE_ENV),
        "rebuilt_environment": dict(REBUILT_ENVIRONMENT),
        "cross_runtime_home_variable": "HERMES_HOME" if runtime == "codex" else "CODEX_HOME",
        "cross_runtime_home_policy": "isolated-disposable-path-under-runtime-home",
        "initial_files": initial_files,
        "global_rules_loaded": False,
        "memory_loaded": False,
        "credentials_persist_after_call": False,
        "hermes_telemetry": "isolated_home_state_db" if runtime == "hermes" else "not_applicable",
    }


def validate_private_runtime_home(path: Path) -> Path:
    resolved = path.resolve()
    root = RUNTIME_HOME_ROOT.resolve()
    if resolved.parent != root:
        raise ValueError("isolated runtime home must be a direct child of its private root")
    repo = REPO.resolve()
    public = WORKSPACE_ROOT.resolve()
    if resolved == repo or repo in resolved.parents or resolved == public or public in resolved.parents:
        raise ValueError("isolated runtime home is not private from the experiment workspace")
    if os.name == "nt":
        local_app_data = Path(os.environ.get(
            "LOCALAPPDATA", Path.home() / "AppData" / "Local")).resolve()
        if root != local_app_data and local_app_data not in root.parents:
            raise ValueError("Windows runtime credentials must remain under user LocalAppData")
    return resolved


def validate_private_checkpoint_state_path(path: Path) -> Path:
    resolved = path.resolve()
    root = CHECKPOINT_STATE_ROOT.resolve()
    if resolved.parent != root:
        raise ValueError("checkpoint state must be a direct child of its private root")
    repo = REPO.resolve()
    public = WORKSPACE_ROOT.resolve()
    if resolved == repo or repo in resolved.parents or resolved == public or public in resolved.parents:
        raise ValueError("checkpoint state is not private from the experiment workspace")
    if os.name == "nt":
        local_app_data = Path(os.environ.get(
            "LOCALAPPDATA", Path.home() / "AppData" / "Local")).resolve()
        if root != local_app_data and local_app_data not in root.parents:
            raise ValueError("Windows checkpoint state must remain under user LocalAppData")
    return resolved


def remove_credential_file(auth: Path) -> str:
    for attempt in range(6):
        if not auth.exists() and not auth.is_symlink():
            return "removed"
        try:
            if not auth.is_symlink():
                os.chmod(auth, stat.S_IREAD | stat.S_IWRITE)
            auth.unlink(missing_ok=True)
        except OSError:
            if attempt < 5:
                time.sleep(0.05 * (attempt + 1))
    return "pending" if auth.exists() or auth.is_symlink() else "removed"


def windows_lstat_is_reparse_point(info: os.stat_result) -> bool:
    """Detect Windows junctions/reparse points without Path.is_junction().

    Path.is_junction() was added in Python 3.12, while this repository supports
    Python 3.8+.  Both the reparse tag and the legacy file-attribute bit are
    checked so older runtimes fail closed before any child-path traversal.
    """
    return bool(
        getattr(info, "st_reparse_tag", 0)
        or (getattr(info, "st_file_attributes", 0)
            & WINDOWS_REPARSE_POINT_ATTRIBUTE)
    )


def is_link_like_directory(path: Path) -> bool:
    if path.is_symlink():
        return True
    if os.name != "nt":
        return False
    try:
        return windows_lstat_is_reparse_point(os.lstat(path))
    except FileNotFoundError:
        return False
    except OSError:
        return True


def remove_link_like_directory(path: Path) -> str:
    for attempt in range(6):
        link_like = is_link_like_directory(path)
        if not path.exists() and not link_like:
            return "removed"
        if not link_like:
            return "pending"
        try:
            if path.is_symlink():
                path.unlink(missing_ok=True)
            else:
                path.rmdir()
        except OSError:
            if attempt < 5:
                time.sleep(0.05 * (attempt + 1))
    return "pending" if path.exists() or is_link_like_directory(path) else "removed"


def remove_runtime_credentials(home: Path) -> str:
    statuses = [remove_credential_file(home / "auth.json")]
    cross_runtime_home = home / CROSS_RUNTIME_HOME_NAME
    if is_link_like_directory(cross_runtime_home):
        statuses.append(remove_link_like_directory(cross_runtime_home))
    else:
        statuses.append(remove_credential_file(cross_runtime_home / "auth.json"))
    return "pending" if "pending" in statuses else "removed"


def cleanup_private_runtime_home(path: Path) -> str:
    path = validate_private_runtime_home(path)
    credential_cleanup = remove_runtime_credentials(path) if path.exists() else "removed"
    if credential_cleanup != "removed":
        return "credential_pending"
    remainder_cleanup = base.cleanup_workspace(path) if path.exists() else "already_missing"
    cross_runtime_auth = path / CROSS_RUNTIME_HOME_NAME / "auth.json"
    if ((path / "auth.json").exists() or (path / "auth.json").is_symlink()
            or cross_runtime_auth.exists() or cross_runtime_auth.is_symlink()):
        return "credential_pending"
    return remainder_cleanup


def runtime_home_prefix(runtime: str, run_scope: str) -> str:
    if runtime not in RUNTIMES or HEX64.fullmatch(run_scope) is None:
        raise ValueError("runtime home cleanup scope is invalid")
    return f"{runtime}-{run_scope}-"


def scavenge_runtime_homes(runtime: str, run_scope: str) -> None:
    if not RUNTIME_HOME_ROOT.exists():
        return
    prefix = runtime_home_prefix(runtime, run_scope)
    for candidate in RUNTIME_HOME_ROOT.iterdir():
        if candidate.name.startswith(prefix):
            cleanup = cleanup_private_runtime_home(candidate)
            if cleanup == "credential_pending" or (candidate / "auth.json").exists():
                raise ValueError(f"{runtime} stale credential cleanup failed")
            if candidate.exists():
                raise ValueError(f"{runtime} stale isolated runtime home cleanup failed")


def child_process_path(
        runtime_executable: Path,
        runtime_command_prefix: tuple[Path, ...] = ()) -> str:
    directories = [runtime_executable.resolve().parent]
    directories.extend(path.resolve().parent for path in runtime_command_prefix)
    if os.name == "nt":
        windows = Path(os.environ.get("SystemRoot", "C:/Windows")).resolve()
        directories.extend((
            windows / "System32",
            windows / "System32" / "WindowsPowerShell" / "v1.0",
            windows,
        ))
    else:
        directories.extend((Path("/usr/bin"), Path("/bin")))
    unique = []
    for directory in directories:
        value = str(directory)
        if value not in unique:
            unique.append(value)
    return os.pathsep.join(unique)


def sanitized_child_environment(
        runtime: str, runtime_executable: Path,
        runtime_command_prefix: tuple[Path, ...] = ()) -> dict[str, str]:
    env = os.environ.copy()
    prefixes = (*RUNTIME_ENV_PREFIXES, *PROVIDER_ENV_PREFIXES)
    for key in list(env):
        if key.startswith(prefixes) or key in TRANSPORT_OVERRIDE_ENV:
            env.pop(key)
    env["PATH"] = child_process_path(runtime_executable, runtime_command_prefix)
    env["PYTHONNOUSERSITE"] = "1"
    env["PYTHONSAFEPATH"] = "1"
    return env


@contextlib.contextmanager
def isolated_runtime_environment(
        runtime: str, experiment_id: str, provider: str | None = None,
        *, run_scope: str, runtime_executable: Path,
        runtime_command_prefix: tuple[Path, ...]):
    scavenge_runtime_homes(runtime, run_scope)
    policy = runtime_home_binding(runtime, experiment_id, provider)
    source_auth = runtime_home_source(runtime) / "auth.json"
    credential_initialized = False
    RUNTIME_HOME_ROOT.mkdir(parents=True, exist_ok=True)
    if os.name != "nt":
        RUNTIME_HOME_ROOT.chmod(0o700)
    home = validate_private_runtime_home(
        RUNTIME_HOME_ROOT / f"{runtime_home_prefix(runtime, run_scope)}{uuid.uuid4().hex}")
    home.mkdir(parents=True, exist_ok=False)
    if os.name != "nt":
        home.chmod(0o700)
    try:
        shutil.copy2(source_auth, home / "auth.json")
        if os.name != "nt":
            (home / "auth.json").chmod(0o600)
        if runtime == "hermes":
            (home / "SOUL.md").touch()
        if sorted(path.name for path in home.iterdir()) != sorted(policy["initial_files"]):
            raise ValueError(f"{runtime} isolated home allowlist drifted")
        if credential_identity_fingerprint(
                runtime, experiment_id, provider, auth_path=home / "auth.json") != (
                    policy["credential_identity_sha256"]):
            raise ValueError(f"{runtime} credential identity drifted during isolated copy")
        credential_initialized = True
        env = sanitized_child_environment(
            runtime, runtime_executable, runtime_command_prefix)
        env[policy["environment_variable"]] = str(home)
        cross_runtime_home = home / CROSS_RUNTIME_HOME_NAME
        if cross_runtime_home.exists() or cross_runtime_home.is_symlink():
            raise ValueError(f"{runtime} cross-runtime credential decoy must remain absent")
        env[policy["cross_runtime_home_variable"]] = str(cross_runtime_home)
        state_db = home / "state.db" if runtime == "hermes" else None
        yield env, state_db
    finally:
        identity_drifted = False
        if credential_initialized:
            try:
                identity_drifted = (
                    not home.exists()
                    or credential_identity_fingerprint(
                        runtime, experiment_id, provider, auth_path=home / "auth.json")
                    != policy["credential_identity_sha256"]
                )
            except (OSError, ValueError):
                identity_drifted = True
        cleanup = cleanup_private_runtime_home(home) if home.exists() else "already_missing"
        if cleanup in {"pending", "credential_pending"} or home.exists():
            raise ValueError(f"{runtime} isolated runtime home cleanup failed")
        if identity_drifted:
            raise ValueError(f"{runtime} credential identity drifted during invocation")


def verified_runtime_executable(binding: dict[str, Any], runtime: str) -> Path:
    resolved = shutil.which(runtime)
    if resolved is None:
        raise ValueError(f"runtime executable unavailable: {runtime}")
    path = Path(resolved).resolve()
    identity = binding["runtime_bindings"][runtime]["identity"]
    if (path.name != identity["resolved_basename"]
            or path.stat().st_size != identity["resolved_size_bytes"]
            or sha256_file(path) != identity["resolved_sha256"]):
        raise ValueError(f"runtime launcher drifted: {runtime}")
    return path


def verified_runtime_command_prefix(
        binding: dict[str, Any], runtime: str, launcher: Path) -> tuple[Path, ...]:
    if runtime == "hermes":
        return (launcher,)
    node, script = codex_launch_prefix(launcher)
    expected = binding["runtime_bindings"]["codex"]["identity"]["runtime_source"]["node"]
    if (node.name != expected["basename"] or node.stat().st_size != expected["size_bytes"]
            or sha256_file(node) != expected["sha256"]):
        raise ValueError("Codex Node launcher drifted")
    return node, script


def runtime_command(runtime: str, binding: dict[str, Any], workspace: Path,
                    prompt: str, final_message: Path,
                    runtime_command_prefix: tuple[Path, ...] | None = None
                    ) -> tuple[list[str], str]:
    config = binding["runtime_bindings"][runtime]
    prefix = ([str(path) for path in runtime_command_prefix]
              if runtime_command_prefix is not None else [runtime])
    if runtime == "codex":
        base_command = [
            *prefix, "exec", "--json", "--strict-config", "--ephemeral",
            "--skip-git-repo-check",
            "--disable", config["disabled_features"][0],
            "--ignore-user-config", "-C", str(workspace), "-s", "read-only",
            "-m", config["model"], "-c",
            f'model_reasoning_effort="{config["reasoning_effort"]}"',
            "-o", str(final_message), "-",
        ]
        return base_command, prompt
    if runtime == "hermes":
        return ([
            *prefix, "--ignore-user-config", "-m", config["model"],
            "--provider", config["provider"], "-t", config["toolsets"],
            "-z", prompt,
        ], "")
    raise ValueError(f"unsupported runtime: {runtime}")


def bound_runtime_environment_fingerprint(
        binding: dict[str, Any], runtime: str) -> str:
    config = binding["runtime_bindings"][runtime]
    return sha256_bytes(canonical_json({
        "identity": config["identity"],
        "home_isolation": config["home_isolation"],
    }).encode("utf-8"))


def observe_runtime_environment_fingerprint(
        binding: dict[str, Any], runtime: str) -> str | None:
    config = binding["runtime_bindings"][runtime]
    try:
        payload = {
            "identity": executable_identity(runtime),
            "home_isolation": runtime_home_binding(
                runtime, binding["experiment_id"], config.get("provider")),
        }
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return None
    return sha256_bytes(canonical_json(payload).encode("utf-8"))


def environment_evidence(
        binding: dict[str, Any], runtime: str, before: str | None,
        after: str | None, *, observed: bool = True) -> dict[str, Any]:
    expected = bound_runtime_environment_fingerprint(binding, runtime)
    if not observed:
        status = "NOT_OBSERVED"
        before = after = None
    else:
        status = "MATCHED" if before == after == expected else "DRIFTED"
    return {
        "status": status,
        "binding_sha256": expected,
        "before_sha256": before,
        "after_sha256": after,
    }


def invocation_process_status(exit_code: int | None, process_reason: str) -> str:
    if process_reason.startswith("timeout_"):
        return "timeout"
    if exit_code != 0 or process_reason:
        return "error"
    return "completed"


def run_invocation(runtime: str, binding: dict[str, Any], workspace: Path,
                   prompt: str, nonce: str, expected: dict[str, str],
                   state_db: Path | None) -> dict[str, Any]:
    if state_db is not None:
        raise ValueError("external Hermes state DBs are forbidden by the isolated telemetry policy")
    environment_before = observe_runtime_environment_fingerprint(binding, runtime)
    expected_environment = bound_runtime_environment_fingerprint(binding, runtime)
    if environment_before != expected_environment:
        return {
            "exit_code": None,
            "process_status": "error",
            "process_reason": "environment_drift_before_call",
            "duration_seconds": 0.0,
            "usage": {"status": "UNSCORED", "reason": "environment_drift_before_call"},
            "receipt": None,
            "receipt_error": "process_unscored",
            "correct": None,
            "receipt_output": {"bytes": 0, "sha256": sha256_bytes(b"")},
            "process_stderr": {"bytes": 0, "sha256": sha256_bytes(b"")},
            "environment": environment_evidence(
                binding, runtime, environment_before, None),
        }
    config = binding["runtime_bindings"][runtime]
    executable = verified_runtime_executable(binding, runtime)
    command_prefix = verified_runtime_command_prefix(binding, runtime, executable)
    with isolated_runtime_environment(
            runtime, binding["experiment_id"], config.get("provider"),
            run_scope=binding["binding_fingerprint"], runtime_executable=executable,
            runtime_command_prefix=command_prefix) as (
                process_env, isolated_state_db):
        before = (base.snapshot_session_ids(isolated_state_db)
                  if runtime == "hermes" else set())
        with temporary_final_message() as final_message:
            command, stdin = runtime_command(
                runtime, binding, workspace, prompt, final_message, command_prefix)
            stdout, stderr, exit_code, process_reason, duration = base.run_process(
                command, stdin, binding["timeout_seconds_per_call"], workspace,
                env=process_env)
            receipt_text = stdout if runtime == "hermes" else (
                final_message.read_text(encoding="utf-8", errors="replace")
                if final_message.is_file() else "")
        usage = (base.correlate_hermes_usage(isolated_state_db, before, nonce)
                 if runtime == "hermes" else extract_codex_usage(stdout))
    environment_after = observe_runtime_environment_fingerprint(binding, runtime)
    environment = environment_evidence(
        binding, runtime, environment_before, environment_after)
    status = invocation_process_status(exit_code, process_reason)
    result: dict[str, Any] = {
        "exit_code": exit_code,
        "process_status": status,
        "process_reason": process_reason,
        "duration_seconds": round(duration, 6),
        "usage": usage,
        "receipt_output": base.output_digest(receipt_text),
        "process_stderr": base.output_digest(stderr),
        "environment": environment,
    }
    if environment["status"] != "MATCHED":
        result.update(
            process_status="error",
            process_reason="environment_drift_during_call",
            usage={"status": "UNSCORED", "reason": "environment_drift_during_call"},
            receipt=None,
            receipt_error="process_unscored",
            correct=None,
        )
        return result
    if status != "completed":
        result.update(receipt=None, receipt_error="process_unscored", correct=None)
        return result
    try:
        receipt = base.parse_receipt(receipt_text)
    except (json.JSONDecodeError, ValueError) as exc:
        result.update(receipt=None, receipt_error=type(exc).__name__, correct=False)
        return result
    result.update(
        receipt=receipt,
        receipt_error="",
        correct=base.receipt_matches_expected(receipt, expected),
    )
    return result


def interrupted_invocation(
        reason: str, binding: dict[str, Any], runtime: str) -> dict[str, Any]:
    return {
        "exit_code": None,
        "process_status": "error",
        "process_reason": reason,
        "duration_seconds": 0.0,
        "usage": {"status": "UNSCORED", "reason": reason},
        "receipt": None,
        "receipt_error": "process_unscored",
        "correct": None,
        "receipt_output": {"bytes": 0, "sha256": sha256_bytes(b"")},
        "process_stderr": {"bytes": 0, "sha256": sha256_bytes(b"")},
        "environment": environment_evidence(
            binding, runtime, None, None, observed=False),
    }


def invalidate_invocation_for_workspace_drift(invocation: dict[str, Any]) -> None:
    invocation.update(
        process_status="error",
        process_reason="workspace_drift_during_call",
        usage={"status": "UNSCORED", "reason": "workspace_drift_during_call"},
        receipt=None,
        receipt_error="process_unscored",
        correct=None,
    )


def invocations_to_row(case_id: str, initial: dict[str, Any],
                       corrective: dict[str, Any] | None) -> dict[str, Any]:
    if corrective is not None and initial.get("correct") is not False:
        raise ValueError("corrective invocation requires an incorrect successful initial receipt")
    corrective_count = 1 if corrective is not None else 0
    invocations = [initial] + ([corrective] if corrective is not None else [])
    exact = all(item["usage"].get("status") == "EXACT" for item in invocations)
    if exact:
        total_tokens = sum(item["usage"]["total_tokens"] for item in invocations)
        corrective_tokens = corrective["usage"]["total_tokens"] if corrective is not None else 0
    else:
        total_tokens = corrective_tokens = None
    statuses = [item["process_status"] for item in invocations]
    process_status = "timeout" if "timeout" in statuses else (
        "error" if "error" in statuses else "completed")
    final_correct = initial["correct"] if corrective is None else corrective["correct"]
    duration = sum(float(item["duration_seconds"]) for item in invocations)
    corrective_duration = float(corrective["duration_seconds"]) if corrective is not None else 0.0
    return {
        "case_id": case_id,
        "initial_correct": initial["correct"],
        "corrective_invocations": corrective_count,
        "final_correct": final_correct,
        "usage_status": "EXACT" if exact else "UNSCORED",
        "total_tokens": total_tokens,
        "corrective_tokens": corrective_tokens,
        "duration_seconds": round(duration, 6),
        "corrective_duration_seconds": round(corrective_duration, 6),
        "process_status": process_status,
    }


def resume_action(episode: dict[str, Any]) -> str:
    stage = episode.get("stage")
    if stage in ("initial_started", "corrective_started"):
        return "interrupt"
    if stage == "initial_completed":
        initial = episode.get("initial", {})
        return "corrective" if initial.get("correct") is False else "finalize"
    if stage == "corrective_completed":
        return "finalize"
    if stage == "completed":
        return "skip"
    raise ValueError(f"invalid progress stage: {stage}")


def cleanup_episode_workspace(path: Path) -> str:
    path = validate_episode_workspace(path)
    return base.cleanup_workspace(path) if path.exists() else "already_missing"


def finalize_episode(episode: dict[str, Any], progress_path: Path,
                     progress: dict[str, Any], checkpoint_path: Path,
                     checkpoint_state: dict[str, Any]) -> None:
    episode["row"] = invocations_to_row(
        episode["schedule"]["case_id"], episode["initial"], episode.get("corrective"))
    episode["workspace_cleanup"] = cleanup_episode_workspace(Path(episode["workspace"]))
    episode["stage"] = "completed"
    write_authenticated_progress(
        progress_path, progress, checkpoint_path, checkpoint_state)


def run_episode(progress: dict[str, Any], progress_path: Path, schedule: dict[str, Any],
                case: dict[str, Any], binding: dict[str, Any], design: dict[str, Any],
                state_db: Path | None, checkpoint_path: Path,
                checkpoint_state: dict[str, Any],
                entrypoint_cache: dict[str, dict[str, bytes]] | None = None) -> None:
    key = str(schedule["index"])
    episode = progress["episodes"].get(key)
    entrypoints = (entrypoint_cache[schedule["arm"]] if entrypoint_cache is not None
                   else load_arm_entrypoints(design, schedule["arm"]))
    workspace = validate_episode_workspace(WORKSPACE_ROOT / schedule["schedule_id"])
    if episode is not None and Path(episode.get("workspace", "")).resolve() != workspace:
        raise ValueError(f"progress workspace mismatch: {schedule['schedule_id']}")
    if episode is None:
        if workspace.exists():
            cleanup_episode_workspace(workspace)
        prepare_workspace(workspace, entrypoints, case["marker_present"])
        episode = {
            "stage": "initial_started",
            "schedule": schedule,
            "workspace": str(workspace),
            "nonce": uuid.uuid4().hex,
        }
        progress["episodes"][key] = episode
        write_authenticated_progress(
            progress_path, progress, checkpoint_path, checkpoint_state)
        episode["initial"] = run_invocation(
            schedule["runtime"], binding, workspace,
            build_prompt(case, episode["nonce"]), episode["nonce"], case["expected"], state_db)
        if not workspace_matches(workspace, entrypoints, case["marker_present"]):
            invalidate_invocation_for_workspace_drift(episode["initial"])
        episode["stage"] = "initial_completed"
        write_authenticated_progress(
            progress_path, progress, checkpoint_path, checkpoint_state)

    action = resume_action(episode)
    if action == "skip":
        return
    if action == "interrupt":
        if episode["stage"] == "initial_started":
            episode["initial"] = interrupted_invocation(
                "initial_call_interrupted_no_retry", binding, schedule["runtime"])
        else:
            episode["corrective"] = interrupted_invocation(
                "corrective_call_interrupted_no_retry", binding, schedule["runtime"])
            episode["stage"] = "corrective_completed"
        finalize_episode(
            episode, progress_path, progress, checkpoint_path, checkpoint_state)
        return
    if action == "corrective":
        if not workspace_matches(workspace, entrypoints, case["marker_present"]):
            episode["corrective"] = interrupted_invocation(
                "corrective_workspace_drift", binding, schedule["runtime"])
            episode["stage"] = "corrective_completed"
        else:
            episode["stage"] = "corrective_started"
            write_authenticated_progress(
                progress_path, progress, checkpoint_path, checkpoint_state)
            episode["corrective"] = run_invocation(
                schedule["runtime"], binding, workspace,
                build_prompt(case, episode["nonce"], corrective=True), episode["nonce"],
                case["expected"], state_db)
            if not workspace_matches(workspace, entrypoints, case["marker_present"]):
                invalidate_invocation_for_workspace_drift(episode["corrective"])
            episode["stage"] = "corrective_completed"
            write_authenticated_progress(
                progress_path, progress, checkpoint_path, checkpoint_state)
    finalize_episode(
        episode, progress_path, progress, checkpoint_path, checkpoint_state)


def observation_from_progress(progress: dict[str, Any], binding: dict[str, Any],
                              runtime: str, cases: list[dict[str, Any]]) -> dict[str, Any]:
    rows: dict[tuple[str, str], dict[str, Any]] = {}
    for episode in progress.get("episodes", {}).values():
        schedule = episode.get("schedule", {})
        if schedule.get("runtime") != runtime:
            continue
        if episode.get("stage") != "completed" or not isinstance(episode.get("row"), dict):
            raise ValueError(f"incomplete episode: {schedule.get('schedule_id', 'unknown')}")
        rows[(schedule["arm"], schedule["case_id"])] = episode["row"]
    expected = {(arm, case["id"]) for arm in ARMS for case in cases}
    if set(rows) != expected:
        raise ValueError("progress does not contain one completed row per runtime arm/case")
    return {
        "schema_version": SCHEMA_VERSION,
        "window_id": f"{binding['experiment_id']}-{runtime}-{binding['case_set_id']}",
        "rule_id": "activation_payload_only_v1",
        "runtime": runtime,
        "binding_fingerprint": binding["parity_fingerprints"][runtime],
        "binding_id": binding["experiment_id"],
        "control": {"cases": [rows[("control", case["id"])] for case in cases]},
        "treatment": {"cases": [rows[("treatment", case["id"])] for case in cases]},
    }


def runtime_binding_config(args: argparse.Namespace) -> dict[str, Any]:
    if args.reasoning_effort != "medium":
        raise ValueError(
            "Hermes --ignore-user-config exposes only its built-in medium reasoning default")
    if (args.codex_model != EXPECTED_CODEX_MODEL
            or args.hermes_model != EXPECTED_HERMES_MODEL
            or args.hermes_provider != EXPECTED_HERMES_PROVIDER):
        raise ValueError("runtime model/provider differs from the confirmatory instrument")
    return {
        "codex": {
            "identity": executable_identity("codex"),
            "home_isolation": runtime_home_binding("codex", args.experiment_id),
            "model": args.codex_model,
            "reasoning_effort": args.reasoning_effort,
            "disabled_features": list(EXPECTED_CODEX_DISABLED_FEATURES),
            "sandbox": "read-only",
            "user_config": "ignored",
            "session": "ephemeral",
        },
        "hermes": {
            "identity": executable_identity("hermes"),
            "home_isolation": runtime_home_binding(
                "hermes", args.experiment_id, args.hermes_provider),
            "model": args.hermes_model,
            "provider": args.hermes_provider,
            "reasoning_effort": args.reasoning_effort,
            "reasoning_source": "Hermes built-in default under --ignore-user-config",
            "toolsets": EXPECTED_HERMES_TOOLSETS,
            "user_config": "ignored",
            "session": "fresh oneshot",
        },
    }


def parity_payload(binding: dict[str, Any], runtime: str) -> dict[str, Any]:
    return {
        "rule_id": "activation_payload_only_v1",
        "runtime": runtime,
        "runtime_binding": binding["runtime_bindings"][runtime],
        "arm_entrypoints": binding["arm_entrypoints"],
        "semantic_input_sha256": {
            key: binding["frozen_input_sha256"][key]
            for key in FROZEN_INPUTS
            if key != "benchmarks/adaptive_loop/cases_v1.json"
        },
        "instrument_python": binding["instrument_python"],
        "prompt_template_sha256": binding["prompt_template_sha256"],
        "corrective_suffix_sha256": binding["corrective_suffix_sha256"],
        "timeout_seconds_per_call": binding["timeout_seconds_per_call"],
        "token_semantics": binding["token_semantics"],
        "workspace_policy": binding["workspace_policy"],
        "progress_policy": binding["progress_policy"],
    }


def build_binding(args: argparse.Namespace) -> dict[str, Any]:
    design = load_design()
    case_payload = read_object(CASES)
    cases = load_cases()
    schedule = build_schedule(cases, args.seed)
    arms = design["confirmatory_design"]["arms"]
    for arm in ARMS:
        load_arm_entrypoints(design, arm)
    frozen = {relative: sha256_file(REPO / relative) for relative in FROZEN_INPUTS}
    binding: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "experiment_id": args.experiment_id,
        "status": "frozen_before_live_calls",
        "frozen_before_new_live_outputs": True,
        "instrument_commit": git_text("rev-parse", "HEAD"),
        "instrument_python": sys.version,
        "case_set_id": case_payload["case_set_id"],
        "frozen_input_sha256": frozen,
        "arm_entrypoints": {
            arm: {"git_commit": arms[arm]["git_commit"], "sha256": arms[arm]["sha256"]}
            for arm in ARMS
        },
        "schedule_seed": args.seed,
        "schedule": schedule,
        "schedule_sha256": sha256_bytes(canonical_json(schedule).encode("utf-8")),
        "prompt_template_sha256": sha256_bytes(PROMPT_TEMPLATE.encode("utf-8")),
        "corrective_suffix_sha256": sha256_bytes(CORRECTIVE_SUFFIX.encode("utf-8")),
        "timeout_seconds_per_call": 180,
        "infrastructure_retries": 0,
        "runtime_bindings": runtime_binding_config(args),
        "token_semantics": TOKEN_SEMANTICS,
        "workspace_policy": WORKSPACE_POLICY,
        "progress_policy": PROGRESS_POLICY,
    }
    binding["parity_fingerprints"] = {
        runtime: sha256_bytes(canonical_json(parity_payload(binding, runtime)).encode("utf-8"))
        for runtime in RUNTIMES
    }
    binding["binding_fingerprint"] = sha256_bytes(canonical_json(binding).encode("utf-8"))
    validate_binding_structure(binding)
    return binding


def validate_binding_structure(binding: dict[str, Any]) -> None:
    validate_public_binding_strings(binding)
    if set(binding) != BINDING_FIELDS:
        missing = sorted(BINDING_FIELDS - set(binding))
        extra = sorted(set(binding) - BINDING_FIELDS)
        raise ValueError(f"binding fields are invalid: missing={missing}, extra={extra}")
    unsigned = {key: value for key, value in binding.items() if key != "binding_fingerprint"}
    expected_fingerprint = sha256_bytes(canonical_json(unsigned).encode("utf-8"))
    if (binding.get("schema_version") != SCHEMA_VERSION
            or binding.get("status") != "frozen_before_live_calls"
            or binding.get("frozen_before_new_live_outputs") is not True
            or binding.get("binding_fingerprint") != expected_fingerprint):
        raise ValueError("binding schema, status, or fingerprint is invalid")
    if (not isinstance(binding.get("experiment_id"), str)
            or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", binding["experiment_id"]) is None
            or not isinstance(binding.get("schedule_seed"), str)
            or not binding["schedule_seed"]
            or not isinstance(binding.get("case_set_id"), str)
            or not binding["case_set_id"]
            or not isinstance(binding.get("instrument_python"), str)
            or not binding["instrument_python"]
            or HEX40.fullmatch(binding.get("instrument_commit", "")) is None):
        raise ValueError("binding identifiers or instrument provenance are invalid")
    if not isinstance(binding.get("schedule"), list):
        raise ValueError("binding schedule must be a list")
    expected_schedule_hash = sha256_bytes(canonical_json(binding["schedule"]).encode("utf-8"))
    if binding.get("schedule_sha256") != expected_schedule_hash:
        raise ValueError("binding schedule hash is invalid")
    for key in ("prompt_template_sha256", "corrective_suffix_sha256"):
        if HEX64.fullmatch(binding.get(key, "")) is None:
            raise ValueError(f"binding hash is invalid: {key}")
    frozen = binding.get("frozen_input_sha256")
    if (not isinstance(frozen, dict) or set(frozen) != set(FROZEN_INPUTS)
            or any(HEX64.fullmatch(value) is None for value in frozen.values())):
        raise ValueError("binding frozen input set or hashes are invalid")
    parity = binding.get("parity_fingerprints")
    if (not isinstance(parity, dict) or set(parity) != set(RUNTIMES)
            or any(HEX64.fullmatch(value) is None for value in parity.values())):
        raise ValueError("binding parity fingerprints are invalid")
    runtimes = binding.get("runtime_bindings")
    if not isinstance(runtimes, dict) or set(runtimes) != set(RUNTIMES):
        raise ValueError("binding runtime set is invalid")
    runtime_fields = {
        "codex": {
            "identity", "home_isolation", "model", "reasoning_effort",
            "disabled_features", "sandbox", "user_config", "session",
        },
        "hermes": {
            "identity", "home_isolation", "model", "provider", "reasoning_effort",
            "reasoning_source", "toolsets", "user_config", "session",
        },
    }
    for runtime, config in runtimes.items():
        if (not isinstance(config, dict) or set(config) != runtime_fields[runtime]
                or not isinstance(config.get("identity"), dict)
                or config.get("reasoning_effort") != "medium"
                or not isinstance(config.get("model"), str) or not config["model"]):
            raise ValueError(f"binding runtime config is invalid: {runtime}")
        identity = config["identity"]
        common_identity = {
            "executable", "resolved_basename", "resolved_sha256", "resolved_size_bytes", "version"}
        expected_identity = common_identity | {"runtime_source"}
        if (set(identity) != expected_identity or identity.get("executable") != runtime
                or not isinstance(identity.get("resolved_basename"), str)
                or any(separator in identity["resolved_basename"] for separator in ("/", "\\"))
                or HEX64.fullmatch(identity.get("resolved_sha256", "")) is None
                or not isinstance(identity.get("resolved_size_bytes"), int)
                or isinstance(identity.get("resolved_size_bytes"), bool)
                or identity["resolved_size_bytes"] < 1
                or not isinstance(identity.get("version"), str) or not identity["version"]
                or "Project:" in identity["version"]):
            raise ValueError(f"binding runtime identity is invalid: {runtime}")
        home = config.get("home_isolation")
        if (not isinstance(home, dict)
                or set(home) != {
                    "policy", "environment_variable", "credential_source",
                    "credential_identity_method", "credential_identity_sha256",
                    "cleared_environment_prefixes", "cleared_environment_variables",
                    "rebuilt_environment", "cross_runtime_home_variable",
                    "cross_runtime_home_policy",
                    "initial_files", "global_rules_loaded", "memory_loaded",
                    "credentials_persist_after_call", "hermes_telemetry"}
                or home.get("policy") != "per-invocation-clean-auth-only"
                or home.get("environment_variable") != (
                    "CODEX_HOME" if runtime == "codex" else "HERMES_HOME")
                or home.get("credential_source") != "auth.json"
                or home.get("credential_identity_method") != (
                    "experiment-scoped-stable-account-sha256")
                or HEX64.fullmatch(home.get("credential_identity_sha256", "")) is None
                or home.get("cleared_environment_prefixes") != [
                    *RUNTIME_ENV_PREFIXES, *PROVIDER_ENV_PREFIXES]
                or home.get("cleared_environment_variables") != list(
                    TRANSPORT_OVERRIDE_ENV)
                or home.get("rebuilt_environment") != REBUILT_ENVIRONMENT
                or home.get("cross_runtime_home_variable") != (
                    "HERMES_HOME" if runtime == "codex" else "CODEX_HOME")
                or home.get("cross_runtime_home_policy") != (
                    "isolated-disposable-path-under-runtime-home")
                or home.get("initial_files") != (
                    ["auth.json"] if runtime == "codex" else ["auth.json", "SOUL.md"])
                or any(home.get(key) is not False for key in (
                    "global_rules_loaded", "memory_loaded", "credentials_persist_after_call"))
                or home.get("hermes_telemetry") != (
                    "not_applicable" if runtime == "codex" else "isolated_home_state_db")):
            raise ValueError(f"binding runtime home isolation is invalid: {runtime}")
        if runtime == "codex":
            if (config.get("model") != EXPECTED_CODEX_MODEL
                    or config.get("disabled_features")
                    != list(EXPECTED_CODEX_DISABLED_FEATURES)
                    or config.get("sandbox") != "read-only"
                    or config.get("user_config") != "ignored"
                    or config.get("session") != "ephemeral"):
                raise ValueError("binding Codex execution policy is invalid")
            source = identity["runtime_source"]
            if (not isinstance(source, dict)
                    or set(source) != {
                        "install_mode", "package_name", "package_version", "package_tree", "node"}
                    or source.get("install_mode") != "npm_package"
                    or source.get("package_name") != "@openai/codex"
                    or not isinstance(source.get("package_version"), str)
                    or not source["package_version"]):
                raise ValueError("binding Codex package identity is invalid")
            package_tree = source.get("package_tree")
            node = source.get("node")
            if (not isinstance(package_tree, dict)
                    or set(package_tree) != {"file_count", "total_bytes", "tree_sha256"}
                    or any(not isinstance(package_tree.get(key), int)
                           or isinstance(package_tree.get(key), bool) or package_tree[key] < 1
                           for key in ("file_count", "total_bytes"))
                    or HEX64.fullmatch(package_tree.get("tree_sha256", "")) is None
                    or not isinstance(node, dict)
                    or set(node) != {"basename", "sha256", "size_bytes"}
                    or not isinstance(node.get("basename"), str) or not node["basename"]
                    or any(separator in node["basename"] for separator in ("/", "\\"))
                    or HEX64.fullmatch(node.get("sha256", "")) is None
                    or not isinstance(node.get("size_bytes"), int)
                    or isinstance(node.get("size_bytes"), bool) or node["size_bytes"] < 1):
                raise ValueError("binding Codex package payload is invalid")
        else:
            source = identity["runtime_source"]
            if (not isinstance(source, dict)
                    or set(source) != {
                        "install_mode", "ignored_project_fallbacks_absent",
                        "project_git", "python_environment"}
                    or source.get("install_mode") != "editable_project"):
                raise ValueError("binding Hermes source identity is invalid")
            if source.get("ignored_project_fallbacks_absent") != list(
                    HERMES_IGNORED_PROJECT_FALLBACKS):
                raise ValueError("binding Hermes project fallback policy is invalid")
            project_git = source.get("project_git")
            if (not isinstance(project_git, dict)
                    or set(project_git) != {
                        "git_head", "git_status_sha256", "changed_content_sha256",
                        "changed_entry_count", "untracked_entry_count", "dirty",
                        "worktree_fingerprint"}
                    or HEX40.fullmatch(project_git.get("git_head", "")) is None
                    or any(HEX64.fullmatch(project_git.get(key, "")) is None for key in (
                        "git_status_sha256", "changed_content_sha256", "worktree_fingerprint"))
                    or any(not isinstance(project_git.get(key), int)
                           or isinstance(project_git.get(key), bool) or project_git[key] < 0
                           for key in ("changed_entry_count", "untracked_entry_count"))
                    or not isinstance(project_git.get("dirty"), bool)):
                raise ValueError("binding Hermes git identity is invalid")
            python_environment = source.get("python_environment")
            if (not isinstance(python_environment, dict)
                    or set(python_environment) != {
                        "distribution_count", "distribution_set_sha256", "python_sha256",
                        "python_size_bytes"}
                    or any(not isinstance(python_environment.get(key), int)
                           or isinstance(python_environment.get(key), bool)
                           or python_environment[key] < 1
                           for key in ("distribution_count", "python_size_bytes"))
                    or any(HEX64.fullmatch(python_environment.get(key, "")) is None for key in (
                        "distribution_set_sha256", "python_sha256"))):
                raise ValueError("binding Hermes Python environment is invalid")
            if (config.get("model") != EXPECTED_HERMES_MODEL
                    or config.get("provider") != EXPECTED_HERMES_PROVIDER
                    or config.get("reasoning_source") != (
                        "Hermes built-in default under --ignore-user-config")
                    or config.get("toolsets") != EXPECTED_HERMES_TOOLSETS
                    or config.get("user_config") != "ignored"
                    or config.get("session") != "fresh oneshot"):
                raise ValueError("binding Hermes execution policy is invalid")
    if (binding.get("timeout_seconds_per_call") != 180
            or binding.get("infrastructure_retries") != 0):
        raise ValueError("binding timeout or retry contract is invalid")


def validate_binding(path: Path, *, verify_environment: bool = True) -> dict[str, Any]:
    require_clean_repository()
    relative = require_tracked_at_head(path)
    binding = read_object(path)
    validate_binding_structure(binding)
    if (binding.get("prompt_template_sha256") != sha256_bytes(PROMPT_TEMPLATE.encode("utf-8"))
            or binding.get("corrective_suffix_sha256") != sha256_bytes(CORRECTIVE_SUFFIX.encode("utf-8"))
            or binding.get("timeout_seconds_per_call") != 180
            or binding.get("infrastructure_retries") != 0
            or binding.get("instrument_python") != sys.version
            or binding.get("token_semantics") != TOKEN_SEMANTICS
            or binding.get("workspace_policy") != WORKSPACE_POLICY
            or binding.get("progress_policy") != PROGRESS_POLICY):
        raise ValueError("binding prompt, timeout, or retry contract drifted")
    if subprocess.run(
            ["git", "merge-base", "--is-ancestor", binding.get("instrument_commit", ""), "HEAD"],
            cwd=REPO, capture_output=True, timeout=30).returncode != 0:
        raise ValueError("binding instrument commit is not an ancestor of HEAD")
    for frozen_path, expected in binding["frozen_input_sha256"].items():
        candidate = (REPO / frozen_path).resolve()
        require_tracked_at_head(candidate)
        if sha256_file(candidate) != expected:
            raise ValueError(f"frozen input drifted: {frozen_path}")
    design = load_frozen_design(binding)
    cases = load_frozen_cases(binding)
    case_payload = frozen_object(binding, "benchmarks/adaptive_loop/cases_v1.json")
    if binding.get("case_set_id") != case_payload.get("case_set_id"):
        raise ValueError("binding case_set_id drifted")
    expected_arms = {
        arm: {
            "git_commit": design["confirmatory_design"]["arms"][arm]["git_commit"],
            "sha256": design["confirmatory_design"]["arms"][arm]["sha256"],
        }
        for arm in ARMS
    }
    if binding.get("arm_entrypoints") != expected_arms:
        raise ValueError("binding arm entrypoints drifted from preregistration")
    for arm in ARMS:
        blobs = load_arm_entrypoints(design, arm)
        for name, content in blobs.items():
            if sha256_bytes(content) != binding["arm_entrypoints"][arm]["sha256"][name]:
                raise ValueError(f"binding arm entrypoint drifted: {arm}/{name}")
    schedule = build_schedule(cases, binding["schedule_seed"])
    if schedule != binding.get("schedule"):
        raise ValueError("binding schedule drifted")
    for runtime in RUNTIMES:
        parity = sha256_bytes(canonical_json(parity_payload(binding, runtime)).encode("utf-8"))
        if parity != binding["parity_fingerprints"].get(runtime):
            raise ValueError(f"binding parity fingerprint drifted: {runtime}")
        if verify_environment and executable_identity(runtime) != binding["runtime_bindings"][runtime]["identity"]:
            raise ValueError(f"runtime identity drifted: {runtime}")
        provider = binding["runtime_bindings"][runtime].get("provider")
        if (verify_environment
                and runtime_home_binding(runtime, binding["experiment_id"], provider)
                != binding["runtime_bindings"][runtime]["home_isolation"]):
            raise ValueError(f"runtime home isolation drifted: {runtime}")
    binding["binding_path"] = relative
    return binding


def progress_path(output: Path) -> Path:
    return output.with_name(output.stem + ".progress.json")


def validate_eval_output(path: Path) -> Path:
    resolved = path.resolve()
    try:
        resolved.relative_to(EVAL_ROOT.resolve())
    except ValueError as exc:
        raise ValueError("live output must be inside ignored evals/adaptive_loop") from exc
    if resolved.suffix.lower() != ".json":
        raise ValueError("live output must have .json suffix")
    if resolved.name.lower().endswith(".progress.json"):
        raise ValueError("live observation name reserves *.progress.json for checkpoints")
    return resolved


def canonical_eval_output(binding: dict[str, Any], runtime: str) -> Path:
    if runtime not in RUNTIMES:
        raise ValueError(f"unsupported runtime: {runtime}")
    name = (
        f"{binding['experiment_id']}-{runtime}-{binding['binding_fingerprint'][:16]}.json")
    return validate_eval_output(EVAL_ROOT / name)


def binding_runtime_lock_path(binding: dict[str, Any], runtime: str) -> Path:
    output = canonical_eval_output(binding, runtime)
    return output.with_name(output.stem + ".run.lock")


@contextlib.contextmanager
def exclusive_run_lock(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("a+b")
    acquired = False
    try:
        try:
            handle.seek(0)
            if handle.read(1) == b"":
                handle.write(b"0")
                handle.flush()
            handle.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise ValueError("this binding/runtime experiment is already running") from exc
        acquired = True
        yield
    finally:
        if acquired:
            handle.seek(0)
            if os.name == "nt":
                import msvcrt
                with contextlib.suppress(OSError):
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                with contextlib.suppress(OSError):
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()


CHECKPOINT_STATE_FIELDS = {
    "schema_version", "experiment_id", "binding_fingerprint", "runtime",
    "hmac_key_hex", "anchor_sequence", "anchor_progress_sha256", "anchor_mac",
}


def checkpoint_state_path(binding: dict[str, Any], runtime: str) -> Path:
    if runtime not in RUNTIMES:
        raise ValueError(f"unsupported runtime: {runtime}")
    scope = sha256_bytes(canonical_json({
        "experiment_id": binding["experiment_id"],
        "binding_fingerprint": binding["binding_fingerprint"],
        "runtime": runtime,
    }).encode("utf-8"))
    return validate_private_checkpoint_state_path(
        CHECKPOINT_STATE_ROOT / f"{runtime}-{scope}.json")


def new_checkpoint_state(binding: dict[str, Any], runtime: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "experiment_id": binding["experiment_id"],
        "binding_fingerprint": binding["binding_fingerprint"],
        "runtime": runtime,
        "hmac_key_hex": secrets.token_hex(32),
        "anchor_sequence": -1,
        "anchor_progress_sha256": None,
        "anchor_mac": None,
    }


def validate_checkpoint_state(
        state: Any, binding: dict[str, Any], runtime: str) -> None:
    if (not isinstance(state, dict) or set(state) != CHECKPOINT_STATE_FIELDS
            or state.get("schema_version") != SCHEMA_VERSION
            or state.get("experiment_id") != binding["experiment_id"]
            or state.get("binding_fingerprint") != binding["binding_fingerprint"]
            or state.get("runtime") != runtime
            or HEX64.fullmatch(state.get("hmac_key_hex", "")) is None
            or not isinstance(state.get("anchor_sequence"), int)
            or isinstance(state.get("anchor_sequence"), bool)
            or state["anchor_sequence"] < -1):
        raise ValueError("private checkpoint state is invalid")
    if state["anchor_sequence"] == -1:
        if state.get("anchor_progress_sha256") is not None or state.get("anchor_mac") is not None:
            raise ValueError("private checkpoint initial anchor is invalid")
    elif (HEX64.fullmatch(state.get("anchor_progress_sha256", "")) is None
          or HEX64.fullmatch(state.get("anchor_mac", "")) is None):
        raise ValueError("private checkpoint anchor is invalid")


def write_checkpoint_state(path: Path, state: dict[str, Any]) -> None:
    path = validate_private_checkpoint_state_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if os.name != "nt":
        path.parent.chmod(0o700)
    atomic_write_json(path, state)
    if os.name != "nt":
        path.chmod(0o600)


def load_or_create_checkpoint_state(
        binding: dict[str, Any], runtime: str, *, progress_exists: bool
        ) -> tuple[Path, dict[str, Any]]:
    path = checkpoint_state_path(binding, runtime)
    if not path.is_file():
        if progress_exists:
            raise ValueError("progress exists without its private checkpoint state")
        state = new_checkpoint_state(binding, runtime)
        write_checkpoint_state(path, state)
        return path, state
    state = read_object(path)
    validate_checkpoint_state(state, binding, runtime)
    if not progress_exists and state["anchor_sequence"] >= 0:
        raise ValueError("authenticated progress was deleted or rolled back")
    return path, state


def unsigned_progress(progress: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in progress.items() if key != "checkpoint_mac"}


def checkpoint_mac(progress: dict[str, Any], state: dict[str, Any]) -> str:
    key = bytes.fromhex(state["hmac_key_hex"])
    payload = canonical_json(unsigned_progress(progress)).encode("utf-8")
    return hmac.new(key, payload, hashlib.sha256).hexdigest()


def signed_progress_sha256(progress: dict[str, Any]) -> str:
    return sha256_bytes(canonical_json(progress).encode("utf-8"))


def update_checkpoint_anchor(
        state_path: Path, state: dict[str, Any], progress: dict[str, Any]) -> None:
    state["anchor_sequence"] = progress["checkpoint_sequence"]
    state["anchor_progress_sha256"] = signed_progress_sha256(progress)
    state["anchor_mac"] = progress["checkpoint_mac"]
    write_checkpoint_state(state_path, state)


def verify_authenticated_progress(
        progress: dict[str, Any], state_path: Path, state: dict[str, Any]) -> None:
    sequence = progress.get("checkpoint_sequence")
    mac = progress.get("checkpoint_mac")
    if (not isinstance(sequence, int) or isinstance(sequence, bool) or sequence < 0
            or HEX64.fullmatch(mac or "") is None
            or not hmac.compare_digest(mac, checkpoint_mac(progress, state))):
        raise ValueError("progress authentication failed")
    digest = signed_progress_sha256(progress)
    anchor = state["anchor_sequence"]
    if sequence == anchor:
        if (not hmac.compare_digest(digest, state["anchor_progress_sha256"])
                or not hmac.compare_digest(mac, state["anchor_mac"])):
            raise ValueError("progress differs from its private checkpoint anchor")
    elif sequence == anchor + 1:
        update_checkpoint_anchor(state_path, state, progress)
    elif sequence < anchor:
        raise ValueError("authenticated progress rollback detected")
    else:
        raise ValueError("authenticated progress sequence gap detected")


def write_authenticated_progress(
        path: Path, progress: dict[str, Any], state_path: Path,
        state: dict[str, Any]) -> None:
    if progress.get("checkpoint_sequence") != state["anchor_sequence"]:
        raise ValueError("progress writer is not aligned with its private anchor")
    progress["checkpoint_sequence"] = state["anchor_sequence"] + 1
    progress["checkpoint_mac"] = checkpoint_mac(progress, state)
    atomic_write_json(path, progress)
    update_checkpoint_anchor(state_path, state, progress)


def new_progress(binding: dict[str, Any], runtime: str) -> dict[str, Any]:
    schedule = [row for row in binding["schedule"] if row["runtime"] == runtime]
    return {
        "schema_version": SCHEMA_VERSION,
        "experiment_id": binding["experiment_id"],
        "binding_fingerprint": binding["binding_fingerprint"],
        "runtime": runtime,
        "schedule": schedule,
        "episodes": {},
        "checkpoint_sequence": -1,
        "checkpoint_mac": None,
    }


def validate_output_digest(value: Any, label: str) -> None:
    if (not isinstance(value, dict) or set(value) != {"bytes", "sha256"}
            or not isinstance(value.get("bytes"), int) or isinstance(value.get("bytes"), bool)
            or value["bytes"] < 0 or HEX64.fullmatch(value.get("sha256", "")) is None):
        raise ValueError(f"checkpoint invocation {label} digest is invalid")


def validate_environment_checkpoint(
        value: Any, binding: dict[str, Any], runtime: str, label: str) -> None:
    fields = {"status", "binding_sha256", "before_sha256", "after_sha256"}
    expected = bound_runtime_environment_fingerprint(binding, runtime)
    if (not isinstance(value, dict) or set(value) != fields
            or value.get("status") not in {"MATCHED", "DRIFTED", "NOT_OBSERVED"}
            or value.get("binding_sha256") != expected):
        raise ValueError(f"checkpoint invocation {label} environment is invalid")
    before = value.get("before_sha256")
    after = value.get("after_sha256")
    if any(item is not None and HEX64.fullmatch(item) is None for item in (before, after)):
        raise ValueError(f"checkpoint invocation {label} environment hash is invalid")
    if value["status"] == "MATCHED" and (before != expected or after != expected):
        raise ValueError(f"checkpoint invocation {label} matched environment is invalid")
    if value["status"] == "DRIFTED" and before == after == expected:
        raise ValueError(f"checkpoint invocation {label} drift evidence is invalid")
    if value["status"] == "NOT_OBSERVED" and (before is not None or after is not None):
        raise ValueError(f"checkpoint invocation {label} unobserved environment is invalid")


def validate_invocation_checkpoint(invocation: Any, label: str, runtime: str,
                                   expected_receipt: dict[str, str],
                                   binding: dict[str, Any]) -> None:
    required = {
        "exit_code", "process_status", "process_reason", "duration_seconds", "usage",
        "receipt", "receipt_error", "correct", "receipt_output", "process_stderr",
        "environment",
    }
    if not isinstance(invocation, dict) or set(invocation) != required:
        raise ValueError(f"checkpoint invocation {label} fields are invalid")
    exit_code = invocation["exit_code"]
    if exit_code is not None and (not isinstance(exit_code, int) or isinstance(exit_code, bool)):
        raise ValueError(f"checkpoint invocation {label} exit code is invalid")
    status = invocation["process_status"]
    if status not in {"completed", "error", "timeout"}:
        raise ValueError(f"checkpoint invocation {label} process status is invalid")
    if (not isinstance(invocation["process_reason"], str)
            or not isinstance(invocation["receipt_error"], str)):
        raise ValueError(f"checkpoint invocation {label} reason is invalid")
    duration = invocation["duration_seconds"]
    if (not isinstance(duration, (int, float)) or isinstance(duration, bool)
            or not math.isfinite(float(duration)) or duration < 0):
        raise ValueError(f"checkpoint invocation {label} duration is invalid")
    if invocation["correct"] not in {True, False, None}:
        raise ValueError(f"checkpoint invocation {label} correctness is invalid")
    if invocation["receipt"] is not None and not isinstance(invocation["receipt"], dict):
        raise ValueError(f"checkpoint invocation {label} receipt is invalid")
    usage = invocation["usage"]
    if not isinstance(usage, dict) or usage.get("status") not in {"EXACT", "UNSCORED"}:
        raise ValueError(f"checkpoint invocation {label} usage is invalid")
    if usage["status"] == "EXACT":
        common = {
            "status", "reason", "input_tokens", "output_tokens", "cache_read_tokens",
            "cache_write_tokens", "reasoning_tokens", "total_tokens",
        }
        runtime_fields = ({"input_semantics"} if runtime == "codex" else {"api_call_count"})
        if set(usage) != common | runtime_fields:
            raise ValueError(f"checkpoint invocation {label} exact usage fields are invalid")
        numeric = (
            "input_tokens", "output_tokens", "cache_read_tokens", "cache_write_tokens",
            "reasoning_tokens", "total_tokens",
        )
        if any(not isinstance(usage.get(key), int) or isinstance(usage.get(key), bool)
               or usage[key] < 0 for key in numeric):
            raise ValueError(f"checkpoint invocation {label} exact usage is invalid")
        canonical_total = sum(usage[key] for key in (
            "input_tokens", "output_tokens", "cache_read_tokens", "cache_write_tokens"))
        if usage["total_tokens"] != canonical_total or usage.get("reason") != "":
            raise ValueError(f"checkpoint invocation {label} canonical usage total is invalid")
        if runtime == "codex" and usage.get("input_semantics") not in {
                "raw_input_includes_cached_subset", "input_and_cache_are_separate"}:
            raise ValueError(f"checkpoint invocation {label} Codex usage semantics are invalid")
        if runtime == "hermes" and (
                not isinstance(usage.get("api_call_count"), int)
                or isinstance(usage.get("api_call_count"), bool)
                or usage["api_call_count"] < 1):
            raise ValueError(f"checkpoint invocation {label} Hermes usage semantics are invalid")
    elif (set(usage) != {"status", "reason"}
          or not isinstance(usage.get("reason"), str) or not usage["reason"]):
        raise ValueError(f"checkpoint invocation {label} unscored usage is invalid")
    validate_output_digest(invocation["receipt_output"], f"{label}/receipt")
    validate_output_digest(invocation["process_stderr"], f"{label}/stderr")
    validate_environment_checkpoint(invocation["environment"], binding, runtime, label)
    environment_status = invocation["environment"]["status"]
    if environment_status != "MATCHED" and (
            status != "error" or usage["status"] != "UNSCORED"
            or invocation["correct"] is not None or invocation["receipt"] is not None):
        raise ValueError(f"checkpoint invocation {label} tainted environment was scored")
    if environment_status == "DRIFTED" and invocation["process_reason"] not in {
            "environment_drift_before_call", "environment_drift_during_call",
            "workspace_drift_during_call"}:
        raise ValueError(f"checkpoint invocation {label} drift reason is invalid")
    if environment_status == "NOT_OBSERVED" and invocation["process_reason"] not in {
            "initial_call_interrupted_no_retry", "corrective_call_interrupted_no_retry",
            "corrective_workspace_drift"}:
        raise ValueError(f"checkpoint invocation {label} unobserved reason is invalid")
    if invocation["process_reason"] == "workspace_drift_during_call" and (
            status != "error" or usage["status"] != "UNSCORED"
            or invocation["correct"] is not None or invocation["receipt"] is not None):
        raise ValueError(f"checkpoint invocation {label} workspace drift was scored")
    if status == "completed":
        if exit_code != 0 or invocation["correct"] not in {True, False}:
            raise ValueError(f"checkpoint invocation {label} completion is inconsistent")
        if invocation["process_reason"] != "":
            raise ValueError(f"checkpoint invocation {label} completion reason is inconsistent")
        if invocation["receipt"] is None:
            if invocation["receipt_error"] not in {"JSONDecodeError", "ValueError"}:
                raise ValueError(f"checkpoint invocation {label} receipt error is inconsistent")
            derived_correct = False
        else:
            if invocation["receipt_error"] != "":
                raise ValueError(f"checkpoint invocation {label} receipt error is inconsistent")
            try:
                receipt = base.parse_receipt(canonical_json(invocation["receipt"]))
            except (json.JSONDecodeError, ValueError) as exc:
                raise ValueError(f"checkpoint invocation {label} receipt schema is invalid") from exc
            derived_correct = base.receipt_matches_expected(receipt, expected_receipt)
        if invocation["correct"] is not derived_correct:
            raise ValueError(f"checkpoint invocation {label} correctness was not oracle-derived")
    elif invocation["correct"] is not None or invocation["receipt"] is not None:
        raise ValueError(f"checkpoint invocation {label} failure is inconsistent")
    elif invocation["receipt_error"] != "process_unscored":
        raise ValueError(f"checkpoint invocation {label} failure receipt state is inconsistent")


def validate_episode_checkpoint(episode: Any, expected_schedule: dict[str, Any],
                                expected_receipt: dict[str, str], runtime: str,
                                binding: dict[str, Any]) -> None:
    if not isinstance(episode, dict) or episode.get("schedule") != expected_schedule:
        raise ValueError("checkpoint episode schedule is invalid")
    stage = episode.get("stage")
    fields_by_stage = {
        "initial_started": {"stage", "schedule", "workspace", "nonce"},
        "initial_completed": {"stage", "schedule", "workspace", "nonce", "initial"},
        "corrective_started": {"stage", "schedule", "workspace", "nonce", "initial"},
        "corrective_completed": {
            "stage", "schedule", "workspace", "nonce", "initial", "corrective"},
    }
    if stage == "completed":
        expected_fields = {
            "stage", "schedule", "workspace", "nonce", "initial", "row", "workspace_cleanup"}
        if "corrective" in episode:
            expected_fields.add("corrective")
    else:
        expected_fields = fields_by_stage.get(stage)
    if expected_fields is None or set(episode) != expected_fields:
        raise ValueError("checkpoint episode fields are invalid")
    nonce = episode.get("nonce")
    if not isinstance(nonce, str) or re.fullmatch(r"[0-9a-f]{32}", nonce) is None:
        raise ValueError("checkpoint episode nonce is invalid")
    expected_workspace = validate_episode_workspace(
        WORKSPACE_ROOT / expected_schedule["schedule_id"])
    try:
        actual_workspace = Path(episode.get("workspace", "")).resolve()
    except (OSError, RuntimeError) as exc:
        raise ValueError("checkpoint episode workspace is invalid") from exc
    if actual_workspace != expected_workspace:
        raise ValueError("checkpoint episode workspace is invalid")
    if stage != "initial_started":
        validate_invocation_checkpoint(
            episode["initial"], "initial", runtime, expected_receipt, binding)
    if stage in {"corrective_started", "corrective_completed"}:
        if episode["initial"]["correct"] is not False:
            raise ValueError("checkpoint corrective stage lacks an incorrect initial invocation")
    if stage == "corrective_completed":
        validate_invocation_checkpoint(
            episode["corrective"], "corrective", runtime, expected_receipt, binding)
    if stage == "completed":
        corrective = episode.get("corrective")
        if corrective is not None:
            validate_invocation_checkpoint(
                corrective, "corrective", runtime, expected_receipt, binding)
        if (episode["initial"]["correct"] is False) != (corrective is not None):
            raise ValueError("checkpoint completed corrective history is inconsistent")
        expected_row = invocations_to_row(
            expected_schedule["case_id"], episode["initial"], corrective)
        if episode.get("row") != expected_row:
            raise ValueError("checkpoint completed row is invalid")
        if episode.get("workspace_cleanup") not in {"removed", "pending", "already_missing"}:
            raise ValueError("checkpoint workspace cleanup status is invalid")


def load_or_create_progress(
        path: Path, binding: dict[str, Any], runtime: str,
        cases: list[dict[str, Any]],
        ) -> tuple[dict[str, Any], Path, dict[str, Any]]:
    expected = new_progress(binding, runtime)
    checkpoint_path, checkpoint_state = load_or_create_checkpoint_state(
        binding, runtime, progress_exists=path.is_file())
    if not path.is_file():
        write_authenticated_progress(
            path, expected, checkpoint_path, checkpoint_state)
        return expected, checkpoint_path, checkpoint_state
    progress = read_object(path)
    verify_authenticated_progress(progress, checkpoint_path, checkpoint_state)
    if set(progress) != set(expected):
        raise ValueError("progress fields are invalid")
    for key in ("schema_version", "experiment_id", "binding_fingerprint", "runtime", "schedule"):
        if progress.get(key) != expected[key]:
            raise ValueError(f"progress binding mismatch: {key}")
    if not isinstance(progress.get("episodes"), dict):
        raise ValueError("progress episodes must be an object")
    schedule_by_key = {str(item["index"]): item for item in expected["schedule"]}
    cases_by_id = {case["id"]: case for case in cases}
    for key, episode in progress["episodes"].items():
        if key not in schedule_by_key:
            raise ValueError(f"progress contains an unknown episode: {key}")
        schedule = schedule_by_key[key]
        validate_episode_checkpoint(
            episode, schedule, cases_by_id[schedule["case_id"]]["expected"], runtime,
            binding)
    return progress, checkpoint_path, checkpoint_state


def run_runtime(binding_path: Path, runtime: str, output: Path,
                state_db: Path | None) -> dict[str, Any]:
    if state_db is not None:
        raise ValueError("--hermes-state-db is incompatible with isolated per-call telemetry")
    preliminary = read_object(binding_path)
    validate_binding_structure(preliminary)
    with exclusive_run_lock(binding_runtime_lock_path(preliminary, runtime)):
        scavenge_runtime_homes(runtime, preliminary["binding_fingerprint"])
        binding = validate_binding(binding_path)
        if binding["binding_fingerprint"] != preliminary["binding_fingerprint"]:
            raise ValueError("binding changed while acquiring the canonical run lock")
        destination = validate_eval_output(output)
        canonical_destination = canonical_eval_output(binding, runtime)
        if destination != canonical_destination:
            raise ValueError(
                f"live output must equal canonical binding/runtime path: {canonical_destination}")
        return run_runtime_locked(binding, runtime, destination)


def run_runtime_locked(binding: dict[str, Any], runtime: str,
                       destination: Path) -> dict[str, Any]:
    scavenge_runtime_homes(runtime, binding["binding_fingerprint"])
    cases = load_frozen_cases(binding)
    by_id = {case["id"]: case for case in cases}
    design = load_frozen_design(binding)
    progress_file = progress_path(destination)
    if destination.exists() and not progress_file.exists():
        raise ValueError("observation exists without canonical progress; refusing any repeated live calls")
    progress, checkpoint_path, checkpoint_state = load_or_create_progress(
        progress_file, binding, runtime, cases)
    WORKSPACE_ROOT.mkdir(parents=True, exist_ok=True)
    assert_workspace_isolated(WORKSPACE_ROOT / "isolation-probe")
    entrypoint_cache = {arm: load_arm_entrypoints(design, arm) for arm in ARMS}
    for item in progress["schedule"]:
        run_episode(
            progress, progress_file, item, by_id[item["case_id"]], binding, design,
            None, checkpoint_path, checkpoint_state,
            entrypoint_cache=entrypoint_cache)
    if executable_identity(runtime) != binding["runtime_bindings"][runtime]["identity"]:
        raise ValueError(f"runtime identity drifted after calls: {runtime}")
    provider = binding["runtime_bindings"][runtime].get("provider")
    if (runtime_home_binding(runtime, binding["experiment_id"], provider)
            != binding["runtime_bindings"][runtime]["home_isolation"]):
        raise ValueError(f"runtime home isolation drifted after calls: {runtime}")
    observation = observation_from_progress(progress, binding, runtime, cases)
    atomic_write_json(destination, observation)
    return observation


def binding_output_path(path: Path) -> Path:
    resolved = path.resolve()
    allowed = (REPO / "benchmarks" / "adaptive_loop").resolve()
    try:
        resolved.relative_to(allowed)
    except ValueError as exc:
        raise ValueError("binding output must be inside benchmarks/adaptive_loop") from exc
    if resolved.suffix.lower() != ".json":
        raise ValueError("binding output must have .json suffix")
    return resolved


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate-cases", help="Validate the six-case fixture without runtime calls.")
    bind = sub.add_parser("bind", help="Write a final no-model-call environment binding.")
    bind.add_argument("--output", type=Path, required=True)
    bind.add_argument("--experiment-id", required=True)
    bind.add_argument("--seed", required=True)
    bind.add_argument("--codex-model", required=True)
    bind.add_argument("--hermes-model", required=True)
    bind.add_argument("--hermes-provider", required=True)
    bind.add_argument("--reasoning-effort", choices=("minimal", "low", "medium", "high", "xhigh"),
                      required=True)
    validate = sub.add_parser("validate-binding", help="Validate a committed binding without model calls.")
    validate.add_argument("--binding", type=Path, required=True)
    run = sub.add_parser("run", help="Run or safely resume one runtime's frozen paired schedule.")
    run.add_argument("--binding", type=Path, required=True)
    run.add_argument("--runtime", choices=RUNTIMES, required=True)
    run.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "validate-cases":
            print(f"adaptive cases valid: {len(load_cases())}")
            return 0
        if args.command == "bind":
            require_clean_repository()
            for relative in FROZEN_INPUTS:
                require_tracked_at_head(REPO / relative)
            destination = binding_output_path(args.output)
            if destination.exists():
                raise ValueError(f"binding output already exists: {destination}")
            binding = build_binding(args)
            atomic_write_json(destination, binding)
            print(json.dumps({
                "experiment_id": binding["experiment_id"],
                "binding_fingerprint": binding["binding_fingerprint"],
                "schedule_sha256": binding["schedule_sha256"],
            }, sort_keys=True))
            return 0
        if args.command == "validate-binding":
            binding = validate_binding(args.binding)
            print(json.dumps({
                "experiment_id": binding["experiment_id"],
                "binding_fingerprint": binding["binding_fingerprint"],
            }, sort_keys=True))
            return 0
        observation = run_runtime(
            args.binding, args.runtime, args.output, None)
        print(json.dumps({
            "runtime": args.runtime,
            "control_cases": len(observation["control"]["cases"]),
            "treatment_cases": len(observation["treatment"]["cases"]),
            "output": str(args.output),
        }, sort_keys=True))
        return 0
    except (OSError, ValueError, KeyError, json.JSONDecodeError, subprocess.TimeoutExpired) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
