#!/usr/bin/env python3
"""Regression tests for adaptive_rule_lifecycle.py.

Dual-runnable:
    python scripts/test_adaptive_rule_lifecycle.py
    python -m pytest scripts/test_adaptive_rule_lifecycle.py
"""

import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "adaptive_rule_lifecycle.py"
CATALOG = REPO / "benchmarks" / "adaptive_loop" / "rules_v1.json"
DESIGN = REPO / "benchmarks" / "adaptive_loop" / "preregistration_design_v1.json"

_spec = importlib.util.spec_from_file_location("adaptive_rule_lifecycle", SCRIPT)
arl = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(arl)


def row(case_id, *, correct=True, final=True, exact=True, tokens=100, seconds=1.0):
    corrective = 0 if correct else 1
    corrective_tokens = tokens // 2 if corrective and exact else (0 if exact else None)
    corrective_seconds = seconds / 2 if corrective else 0.0
    return {
        "case_id": case_id,
        "initial_correct": correct,
        "corrective_invocations": corrective,
        "final_correct": final if not correct else True,
        "usage_status": "EXACT" if exact else "UNSCORED",
        "total_tokens": tokens if exact else None,
        "corrective_tokens": corrective_tokens,
        "duration_seconds": seconds,
        "corrective_duration_seconds": corrective_seconds,
        "process_status": "completed",
    }


def window(*, rule="activation_payload_only_v1", runtime="codex", window_id="w1",
           binding="binding-a", ids=None, control_bad=0, treatment_bad=0,
           control_tokens=100, treatment_tokens=100, control_seconds=1.0,
           treatment_seconds=1.0, exact=True, treatment_unresolved=0):
    ids = ids or [f"C{i}" for i in range(6)]
    control = []
    treatment = []
    for index, case_id in enumerate(ids):
        c_bad = index < control_bad
        t_bad = index < treatment_bad
        control.append(row(case_id, correct=not c_bad, final=True,
                           exact=exact, tokens=control_tokens, seconds=control_seconds))
        treatment.append(row(case_id, correct=not t_bad,
                             final=not (t_bad and index < treatment_unresolved),
                             exact=exact, tokens=treatment_tokens,
                             seconds=treatment_seconds))
    return {
        "schema_version": 1,
        "window_id": window_id,
        "rule_id": rule,
        "runtime": runtime,
        "binding_fingerprint": binding,
        "control": {"cases": control},
        "treatment": {"cases": treatment},
    }


def state_and_catalog():
    catalog = arl.load_catalog(CATALOG)
    return arl.new_state(catalog, "test-experiment"), catalog


def apply(state, catalog, observation):
    score = arl.evaluate_window(state, catalog, observation)
    return score, state


def test_new_state_is_runtime_scoped_and_candidate_rules_are_not_packed():
    state, catalog = state_and_catalog()
    assert state["rules"]["activation_payload_only_v1"]["codex"]["status"] == "candidate"
    assert state["rules"]["activation_payload_only_v1"]["hermes"]["status"] == "candidate"
    assert "No active learned rules" in arl.render_pack(state, catalog, "codex")


def test_catalog_is_an_exact_projection_of_preregistered_rules():
    catalog = arl.load_catalog(CATALOG)
    design = json.loads(DESIGN.read_text(encoding="utf-8"))
    expected_policy = {
        "confirmatory_paired": "confirmatory",
        "retrospective_negative_control": "retire_or_degrade_only",
    }
    expected = {
        rule["rule_id"]: (
            rule["runtimes"], rule["prompt_text"], expected_policy[rule["evidence_lane"]]
        )
        for rule in design["rules_under_test"]
    }
    actual = {
        rule["rule_id"]: (rule["runtimes"], rule["prompt_text"], rule["promotion_policy"])
        for rule in catalog["rules"]
    }
    assert actual == expected


def test_correctness_and_real_rework_benefit_activate_with_bounded_cost():
    state, catalog = state_and_catalog()
    score, _ = apply(state, catalog, window(control_bad=2, treatment_bad=0,
                                             treatment_tokens=110))
    assert score["decision_branch"] == "outcome_benefit"
    assert score["status_after"] == "active"
    assert score["metrics"]["defects_prevented"] == 2
    assert score["metrics"]["rework_invocations_prevented"] == 2
    assert score["metrics"]["rework_tokens_prevented"] == 100
    assert score["metrics"]["rework_duration_seconds_prevented"] == 1.0
    pack = arl.render_pack(state, catalog, "codex")
    assert "activation_payload_only_v1" in pack
    assert "activation_payload_only_v1" not in arl.render_pack(state, catalog, "hermes")


