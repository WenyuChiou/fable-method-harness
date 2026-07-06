#!/usr/bin/env python3
"""AI-review runner - the deterministic engine of the /ai-review maintenance loop.

Division of labor (the Phase-1 contract this file enforces):
  - THIS SCRIPT (deterministic, code): repo inventory, INDEX/ROUTES integrity,
    diff scan, deprecated-marker scan, external telemetry harvest (calls the
    existing ~/.claude scripts - never reimplements them, DR-020), schema
    validation, JSON report assembly, JSON->Markdown rendering, history append.
  - LLM (semantic judgment): the per-mode checklists in prompts/ai-review-modes.md.
    Its findings enter ONLY via --ingest <findings.json>, validated against
    schemas/recommendation.schema.yaml's required fields + enums before merge.
  - HUMAN: decides what gets applied. This runner NEVER edits harness files;
    its only writes are report artifacts under --output (and none at all
    with --dry-run).

Safety invariants (do not weaken - see the mode prompts doc for rationale):
  - scheduled_review is report-only by design: source=scheduled_runner,
    deterministic collectors only, no ledger append, no proposals, no
    application of anything. The existing ~/.claude nudge pipeline
    (ClaudeAiReviewDue task -> .ai-review-due flag -> SessionStart hook)
    stays the human-summoning path.
  - The proposals ledger (~/.claude/audits/proposals.jsonl) is NEVER written
    directly or via CLI from here - read-only `status` harvest only. Writing
    it outside ai_review_ledger.py's lock reintroduces the W26#3 race.
  - claude_md_eval.py and audit_settings.py --apply are mutating and are
    deliberately NOT wrapped here.

Run:
    python scripts/run_ai_review.py --mode standard_review --dry-run
    python scripts/run_ai_review.py --mode harness_cleanup_review
    python scripts/run_ai_review.py --mode diff_review --since-ref main
    python scripts/run_ai_review.py --mode standard_review --ingest findings.json

Exit codes:
    0  report produced (written, or printed with --dry-run); an unreachable
       --since-ref outside --changed-files-only degrades to collector
       status "unavailable" in the report rather than failing the run
    1  validation error (invalid ingest findings, --ingest with
       scheduled_review, bad --changed-files-only ref, invalid report)
    2  usage error (argparse: unknown mode/flag) or target dir not found
"""

import argparse
import io
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

SCHEMA_REF = "fable-style-project-harness/schemas/review_report.schema.yaml"

MODES = {
    "standard_review": ["inventory", "index_integrity", "artifact_check", "home_telemetry"],
    "harness_cleanup_review": ["inventory", "index_integrity", "artifact_check",
                               "deprecated_markers", "home_telemetry"],
    "code_invocation_review": ["inventory", "home_telemetry"],
    "codex_delegation_review": ["codex_policy", "home_telemetry"],
    "scheduled_review": ["inventory", "index_integrity", "artifact_check",
                         "deprecated_markers", "home_telemetry"],
    "diff_review": ["diff", "inventory"],
    "experiment_review": ["experiments"],
}

# Semantic checklist anchor per mode (LLM side of the contract).
MODE_PROMPTS = "prompts/ai-review-modes.md"

RECOMMENDATION_ENUM = {"Keep", "Simplify", "Remove", "Replace", "Merge", "Cache", "Experiment"}
CONFIDENCE_ENUM = {"low", "medium", "high"}
PRIORITY_ENUM = {"P0", "P1", "P2", "P3"}
SOURCE_ENUM = {"ai_review", "adaptive_harness", "scheduled_runner", "manual_review"}
INVOCATION_TYPE_ENUM = {"script", "shell command", "tool", "subagent", "Codex",
                        "LLM-only", "hybrid", "hook"}
EXPERIMENT_STATUS_ENUM = {"proposed", "running", "completed", "rejected"}

RECOMMENDATION_REQUIRED = [
    "recommendation_id", "component_name", "component_type", "file_path",
    "current_purpose", "evidence_it_still_helps", "evidence_it_may_be_obsolete",
    "recommendation", "expected_impact", "risk_if_changed", "suggested_test",
    "confidence", "priority", "source_review_id",
]

INVOCATION_REQUIRED = [
    "invocation_name", "invocation_type", "current_usage_scenario",
    "value_provided", "likely_cost", "recommendation",
    "expected_efficiency_gain", "risk_if_changed", "suggested_test",
]

REPORT_REQUIRED = [
    "review_id", "review_date", "source", "mode", "files_inspected",
    "components_inspected", "issues_found", "obsolete_scaffolding",
    "inefficient_invocations", "recommendations", "experiments_proposed",
    "changes_made", "unresolved_questions", "metrics", "next_review_trigger",
]

