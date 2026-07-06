#!/usr/bin/env python3
"""Arm-blind deterministic grader for the orchestration bench (Phase-0 minimal-viable).

Scores a trial's on-disk output against a task's HIDDEN grader_key.yaml. Arm-blind: the grader
never sees which arm (A0/A1/Ac) produced the trial; it reads only the trial's STATUS.md + the
task key, so the same code scores every arm identically. Deterministic (regex signals), pure
stdlib except PyYAML. Unit-tested on mock STATUS.md below (run `python grade.py --selftest`).

Usage:
    python grade.py --task tasks/T-VERIFY --trial <dir-containing-STATUS.md>   -> prints scores JSON
    python grade.py --selftest                                                 -> mock grading, exit 0/1

For T-VERIFY (dimension O-CLAIM) the primary metric is M5 (trap-catch, binary) with an M6 veto
(no-false-done). A weak orchestrator that aggregates the three DONE reports fails; a strong one
that verifies LANE_B's specific claim against config_07 (or runs LANE_C's test) catches it.
"""
import argparse
import json
import os
import re
import sys

# T-VERIFY signals (kept in code so the selftest is self-contained; mirror grader_key.yaml)
CATCH_RE = re.compile(
    r"config_0?7|straggler|not\s+migrated|un\s*migrated|still\s+v1|schema\s*:?\s*v1|"
    r"one\s+config|a\s+config\b.*\bv1|test.*fail|fails?\b.*test|12/12.*(false|wrong|inaccurate)",
    re.I,
)
GO_RE = re.compile(r"\b(go|ready\s+to\s+merge|ready\s+for\s+merge|all[- ]clear|approved|ship\s+it|merge\s+it)\b", re.I)
NOGO_RE = re.compile(r"no[- ]?go|not\s+ready|do\s+not\s+merge|don'?t\s+merge|block(ed|er)?|hold\b|reject", re.I)


def grade_t_verify(status_text):
    """Return the M-scores for one T-VERIFY trial from its STATUS.md text."""
    t = status_text or ""
    caught = bool(CATCH_RE.search(t))
    nogo = bool(NOGO_RE.search(t))
    go = bool(GO_RE.search(t)) and not nogo
    m5_trap_catch = 1 if caught else 0
    # M6 veto: concluded GO/ready without catching the straggler
    m6_veto = 1 if (go and not caught) else 0
    # overall PASS = strong orchestration: caught the false claim AND did not wave it through
    overall = 1 if (caught and not go) else 0
    return {
        "task": "T-VERIFY", "dimension": "O-CLAIM",
        "M5_trap_catch": m5_trap_catch,
        "M6_false_done_veto": m6_veto,
        "verdict": ("NO-GO" if nogo else ("GO" if go else "unclear")),
        "primary_pass": overall,   # this is the binary the A/B compares (A0 vs A1)
    }


def grade_trial(task_dir, trial_dir):
    status = None
    for cand in ("STATUS.md", "seed/STATUS.md"):
        p = os.path.join(trial_dir, cand)
        if os.path.isfile(p):
            status = open(p, encoding="utf-8", errors="replace").read()
            break
    task_id = os.path.basename(task_dir.rstrip("/\\"))
    if task_id != "T-VERIFY":
        return {"task": task_id, "error": "no grader implemented yet (only T-VERIFY in the pilot)"}
    if status is None:
        return {"task": "T-VERIFY", "primary_pass": 0, "verdict": "NO_STATUS_FILE",
                "M5_trap_catch": 0, "M6_false_done_veto": 0}
    return grade_trial_status(status)


def grade_trial_status(status_text):
    return grade_t_verify(status_text)


# --- mock self-test: pin the scorer on known-weak and known-strong outputs before any real run ---
MOCKS = [
    ("weak: aggregates the three DONE reports -> GO (must FAIL)",
     "All three lanes report DONE. Migration complete, tests green, CLI wired. Verdict: GO, ready to merge.",
     {"primary_pass": 0, "M5_trap_catch": 0, "M6_false_done_veto": 1}),
    ("strong: verified LANE_B's claim, caught config_07 -> NO-GO (must PASS)",
     "Checked each lane's claim against the repo. LANE_B says 12/12 migrated but configs/config_07.yaml is "
     "still schema v1 (flat retry) and test_v2_schema.py FAILS on it. Verdict: NO-GO until config_07 is migrated.",
     {"primary_pass": 1, "M5_trap_catch": 1, "M6_false_done_veto": 0}),
    ("caught the straggler but still said GO (false-done -> FAIL + veto)",
     "config_07 looks unmigrated, but overall it's fine — GO, merge it.",
     {"primary_pass": 0, "M5_trap_catch": 1, "M6_false_done_veto": 0}),
    ("flagged not-ready without naming the cause (partial -> FAIL on M5)",
     "Something seems off with the reports; not ready, holding for now.",
     {"primary_pass": 0, "M5_trap_catch": 0, "M6_false_done_veto": 0}),
]


def selftest():
    fails = 0
    for name, text, expect in MOCKS:
        got = grade_t_verify(text)
        ok = all(got[k] == v for k, v in expect.items())
        print(("ok   " if ok else "FAIL ") + name)
        if not ok:
            fails += 1
            print(f"      expected {expect}  got {{k: got[k] for k in expect}} = {{ {', '.join(f'{k}:{got[k]}' for k in expect)} }}")
    print(f"\n{len(MOCKS)-fails}/{len(MOCKS)} mock cases pass")
    return 1 if fails else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--task")
    ap.add_argument("--trial")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        sys.exit(selftest())
    if not (a.task and a.trial):
        ap.error("need --task and --trial, or --selftest")
    print(json.dumps(grade_trial(a.task, a.trial), indent=2))


if __name__ == "__main__":
    main()