def test_observable_harm_retires_even_when_token_usage_is_missing():
    state, catalog = state_and_catalog()
    entry = state["rules"]["activation_payload_only_v1"]["codex"]
    entry["status"] = "active"
    score, _ = apply(state, catalog, window(treatment_bad=1, exact=False))
    assert score["decision_branch"] == "safety_veto"
    assert score["status_after"] == "retired"
    assert "activation_payload_only_v1" not in arl.render_pack(state, catalog, "codex")


def test_missing_usage_without_harm_is_unscored_and_preserves_state():
    state, catalog = state_and_catalog()
    entry = state["rules"]["activation_payload_only_v1"]["codex"]
    entry["status"] = "active"
    score, _ = apply(state, catalog, window(exact=False))
    assert score["decision_branch"] == "unscored"
    assert score["status_after"] == "active"


def test_outcome_benefit_over_ten_percent_cost_degrades_then_retires():
    state, catalog = state_and_catalog()
    first, _ = apply(state, catalog, window(window_id="w1", control_bad=1,
                                            treatment_bad=0, treatment_tokens=111))
    assert first["decision_branch"] == "benefit_excessive_cost"
    assert first["status_after"] == "degraded"
    second, _ = apply(state, catalog, window(window_id="w2", ids=[f"D{i}" for i in range(6)],
                                             control_bad=1, treatment_bad=0,
                                             treatment_tokens=111))
    assert second["status_after"] == "retired"


def test_no_benefit_degrades_then_retires():
    state, catalog = state_and_catalog()
    first, _ = apply(state, catalog, window(window_id="w1"))
    assert first["decision_branch"] == "no_outcome_benefit"
    assert first["status_after"] == "degraded"
    second, _ = apply(state, catalog, window(window_id="w2", ids=[f"D{i}" for i in range(6)]))
    assert second["status_after"] == "retired"


def test_two_disjoint_parity_bound_windows_can_promote_token_only_rule():
    state, catalog = state_and_catalog()
    first, _ = apply(state, catalog, window(window_id="w1", treatment_tokens=95))
    assert first["status_after"] == "degraded"
    second, _ = apply(state, catalog, window(window_id="w2", ids=[f"D{i}" for i in range(6)],
                                             treatment_tokens=95))
    assert second["decision_branch"] == "cost_only_promotion"
    assert second["status_after"] == "active"


def test_cost_only_binding_drift_is_unscored_and_preserves_degraded():
    state, catalog = state_and_catalog()
    apply(state, catalog, window(window_id="w1", treatment_tokens=95))
    second, _ = apply(state, catalog, window(window_id="w2", binding="binding-b",
                                             ids=[f"D{i}" for i in range(6)],
                                             treatment_tokens=95))
    assert second["decision_branch"] == "unscored"
    assert second["reason"] == "cost_window_binding_drift"
    assert second["status_after"] == "degraded"


def test_binding_drift_without_cost_savings_also_preserves_degraded():
    state, catalog = state_and_catalog()
    apply(state, catalog, window(window_id="w1"))
    second, _ = apply(state, catalog, window(window_id="w2", binding="binding-b",
                                             ids=[f"D{i}" for i in range(6)]))
    assert second["decision_branch"] == "unscored"
    assert second["reason"] == "cost_window_binding_drift"
    assert second["status_after"] == "degraded"


def test_reused_cost_only_cases_are_unscored_not_fake_replication():
    state, catalog = state_and_catalog()
    apply(state, catalog, window(window_id="w1", treatment_tokens=95))
    second, _ = apply(state, catalog, window(window_id="w2", treatment_tokens=95))
    assert second["reason"] == "cost_window_cases_not_disjoint"
    assert second["status_after"] == "degraded"


def test_reused_no_savings_cases_are_also_unscored():
    state, catalog = state_and_catalog()
    apply(state, catalog, window(window_id="w1"))
    second, _ = apply(state, catalog, window(window_id="w2"))
    assert second["reason"] == "cost_window_cases_not_disjoint"
    assert second["status_after"] == "degraded"