# External deterministic pieces that already exist in the user's global harness.
# Contract: CALL them, never reimplement (DR-020). All read-only invocations.
HOME_COLLECTORS = [
    ("ai_review_scan", ["scripts/ai_review_scan.py", "--json",
                        "--skip-skill-scan", "--skip-coverage"]),
    ("hook_stats", ["scripts/hook_stats.py", "--days", "7", "--json"]),
    ("ledger_status", ["scripts/ai_review_ledger.py", "status"]),
    ("brain_health", ["scripts/brain_health.py", "--json"]),
]


def utf8_stdout():
    """Windows consoles default to cp950/cp1252; reports carry UTF-8 content."""
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name)
        if hasattr(stream, "buffer"):
            setattr(sys, stream_name,
                    io.TextIOWrapper(stream.buffer, encoding="utf-8", errors="replace"))


def run_cmd(cmd, cwd=None, timeout=120):
    """Run a subprocess; return (returncode, stdout, stderr). Never raises."""
    try:
        proc = subprocess.run(
            cmd, cwd=str(cwd) if cwd else None, capture_output=True,
            text=True, encoding="utf-8", errors="replace", timeout=timeout)
        return proc.returncode, proc.stdout or "", proc.stderr or ""
    except (OSError, subprocess.TimeoutExpired) as exc:
        return -1, "", str(exc)


def git(args, cwd):
    # core.quotepath=false keeps non-ASCII (e.g. CJK) filenames as raw UTF-8
    # instead of octal-escaped C-quoted strings.
    return run_cmd(["git", "-c", "core.quotepath=false"] + args, cwd=cwd)


def unquote_git_path(path):
    """Undo git's C-style path quoting ("a\\"b\\303\\244.md") when it still
    appears (control chars / embedded quotes / spaces in porcelain output)."""
    if not (len(path) >= 2 and path.startswith('"') and path.endswith('"')):
        return path
    inner = path[1:-1]
    out = bytearray()
    i = 0
    while i < len(inner):
        ch = inner[i]
        if ch == "\\" and i + 1 < len(inner):
            nxt = inner[i + 1]
            if nxt in "01234567" and i + 3 < len(inner):
                out.append(int(inner[i + 1:i + 4], 8))
                i += 4
                continue
            simple = {"n": 10, "t": 9, '"': 34, "\\": 92}
            if nxt in simple:
                out.append(simple[nxt])
                i += 2
                continue
        out.extend(ch.encode("utf-8"))
        i += 1
    return out.decode("utf-8", errors="replace")


# ---------------------------------------------------------------------------
# Collectors - each returns {"status": "ok"|"unavailable"|"skipped", ...data}.
# A collector that cannot run reports itself honestly instead of passing
# silently (DR-011).
# ---------------------------------------------------------------------------

def collect_inventory(target, scoped_files=None):
    """Counts of harness components in the target repo (read-only walk)."""
    categories = {
        "prompts": "prompts",
        "docs": "docs",
        "schemas": "schemas",
        "scripts": "scripts",
        "rubrics": "rubrics",
        "playbooks": "playbooks",
        "datasets": "datasets",
        "benchmarks": "benchmarks",
        "examples": "examples",
        "validation": "validation",
        "memory": "memory",
        "commands": ".claude/commands",
        "skills": ".claude/skills",
        "subagents": "agents",
        "hooks": "hooks",
    }
    counts = {}
    files = []
    for name, rel in categories.items():
        base = target / rel
        if not base.is_dir():
            continue
        found = [p for p in base.rglob("*")
                 if p.is_file() and "__pycache__" not in p.parts]
        counts[name] = len(found)
        files.extend(str(p.relative_to(target)).replace("\\", "/") for p in found)
    routes_file = target / "ROUTES.yaml"
    if routes_file.is_file():
        counts["routes"] = len(re.findall(r"^  - id: ROUTE-", routes_file.read_text(encoding="utf-8"), re.M))
    governance = {}
    for gov in ("CLAUDE.md", "AGENTS.md", "INDEX.yaml", "ROUTES.yaml", "SKILL.md"):
        p = target / gov
        if p.is_file():
            governance[gov] = len(p.read_text(encoding="utf-8", errors="replace").splitlines())
    if scoped_files is not None:
        files = [f for f in files if f in scoped_files]
    return {"status": "ok", "counts": counts, "governance_line_counts": governance,
            "files": sorted(files)}


