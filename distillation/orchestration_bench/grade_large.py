#!/usr/bin/env python3
"""Behavioral grader for T-LARGE (eventkit). Primary metrics: buried_rate + hazard_pass.

Per the T-LARGE audit, the discriminating signal is NOT overall requirement coverage (Opus aces
the loud breadth) but whether the orchestrator DROPS the buried invariants / BREAKS the
coordination hazard. So this grader checks, by RUNNING the arm's built code (behavioral, not
substring — behavioral checks are robust to legitimate implementation variety):

  buried invariants (buried_rate = k/5):
    I1 registry stores TYPES not name-strings
    I2 parse coerces ts to int via the registry
    I3 filter on an unknown field RAISES (not silent non-match)
    I4 config strict-REJECTS unknown keys (raises)
    I6 README documents all 3 subcommands + the schema version
  hazard (hazard_pass, force-firing single-source):
    I5 SCHEMA_VERSION single-sourced — monkeypatch registry.SCHEMA_VERSION, `cli version` must
       print the patched value (a re-literalled version REGRESSES this)

Each check runs in a fresh subprocess inside the submission dir so imports resolve and a crash in
one check cannot poison another. A check that cannot run (import/attr error) counts as NOT
satisfied (DR-011: no silent pass — a broken build does not get invariant credit).

Usage:  python grade_large.py <submission_dir_containing_eventkit/>   |   python grade_large.py --selftest
"""
import json
import os
import subprocess
import sys

PY = sys.executable

# Each probe is a self-contained python snippet run inside the submission dir. It must print
# exactly "PASS" on its last line if the invariant holds, else anything else (or crash).
PROBES = {
    "I1_registry_types": r"""
from eventkit import registry as r
vals = list(getattr(r, "FIELD_TYPES", {}).values())
print("PASS" if vals and all(isinstance(v, type) for v in vals) else "FAIL")
""",
    "I2_parse_coerces_ts": r"""
from eventkit import parse
e = parse.parse_line("ts=100 level=info msg=hi")
print("PASS" if isinstance(e.get("ts"), int) else "FAIL")
""",
    "I3_unknown_field_raises": r"""
from eventkit import filters
try:
    filters.match({"level": "info"}, "not_a_field", "x")
    print("FAIL")   # silently returned instead of raising
except Exception:
    print("PASS")
""",
    "I4_config_strict_reject": r"""
from eventkit import config
try:
    config.load_config({"totally_unknown_key": 1})
    print("FAIL")
except Exception:
    print("PASS")
""",
    "I6_readme_documents": r"""
import io, os, re
txt = ""
for name in ("README.md", "readme.md", "README.rst"):
    if os.path.exists(name):
        txt = open(name, encoding="utf-8", errors="replace").read().lower(); break
from eventkit import registry as r
ver = str(getattr(r, "SCHEMA_VERSION", "\x00__nover__"))
has_cmds = all(c in txt for c in ("ingest", "query", "version"))
has_ver = ver.lower() in txt and ver != "\x00__nover__"
print("PASS" if (has_cmds and has_ver) else "FAIL")
""",
    # HAZARD (force-firing): patch the registry's version; the CLI must reflect it (single source).
    "I5_version_single_source": r"""
import io, contextlib
from eventkit import registry as r
r.SCHEMA_VERSION = "9.9.9-probe"
from eventkit import cli
buf = io.StringIO()
rc = None
try:
    with contextlib.redirect_stdout(buf):
        rc = cli.main(["version"])
except SystemExit:
    pass
except Exception:
    print("FAIL"); raise SystemExit
out = buf.getvalue()
print("PASS" if "9.9.9-probe" in out else "FAIL")
""",
}
BURIED = ["I1_registry_types", "I2_parse_coerces_ts", "I3_unknown_field_raises",
          "I4_config_strict_reject", "I6_readme_documents"]
HAZARD = "I5_version_single_source"


def run_probe(sub_dir, code):
    try:
        p = subprocess.run([PY, "-c", code], cwd=sub_dir, capture_output=True, text=True, timeout=30)
        last = [l for l in (p.stdout or "").strip().splitlines() if l.strip()]
        return bool(last) and last[-1].strip() == "PASS"
    except Exception:
        return False


def grade(sub_dir):
    # sub_dir must contain an importable eventkit/ package
    results = {name: run_probe(sub_dir, code) for name, code in PROBES.items()}
    buried_hits = sum(1 for k in BURIED if results[k])
    return {
        "per_invariant": results,
        "buried_rate": round(buried_hits / len(BURIED), 3),
        "buried_hits": buried_hits, "buried_total": len(BURIED),
        "hazard_pass": bool(results[HAZARD]),
    }


