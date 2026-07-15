# PATCH PROPOSAL — minimal read-only CI workflow (APPLIED 2026-07-14)

Status: **APPLIED 2026-07-14** — user-directed README/visibility upgrade
supplied the human approval this proposal required; the workflow shipped as
`.github/workflows/validate.yml` essentially verbatim (additions: a
timeout-minutes guard and a header comment citing this file). The
integration_check invariant was flipped in the same reviewed change: it now
asserts CI is EXACTLY the single sanctioned read-only workflow
(validate.yml, `contents: read`, no secrets) instead of asserting `.github/`
is absent. Original proposal text below, kept verbatim for the record.

Original status line: proposal-only. Per the standing safety rules, GitHub
Actions changes require human approval / PR; nothing here is active
(`.github/` deliberately does not exist — verified by integration_check row
"no GitHub Actions workflow").

## Why

Local pre-commit gates (2 validators) + 4 test suites are enforced only on
machines with `core.hooksPath` set. A read-only CI run makes the same checks
world-visible on the public repo without granting CI any write capability.

## Proposed workflow (create as `.github/workflows/validate.yml` AFTER human review)

```yaml
name: validate
on: [push, pull_request]
permissions:
  contents: read        # read-only token - CI can never push/modify
jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: python scripts/check_agent_artifacts.py
      - run: python scripts/check_adaptive_harness.py
      - run: python scripts/test_run_ai_review.py
      - run: python scripts/test_run_adaptive_harness_review.py
      - run: python scripts/test_build_harness_graph.py
      - run: python scripts/test_check_agent_artifacts.py
      - run: python validation/retrieval_probe.py
      - run: python scripts/build_harness_graph.py --dry-run
```

Notes: no scheduled trigger (scheduled reviews stay operator-local and
report-only); no secrets; `permissions: contents: read` pins the token.
integration_check.py is EXCLUDED from CI on purpose - its home-telemetry
collectors and ledger-mtime checks are operator-machine-specific.

## Rollback

Delete the workflow file; CI has no state.

## Apply convention

The applying commit should cite this proposal file path (no REC id assigned —
this is infrastructure, tracked here and in the Phase-3 report).
