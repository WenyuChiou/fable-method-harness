#!/usr/bin/env python3
"""Deterministic tests for the Codex/Hermes adaptive-loop live instrument."""

import base64
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "run_adaptive_loop_experiment.py"
CASES = REPO / "benchmarks" / "adaptive_loop" / "cases_v1.json"
DESIGN = REPO / "benchmarks" / "adaptive_loop" / "preregistration_design_v1.json"

_spec = importlib.util.spec_from_file_location("run_adaptive_loop_experiment", SCRIPT)
runner = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(runner)


def fixture_jwt(subject: str, account_id: str, rotation: str = "v1") -> str:
    def encode(value):
        return base64.urlsafe_b64encode(
            json.dumps(value, separators=(",", ":")).encode("utf-8")
        ).rstrip(b"=").decode("ascii")

    return ".".join((
        encode({"alg": "none", "typ": "JWT"}),
        encode({
            "sub": subject,
            "https://api.openai.com/auth": {"chatgpt_account_id": account_id},
            "jti": rotation,
            "iat": 1 if rotation == "v1" else 2,
            "exp": 100 if rotation == "v1" else 200,
        }),
        "fixture-signature",
    ))


def invocation(*, correct=True, exact=True, tokens=100, seconds=1.0,
               process_status="completed"):
    return {
        "correct": correct,
        "usage": {
            "status": "EXACT" if exact else "UNSCORED",
            "total_tokens": tokens if exact else None,
        },
        "duration_seconds": seconds,
        "process_status": process_status,
    }


def checkpoint_invocation(receipt, *, correct=True, total=12, binding=None):
    binding = binding or build_test_binding()
    empty_digest = {"bytes": 0, "sha256": hashlib.sha256(b"").hexdigest()}
    environment_sha = runner.bound_runtime_environment_fingerprint(binding, "codex")
    return {
        "exit_code": 0,
        "process_status": "completed",
        "process_reason": "",
        "duration_seconds": 1.0,
        "usage": {
            "status": "EXACT", "reason": "", "input_tokens": 10,
            "output_tokens": 2, "cache_read_tokens": 0, "cache_write_tokens": 0,
            "reasoning_tokens": 1, "total_tokens": total,
            "input_semantics": "input_and_cache_are_separate",
        },
        "receipt": receipt,
        "receipt_error": "",
        "correct": correct,
        "receipt_output": empty_digest,
        "process_stderr": empty_digest,
        "environment": {
            "status": "MATCHED",
            "binding_sha256": environment_sha,
            "before_sha256": environment_sha,
            "after_sha256": environment_sha,
        },
    }


def test_cases_are_six_unseen_typed_episodes():
    cases = runner.load_cases(CASES)
    assert len(cases) == 6
    assert {case["id"] for case in cases} == {f"AL0{i}" for i in range(1, 7)}
    assert {case["kind"] for case in cases} == {"routine", "trigger", "rollback"}
    assert sum(case["marker_present"] for case in cases) == 1


def test_schedule_is_deterministic_adjacent_and_complete():
    cases = runner.load_cases(CASES)
    first = runner.build_schedule(cases, "fixed-seed")
    second = runner.build_schedule(cases, "fixed-seed")
    assert first == second and len(first) == 24
    assert len({row["schedule_id"] for row in first}) == 24
    for index in range(0, len(first), 2):
        pair = first[index:index + 2]
        assert {(row["runtime"], row["case_id"]) for row in pair}.__len__() == 1
        assert {row["arm"] for row in pair} == {"control", "treatment"}
    assert {(row["runtime"], row["case_id"], row["arm"]) for row in first} == {
        (runtime, case["id"], arm)
        for runtime in runner.RUNTIMES for case in cases for arm in runner.ARMS
    }


def test_corrective_prompt_replays_original_then_appends_exactly_two_fields():
    case = runner.load_cases(CASES)[0]
    original = runner.build_prompt(case, "nonce-1")
    corrective = runner.build_prompt(case, "nonce-1", corrective=True)
    assert corrective.startswith(original)
    assert corrective[len(original):] == runner.CORRECTIVE_SUFFIX
    assert corrective.count("rework_attempt: 2") == 1
    assert corrective.count("prior_receipt_rejected: true") == 1


def test_prompt_freezes_marker_evidence_and_requires_zero_tool_use():
    cases = {case["kind"]: case for case in runner.load_cases(CASES)}
    routine = runner.build_prompt(cases["routine"], "nonce-routine")
    rollback = runner.build_prompt(cases["rollback"], "nonce-rollback")
    assert "rollback_marker_at_repository_root: absent" in routine
    assert "rollback_marker_at_repository_root: present" in rollback
    for prompt in (routine, rollback):
        assert "do not use tools" in prompt
        assert "reason: rollback" not in prompt
        assert '"harness":' not in prompt


def test_codex_usage_subtracts_cached_subset_without_double_counting():
    stdout = json.dumps({
        "type": "turn.completed",
        "usage": {
            "input_tokens": 100,
            "cached_input_tokens": 70,
            "output_tokens": 10,
            "reasoning_tokens": 4,
        },
    })
    usage = runner.extract_codex_usage(stdout)
    assert usage["status"] == "EXACT"
    assert usage["input_tokens"] == 30
    assert usage["cache_read_tokens"] == 70
    assert usage["output_tokens"] == 10
    assert usage["reasoning_tokens"] == 4
    assert usage["total_tokens"] == 110
    assert usage["input_semantics"] == "raw_input_includes_cached_subset"


def test_codex_usage_accepts_separate_cache_schema_and_rejects_ambiguity():
    separate = json.dumps({"type": "turn.completed", "usage": {
        "input_tokens": 30, "cache_read_tokens": 70, "output_tokens": 10}})
    usage = runner.extract_codex_usage(separate)
    assert usage["status"] == "EXACT" and usage["total_tokens"] == 110
    ambiguous = json.dumps({"type": "turn.completed", "usage": {
        "input_tokens": 100, "cached_input_tokens": 70,
        "cache_read_tokens": 60, "output_tokens": 10}})
    rejected = runner.extract_codex_usage(ambiguous)
    assert rejected == {"status": "UNSCORED", "reason": "codex_cache_schema_conflict"}


def test_codex_usage_rejects_multiple_terminal_snapshots_instead_of_max_compositing():
    stdout = "\n".join((
        json.dumps({"type": "turn.completed", "usage": {
            "input_tokens": 100, "cached_input_tokens": 70, "output_tokens": 10}}),
        json.dumps({"type": "turn.completed", "usage": {
            "input_tokens": 90, "cached_input_tokens": 60, "output_tokens": 30}}),
    ))
    assert runner.extract_codex_usage(stdout) == {
        "status": "UNSCORED", "reason": "codex_multiple_terminal_usage_events"}


def test_invocation_rows_measure_actual_corrective_work():
    row = runner.invocations_to_row(
        "AL01",
        invocation(correct=False, tokens=100, seconds=2.0),
        invocation(correct=True, tokens=60, seconds=1.5),
    )
    assert row == {
        "case_id": "AL01",
        "initial_correct": False,
        "corrective_invocations": 1,
        "final_correct": True,
        "usage_status": "EXACT",
        "total_tokens": 160,
        "corrective_tokens": 60,
        "duration_seconds": 3.5,
        "corrective_duration_seconds": 1.5,
        "process_status": "completed",
    }
    no_rework = runner.invocations_to_row(
        "AL02", invocation(correct=True, tokens=80, seconds=0.5), None)
    assert no_rework["corrective_invocations"] == 0
    assert no_rework["corrective_tokens"] == 0
    assert no_rework["final_correct"] is True