def test_retired_rule_cannot_resurrect_without_new_experiment():
    state, catalog = state_and_catalog()
    entry = state["rules"]["activation_payload_only_v1"]["codex"]
    entry["status"] = "retired"
    score, _ = apply(state, catalog, window(control_bad=2, treatment_bad=0))
    assert score["decision_branch"] == "retired_locked"
    assert score["status_after"] == "retired"


def test_identical_window_replay_is_idempotent_without_second_transition():
    state, catalog = state_and_catalog()
    observation = window(window_id="same")
    first, _ = apply(state, catalog, observation)
    assert first["status_after"] == "degraded"
    second, _ = apply(state, catalog, observation)
    assert second["idempotent_replay"] is True
    assert second["state_changed"] is False
    assert second["status_after"] == "degraded"
    assert state["rules"]["activation_payload_only_v1"]["codex"]["status"] == "degraded"
    assert len(state["rules"]["activation_payload_only_v1"]["codex"]["windows"]) == 1


def test_duplicate_window_id_with_changed_payload_is_rejected():
    state, catalog = state_and_catalog()
    apply(state, catalog, window(window_id="same"))
    changed = window(window_id="same", binding="different")
    try:
        apply(state, catalog, changed)
    except ValueError as exc:
        assert "conflicting duplicate window_id" in str(exc)
    else:
        raise AssertionError("changed duplicate window was accepted")


def test_catalog_prompt_drift_invalidates_persisted_state():
    state, catalog = state_and_catalog()
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "state.json"
        path.write_text(json.dumps(state), encoding="utf-8")
        changed = json.loads(json.dumps(catalog))
        changed["rules"][0]["prompt_text"] += " changed"
        try:
            arl.validate_state(state, changed, "test-experiment")
        except ValueError as exc:
            assert "catalog fingerprint" in str(exc)
        else:
            raise AssertionError("catalog drift reused an old active state")


def test_pack_defensively_excludes_non_confirmatory_rule_even_if_state_is_tampered():
    state, catalog = state_and_catalog()
    state["rules"]["activation_envelope_trigger_v0"]["codex"]["status"] = "active"
    assert "activation_envelope_trigger_v0" not in arl.render_pack(state, catalog, "codex")


def test_evidence_free_active_state_is_rejected_and_not_packed():
    state, catalog = state_and_catalog()
    state["rules"]["activation_payload_only_v1"]["codex"]["status"] = "active"
    try:
        arl.validate_state(state, catalog, "test-experiment")
    except ValueError as exc:
        assert "evidence-backed" in str(exc)
    else:
        raise AssertionError("evidence-free active state passed validation")
    assert "activation_payload_only_v1" not in arl.render_pack(state, catalog, "codex")


def test_last_eligible_cannot_disagree_with_append_only_history():
    state, catalog = state_and_catalog()
    apply(state, catalog, window(control_bad=1, treatment_bad=0))
    corrupted = json.loads(json.dumps(state))
    corrupted["rules"]["activation_payload_only_v1"]["codex"]["last_eligible"]["metrics"]["defects_prevented"] = 999
    try:
        arl.validate_state(corrupted, catalog, "test-experiment")
    except ValueError as exc:
        assert "last_eligible disagrees" in str(exc)
    else:
        raise AssertionError("corrupted last_eligible was trusted")


def test_case_level_harm_retires_even_when_aggregate_defects_improve():
    state, catalog = state_and_catalog()
    observation = window(control_bad=2, treatment_bad=0)
    treatment = observation["treatment"]["cases"]
    treatment[2] = row("C2", correct=False, final=True)
    score, _ = apply(state, catalog, observation)
    assert score["metrics"]["defects_prevented"] == 1
    assert score["metrics"]["harmful_cases"] == ["C2"]
    assert score["status_after"] == "retired"


def test_new_unresolved_defect_triggers_safety_veto():
    state, catalog = state_and_catalog()
    observation = window(control_bad=1, treatment_bad=1)
    observation["treatment"]["cases"][0]["final_correct"] = False
    score, _ = apply(state, catalog, observation)
    assert score["status_after"] == "retired"
    assert score["metrics"]["treatment_unresolved_defects"] == 1


def test_more_treatment_rework_retires_even_when_corrective_result_is_unscored():
    state, catalog = state_and_catalog()
    observation = window(treatment_bad=1, exact=False)
    treatment = observation["treatment"]["cases"][0]
    treatment["final_correct"] = None
    treatment["process_status"] = "timeout"
    score, _ = apply(state, catalog, observation)
    assert score["decision_branch"] == "safety_veto"
    assert score["status_after"] == "retired"
    assert score["metrics"]["harmful_cases"] == ["C0"]
    assert score["metrics"]["treatment_rework_invocations"] == 1
    assert score["metrics"]["exact_usage"] is False
    assert score["metrics"]["correctness_complete"] is False


