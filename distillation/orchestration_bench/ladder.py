#!/usr/bin/env python3
"""Escalation-ladder task generator + grader for the Fable-edge test.

The small/large fixtures all ceilinged: plain Opus drops nothing. This escapes that deadlock by
making the *number* of buried requirements a knob (N) and escalating until plain Opus's drop-rate
leaves the ceiling — that scale is where Fable's documented "sustains over length / doesn't drop
the tail" edge should appear. Grading a requirement is O(1), so N can grow cheaply.

The task: build `eventkit` whose registry declares N fields, each with a type and (for ~1/3) a
SPECIAL rule, all stated ONCE in a dense prose paragraph (no clean table) so a tail-dropper loses
some. Deterministic behavioral grader: each field contributes checks (registry-type, parse-coerce,
+ its special rule). buried_rate = fraction of all field-checks satisfied.

ARTIFACT WARNING (see evidence/v1_compressible_registry_sample.py): the v1 generator assigned
types/rules by an index formula (type=TYPES[i%4], rule on i%3). Plain Opus reverse-engineered the
formula and reproduced every field from a 5-line loop, retaining NOTHING, yet scored buried_rate=1.0
— the score measured pattern-recognition, not retention. make_fields below fixes this by drawing each
field's (type, rule) from a seeded PRNG with NO index formula (+ shuffled prose order), so the spec
cannot be regenerated and buried_rate genuinely measures how many independent specs survive to code.

Usage:
  python ladder.py gen  <N> <task_dir>        # emit seed + task.md + key.json
  python ladder.py grade <task_dir> <sub_dir> # -> JSON with buried_rate
  python ladder.py selftest
"""
import json, os, subprocess, sys, random

TYPES = ["int", "str", "float", "bool"]
PYTYPE = {"int": int, "str": str, "float": float, "bool": bool}
SAMPLE = {"int": "42", "str": "hello", "float": "3.5", "bool": "true"}


def make_fields(n, seed=20260705):
    """Deterministic but NON-COMPRESSIBLE: each field's (type, rule) is drawn from a seeded PRNG
    with no index formula, so field f097's type is knowable ONLY by reading f097's spec line.
    (The v1 generator used type=TYPES[i%4] / rule on i%3 — fully compressible; Opus reverse-engineered
    the formula and aced N=120 without retaining anything. That measured pattern-recognition, not
    tail-retention. This version forces genuine prose->code carry of every field.)"""
    rnd = random.Random(seed)
    fields = []
    for i in range(n):
        name = f"f{i:03d}"
        t = rnd.choice(TYPES)
        rule = None
        if rnd.random() < 0.35:            # ~1/3 of fields carry a compatible special rule
            if t in ("int", "float"):
                rule = "positive"          # parse must raise on a negative value
            elif t == "str":
                rule = "upper"             # parse must uppercase the value
            # bool: no special rule (drawn but not applicable)
        fields.append({"name": name, "type": t, "rule": rule})
    return fields


def gen(n, task_dir):
    fields = make_fields(n)
    os.makedirs(os.path.join(task_dir, "seed", "eventkit"), exist_ok=True)
    # --- dense prose spec: every field stated once, scattered, no table ---
    # Present in SHUFFLED order (seeded) so a field's POSITION in the paragraph does not encode its
    # index — the only way to get f097 right is to read the sentence that names f097.
    order = list(fields)
    random.Random(n * 7919 + 13).shuffle(order)
    lines = []
    for f in order:
        s = f"`{f['name']}` is a {f['type']}"
        if f["rule"] == "positive":
            s += " that must be rejected (raise) if its parsed value is negative"
        elif f["rule"] == "upper":
            s += " whose parsed value must be upper-cased"
        lines.append(s)
    dense = "; ".join(lines)
    spec = f"""Build out `eventkit` (in ./seed) into a working structured-event ingestion library.
It has a `registry` that is the single source of truth, a `parse` module, and a `cli`.

The registry's `FIELD_TYPES` must declare exactly these {n} fields, mapping each field NAME to its
real Python TYPE object (not a string label), and `parse.parse_line("k=v k=v ...")` must coerce
each field's value to its registered type. The fields, with their rules, are: {dense}.

Also: define `SCHEMA_VERSION` once in the registry and import it elsewhere; `cli` is a real
argparse CLI with a `version` subcommand that prints it. Add tests and make the suite green.
Leave the built package in ./seed; do not commit.
"""
    open(os.path.join(task_dir, "task.md"), "w", encoding="utf-8", newline="\n").write(spec)
    # --- seed stubs (registry empty; nothing satisfied) ---
    reg = os.path.join(task_dir, "seed", "eventkit")
    open(os.path.join(reg, "__init__.py"), "w").write("")
    open(os.path.join(reg, "registry.py"), "w").write("FIELD_TYPES = {}\n")
    open(os.path.join(reg, "parse.py"), "w").write(
        "def parse_line(line):\n    return dict(t.split('=',1) for t in line.split() if '=' in t)\n")
    open(os.path.join(reg, "cli.py"), "w").write(
        "import sys\ndef main(argv=None):\n    print('eventkit'); return 0\n")
    # --- hidden key ---
    open(os.path.join(task_dir, "key.json"), "w", encoding="utf-8").write(json.dumps({"n": n, "fields": fields}, indent=2))
    return fields


