"""Regression checks for portable runtime wiring output."""

import importlib.util
from pathlib import Path


REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "setup_harness.py"
_spec = importlib.util.spec_from_file_location("setup_harness", SCRIPT)
setup = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(setup)


def test_print_wiring_includes_target_rollback_for_codex_and_hermes():
    text = setup.WIRING.format(repo="C:/example/harness")
    assert "TARGET repository root" in text
    assert ".fable-harness-off" in text
    assert "Create <target-repository>/HERMES.md" in text
    assert "<target-repository>/.fable-harness-off" in text
    assert "<target-repository>/AGENTS.md when present" in text
    assert "C:/example/harness/core/GLOBAL_BOOTSTRAP.md" in text


if __name__ == "__main__":
    test_print_wiring_includes_target_rollback_for_codex_and_hermes()
    print("ok test_print_wiring_includes_target_rollback_for_codex_and_hermes")