def test_rework_difference_is_not_harm_when_initial_pair_is_not_comparable():
    state, catalog = state_and_catalog()
    observation = window(treatment_bad=1, exact=False)
    control = observation["control"]["cases"][0]
    control.update(
        initial_correct=None,
        final_correct=None,
        process_status="error",
    )
    treatment = observation["treatment"]["cases"][0]
    treatment.update(
        final_correct=None,
        process_status="timeout",
    )
    score, _ = apply(state, catalog, observation)
    assert score["decision_branch"] == "unscored"
    assert score["status_after"] == "candidate"
    assert score["metrics"]["harmful_cases"] == []


def test_negative_control_policy_cannot_activate_from_retrospective_evidence():
    state, catalog = state_and_catalog()
    observation = window(rule="activation_envelope_trigger_v0",
                         control_bad=2, treatment_bad=0)
    score, _ = apply(state, catalog, observation)
    assert score["decision_branch"] == "promotion_forbidden"
    assert score["status_after"] == "degraded"


def test_invalid_corrective_contract_is_rejected():
    state, catalog = state_and_catalog()
    observation = window()
    observation["treatment"]["cases"][0]["initial_correct"] = False
    observation["treatment"]["cases"][0]["corrective_invocations"] = 0
    try:
        apply(state, catalog, observation)
    except ValueError as exc:
        assert "corrective" in str(exc)
    else:
        raise AssertionError("invalid corrective contract accepted")


def test_cli_dry_run_writes_nothing():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        observation = root / "window.json"
        observation.write_text(json.dumps(window(control_bad=1, treatment_bad=0)), encoding="utf-8")
        state = root / "state.json"
        scorecard = root / "scorecard.json"
        packs = root / "packs"
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "score", "--catalog", str(CATALOG),
             "--state", str(state), "--observation", str(observation),
             "--scorecard", str(scorecard), "--pack-dir", str(packs), "--dry-run"],
            capture_output=True, text=True, encoding="utf-8", timeout=30)
        assert proc.returncode == 0, proc.stderr
        assert json.loads(proc.stdout)["status_after"] == "active"
        assert not state.exists()
        assert not scorecard.exists()
        assert not packs.exists()


def test_cli_score_updates_state_scorecard_and_runtime_packs():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        observation = root / "window.json"
        observation.write_text(json.dumps(window(control_bad=1, treatment_bad=0)), encoding="utf-8")
        state = root / "state.json"
        scorecard = root / "scorecard.json"
        packs = root / "packs"
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "score", "--catalog", str(CATALOG),
             "--state", str(state), "--observation", str(observation),
             "--scorecard", str(scorecard), "--pack-dir", str(packs)],
            capture_output=True, text=True, encoding="utf-8", timeout=30)
        assert proc.returncode == 0, proc.stderr
        assert state.is_file() and scorecard.is_file()
        persisted = json.loads(state.read_text(encoding="utf-8"))
        assert persisted["pack_dir"] == arl.pack_dir_identity(packs)
        assert "activation_payload_only_v1" in (packs / "codex.md").read_text(encoding="utf-8")
        assert "No active learned rules" in (packs / "hermes.md").read_text(encoding="utf-8")


def test_cli_pack_requires_matching_experiment_and_regenerates_packs():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        state, catalog = state_and_catalog()
        state_path = root / "state.json"
        packs = root / "packs"
        arl.bind_pack_dir(state, packs)
        state_path.write_text(json.dumps(state), encoding="utf-8")
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "pack", "--catalog", str(CATALOG),
             "--state", str(state_path), "--pack-dir", str(packs),
             "--experiment-id", "test-experiment"],
            capture_output=True, text=True, encoding="utf-8", timeout=30)
        assert proc.returncode == 0, proc.stderr
        assert (packs / "codex.md").is_file()


def test_cli_init_refuses_to_overwrite_existing_learning_state():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        state = root / "state.json"
        state.write_text("{}", encoding="utf-8")
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "init", "--catalog", str(CATALOG),
             "--state", str(state), "--pack-dir", str(root / "packs"),
             "--experiment-id", "new"],
            capture_output=True, text=True, encoding="utf-8", timeout=30)
        assert proc.returncode == 2
        assert "already exists" in proc.stderr
        assert state.read_text(encoding="utf-8") == "{}"