PROBE = r"""
import json, sys
from eventkit import registry as r, parse
f = json.loads(sys.argv[1])
name, typ, rule = f["name"], f["type"], f["rule"]
tobj = {"int": int, "str": str, "float": float, "bool": bool}[typ]
ok_type = r.FIELD_TYPES.get(name) is tobj
sample = {"int": "42", "str": "hello", "float": "3.5", "bool": "true"}[typ]
ev = parse.parse_line(name + "=" + sample)
val = ev.get(name)
ok_coerce = isinstance(val, tobj) and not (typ != "bool" and isinstance(val, bool))
ok_rule = True
if rule == "positive":
    neg = {"int": "-5", "float": "-2.5"}[typ]
    try:
        parse.parse_line(name + "=" + neg); ok_rule = False
    except Exception:
        ok_rule = True
elif rule == "upper":
    ev2 = parse.parse_line(name + "=abc")
    ok_rule = ev2.get(name) == "ABC"
print("PASS" if (ok_type and ok_coerce and ok_rule) else "FAIL")
"""


def _probe(sub, fjson):
    try:
        p = subprocess.run([sys.executable, "-c", PROBE, fjson], cwd=sub, capture_output=True, text=True, timeout=30)
        last = [l for l in (p.stdout or "").strip().splitlines() if l.strip()]
        return bool(last) and last[-1].strip() == "PASS"
    except Exception:
        return False


def grade(task_dir, sub_dir):
    key = json.load(open(os.path.join(task_dir, "key.json"), encoding="utf-8"))
    fields = key["fields"]
    hits = 0
    missed = []
    for f in fields:
        if _probe(sub_dir, json.dumps(f)):
            hits += 1
        else:
            missed.append(f["name"])
    n = len(fields)
    return {"n": n, "satisfied": hits, "buried_rate": round(hits / n, 3), "missed": missed}


def selftest():
    import tempfile, pathlib
    td = tempfile.mkdtemp()
    fields = gen(6, td)
    # build a GOLD submission satisfying all
    reg = pathlib.Path(td) / "gold" / "eventkit"; reg.mkdir(parents=True)
    (reg / "__init__.py").write_text("")
    ftmap = ", ".join(f'"{f["name"]}": {f["type"]}' for f in fields)
    (reg / "registry.py").write_text(f'SCHEMA_VERSION="1.0"\nFIELD_TYPES = {{{ftmap}}}\n')
    rules = {f["name"]: f["rule"] for f in fields}
    (reg / "parse.py").write_text(
        "from eventkit.registry import FIELD_TYPES\n"
        f"RULES = {rules!r}\n"
        "def _b(v): return v.lower() in ('1','true','yes','t')\n"
        "def parse_line(line):\n"
        "    out={}\n"
        "    for tok in line.split():\n"
        "        if '=' not in tok: continue\n"
        "        k,v=tok.split('=',1)\n"
        "        t=FIELD_TYPES.get(k)\n"
        "        if t is None: out[k]=v; continue\n"
        "        cv = _b(v) if t is bool else t(v)\n"
        "        rule=RULES.get(k)\n"
        "        if rule=='positive' and cv<0: raise ValueError('neg')\n"
        "        if rule=='upper': cv=cv.upper()\n"
        "        out[k]=cv\n"
        "    return out\n")
    (reg / "cli.py").write_text("def main(argv=None):\n    return 0\n")
    gold = grade(td, str(pathlib.Path(td) / "gold"))
    seed = grade(td, str(pathlib.Path(td) / "seed"))
    ok = gold["buried_rate"] == 1.0 and seed["buried_rate"] == 0.0
    print(f"{'ok  ' if ok else 'FAIL'} gold buried_rate={gold['buried_rate']} (exp 1.0); seed buried_rate={seed['buried_rate']} (exp 0.0)")
    return 0 if ok else 1


if __name__ == "__main__":
    a = sys.argv
    if len(a) >= 2 and a[1] == "selftest":
        sys.exit(selftest())
    elif len(a) == 4 and a[1] == "gen":
        fs = gen(int(a[2]), a[3]); print(f"generated N={len(fs)} task at {a[3]}")
    elif len(a) == 4 and a[1] == "grade":
        print(json.dumps(grade(a[2], a[3]), indent=2))
    else:
        print(__doc__); sys.exit(2)
