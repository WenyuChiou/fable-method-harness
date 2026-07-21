#!/usr/bin/env python3
"""Render a public-safe aggregate from frozen adaptive-loop evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from adaptive_rule_lifecycle import derive_metrics, load_catalog, validate_observation
from run_adaptive_loop_experiment import (
    FROZEN_INPUTS,
    canonical_json,
    parity_payload,
    sha256_bytes,
    validate_binding_structure,
)

SCHEMA_VERSION = 1
REPO = Path(__file__).resolve().parent.parent
ABSOLUTE_PATH = re.compile(r"(?:[A-Za-z]:[\\/]|/(?:Users|home|tmp)/)")


def read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path.name}: root must be an object")
    return value


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_frozen_binding(binding: dict[str, Any]) -> None:
    """Ensure every scoring input and runtime parity claim matches the binding."""
    validate_binding_structure(binding)
    for relative in FROZEN_INPUTS:
        if sha256_file(REPO / relative) != binding["frozen_input_sha256"][relative]:
            raise ValueError(f"frozen scoring input drifted: {relative}")
    for runtime in ("codex", "hermes"):
        expected = sha256_bytes(canonical_json(parity_payload(binding, runtime)).encode("utf-8"))
        if binding["parity_fingerprints"][runtime] != expected:
            raise ValueError(f"binding parity fingerprint drifted: {runtime}")


def require_scorecard(value: dict[str, Any], runtime: str) -> dict[str, Any]:
    required = {"runtime", "decision_branch", "reason", "status_after", "metrics"}
    if not required <= set(value) or value.get("runtime") != runtime:
        raise ValueError(f"{runtime}: invalid lifecycle scorecard")
    metrics = value["metrics"]
    if not isinstance(metrics, dict):
        raise ValueError(f"{runtime}: scorecard metrics must be an object")
    return value


def historical_summary(path: Path) -> dict[str, Any]:
    value = read_object(path)
    metrics = value.get("metrics")
    if not isinstance(metrics, dict) or not isinstance(value.get("runtime"), str):
        raise ValueError(f"{path.name}: invalid historical activation observation")
    return {
        "source_sha256": sha256_file(path),
        "runtime": value["runtime"],
        "preregistration_id": value.get("preregistration_id"),
        "metrics": metrics,
    }


def render(binding_path: Path, catalog_path: Path, observations: dict[str, Path], scorecards: dict[str, Path],
    historical: list[Path]) -> dict[str, Any]:
    binding = read_object(binding_path)
    validate_frozen_binding(binding)
    if binding.get("status") != "frozen_before_live_calls":
        raise ValueError("binding is not frozen")
    catalog = load_catalog(catalog_path)
    frozen_catalog = binding.get("frozen_input_sha256", {}).get("benchmarks/adaptive_loop/rules_v1.json")
    if frozen_catalog != sha256_file(catalog_path):
        raise ValueError("catalog differs from the frozen binding")
    runtime_results: dict[str, Any] = {}
    for runtime in ("codex", "hermes"):
        observation = read_object(observations[runtime])
        score = require_scorecard(read_object(scorecards[runtime]), runtime)
        if (observation.get("runtime") != runtime or score.get("window_id") != observation.get("window_id")
                or observation.get("binding_id") != binding.get("experiment_id")
                or observation.get("binding_fingerprint") != binding.get("parity_fingerprints", {}).get(runtime)
                or score.get("binding_fingerprint") != observation.get("binding_fingerprint")):
            raise ValueError(f"{runtime}: observation/scorecard mismatch")
        control, treatment = validate_observation(observation, catalog)
        if score["metrics"] != derive_metrics(control, treatment):
            raise ValueError(f"{runtime}: scorecard metrics are not derived from observation")
        runtime_results[runtime] = {
            "observation_sha256": sha256_file(observations[runtime]),
            "scorecard_sha256": sha256_file(scorecards[runtime]),
            "decision_branch": score["decision_branch"],
            "reason": score["reason"],
            "status_after": score["status_after"],
            "metrics": score["metrics"],
        }
    result = {
        "schema_version": SCHEMA_VERSION,
        "binding_fingerprint": binding.get("binding_fingerprint"),
        "binding_sha256": sha256_file(binding_path),
        "claim_boundary": "Results apply only to the frozen binding, cases, runtime identities, models, and token semantics.",
        "confirmatory": runtime_results,
        "retrospective_negative_control": [historical_summary(path) for path in historical],
        "historical_development_rework": {
            "status": "UNSCORED",
            "reason": "The preregistered redacted session aggregate was unavailable; chat content was not used as a substitute.",
        },
    }
    encoded = json.dumps(result, ensure_ascii=False, sort_keys=True)
    if ABSOLUTE_PATH.search(encoded):
        raise ValueError("public aggregate contains an absolute local path")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binding", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--codex-observation", type=Path, required=True)
    parser.add_argument("--hermes-observation", type=Path, required=True)
    parser.add_argument("--codex-scorecard", type=Path, required=True)
    parser.add_argument("--hermes-scorecard", type=Path, required=True)
    parser.add_argument("--historical", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = render(
            args.binding,
            args.catalog,
            {"codex": args.codex_observation, "hermes": args.hermes_observation},
            {"codex": args.codex_scorecard, "hermes": args.hermes_scorecard},
            args.historical,
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"output": str(args.output), "binding_fingerprint": result["binding_fingerprint"]}))
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