def test_atomic_write_preserves_legacy_fixed_sidecar_path():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        target = root / "state.json"
        legacy_sidecar = root / "state.json.tmp"
        legacy_sidecar.write_text("canonical-input", encoding="utf-8")
        arl.atomic_write_text(target, "new-state")
        assert target.read_text(encoding="utf-8") == "new-state"
        assert legacy_sidecar.read_text(encoding="utf-8") == "canonical-input"


def test_cli_rejects_output_collisions_before_any_write():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        observation = root / "window.json"
        observation.write_text(json.dumps(window(control_bad=1, treatment_bad=0)), encoding="utf-8")
        state = root / "state.json"
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "score", "--catalog", str(CATALOG),
             "--state", str(state), "--observation", str(observation),
             "--scorecard", str(state), "--pack-dir", str(root / "packs")],
            capture_output=True, text=True, encoding="utf-8", timeout=30)
        assert proc.returncode == 2
        assert "output path collision" in proc.stderr
        assert not state.exists()

        packs = root / "packs"
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "score", "--catalog", str(CATALOG),
             "--state", str(state), "--observation", str(observation),
             "--scorecard", str(packs / "codex.md"), "--pack-dir", str(packs)],
            capture_output=True, text=True, encoding="utf-8", timeout=30)
        assert proc.returncode == 2
        assert "output path collision" in proc.stderr
        assert not state.exists() and not packs.exists()

        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "score", "--catalog", str(CATALOG),
             "--state", str(state), "--observation", str(observation),
             "--scorecard", str(packs), "--pack-dir", str(packs)],
            capture_output=True, text=True, encoding="utf-8", timeout=30)
        assert proc.returncode == 2
        assert "output path collision" in proc.stderr
        assert not state.exists() and not packs.exists()

        nested_pack_dir = state / "packs"
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "score", "--catalog", str(CATALOG),
             "--state", str(state), "--observation", str(observation),
             "--scorecard", str(root / "score.json"), "--pack-dir", str(nested_pack_dir)],
            capture_output=True, text=True, encoding="utf-8", timeout=30)
        assert proc.returncode == 2
        assert "output path collision" in proc.stderr
        assert not state.exists() and not nested_pack_dir.exists()

        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "score", "--catalog", str(CATALOG),
             "--state", str(observation), "--observation", str(observation),
             "--scorecard", str(root / "score.json"), "--pack-dir", str(packs)],
            capture_output=True, text=True, encoding="utf-8", timeout=30)
        assert proc.returncode == 2
        assert "observation" in proc.stderr and "output path collision" in proc.stderr

        copied_catalog = root / "codex.md"
        catalog_bytes = CATALOG.read_bytes()
        copied_catalog.write_bytes(catalog_bytes)
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "init", "--catalog", str(copied_catalog),
             "--state", str(root / "learning.json"), "--pack-dir", str(root),
             "--experiment-id", "collision"],
            capture_output=True, text=True, encoding="utf-8", timeout=30)
        assert proc.returncode == 2
        assert "catalog" in proc.stderr and "output path collision" in proc.stderr
        assert copied_catalog.read_bytes() == catalog_bytes

        valid_state, catalog = state_and_catalog()
        colliding_state = root / "pack-state" / "codex.md"
        arl.atomic_write_json(colliding_state, valid_state)
        before = colliding_state.read_bytes()
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "pack", "--catalog", str(CATALOG),
             "--state", str(colliding_state), "--pack-dir", str(colliding_state.parent),
             "--experiment-id", "test-experiment"],
            capture_output=True, text=True, encoding="utf-8", timeout=30)
        assert proc.returncode == 2
        assert "state" in proc.stderr and "output path collision" in proc.stderr
        assert colliding_state.read_bytes() == before