def test_nonexact_corrective_work_makes_total_usage_unscored():
    row = runner.invocations_to_row(
        "AL03",
        invocation(correct=False, tokens=100),
        invocation(correct=None, exact=False, process_status="timeout"),
    )
    assert row["usage_status"] == "UNSCORED"
    assert row["total_tokens"] is None and row["corrective_tokens"] is None
    assert row["corrective_invocations"] == 1
    assert row["final_correct"] is None
    assert row["process_status"] == "timeout"


def test_resume_state_machine_never_retries_an_uncertain_call():
    assert runner.resume_action({"stage": "initial_started"}) == "interrupt"
    assert runner.resume_action({"stage": "corrective_started"}) == "interrupt"
    assert runner.resume_action({
        "stage": "initial_completed", "initial": invocation(correct=False)}) == "corrective"
    assert runner.resume_action({
        "stage": "initial_completed", "initial": invocation(correct=True)}) == "finalize"
    assert runner.resume_action({"stage": "corrective_completed"}) == "finalize"
    assert runner.resume_action({"stage": "completed"}) == "skip"


def test_arm_entrypoints_are_extracted_from_frozen_git_blobs():
    design = json.loads(DESIGN.read_text(encoding="utf-8"))
    for arm in runner.ARMS:
        blobs = runner.load_arm_entrypoints(design, arm)
        expected = design["confirmatory_design"]["arms"][arm]["sha256"]
        assert set(blobs) == {"AGENTS.md", "HERMES.md"}
        for name, content in blobs.items():
            assert hashlib.sha256(content).hexdigest() == expected[name]
    assert runner.load_arm_entrypoints(design, "control")["AGENTS.md"] != (
        runner.load_arm_entrypoints(design, "treatment")["AGENTS.md"])


def test_workspace_must_be_outside_repo_and_contains_only_arm_entrypoints():
    design = json.loads(DESIGN.read_text(encoding="utf-8"))
    blobs = runner.load_arm_entrypoints(design, "control")
    runner.WORKSPACE_ROOT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=runner.WORKSPACE_ROOT) as tmp:
        workspace = Path(tmp) / "episode"
        runner.prepare_workspace(workspace, blobs, marker_present=True)
        assert (workspace / "AGENTS.md").read_bytes() == blobs["AGENTS.md"]
        assert (workspace / "HERMES.md").read_bytes() == blobs["HERMES.md"]
        assert (workspace / ".fable-harness-off").is_file()
        assert runner.workspace_matches(workspace, blobs, marker_present=True)
        (workspace / "prior-rejected-receipt.txt").write_text("leak", encoding="utf-8")
        assert not runner.workspace_matches(workspace, blobs, marker_present=True)
    try:
        runner.assert_workspace_isolated(REPO / "evals" / "adaptive_loop" / "bad")
    except ValueError as exc:
        assert "outside the repository" in str(exc)
    else:
        raise AssertionError("repo-descendant workspace could leak treatment rules into control")


def test_workspace_rejects_all_ambient_codex_and_hermes_rule_files():
    runner.WORKSPACE_ROOT.mkdir(parents=True, exist_ok=True)
    for rule_name in ("SOUL.md", "AGENTS.override.md", ".hermes.md"):
        with tempfile.TemporaryDirectory(dir=runner.WORKSPACE_ROOT) as tmp:
            parent = Path(tmp)
            (parent / rule_name).write_text("ambient rules", encoding="utf-8")
            try:
                runner.assert_workspace_isolated(parent / "episode")
            except ValueError as exc:
                assert rule_name in str(exc)
            else:
                raise AssertionError(f"ambient {rule_name} was not rejected")


def test_recursive_cleanup_refuses_any_path_outside_dedicated_root():
    sentinel = REPO / "AGENTS.md"
    before = sentinel.read_bytes()
    try:
        runner.cleanup_episode_workspace(REPO)
    except ValueError as exc:
        assert "escapes" in str(exc)
    else:
        raise AssertionError("unsafe recursive cleanup target was accepted")
    assert sentinel.read_bytes() == before


