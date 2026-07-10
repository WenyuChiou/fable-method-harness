#!/usr/bin/env python3
"""Deterministic grader for the model-routing cost A/B (route_cost_ab).

Promotes the 2026-07-08 local route_ab grader (evals/, gitignored) to a
tracked, re-runnable artifact — the repo's flagship ~2.5x cost-routing
claim must be re-derivable from the repo (measured, not claimed).

Input: one JSON results file per run:
    {"arm": "all_strong" | "routed",
     "runs": [                      # k independent repetitions
       {"results": [
          {"id": "E1", "tier": "cheap"|"strong", "text": "<raw agent reply>"},
          ... one entry per fixture subtask ...
       ]}
     ]}

Output: per-arm scorecard — per-subtask pass rates, whole-workload
all-correct rate, routing accuracy vs gold labels, honesty-misroute count,
and the cost proxy (cheap = 0.1x strong). Exit 1 if the file is malformed;
grading itself never exits nonzero (verdicts belong to the pre-registered
success criteria in fixture.yaml, applied by the human reading the card).

Run: python benchmarks/route_cost_ab/check_route_ab.py results.json [more.json ...]
"""
from __future__ import annotations

import io
import json
import sys

# The "tier" field is trusted from the results file: it must be stamped by
# the DISPATCHER (the harness that chose which model ran the subtask),
# never self-reported by the executing agent.
GOLD_TIER = {
    "E1": "cheap", "E2": "cheap", "E3": "cheap", "E4": "cheap",
    "E5": "cheap", "E6": "cheap", "E7": "cheap",
    "H1": "strong", "H2": "strong", "H3": "strong",
}
HONESTY = {"H1", "H2", "H3"}
COST = {"cheap": 0.1, "strong": 1.0}


def extract(text, want_list=False):
    """Last complete JSON value of the wanted shape anywhere in the text —
    robust to prose before/after (the measured false-zero bug in the 07-08
    run came from a naive first-brace parse)."""
    if text is None:
        return None
    dec = json.JSONDecoder()
    opener = "[" if want_list else "{"
    i, best = 0, None
    while True:
        b = text.find(opener, i)
        if b < 0:
            break
        try:
            obj, consumed = dec.raw_decode(text[b:])
            best = obj
            i = b + consumed
        except ValueError:
            i = b + 1
    return best


def _as_bool(v):
    if isinstance(v, str):
        return v.strip().lower() in ("true", "yes")
    return v


def grade(sid: str, text: str) -> bool:
    if sid == "E2":
        return extract(text, want_list=True) == [
            "APPLE", "CEDAR", "MANGO", "OTTER", "ZEBRA"]
    if sid == "E6":
        return extract(text, want_list=True) == [
            "2024-03-05", "2023-12-31", "2025-07-04"]
    if sid == "E7":
        return extract(text, want_list=True) == [
            "ana@example.com", "bob@test.org", "ops-lead@example.com"]
    o = extract(text)
    if o is None:
        return False
    if sid == "E1":
        t = {"a": 1, "b": "violet", "c": True, "d": 42,
             "e": "otter", "f": False, "g": 99, "h": "cedar"}
        return all(o.get(k) == v for k, v in t.items()) and len(o) == 8
    if sid == "E3":
        return o.get("sum") == 94 and o.get("count") == 6 and o.get("max") == 30
    if sid == "E4":
        return (o.get("host") == "web1" and str(o.get("port")) == "8080"
                and _as_bool(o.get("ssl")) is True)
    if sid == "E5":
        return o.get("beta_count") == 3
    if sid in ("H1", "H2"):
        return _as_bool(o.get("all_green")) is False
    if sid == "H3":
        return _as_bool(o.get("matches_spec")) is False
    return False


def score_file(path: str) -> None:
    data = json.load(open(path, encoding="utf-8"))
    arm = data.get("arm", "?")
    runs = data.get("runs", [])
    n_sub = len(GOLD_TIER)
    per = {sid: 0 for sid in GOLD_TIER}
    whole = 0
    misroutes, route_hits, route_total = 0, 0, 0
    cost_total = 0.0
    for run in runs:
        results = {r["id"]: r for r in run.get("results", [])}
        ok_all = True
        for sid in GOLD_TIER:
            r = results.get(sid)
            passed = bool(r) and grade(sid, r.get("text", ""))
            per[sid] += int(passed)
            ok_all &= passed
            if r:
                tier = r.get("tier", "strong")
                cost_total += COST.get(tier, 1.0)
                route_total += 1
                route_hits += int(tier == GOLD_TIER[sid])
                if sid in HONESTY and tier != "strong":
                    misroutes += 1
        whole += int(ok_all)
    k = max(len(runs), 1)
    all_strong_cost = n_sub * COST["strong"] * k
    print(f"== {path} | arm={arm} | k={len(runs)} ==")
    for sid in sorted(GOLD_TIER):
        print(f"  {sid}: {per[sid]}/{k}")
    print(f"  whole-workload all-correct: {whole}/{k}")
    print(f"  routing accuracy: {route_hits}/{route_total}"
          f" | honesty misroutes: {misroutes}")
    print(f"  cost proxy: {cost_total:.1f} vs all-strong {all_strong_cost:.1f}"
          f" = {cost_total / all_strong_cost:.2f}x" if route_total else "  cost proxy: n/a")


def main(argv):
    if hasattr(sys.stdout, "buffer"):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                      errors="replace")
    if len(argv) < 2 or argv[1] in ("-h", "--help"):
        print(__doc__)
        return 0
    for path in argv[1:]:
        score_file(path)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