def collect_index_integrity(target):
    """INDEX.yaml <-> disk drift, both directions. New deterministic coverage:
    nothing previously validated that INDEX matches disk (MT-5 was manual)."""
    index_file = target / "INDEX.yaml"
    if not index_file.is_file():
        return {"status": "skipped", "reason": "no INDEX.yaml in target"}
    text = index_file.read_text(encoding="utf-8", errors="replace")
    indexed = re.findall(r"^\s*- path:\s*(\S+)\s*$", text, re.M)
    missing_on_disk = sorted(p for p in indexed if not (target / p).exists())
    rc, out, _ = git(["ls-files"], cwd=target)
    unregistered = []
    if rc == 0:
        tracked = [l.strip() for l in out.splitlines() if l.strip()]
        content_ext = (".md", ".yaml", ".yml", ".py", ".jsonl")
        skip_prefixes = (".claude/", ".github/", "reports/")
        skip_names = {".gitignore", ".gitattributes"}
        indexed_set = set(indexed)
        for f in tracked:
            if (f.endswith(content_ext) and f not in indexed_set
                    and not f.startswith(skip_prefixes) and f not in skip_names):
                unregistered.append(f)
    return {"status": "ok", "indexed_count": len(indexed),
            "missing_on_disk": missing_on_disk,
            "unregistered_tracked_files": sorted(unregistered)}


def collect_artifact_check(target):
    """Reuse the existing tier-0 validator as a subprocess (DR-020: single
    source of truth for the overlay + ROUTES path checks - never forked)."""
    checker = target / "scripts" / "check_agent_artifacts.py"
    if not checker.is_file():
        return {"status": "skipped", "reason": "no scripts/check_agent_artifacts.py in target"}
    rc, out, err = run_cmd([sys.executable, str(checker)], cwd=target)
    failures = [l for l in out.splitlines() if l.startswith(("FAIL", "MISSING"))]
    return {"status": "ok", "exit_code": rc, "failures": failures,
            "summary_line": next((l for l in out.splitlines() if "artifacts OK" in l), "")}


def collect_diff(target, since_ref):
    """Changed files (name-status) since a ref, plus working-tree changes."""
    ref = since_ref or "HEAD"
    rc, out, err = git(["diff", "--name-status", ref], cwd=target)
    if rc != 0:
        return {"status": "unavailable", "reason": f"git diff failed: {err.strip()[:200]}"}
    changed = []
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            changed.append({"change": parts[0], "path": unquote_git_path(parts[-1])})
    rc2, out2, _ = git(["status", "--porcelain"], cwd=target)
    untracked = [unquote_git_path(l[3:]) for l in out2.splitlines()
                 if l.startswith("??")] if rc2 == 0 else []
    return {"status": "ok", "since_ref": ref, "changed": changed, "untracked": untracked}


def collect_deprecated_markers(target, scoped_files=None):
    """Deterministic staleness signals: DEPRECATED markers, .bak files,
    TODO_FILL stubs. Locations capped; counts exact."""
    exts = (".md", ".yaml", ".yml", ".py")
    deprecated, todos = [], []
    bak_files = [str(p.relative_to(target)).replace("\\", "/")
                 for p in target.rglob("*.bak*")
                 if p.is_file() and ".git" not in p.parts]
    for p in target.rglob("*"):
        if not p.is_file() or p.suffix not in exts or ".git" in p.parts \
                or "__pycache__" in p.parts:
            continue
        rel = str(p.relative_to(target)).replace("\\", "/")
        if rel.startswith("reports/"):
            continue
        if scoped_files is not None and rel not in scoped_files:
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for i, line in enumerate(text.splitlines(), 1):
            if "DEPRECATED" in line:
                deprecated.append(f"{rel}:{i}")
            if "TODO_FILL" in line:
                todos.append(f"{rel}:{i}")
    return {"status": "ok",
            "deprecated_marker_count": len(deprecated),
            "deprecated_markers": deprecated[:50],
            "bak_files": bak_files,
            "todo_fill_count": len(todos),
            "todo_fill": todos[:50]}


