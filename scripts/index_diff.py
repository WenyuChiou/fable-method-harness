#!/usr/bin/env python3
"""MT-5 machine check: INDEX.yaml must mirror the git-tracked file set exactly.

Empirically derived rule (2026-07-09, Wave 2b): the INDEX's inclusion rule is
simply `git ls-files` — on a clean tree, 204 entries == 204 tracked paths,
zero exceptions, both directions. That makes drift a pure set-difference no
model needs to eyeball: the previous ROUTE-repo-maintenance practice Read the
whole INDEX (~23.5k tokens) to check what this script computes in ~0 tokens.

Prints ONLY mismatches (ghosts / unindexed / duplicates) + a one-line summary.
OUT OF SCOPE, deliberately: purpose-string drift (an entry whose prose no
longer matches the file). That stays a judgment call — grep the specific
entry and read the file; this script narrows MT-5's mechanical half only.

Run:  python scripts/index_diff.py
Exit: 0 clean; 1 any ghost / unindexed / duplicate; 2 environment error.
"""
from __future__ import annotations

import io
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

repo_root = Path(__file__).resolve().parent.parent


def main() -> int:
    if hasattr(sys.stdout, "buffer"):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                      errors="replace")
    try:
        idx_text = (repo_root / "INDEX.yaml").read_text(encoding="utf-8")
    except OSError as e:
        print(f"ERROR reading INDEX.yaml: {e}")
        return 2
    r = subprocess.run(["git", "-C", str(repo_root), "ls-files"],
                       capture_output=True, text=True, encoding="utf-8")
    if r.returncode != 0:
        print(f"ERROR git ls-files: {r.stderr.strip()}")
        return 2

    # (.+?) not \S+, and splitlines() not split(): a path containing a space
    # must not be silently dropped from either side — the review re-test
    # demonstrated a spaced ghost entry passing CLEAN under \S+/split().
    entries = re.findall(r"^\s*- path:\s*(.+?)\s*$", idx_text, re.M)
    tracked = set(line.strip() for line in r.stdout.splitlines() if line.strip())
    indexed = set(entries)

    dupes = sorted(p for p, n in Counter(entries).items() if n > 1)
    ghosts = sorted(indexed - tracked)
    unindexed = sorted(tracked - indexed)

    for p in ghosts:
        print(f"GHOST (in INDEX, not tracked): {p}")
    for p in unindexed:
        print(f"UNINDEXED (tracked, not in INDEX): {p}")
    for p in dupes:
        print(f"DUPLICATE INDEX entry: {p}")

    drift = len(ghosts) + len(unindexed) + len(dupes)
    print(f"{len(entries)} INDEX entries vs {len(tracked)} tracked files: "
          f"{'CLEAN' if drift == 0 else f'{drift} drift item(s)'}"
          f" (purpose-string drift not covered - judgment, per docstring)")
    return 1 if drift else 0


if __name__ == "__main__":
    sys.exit(main())
