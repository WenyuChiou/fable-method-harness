#!/usr/bin/env python3
"""Print a route's ENTIRE lean context bundle in one call — the turn-cost fix.

Why (measured, 2026-07-11 live A/Bs route-live-ab{,-heavy}-20260711): the
route discipline reliably cut content READ to 0.65-0.73x of free
orientation, but total cost broke even because the discipline spent ~8
extra turns (route_show -> per-file reads -> per-name greps), and every
turn replays the session's standing context. This script collapses the
orientation phase to ONE tool call: the route entry plus the full text of
every start+required file, with per-file byte counts and a total.

Run:
    python scripts/route_pack.py <task_type | ROUTE-id>
    python scripts/route_pack.py repo_maintenance --entry-only
    python scripts/route_pack.py --list

Exit: 0 printed; 1 no such route; 2 environment error.
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path

from route_show import split_entries

repo_root = Path(__file__).resolve().parent.parent


def route_files(block: str):
    """Extract start+required file paths from one route block, in order."""
    out, section = [], None
    for line in block.splitlines():
        sec = re.match(r"^\s{4}(start|required|optional|entrypoints):\s*$", line)
        if sec:
            section = sec.group(1)
            continue
        item = re.match(r"^\s{6}- (\S+)\s*$", line)
        if item and section in ("start", "required"):
            out.append(item.group(1))
    return out


def main() -> int:
    if hasattr(sys.stdout, "buffer"):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                      errors="replace")
    args = sys.argv[1:]
    query = next((a for a in args if not a.startswith("--")), None)
    try:
        text = (repo_root / "ROUTES.yaml").read_text(encoding="utf-8")
    except OSError as e:
        print(f"ERROR reading ROUTES.yaml: {e}")
        return 2
    _, entries = split_entries(text)

    if "--list" in args or query is None:
        for rid, ttype, _ in entries:
            print(f"{rid}  ({ttype})")
        return 0

    for rid, ttype, block in entries:
        if query in (rid, ttype):
            print(block)
            if "--entry-only" in args:
                return 0
            total = 0
            for rel in route_files(block):
                p = repo_root / rel
                try:
                    body = p.read_text(encoding="utf-8", errors="replace")
                except OSError as e:
                    print(f"\n===== {rel} (UNREADABLE: {e}) =====")
                    continue
                total += len(body)
                print(f"\n===== {rel} ({len(body):,} bytes) =====")
                print(body.rstrip("\n"))
            print(f"\n===== pack total: {total:,} bytes "
                  f"(~{total // 4:,} tok) — start+required only; grep INDEX "
                  f"entries for anything else =====")
            return 0

    print(f"no route matches '{query}'; valid:")
    for rid, ttype, _ in entries:
        print(f"  {rid}  ({ttype})")
    return 1


if __name__ == "__main__":
    sys.exit(main())