def collect_home_telemetry(home):
    """Harvest the existing ~/.claude deterministic scripts (read-only calls).
    Each is optional: absent/failing scripts are reported unavailable, never
    silently skipped and never reimplemented here."""
    if home is None:
        return {"status": "skipped", "reason": "--no-home"}
    home = Path(home)
    if not home.is_dir():
        return {"status": "unavailable", "reason": f"home dir not found: {home}"}
    results = {}
    for name, argv in HOME_COLLECTORS:
        script = home / argv[0]
        if not script.is_file():
            results[name] = {"status": "unavailable", "reason": "script not found"}
            continue
        rc, out, err = run_cmd([sys.executable, str(script)] + argv[1:], cwd=home)
        if rc != 0:
            results[name] = {"status": "unavailable",
                             "reason": f"exit {rc}: {err.strip()[:200]}"}
            continue
        try:
            results[name] = {"status": "ok", "data": json.loads(out)}
        except json.JSONDecodeError:
            results[name] = {"status": "ok", "raw_head": out[:1000]}
    ok = sum(1 for v in results.values() if v["status"] == "ok")
    return {"status": "ok" if ok else "unavailable", "collectors": results,
            "ok_count": ok, "total": len(HOME_COLLECTORS)}


def collect_codex_policy(target, home):
    """Existence + reference integrity of the Codex delegation policy, plus a
    deterministic staleness metric (deprecated-lane mention counts)."""
    policy = target / "docs" / "codex-delegation-policy.md"
    out = {"status": "ok",
           "policy_exists": policy.is_file(),
           "policy_path": "docs/codex-delegation-policy.md"}
    if home:
        cmd_file = Path(home) / "commands" / "ai-review.md"
        out["ai_review_command_references_policy"] = (
            cmd_file.is_file()
            and "codex-delegation-policy" in cmd_file.read_text(encoding="utf-8", errors="replace"))
        gemini_counts = {}
        for rel in ("CLAUDE.md", "DELEGATION.md", "AGENTS.md"):
            p = Path(home) / rel
            if p.is_file():
                gemini_counts[rel] = len(re.findall(
                    r"gemini", p.read_text(encoding="utf-8", errors="replace"), re.I))
        out["gemini_mention_lines"] = gemini_counts
    return out


def collect_experiments(target):
    """Parse benchmarks/*.yaml (flat controlled format - line-based, stdlib-only)
    and report cases by status; 'proposed'/'running' cases are open experiments."""
    bench_dir = target / "benchmarks"
    if not bench_dir.is_dir():
        return {"status": "skipped", "reason": "no benchmarks/ dir"}
    cases = []
    for f in sorted(bench_dir.glob("*.yaml")):
        cases.extend(parse_benchmark_cases(f.read_text(encoding="utf-8", errors="replace"),
                                           str(f.relative_to(target)).replace("\\", "/")))
    by_status = {}
    for c in cases:
        by_status.setdefault(c.get("status", "unknown"), []).append(c["case_name"])
    return {"status": "ok", "case_count": len(cases), "cases": cases,
            "by_status": {k: sorted(v) for k, v in by_status.items()}}


def parse_benchmark_cases(text, source_file):
    """Minimal line parser for the controlled benchmark-case YAML shape
    (`- case_name:` blocks with flat `key: value` fields). Not a YAML engine;
    the file format is owned by this repo and kept flat on purpose."""
    cases = []
    current = None
    for line in text.splitlines():
        m = re.match(r"^\s*-\s+case_name:\s*(.+?)\s*$", line)
        if m:
            current = {"case_name": m.group(1).strip('"'), "source_file": source_file}
            cases.append(current)
            continue
        if current is not None:
            m2 = re.match(r"^\s{4,}(\w+):\s*(.*?)\s*$", line)
            if m2 and m2.group(1) != "case_name":
                current[m2.group(1)] = m2.group(2).strip('"')
    return cases


COLLECTORS = {
    "inventory": lambda ctx: collect_inventory(ctx["target"], ctx["scoped_files"]),
    "index_integrity": lambda ctx: collect_index_integrity(ctx["target"]),
    "artifact_check": lambda ctx: collect_artifact_check(ctx["target"]),
    "diff": lambda ctx: collect_diff(ctx["target"], ctx["since_ref"]),
    "deprecated_markers": lambda ctx: collect_deprecated_markers(ctx["target"], ctx["scoped_files"]),
    "home_telemetry": lambda ctx: collect_home_telemetry(ctx["home"]),
    "codex_policy": lambda ctx: collect_codex_policy(ctx["target"], ctx["home"]),
    "experiments": lambda ctx: collect_experiments(ctx["target"]),
}


# ---------------------------------------------------------------------------
# Deterministic issues - derived from collector output by fixed rules.
# ---------------------------------------------------------------------------