def test_quarantine_precedes_pending_journal_publication():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        state, catalog = state_and_catalog()
        apply(state, catalog, window(window_id="active", control_bad=1, treatment_bad=0))
        state_path = root / "state.json"
        packs = root / "packs"
        arl.bind_pack_dir(state, packs)
        arl.atomic_write_json(state_path, state)
        arl.write_packs(packs, state, catalog)
        harmful = window(window_id="harm", treatment_bad=1, exact=False)
        score = arl.evaluate_window(state, catalog, harmful)
        args = SimpleNamespace(
            state=state_path,
            pack_dir=packs,
            scorecard=root / "scorecards" / "harm.json",
            catalog=CATALOG,
            observation=root / "harm.json",
        )
        original = arl.os.replace

        def fail_journal_publish(source, destination):
            if (Path(source) == arl.prepared_path(state_path)
                    and Path(destination) == arl.pending_path(state_path)):
                raise OSError("injected journal publication failure")
            return original(source, destination)

        arl.os.replace = fail_journal_publish
        try:
            try:
                arl.write_scored_state(args, score, state, catalog)
            except OSError as exc:
                assert "injected" in str(exc)
            else:
                raise AssertionError("fault injection did not interrupt transaction")
        finally:
            arl.os.replace = original

        assert not arl.pending_path(state_path).exists()
        assert arl.prepared_path(state_path).is_file()
        assert "activation_payload_only_v1" not in (packs / "codex.md").read_text(encoding="utf-8")
        persisted = arl.load_state(state_path, catalog, "test-experiment")
        assert persisted["rules"]["activation_payload_only_v1"]["codex"]["status"] == "active"

        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "pack", "--catalog", str(CATALOG),
             "--state", str(state_path), "--pack-dir", str(packs),
             "--experiment-id", "test-experiment"],
            capture_output=True, text=True, encoding="utf-8", timeout=30)
        assert proc.returncode == 0, proc.stderr
        recovered = arl.load_state(state_path, catalog, "test-experiment")
        assert recovered["rules"]["activation_payload_only_v1"]["codex"]["status"] == "retired"
        assert not arl.pending_path(state_path).exists()
        assert not arl.prepared_path(state_path).exists()
        assert "activation_payload_only_v1" not in (packs / "codex.md").read_text(encoding="utf-8")


def test_orphan_quarantine_blocks_pack_when_prepared_journal_write_fails():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        state, catalog = state_and_catalog()
        apply(state, catalog, window(window_id="active", control_bad=1, treatment_bad=0))
        state_path = root / "state.json"
        packs = root / "packs"
        arl.bind_pack_dir(state, packs)
        arl.atomic_write_json(state_path, state)
        arl.write_packs(packs, state, catalog)
        score = arl.evaluate_window(
            state, catalog, window(window_id="harm", treatment_bad=1, exact=False))
        args = SimpleNamespace(
            state=state_path,
            pack_dir=packs,
            scorecard=root / "scores" / "harm.json",
            catalog=CATALOG,
            observation=root / "harm.json",
        )
        original = arl.atomic_write_json

        def fail_prepared_write(path, value):
            if path == arl.prepared_path(state_path):
                raise OSError("injected prepared journal write failure")
            return original(path, value)

        arl.atomic_write_json = fail_prepared_write
        try:
            try:
                arl.write_scored_state(args, score, state, catalog)
            except OSError:
                pass
        finally:
            arl.atomic_write_json = original

        assert not arl.pending_path(state_path).exists()
        assert not arl.prepared_path(state_path).exists()
        assert "activation_payload_only_v1" not in (packs / "codex.md").read_text(encoding="utf-8")
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "pack", "--catalog", str(CATALOG),
             "--state", str(state_path), "--pack-dir", str(packs),
             "--experiment-id", "test-experiment"],
            capture_output=True, text=True, encoding="utf-8", timeout=30)
        assert proc.returncode == 2
        assert "orphan quarantine blocks pack generation" in proc.stderr
        assert "activation_payload_only_v1" not in (packs / "codex.md").read_text(encoding="utf-8")
        alternate_packs = root / "alternate-packs"
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "pack", "--catalog", str(CATALOG),
             "--state", str(state_path), "--pack-dir", str(alternate_packs),
             "--experiment-id", "test-experiment"],
            capture_output=True, text=True, encoding="utf-8", timeout=30)
        assert proc.returncode == 2
        assert "pack_dir binding mismatch" in proc.stderr
        assert not alternate_packs.exists()


