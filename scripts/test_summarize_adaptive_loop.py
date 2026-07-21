#!/usr/bin/env python3
"""Regression tests for summarize_adaptive_loop.py."""

import importlib.util
import hashlib
import json
import tempfile
from pathlib import Path


REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "summarize_adaptive_loop.py"
CATALOG = REPO / "benchmarks" / "adaptive_loop" / "rules_v1.json"
BINDING = REPO / "benchmarks" / "adaptive_loop" / "final_binding_v1.json"
_spec = importlib.util.spec_from_file_location("summarize_adaptive_loop", SCRIPT)
summary = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(summary)


def write(path: Path, value: dict) -> Path:
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def binding() -> dict:
    return json.loads(BINDING.read_text(encoding="utf-8"))


def row(case_id: str) -> dict:
    return {"case_id": case_id, "initial_correct": True, "final_correct": True,
            "corrective_invocations": 0, "usage_status": "EXACT", "total_tokens": 10,
            "corrective_tokens": 0, "duration_seconds": 1.0,
            "corrective_duration_seconds": 0.0, "process_status": "completed"}


def observation(runtime: str) -> dict:
    rows = [row(f"C{i}") for i in range(6)]
    return {"schema_version": 1, "window_id": f"window-{runtime}",
            "rule_id": "activation_payload_only_v1", "runtime": runtime,
            "binding_id": binding()["experiment_id"],
            "binding_fingerprint": binding()["parity_fingerprints"][runtime],
            "control": {"cases": rows}, "treatment": {"cases": [dict(item) for item in rows]}}


def scorecard(observation_value: dict) -> dict:
    control = {item["case_id"]: item for item in observation_value["control"]["cases"]}
    treatment = {item["case_id"]: item for item in observation_value["treatment"]["cases"]}
    return {"runtime": observation_value["runtime"], "window_id": observation_value["window_id"],
            "binding_fingerprint": observation_value["binding_fingerprint"], "decision_branch": "unscored",
            "reason": "test", "status_after": "candidate",
            "metrics": summary.derive_metrics(control, treatment)}


def fixture(root: Path):
    observations = {runtime: write(root / f"{runtime}.json", observation(runtime)) for runtime in ("codex", "hermes")}
    scores = {runtime: write(root / f"{runtime}-score.json", scorecard(json.loads(path.read_text())))
              for runtime, path in observations.items()}
    historic = write(root / "historic.json", {"runtime": "hermes", "preregistration_id": "historic", "metrics": {"passed": True}})
    return write(root / "binding.json", binding()), observations, scores, [historic]


def test_render_binds_metrics_to_frozen_observation():
    with tempfile.TemporaryDirectory() as tmp:
        binding_path, observations, scores, historic = fixture(Path(tmp))
        result = summary.render(binding_path, CATALOG, observations, scores, historic)
    assert result["confirmatory"]["hermes"]["decision_branch"] == "unscored"


def test_render_rejects_forged_metrics_and_wrong_parity():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        binding_path, observations, scores, historic = fixture(root)
        forged = json.loads(scores["codex"].read_text())
        forged["metrics"]["defects_prevented"] = 99
        write(scores["codex"], forged)
        try:
            summary.render(binding_path, CATALOG, observations, scores, historic)
        except ValueError as exc:
            assert "not derived" in str(exc)
        else:
            raise AssertionError("forged metrics were accepted")
        write(scores["codex"], scorecard(json.loads(observations["codex"].read_text())))
        wrong = json.loads(observations["codex"].read_text())
        wrong["binding_fingerprint"] = "0" * 64
        write(observations["codex"], wrong)
        try:
            summary.render(binding_path, CATALOG, observations, scores, historic)
        except ValueError as exc:
            assert "mismatch" in str(exc)
        else:
            raise AssertionError("wrong binding parity was accepted")


def test_render_rejects_tampered_or_incomplete_binding():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        binding_path, observations, scores, historic = fixture(root)
        tampered = json.loads(binding_path.read_text())
        tampered["experiment_id"] = "tampered-binding"
        write(binding_path, tampered)
        try:
            summary.render(binding_path, CATALOG, observations, scores, historic)
        except ValueError as exc:
            assert "fingerprint" in str(exc)
        else:
            raise AssertionError("binding field tampering was accepted")

        incomplete = binding()
        incomplete.pop("instrument_commit")
        unsigned = {key: value for key, value in incomplete.items() if key != "binding_fingerprint"}
        incomplete["binding_fingerprint"] = hashlib.sha256(json.dumps(
            unsigned, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()
        write(binding_path, incomplete)
        try:
            summary.render(binding_path, CATALOG, observations, scores, historic)
        except ValueError as exc:
            assert "fields are invalid" in str(exc)
        else:
            raise AssertionError("incomplete binding with forged fingerprint was accepted")


def test_render_rejects_rehashed_binding_with_stale_runtime_parity():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        binding_path, observations, scores, historic = fixture(root)
        forged = json.loads(binding_path.read_text())
        forged["runtime_bindings"]["codex"]["identity"]["version"] = "tampered-but-well-formed"
        unsigned = {key: value for key, value in forged.items() if key != "binding_fingerprint"}
        forged["binding_fingerprint"] = hashlib.sha256(json.dumps(
            unsigned, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()
        write(binding_path, forged)
        try:
            summary.render(binding_path, CATALOG, observations, scores, historic)
        except ValueError as exc:
            assert "parity fingerprint drifted" in str(exc)
        else:
            raise AssertionError("rehashed binding with stale parity was accepted")


if __name__ == "__main__":
    for test in (test_render_binds_metrics_to_frozen_observation, test_render_rejects_forged_metrics_and_wrong_parity,
                 test_render_rejects_tampered_or_incomplete_binding,
                 test_render_rejects_rehashed_binding_with_stale_runtime_parity):
        test()
        print(f"ok {test.__name__}")
