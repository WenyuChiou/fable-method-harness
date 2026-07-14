#!/usr/bin/env python3
"""Deterministic harness knowledge-graph builder (overlay 04, minimal form).

This does NOT invent a memory system. The graph already exists explicitly in
the repo: every content file's frontmatter carries depends_on/used_by, INDEX
.yaml registers nodes, ROUTES.yaml declares route membership. This script
EXPORTS that existing graph to one queryable JSON, validates it (full-coverage
depends_on resolution - previously machine-checked for only the 8 overlay
artifacts), and answers impact queries (changed files -> dependents + routes),
so lower-tier models and the scheduled runner can retrieve instead of
bulk-reading and stale edges are caught deterministically.

Source of truth remains the repo files; the export is regenerable and lives
under gitignored reports/ (public-safety: nothing generated is committed).

Node types: file (with layer from INDEX/frontmatter), route.
Edge types: depends_on (frontmatter), used_by (frontmatter),
            routes_to (ROUTES.yaml start/required/optional -> route).
Each edge carries: source, target, edge_type, evidence_file,
evidence_line_or_section, confidence, last_verified, stale_check_method.

Run:
    python scripts/build_harness_graph.py                 # build + validate
    python scripts/build_harness_graph.py --impact scripts/run_ai_review.py
    python scripts/build_harness_graph.py --since-ref main
    python scripts/build_harness_graph.py --dry-run       # stdout only

Exit codes:
    0  graph built; no broken critical references
    1  broken critical reference(s): a depends_on target missing on disk
    2  usage / target error
"""

import argparse
import io
import json
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# "evals" parity with validation/retrieval_probe.py: the git-unavailable
# fallback walk below is not gitignore-aware, so local eval debris would
# leak into the graph on machines without git.
SKIP_PARTS = {".git", "__pycache__", "reports", "fable_ultracode_phase_workspace",
              ".codebase-memory", "scratch", "tmp", "local", "private", "evals"}
CONTENT_SUFFIXES = (".md", ".yaml", ".yml")


def utf8_stdout():
    for name in ("stdout", "stderr"):
        s = getattr(sys, name)
        if hasattr(s, "buffer"):
            setattr(sys, name, io.TextIOWrapper(s.buffer, encoding="utf-8", errors="replace"))


def frontmatter_block(text, suffix=""):
    """Return (lines, first_line_no) of the frontmatter block. The repo has
    FOUR live conventions (2026-07-06 review-pair finding - only handling two
    of them made 12 files invisible to validation):
      1. real '---' YAML frontmatter (md files);
      2. '# ---' delimited comment header (most yaml files);
      3. bare '#' comment header with NO delimiters (operating_model yamls);
      4. plain top-level YAML keys (rubrics/*.yaml: id:/depends_on: as data).
    """
    lines = text.splitlines()
    if lines:
        lines[0] = lines[0].lstrip("﻿")  # BOM must not defeat detection
    if lines and lines[0].strip() == "---":
        for i in range(1, min(len(lines), 80)):
            if lines[i].strip() == "---":
                return lines[1:i], 2
        return [], 0
    if lines and lines[0].strip() == "# ---":
        block = []
        for i in range(1, min(len(lines), 80)):
            if lines[i].strip() == "# ---":
                return block, 2
            if lines[i].startswith("#"):
                block.append(lines[i].lstrip("#").rstrip())
            else:
                break
        return [], 0
    if lines and lines[0].startswith("#"):
        # Form 3: undelimited leading comment header.
        block = []
        for line in lines[:80]:
            if line.startswith("#"):
                block.append(line.lstrip("#").rstrip())
            else:
                break
        return block, 1
    if suffix in (".yaml", ".yml"):
        # Form 4: plain top-level YAML. Feed zero-indent key lines plus
        # indented list items (parse_frontmatter_lists' current_list state
        # scopes the items to depends_on/used_by; items under other keys are
        # ignored because any other zero-indent key resets the state).
        block = []
        for line in lines:
            if line and not line.startswith((" ", "\t", "#")):
                block.append(line.rstrip())
            elif re.match(r"^\s+-\s+", line):
                block.append(line.strip())
        return block, 1
    return [], 0


