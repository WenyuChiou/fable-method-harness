#!/usr/bin/env python3
"""Print ONE route entry from ROUTES.yaml — the grep-entry discipline, scripted.

Measured (2026-07-09 audit): every mhc task Read ROUTES.yaml whole (~5.0k
tokens) to use one ~0.4k-token entry — ~92% dead weight on 100% of route
activations. This prints exactly one validated entry (plus the header rules
block on first activation via --header), so the session loads what it needs.

Run:
    python scripts/route_show.py <task_type | ROUTE-id>
    python scripts/route_show.py pr_review --header
    python scripts/route_show.py --list

Exit: 0 printed; 1 no such route (prints the valid ids); 2 environment error.
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path

repo_root = Path(__file__).resolve().parent.parent


def split_entries(text: str):
    """Return (header, [(route_id, task_type, block)]) split on '  - id:' lines."""
    marker = re.compile(r"^  - id: (ROUTE-\S+)\s*$", re.M)
    hits = list(marker.finditer(text))
    header = text[: hits[0].start()] if hits else text
    out = []
    for i, m in enumerate(hits):
        end = hits[i + 1].start() if i + 1 < len(hits) else len(text)
        block = text[m.start():end].rstrip("\n")
        tm = re.search(r"^\s*task_type:\s*(\S+)", block, re.M)
        out.append((m.group(1), tm.group(1) if tm else "", block))
    return header, out


def main() -> int:
    if hasattr(sys.stdout, "buffer"):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                      errors="replace")
    args = [a for a in sys.argv[1:]]
    want_header = "--header" in args
    want_list = "--list" in args
    query = next((a for a in args if not a.startswith("--")), None)
    try:
        text = (repo_root / "ROUTES.yaml").read_text(encoding="utf-8")
    except OSError as e:
        print(f"ERROR reading ROUTES.yaml: {e}")
        return 2
    header, entries = split_entries(text)

    if want_list or query is None:
        for rid, ttype, _ in entries:
            print(f"{rid}  ({ttype})")
        return 0

    for rid, ttype, block in entries:
        if query in (rid, ttype):
            if want_header:
                print(header.rstrip("\n"))
                print()
            print(block)
            return 0
    print(f"no route matches '{query}'; valid:")
    for rid, ttype, _ in entries:
        print(f"  {rid}  ({ttype})")
    return 1


if __name__ == "__main__":
    sys.exit(main())
