#!/usr/bin/env python3
"""Evidence-gated lifecycle state for Codex/Hermes learned rules.

The scorer is deterministic and provider-agnostic.  It consumes a paired,
public-safe observation produced by a separate live runner; it never invokes a
model.  Only local state and generated prompt packs are mutated automatically.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
RUNTIMES = ("codex", "hermes")
STATUSES = ("candidate", "active", "degraded", "retired")
MINIMUM_PAIRS = 6


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: root must be an object")
    return value


def load_catalog(path: Path) -> dict[str, Any]:
    catalog = read_json(path)
    if catalog.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported catalog schema_version")
    rules = catalog.get("rules")
    if not isinstance(rules, list) or not rules:
        raise ValueError("catalog rules must be a non-empty list")
    seen: set[str] = set()
    for rule in rules:
        if not isinstance(rule, dict):
            raise ValueError("catalog rule must be an object")
        rule_id = rule.get("rule_id")
        if not isinstance(rule_id, str) or not rule_id or rule_id in seen:
            raise ValueError("catalog rule_id must be unique and non-empty")
        seen.add(rule_id)
        runtimes = rule.get("runtimes")
        if (not isinstance(runtimes, list) or not runtimes
                or any(runtime not in RUNTIMES for runtime in runtimes)):
            raise ValueError(f"{rule_id}: invalid runtimes")
        if not isinstance(rule.get("prompt_text"), str) or not rule["prompt_text"].strip():
            raise ValueError(f"{rule_id}: prompt_text is required")
        if rule.get("promotion_policy") not in ("confirmatory", "retire_or_degrade_only"):
            raise ValueError(f"{rule_id}: invalid promotion_policy")
    return catalog


def rule_map(catalog: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {rule["rule_id"]: rule for rule in catalog["rules"]}


def catalog_fingerprint(catalog: dict[str, Any]) -> str:
    canonical = json.dumps(catalog, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def observation_fingerprint(observation: dict[str, Any]) -> str:
    canonical = json.dumps(observation, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def new_state(catalog: dict[str, Any], experiment_id: str) -> dict[str, Any]:
    if not experiment_id:
        raise ValueError("experiment_id is required")
    rules: dict[str, Any] = {}
    for rule in catalog["rules"]:
        rules[rule["rule_id"]] = {
            runtime: {
                "status": "candidate",
                "last_eligible": None,
                "windows": [],
            }
            for runtime in rule["runtimes"]
        }
    return {
        "schema_version": SCHEMA_VERSION,
        "experiment_id": experiment_id,
        "catalog_id": catalog.get("catalog_id", "unknown"),
        "catalog_fingerprint": catalog_fingerprint(catalog),
        "pack_dir": None,
        "rules": rules,
    }


def has_active_evidence(entry: dict[str, Any]) -> bool:
    return any(
        record.get("eligible") is True
        and isinstance(record.get("score"), dict)
        and record["score"].get("status_after") == "active"
        and record["score"].get("decision_branch") in ("outcome_benefit", "cost_only_promotion")
        for record in entry.get("windows", [])
    )


def validate_state(state: dict[str, Any], catalog: dict[str, Any], experiment_id: str) -> None:
    if state.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported state schema_version")
    if state.get("experiment_id") != experiment_id:
        raise ValueError("state experiment_id mismatch")
    if state.get("catalog_id") != catalog.get("catalog_id"):
        raise ValueError("state catalog_id mismatch")
    if state.get("catalog_fingerprint") != catalog_fingerprint(catalog):
        raise ValueError("state catalog fingerprint mismatch")
    if "pack_dir" not in state:
        raise ValueError("state pack_dir binding is missing")
    pack_binding = state["pack_dir"]
    if pack_binding is not None and (
            not isinstance(pack_binding, str) or not pack_binding
            or pack_binding != pack_dir_identity(Path(pack_binding))):
        raise ValueError("state pack_dir binding is invalid")
    expected = rule_map(catalog)
    if set(state.get("rules", {})) != set(expected):
        raise ValueError("state/catalog rule mismatch")
    for rule_id, rule in expected.items():
        runtime_entries = state["rules"][rule_id]
        if set(runtime_entries) != set(rule["runtimes"]):
            raise ValueError(f"{rule_id}: state/catalog runtime mismatch")
        for runtime, entry in runtime_entries.items():
            if entry.get("status") not in STATUSES:
                raise ValueError(f"{rule_id}/{runtime}: invalid state status")
            if not isinstance(entry.get("windows"), list):
                raise ValueError(f"{rule_id}/{runtime}: windows must be a list")
            window_ids: set[str] = set()
            for record in entry["windows"]:
                if not isinstance(record, dict) or not isinstance(record.get("window_id"), str):
                    raise ValueError(f"{rule_id}/{runtime}: invalid window record")
                if record["window_id"] in window_ids:
                    raise ValueError(f"{rule_id}/{runtime}: duplicate persisted window_id")
                window_ids.add(record["window_id"])
                if (not isinstance(record.get("observation_fingerprint"), str)
                        or not isinstance(record.get("score"), dict)):
                    raise ValueError(f"{rule_id}/{runtime}: incomplete window replay record")
            last = entry.get("last_eligible")
            if last is not None and (
                    not isinstance(last, dict) or last.get("window_id") not in window_ids
                    or last.get("eligible") is not True):
                raise ValueError(f"{rule_id}/{runtime}: invalid last_eligible pointer")
            if last is not None:
                persisted = next(record for record in entry["windows"]
                                 if record["window_id"] == last["window_id"])
                if last != persisted:
                    raise ValueError(f"{rule_id}/{runtime}: last_eligible disagrees with history")
            if entry["windows"]:
                recorded_status = entry["windows"][-1]["score"].get("status_after")
                if recorded_status != entry["status"]:
                    raise ValueError(f"{rule_id}/{runtime}: status disagrees with transition history")
            elif entry["status"] != "candidate":
                raise ValueError(f"{rule_id}/{runtime}: status is not evidence-backed")
            if entry["status"] == "active" and not has_active_evidence(entry):
                raise ValueError(f"{rule_id}/{runtime}: active status is not evidence-backed")
            if entry["status"] == "active" and rule["promotion_policy"] != "confirmatory":
                raise ValueError(f"{rule_id}/{runtime}: non-confirmatory rule cannot be active")
    if pack_binding is None and any(
            entry["status"] != "candidate" or entry["windows"]
            for runtimes in state["rules"].values()
            for entry in runtimes.values()):
        raise ValueError("non-virgin state must have a pack_dir binding")


def load_state(path: Path, catalog: dict[str, Any], experiment_id: str) -> dict[str, Any]:
    if not path.is_file():
        return new_state(catalog, experiment_id)
    state = read_json(path)
    validate_state(state, catalog, experiment_id)
    return state


def pack_dir_identity(path: Path) -> str:
    return os.path.normcase(str(path.resolve()))


def bind_pack_dir(state: dict[str, Any], pack_dir: Path) -> None:
    identity = pack_dir_identity(pack_dir)
    existing = state.get("pack_dir")
    if existing is None:
        state["pack_dir"] = identity
    elif existing != identity:
        raise ValueError(
            f"pack_dir binding mismatch: expected {existing}, received {identity}")


def require_pack_dir(state: dict[str, Any], pack_dir: Path) -> None:
    existing = state.get("pack_dir")
    if existing is None:
        raise ValueError("state pack_dir is unbound; initialize or score it first")
    identity = pack_dir_identity(pack_dir)
    if existing != identity:
        raise ValueError(
            f"pack_dir binding mismatch: expected {existing}, received {identity}")


def validate_row(row: dict[str, Any], lane: str) -> None:
    case_id = row.get("case_id")
    if not isinstance(case_id, str) or not case_id:
        raise ValueError(f"{lane}: case_id is required")
    initial = row.get("initial_correct")
    final = row.get("final_correct")
    corrective = row.get("corrective_invocations")
    if initial not in (True, False, None) or final not in (True, False, None):
        raise ValueError(f"{lane}/{case_id}: correctness must be boolean or null")
    if not isinstance(corrective, int) or isinstance(corrective, bool) or corrective not in (0, 1):
        raise ValueError(f"{lane}/{case_id}: corrective_invocations must be 0 or 1")
    if initial is True and (corrective != 0 or final is not True):
        raise ValueError(f"{lane}/{case_id}: correct initial result cannot have corrective work")
    if initial is False and corrective != 1:
        raise ValueError(f"{lane}/{case_id}: incorrect initial result requires one corrective invocation")
    if initial is None and (corrective != 0 or final is not None):
        raise ValueError(f"{lane}/{case_id}: unscored initial result cannot invent corrective work")
    usage_status = row.get("usage_status")
    if usage_status not in ("EXACT", "UNSCORED"):
        raise ValueError(f"{lane}/{case_id}: invalid usage_status")
    tokens = row.get("total_tokens")
    corrective_tokens = row.get("corrective_tokens")
    if usage_status == "EXACT":
        if not isinstance(tokens, int) or isinstance(tokens, bool) or tokens < 0:
            raise ValueError(f"{lane}/{case_id}: exact total_tokens must be a non-negative integer")
        if (not isinstance(corrective_tokens, int) or isinstance(corrective_tokens, bool)
                or corrective_tokens < 0 or corrective_tokens > tokens):
            raise ValueError(f"{lane}/{case_id}: invalid exact corrective_tokens")
        if corrective == 0 and corrective_tokens != 0:
            raise ValueError(f"{lane}/{case_id}: no corrective invocation can consume corrective_tokens")
    elif tokens is not None or corrective_tokens is not None:
        raise ValueError(f"{lane}/{case_id}: unscored token fields must be null")
    seconds = row.get("duration_seconds")
    if (not isinstance(seconds, (int, float)) or isinstance(seconds, bool)
            or not math.isfinite(seconds) or seconds < 0):
        raise ValueError(f"{lane}/{case_id}: duration_seconds must be finite and non-negative")
    corrective_seconds = row.get("corrective_duration_seconds")
    if (not isinstance(corrective_seconds, (int, float)) or isinstance(corrective_seconds, bool)
            or not math.isfinite(corrective_seconds) or corrective_seconds < 0
            or corrective_seconds > seconds):
        raise ValueError(f"{lane}/{case_id}: invalid corrective_duration_seconds")
    if corrective == 0 and corrective_seconds != 0:
        raise ValueError(f"{lane}/{case_id}: no corrective invocation can consume corrective time")
    if row.get("process_status") not in ("completed", "timeout", "error"):
        raise ValueError(f"{lane}/{case_id}: invalid process_status")


def validate_observation(observation: dict[str, Any], catalog: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    if observation.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported observation schema_version")
    rule_id = observation.get("rule_id")
    runtime = observation.get("runtime")
    rules = rule_map(catalog)
    if rule_id not in rules:
        raise ValueError("observation rule_id is not in catalog")
    if runtime not in rules[rule_id]["runtimes"]:
        raise ValueError("observation runtime is not enabled for rule")
    for key in ("window_id", "binding_fingerprint"):
        if not isinstance(observation.get(key), str) or not observation[key]:
            raise ValueError(f"observation {key} is required")
    lanes: dict[str, dict[str, Any]] = {}
    for lane in ("control", "treatment"):
        value = observation.get(lane)
        rows = value.get("cases") if isinstance(value, dict) else None
        if not isinstance(rows, list) or not rows:
            raise ValueError(f"{lane}.cases must be a non-empty list")
        by_id: dict[str, Any] = {}
        for row in rows:
            if not isinstance(row, dict):
                raise ValueError(f"{lane}: case row must be an object")
            validate_row(row, lane)
            if row["case_id"] in by_id:
                raise ValueError(f"{lane}: duplicate case_id {row['case_id']}")
            by_id[row["case_id"]] = row
        lanes[lane] = by_id
    if set(lanes["control"]) != set(lanes["treatment"]):
        raise ValueError("control and treatment case ids must match exactly")
    return lanes["control"], lanes["treatment"]


def ratio(numerator: float, denominator: float) -> float | None:
    return round(numerator / denominator, 6) if denominator > 0 else None


def ratio_at_most(numerator: float, denominator: float, threshold: float) -> bool:
    return denominator > 0 and numerator <= denominator * threshold


def derive_metrics(control: dict[str, Any], treatment: dict[str, Any]) -> dict[str, Any]:
    ids = sorted(control)
    complete = all(
        isinstance(control[case_id]["initial_correct"], bool)
        and isinstance(control[case_id]["final_correct"], bool)
        and control[case_id]["process_status"] == "completed"
        and isinstance(treatment[case_id]["initial_correct"], bool)
        and isinstance(treatment[case_id]["final_correct"], bool)
        and treatment[case_id]["process_status"] == "completed"
        for case_id in ids
    )
    harmful_cases = []
    for case_id in ids:
        c = control[case_id]
        t = treatment[case_id]
        initial_comparable = all(isinstance(value, bool) for value in (
            c["initial_correct"], t["initial_correct"]))
        final_comparable = all(isinstance(value, bool) for value in (
            c["final_correct"], t["final_correct"]))
        if ((initial_comparable and (
                (not t["initial_correct"]) > (not c["initial_correct"])
                or t["corrective_invocations"] > c["corrective_invocations"]))
                or (final_comparable
                    and (not t["final_correct"]) > (not c["final_correct"]))):
            harmful_cases.append(case_id)
    exact_usage = all(
        control[case_id]["usage_status"] == "EXACT"
        and treatment[case_id]["usage_status"] == "EXACT"
        for case_id in ids
    )
    c_defects = sum(row["initial_correct"] is False for row in control.values())
    t_defects = sum(row["initial_correct"] is False for row in treatment.values())
    c_rework = sum(row["corrective_invocations"] for row in control.values())
    t_rework = sum(row["corrective_invocations"] for row in treatment.values())
    c_unresolved = sum(row["final_correct"] is False for row in control.values())
    t_unresolved = sum(row["final_correct"] is False for row in treatment.values())
    c_tokens = sum(row["total_tokens"] or 0 for row in control.values())
    t_tokens = sum(row["total_tokens"] or 0 for row in treatment.values())
    c_rework_tokens = sum(row["corrective_tokens"] or 0 for row in control.values())
    t_rework_tokens = sum(row["corrective_tokens"] or 0 for row in treatment.values())
    c_seconds = sum(float(row["duration_seconds"]) for row in control.values())
    t_seconds = sum(float(row["duration_seconds"]) for row in treatment.values())
    c_rework_seconds = sum(float(row["corrective_duration_seconds"]) for row in control.values())
    t_rework_seconds = sum(float(row["corrective_duration_seconds"]) for row in treatment.values())
    return {
        "case_ids": ids,
        "pair_count": len(ids),
        "correctness_complete": complete,
        "exact_usage": exact_usage,
        "harmful_cases": harmful_cases,
        "control_initial_defects": c_defects,
        "treatment_initial_defects": t_defects,
        "defects_prevented": c_defects - t_defects,
        "control_rework_invocations": c_rework,
        "treatment_rework_invocations": t_rework,
        "rework_invocations_prevented": c_rework - t_rework,
        "control_rework_tokens": c_rework_tokens if exact_usage else None,
        "treatment_rework_tokens": t_rework_tokens if exact_usage else None,
        "rework_tokens_prevented": c_rework_tokens - t_rework_tokens if exact_usage else None,
        "control_rework_duration_seconds": round(c_rework_seconds, 6),
        "treatment_rework_duration_seconds": round(t_rework_seconds, 6),
        "rework_duration_seconds_prevented": round(c_rework_seconds - t_rework_seconds, 6),
        "control_unresolved_defects": c_unresolved,
        "treatment_unresolved_defects": t_unresolved,
        "control_total_tokens": c_tokens if exact_usage else None,
        "treatment_total_tokens": t_tokens if exact_usage else None,
        "exact_token_ratio": ratio(t_tokens, c_tokens) if exact_usage else None,
        "control_duration_seconds": round(c_seconds, 6),
        "treatment_duration_seconds": round(t_seconds, 6),
        "latency_ratio": ratio(t_seconds, c_seconds),
    }


def cost_paths(metrics: dict[str, Any]) -> tuple[bool, bool]:
    token = (
        metrics["exact_usage"]
        and ratio_at_most(metrics["treatment_total_tokens"], metrics["control_total_tokens"], 0.95)
    )
    latency = ratio_at_most(
        metrics["treatment_duration_seconds"], metrics["control_duration_seconds"], 0.90)
    return token, latency


def combined_cost_path(previous: dict[str, Any], current: dict[str, Any]) -> bool:
    prev_token, prev_latency = cost_paths(previous)
    curr_token, curr_latency = cost_paths(current)
    token = (
        prev_token and curr_token
        and ratio_at_most(
            previous["treatment_total_tokens"] + current["treatment_total_tokens"],
            previous["control_total_tokens"] + current["control_total_tokens"], 0.95)
    )
    latency = (
        prev_latency and curr_latency
        and ratio_at_most(
            previous["treatment_duration_seconds"] + current["treatment_duration_seconds"],
            previous["control_duration_seconds"] + current["control_duration_seconds"], 0.90)
    )
    return token or latency


def evaluate_window(state: dict[str, Any], catalog: dict[str, Any],
                    observation: dict[str, Any]) -> dict[str, Any]:
    control, treatment = validate_observation(observation, catalog)
    metrics = derive_metrics(control, treatment)
    rule_id = observation["rule_id"]
    runtime = observation["runtime"]
    rule = rule_map(catalog)[rule_id]
    entry = state["rules"][rule_id][runtime]
    before = entry["status"]
    previous = entry.get("last_eligible")
    fingerprint = observation_fingerprint(observation)
    duplicate = next(
        (record for record in entry["windows"] if record.get("window_id") == observation["window_id"]),
        None,
    )
    if duplicate is not None:
        if duplicate.get("observation_fingerprint") != fingerprint:
            raise ValueError(f"conflicting duplicate window_id for {rule_id}/{runtime}: {observation['window_id']}")
        replay = dict(duplicate["score"])
        replay["idempotent_replay"] = True
        replay["state_changed"] = False
        return replay

    def finish(branch: str, after: str, reason: str, *, eligible: bool) -> dict[str, Any]:
        score = {
            "schema_version": SCHEMA_VERSION,
            "window_id": observation["window_id"],
            "rule_id": rule_id,
            "runtime": runtime,
            "binding_fingerprint": observation["binding_fingerprint"],
            "status_before": before,
            "status_after": after,
            "decision_branch": branch,
            "reason": reason,
            "state_changed": before != after,
            "idempotent_replay": False,
            "metrics": metrics,
        }
        entry["status"] = after
        record = {
            "window_id": observation["window_id"],
            "binding_fingerprint": observation["binding_fingerprint"],
            "decision_branch": branch,
            "status_after": after,
            "eligible": eligible,
            "metrics": metrics,
            "observation_fingerprint": fingerprint,
            "score": score,
        }
        entry["windows"].append(record)
        if eligible:
            entry["last_eligible"] = record
        return score

    if entry["status"] == "retired":
        return finish("retired_locked", "retired", "retired_rule_requires_new_experiment", eligible=False)
    if metrics["harmful_cases"]:
        return finish("safety_veto", "retired", "case_level_correctness_or_rework_regression", eligible=True)
    if (metrics["pair_count"] < MINIMUM_PAIRS or not metrics["correctness_complete"]
            or not metrics["exact_usage"] or not metrics["control_total_tokens"]):
        reasons = []
        if metrics["pair_count"] < MINIMUM_PAIRS:
            reasons.append("fewer_than_six_pairs")
        if not metrics["correctness_complete"]:
            reasons.append("correctness_or_process_incomplete")
        if not metrics["exact_usage"] or not metrics["control_total_tokens"]:
            reasons.append("exact_usage_incomplete")
        return finish("unscored", before, ",".join(reasons), eligible=False)

    outcome_benefit = (
        metrics["defects_prevented"] >= 1
        or metrics["rework_invocations_prevented"] >= 1
    )
    bounded_cost = ratio_at_most(
        metrics["treatment_total_tokens"], metrics["control_total_tokens"], 1.10)
    if outcome_benefit and bounded_cost:
        if rule["promotion_policy"] != "confirmatory":
            return finish("promotion_forbidden", "degraded",
                          "retrospective_rule_cannot_activate", eligible=True)
        return finish("outcome_benefit", "active",
                      "defect_or_actual_rework_prevented_with_bounded_cost", eligible=True)
    if outcome_benefit:
        second = before == "degraded" and previous and previous["decision_branch"] == "benefit_excessive_cost"
        return finish("benefit_excessive_cost", "retired" if second else "degraded",
                      "outcome_benefit_exceeds_token_overhead_cap", eligible=True)

    if before == "degraded" and previous:
        if previous["decision_branch"] == "no_outcome_benefit":
            previous_metrics = previous["metrics"]
            if previous["binding_fingerprint"] != observation["binding_fingerprint"]:
                return finish("unscored", "degraded", "cost_window_binding_drift", eligible=False)
            if set(previous_metrics["case_ids"]) & set(metrics["case_ids"]):
                return finish("unscored", "degraded", "cost_window_cases_not_disjoint", eligible=False)
            if combined_cost_path(previous_metrics, metrics):
                if rule["promotion_policy"] != "confirmatory":
                    return finish("promotion_forbidden", "degraded",
                                  "retrospective_rule_cannot_activate", eligible=True)
                return finish("cost_only_promotion", "active",
                              "two_disjoint_parity_bound_cost_windows", eligible=True)
        return finish("no_outcome_benefit", "retired",
                      "second_consecutive_eligible_degraded_window", eligible=True)
    return finish("no_outcome_benefit", "degraded",
                  "first_eligible_window_without_outcome_benefit", eligible=True)


def render_pack(state: dict[str, Any], catalog: dict[str, Any], runtime: str) -> str:
    if runtime not in RUNTIMES:
        raise ValueError(f"unsupported runtime: {runtime}")
    active = []
    for rule in sorted(catalog["rules"], key=lambda value: value["rule_id"]):
        if runtime not in rule["runtimes"]:
            continue
        entry = state["rules"][rule["rule_id"]][runtime]
        if (entry["status"] == "active" and rule["promotion_policy"] == "confirmatory"
                and has_active_evidence(entry)):
            active.append(rule)
    lines = [
        f"# Active adaptive rules — {runtime}",
        "",
        f"Experiment: `{state['experiment_id']}`. Generated from evidence-gated local state.",
        "",
    ]
    if not active:
        lines.append("No active learned rules.")
    else:
        for rule in active:
            lines.extend((f"## {rule['rule_id']}", "", rule["prompt_text"], ""))
    return "\n".join(lines).rstrip() + "\n"


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        text=True,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            os.close(descriptor)
        except OSError:
            pass
        temporary.unlink(missing_ok=True)
        raise


def atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    atomic_write_text(path, json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def write_packs(pack_dir: Path, state: dict[str, Any], catalog: dict[str, Any]) -> None:
    for runtime in RUNTIMES:
        atomic_write_text(pack_dir / f"{runtime}.md", render_pack(state, catalog, runtime))


def pending_path(state_path: Path) -> Path:
    return state_path.with_name(state_path.name + ".pending")


def prepared_path(state_path: Path) -> Path:
    return state_path.with_name(state_path.name + ".pending.prepare")


def validate_output_layout(state_path: Path, pack_dir: Path, *,
                           scorecard_path: Path | None = None,
                           protected_paths: dict[str, Path] | None = None,
                           state_writable: bool = True) -> None:
    """Reject aliases between canonical inputs and transaction outputs."""
    protected = dict(protected_paths or {})
    if not state_writable:
        protected["state"] = state_path
        protected["pending transaction"] = pending_path(state_path)
        protected["prepared transaction"] = prepared_path(state_path)

    outputs: dict[str, Path] = {
        f"{runtime} pack": pack_dir / f"{runtime}.md"
        for runtime in RUNTIMES
    }
    if state_writable:
        outputs["state"] = state_path
        outputs["pending transaction"] = pending_path(state_path)
        outputs["prepared transaction"] = prepared_path(state_path)
    if scorecard_path is not None:
        outputs["scorecard"] = scorecard_path

    resolved_outputs: dict[Path, str] = {}
    for label, path in outputs.items():
        resolved = path.resolve()
        for prior_path, prior_label in resolved_outputs.items():
            if (resolved == prior_path or resolved in prior_path.parents
                    or prior_path in resolved.parents):
                raise ValueError(f"output path collision: {label} aliases or contains {prior_label}")
        resolved_outputs[resolved] = label

    resolved_protected: dict[Path, str] = {}
    for label, path in protected.items():
        resolved = path.resolve()
        prior = resolved_protected.get(resolved)
        if prior is not None:
            continue
        resolved_protected[resolved] = label
        for output_path, output_label in resolved_outputs.items():
            if (resolved == output_path or resolved in output_path.parents
                    or output_path in resolved.parents):
                raise ValueError(
                    f"output path collision: {output_label} would overwrite or contain {label}")

    pack_root = pack_dir.resolve()
    canonical_files = {
        **protected,
        "state": state_path,
        "pending transaction": pending_path(state_path),
        "prepared transaction": prepared_path(state_path),
    }
    if scorecard_path is not None:
        canonical_files["scorecard"] = scorecard_path
    for label, path in canonical_files.items():
        resolved = path.resolve()
        if pack_root == resolved or resolved in pack_root.parents:
            raise ValueError(f"pack_dir must not alias or be nested below {label}")


def relative_output(root: Path, path: Path, label: str) -> str:
    root_resolved = root.resolve()
    try:
        relative = path.resolve().relative_to(root_resolved)
    except ValueError as exc:
        raise ValueError(f"{label} must be inside the state directory") from exc
    return relative.as_posix()


def resolve_pending_output(root: Path, relative: str, label: str) -> Path:
    if not isinstance(relative, str) or not relative:
        raise ValueError(f"pending transaction {label} is invalid")
    path = (root / Path(relative)).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"pending transaction {label} escapes state directory") from exc
    return path


def render_quarantine_pack(runtime: str, window_id: str) -> str:
    return (
        f"# Active adaptive rules — {runtime}\n\n"
        f"Lifecycle transaction `{window_id}` is pending recovery.\n\n"
        "No active learned rules.\n"
    )


def orphan_quarantine_runtimes(pack_dir: Path) -> list[str]:
    orphaned = []
    for runtime in RUNTIMES:
        path = pack_dir / f"{runtime}.md"
        try:
            text = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            continue
        if ("Lifecycle transaction `" in text
                and "is pending recovery." in text
                and "No active learned rules." in text):
            orphaned.append(runtime)
    return orphaned


def apply_pending_transaction(state_path: Path, pending: dict[str, Any],
                              catalog: dict[str, Any], experiment_id: str,
                              protected_paths: dict[str, Path] | None = None) -> None:
    if pending.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported pending transaction schema_version")
    if pending.get("catalog_fingerprint") != catalog_fingerprint(catalog):
        raise ValueError("pending transaction catalog fingerprint mismatch")
    state = pending.get("state")
    score = pending.get("score")
    if not isinstance(state, dict) or not isinstance(score, dict):
        raise ValueError("pending transaction state and score are required")
    validate_state(state, catalog, experiment_id)
    runtime = score.get("runtime")
    if runtime not in RUNTIMES:
        raise ValueError("pending transaction runtime is invalid")
    root = state_path.parent.resolve()
    pack_dir = resolve_pending_output(root, pending.get("pack_dir"), "pack_dir")
    scorecard = resolve_pending_output(root, pending.get("scorecard"), "scorecard")
    require_pack_dir(state, pack_dir)
    validate_output_layout(
        state_path,
        pack_dir,
        scorecard_path=scorecard,
        protected_paths=protected_paths,
    )

    # Quarantine first: any interruption after the journal exists leaves the
    # changed runtime with zero learned rules until recovery completes.
    atomic_write_text(pack_dir / f"{runtime}.md", render_quarantine_pack(runtime, score["window_id"]))
    activating = score.get("status_before") != "active" and score.get("status_after") == "active"
    if activating:
        atomic_write_json(state_path, state)
        write_packs(pack_dir, state, catalog)
    else:
        atomic_write_text(pack_dir / f"{runtime}.md", render_pack(state, catalog, runtime))
        for other in RUNTIMES:
            if other != runtime:
                atomic_write_text(pack_dir / f"{other}.md", render_pack(state, catalog, other))
        atomic_write_json(state_path, state)
    atomic_write_json(scorecard, score)


def recover_pending(state_path: Path, catalog: dict[str, Any], experiment_id: str,
                    protected_paths: dict[str, Path] | None = None) -> bool:
    journal = pending_path(state_path)
    prepared = prepared_path(state_path)
    existing = [path for path in (journal, prepared) if path.is_file()]
    if not existing:
        return False
    if len(existing) != 1:
        raise ValueError("both pending and prepared transaction journals exist")
    marker = existing[0]
    pending = read_json(marker)
    apply_pending_transaction(
        state_path, pending, catalog, experiment_id, protected_paths=protected_paths)
    marker.unlink()
    return True


def write_scored_state(args: argparse.Namespace, score: dict[str, Any],
                       state: dict[str, Any], catalog: dict[str, Any]) -> None:
    """Journal and apply one lifecycle transition with mandatory recovery."""
    root = args.state.parent.resolve()
    protected = {
        label: path
        for label, path in (
            ("catalog", getattr(args, "catalog", None)),
            ("observation", getattr(args, "observation", None)),
        )
        if path is not None
    }
    validate_output_layout(
        args.state,
        args.pack_dir,
        scorecard_path=args.scorecard,
        protected_paths=protected,
    )
    require_pack_dir(state, args.pack_dir)
    pending = {
        "schema_version": SCHEMA_VERSION,
        "catalog_fingerprint": catalog_fingerprint(catalog),
        "state": state,
        "score": score,
        "pack_dir": relative_output(root, args.pack_dir, "pack_dir"),
        "scorecard": relative_output(root, args.scorecard, "scorecard"),
    }
    journal = pending_path(args.state)
    prepared = prepared_path(args.state)
    if journal.exists() or prepared.exists():
        raise ValueError(f"pending transaction requires recovery: {args.state}")
    # Quarantine before publishing the journal.  If either write fails, a
    # published pending transaction can never coexist with a consumable old
    # pack for the runtime whose lifecycle decision just changed.
    atomic_write_text(
        args.pack_dir / f"{score['runtime']}.md",
        render_quarantine_pack(score["runtime"], score["window_id"]),
    )
    atomic_write_json(prepared, pending)
    os.replace(prepared, journal)
    recover_pending(
        args.state, catalog, state["experiment_id"], protected_paths=protected)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init", help="Create candidate state and empty packs.")
    init.add_argument("--catalog", type=Path, required=True)
    init.add_argument("--state", type=Path, required=True)
    init.add_argument("--pack-dir", type=Path, required=True)
    init.add_argument("--experiment-id", required=True)
    score = sub.add_parser("score", help="Score one paired window and update local state/packs.")
    score.add_argument("--catalog", type=Path, required=True)
    score.add_argument("--state", type=Path, required=True)
    score.add_argument("--observation", type=Path, required=True)
    score.add_argument("--scorecard", type=Path, required=True)
    score.add_argument("--pack-dir", type=Path, required=True)
    score.add_argument("--experiment-id", default="adaptive_rule_lifecycle_v1_20260716")
    score.add_argument("--dry-run", action="store_true")
    pack = sub.add_parser("pack", help="Regenerate runtime packs from canonical state.")
    pack.add_argument("--catalog", type=Path, required=True)
    pack.add_argument("--state", type=Path, required=True)
    pack.add_argument("--pack-dir", type=Path, required=True)
    pack.add_argument("--experiment-id", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        catalog = load_catalog(args.catalog)
        if args.command == "init":
            validate_output_layout(
                args.state,
                args.pack_dir,
                protected_paths={"catalog": args.catalog},
            )
            if (args.state.exists() or pending_path(args.state).exists()
                    or prepared_path(args.state).exists()):
                raise ValueError(f"state or transaction journal already exists: {args.state}")
            orphaned = orphan_quarantine_runtimes(args.pack_dir)
            if orphaned:
                raise ValueError(f"orphan quarantine blocks pack generation: {','.join(orphaned)}")
            state = new_state(catalog, args.experiment_id)
            bind_pack_dir(state, args.pack_dir)
            write_packs(args.pack_dir, state, catalog)
            atomic_write_json(args.state, state)
            return 0
        experiment_id = args.experiment_id
        protected = {"catalog": args.catalog}
        if args.command == "score":
            protected["observation"] = args.observation
            validate_output_layout(
                args.state,
                args.pack_dir,
                scorecard_path=args.scorecard,
                protected_paths=protected,
            )
            if (args.dry_run and (pending_path(args.state).is_file()
                                  or prepared_path(args.state).is_file())):
                raise ValueError(
                    "dry-run refuses to recover a pending transaction; run a non-dry lifecycle command first")
        else:
            validate_output_layout(
                args.state,
                args.pack_dir,
                protected_paths=protected,
                state_writable=False,
            )
        recovered = recover_pending(
            args.state, catalog, experiment_id, protected_paths=protected)
        if not recovered:
            orphaned = orphan_quarantine_runtimes(args.pack_dir)
            if orphaned:
                raise ValueError(f"orphan quarantine blocks pack generation: {','.join(orphaned)}")
        if args.command == "pack" and not args.state.is_file():
            raise ValueError(f"state does not exist: {args.state}")
        state = load_state(args.state, catalog, experiment_id)
        if args.command == "pack":
            require_pack_dir(state, args.pack_dir)
            write_packs(args.pack_dir, state, catalog)
            return 0
        bind_pack_dir(state, args.pack_dir)
        observation = read_json(args.observation)
        score = evaluate_window(state, catalog, observation)
        if args.dry_run:
            print(json.dumps(score, ensure_ascii=False))
            return 0
        write_scored_state(args, score, state, catalog)
        print(json.dumps(score, ensure_ascii=False))
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
