#!/usr/bin/env python3
"""Scripted retrieval smoke probes (docs/retrieval_smoke_test.md, computed form).

Each probe is a term-set query; it PASSES iff every expected file contains all
terms (the grep-on-retrieval_keywords form of the smoke test's step 2). Also
sweeps INDEX.yaml for ghost entries (paths that do not exist on disk).

Committed under validation/ so smoke runs are re-runnable from the repo
instead of reconstructed per session (2026-07-06 review-pair finding: the
dated smoke records cited a session-scratchpad script that did not travel
with the repo — measured-not-claimed requires the instrument to be durable).

Run:
    python validation/retrieval_probe.py

Exit codes: 0 all probes pass and zero INDEX ghosts; 1 otherwise.
"""
import io
import re
import sys
from pathlib import Path

repo_root = Path(__file__).resolve().parent.parent

# (query terms, expected files) — extend per edit round; never weaken an
# expectation to make a probe pass (smoke-test procedure step 5).
PROBES = [
    ("codex delegation policy tripwire", ["docs/codex-delegation-policy.md"]),
    ("ai review modes checklist ingest", ["prompts/ai-review-modes.md"]),
    ("review report schema shared contract", ["schemas/review_report.schema.yaml"]),
    ("recommendation finding schema traceability", ["schemas/recommendation.schema.yaml"]),
    ("ai review benchmark cases ab test", ["benchmarks/ai_review_cases.yaml"]),
    ("ai review runner report-only", ["scripts/run_ai_review.py"]),
    ("publication status public safety review checklist", ["docs/publication_status.md"]),
    ("adaptive harness skill rolling improvement", [".claude/skills/adaptive-harness/SKILL.md"]),
    ("ai review adaptive harness integration division of labor", ["docs/ai_review_adaptive_harness_integration.md"]),
    ("harness benchmark cases skill adapter", ["benchmarks/harness_cases.yaml"]),
    ("adaptive harness runner patch proposal", ["scripts/run_adaptive_harness_review.py"]),
    ("integration test matrix phase3", ["docs/integration_test_matrix.md"]),
    ("model compatibility test plan unverified ledger", ["docs/model_compatibility_test_plan.md"]),
    # pins the invocation lean-load fix (2026-07-08): activation classifies
    # first and loads only the matching rule, not the full portable triad.
    ("global bootstrap portable load classify first lean default", ["core/GLOBAL_BOOTSTRAP.md"]),
    # pins the Wave-1 cost-router operationalization (2026-07-09): the
    # measured 2.5x split must be findable as an operational playbook.
    ("model routing cost router cheap tier mechanical honesty critical strong", ["core/model_routing_playbook.md"]),
    # pins the Wave-2b grep-entry discipline (2026-07-09): the two
    # wholesale-read killers must stay findable.
    ("index diff tracked ghost unindexed duplicate mt-5", ["scripts/index_diff.py"]),
    ("route show one validated route entry grep", ["scripts/route_show.py"]),
    # pins the Wave-2c hot/cold split (2026-07-09): the cold history must
    # stay findable after leaving the start ladder.
    ("phase history milestone table gate story cold reference", ["context/L2_phase_history.md"]),
    # content-integrity pin (audit-mandated third-gate probe): the hot L2
    # must keep the third-behavioral-gate prohibition; a future edit that
    # drops it must fail here, not silently narrow the Forbidden list.
    ("do not design or run a third behavioral gate", ["context/L2_current_phase.md"]),
    # pins the Wave-3b multi-delegate adapter (2026-07-10): the contracts
    # + single-gate rule must stay findable.
    ("multi delegate route plan.yml contract single gate", ["docs/multi_delegate_route.md"]),
]

# "evals" is gitignored machine-local debris (measured 1,292 files / 4.3 MB
# on the dev machine): including it made probe diagnostics machine-dependent
# and tripled the scanned corpus vs a fresh clone.
SKIP_PARTS = {".git", "__pycache__", "reports", "fable_ultracode_phase_workspace",
              "evals"}


def searchable_files():
    out = []
    for p in repo_root.rglob("*"):
        if (p.is_file() and p.suffix in (".md", ".yaml", ".py")
                and not SKIP_PARTS & set(p.parts)):
            try:
                out.append((p.relative_to(repo_root).as_posix(),
                            p.read_text(encoding="utf-8", errors="replace").lower()))
            except OSError:
                pass
    return out


def main():
    if hasattr(sys.stdout, "buffer"):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    corpus = searchable_files()
    all_ok = True
    for query, expected in PROBES:
        terms = query.lower().split()
        hits = {f for f, text in corpus if all(t in text for t in terms)}
        ok = all(e in hits for e in expected)
        all_ok &= ok
        print("{} | {} | expected: {} | matching files: {}".format(
            "PASS" if ok else "FAIL", query, expected, len(hits)))
    idx_text = (repo_root / "INDEX.yaml").read_text(encoding="utf-8")
    paths = re.findall(r"^\s*- path:\s*(\S+)\s*$", idx_text, re.M)
    ghosts = [p for p in paths if not (repo_root / p).exists()]
    print("INDEX entries: {} | ghosts: {}".format(len(paths), ghosts if ghosts else "none"))
    print("ALL PROBES PASS" if all_ok and not ghosts else "SOME FAILED")
    return 0 if (all_ok and not ghosts) else 1


if __name__ == "__main__":
    sys.exit(main())