def test_git_worktree_identity_detects_dirty_and_untracked_source_without_leaking_paths():
    with tempfile.TemporaryDirectory() as tmp:
        project = Path(tmp) / "hermes-source"
        project.mkdir()
        subprocess.run(["git", "init", "-q", str(project)], check=True)
        source = project / "runtime.py"
        source.write_text("VALUE = 1\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(project), "add", "runtime.py"], check=True)
        subprocess.run([
            "git", "-C", str(project), "-c", "user.name=Harness Test",
            "-c", "user.email=harness@example.invalid", "commit", "-qm", "fixture",
        ], check=True)

        clean = runner.git_worktree_identity(project)
        source.write_text("VALUE = 2\n", encoding="utf-8")
        dirty = runner.git_worktree_identity(project)
        (project / "new_runtime.py").write_text("NEW = True\n", encoding="utf-8")
        untracked = runner.git_worktree_identity(project)

        assert clean["git_head"] == dirty["git_head"] == untracked["git_head"]
        assert clean["worktree_fingerprint"] != dirty["worktree_fingerprint"]
        assert dirty["worktree_fingerprint"] != untracked["worktree_fingerprint"]
        assert clean["dirty"] is False
        assert dirty["dirty"] is True and untracked["dirty"] is True
        assert str(project) not in json.dumps(untracked)


def test_directory_tree_identity_detects_codex_payload_drift_without_leaking_paths():
    with tempfile.TemporaryDirectory() as tmp:
        package = Path(tmp) / "codex-package"
        package.mkdir()
        binary = package / "codex.exe"
        binary.write_bytes(b"version-one")
        first = runner.directory_tree_identity(package)
        binary.write_bytes(b"version-two")
        second = runner.directory_tree_identity(package)
        assert first["tree_sha256"] != second["tree_sha256"]
        assert str(package) not in json.dumps(second)


def test_hermes_executable_identity_includes_source_and_environment_fingerprints():
    with tempfile.TemporaryDirectory() as tmp:
        executable = Path(tmp) / "hermes.exe"
        executable.write_bytes(b"launcher")
        original_which = runner.shutil.which
        original_probe = runner.runtime_version_output
        original_source = runner.hermes_runtime_source_identity
        runner.shutil.which = lambda name: str(executable)
        runner.runtime_version_output = lambda name, path=None: (
            f"Hermes Agent v1.0\nProject: {tmp}\nPython: 3.11\n")
        runner.hermes_runtime_source_identity = lambda raw, path: {
            "install_mode": "editable_project",
            "ignored_project_fallbacks_absent": ["cli-config.yaml", ".env"],
            "project_git": {"worktree_fingerprint": "a" * 64},
            "python_environment": {"distribution_set_sha256": "b" * 64},
        }
        try:
            identity = runner.executable_identity("hermes")
        finally:
            runner.shutil.which = original_which
            runner.runtime_version_output = original_probe
            runner.hermes_runtime_source_identity = original_source
        assert identity["runtime_source"]["project_git"]["worktree_fingerprint"] == "a" * 64
        assert identity["runtime_source"]["python_environment"][
            "distribution_set_sha256"] == "b" * 64
        assert "Project:" not in identity["version"]
        assert str(Path(tmp).resolve()) not in json.dumps(identity)


def test_hermes_ignored_project_config_fallbacks_must_be_absent():
    with tempfile.TemporaryDirectory() as tmp:
        project = Path(tmp)
        runner.assert_hermes_project_fallbacks_absent(project)
        for name in runner.HERMES_IGNORED_PROJECT_FALLBACKS:
            candidate = project / name
            candidate.write_text("must fail closed", encoding="utf-8")
            try:
                runner.assert_hermes_project_fallbacks_absent(project)
            except ValueError as exc:
                assert "fallback" in str(exc)
            else:
                raise AssertionError(f"Hermes ignored fallback was accepted: {name}")
            candidate.unlink()

def test_live_observation_name_cannot_impersonate_another_progress_file():
    try:
        runner.validate_eval_output(runner.EVAL_ROOT / "codex.progress.json")
    except ValueError as exc:
        assert "progress" in str(exc)
    else:
        raise AssertionError("reserved *.progress.json observation name was accepted")


def test_codex_final_receipt_is_outside_episode_and_scrubbed_before_rework():
    runner.WORKSPACE_ROOT.mkdir(parents=True, exist_ok=True)
    episode = runner.WORKSPACE_ROOT / "S999-receipt-isolation"
    with runner.temporary_final_message() as final_message:
        assert episode not in final_message.parents
        assert final_message.parent == runner.INSTRUMENT_OUTPUT_ROOT
        final_message.write_text("rejected receipt", encoding="utf-8")
        assert final_message.is_file()
    assert not final_message.exists()


def test_base_process_runner_passes_an_explicit_isolated_environment():
    with tempfile.TemporaryDirectory() as tmp:
        env = os.environ.copy()
        env["FABLE_RUNTIME_HOME_SENTINEL"] = "isolated-value"
        stdout, stderr, exit_code, reason, _ = runner.base.run_process(
            [sys.executable, "-c",
             "import os; print(os.environ.get('FABLE_RUNTIME_HOME_SENTINEL','missing'))"],
            "", 20, Path(tmp), env=env)
        assert exit_code == 0 and reason == "" and stderr == ""
        assert stdout.strip() == "isolated-value"


def test_per_invocation_runtime_homes_copy_credentials_only_and_are_scrubbed():
    runner.PRIVATE_RUNTIME_ROOT.mkdir(parents=True, exist_ok=True)
    original_root = runner.RUNTIME_HOME_ROOT
    original_codex = os.environ.get("CODEX_HOME")
    original_hermes = os.environ.get("HERMES_HOME")
    original_openai_key = os.environ.get("OPENAI_API_KEY")
    original_openai_base = os.environ.get("OPENAI_BASE_URL")
    original_https_proxy = os.environ.get("HTTPS_PROXY")
    original_pythonpath = os.environ.get("PYTHONPATH")
    original_node_options = os.environ.get("NODE_OPTIONS")
    original_terminal_cwd = os.environ.get("TERMINAL_CWD")
    original_messaging_cwd = os.environ.get("MESSAGING_CWD")
    with tempfile.TemporaryDirectory(dir=runner.PRIVATE_RUNTIME_ROOT) as tmp:
        root = Path(tmp)
        codex_source = root / "codex-source"
        hermes_source = root / "hermes-source"
        codex_source.mkdir()
        hermes_source.mkdir()
        (codex_source / "auth.json").write_text(json.dumps({
            "auth_mode": "chatgpt",
            "tokens": {
                "account_id": "codex-account-fixture",
                "access_token": fixture_jwt(
                    "codex-user-fixture", "codex-account-fixture"),
            },
        }), encoding="utf-8")
        (codex_source / "AGENTS.md").write_text("must not copy", encoding="utf-8")
        (codex_source / "config.toml").write_text("must not copy", encoding="utf-8")
        (hermes_source / "auth.json").write_text(json.dumps({
            "credential_pool": {"openai-codex": [{
                "id": "hermes-credential-fixture",
                "auth_type": "oauth",
                "priority": 1,
                "source": "fixture",
                "access_token": fixture_jwt(
                    "hermes-user-fixture", "hermes-account-fixture"),
            }]},
        }), encoding="utf-8")
        (hermes_source / "SOUL.md").write_text("must not copy", encoding="utf-8")
        (hermes_source / "MEMORY.md").write_text("must not copy", encoding="utf-8")
        runner.RUNTIME_HOME_ROOT = root / "isolated-homes"
        os.environ["CODEX_HOME"] = str(codex_source)
        os.environ["HERMES_HOME"] = str(hermes_source)
        os.environ["OPENAI_API_KEY"] = "must-not-inherit"
        os.environ["OPENAI_BASE_URL"] = "https://must-not-inherit.invalid"
        os.environ["HTTPS_PROXY"] = "https://must-not-inherit.invalid"
        os.environ["PYTHONPATH"] = "must-not-inherit"
        os.environ["NODE_OPTIONS"] = "--require=must-not-inherit"
        os.environ["TERMINAL_CWD"] = str(root / "must-not-inherit")
        os.environ["MESSAGING_CWD"] = str(root / "must-not-inherit")
        try:
            with runner.isolated_runtime_environment(
                    "codex", "isolation-test", run_scope="a" * 64,
                    runtime_executable=Path(sys.executable),
                    runtime_command_prefix=(Path(sys.executable),)) as (env, state_db):
                home = Path(env["CODEX_HOME"])
                assert runner.WORKSPACE_ROOT.resolve() not in home.parents
                assert state_db is None
                assert {path.name for path in home.iterdir()} == {"auth.json"}
                hermes_decoy = Path(env["HERMES_HOME"])
                assert hermes_decoy.parent == home and not hermes_decoy.exists()
                assert all(name not in env for name in (
                    "OPENAI_API_KEY", "OPENAI_BASE_URL", "HTTPS_PROXY",
                    "PYTHONPATH", "NODE_OPTIONS", "TERMINAL_CWD", "MESSAGING_CWD"))
                assert env["PATH"] == runner.child_process_path(
                    Path(sys.executable), (Path(sys.executable),))
                if os.name == "nt":
                    probe = subprocess.run(
                        ["powershell.exe", "-NoProfile", "-Command", "Write-Output shell-ok"],
                        capture_output=True, text=True, encoding="utf-8", env=env, timeout=20)
                    assert probe.returncode == 0 and probe.stdout.strip() == "shell-ok"
            assert not home.exists()

            try:
                with runner.isolated_runtime_environment(
                        "codex", "isolation-test", run_scope="a" * 64,
                        runtime_executable=Path(sys.executable),
                        runtime_command_prefix=(Path(sys.executable),)) as (env, _):
                    drifted_home = Path(env["CODEX_HOME"])
                    (drifted_home / "auth.json").write_text(
                        "not-json", encoding="utf-8")
            except ValueError as exc:
                assert "credential identity drifted" in str(exc)
            else:
                raise AssertionError("invalid isolated credential identity was accepted")
            assert not drifted_home.exists()

            with runner.isolated_runtime_environment(
                    "hermes", "isolation-test", "openai-codex",
                    run_scope="b" * 64,
                    runtime_executable=Path(sys.executable),
                    runtime_command_prefix=(Path(sys.executable),)) as (env, state_db):
                home = Path(env["HERMES_HOME"])
                assert state_db == home / "state.db"
                assert {path.name for path in home.iterdir()} == {"auth.json", "SOUL.md"}
                assert (home / "SOUL.md").read_text(encoding="utf-8") == ""
                codex_decoy = Path(env["CODEX_HOME"])
                assert codex_decoy.parent == home and not codex_decoy.exists()
                assert codex_decoy != codex_source
                assert "HERMES_PROFILE" not in env and "HERMES_CONFIG" not in env
            assert not home.exists()
        finally:
            runner.RUNTIME_HOME_ROOT = original_root
            if original_codex is None:
                os.environ.pop("CODEX_HOME", None)
            else:
                os.environ["CODEX_HOME"] = original_codex
            if original_hermes is None:
                os.environ.pop("HERMES_HOME", None)
            else:
                os.environ["HERMES_HOME"] = original_hermes
            for name, value in (
                    ("OPENAI_API_KEY", original_openai_key),
                    ("OPENAI_BASE_URL", original_openai_base),
                    ("HTTPS_PROXY", original_https_proxy),
                    ("PYTHONPATH", original_pythonpath),
                    ("NODE_OPTIONS", original_node_options),
                    ("TERMINAL_CWD", original_terminal_cwd),
                    ("MESSAGING_CWD", original_messaging_cwd)):
                if value is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = value


def test_credential_identity_ignores_token_refresh_but_detects_account_drift():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        codex_auth = root / "codex-auth.json"
        codex_document = {
            "auth_mode": "chatgpt",
            "tokens": {
                "account_id": "stable-account-id",
                "access_token": fixture_jwt("stable-user-id", "stable-account-id", "v1"),
                "refresh_token": "refresh-v1",
            },
            "last_refresh": "before",
        }
        codex_auth.write_text(json.dumps(codex_document), encoding="utf-8")
        codex_before = runner.credential_identity_fingerprint(
            "codex", "experiment-a", auth_path=codex_auth)
        codex_document["tokens"]["access_token"] = fixture_jwt(
            "stable-user-id", "stable-account-id", "v2")
        codex_document["tokens"]["refresh_token"] = "refresh-v2"
        codex_document["last_refresh"] = "after"
        codex_auth.write_text(json.dumps(codex_document), encoding="utf-8")
        assert runner.credential_identity_fingerprint(
            "codex", "experiment-a", auth_path=codex_auth) == codex_before
        codex_document["tokens"]["account_id"] = "different-account-id"
        codex_document["tokens"]["access_token"] = fixture_jwt(
            "stable-user-id", "different-account-id", "v3")
        codex_auth.write_text(json.dumps(codex_document), encoding="utf-8")
        assert runner.credential_identity_fingerprint(
            "codex", "experiment-a", auth_path=codex_auth) != codex_before

        hermes_auth = root / "hermes-auth.json"
        hermes_document = {
            "updated_at": "before",
            "credential_pool": {"openai-codex": [{
                "id": "stable-credential-id",
                "auth_type": "oauth",
                "priority": 1,
                "source": "fixture",
                "base_url": None,
                "access_token": fixture_jwt(
                    "stable-hermes-user", "stable-hermes-account", "v1"),
                "refresh_token": "refresh-v1",
                "last_refresh": "before",
            }]},
        }
        hermes_auth.write_text(json.dumps(hermes_document), encoding="utf-8")
        hermes_before = runner.credential_identity_fingerprint(
            "hermes", "experiment-a", "openai-codex", auth_path=hermes_auth)
        credential = hermes_document["credential_pool"]["openai-codex"][0]
        credential["access_token"] = fixture_jwt(
            "stable-hermes-user", "stable-hermes-account", "v2")
        credential["refresh_token"] = "refresh-v2"
        credential["last_refresh"] = "after"
        hermes_document["updated_at"] = "after"
        hermes_auth.write_text(json.dumps(hermes_document), encoding="utf-8")
        assert runner.credential_identity_fingerprint(
            "hermes", "experiment-a", "openai-codex", auth_path=hermes_auth
        ) == hermes_before
        credential["access_token"] = fixture_jwt(
            "different-hermes-user", "different-hermes-account", "v3")
        hermes_auth.write_text(json.dumps(hermes_document), encoding="utf-8")
        assert runner.credential_identity_fingerprint(
            "hermes", "experiment-a", "openai-codex", auth_path=hermes_auth
        ) != hermes_before


def test_primary_and_cross_runtime_credentials_are_removed_when_tree_cleanup_is_pending():
    runner.PRIVATE_RUNTIME_ROOT.mkdir(parents=True, exist_ok=True)
    original_root = runner.RUNTIME_HOME_ROOT
    original_cleanup = runner.base.cleanup_workspace
    with tempfile.TemporaryDirectory(dir=runner.PRIVATE_RUNTIME_ROOT) as tmp:
        root = Path(tmp)
        runner.RUNTIME_HOME_ROOT = root / "runtime-homes"
        home = runner.RUNTIME_HOME_ROOT / f"codex-{'a' * 64}-fixture"
        home.mkdir(parents=True)
        auth = home / "auth.json"
        auth.write_text("secret fixture", encoding="utf-8")
        cross_runtime_auth = (
            home / runner.CROSS_RUNTIME_HOME_NAME / "auth.json")
        cross_runtime_auth.parent.mkdir()
        cross_runtime_auth.write_text("cross-runtime secret fixture", encoding="utf-8")
        (home / "state.db").write_text("locked nonsecret fixture", encoding="utf-8")
        runner.base.cleanup_workspace = lambda _: "pending"
        try:
            assert runner.cleanup_private_runtime_home(home) == "pending"
            assert not auth.exists() and not cross_runtime_auth.exists() and home.exists()
        finally:
            runner.base.cleanup_workspace = original_cleanup
            if home.exists():
                original_cleanup(home)
            runner.RUNTIME_HOME_ROOT = original_root


def test_windows_reparse_detector_supports_pre_python_312_stat_shape():
    reparse = SimpleNamespace(
        st_file_attributes=runner.WINDOWS_REPARSE_POINT_ATTRIBUTE,
        st_reparse_tag=0xA0000003,
    )
    legacy_attribute_only = SimpleNamespace(
        st_file_attributes=runner.WINDOWS_REPARSE_POINT_ATTRIBUTE)
    ordinary = SimpleNamespace(st_file_attributes=0, st_reparse_tag=0)
    assert runner.windows_lstat_is_reparse_point(reparse)
    assert runner.windows_lstat_is_reparse_point(legacy_attribute_only)
    assert not runner.windows_lstat_is_reparse_point(ordinary)


def test_windows_junction_cleanup_never_deletes_external_auth():
    if os.name != "nt":
        return
    runner.PRIVATE_RUNTIME_ROOT.mkdir(parents=True, exist_ok=True)
    original_root = runner.RUNTIME_HOME_ROOT
    with tempfile.TemporaryDirectory(dir=runner.PRIVATE_RUNTIME_ROOT) as tmp:
        root = Path(tmp)
        runner.RUNTIME_HOME_ROOT = root / "runtime-homes"
        home = runner.RUNTIME_HOME_ROOT / f"hermes-{'a' * 64}-junction-fixture"
        home.mkdir(parents=True)
        (home / "auth.json").write_text("primary fixture", encoding="utf-8")
        external = root / "external-codex-home"
        external.mkdir()
        external_auth = external / "auth.json"
        external_auth.write_text("must survive", encoding="utf-8")
        junction = home / runner.CROSS_RUNTIME_HOME_NAME
        created = subprocess.run(
            ["cmd", "/d", "/c", "mklink", "/J", str(junction), str(external)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=20,
        )
        if created.returncode != 0:
            raise AssertionError(f"junction fixture creation failed: {created.stderr}")
        try:
            assert runner.is_link_like_directory(junction)
            assert runner.cleanup_private_runtime_home(home) == "removed"
            assert external_auth.read_text(encoding="utf-8") == "must survive"
            assert not junction.exists()
        finally:
            if junction.exists():
                os.rmdir(junction)
            runner.RUNTIME_HOME_ROOT = original_root


def test_pending_link_cleanup_blocks_recursive_tree_cleanup():
    runner.PRIVATE_RUNTIME_ROOT.mkdir(parents=True, exist_ok=True)
    original_root = runner.RUNTIME_HOME_ROOT
    original_is_link_like = runner.is_link_like_directory
    original_remove_link = runner.remove_link_like_directory
    original_cleanup = runner.base.cleanup_workspace
    with tempfile.TemporaryDirectory(dir=runner.PRIVATE_RUNTIME_ROOT) as tmp:
        root = Path(tmp)
        runner.RUNTIME_HOME_ROOT = root / "runtime-homes"
        home = runner.RUNTIME_HOME_ROOT / f"hermes-{'a' * 64}-pending-link"
        cross_runtime_home = home / runner.CROSS_RUNTIME_HOME_NAME
        cross_runtime_home.mkdir(parents=True)
        (home / "auth.json").write_text("primary fixture", encoding="utf-8")
        (cross_runtime_home / "auth.json").write_text(
            "cross-runtime fixture", encoding="utf-8")
        recursive_cleanup_calls = []
        runner.is_link_like_directory = lambda path: path == cross_runtime_home
        runner.remove_link_like_directory = lambda _: "pending"
        runner.base.cleanup_workspace = (
            lambda path: recursive_cleanup_calls.append(path) or "removed")
        try:
            assert runner.cleanup_private_runtime_home(home) == "credential_pending"
            assert recursive_cleanup_calls == []
            assert home.exists()
        finally:
            runner.is_link_like_directory = original_is_link_like
            runner.remove_link_like_directory = original_remove_link
            runner.base.cleanup_workspace = original_cleanup
            original_cleanup(home)
            runner.RUNTIME_HOME_ROOT = original_root


def test_stale_scoped_credentials_are_scrubbed_before_invalid_source_auth_fails():
    runner.PRIVATE_RUNTIME_ROOT.mkdir(parents=True, exist_ok=True)
    original_root = runner.RUNTIME_HOME_ROOT
    original_codex = os.environ.get("CODEX_HOME")
    original_validate_structure = runner.validate_binding_structure
    original_lock_path = runner.binding_runtime_lock_path
    original_validate_binding = runner.validate_binding
    with tempfile.TemporaryDirectory(dir=runner.PRIVATE_RUNTIME_ROOT) as tmp:
        root = Path(tmp)
        run_scope = "a" * 64
        runner.RUNTIME_HOME_ROOT = root / "runtime-homes"
        stale_home = runner.RUNTIME_HOME_ROOT / f"codex-{run_scope}-hard-crash"
        stale_home.mkdir(parents=True)
        stale_auth = stale_home / "auth.json"
        stale_auth.write_text("stale-secret-fixture", encoding="utf-8")
        source_home = root / "invalid-codex-source"
        source_home.mkdir()
        os.environ["CODEX_HOME"] = str(source_home)
        binding_path = root / "binding.json"
        binding_path.write_text(json.dumps({
            "experiment_id": "cleanup-before-auth-validation",
            "binding_fingerprint": run_scope,
        }), encoding="utf-8")
        runner.validate_binding_structure = lambda _: None
        runner.binding_runtime_lock_path = lambda _binding, _runtime: root / "run.lock"

        def fail_on_invalid_source_auth(_path):
            runner.runtime_home_binding("codex", "cleanup-before-auth-validation")
            raise AssertionError("missing source auth was accepted")

        runner.validate_binding = fail_on_invalid_source_auth
        try:
            try:
                runner.run_runtime(
                    binding_path, "codex", root / "never-written.json", None)
            except ValueError as exc:
                assert "auth.json is unavailable" in str(exc)
            else:
                raise AssertionError("invalid source auth did not fail closed")
            assert not stale_auth.exists()
            assert not stale_home.exists()
        finally:
            runner.validate_binding_structure = original_validate_structure
            runner.binding_runtime_lock_path = original_lock_path
            runner.validate_binding = original_validate_binding
            runner.RUNTIME_HOME_ROOT = original_root
            if original_codex is None:
                os.environ.pop("CODEX_HOME", None)
            else:
                os.environ["CODEX_HOME"] = original_codex


def test_single_run_lock_rejects_a_concurrent_writer_and_releases_cleanly():
    with tempfile.TemporaryDirectory() as tmp:
        lock = Path(tmp) / "experiment.run.lock"
        with runner.exclusive_run_lock(lock):
            try:
                with runner.exclusive_run_lock(lock):
                    pass
            except ValueError as exc:
                assert "already running" in str(exc)
            else:
                raise AssertionError("a second live runner acquired the same output lock")
        with runner.exclusive_run_lock(lock):
            pass


def test_binding_runtime_has_one_canonical_output_and_external_state_db_is_rejected():
    binding = {
        "experiment_id": "binding-test",
        "binding_fingerprint": "a" * 64,
    }
    expected = runner.EVAL_ROOT / "binding-test-codex-aaaaaaaaaaaaaaaa.json"
    assert runner.canonical_eval_output(binding, "codex") == expected.resolve()
    assert runner.canonical_eval_output(binding, "codex") != (
        runner.EVAL_ROOT / "alternate.json").resolve()
    try:
        runner.run_runtime(Path("missing-binding.json"), "hermes", expected, Path("external.db"))
    except ValueError as exc:
        assert "isolated" in str(exc)
    else:
        raise AssertionError("external Hermes telemetry DB was silently accepted")


def test_shallow_forged_checkpoint_cannot_trigger_a_corrective_call():
    binding = build_test_binding()
    schedule = {
        "index": 0,
        "schedule_id": "S000-codex-AL01-control-test",
        "runtime": "codex",
        "case_id": "AL01",
        "arm": "control",
    }
    forged = {
        "stage": "initial_completed",
        "schedule": schedule,
        "workspace": str(runner.WORKSPACE_ROOT / schedule["schedule_id"]),
        "nonce": "f" * 32,
        "initial": {"correct": False},
    }
    try:
        runner.validate_episode_checkpoint(
            forged, schedule, {"harness": "inactive", "reason": "routine"},
            "codex", binding)
    except ValueError as exc:
        assert "invocation" in str(exc)
    else:
        raise AssertionError("shallow forged initial completion was accepted")


def test_fully_shaped_checkpoint_rederives_oracle_and_canonical_token_total():
    binding = build_test_binding()
    schedule = {
        "index": 0,
        "schedule_id": "S000-codex-AL01-control-test",
        "runtime": "codex",
        "case_id": "AL01",
        "arm": "control",
    }
    expected = {"harness": "inactive", "reason": "routine"}
    receipt = {"schema_version": 1, **expected}
    episode = {
        "stage": "initial_completed",
        "schedule": schedule,
        "workspace": str(runner.WORKSPACE_ROOT / schedule["schedule_id"]),
        "nonce": "f" * 32,
        "initial": checkpoint_invocation(receipt, correct=False, binding=binding),
    }
    try:
        runner.validate_episode_checkpoint(
            episode, schedule, expected, "codex", binding)
    except ValueError as exc:
        assert "oracle-derived" in str(exc)
    else:
        raise AssertionError("forged correctness was not rederived from the case oracle")

    episode["initial"] = checkpoint_invocation(
        receipt, correct=True, total=999, binding=binding)
    try:
        runner.validate_episode_checkpoint(
            episode, schedule, expected, "codex", binding)
    except ValueError as exc:
        assert "canonical usage total" in str(exc)
    else:
        raise AssertionError("forged total_tokens was not recomputed from exact buckets")


def test_environment_drift_cannot_remain_scored_in_a_checkpoint():
    binding = build_test_binding()
    schedule = {
        "index": 0,
        "schedule_id": "S000-codex-AL01-control-test",
        "runtime": "codex",
        "case_id": "AL01",
        "arm": "control",
    }
    expected = {"harness": "inactive", "reason": "routine"}
    receipt = {"schema_version": 1, **expected}
    initial = checkpoint_invocation(receipt, binding=binding)
    initial["environment"]["status"] = "DRIFTED"
    initial["environment"]["before_sha256"] = "0" * 64
    episode = {
        "stage": "initial_completed",
        "schedule": schedule,
        "workspace": str(runner.WORKSPACE_ROOT / schedule["schedule_id"]),
        "nonce": "f" * 32,
        "initial": initial,
    }
    try:
        runner.validate_episode_checkpoint(
            episode, schedule, expected, "codex", binding)
    except ValueError as exc:
        assert "tainted environment" in str(exc)
    else:
        raise AssertionError("environment-drifted exact evidence remained scored")


def test_combined_environment_and_workspace_drift_remains_resumable_unscored():
    binding = build_test_binding()
    expected = {"harness": "inactive", "reason": "routine"}
    receipt = {"schema_version": 1, **expected}
    invocation = checkpoint_invocation(receipt, binding=binding)
    environment_sha = runner.bound_runtime_environment_fingerprint(binding, "codex")
    invocation["environment"] = {
        "status": "DRIFTED",
        "binding_sha256": environment_sha,
        "before_sha256": environment_sha,
        "after_sha256": "0" * 64,
    }
    runner.invalidate_invocation_for_workspace_drift(invocation)
    runner.validate_invocation_checkpoint(
        invocation, "initial", "codex", expected, binding)
    assert invocation["process_reason"] == "workspace_drift_during_call"
    assert invocation["environment"]["status"] == "DRIFTED"
    assert invocation["usage"] == {
        "status": "UNSCORED", "reason": "workspace_drift_during_call"}
    assert invocation["correct"] is None and invocation["receipt"] is None


def test_runtime_commands_freeze_models_reasoning_and_user_config():
    binding = {
        "runtime_bindings": {
            "codex": {
                "model": "gpt-codex",
                "reasoning_effort": "medium",
                "disabled_features": ["shell_tool"],
            },
            "hermes": {"model": "gpt-hermes", "provider": "openai-codex",
                       "reasoning_effort": "medium", "toolsets": "context_engine"},
        }
    }
    with tempfile.TemporaryDirectory() as tmp:
        workspace = Path(tmp)
        command, stdin = runner.runtime_command(
            "codex", binding, workspace, "PROMPT", workspace / "final.txt")
        joined = " ".join(command)
        assert "--ignore-user-config" in command and "gpt-codex" in command
        assert "--strict-config" in command and "--ignore-rules" not in command
        assert command[command.index("--disable") + 1] == "shell_tool"
        assert 'model_reasoning_effort="medium"' in command
        assert stdin == "PROMPT" and "read-only" in joined
        command, stdin = runner.runtime_command(
            "hermes", binding, workspace, "PROMPT", workspace / "unused.txt")
        assert "--ignore-user-config" in command
        assert "--ignore-rules" not in command
        assert "gpt-hermes" in command and "openai-codex" in command
        assert "context_engine" in command
        assert "file" not in command and "hermes-cli" not in command and stdin == ""


def test_observation_projects_completed_pairs_without_raw_output():
    cases = runner.load_cases(CASES)
    schedule = runner.build_schedule(cases, "fixed-seed")
    runtime_schedule = [row for row in schedule if row["runtime"] == "codex"]
    episodes = {}
    for item in runtime_schedule:
        episodes[str(item["index"])] = {
            "stage": "completed",
            "schedule": item,
            "row": runner.invocations_to_row(
                item["case_id"], invocation(correct=True), None),
        }
    progress = {"episodes": episodes}
    binding = {
        "experiment_id": "binding-v1",
        "case_set_id": "cases-v1",
        "parity_fingerprints": {"codex": "f" * 64},
    }
    observation = runner.observation_from_progress(progress, binding, "codex", cases)
    assert len(observation["control"]["cases"]) == 6
    assert len(observation["treatment"]["cases"]) == 6
    assert observation["binding_fingerprint"] == "f" * 64
    assert "stdout" not in json.dumps(observation).lower()


def build_test_binding():
    original = runner.executable_identity
    original_home = runner.runtime_home_binding

    def fake_identity(name):
        identity = {
            "executable": name, "resolved_basename": name + ".exe",
            "resolved_sha256": ("a" if name == "codex" else "b") * 64,
            "resolved_size_bytes": 10, "version": name + " 1.0",
        }
        if name == "codex":
            identity["runtime_source"] = {
                "install_mode": "npm_package",
                "package_name": "@openai/codex",
                "package_version": "1.0",
                "package_tree": {
                    "file_count": 2,
                    "total_bytes": 10,
                    "tree_sha256": "3" * 64,
                },
                "node": {
                    "basename": "node.exe",
                    "sha256": "4" * 64,
                    "size_bytes": 10,
                },
            }
        else:
            identity["runtime_source"] = {
                "install_mode": "editable_project",
                "ignored_project_fallbacks_absent": ["cli-config.yaml", ".env"],
                "project_git": {
                    "git_head": "c" * 40,
                    "git_status_sha256": "d" * 64,
                    "changed_content_sha256": "e" * 64,
                    "changed_entry_count": 2,
                    "untracked_entry_count": 1,
                    "dirty": True,
                    "worktree_fingerprint": "f" * 64,
                },
                "python_environment": {
                    "distribution_count": 2,
                    "distribution_set_sha256": "1" * 64,
                    "python_sha256": "2" * 64,
                    "python_size_bytes": 10,
                },
            }
        return identity

    def fake_home(name, experiment_id, provider=None):
        return {
            "policy": "per-invocation-clean-auth-only",
            "environment_variable": "CODEX_HOME" if name == "codex" else "HERMES_HOME",
            "credential_source": "auth.json",
            "credential_identity_method": "experiment-scoped-stable-account-sha256",
            "credential_identity_sha256": ("5" if name == "codex" else "6") * 64,
            "cleared_environment_prefixes": [
                "CODEX_", "HERMES_", "OPENAI_", "AZURE_OPENAI_"],
            "cleared_environment_variables": list(runner.TRANSPORT_OVERRIDE_ENV),
            "rebuilt_environment": runner.REBUILT_ENVIRONMENT,
            "cross_runtime_home_variable": (
                "HERMES_HOME" if name == "codex" else "CODEX_HOME"),
            "cross_runtime_home_policy": "isolated-disposable-path-under-runtime-home",
            "initial_files": ["auth.json"] + (["SOUL.md"] if name == "hermes" else []),
            "global_rules_loaded": False,
            "memory_loaded": False,
            "credentials_persist_after_call": False,
            "hermes_telemetry": "isolated_home_state_db" if name == "hermes" else "not_applicable",
        }

    runner.executable_identity = fake_identity
    runner.runtime_home_binding = fake_home
    try:
        binding = runner.build_binding(SimpleNamespace(
            seed="seed-v1",
            experiment_id="binding-test",
            codex_model="gpt-5.6-sol",
            hermes_model="gpt-5.6-luna",
            hermes_provider="openai-codex",
            reasoning_effort="medium",
        ))
    finally:
        runner.executable_identity = original
        runner.runtime_home_binding = original_home
    return binding


def test_binding_builder_freezes_all_instruments_and_keeps_cases_out_of_parity():
    binding = build_test_binding()
    assert set(binding["frozen_input_sha256"]) == set(runner.FROZEN_INPUTS)
    assert len(binding["schedule"]) == 24
    frozen_fingerprint = binding["parity_fingerprints"]["codex"]
    changed = json.loads(json.dumps(binding))
    changed["case_set_id"] = "a-disjoint-future-case-set"
    assert runner.sha256_bytes(
        runner.canonical_json(runner.parity_payload(changed, "codex")).encode("utf-8")) == frozen_fingerprint
    changed = json.loads(json.dumps(binding))
    changed["frozen_input_sha256"]["benchmarks/adaptive_loop/rules_v1.json"] = "c" * 64
    assert runner.sha256_bytes(
        runner.canonical_json(runner.parity_payload(changed, "codex")).encode("utf-8")) != frozen_fingerprint


def test_live_semantic_inputs_load_from_immutable_git_blobs():
    binding = build_test_binding()
    original_cases = runner.load_cases
    original_design = runner.load_design
    runner.load_cases = lambda *args, **kwargs: (_ for _ in ()).throw(
        AssertionError("worktree case loader was used"))
    runner.load_design = lambda *args, **kwargs: (_ for _ in ()).throw(
        AssertionError("worktree design loader was used"))
    try:
        assert len(runner.load_frozen_cases(binding)) == 6
        assert runner.load_frozen_design(binding)["frozen_before_new_live_outputs"] is True
    finally:
        runner.load_cases = original_cases
        runner.load_design = original_design


def test_binding_schema_rejects_missing_experiment_id_or_schedule_hash():
    binding = build_test_binding()
    runner.validate_binding_structure(binding)
    for missing in ("experiment_id", "schedule_sha256"):
        forged = json.loads(json.dumps(binding))
        forged.pop(missing)
        without_fingerprint = {key: value for key, value in forged.items()
                               if key != "binding_fingerprint"}
        forged["binding_fingerprint"] = runner.sha256_bytes(
            runner.canonical_json(without_fingerprint).encode("utf-8"))
        try:
            runner.validate_binding_structure(forged)
        except ValueError as exc:
            assert "binding" in str(exc)
        else:
            raise AssertionError(f"binding without {missing} passed structural validation")


def test_binding_schema_rejects_nested_runtime_policy_mutations():
    def resign(binding):
        binding["parity_fingerprints"] = {
            runtime: runner.sha256_bytes(
                runner.canonical_json(runner.parity_payload(binding, runtime)).encode("utf-8"))
            for runtime in runner.RUNTIMES
        }
        unsigned = {key: value for key, value in binding.items()
                    if key != "binding_fingerprint"}
        binding["binding_fingerprint"] = runner.sha256_bytes(
            runner.canonical_json(unsigned).encode("utf-8"))

    mutations = (
        lambda value: value["runtime_bindings"]["codex"]["home_isolation"].pop(
            "credential_identity_sha256"),
        lambda value: value["runtime_bindings"]["codex"].__setitem__(
            "sandbox", "workspace-write"),
        lambda value: value["runtime_bindings"]["hermes"].__setitem__(
            "provider", "different-provider"),
        lambda value: value.__setitem__(
            "instrument_python", r"Python built at C:\Users\fixture\python.exe"),
    )
    for mutate in mutations:
        forged = json.loads(json.dumps(build_test_binding()))
        mutate(forged)
        resign(forged)
        try:
            runner.validate_binding_structure(forged)
        except ValueError as exc:
            assert "binding" in str(exc)
        else:
            raise AssertionError("mutated nested runtime binding passed validation")


def test_authenticated_progress_rejects_self_consistent_forgery_and_rollback():
    binding = build_test_binding()
    cases = runner.load_cases(CASES)
    schedule = next(
        row for row in binding["schedule"] if row["runtime"] == "codex")
    case = next(item for item in cases if item["id"] == schedule["case_id"])
    receipt = {"schema_version": 1, **case["expected"]}
    initial = checkpoint_invocation(receipt, binding=binding)
    episode = {
        "stage": "completed",
        "schedule": schedule,
        "workspace": str(runner.WORKSPACE_ROOT / schedule["schedule_id"]),
        "nonce": "f" * 32,
        "initial": initial,
        "row": runner.invocations_to_row(case["id"], initial, None),
        "workspace_cleanup": "removed",
    }
    progress = runner.new_progress(binding, "codex")
    progress["episodes"][str(schedule["index"])] = episode
    original_root = runner.CHECKPOINT_STATE_ROOT
    with tempfile.TemporaryDirectory() as tmp:
        runner.CHECKPOINT_STATE_ROOT = Path(tmp) / "checkpoint-state"
        try:
            progress_path = Path(tmp) / "progress.json"
            state_path = runner.checkpoint_state_path(binding, "codex")
            state = runner.new_checkpoint_state(binding, "codex")
            runner.write_checkpoint_state(state_path, state)
            runner.write_authenticated_progress(progress_path, progress, state_path, state)
            signed_sequence_zero = json.loads(json.dumps(progress))

            forged = json.loads(json.dumps(progress))
            forged_invocation = forged["episodes"][str(schedule["index"])]["initial"]
            forged_invocation["usage"]["input_tokens"] = 500_000
            forged_invocation["usage"]["total_tokens"] = 500_002
            forged["episodes"][str(schedule["index"])]["row"] = (
                runner.invocations_to_row(case["id"], forged_invocation, None))
            runner.atomic_write_json(progress_path, forged)
            try:
                runner.verify_authenticated_progress(forged, state_path, state)
            except ValueError as exc:
                assert "authentication" in str(exc)
            else:
                raise AssertionError("self-consistent forged exact evidence was accepted")

            rollback_copy = json.loads(json.dumps(signed_sequence_zero))
            progress = json.loads(json.dumps(signed_sequence_zero))
            progress["episodes"][str(schedule["index"])][
                "workspace_cleanup"] = "already_missing"
            runner.write_authenticated_progress(progress_path, progress, state_path, state)
            runner.atomic_write_json(progress_path, rollback_copy)
            try:
                runner.verify_authenticated_progress(
                    rollback_copy, state_path, state)
            except ValueError as exc:
                assert "rollback" in str(exc)
            else:
                raise AssertionError("authenticated progress rollback was accepted")
        finally:
            runner.CHECKPOINT_STATE_ROOT = original_root


def test_started_progress_is_marked_interrupted_without_runtime_retry():
    binding = build_test_binding()
    cases = runner.load_cases(CASES)
    case = cases[0]
    schedule = {
        "index": 999,
        "schedule_id": "S999-codex-AL01-control-test",
        "runtime": "codex",
        "case_id": case["id"],
        "arm": "control",
    }
    workspace = runner.WORKSPACE_ROOT / schedule["schedule_id"]
    runner.WORKSPACE_ROOT.mkdir(parents=True, exist_ok=True)
    if workspace.exists():
        runner.cleanup_episode_workspace(workspace)
    design = json.loads(DESIGN.read_text(encoding="utf-8"))
    progress = {
        "schema_version": runner.SCHEMA_VERSION,
        "experiment_id": binding["experiment_id"],
        "binding_fingerprint": binding["binding_fingerprint"],
        "runtime": "codex",
        "schedule": [schedule],
        "checkpoint_sequence": -1,
        "checkpoint_mac": None,
        "episodes": {"999": {
        "stage": "initial_started",
        "schedule": schedule,
        "workspace": str(workspace),
        "nonce": "a" * 32,
    }}}
    original = runner.run_invocation
    original_checkpoint_root = runner.CHECKPOINT_STATE_ROOT
    runner.run_invocation = lambda *args, **kwargs: (_ for _ in ()).throw(
        AssertionError("uncertain call was retried"))
    try:
        with tempfile.TemporaryDirectory() as tmp:
            runner.CHECKPOINT_STATE_ROOT = Path(tmp) / "checkpoint-state"
            progress_path = Path(tmp) / "progress.json"
            checkpoint_path = runner.checkpoint_state_path(binding, "codex")
            checkpoint_state = runner.new_checkpoint_state(binding, "codex")
            runner.write_checkpoint_state(checkpoint_path, checkpoint_state)
            runner.write_authenticated_progress(
                progress_path, progress, checkpoint_path, checkpoint_state)
            runner.run_episode(
                progress, progress_path, schedule, case, binding, design, None,
                checkpoint_path, checkpoint_state)
            runner.CHECKPOINT_STATE_ROOT = original_checkpoint_root
    finally:
        runner.run_invocation = original
        runner.CHECKPOINT_STATE_ROOT = original_checkpoint_root
    episode = progress["episodes"]["999"]
    assert episode["stage"] == "completed"
    assert episode["row"]["initial_correct"] is None
    assert episode["initial"]["process_reason"] == "initial_call_interrupted_no_retry"
    assert set(episode["initial"]["usage"]) == {"status", "reason"}
    runner.validate_episode_checkpoint(
        episode, schedule, case["expected"], "codex", binding)


def test_workspace_mutation_during_call_is_unscored_without_corrective_rework():
    binding = build_test_binding()
    case = runner.load_cases(CASES)[0]
    schedule = {
        "index": 998,
        "schedule_id": "S998-codex-AL01-control-workspace-drift",
        "runtime": "codex",
        "case_id": case["id"],
        "arm": "control",
    }
    workspace = runner.WORKSPACE_ROOT / schedule["schedule_id"]
    runner.WORKSPACE_ROOT.mkdir(parents=True, exist_ok=True)
    if workspace.exists():
        runner.cleanup_episode_workspace(workspace)
    design = json.loads(DESIGN.read_text(encoding="utf-8"))
    progress = {
        "schema_version": runner.SCHEMA_VERSION,
        "experiment_id": binding["experiment_id"],
        "binding_fingerprint": binding["binding_fingerprint"],
        "runtime": "codex",
        "schedule": [schedule],
        "checkpoint_sequence": -1,
        "checkpoint_mac": None,
        "episodes": {},
    }
    original_invocation = runner.run_invocation
    original_checkpoint_root = runner.CHECKPOINT_STATE_ROOT

    def mutate_workspace(*args, **kwargs):
        workspace_path = args[2]
        (workspace_path / "unexpected.txt").write_text(
            "task work must invalidate the probe", encoding="utf-8")
        receipt = {"schema_version": 1, **case["expected"]}
        return checkpoint_invocation(receipt, binding=binding)

    runner.run_invocation = mutate_workspace
    try:
        with tempfile.TemporaryDirectory() as tmp:
            runner.CHECKPOINT_STATE_ROOT = Path(tmp) / "checkpoint-state"
            checkpoint_path = runner.checkpoint_state_path(binding, "codex")
            checkpoint_state = runner.new_checkpoint_state(binding, "codex")
            runner.write_checkpoint_state(checkpoint_path, checkpoint_state)
            progress_path = Path(tmp) / "progress.json"
            runner.write_authenticated_progress(
                progress_path, progress, checkpoint_path, checkpoint_state)
            runner.run_episode(
                progress, progress_path, schedule, case, binding, design, None,
                checkpoint_path, checkpoint_state)
    finally:
        runner.run_invocation = original_invocation
        runner.CHECKPOINT_STATE_ROOT = original_checkpoint_root
        if workspace.exists():
            runner.cleanup_episode_workspace(workspace)
    episode = progress["episodes"]["998"]
    assert episode["stage"] == "completed"
    assert episode["initial"]["process_reason"] == "workspace_drift_during_call"
    assert episode["initial"]["usage"] == {
        "status": "UNSCORED", "reason": "workspace_drift_during_call"}
    assert episode["row"]["initial_correct"] is None
    assert episode["row"]["corrective_invocations"] == 0
    assert "corrective" not in episode
    runner.validate_episode_checkpoint(
        episode, schedule, case["expected"], "codex", binding)


TESTS = [
    test_cases_are_six_unseen_typed_episodes,
    test_schedule_is_deterministic_adjacent_and_complete,
    test_corrective_prompt_replays_original_then_appends_exactly_two_fields,
    test_prompt_freezes_marker_evidence_and_requires_zero_tool_use,
    test_codex_usage_subtracts_cached_subset_without_double_counting,
    test_codex_usage_accepts_separate_cache_schema_and_rejects_ambiguity,
    test_codex_usage_rejects_multiple_terminal_snapshots_instead_of_max_compositing,
    test_invocation_rows_measure_actual_corrective_work,
    test_nonexact_corrective_work_makes_total_usage_unscored,
    test_resume_state_machine_never_retries_an_uncertain_call,
    test_arm_entrypoints_are_extracted_from_frozen_git_blobs,
    test_workspace_must_be_outside_repo_and_contains_only_arm_entrypoints,
    test_workspace_rejects_all_ambient_codex_and_hermes_rule_files,
    test_recursive_cleanup_refuses_any_path_outside_dedicated_root,
    test_git_worktree_identity_detects_dirty_and_untracked_source_without_leaking_paths,
    test_directory_tree_identity_detects_codex_payload_drift_without_leaking_paths,
    test_hermes_executable_identity_includes_source_and_environment_fingerprints,
    test_hermes_ignored_project_config_fallbacks_must_be_absent,
    test_live_observation_name_cannot_impersonate_another_progress_file,
    test_codex_final_receipt_is_outside_episode_and_scrubbed_before_rework,
    test_base_process_runner_passes_an_explicit_isolated_environment,
    test_per_invocation_runtime_homes_copy_credentials_only_and_are_scrubbed,
    test_credential_identity_ignores_token_refresh_but_detects_account_drift,
    test_primary_and_cross_runtime_credentials_are_removed_when_tree_cleanup_is_pending,
    test_windows_reparse_detector_supports_pre_python_312_stat_shape,
    test_windows_junction_cleanup_never_deletes_external_auth,
    test_pending_link_cleanup_blocks_recursive_tree_cleanup,
    test_stale_scoped_credentials_are_scrubbed_before_invalid_source_auth_fails,
    test_single_run_lock_rejects_a_concurrent_writer_and_releases_cleanly,
    test_binding_runtime_has_one_canonical_output_and_external_state_db_is_rejected,
    test_shallow_forged_checkpoint_cannot_trigger_a_corrective_call,
    test_fully_shaped_checkpoint_rederives_oracle_and_canonical_token_total,
    test_environment_drift_cannot_remain_scored_in_a_checkpoint,
    test_combined_environment_and_workspace_drift_remains_resumable_unscored,
    test_runtime_commands_freeze_models_reasoning_and_user_config,
    test_observation_projects_completed_pairs_without_raw_output,
    test_binding_builder_freezes_all_instruments_and_keeps_cases_out_of_parity,
    test_live_semantic_inputs_load_from_immutable_git_blobs,
    test_binding_schema_rejects_missing_experiment_id_or_schedule_hash,
    test_binding_schema_rejects_nested_runtime_policy_mutations,
    test_authenticated_progress_rejects_self_consistent_forgery_and_rollback,
    test_started_progress_is_marked_interrupted_without_runtime_retry,
    test_workspace_mutation_during_call_is_unscored_without_corrective_rework,
]


def main():
    passed = failed = 0
    for test in TESTS:
        try:
            test()
            print(f"ok {test.__name__}")
            passed += 1
        except Exception as exc:
            print(f"FAIL {test.__name__}: {exc!r}")
            failed += 1
    print(f"{passed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