# --- selftest: build a gold (all-satisfied) + weak (loud-only, invariants dropped) submission,
#     assert the grader gives gold buried_rate 1.0 + hazard pass, weak buried_rate 0.0 + hazard fail
GOLD = {
    "eventkit/__init__.py": "",
    "eventkit/registry.py": 'SCHEMA_VERSION = "1.2.0"\nFIELD_TYPES = {"ts": int, "level": str, "msg": str}\n',
    "eventkit/parse.py": (
        "from eventkit.registry import FIELD_TYPES\n"
        "def parse_line(line):\n"
        "    out = {}\n"
        "    for tok in line.split():\n"
        "        if '=' in tok:\n"
        "            k, v = tok.split('=', 1)\n"
        "            t = FIELD_TYPES.get(k)\n"
        "            out[k] = t(v) if t else v\n"
        "    return out\n"
    ),
    "eventkit/filters.py": (
        "from eventkit.registry import FIELD_TYPES\n"
        "def match(event, field, value):\n"
        "    if field not in FIELD_TYPES:\n"
        "        raise KeyError(field)\n"
        "    return event.get(field) == value\n"
    ),
    "eventkit/config.py": (
        "from eventkit.registry import FIELD_TYPES\n"
        "_ALLOWED = set(FIELD_TYPES) | {'path', 'level'}\n"
        "def load_config(d):\n"
        "    bad = set(d) - _ALLOWED\n"
        "    if bad:\n"
        "        raise ValueError(f'unknown keys: {bad}')\n"
        "    return dict(d)\n"
    ),
    "eventkit/cli.py": (
        "import sys, argparse\n"
        "from eventkit.registry import SCHEMA_VERSION\n"
        "def main(argv=None):\n"
        "    argv = sys.argv[1:] if argv is None else argv\n"
        "    ap = argparse.ArgumentParser(prog='eventkit')\n"
        "    sub = ap.add_subparsers(dest='cmd')\n"
        "    sub.add_parser('ingest'); sub.add_parser('query'); sub.add_parser('version')\n"
        "    a = ap.parse_args(argv)\n"
        "    if a.cmd == 'version':\n"
        "        print(SCHEMA_VERSION)\n"
        "    return 0\n"
    ),
    "README.md": "# eventkit\nSubcommands: `ingest`, `query`, `version`.\nSchema version: 1.2.0\n",
}
WEAK = dict(GOLD)
# weak orchestrator: loud CLI works but drops every buried invariant + re-literals the version
WEAK["eventkit/registry.py"] = 'SCHEMA_VERSION = "1.2.0"\nFIELD_TYPES = {"ts": "int", "level": "str"}\n'
WEAK["eventkit/parse.py"] = "def parse_line(line):\n    return dict(t.split('=',1) for t in line.split() if '=' in t)\n"
WEAK["eventkit/filters.py"] = "def match(event, field, value):\n    return event.get(field) == value\n"
WEAK["eventkit/config.py"] = "def load_config(d):\n    return dict(d)\n"
WEAK["eventkit/cli.py"] = (
    "import sys, argparse\n"
    "def main(argv=None):\n"
    "    argv = sys.argv[1:] if argv is None else argv\n"
    "    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest='cmd')\n"
    "    sub.add_parser('ingest'); sub.add_parser('query'); sub.add_parser('version')\n"
    "    a = ap.parse_args(argv)\n"
    "    if a.cmd == 'version':\n"
    "        print('1.2.0')\n"   # re-literalled -> breaks single-source hazard
    "    return 0\n"
)
WEAK["README.md"] = "# eventkit\nAn event library.\n"   # drops subcommand + version docs


def _materialize(root, files):
    import pathlib
    for rel, content in files.items():
        p = pathlib.Path(root) / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8", newline="\n")


def selftest():
    import tempfile
    fails = 0
    for name, files, exp_rate, exp_haz in [("GOLD", GOLD, 1.0, True), ("WEAK", WEAK, 0.0, False)]:
        d = tempfile.mkdtemp()
        _materialize(d, files)
        r = grade(d)
        ok = (r["buried_rate"] == exp_rate) and (r["hazard_pass"] == exp_haz)
        print(f"{'ok  ' if ok else 'FAIL'} {name}: buried_rate={r['buried_rate']} hazard_pass={r['hazard_pass']} "
              f"(expected {exp_rate}/{exp_haz})  per={r['per_invariant']}")
        if not ok:
            fails += 1
    print(f"\n{2-fails}/2 selftest cases pass")
    return 1 if fails else 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    if len(sys.argv) < 2:
        print("usage: grade_large.py <submission_dir> | --selftest"); sys.exit(2)
    print(json.dumps(grade(sys.argv[1]), indent=2))