def test_pending_deactivation_transaction_recovers_before_pack_can_reinclude_rule():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        state, catalog = state_and_catalog()
        apply(state, catalog, window(window_id="active", control_bad=1, treatment_bad=0))
        state_path = root / "state.json"
        packs = root / "packs"
        arl.bind_pack_dir(state, packs)
        arl.atomic_write_json(state_path, state)
        arl.write_packs(packs, state, catalog)
        assert "activation_payload_only_v1" in (packs / "codex.md").read_text(encoding="utf-8")

        harmful = window(window_id="harm", ids=[f"H{i}" for i in range(6)], treatment_bad=1)
        score = arl.evaluate_window(state, catalog, harmful)
        assert score["status_after"] == "retired"
        args = SimpleNamespace(
            state=state_path,
            pack_dir=packs,
            scorecard=root / "scorecards" / "harm.json",
            catalog=CATALOG,
            observation=root / "harm.json",
        )
        original = arl.atomic_write_json

        def fail_state_write(path, value):
            if path == state_path and value["rules"]["activation_payload_only_v1"]["codex"]["status"] == "retired":
                raise OSError("injected state write failure")
            return original(path, value)

        arl.atomic_write_json = fail_state_write
        try:
            try:
                arl.write_scored_state(args, score, state, catalog)
            except OSError as exc:
                assert "injected" in str(exc)
            else:
                raise AssertionError("fault injection did not interrupt transaction")
        finally:
            arl.atomic_write_json = original

        assert arl.pending_path(state_path).is_file()
        assert "activation_payload_only_v1" not in (packs / "codex.md").read_text(encoding="utf-8")
        arl.recover_pending(state_path, catalog, "test-experiment")
        recovered = arl.load_state(state_path, catalog, "test-experiment")
        assert recovered["rules"]["activation_payload_only_v1"]["codex"]["status"] == "retired"
        assert not arl.pending_path(state_path).exists()
        arl.write_packs(packs, recovered, catalog)
        assert "activation_payload_only_v1" not in (packs / "codex.md").read_text(encoding="utf-8")
        assert args.scorecard.is_file()


def test_dry_run_refuses_pending_recovery_without_writing():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        state, catalog = state_and_catalog()
        apply(state, catalog, window(window_id="active", control_bad=1, treatment_bad=0))
        state_path = root / "state.json"
        packs = root / "packs"
        arl.bind_pack_dir(state, packs)
        arl.atomic_write_json(state_path, state)
        arl.write_packs(packs, state, catalog)
        harmful_path = root / "harm.json"
        harmful_path.write_text(
            json.dumps(window(window_id="harm", treatment_bad=1, exact=False)), encoding="utf-8")
        score = arl.evaluate_window(state, catalog, json.loads(harmful_path.read_text(encoding="utf-8")))
        scorecard = root / "scores" / "harm.json"
        args = SimpleNamespace(
            state=state_path,
            pack_dir=packs,
            scorecard=scorecard,
            catalog=CATALOG,
            observation=harmful_path,
        )
        original = arl.atomic_write_json

        def fail_state_write(path, value):
            if path == state_path:
                raise OSError("leave pending transaction")
            return original(path, value)

        arl.atomic_write_json = fail_state_write
        try:
            try:
                arl.write_scored_state(args, score, state, catalog)
            except OSError:
                pass
        finally:
            arl.atomic_write_json = original

        before = {
            "state": state_path.read_bytes(),
            "pending": arl.pending_path(state_path).read_bytes(),
            "codex": (packs / "codex.md").read_bytes(),
            "hermes": (packs / "hermes.md").read_bytes(),
        }
        next_observation = root / "next.json"
        next_observation.write_text(json.dumps(window(window_id="next")), encoding="utf-8")
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "score", "--catalog", str(CATALOG),
             "--state", str(state_path), "--observation", str(next_observation),
             "--scorecard", str(root / "scores" / "next.json"),
             "--pack-dir", str(packs), "--experiment-id", "test-experiment", "--dry-run"],
            capture_output=True, text=True, encoding="utf-8", timeout=30)
        assert proc.returncode == 2
        assert "dry-run refuses to recover" in proc.stderr
        assert not (root / "scores" / "next.json").exists()
        assert state_path.read_bytes() == before["state"]
        assert arl.pending_path(state_path).read_bytes() == before["pending"]
        assert (packs / "codex.md").read_bytes() == before["codex"]
        assert (packs / "hermes.md").read_bytes() == before["hermes"]


