# v1 COMPRESSIBILITY ARTIFACT — evidence for DL-20260705-01 / LL-022.
# This is the registry.py a plain-Opus build produced for the N=120 *v1* ladder task,
# whose generator was compressible (type=TYPES[i%4], rule on i%3). The agent
# reverse-engineered the formula into a _build_schema() loop and retained NO individual
# field spec, yet scored buried_rate=1.0. This is why a buried-requirements bench MUST be
# non-compressible; the hardened v2 re-run (random per-field type/rule) still ceilinged
# 15/15 but as genuine literal retention. Full record: ../../distillation-log.md DL-20260705-01.

"""Registry: the single source of truth for eventkit.

This module declares the schema version and, most importantly, ``FIELD_TYPES``:
a mapping of every field NAME to its real Python TYPE object (``int``, ``str``,
``float`` or ``bool`` -- not a string label).

Per-field *special rules* (reject-negative for some numeric fields, upper-case
for some string fields) live alongside the types in ``FIELD_RULES`` so the
``parse`` module can enforce them without re-deriving anything.

Nothing here is guessed at runtime: the tables below are the authoritative,
explicit declaration of the 120-field schema described in the task spec.
"""

# --------------------------------------------------------------------------- #
# Schema version -- defined ONCE here and imported everywhere else.
# --------------------------------------------------------------------------- #
SCHEMA_VERSION = "1.0.0"


# --------------------------------------------------------------------------- #
# Special-rule sentinels.
#
# A field may carry at most one special rule beyond its base type:
#   REJECT_NEGATIVE -- a numeric (int/float) field whose parsed value must be
#                      rejected (ValueError raised) when it is negative.
#   UPPER           -- a str field whose parsed value must be upper-cased.
# --------------------------------------------------------------------------- #
REJECT_NEGATIVE = "reject_negative"
UPPER = "upper"


def _build_schema():
    """Construct the 120-field schema exactly as the spec dictates.

    The spec lays the fields out in a strict period-4 type cycle
    (int, str, float, bool) over ``f00`` .. ``f119`` with two overlaid
    special-rule cycles:

      * numeric reject-negative: every field whose index mod 12 is 4 (an int)
        or 10 (a float) -- 20 fields total.
      * str upper-case: every field whose index mod 12 is 5 (a str) --
        10 fields total.

    We generate from those rules and then assert the resulting counts match the
    spec's stated totals, so a silent drift in the pattern cannot slip through.
    """
    base_cycle = (int, str, float, bool)
    field_types = {}
    field_rules = {}

    for i in range(120):
        name = "f%02d" % i
        base = base_cycle[i % 4]
        field_types[name] = base

        rule = None
        m = i % 12
        if m == 4 or m == 10:
            # m == 4 lands on an int, m == 10 lands on a float -> numeric.
            rule = REJECT_NEGATIVE
        elif m == 5:
            # m == 5 lands on a str.
            rule = UPPER
        if rule is not None:
            field_rules[name] = rule

    return field_types, field_rules


FIELD_TYPES, FIELD_RULES = _build_schema()


# --------------------------------------------------------------------------- #
# Invariants -- fail loudly at import time if the schema ever drifts from spec.
# --------------------------------------------------------------------------- #
assert len(FIELD_TYPES) == 120, "expected exactly 120 fields"
assert list(FIELD_TYPES) == ["f%02d" % i for i in range(120)], "field ordering"
assert all(isinstance(t, type) for t in FIELD_TYPES.values()), \
    "FIELD_TYPES values must be real Python type objects, not string labels"

_type_counts = {}
for _t in FIELD_TYPES.values():
    _type_counts[_t] = _type_counts.get(_t, 0) + 1
assert _type_counts == {int: 30, str: 30, float: 30, bool: 30}, _type_counts

_reject = [n for n, r in FIELD_RULES.items() if r == REJECT_NEGATIVE]
_upper = [n for n, r in FIELD_RULES.items() if r == UPPER]
assert len(_reject) == 20, ("reject-negative count", _reject)
assert len(_upper) == 10, ("upper count", _upper)
# Every reject-negative field must be numeric; every upper field must be str.
assert all(FIELD_TYPES[n] in (int, float) for n in _reject)
assert all(FIELD_TYPES[n] is str for n in _upper)

del _t, _type_counts, _reject, _upper


def field_names():
    """Return the field names in schema order."""
    return list(FIELD_TYPES)


def field_type(name):
    """Return the registered Python type for ``name`` (KeyError if unknown)."""
    return FIELD_TYPES[name]


def field_rule(name):
    """Return the special rule for ``name`` (or ``None`` if it has none)."""
    return FIELD_RULES.get(name)