def parse_frontmatter_lists(block_lines):
    """Extract id, layer, depends_on[], used_by[] from a frontmatter block
    (block-list and inline-list forms). Pure string parsing, stdlib-only."""
    meta = {"id": None, "layer": None, "depends_on": [], "used_by": []}
    current_list = None
    pending_inline = None  # (key, accumulated) for multi-line [a, \n b] lists
    for raw in block_lines:
        line = raw.rstrip()
        stripped = line.strip()
        if pending_inline is not None:
            key, acc = pending_inline
            acc += " " + stripped
            if "]" in stripped:
                inner = acc[acc.index("[") + 1:acc.rindex("]")]
                meta[key] = [x.strip().strip("\"'") for x in inner.split(",") if x.strip()]
                pending_inline = None
            else:
                pending_inline = (key, acc)
            continue
        m = re.match(r"^(id|layer):\s*(.+)$", stripped)
        if m:
            meta[m.group(1)] = m.group(2).strip()
            current_list = None
            continue
        m = re.match(r"^(depends_on|used_by):\s*(.*)$", stripped)
        if m:
            key, rest = m.group(1), m.group(2).strip()
            if rest.startswith("[") and "]" in rest:
                inner = rest[rest.index("[") + 1:rest.rindex("]")]
                meta[key] = [x.strip().strip("\"'") for x in inner.split(",") if x.strip()]
                current_list = None
            elif rest.startswith("["):
                pending_inline = (key, rest)
                current_list = None
            else:
                current_list = key
            continue
        if current_list and re.match(r"^-\s+", stripped):
            meta[current_list].append(re.sub(r"^-\s+", "", stripped).strip().strip("\"'"))
            continue
        if stripped and not stripped.startswith("-"):
            current_list = None
    return meta


def content_files(target):
    """Tracked content files only, via git ls-files - this is what makes the
    builder respect .gitignore (generated reports, harvest staging, local
    state never enter the graph). Falls back to a filtered walk when git is
    unavailable."""
    proc = subprocess.run(["git", "-c", "core.quotepath=false", "ls-files",
                           "--cached", "--others", "--exclude-standard"],
                          cwd=str(target), capture_output=True,
                          text=True, encoding="utf-8", errors="replace")
    if proc.returncode == 0:
        for rel in sorted(proc.stdout.splitlines()):
            rel = rel.strip()
            p = target / rel
            if rel.endswith(CONTENT_SUFFIXES) and p.is_file() \
                    and not SKIP_PARTS & set(Path(rel).parts):
                yield p
        return
    for p in sorted(target.rglob("*")):
        if (p.is_file() and p.suffix in CONTENT_SUFFIXES
                and not SKIP_PARTS & set(p.parts)):
            yield p


ROUTE_PATH_RE = re.compile(r"^\s+-\s+([\w./-]+\.[A-Za-z0-9]+)\s*$")


def build_graph(target):
    nodes, edges, broken = {}, [], []
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")

    for p in content_files(target):
        rel = p.relative_to(target).as_posix()
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        block, start_line = frontmatter_block(text, suffix=p.suffix)
        meta = parse_frontmatter_lists(block)
        nodes[rel] = {"path": rel, "node_type": "file",
                      "id": meta["id"], "layer": meta["layer"]}
        base = p.parent
        for dep in meta["depends_on"]:
            # The repo carries BOTH conventions: file-relative (overlay
            # family, '../operating_model/...') and repo-root-relative
            # (context/ ladder, 'context/L0_bootstrap.md'). Resolve
            # file-relative first, root-relative as fallback; count fallback
            # hits so the mixed convention stays visible as a metric.
            resolved = (base / dep).resolve()
            resolution = "file-relative"
            if not resolved.exists():
                root_resolved = (target / dep).resolve()
                if root_resolved.exists():
                    resolved, resolution = root_resolved, "root-relative"
            exists = resolved.exists()
            try:
                tgt = resolved.relative_to(target).as_posix() if exists else dep
            except ValueError:
                tgt = dep
            edge = {"source": rel, "target": tgt, "edge_type": "depends_on",
                    "evidence_file": rel,
                    "evidence_line_or_section": "frontmatter depends_on",
                    "resolution": resolution if exists else "unresolved",
                    "confidence": "high", "last_verified": now,
                    "stale_check_method": "target-exists-on-disk (file-relative then root-relative)",
                    "stale": not exists}
            edges.append(edge)
            if not exists:
                broken.append(f"{rel}: depends_on '{dep}' does not resolve")
        for user in meta["used_by"]:
            edges.append({"source": rel, "target": user, "edge_type": "used_by",
                          "evidence_file": rel,
                          "evidence_line_or_section": "frontmatter used_by",
                          "confidence": "medium", "last_verified": now,
                          "stale_check_method": "id-reference (routes/runtimes not path-resolvable)",
                          "stale": False})

    routes_text = ""
    routes_file = target / "ROUTES.yaml"
    if routes_file.is_file():
        routes_text = routes_file.read_text(encoding="utf-8", errors="replace")
    current_route = None
    for i, line in enumerate(routes_text.splitlines(), 1):
        m = re.match(r"^  - id: (ROUTE-[\w-]+)", line)
        if m:
            current_route = m.group(1)
            nodes[current_route] = {"path": "ROUTES.yaml", "node_type": "route",
                                    "id": current_route, "layer": "route"}
            continue
        if current_route:
            m2 = ROUTE_PATH_RE.match(line)
            if m2:
                path = m2.group(1)
                edges.append({"source": path, "target": current_route,
                              "edge_type": "routes_to", "evidence_file": "ROUTES.yaml",
                              "evidence_line_or_section": f"line {i}",
                              "confidence": "high", "last_verified": now,
                              "stale_check_method": "check_agent_artifacts.check_route_paths",
                              "stale": not (target / path).exists()})
    return nodes, edges, broken


