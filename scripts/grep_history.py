#!/usr/bin/env python3
"""Grep-history helper - the linkage query surface that replaced the rolling
loop's state machinery (applies REC-20260714-001; evidence: the 2026-07-14
round-4 A/B in benchmarks/harness_cases.yaml case
ai_review_only_vs_ai_review_plus_adaptive_harness - B lost).

Linkage questions are answered ON DEMAND from two sources that already exist:
the append-only report history (reports/harness/history/*.json +
reports/ai-review/history/*.json) and git log. No state file, no carry, no
writes - this script is read-only by construction.

The closure CONVENTION is unchanged and stays greppable (kept as a dormant
convention when the outcome-ledger code was retired): a commit closes a
recommendation only when its subject says `applies REC-YYYYMMDD-NNN` (or
`resolves ...`), or its body carries a `Harness-Outcome:` trailer. A revert
says `reverts REC-...`. Bare mentions never close anything.

Run:
    python scripts/grep_history.py --rec REC-20260706-034   # appearances + closure
    python scripts/grep_history.py --repeats                # recurrence across runs
    python scripts/grep_history.py --open                   # latest recs lacking closure

Exit codes: 0 report printed, 2 usage/target error.
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

REC_ID_RE = re.compile(r"^REC-\d{8}-\d{3}$")
CLOSURE_SUBJECT_RE = re.compile(
    r"^(?:[A-Za-z0-9_.-]+(?:\([^\n)]+\))?:\s+)?"
    r"(?P<verb>applies|resolves)\s+(?P<rec>REC-\d{8}-\d{3})", re.IGNORECASE)
REVERT_SUBJECT_RE = re.compile(
    r"\breverts\s+(?P<rec>REC-\d{8}-\d{3})", re.IGNORECASE)
OUTCOME_TRAILER_RE = re.compile(
    r"^Harness-Outcome:\s+(?P<rec>REC-\d{8}-\d{3})\s+"
    r"(?P<outcome>applied|validated|rejected|reopened)\b", re.IGNORECASE)


def history_reports(history_dirs):
    """Yield (path, parsed report) for every readable history JSON, oldest
    first by filename; unreadable files are reported, never silently skipped."""
    reports, unreadable = [], []
    for d in history_dirs:
        if not d.is_dir():
            continue
        for p in sorted(d.glob("*.json")):
            try:
                reports.append((p, json.loads(p.read_text(encoding="utf-8"))))
            except (OSError, json.JSONDecodeError) as exc:
                unreadable.append(f"{p}: {exc}")
    return reports, unreadable


def rec_appearances(reports):
    """rec_id -> list of (history file name, review_date, mode)."""
    seen = {}
    for path, report in reports:
        for rec in report.get("recommendations", []) or []:
            rid = rec.get("recommendation_id")
            if rid:
                seen.setdefault(rid, []).append(
                    (path.name, report.get("review_date", "?"), report.get("mode", "?")))
    return seen


def closure_events(target, since_days):
    """rec_id -> list of closure/revert events from git log (newest first)."""
    try:
        proc = subprocess.run(
            ["git", "log", f"--since={since_days} days ago",
             "--format=%h%x1f%cI%x1f%s%x1f%b%x1e"],
            cwd=str(target), capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=60)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, f"git log failed: {exc}"
    if proc.returncode != 0:
        return None, f"git log failed: {proc.stderr.strip()[:200]}"
    events = {}

    def add(rid, kind, sha, date, subject):
        events.setdefault(rid, []).append(
            {"kind": kind, "commit": sha, "date": date, "subject": subject})

    for raw in proc.stdout.split("\x1e"):
        fields = raw.strip("\r\n").split("\x1f", 3)
        if len(fields) != 4:
            continue
        sha, date, subject, body = fields
        m = CLOSURE_SUBJECT_RE.match(subject.strip())
        if m:
            add(m.group("rec").upper(), m.group("verb").lower(), sha, date, subject)
        m = REVERT_SUBJECT_RE.search(subject)
        if m:
            add(m.group("rec").upper(), "reverts", sha, date, subject)
        for line in body.splitlines():
            m = OUTCOME_TRAILER_RE.match(line.strip())
            if m:
                add(m.group("rec").upper(), f"trailer:{m.group('outcome').lower()}",
                    sha, date, subject)
    return events, ""


def is_closed(rec_events):
    """Closed = the NEWEST closure-relevant event is a closing one (git log is
    newest-first). A later revert or reopened trailer restores open."""
    for e in rec_events or []:
        if e["kind"] in ("reverts", "trailer:reopened"):
            return False
        if e["kind"] in ("applies", "resolves", "trailer:applied",
                         "trailer:validated"):
            return True
        # trailer:rejected closes the recommendation as won't-do
        if e["kind"] == "trailer:rejected":
            return True
    return False


def latest_report(reports, require_recommendations=False):
    """The newest report by review_date (falls back to file order). With
    require_recommendations, the newest one whose recommendations list is
    non-empty - deterministic scheduled heartbeats carry none, and using one
    as the --open baseline would report '0 open' while unapplied
    recommendations sit in the report just before it."""
    best = None
    for path, report in reports:
        if require_recommendations and not report.get("recommendations"):
            continue
        key = report.get("review_date", "")
        if best is None or key >= best[1].get("review_date", ""):
            best = (path, report)
    return best


def main(argv=None):
    p = argparse.ArgumentParser(
        prog="grep_history.py",
        description="Read-only linkage queries over report history + git log "
                    "(the rolling loop's replacement, REC-20260714-001).")
    p.add_argument("--target", default=str(REPO_ROOT))
    p.add_argument("--history-dir", action="append", default=None,
                   help="History dir(s); default: <target>/reports/harness/history "
                        "+ <target>/reports/ai-review/history.")
    p.add_argument("--since-days", type=int, default=365)
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--rec", help="One REC id: appearances + closure status.")
    g.add_argument("--repeats", action="store_true",
                   help="REC ids appearing in more than one history report.")
    g.add_argument("--open", action="store_true", dest="open_",
                   help="REC ids in the newest report with no closure commit.")
    args = p.parse_args(argv)

    target = Path(args.target).resolve()
    if not target.is_dir():
        print(f"ERROR: target not found: {target}", file=sys.stderr)
        return 2
    if args.rec and not REC_ID_RE.match(args.rec):
        print(f"ERROR: not a REC id: {args.rec} (expected REC-YYYYMMDD-NNN)",
              file=sys.stderr)
        return 2
    history_dirs = ([Path(d) for d in args.history_dir] if args.history_dir else
                    [target / "reports" / "harness" / "history",
                     target / "reports" / "ai-review" / "history"])
    reports, unreadable = history_reports(history_dirs)
    for u in unreadable:
        print(f"WARN unreadable history file: {u}")
    appearances = rec_appearances(reports)
    events, err = closure_events(target, args.since_days)
    if events is None:
        print(f"WARN closure scan unavailable ({err}); reporting history only")
        events = {}

    if args.rec:
        rid = args.rec.upper()
        rows = appearances.get(rid, [])
        print(f"{rid}: {len(rows)} appearance(s) in {len(reports)} history report(s)")
        for name, date, mode in rows:
            print(f"  seen {date}  {mode}  ({name})")
        for e in events.get(rid, []):
            print(f"  commit {e['commit']} {e['date']}  [{e['kind']}]  {e['subject']}")
        print(f"  status: {'CLOSED' if is_closed(events.get(rid)) else 'OPEN'}"
              f" (closure convention: applies/resolves subject or Harness-Outcome trailer)")
    elif args.repeats:
        repeats = {rid: rows for rid, rows in appearances.items() if len(rows) > 1}
        print(f"{len(repeats)} REC id(s) appear in more than one of "
              f"{len(reports)} history report(s)")
        for rid in sorted(repeats):
            rows = repeats[rid]
            print(f"  {rid}: {len(rows)}x  first {rows[0][1]}  last {rows[-1][1]}"
                  f"{'  [CLOSED]' if is_closed(events.get(rid)) else ''}")
    else:
        newest_with_recs = latest_report(reports, require_recommendations=True)
        newest = newest_with_recs or latest_report(reports)
        if newest is None:
            print("No history reports found - run the runners first.")
            return 0
        path, report = newest
        label = ("newest report with recommendations" if newest_with_recs
                 else "newest report (no report carries recommendations)")
        rec_ids = sorted({r.get("recommendation_id")
                          for r in report.get("recommendations", []) or []
                          if r.get("recommendation_id")})
        open_ids = [rid for rid in rec_ids if not is_closed(events.get(rid))]
        print(f"{label}: {path.name} ({report.get('review_date', '?')}) - "
              f"{len(open_ids)} open / {len(rec_ids)} total")
        for rid in open_ids:
            print(f"  OPEN {rid}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
