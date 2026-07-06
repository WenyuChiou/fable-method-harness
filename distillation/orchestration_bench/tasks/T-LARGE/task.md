Build out `eventkit` (in ./seed) into a working structured-event ingestion + query library
with a CLI. It is a scaffold today; make it a real, coherent package. Work in ./seed.

Invariants (these hold across the whole package, decide them once and keep them): the field
registry is the single source of truth — it maps each field NAME to its actual Python TYPE
object (not a string label), and the schema version is defined there ONCE as `SCHEMA_VERSION`
and every other part imports it rather than re-stating the string; parsing coerces each value
to its registered type via the registry (a numeric field like `ts` becomes an int, not a
string); a filter on a field that is NOT in the registry must RAISE, never silently treat it
as a non-match; and config loading must strictly REJECT unknown keys (raise), not ignore them.

Now the components. **registry** — the canonical `FIELD_TYPES` for at least `ts` (numeric),
`level` (text), `msg` (text), plus `SCHEMA_VERSION`. **parse** — `parse_line("k=v k=v")` →
dict with values coerced per the registry. **filters** — `match(event, field, value)` per the
invariant above. **config** — `load_config(dict)` per the invariant above. **cli** — a real
argparse CLI with three subcommands: `ingest` (read lines, parse, print count), `query`
(filter parsed events), and `version` (print the schema version). **README** — document all
three subcommands and state the schema version. Add whatever tests you think it needs and make
the suite green. When you're done, leave the built package in ./seed; do not commit.
