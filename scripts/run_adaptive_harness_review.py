#!/usr/bin/env python3
"""Adaptive-harness runner - the rolling-improvement half of the review system.

Division of labor (docs/ai_review_adaptive_harness_integration.md is the
contract): AI-review (scripts/run_ai_review.py) reviews the CURRENT state and
produces structured findings; THIS runner manages how those findings evolve
over time - reading AI-review's latest report + history, linking repeated
findings across runs, detecting resolved ones from commit citations, and
rendering patch proposals for the human. Same shared schemas
(schemas/review_report.schema.yaml + recommendation.schema.yaml), same
writer, same safety posture. This is ONE system with two runners, not two
systems: every collector, validator, and writer here is IMPORTED from
run_ai_review.py (DR-020 single-source), never forked.

Safety invariants (identical to the AI-review runner):
  - never edits harness files; only writes under --output;
  - --dry-run writes nothing;
  - scheduled_harness_review is report-only BY CODE (source=scheduled_runner,
    --ingest rejected, changes_made must be empty);
  - high-risk recommendations only ever become PATCH PROPOSALS (rendered
    markdown for a human), never applied changes.

Run:
    python scripts/run_adaptive_harness_review.py --mode rolling_improvement_review
    python scripts/run_adaptive_harness_review.py --mode harness_inventory --dry-run
    python scripts/run_adaptive_harness_review.py --mode patch_proposal --read-ai-review reports/ai-review/latest.json

Exit codes: same contract as run_ai_review.py (0 report, 1 validation, 2 usage/target).
"""

import argparse
import importlib.util
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("run_ai_review", _HERE / "run_ai_review.py")
rar = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rar)

REPO_ROOT = _HERE.parent

# Mode -> deterministic collectors (names resolve in rar.COLLECTORS plus the
# local ROLLING_COLLECTORS below).
MODES = {
    "harness_inventory": ["inventory", "index_integrity", "artifact_check"],
    "harness_cleanup_review": ["inventory", "index_integrity", "artifact_check",
                               "deprecated_markers", "home_telemetry"],
    "code_invocation_review": ["inventory", "home_telemetry"],
    "ai_review_integration": ["integration_wiring", "ai_review_input"],
    "skill_fit_review": ["inventory", "integration_wiring"],
    "diff_only_review": ["diff", "inventory", "graph_impact"],
    "scheduled_harness_review": ["inventory", "index_integrity", "artifact_check",
                                 "deprecated_markers", "ai_review_input"],
    "experiment_design": ["experiments"],
    "patch_proposal": ["ai_review_input"],
    "rolling_improvement_review": ["inventory", "index_integrity", "diff",
                                   "ai_review_input", "rolling_state",
                                   "graph_impact"],
}

MODE_PROMPTS = "prompts/ai-review-modes.md"
INTEGRATION_DOC = "docs/ai_review_adaptive_harness_integration.md"

REQUIRED_WIRING = [
    ".claude/skills/adaptive-harness/SKILL.md",
    "docs/ai_review_adaptive_harness_integration.md",
    "schemas/review_report.schema.yaml",
    "schemas/recommendation.schema.yaml",
    "scripts/run_ai_review.py",
    "prompts/ai-review-modes.md",
    "docs/codex-delegation-policy.md",
    "benchmarks/ai_review_cases.yaml",
    "benchmarks/harness_cases.yaml",
]


def collect_integration_wiring(ctx):
    """Presence of every artifact the AI-review <-> adaptive-harness contract
    depends on; a missing one is a P1 wiring break."""
    target = ctx["target"]
    missing = [p for p in REQUIRED_WIRING if not (target / p).is_file()]
    root_skill = target / "SKILL.md"
    adapter_documented = (root_skill.is_file()
                          and "adaptive-harness" in root_skill.read_text(encoding="utf-8", errors="replace"))
    return {"status": "ok", "missing": missing, "present": len(REQUIRED_WIRING) - len(missing),
            "root_skill_documents_adapter": adapter_documented}


def collect_ai_review_input(ctx):
    """Read AI-review's latest structured report + run history (read-only)."""
    path = ctx["read_ai_review"]
    if path is None:
        path = ctx["target"] / "reports" / "ai-review" / "latest.json"
    path = Path(path)
    if not path.is_file():
        return {"status": "unavailable",
                "reason": f"no AI-review report at {path} - run scripts/run_ai_review.py first"}
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"status": "unavailable", "reason": f"unreadable report: {exc}"}
    history_rows = []
    skipped_rows = 0
    history = path.parent / "history" / "review-log.jsonl"
    if history.is_file():
        for line in history.read_text(encoding="utf-8").splitlines():
            try:
                history_rows.append(json.loads(line))
            except json.JSONDecodeError:
                skipped_rows += 1  # never drop the run over one bad row; reported below
    return {"status": "ok", "path": str(path),
            "history_rows_skipped": skipped_rows,
            "review_id": report.get("review_id"),
            "mode": report.get("mode"),
            "recommendations": report.get("recommendations", []),
            "inefficient_invocations": report.get("inefficient_invocations", []),
            "issues_found": report.get("issues_found", []),
            "experiments_proposed": report.get("experiments_proposed", []),
            "unresolved_questions": report.get("unresolved_questions", []),
            "history_runs": len(history_rows)}


