#!/usr/bin/env python3
"""Adaptive-harness runner - the harness-review half of the review system.

Division of labor (docs/ai_review_adaptive_harness_integration.md is the
contract): AI-review (scripts/run_ai_review.py) reviews the CURRENT state and
produces structured findings; THIS runner runs the harness-shaped review
modes over them (inventory, integration wiring, diff impact, scheduled
report-only scans) and renders patch proposals for the human. Same shared
schemas (schemas/review_report.schema.yaml + recommendation.schema.yaml),
same writer, same safety posture. This is ONE system with two runners, not
two systems: every collector, validator, and writer here is IMPORTED from
run_ai_review.py (DR-020 single-source), never forked.

Cross-run finding LINKAGE (new/repeated/resolved tagging + rolling_state.json
carry + the outcome-evidence ledger) was retired by REC-20260714-001 after the
pre-registered round-4 A/B measured no recall advantage over on-demand
re-derivation (benchmarks/harness_cases.yaml case
ai_review_only_vs_ai_review_plus_adaptive_harness, executed 2026-07-14 -
B lost). Linkage questions are now answered read-only by
scripts/grep_history.py over the append-only history + git log; the
`applies REC-YYYYMMDD-NNN` closure convention is unchanged and greppable.

Safety invariants (identical to the AI-review runner):
  - never edits harness files; only writes under --output;
  - --dry-run writes nothing;
  - scheduled_harness_review is report-only BY CODE (source=scheduled_runner,
    --ingest rejected, changes_made must be empty);
  - high-risk recommendations only ever become PATCH PROPOSALS (rendered
    markdown for a human), never applied changes.

Run:
    python scripts/run_adaptive_harness_review.py --mode harness_inventory --dry-run
    python scripts/run_adaptive_harness_review.py --mode patch_proposal --read-ai-review reports/ai-review/latest.json

Exit codes: same contract as run_ai_review.py (0 report, 1 validation, 2 usage/target).
"""

import argparse
import importlib.util
import json
import os
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
# LOCAL_COLLECTORS below).
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
             "that apply one MUST cite its recommendation_id so closure stays",
             "greppable (scripts/grep_history.py --rec REC-...).", ""]
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
                  f"that exact verb is what grep_history.py treats as closure; "
                  f"bare mentions do not close anything.",
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
        "patch_proposal": "when a review surfaces new high-risk recommendations",
    }[mode]


def assemble_report(mode, args, collected, ingest, started):
    now = datetime.now(timezone.utc)
    source = "scheduled_runner" if mode == "scheduled_harness_review" else "adaptive_harness"
    inventory = collected.get("inventory", {})
    counts = inventory.get("counts", {})
    recommendations = list(ingest.get("recommendations", []))
    ai = collected.get("ai_review_input", {})
    unresolved = list(ingest.get("unresolved_questions", []))
    unresolved += [q for q in ai.get("unresolved_questions", []) if q not in unresolved]
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
        description="Adaptive-harness review runner. Reads AI-review structured "
                    "output, runs harness-shaped review modes, renders patch "
                    "proposals. Never edits harness files; scheduled mode is "
                    "report-only. Cross-run linkage queries: scripts/grep_history.py.")
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
        # must not mask high-risk items pending elsewhere (2026-07-06 review
        # pair, correctness nit). A LEGACY rolling_state.json (written by the
        # loop retired per REC-20260714-001) is still read so its pending
        # items never vanish from proposal sheets; nothing writes it anymore.
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
    if proposals_md is not None:
        pdir = out_dir / "proposals"
        pdir.mkdir(parents=True, exist_ok=True)
        pfile = pdir / f"PATCH-PROPOSALS-{report['review_date'][:10]}.md"
        pfile.write_text(proposals_md, encoding="utf-8")
        print(f"   patch proposals: {pfile}")
    print(f"OK {report['review_id']}: wrote {latest} (+ latest.md, history/)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