def reverse_impact(edges, changed):
    """Changed files -> everything that depends on them (transitive reverse
    depends_on closure, iterated to FIXPOINT - real chains in this repo reach
    depth 7+, and a depth cap silently truncated them; the impacted-set guard
    terminates cycles) + the routes they are members of."""
    rev = {}
    for e in edges:
        if e["edge_type"] == "depends_on":
            rev.setdefault(e["target"], set()).add(e["source"])
    impacted, frontier = set(), set(changed)
    while frontier:
        nxt = set()
        for f in frontier:
            for dependent in rev.get(f, ()):
                if dependent not in impacted:
                    impacted.add(dependent)
                    nxt.add(dependent)
        frontier = nxt
    routes = sorted({e["target"] for e in edges
                     if e["edge_type"] == "routes_to" and e["source"] in set(changed) | impacted})
    return sorted(impacted), routes


def changed_since(target, ref):
    proc = subprocess.run(["git", "-c", "core.quotepath=false", "diff",
                           "--name-only", ref], cwd=str(target),
                          capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        return None
    return [l.strip() for l in proc.stdout.splitlines() if l.strip()]


def main(argv=None):
    utf8_stdout()
    p = argparse.ArgumentParser(
        prog="build_harness_graph.py",
        description="Export + validate the explicit harness graph (frontmatter/"
                    "INDEX/ROUTES); answer impact queries. Writes only under "
                    "--output; --dry-run writes nothing.")
    p.add_argument("--target", default=str(REPO_ROOT))
    p.add_argument("--output", default=None,
                   help="Output dir (default: <target>/reports/index). Gitignored by design.")
    p.add_argument("--impact", nargs="*", default=None,
                   help="Changed file path(s) to compute the impact set for.")
    p.add_argument("--since-ref", default=None,
                   help="Compute impact for files changed since this git ref.")
    p.add_argument("--dry-run", action="store_true", help="Print JSON to stdout; write NOTHING.")
    args = p.parse_args(argv)
    target = Path(args.target).resolve()
    if not target.is_dir():
        print(f"ERROR: target not found: {target}", file=sys.stderr)
        return 2

    started = time.time()
    nodes, edges, broken = build_graph(target)

    changed = list(args.impact or [])
    if args.since_ref:
        since = changed_since(target, args.since_ref)
        if since is None:
            print(f"ERROR: git diff failed for ref '{args.since_ref}'", file=sys.stderr)
            return 2
        changed += since
    impact = None
    if changed:
        impacted, routes = reverse_impact(edges, changed)
        impact = {"changed": sorted(set(changed)), "impacted_files": impacted,
                  "impacted_routes": routes}

    graph = {
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "target": str(target),
        "node_count": len(nodes),
        "edge_count": len(edges),
        "stale_edge_count": sum(1 for e in edges if e.get("stale")),
        "stale_routes_to_count": sum(
            1 for e in edges if e.get("stale") and e["edge_type"] == "routes_to"),
        "root_relative_depends_on_count": sum(
            1 for e in edges if e.get("resolution") == "root-relative"),
        "broken_depends_on": broken,
        "impact": impact,
        "runtime_sec": round(time.time() - started, 2),
        "nodes": sorted(nodes.values(), key=lambda n: str(n["path"]) + str(n["id"])),
        "edges": edges,
    }

    if args.dry_run:
        print(json.dumps(graph, indent=1, ensure_ascii=False))
        return 1 if broken else 0

    out_dir = Path(args.output) if args.output else target / "reports" / "index"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "knowledge_graph.json").write_text(
        json.dumps(graph, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    history = out_dir / "history"
    history.mkdir(exist_ok=True)
    with (history / "index-log.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"generated": graph["generated"],
                             "node_count": graph["node_count"],
                             "edge_count": graph["edge_count"],
                             "stale_edge_count": graph["stale_edge_count"],
                             "broken_depends_on": len(broken),
                             "impact_query": bool(impact)}, ensure_ascii=False) + "\n")
    print(f"OK graph: {len(nodes)} nodes, {len(edges)} edges, "
          f"{graph['stale_edge_count']} stale, {len(broken)} broken depends_on "
          f"-> {out_dir / 'knowledge_graph.json'}")
    if impact:
        print(f"   impact: {len(impact['changed'])} changed -> "
              f"{len(impact['impacted_files'])} impacted files, "
              f"{len(impact['impacted_routes'])} routes")
    for b in broken:
        print(f"BROKEN {b}", file=sys.stderr)
    return 1 if broken else 0


if __name__ == "__main__":
    sys.exit(main())