def test_hermes_deactivation_recovery_is_runtime_isolated():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        state, catalog = state_and_catalog()
        apply(state, catalog, window(runtime="hermes", window_id="active",
                                     control_bad=1, treatment_bad=0))
        state_path = root / "state.json"
        packs = root / "packs"
        arl.bind_pack_dir(state, packs)
        arl.atomic_write_json(state_path, state)
        arl.write_packs(packs, state, catalog)
        assert "activation_payload_only_v1" in (packs / "hermes.md").read_text(encoding="utf-8")
        assert "activation_payload_only_v1" not in (packs / "codex.md").read_text(encoding="utf-8")

        harmful = window(runtime="hermes", window_id="harm", treatment_bad=1, exact=False)
        score = arl.evaluate_window(state, catalog, harmful)
        args = SimpleNamespace(
            state=state_path,
            pack_dir=packs,
            scorecard=root / "scores" / "harm.json",
            catalog=CATALOG,
            observation=root / "harm.json",
        )
        original = arl.atomic_write_json

        def fail_state_write(path, value):
            if path == state_path:
                raise OSError("injected Hermes state write failure")
            return original(path, value)

        arl.atomic_write_json = fail_state_write
        try:
            try:
                arl.write_scored_state(args, score, state, catalog)
            except OSError:
                pass
        finally:
            arl.atomic_write_json = original

        assert "activation_payload_only_v1" not in (packs / "hermes.md").read_text(encoding="utf-8")
        assert "activation_payload_only_v1" not in (packs / "codex.md").read_text(encoding="utf-8")
        arl.recover_pending(
            state_path, catalog, "test-experiment", protected_paths={"catalog": CATALOG})
        recovered = arl.load_state(state_path, catalog, "test-experiment")
        assert recovered["rules"]["activation_payload_only_v1"]["hermes"]["status"] == "retired"
        assert recovered["rules"]["activation_payload_only_v1"]["codex"]["status"] == "candidate"


TESTS = [
    test_new_state_is_runtime_scoped_and_candidate_rules_are_not_packed,
    test_catalog_is_an_exact_projection_of_preregistered_rules,
    test_correctness_and_real_rework_benefit_activate_with_bounded_cost,
    test_observable_harm_retires_even_when_token_usage_is_missing,
    test_missing_usage_without_harm_is_unscored_and_preserves_state,
    test_outcome_benefit_over_ten_percent_cost_degrades_then_retires,
    test_no_benefit_degrades_then_retires,
    test_two_disjoint_parity_bound_windows_can_promote_token_only_rule,
    test_cost_only_binding_drift_is_unscored_and_preserves_degraded,
    test_binding_drift_without_cost_savings_also_preserves_degraded,
    test_reused_cost_only_cases_are_unscored_not_fake_replication,
    test_reused_no_savings_cases_are_also_unscored,
    test_retired_rule_cannot_resurrect_without_new_experiment,
    test_identical_window_replay_is_idempotent_without_second_transition,
    test_duplicate_window_id_with_changed_payload_is_rejected,
    test_catalog_prompt_drift_invalidates_persisted_state,
    test_pack_defensively_excludes_non_confirmatory_rule_even_if_state_is_tampered,
    test_evidence_free_active_state_is_rejected_and_not_packed,
    test_last_eligible_cannot_disagree_with_append_only_history,
    test_case_level_harm_retires_even_when_aggregate_defects_improve,
    test_new_unresolved_defect_triggers_safety_veto,
    test_more_treatment_rework_retires_even_when_corrective_result_is_unscored,
    test_rework_difference_is_not_harm_when_initial_pair_is_not_comparable,
    test_negative_control_policy_cannot_activate_from_retrospective_evidence,
    test_invalid_corrective_contract_is_rejected,
    test_cli_dry_run_writes_nothing,
    test_cli_score_updates_state_scorecard_and_runtime_packs,
    test_cli_pack_requires_matching_experiment_and_regenerates_packs,
    test_cli_init_refuses_to_overwrite_existing_learning_state,
    test_atomic_write_preserves_legacy_fixed_sidecar_path,
    test_cli_rejects_output_collisions_before_any_write,
    test_quarantine_precedes_pending_journal_publication,
    test_orphan_quarantine_blocks_pack_when_prepared_journal_write_fails,
    test_pending_deactivation_transaction_recovers_before_pack_can_reinclude_rule,
    test_dry_run_refuses_pending_recovery_without_writing,
    test_hermes_deactivation_recovery_is_runtime_isolated,
]


def main():
    passed = failed = 0
    for test in TESTS:
        try:
            test()
            print(f"ok {test.__name__}")
            passed += 1
        except Exception as exc:  # noqa: BLE001 - report every failure
            print(f"FAIL {test.__name__}: {exc!r}")
            failed += 1
    print(f"{passed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
