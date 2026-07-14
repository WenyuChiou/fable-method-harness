#!/usr/bin/env python3
"""Tier-0 presence + posture check for the adaptive-harness layer.

Deterministic, offline, stdlib-only (same class as check_agent_artifacts.py,
which owns the agent-optimization overlay; THIS validator owns the adaptive
layer added 2026-07-06). Wired into scripts/hooks/pre-commit so a commit
cannot land with (a) a missing wiring artifact, (b) a resurrected
private-repo posture claim, or (c) a runner whose report-only keywords
vanished (DR-011 no-silent-pass).

Checks:
    1. Every adaptive-layer artifact exists and carries its load-bearing
       keywords (skill adapter lists all 10 modes; integration doc has the
       five responsibility sections; runners state report-only).
    2. Posture: content surfaces contain NO stale private-repo claims
       ("stays private", "private remote", "private_until_reviewed",
       "must never be made public", "a private operating harness") - the repo
       is PUBLIC (docs/publication_status.md). Scanned surface: the 7 root
       entry/governance files + context/, docs/, core/, prompts/, .claude/,
       operating_model/, playbooks/, rubrics/, validation/, schemas/,
       benchmarks/ (.md/.yaml/.yml). Exempt by design: memory/, datasets/,
       examples/, distillation/ (append-only history + records ABOUT the
       still-private source project) and scripts/ (test files carry the
       forbidden phrases as string literals). In publication_status.md only
       lines quoting the superseded policy (containing 'private_repo_setup')
       are exempt.
    3. ROUTES.yaml entrypoints include the adaptive-harness skill adapter.

Run:
    python scripts/check_adaptive_harness.py

Exit codes:
    0  all artifacts present, keywords found, no posture conflicts
    1  any gap
"""
import re
import sys
from pathlib import Path

repo_root = Path(__file__).resolve().parent.parent

REQUIRED = {
    ".claude/skills/adaptive-harness/SKILL.md": [
        "harness_inventory", "harness_cleanup_review", "code_invocation_review",
        "ai_review_integration", "skill_fit_review", "diff_only_review",
        "scheduled_harness_review", "experiment_design", "patch_proposal",
        "rolling_improvement_review", "report-only", "human",
    ],
    "docs/ai_review_adaptive_harness_integration.md": [
        "AI-review", "adaptive-harness", "deterministic scripts", "LLM",
        "human", "shared schemas", "rolling improvement",
    ],
    "docs/publication_status.md": [
        "PUBLIC", "never-include", "public-safety review", "checklist",
    ],
    "docs/codex-delegation-policy.md": [
        "tripwire", "brief", "never commit", "review",
    ],
    "schemas/review_report.schema.yaml": ["review_id", "scheduled_runner", "recommendations"],
    "schemas/recommendation.schema.yaml": ["recommendation_id", "source_review_id", "requires_human_approval"],
    "scripts/run_ai_review.py": ["scheduled_review", "report-only", "--dry-run"],
    "scripts/run_adaptive_harness_review.py": [
        "rolling_improvement_review", "patch_proposal", "report-only", "read-ai-review",
    ],
    "prompts/ai-review-modes.md": ["standard_review", "experiment_review", "ingest"],
    "benchmarks/ai_review_cases.yaml": ["case_name", "linked_recommendation_id"],
    "benchmarks/harness_cases.yaml": ["case_name", "linked_recommendation_id"],
    "SKILL.md": ["adaptive-harness"],  # root launcher documents the adapter relationship
    # Universal-entry wiring (2026-07-06, user request): every non-Claude
    # runtime's entry file must point at the adaptive-harness system.
    "AGENTS.md": ["adaptive-harness", "Harness-maintenance path"],
    "BOOTSTRAP.md": ["adaptive-harness"],
    "prompts/hermes-router.md": ["harness maintenance", "adaptive-harness"],
}

# Posture claims that must not reappear on the world-facing surface.
FORBIDDEN_POSTURE = [
    "stays private",
    "private remote",
    "private_until_reviewed",
    "must never be made public",
    "a private operating harness",
    "no public remote",
]

# Surfaces the posture rule applies to (entry + governance + routed content).
POSTURE_SURFACES = ["README.md", "AGENTS.md", "SKILL.md", "BOOTSTRAP.md",
                    "HARNESS.yaml", "INDEX.yaml", "ROUTES.yaml"]
POSTURE_DIRS = ["context", "docs", "core", "prompts", ".claude",
                "operating_model", "playbooks", "rubrics", "validation",
                "schemas", "benchmarks"]


def read_text(rel_path):
    try:
        return (repo_root / rel_path).read_text(encoding="utf-8")
    except (FileNotFoundError, OSError):
        return None


def check_artifacts(quiet=False):
    failures = []
    for rel_path, keywords in REQUIRED.items():
        text = read_text(rel_path)
        if text is None:
            failures.append("MISSING FILE {}".format(rel_path))
            continue
        low = text.lower()
        missing = [k for k in keywords if k.lower() not in low]
        if missing:
            failures.append("FAIL {}: missing keywords {}".format(rel_path, missing))
        elif not quiet:
            print("OK {} ({} keywords)".format(rel_path, len(keywords)))
    return failures


def posture_files():
    # "worktrees" exclusion: .claude/worktrees/<name>/ holds full repo
    # copies whose nested files inherit none of the top-level posture
    # exemptions — scanning them produced false-positive POSTURE blocks
    # at commit time (2026-07-11 incident; recurs with any linked worktree).
    files = [repo_root / p for p in POSTURE_SURFACES]
    for d in POSTURE_DIRS:
        base = repo_root / d
        if base.is_dir():
            files.extend(p for p in base.rglob("*")
                         if p.is_file() and p.suffix in (".md", ".yaml", ".yml")
                         and "worktrees" not in p.parts)
    return files


def check_posture():
    failures = []
    for f in posture_files():
        text = f.read_text(encoding="utf-8", errors="replace") if f.is_file() else None
        if text is None:
            continue
        rel = f.relative_to(repo_root).as_posix()
        low = text.lower()
        for phrase in FORBIDDEN_POSTURE:
            if phrase in low:
                for i, line in enumerate(text.splitlines(), 1):
                    if phrase not in line.lower():
                        continue
                    # The one sanctioned form: publication_status.md quoting the
                    # superseded policy it replaced (line names the old file).
                    if (rel == "docs/publication_status.md"
                            and "private_repo_setup" in line):
                        continue
                    failures.append(
                        "POSTURE {}:{}: stale private-repo claim '{}'".format(rel, i, phrase))
    return failures


def check_entrypoint(quiet=False):
    routes = read_text("ROUTES.yaml") or ""
    if ".claude/skills/adaptive-harness/SKILL.md" not in routes:
        return ["FAIL ROUTES.yaml: adaptive-harness skill adapter missing from entrypoints"]
    if not quiet:
        print("OK ROUTES.yaml entrypoints include the adaptive-harness adapter")
    return []


def main():
    # --quiet: suppress OK lines; failures and the summary print verbatim.
    quiet = "--quiet" in sys.argv[1:]
    artifact_failures = check_artifacts(quiet=quiet)
    failures = artifact_failures + check_posture() + check_entrypoint(quiet=quiet)
    for f in failures:
        print(f)
    n_ok = len(REQUIRED) - len(artifact_failures)
    print("{}/{} adaptive-layer artifacts OK; {} posture conflict(s)".format(
        n_ok, len(REQUIRED), sum(1 for f in failures if f.startswith("POSTURE"))))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