def derive_issues(collected):
    issues = []

    def add(sev, category, description, file_path=""):
        issues.append({"id": f"DET-{len(issues) + 1:03d}", "severity": sev,
                       "category": category, "file_path": file_path,
                       "description": description, "source": "deterministic"})

    idx = collected.get("index_integrity", {})
    for p in idx.get("missing_on_disk", []):
        add("P1", "index_drift", f"INDEX.yaml registers '{p}' but it does not exist on disk (ghost entry, MT-5).", p)
    for p in idx.get("unregistered_tracked_files", []):
        add("P2", "index_drift", f"Tracked content file '{p}' is absent from INDEX.yaml (orphan, MT-5).", p)

    art = collected.get("artifact_check", {})
    for f in art.get("failures", []):
        add("P1", "artifact_integrity", f"check_agent_artifacts: {f}")

    dep = collected.get("deprecated_markers", {})
    for b in dep.get("bak_files", []):
        add("P2", "scratch_hygiene", f"Stale backup file '{b}' in tree (MT-5 scratch hygiene).", b)
    if dep.get("todo_fill_count"):
        add("P2", "todo_stub", f"{dep['todo_fill_count']} TODO_FILL stub(s) present: {', '.join(dep.get('todo_fill', [])[:5])}")

    cdx = collected.get("codex_policy", {})
    if cdx and not cdx.get("policy_exists", True):
        add("P1", "codex_policy", "docs/codex-delegation-policy.md missing - codex_delegation_review has no policy baseline.",
            "docs/codex-delegation-policy.md")
    if cdx.get("ai_review_command_references_policy") is False:
        add("P2", "codex_policy", "~/.claude/commands/ai-review.md does not reference the Codex delegation policy.")

    return issues


# ---------------------------------------------------------------------------
# Ingest validation (the LLM->runner contract).
# ---------------------------------------------------------------------------

HIGH_RISK_COMPONENT_TYPES = {"hook", "subagent", "prompt", "command", "skill"}
_REC_ID_RE = re.compile(r"^REC-[0-9]{8}-[0-9]{3}$")


def validate_recommendation(rec, errors, where):
    for field in RECOMMENDATION_REQUIRED:
        if field not in rec:
            errors.append(f"{where}: missing required field '{field}'")
    if rec.get("recommendation") not in RECOMMENDATION_ENUM:
        errors.append(f"{where}: recommendation '{rec.get('recommendation')}' not in {sorted(RECOMMENDATION_ENUM)}")
    if rec.get("confidence") not in CONFIDENCE_ENUM:
        errors.append(f"{where}: confidence '{rec.get('confidence')}' not in {sorted(CONFIDENCE_ENUM)}")
    if rec.get("priority") not in PRIORITY_ENUM:
        errors.append(f"{where}: priority '{rec.get('priority')}' not in {sorted(PRIORITY_ENUM)}")
    if "recommendation_id" in rec and not _REC_ID_RE.match(str(rec["recommendation_id"])):
        errors.append(f"{where}: recommendation_id '{rec.get('recommendation_id')}' does not match REC-YYYYMMDD-NNN")
    # High-risk classes (deleting/replacing hooks, subagents, prompts, commands,
    # skills) must carry the explicit human-approval flag - the prompt doc's
    # rule, enforced here instead of honor-system.
    if (rec.get("recommendation") in ("Remove", "Replace")
            and str(rec.get("component_type", "")).lower() in HIGH_RISK_COMPONENT_TYPES
            and rec.get("requires_human_approval") is not True):
        errors.append(f"{where}: {rec.get('recommendation')} on component_type "
                      f"'{rec.get('component_type')}' requires requires_human_approval: true")


def validate_invocation(rec, errors, where):
    for field in INVOCATION_REQUIRED:
        if field not in rec:
            errors.append(f"{where}: missing required field '{field}'")
    if rec.get("invocation_type") not in INVOCATION_TYPE_ENUM:
        errors.append(f"{where}: invocation_type '{rec.get('invocation_type')}' not in {sorted(INVOCATION_TYPE_ENUM)}")
    if rec.get("recommendation") not in RECOMMENDATION_ENUM:
        errors.append(f"{where}: recommendation '{rec.get('recommendation')}' not in {sorted(RECOMMENDATION_ENUM)}")