def _rec_key(rec):
    return rec.get("recommendation_id") or (
        rec.get("component_name", ""), rec.get("file_path", ""), rec.get("recommendation", ""))


OUTCOME_TRAILER_RE = re.compile(
    r"^Harness-Outcome:\s+(?P<rec>REC-\d{8}-\d{3})\s+"
    r"(?P<outcome>applied|validated|rejected|reopened);\s*evidence=(?P<evidence>\S.*)$",
    re.IGNORECASE,
)
LEGACY_OUTCOME_SUBJECT_RE = re.compile(
    r"^(?:[A-Za-z0-9_.-]+(?:\([^\n)]+\))?:\s+)?"
    r"(?P<verb>applies|resolves)\s+(?P<rec>REC-\d{8}-\d{3})$",
    re.IGNORECASE,
)
CLOSED_OUTCOMES = {"validated", "rejected"}


def _read_head_sha(target):
    """Read HEAD without forking Git; supports normal repos and worktrees."""
    dot_git = Path(target) / ".git"
    try:
        if dot_git.is_dir():
            git_dir = dot_git
        elif dot_git.is_file():
            marker = dot_git.read_text(encoding="utf-8", errors="replace").strip()
            if not marker.lower().startswith("gitdir:"):
                return ""
            git_dir = Path(marker.split(":", 1)[1].strip())
            if not git_dir.is_absolute():
                git_dir = (Path(target) / git_dir).resolve()
        else:
            return ""
        head = (git_dir / "HEAD").read_text(encoding="ascii").strip()
        if not head.startswith("ref:"):
            return head if re.fullmatch(r"[0-9a-fA-F]{40,64}", head) else ""
        ref = head.split(":", 1)[1].strip()
        common_dir = git_dir
        commondir = git_dir / "commondir"
        if commondir.is_file():
            common_dir = (git_dir / commondir.read_text(encoding="utf-8").strip()).resolve()
        for base in (git_dir, common_dir):
            ref_path = base / Path(ref)
            if ref_path.is_file():
                value = ref_path.read_text(encoding="ascii").strip()
                if re.fullmatch(r"[0-9a-fA-F]{40,64}", value):
                    return value
        for base in (common_dir, git_dir):
            packed = base / "packed-refs"
            if not packed.is_file():
                continue
            for line in packed.read_text(encoding="ascii", errors="replace").splitlines():
                if line.startswith(("#", "^")):
                    continue
                parts = line.split(" ", 1)
                if len(parts) == 2 and parts[1] == ref:
                    return parts[0]
    except OSError:
        return ""
    return ""


def _evidence_path_error(evidence):
    path = Path(evidence)
    if path.is_absolute() or ".." in path.parts or "\n" in evidence or "\r" in evidence:
        return "evidence path must stay relative to the target repository"
    return ""


