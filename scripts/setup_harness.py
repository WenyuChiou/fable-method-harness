#!/usr/bin/env python3
"""Post-clone setup for the adaptive harness - runnable by ANY agent or human.

Idempotent, stdlib-only, offline. Deterministic actions only; nothing here
needs judgment, which is exactly why an AI of any tier (Codex, Hermes,
Claude, a shell script) can run it safely. Re-running is always safe.

Default actions (no flags):
    1. git config core.hooksPath scripts/hooks   (enable the pre-commit gates)
    2. run validation/integration_check.py        (53 self-checks; proves the clone works)

Opt-in flags:
    --wire-skill    install a launcher STUB at ~/.claude/skills/adaptive-harness/
                    (Claude Code auto-discovery everywhere; the stub points at
                    THIS clone - single source of truth stays in the repo)
    --wire-claude   append the two pointer lines to ~/.claude/CLAUDE.md
                    (created if absent; skipped if the pointer already exists)
    --schedule      register the weekly report-only scan (Windows Task Scheduler;
                    prints the crontab line on other platforms)
    --print-wiring  print per-runtime wiring snippets (Claude Code / Codex /
                    Cursor / OpenCode / Hermes / plain shell) and exit
    --dry-run       show what would be done; write nothing
    --skip-check    skip the integration check (e.g. on very slow machines)

Exit codes: 0 = everything requested succeeded; 1 = something failed (stated).
"""

import argparse
import io
import os
import subprocess
import sys
from pathlib import Path

if sys.version_info < (3, 8):
    sys.exit("setup_harness.py requires Python >= 3.8")

REPO = Path(__file__).resolve().parent.parent
HOME_CLAUDE = Path(os.path.expanduser("~/.claude"))


def utf8():
    for n in ("stdout", "stderr"):
        s = getattr(sys, n)
        if hasattr(s, "buffer"):
            setattr(sys, n, io.TextIOWrapper(s.buffer, encoding="utf-8", errors="replace"))


def run(cmd, cwd=None):
    return subprocess.run(cmd, cwd=str(cwd or REPO), capture_output=True,
                          text=True, encoding="utf-8", errors="replace")


STUB_TEMPLATE = """---
name: adaptive-harness
description: {description}
---

# adaptive-harness (launcher stub)

Installed by `setup_harness.py` on {installed_from}. The full skill - modes,
improvement loop, safety boundaries, runtime portability - is the single source
of truth in the harness clone. READ IT AND FOLLOW IT:

    {skill_path}

Deterministic runners (any tier, plain Python, no dependencies):

    python "{repo}/scripts/run_ai_review.py" --mode <mode> [--target <repo>]
    python "{repo}/scripts/run_adaptive_harness_review.py" --mode <mode> [--target <repo>]

If the clone has moved, reinstall this stub:
    python <new-clone>/scripts/setup_harness.py --wire-skill
"""

POINTER_SENTINEL = "<!-- adaptive-harness:wire-claude-pointer -->"

CLAUDE_MD_POINTER = """
""" + POINTER_SENTINEL + """
## Fable-method Adaptive Harness
For large, multi-agent, high-risk, or phase-gated tasks: read
`{repo}/core/GLOBAL_BOOTSTRAP.md` and follow its ROUTES. For auditing /
simplifying / maintaining an AI harness (this file included): read
`{repo}/.claude/skills/adaptive-harness/SKILL.md`.
"""

WIRING = """
=== Per-runtime wiring (copy what applies) ===

Claude Code (global auto-discovery):
    python "{repo}/scripts/setup_harness.py" --wire-skill --wire-claude

Codex CLI / Cursor / OpenCode / any AGENTS.md-convention agent:
    Working inside this clone: nothing to do - AGENTS.md is auto-read.
    For OTHER repos, add to that repo's (or your global) AGENTS.md:
        For large, multi-agent, high-risk, phase-gated, or completion-sensitive tasks:
            read {repo}/core/GLOBAL_BOOTSTRAP.md and follow its routing.
        For AI-harness maintenance, README/evidence work, AGENTS.md/CLAUDE.md/hooks/skills/settings review:
            read {repo}/.claude/skills/adaptive-harness/SKILL.md.
        Runners are plain Python CLIs; never act as final authority - see
        {repo}/docs/codex-delegation-policy.md

Hermes / any router surface - add a routing row:
    harness maintenance (audit/simplify/benchmark an AI setup) ->
    deterministic scans: python "{repo}/scripts/run_ai_review.py" (run directly);
    semantic checklists -> route to a strong-reasoning surface.

Plain shell / cron (report-only scan, cannot modify anything):
    python "{repo}/scripts/run_ai_review.py" --mode scheduled_review
    Windows weekly task: "{repo}/scripts/register_scheduled_scan.bat"
    crontab example: 5 9 * * 1 python "{repo}/scripts/run_ai_review.py" --mode scheduled_review
"""