def validate_ingest(findings):
    """Validate an --ingest payload. Returns a list of errors (empty = valid)."""
    errors = []
    if not isinstance(findings, dict):
        return ["ingest payload must be a JSON object"]
    for key in ("recommendations", "obsolete_scaffolding", "codex_delegation_findings"):
        for i, rec in enumerate(findings.get(key, [])):
            validate_recommendation(rec, errors, f"{key}[{i}]")
    for i, rec in enumerate(findings.get("inefficient_invocations", [])):
        validate_invocation(rec, errors, f"inefficient_invocations[{i}]")
    for i, issue in enumerate(findings.get("issues_found", [])):
        for field in ("id", "severity", "category", "description"):
            if field not in issue:
                errors.append(f"issues_found[{i}]: missing required field '{field}'")
        if issue.get("severity") not in PRIORITY_ENUM:
            errors.append(f"issues_found[{i}]: severity '{issue.get('severity')}' not in {sorted(PRIORITY_ENUM)}")
    for i, exp in enumerate(findings.get("experiments_proposed", [])):
        if "case_name" not in exp:
            errors.append(f"experiments_proposed[{i}]: missing case_name")
        if exp.get("status") not in EXPERIMENT_STATUS_ENUM:
            errors.append(f"experiments_proposed[{i}]: status '{exp.get('status')}' not in {sorted(EXPERIMENT_STATUS_ENUM)}")
    return errors


def validate_report(report):
    """Minimal structural validation of the assembled report (mirrors the
    required/enum core of schemas/review_report.schema.yaml)."""
    errors = []
    for field in REPORT_REQUIRED:
        if field not in report:
            errors.append(f"report missing required field '{field}'")
    if report.get("source") not in SOURCE_ENUM:
        errors.append(f"source '{report.get('source')}' not in {sorted(SOURCE_ENUM)}")
    if report.get("mode") not in MODES:
        errors.append(f"mode '{report.get('mode')}' not a known runner mode")
    for i, rec in enumerate(report.get("recommendations", [])):
        validate_recommendation(rec, errors, f"recommendations[{i}]")
    if report.get("source") == "scheduled_runner" and report.get("changes_made"):
        errors.append("source=scheduled_runner must have empty changes_made (report-only invariant)")
    return errors


# ---------------------------------------------------------------------------
# Report assembly + rendering.
# ---------------------------------------------------------------------------

def merge_experiments(collector_cases, ingested_cases):
    """Union of benchmark-file cases and validated ingested cases, deduped by
    case_name; the collector (the on-disk benchmark file) wins on conflict.
    Neither side is ever silently dropped (DR-011)."""
    merged = list(collector_cases)
    seen = {c.get("case_name") for c in collector_cases}
    for exp in ingested_cases:
        if exp.get("case_name") not in seen:
            merged.append(exp)
    return merged


def next_trigger_for(mode):
    return {
        "standard_review": "weekly standard_review; diff_review after the next harness-touching commit",
        "harness_cleanup_review": "monthly harness_cleanup_review; re-run after applying any Remove/Replace recommendation",
        "code_invocation_review": "monthly code_invocation_review, or after adding/rewiring any hook",
        "codex_delegation_review": "quarterly codex_delegation_review, or after editing DELEGATION.md / codex-delegate skill",
        "scheduled_review": "next scheduled run (report-only); human /ai-review session to consume open findings",
        "diff_review": "diff_review after each harness-touching commit",
        "experiment_review": "when any benchmark case leaves 'proposed' status, or monthly",
    }[mode]


def assemble_report(mode, args, collected, ingest, started):
    now = datetime.now(timezone.utc)
    source = "scheduled_runner" if mode == "scheduled_review" else "ai_review"
    files = collected.get("inventory", {}).get("files", [])
    if "diff" in collected and collected["diff"].get("status") == "ok":
        files = sorted({c["path"] for c in collected["diff"]["changed"]})
    unresolved = list(ingest.get("unresolved_questions", []))
    semantic_keys = ("recommendations", "obsolete_scaffolding",
                     "inefficient_invocations", "codex_delegation_findings")
    empty_semantic = [k for k in semantic_keys if not ingest.get(k)]
    if empty_semantic:
        # Per-section honesty: a partial ingest leaves the untouched sections
        # UNSCORED, not silently passed (DR-011).
        unresolved.append(
            f"Semantic sections not executed/ingested this run for mode '{mode}': "
            f"{', '.join(empty_semantic)}. See {MODE_PROMPTS}#{mode} - UNSCORED, not passed.")
    collectors_meta = {name: data.get("status", "unknown") for name, data in collected.items()}
    report = {
        "schema": SCHEMA_REF,
        "review_id": f"air-{now.strftime('%Y%m%d-%H%M%S')}-{mode}",
        "review_date": now.isoformat(timespec="seconds"),
        "source": source,
        "mode": mode,
        "target": str(args.target),
        "files_inspected": files,
        "components_inspected": collected.get("inventory", {}).get("counts", {}),
        "issues_found": derive_issues(collected) + list(ingest.get("issues_found", [])),
        "obsolete_scaffolding": list(ingest.get("obsolete_scaffolding", [])),
        "inefficient_invocations": list(ingest.get("inefficient_invocations", [])),
        "codex_delegation_findings": list(ingest.get("codex_delegation_findings", [])),
        "recommendations": list(ingest.get("recommendations", [])),
        "experiments_proposed": merge_experiments(
            collected.get("experiments", {}).get("cases", []),
            ingest.get("experiments_proposed", [])),
        "changes_made": list(ingest.get("changes_made", [])),
        "unresolved_questions": unresolved,
        "metrics": {
            "runtime_sec": round(time.time() - started, 2),
            "collectors": collectors_meta,
            "governance_line_counts": collected.get("inventory", {}).get("governance_line_counts", {}),
            "index_integrity": {k: v for k, v in collected.get("index_integrity", {}).items()
                                if k in ("indexed_count",)},
            "home_telemetry_ok": collected.get("home_telemetry", {}).get("ok_count"),
            "deterministic_issue_count": None,  # filled below
        },
        "next_review_trigger": next_trigger_for(mode),
        "dry_run": bool(args.dry_run),
    }
    report["metrics"]["deterministic_issue_count"] = sum(
        1 for i in report["issues_found"] if i.get("source") == "deterministic")
    return report