def _batch_commit_evidence_errors(target, candidates):
    """Check every structured evidence path against its outcome commit tree."""
    errors = {}
    specs, positions = [], []
    for index, candidate in enumerate(candidates):
        if candidate["source"] != "structured-trailer" or candidate.get("pre_error"):
            continue
        path_error = _evidence_path_error(candidate["evidence"])
        if path_error:
            errors[index] = path_error
            continue
        specs.append(f"{candidate['commit_sha']}:{Path(candidate['evidence']).as_posix()}")
        positions.append(index)
    if not specs:
        return errors, ""
    try:
        proc = subprocess.run(
            ["git", "cat-file", "--batch-check"], cwd=str(target),
            input="\n".join(specs) + "\n", capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return errors, f"evidence verification failed: {exc}"
    lines = proc.stdout.splitlines()
    if proc.returncode != 0 or len(lines) != len(specs):
        return errors, "evidence verification returned an incomplete result"
    for index, line in zip(positions, lines):
        if line.endswith(" missing"):
            errors[index] = "evidence file is missing from the outcome commit"
        elif " blob " not in line:
            errors[index] = "evidence path in the outcome commit is not a file"
    return errors, ""


def scan_outcome_evidence(target, rec_ids, since_days=180):
    """Return the newest machine-checkable outcome for each recommendation.

    Free-form body prose is deliberately ignored. A legacy exact commit subject
    remains supported, while new commits can use a structured Harness-Outcome
    trailer with an evidence pointer. The newest event wins, so a later
    ``reopened`` trailer restores a recommendation to the active queue.
    """
    wanted = set(rec_ids)
    if not wanted:
        return {"status": "ok", "outcomes": {}}
    rc, out, err = rar.git([
        "log", f"--since={since_days} days ago",
        "--format=%H%x1f%h%x1f%cI%x1f%s%x1f%b%x1e",
    ], cwd=target)
    if rc != 0:
        return {"status": "unavailable", "reason": f"git log failed: {err.strip()[:200]}"}
    if not out.strip():
        return {"status": "ok", "outcomes": {}}
    candidates = []
    for raw in out.split("\x1e"):
        fields = raw.strip("\r\n").split("\x1f", 4)
        if len(fields) != 5:
            continue
        sha, short_sha, commit_date, subject, body = fields
        commit_candidates = []
        for line in body.splitlines():
            match = OUTCOME_TRAILER_RE.fullmatch(line.strip())
            if match:
                evidence = match.group("evidence").strip()
                commit_candidates.append({
                    "rec_id": match.group("rec"),
                    "outcome": match.group("outcome").lower(),
                    "evidence": evidence,
                    "source": "structured-trailer",
                })
        legacy = LEGACY_OUTCOME_SUBJECT_RE.fullmatch(subject.strip())
        if legacy:
            outcome = "applied" if legacy.group("verb").lower() == "applies" else "validated"
            commit_candidates.append({
                "rec_id": legacy.group("rec"),
                "outcome": outcome,
                "evidence": "legacy-exact-subject",
                "source": "legacy-subject",
            })
        grouped = {}
        for candidate in commit_candidates:
            grouped.setdefault(candidate["rec_id"], []).append(candidate)
        for rec_id, grouped_candidates in grouped.items():
            candidate = dict(grouped_candidates[0])
            candidate.update({
                "commit_sha": sha, "short_sha": short_sha,
                "commit_date": commit_date, "subject": subject,
            })
            if len(grouped_candidates) > 1:
                candidate["pre_error"] = "multiple outcome declarations for one recommendation in the same commit"
                candidate["claimed_outcomes"] = [c["outcome"] for c in grouped_candidates]
            candidates.append(candidate)

    evidence_errors, batch_error = _batch_commit_evidence_errors(target, candidates)
    if batch_error:
        return {"status": "unavailable", "reason": batch_error}
    found = {}
    for index, candidate in enumerate(candidates):
        rec_id = candidate["rec_id"]
        if rec_id in wanted and rec_id not in found:
            evidence_error = candidate.get("pre_error") or evidence_errors.get(index, "")
            found[rec_id] = {
                "recommendation_id": rec_id,
                "outcome": "unverified" if evidence_error else candidate["outcome"],
                "claimed_outcome": candidate["outcome"],
                "resolving_commit": f"{candidate['short_sha']} {candidate['subject']}",
                "commit_sha": candidate["commit_sha"],
                "commit_date": candidate["commit_date"],
                "evidence": candidate["evidence"],
                "evidence_source": candidate["source"],
            }
            if candidate.get("claimed_outcomes"):
                found[rec_id]["claimed_outcomes"] = candidate["claimed_outcomes"]
            if evidence_error:
                found[rec_id]["evidence_error"] = evidence_error
    return {"status": "ok", "outcomes": found}


def collect_outcome_evidence(target, rec_ids, since_days=180):
    """Compatibility wrapper returning only successfully scanned outcomes."""
    result = scan_outcome_evidence(target, rec_ids, since_days)
    return result.get("outcomes", {}) if result.get("status") == "ok" else {}


def resolved_by_commit(target, rec_id, since_days=180):
    """Backward-compatible commit lookup; rolling logic uses outcome states."""
    outcome = collect_outcome_evidence(target, [rec_id], since_days).get(rec_id)
    if not outcome or outcome["outcome"] not in (CLOSED_OUTCOMES | {"applied"}):
        return None
    return outcome["resolving_commit"]


def collect_rolling_state(ctx):
    """Link the current AI-review findings against the previous adaptive-harness
    report: new / repeated / resolved-by-commit. The rolling loop's memory."""
    target = ctx["target"]
    ai = collect_ai_review_input(ctx)
    if ai["status"] != "ok":
        return {"status": "unavailable", "reason": ai.get("reason", "no AI-review input")}
    current = {str(_rec_key(r)): r for r in ai["recommendations"]}
    # Rolling state lives in its own file, written ONLY by
    # rolling_improvement_review runs - latest.json is overwritten by every
    # mode, so reading it here would reset the loop whenever another mode ran
    # in between (found in Phase-2 dogfooding).
    prev_path = (Path(ctx["output"]) if ctx["output"] else target / "reports" / "harness") / "rolling_state.json"
    previous = {}
    previous_archive = {}
    previous_outcomes = {}
    previous_scanned_head = ""
    previous_scanned_rec_ids = set()
    if prev_path.is_file():
        try:
            prev_state = json.loads(prev_path.read_text(encoding="utf-8"))
            previous = {str(_rec_key(r)): r for r in prev_state.get("recommendations", [])}
            archived = prev_state.get("recommendation_archive", prev_state.get("recommendations", []))
            previous_archive = {str(_rec_key(r)): r for r in archived}
            previous_outcomes = {
                r.get("recommendation_id"): r for r in prev_state.get("outcomes", [])
                if r.get("recommendation_id")
            }
            previous_scanned_head = prev_state.get("last_scanned_head", "")
            previous_scanned_rec_ids = set(prev_state.get("last_scanned_rec_ids", []))
        except (OSError, json.JSONDecodeError) as exc:
            # An EXISTING but unreadable state file must not silently reset
            # the loop's memory (2026-07-06 review pair, correctness finding 1):
            # refuse, so the state write guard keeps the corrupt file for a
            # human to inspect instead of overwriting it.
            return {"status": "unavailable",
                    "reason": f"rolling_state.json exists but is unreadable ({exc}) - "
                              f"fix or delete it explicitly; refusing to reset loop memory"}
    archive = dict(previous_archive)
    archive.update(current)
    rec_ids = {r.get("recommendation_id") for r in archive.values() if r.get("recommendation_id")}
    current_head = _read_head_sha(target)
    if not current_head:
        head_rc, head_out, _ = rar.git(["rev-parse", "HEAD"], cwd=target)
        current_head = head_out.strip() if head_rc == 0 else ""
    outcomes = dict(previous_outcomes)
    last_scanned_head = previous_scanned_head
    last_scanned_rec_ids = set(previous_scanned_rec_ids)
    outcome_scan_error = ""
    if (current_head and current_head == previous_scanned_head
            and rec_ids.issubset(previous_scanned_rec_ids)):
        outcome_scan = "cache_hit"
    else:
        scan = (scan_outcome_evidence(target, rec_ids) if current_head else
                {"status": "unavailable", "reason": "target HEAD is unavailable"})
        if scan.get("status") == "ok":
            outcomes.update(scan["outcomes"])
            outcome_scan = "git_scan"
            last_scanned_head = current_head
            last_scanned_rec_ids = set(rec_ids)
        else:
            outcome_scan = "unavailable"
            outcome_scan_error = scan.get("reason", "outcome scan failed")
    newly_resolved, newly_reopened = [], []
    for rec_id, outcome in outcomes.items():
        previous_outcome = previous_outcomes.get(rec_id, {}).get("outcome")
        if outcome.get("outcome") in CLOSED_OUTCOMES and previous_outcome not in CLOSED_OUTCOMES:
            newly_resolved.append(outcome)
        if outcome.get("outcome") == "reopened" and previous_outcome in CLOSED_OUTCOMES:
            newly_reopened.append(outcome)

    new, repeated, still_open = [], [], []
    for key, rec in current.items():
        outcome = outcomes.get(rec.get("recommendation_id"), {})
        if outcome.get("outcome") in CLOSED_OUTCOMES:
            continue
        rec = dict(rec)
        if outcome.get("outcome") == "applied":
            rec["status"] = "applied_unvalidated"
        elif outcome.get("outcome") == "reopened":
            rec["status"] = "reopened"
        elif outcome.get("outcome") == "unverified":
            rec["status"] = "outcome_unverified"
        if key in previous:
            rec.setdefault("status", "repeated")
            repeated.append(rec)
        else:
            new.append(rec)
    for key, rec in archive.items():
        if key in current:
            continue
        outcome = outcomes.get(rec.get("recommendation_id"), {})
        if outcome.get("outcome") in CLOSED_OUTCOMES:
            continue
        rec = dict(rec)
        rec["status"] = ("applied_unvalidated" if outcome.get("outcome") == "applied"
                         else "reopened" if outcome.get("outcome") == "reopened"
                         else "outcome_unverified" if outcome.get("outcome") == "unverified"
                         else "open")
        still_open.append(rec)  # absent from the new review but unproven-resolved: carried, not dropped
    return {"status": "ok", "new_count": len(new), "repeated_count": len(repeated),
            "resolved_count": len(newly_resolved),
            "resolved_total_count": sum(1 for r in outcomes.values()
                                        if r.get("outcome") in CLOSED_OUTCOMES),
            "reopened_count": len(newly_reopened),
            "applied_unvalidated_count": sum(1 for r in outcomes.values()
                                             if r.get("outcome") == "applied"),
            "unverified_outcome_count": sum(1 for r in outcomes.values()
                                            if r.get("outcome") == "unverified"),
            "carried_open_count": len(still_open),
            "new": new, "repeated": repeated, "resolved": newly_resolved,
            "reopened": newly_reopened, "outcomes": list(outcomes.values()),
            "recommendation_archive": list(archive.values()),
            "last_scanned_head": last_scanned_head,
            "last_scanned_rec_ids": sorted(last_scanned_rec_ids),
            "outcome_scan": outcome_scan,
            "outcome_scan_error": outcome_scan_error,
            "carried_open": still_open, "source_review_id": ai.get("review_id")}


def collect_graph_impact(ctx):
    """Changed-files -> impacted files/routes via the explicit harness graph
    (scripts/build_harness_graph.py, overlay 04). Subprocess reuse, dry-run
    form so THIS collector never writes; unavailable-graceful."""
    builder = _HERE / "build_harness_graph.py"
    if not builder.is_file():
        return {"status": "unavailable", "reason": "build_harness_graph.py not found"}
    argv = [sys.executable, str(builder), "--target", str(ctx["target"]), "--dry-run"]
    if ctx["since_ref"]:
        argv += ["--since-ref", ctx["since_ref"]]
    elif ctx["scoped_files"]:
        argv += ["--impact"] + sorted(ctx["scoped_files"])
    else:
        argv += ["--since-ref", "HEAD"]
    rc, out, err = rar.run_cmd(argv, cwd=ctx["target"], timeout=180)
    if rc not in (0, 1) or not out.strip():
        return {"status": "unavailable", "reason": f"builder failed: {err.strip()[:200]}"}
    try:
        g = json.loads(out)
    except json.JSONDecodeError as exc:
        return {"status": "unavailable", "reason": f"unparseable graph output: {exc}"}
    return {"status": "ok",
            "node_count": g.get("node_count"),
            "edge_count": g.get("edge_count"),
            "stale_edge_count": g.get("stale_edge_count"),
            "stale_routes_to_count": g.get("stale_routes_to_count", 0),
            "broken_depends_on": g.get("broken_depends_on", []),
            "impact": g.get("impact")}


LOCAL_COLLECTORS = {
    "integration_wiring": collect_integration_wiring,
    "ai_review_input": collect_ai_review_input,
    "rolling_state": collect_rolling_state,
    "graph_impact": collect_graph_impact,
}


def resolve_collector(name):
    if name in LOCAL_COLLECTORS:
        return LOCAL_COLLECTORS[name]
    base = rar.COLLECTORS[name]
    return lambda ctx: base({"target": ctx["target"], "home": ctx["home"],
                             "since_ref": ctx["since_ref"], "scoped_files": ctx["scoped_files"]})


def derive_issues(collected):
    issues = []

    def add(sev, category, description, file_path=""):
        issues.append({"id": f"DET-{len(issues) + 1:03d}", "severity": sev,
                       "category": category, "file_path": file_path,
                       "description": description, "source": "deterministic"})

    wiring = collected.get("integration_wiring", {})
    for p in wiring.get("missing", []):
        add("P1", "integration_wiring", f"Required AI-review/adaptive-harness wiring artifact missing: {p}", p)
    if wiring.get("root_skill_documents_adapter") is False:
        add("P2", "integration_wiring",
            "Root SKILL.md does not document its relationship to .claude/skills/adaptive-harness/", "SKILL.md")
    ai = collected.get("ai_review_input", {})
    if ai.get("status") == "unavailable":
        add("P2", "ai_review_input", f"AI-review input unavailable: {ai.get('reason', '')}")
    if ai.get("history_rows_skipped"):
        add("P3", "ai_review_input",
            f"{ai['history_rows_skipped']} unparseable row(s) skipped in AI-review history JSONL.")
    rolling = collected.get("rolling_state", {})
    if rolling.get("status") == "unavailable":
        add("P1", "rolling_state",
            f"Rolling loop did NOT run: {rolling.get('reason', '')} - state preserved, not reset.")
    elif rolling.get("outcome_scan") == "unavailable":
        add("P1", "rolling_outcome_scan",
            f"Outcome evidence scan failed and its cache key was not advanced: "
            f"{rolling.get('outcome_scan_error', '')}")
    graph = collected.get("graph_impact", {})
    if graph.get("status") == "unavailable":
        add("P2", "graph_integrity",
            f"Graph impact computation did NOT run: {graph.get('reason', '')}")
    for b in graph.get("broken_depends_on", []):
        add("P1", "graph_integrity", f"Broken frontmatter dependency: {b}")
    if graph.get("stale_routes_to_count"):
        add("P2", "graph_integrity",
            f"{graph['stale_routes_to_count']} stale routes_to edge(s) (route-listed files missing on disk).")
    for name in ("index_integrity", "artifact_check", "deprecated_markers", "codex_policy"):
        if name in collected:
            issues.extend(_reuse_ai_review_issue_rules(collected, name, len(issues)))
    return issues


def _reuse_ai_review_issue_rules(collected, name, offset):
    """Route the shared collectors through run_ai_review's own issue rules so
    both runners flag identical states identically."""
    sub = {name: collected[name]}
    derived = rar.derive_issues(sub)
    for i, issue in enumerate(derived):
        issue["id"] = f"DET-{offset + i + 1:03d}"
    return derived


def render_patch_proposals(recommendations, review_id):
    """Deterministic patch-proposal document: high-risk recommendations become
    a human-consumable apply/rollback sheet. Rendering is the ONLY action -
    nothing is applied."""
    lines = [f"# Patch proposals - {review_id}", "",
             "Every entry is a PROPOSAL. A human applies or rejects it; commits",
             "that apply one MUST cite its recommendation_id so the rolling loop",
             "can mark it resolved.", ""]
    for rec in recommendations:
        lines += [f"## {rec.get('recommendation_id', '?')} - {rec.get('recommendation')} {rec.get('component_name')}",
                  "",
                  f"- **file**: {rec.get('file_path', '')}",
                  f"- **priority / confidence**: {rec.get('priority')} / {rec.get('confidence')}",
                  f"- **evidence (obsolete)**: {rec.get('evidence_it_may_be_obsolete', '')}",
                  f"- **evidence (still helps)**: {rec.get('evidence_it_still_helps', '')}",
                  f"- **risk if changed**: {rec.get('risk_if_changed', '')}",
                  f"- **validation test**: {rec.get('suggested_test', '')}",
                  f"- **requires human approval**: {rec.get('requires_human_approval', False)}",
                  f"- **apply convention**: the applying commit message MUST say "
                  f"'applies {rec.get('recommendation_id', '?')}' (or 'resolves ...') - "
                  f"that exact verb closes the rolling loop; bare mentions do not.",
                  f"- **rollback**: single-commit revert whose message says "
                  f"'reverts {rec.get('recommendation_id', '?')}' (a revert must NOT say applies/resolves).",
                  ""]
    if not recommendations:
        lines += ["No high-risk recommendations pending.", ""]
    return "\n".join(lines)


def high_risk(recs):
    return [r for r in recs
            if r.get("requires_human_approval") is True
            or (r.get("recommendation") in ("Remove", "Replace") and r.get("priority") in ("P0", "P1"))]


def next_trigger_for(mode):
    return {
        "harness_inventory": "monthly, or after adding any new harness component class",
        "harness_cleanup_review": "monthly deep review",
        "code_invocation_review": "monthly, or after rewiring any hook",
        "ai_review_integration": "after any change to either runner or the shared schemas",
        "skill_fit_review": "after adding/renaming skills or changing skill descriptions",
        "diff_only_review": "after each harness-touching commit",
        "scheduled_harness_review": "next scheduled run (report-only); weekly light cadence",
        "experiment_design": "when a recommendation is classified Experiment without a case",
        "patch_proposal": "when rolling review surfaces new high-risk recommendations",
        "rolling_improvement_review": "weekly light; after every AI-review ingest run",
    }[mode]


def assemble_report(mode, args, collected, ingest, started):
    now = datetime.now(timezone.utc)
    source = "scheduled_runner" if mode == "scheduled_harness_review" else "adaptive_harness"
    inventory = collected.get("inventory", {})
    counts = inventory.get("counts", {})
    rolling = collected.get("rolling_state", {})
    recommendations = list(ingest.get("recommendations", []))
    if rolling.get("status") == "ok":
        # The rolling loop's merged view: new + repeated + carried-open records,
        # plus ingest records deduped by key (same semantics as
        # merge_experiments - the same finding must never appear twice).
        rolled = rolling["new"] + rolling["repeated"] + rolling["carried_open"]
        seen = {str(_rec_key(r)) for r in rolled}
        recommendations = rolled + [r for r in recommendations
                                    if str(_rec_key(r)) not in seen]
    ai = collected.get("ai_review_input", {})
    unresolved = list(ingest.get("unresolved_questions", []))
    unresolved += [q for q in ai.get("unresolved_questions", []) if q not in unresolved]
    if rolling.get("outcome_scan") == "unavailable":
        unresolved.append(
            "Outcome evidence scan unavailable; cache key was NOT advanced and the next run will retry: "
            f"{rolling.get('outcome_scan_error', 'unknown error')}")
    semantic_keys = ("recommendations", "obsolete_scaffolding",
                     "inefficient_invocations", "codex_delegation_findings")
    empty_semantic = [k for k in semantic_keys if not ingest.get(k)]
    if empty_semantic and mode not in ("patch_proposal",):
        unresolved.append(
            f"Semantic sections not executed/ingested this run for mode '{mode}': "
            f"{', '.join(empty_semantic)}. See {MODE_PROMPTS} - UNSCORED, not passed.")
    files = inventory.get("files", [])
    if "diff" in collected and collected["diff"].get("status") == "ok":
        files = sorted({c["path"] for c in collected["diff"]["changed"]})
    report = {
        "schema": rar.SCHEMA_REF,
        "review_id": f"ahr-{now.strftime('%Y%m%d-%H%M%S')}-{mode}",
        "review_date": now.isoformat(timespec="seconds"),
        "source": source,
        "mode": mode,
        "target": str(args.target),
        "files_inspected": files,
        "components_inspected": counts,
        "issues_found": derive_issues(collected) + list(ingest.get("issues_found", [])),
        "obsolete_scaffolding": list(ingest.get("obsolete_scaffolding", [])),
        "inefficient_invocations": (list(ingest.get("inefficient_invocations", []))
                                    or ai.get("inefficient_invocations", [])),
        "codex_delegation_findings": list(ingest.get("codex_delegation_findings", [])),
        "recommendations": recommendations,
        "experiments_proposed": rar.merge_experiments(
            collected.get("experiments", {}).get("cases", []),
            ingest.get("experiments_proposed", []) or ai.get("experiments_proposed", [])),
        "changes_made": list(ingest.get("changes_made", [])),
        "unresolved_questions": unresolved,
        "metrics": {
            "runtime_sec": round(time.time() - started, 2),
            "collectors": {n: d.get("status", "unknown") for n, d in collected.items()},
            "governance_line_counts": inventory.get("governance_line_counts", {}),
            "total_files_scanned": len(inventory.get("files", [])),
            "total_prompts_detected": counts.get("prompts", 0),
            "total_routes_detected": counts.get("routes", 0),
            "total_scripts_detected": counts.get("scripts", 0),
            "total_subagents_detected": counts.get("subagents", 0),
            "total_code_invocations": counts.get("scripts", 0) + counts.get("hooks", 0),
            "source_reports_read": [p for p in [ai.get("path")] if p],
            "ai_review_history_runs": ai.get("history_runs", 0),
            "rolling": {k: rolling.get(k) for k in
                        ("new_count", "repeated_count", "resolved_count",
                         "resolved_total_count", "reopened_count",
                         "applied_unvalidated_count", "unverified_outcome_count",
                         "carried_open_count", "outcome_scan", "outcome_scan_error")
                        } if rolling.get("status") == "ok" else {"status": rolling.get("status", "not_run")},
            "resolved_issues": rolling.get("resolved", []),
            "outcome_ledger": rolling.get("outcomes", []),
            "graph": ({"node_count": collected["graph_impact"].get("node_count"),
                       "edge_count": collected["graph_impact"].get("edge_count"),
                       "stale_edge_count": collected["graph_impact"].get("stale_edge_count"),
                       "impacted_components": collected["graph_impact"].get("impact")}
                      if collected.get("graph_impact", {}).get("status") == "ok"
                      else {"status": collected.get("graph_impact", {}).get("status", "not_run")}),
        },
        "next_review_trigger": next_trigger_for(mode),
        "dry_run": bool(args.dry_run),
    }
    return report


def build_arg_parser():
    p = argparse.ArgumentParser(
        prog="run_adaptive_harness_review.py",
        description="Adaptive-harness rolling-review runner. Reads AI-review structured "
                    "output, links findings across runs, renders patch proposals. "
                    "Never edits harness files; scheduled mode is report-only.")
    p.add_argument("--mode", required=True, choices=sorted(MODES))
    p.add_argument("--target", default=str(REPO_ROOT))
    p.add_argument("--output", default=None,
                   help="Output dir (default: <target>/reports/harness). Gitignored by design.")
    p.add_argument("--read-ai-review", default=None, dest="read_ai_review",
                   help="Path to AI-review latest.json (default: <target>/reports/ai-review/latest.json).")
    p.add_argument("--home", default=os.path.expanduser("~/.claude"))
    p.add_argument("--no-home", action="store_true")
    p.add_argument("--dry-run", action="store_true", help="Print report JSON; write NOTHING.")
    p.add_argument("--changed-files-only", action="store_true")
    p.add_argument("--since-ref", default=None)
    p.add_argument("--ingest", default=None,
                   help="LLM findings JSON (validated, same contract as run_ai_review.py).")
    return p


def main(argv=None):
    rar.utf8_stdout()
    args = build_arg_parser().parse_args(argv)
    args.target = Path(args.target).resolve()
    if not args.target.is_dir():
        print(f"ERROR: target not found: {args.target}", file=sys.stderr)
        return 2
    if args.ingest and args.mode == "scheduled_harness_review":
        print("ERROR: --ingest is not allowed with --mode scheduled_harness_review "
              "(scheduled runs are deterministic report-only by doctrine)", file=sys.stderr)
        return 1
    ingest = {}
    if args.ingest:
        try:
            ingest = json.loads(Path(args.ingest).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"ERROR: cannot read ingest file: {exc}", file=sys.stderr)
            return 1
        errors = rar.validate_ingest(ingest)
        if errors:
            print("ERROR: ingest findings failed validation:", file=sys.stderr)
            for e in errors:
                print(f"  - {e}", file=sys.stderr)
            return 1
    scoped_files = None
    if args.changed_files_only:
        diff = rar.collect_diff(args.target, args.since_ref)
        if diff["status"] != "ok":
            print(f"ERROR: --changed-files-only needs a working git diff: {diff.get('reason')}",
                  file=sys.stderr)
            return 1
        scoped_files = {c["path"] for c in diff["changed"]} | set(diff["untracked"])

    started = time.time()
    ctx = {"target": args.target, "home": None if args.no_home else args.home,
           "since_ref": args.since_ref, "scoped_files": scoped_files,
           "read_ai_review": args.read_ai_review, "output": args.output}
    collected = {}
    for name in MODES[args.mode]:
        collected[name] = resolve_collector(name)(ctx)

    report = assemble_report(args.mode, args, collected, ingest, started)
    errors = rar.validate_report(report, known_modes=MODES)
    if errors:
        print("ERROR: assembled report failed schema core validation:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1

    proposals_md = None
    if args.mode == "patch_proposal":
        # Union of every pending source, deduped by key - a non-empty ingest
        # must not mask high-risk items sitting in the rolling state
        # (2026-07-06 review pair, correctness nit).
        pool = list(report["recommendations"])
        pool += collected.get("ai_review_input", {}).get("recommendations", [])
        state_path = (Path(args.output) if args.output
                      else args.target / "reports" / "harness") / "rolling_state.json"
        if state_path.is_file():
            try:
                pool += json.loads(state_path.read_text(encoding="utf-8")).get("recommendations", [])
            except (OSError, json.JSONDecodeError):
                report["unresolved_questions"].append(
                    "rolling_state.json unreadable during patch_proposal - its pending items are NOT in this sheet.")
        seen, unique_pool = set(), []
        for r in pool:
            key = str(_rec_key(r))
            if key not in seen:
                seen.add(key)
                unique_pool.append(r)
        candidates = high_risk(unique_pool)
        proposals_md = render_patch_proposals(candidates, report["review_id"])
        report["metrics"]["patch_proposals_rendered"] = len(candidates)

    if args.dry_run:
        out = dict(report)
        if proposals_md is not None:
            out["patch_proposals_preview"] = proposals_md
        print(json.dumps(out, indent=2, ensure_ascii=False))
        return 0

    out_dir = Path(args.output) if args.output else args.target / "reports" / "harness"
    latest = rar.write_outputs(report, out_dir, stem_suffix="harness-review")
    if (args.mode == "rolling_improvement_review"
            and collected.get("rolling_state", {}).get("status") == "ok"):
        # Guarded write: when the rolling collector could not run (AI-review
        # input missing, corrupt prior state), the previous state file is
        # PRESERVED - overwriting it with an empty list would silently drop
        # every carried-open finding (2026-07-06 review pair, posture finding 1).
        (out_dir / "rolling_state.json").write_text(json.dumps({
            "review_id": report["review_id"],
            "review_date": report["review_date"],
            "recommendations": report["recommendations"],
            "recommendation_archive": collected["rolling_state"].get("recommendation_archive", []),
            "outcomes": collected["rolling_state"].get("outcomes", []),
            "last_scanned_head": collected["rolling_state"].get("last_scanned_head", ""),
            "last_scanned_rec_ids": collected["rolling_state"].get("last_scanned_rec_ids", []),
        }, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    if proposals_md is not None:
        pdir = out_dir / "proposals"
        pdir.mkdir(parents=True, exist_ok=True)
        pfile = pdir / f"PATCH-PROPOSALS-{report['review_date'][:10]}.md"
        pfile.write_text(proposals_md, encoding="utf-8")
        print(f"   patch proposals: {pfile}")
    print(f"OK {report['review_id']}: wrote {latest} (+ latest.md, history/)")
    rolling = report["metrics"].get("rolling", {})
    if rolling and "new_count" in rolling:
        print(f"   rolling: new={rolling['new_count']} repeated={rolling['repeated_count']} "
              f"resolved={rolling['resolved_count']} total_resolved={rolling['resolved_total_count']} "
              f"applied_unvalidated={rolling['applied_unvalidated_count']} "
              f"unverified_outcomes={rolling['unverified_outcome_count']} "
              f"carried_open={rolling['carried_open_count']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
