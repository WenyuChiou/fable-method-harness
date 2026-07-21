#!/usr/bin/env python3
"""Static regression checks for the shared Codex/Hermes activation contract."""

from pathlib import Path


REPO = Path(__file__).resolve().parent.parent
AGENTS = (REPO / "AGENTS.md").read_text(encoding="utf-8")
HERMES = (REPO / "HERMES.md").read_text(encoding="utf-8")
CONTRACT = (REPO / "docs" / "runtime_activation_contract.md").read_text(encoding="utf-8")


def test_both_runtime_entrypoints_support_probe_and_marker_rollback():
    for text in (AGENTS, HERMES):
        assert "FABLE_ACTIVATION_PROBE" in text
        assert ".fable-harness-off" in text
        assert '"schema_version":1' in text


def test_contract_covers_trigger_routine_and_rollback_outcomes():
    normalized = " ".join(CONTRACT.split())
    for outcome in ("trigger recall", "routine over-trigger", "rollback obedience"):
        assert outcome in normalized
    assert "UNSCORED" in normalized
    assert "one and only one new session" in normalized


def test_hermes_shim_stays_small_and_defers_full_policy_until_activation():
    assert len(HERMES.encode("utf-8")) <= 1800
    assert "repository-root `AGENTS.md`" in HERMES
    assert "Do not load the full harness" in HERMES


TESTS = [value for name, value in sorted(globals().items()) if name.startswith("test_")]


def main() -> int:
    passed = failed = 0
    for test in TESTS:
        try:
            test()
            print(f"ok {test.__name__}")
            passed += 1
        except Exception as exc:  # noqa: BLE001
            print(f"FAIL {test.__name__}: {exc}")
            failed += 1
    print(f"{passed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