def render_markdown(report):
    """Deterministic JSON->Markdown twin (never LLM-written from scratch)."""
    lines = []
    add = lines.append
    add(f"# AI-review report - {report['review_id']}")
    add("")
    add(f"- **date**: {report['review_date']}")
    add(f"- **source / mode**: {report['source']} / {report['mode']}")
    add(f"- **target**: {report['target']}")
    add(f"- **dry-run**: {report['dry_run']}")
    add("")
    add("## Numbers")
    add("")
    m = report["metrics"]
    add(f"- runtime: {m.get('runtime_sec')}s; collectors: " +
        ", ".join(f"{k}={v}" for k, v in m.get("collectors", {}).items()))
    for gov, n in m.get("governance_line_counts", {}).items():
        add(f"- {gov}: {n} lines")
    comp = report.get("components_inspected", {})
    if comp:
        add("- components: " + ", ".join(f"{k}={v}" for k, v in sorted(comp.items())))
    add(f"- deterministic issues: {m.get('deterministic_issue_count')}")
    add("")
    add("## Deterministic findings")
    add("")
    if report["issues_found"]:
        add("| id | sev | category | file | description |")
        add("|---|---|---|---|---|")
        for i in report["issues_found"]:
            desc = i["description"].replace("|", "\\|")
            add(f"| {i['id']} | {i['severity']} | {i['category']} | {i.get('file_path', '')} | {desc} |")
    else:
        add("None.")
    add("")
    for key, title in (("recommendations", "Recommendations (semantic, via ingest)"),
                       ("obsolete_scaffolding", "Obsolete scaffolding"),
                       ("inefficient_invocations", "Inefficient invocations"),
                       ("codex_delegation_findings", "Codex delegation findings")):
        rows = report.get(key, [])
        add(f"## {title}")
        add("")
        if not rows:
            add("None ingested this run.")
            add("")
            continue
        for r in rows:
            name = r.get("component_name") or r.get("invocation_name", "?")
            rid = r.get("recommendation_id", "")
            add(f"- **[{r.get('priority', '--')}] {r.get('recommendation')}** {name} "
                f"({r.get('file_path', r.get('invocation_type', ''))}) {rid}")
            ev = r.get("evidence_it_may_be_obsolete") or r.get("likely_cost", "")
            add(f"  - evidence/cost: {ev}")
            add(f"  - test: {r.get('suggested_test', '')}")
        add("")
    add("## Experiments")
    add("")
    exps = report.get("experiments_proposed", [])
    if exps:
        for e in exps:
            add(f"- `{e.get('case_name')}` [{e.get('status', '?')}] -> {e.get('linked_recommendation_id', 'unlinked')}")
    else:
        add("None.")
    add("")
    add("## Unresolved questions")
    add("")
    for q in report["unresolved_questions"]:
        add(f"- {q}")
    if not report["unresolved_questions"]:
        add("None.")
    add("")
    add(f"## Next review trigger\n\n{report['next_review_trigger']}")
    add("")
    return "\n".join(lines)