def read_repo_skill_description():
    skill = REPO / ".claude" / "skills" / "adaptive-harness" / "SKILL.md"
    text = skill.read_text(encoding="utf-8")
    # description: >- block in the frontmatter
    lines, capture, out = text.splitlines(), False, []
    for line in lines:
        if line.startswith("description:"):
            capture = True
            continue
        if capture:
            if line.startswith("  "):
                out.append(line.strip())
                continue
            break
    return " ".join(out) if out else "Audit, simplify, benchmark, and maintain AI/agent harnesses."


def main(argv=None):
    utf8()
    ap = argparse.ArgumentParser(prog="setup_harness.py",
                                 description="Post-clone setup, runnable by any agent.")
    ap.add_argument("--wire-skill", action="store_true")
    ap.add_argument("--wire-claude", action="store_true")
    ap.add_argument("--schedule", action="store_true")
    ap.add_argument("--print-wiring", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--skip-check", action="store_true")
    args = ap.parse_args(argv)

    if args.print_wiring:
        print(WIRING.format(repo=REPO.as_posix()))
        return 0

    failed = []

    def step(name, fn):
        if args.dry_run:
            print(f"[dry-run] would: {name}")
            return
        try:
            fn()
            print(f"[ok] {name}")
        except Exception as exc:  # noqa: BLE001 - report, don't crash the rest
            print(f"[FAIL] {name}: {exc}")
            failed.append(name)

    # 1. hooks
    def enable_hooks():
        r = run(["git", "config", "core.hooksPath", "scripts/hooks"])
        if r.returncode != 0:
            raise RuntimeError(r.stderr.strip()[:200])
    step("enable pre-commit gates (git config core.hooksPath scripts/hooks)", enable_hooks)

    # 2. integration check
    if not args.skip_check:
        def check():
            r = run([sys.executable, str(REPO / "validation" / "integration_check.py")])
            last = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.stderr[:200]
            if r.returncode != 0:
                raise RuntimeError(f"integration check failed: {last}")
            print(f"     {last}")
        step("verify the clone (validation/integration_check.py)", check)

    # 3. skill stub
    if args.wire_skill:
        def wire_skill():
            if not HOME_CLAUDE.is_dir():
                raise RuntimeError("~/.claude not found - is Claude Code installed? "
                                   "(skill wiring only applies to Claude Code)")
            dest = HOME_CLAUDE / "skills" / "adaptive-harness"
            dest.mkdir(parents=True, exist_ok=True)
            stub = STUB_TEMPLATE.format(
                description=read_repo_skill_description(),
                installed_from=REPO.as_posix(),
                skill_path=(REPO / ".claude/skills/adaptive-harness/SKILL.md").as_posix(),
                repo=REPO.as_posix())
            (dest / "SKILL.md").write_text(stub, encoding="utf-8")
            print(f"     stub -> {dest / 'SKILL.md'}")
        step("install global Claude Code skill stub (~/.claude/skills/adaptive-harness)", wire_skill)

    # 4. CLAUDE.md pointer
    if args.wire_claude:
        def wire_claude():
            target = HOME_CLAUDE / "CLAUDE.md"
            pointer = CLAUDE_MD_POINTER.format(repo=REPO.as_posix())
            if target.is_file():
                existing = target.read_text(encoding="utf-8")
                if POINTER_SENTINEL in existing:
                    print("     pointer already written by this script - skipped (idempotent)")
                    return
                if "adaptive-harness/SKILL.md" in existing or "GLOBAL_BOOTSTRAP.md" in existing:
                    # Not OUR block, but the user already references the harness.
                    # Appending would duplicate; skipping silently would mask a gap.
                    print("     NOTICE: CLAUDE.md already mentions the harness (hand-written,")
                    print("     not this script's block) - NOT appending, to avoid duplication.")
                    print("     Verify your existing pointer covers:")
                    print(f"       {REPO.as_posix()}/core/GLOBAL_BOOTSTRAP.md")
                    print(f"       {REPO.as_posix()}/.claude/skills/adaptive-harness/SKILL.md")
                    return
                target.write_text(existing.rstrip() + "\n" + pointer, encoding="utf-8")
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(pointer.lstrip(), encoding="utf-8")
            print(f"     pointer appended -> {target}")
        step("wire ~/.claude/CLAUDE.md pointer", wire_claude)

    # 5. schedule
    if args.schedule:
        def schedule():
            if os.name != "nt":
                print("     non-Windows: add this crontab line yourself:")
                print(f"     5 9 * * 1 {sys.executable} \"{REPO.as_posix()}/scripts/run_ai_review.py\" --mode scheduled_review")
                return
            r = run(["cmd", "/c", str(REPO / "scripts" / "register_scheduled_scan.bat")])
            if r.returncode != 0:
                raise RuntimeError((r.stdout + r.stderr).strip()[:200])
            print("     weekly report-only scan registered (Mon 09:05)")
        step("register weekly report-only scan", schedule)

    print()
    if failed:
        print(f"DONE WITH FAILURES: {failed}")
        return 1
    print("DONE. Wiring options for other runtimes: python scripts/setup_harness.py --print-wiring")
    return 0


if __name__ == "__main__":
    sys.exit(main())