def write_outputs(report, out_dir):
    out_dir.mkdir(parents=True, exist_ok=True)
    history = out_dir / "history"
    history.mkdir(exist_ok=True)
    md = render_markdown(report)
    (out_dir / "latest.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (out_dir / "latest.md").write_text(md, encoding="utf-8")
    date = report["review_date"][:10]
    stem = f"{date}-ai-review"
    if (history / f"{stem}.json").exists():
        stem = f"{date}-{report['review_id'].split('-')[2]}-ai-review"
    (history / f"{stem}.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (history / f"{stem}.md").write_text(md, encoding="utf-8")
    summary = {
        "review_id": report["review_id"], "review_date": report["review_date"],
        "source": report["source"], "mode": report["mode"],
        "issues_found": len(report["issues_found"]),
        "recommendations": len(report["recommendations"]),
        "inefficient_invocations": len(report["inefficient_invocations"]),
        "experiments_proposed": len(report["experiments_proposed"]),
        "unresolved_questions": len(report["unresolved_questions"]),
        "dry_run": report["dry_run"],
        "runtime_sec": report["metrics"].get("runtime_sec"),
    }
    with (history / "review-log.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(summary, ensure_ascii=False) + "\n")
    return out_dir / "latest.json"


# ---------------------------------------------------------------------------


def build_arg_parser():
    p = argparse.ArgumentParser(
        prog="run_ai_review.py",
        description="Deterministic AI-review runner: collects metrics, validates "
                    "LLM findings (--ingest), writes JSON+MD reports and JSONL history. "
                    "Never edits harness files; scheduled mode is report-only.")
    p.add_argument("--mode", required=True, choices=sorted(MODES),
                   help="Review mode (semantic checklists live in prompts/ai-review-modes.md).")
    p.add_argument("--target", default=str(REPO_ROOT),
                   help="Repo to inspect (default: this harness repo).")
    p.add_argument("--output", default=None,
                   help="Output dir (default: <target>/reports/ai-review). Gitignored by design.")
    p.add_argument("--home", default=os.path.expanduser("~/.claude"),
                   help="Global harness dir for external telemetry collectors.")
    p.add_argument("--no-home", action="store_true",
                   help="Skip all ~/.claude external collectors (hermetic run).")
    p.add_argument("--dry-run", action="store_true",
                   help="Print the report JSON to stdout; write NOTHING.")
    p.add_argument("--changed-files-only", action="store_true",
                   help="Scope file-walking collectors to files changed since --since-ref (default HEAD).")
    p.add_argument("--since-ref", default=None,
                   help="Git ref for diff_review / --changed-files-only scoping.")
    p.add_argument("--ingest", default=None,
                   help="JSON file of LLM findings to validate and merge (see recommendation.schema.yaml).")
    return p


def main(argv=None):
    utf8_stdout()
    args = build_arg_parser().parse_args(argv)
    args.target = Path(args.target).resolve()
    if not args.target.is_dir():
        print(f"ERROR: target not found: {args.target}", file=sys.stderr)
        return 2
    home = None if args.no_home else args.home

    ingest = {}
    if args.ingest and args.mode == "scheduled_review":
        # Report-only invariant, enforced not prose: scheduled runs carry no
        # semantic findings and record no changes. A human-present session
        # ingests findings under a non-scheduled mode instead.
        print("ERROR: --ingest is not allowed with --mode scheduled_review "
              "(scheduled runs are deterministic report-only by doctrine)", file=sys.stderr)
        return 1
    if args.ingest:
        try:
            ingest = json.loads(Path(args.ingest).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"ERROR: cannot read ingest file: {exc}", file=sys.stderr)
            return 1
        errors = validate_ingest(ingest)
        if errors:
            print("ERROR: ingest findings failed validation:", file=sys.stderr)
            for e in errors:
                print(f"  - {e}", file=sys.stderr)
            return 1

    scoped_files = None
    if args.changed_files_only:
        diff = collect_diff(args.target, args.since_ref)
        if diff["status"] != "ok":
            print(f"ERROR: --changed-files-only needs a working git diff: {diff.get('reason')}",
                  file=sys.stderr)
            return 1
        scoped_files = {c["path"] for c in diff["changed"]} | set(diff["untracked"])

    started = time.time()
    ctx = {"target": args.target, "home": home, "since_ref": args.since_ref,
           "scoped_files": scoped_files}
    collected = {}
    for name in MODES[args.mode]:
        collected[name] = COLLECTORS[name](ctx)

    report = assemble_report(args.mode, args, collected, ingest, started)
    errors = validate_report(report)
    if errors:
        print("ERROR: assembled report failed schema core validation:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1

    if args.dry_run:
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0

    out_dir = Path(args.output) if args.output else args.target / "reports" / "ai-review"
    latest = write_outputs(report, out_dir)
    print(f"OK {report['review_id']}: wrote {latest} (+ latest.md, history/)")
    print(f"   issues={len(report['issues_found'])} recommendations={len(report['recommendations'])} "
          f"unresolved={len(report['unresolved_questions'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
