---
id: L4-progressive-disclosure-policy
layer: context
purpose: The rules for how much of this repo to load, and the exceptions
read_when: Tempted to read beyond the routed file list, or unsure whether full-context load is justified
depends_on: [context/L3_task_router.md, ROUTES.yaml]
used_by: [ROUTE-phase-review, ROUTE-tool-discovery, ROUTE-pr-review, ROUTE-eval-design, ROUTE-memory-update, ROUTE-runtime-export, ROUTE-repo-maintenance, ROUTE-ab-test-design]
tags: [progressive-disclosure, context-budget, loading-policy]
retrieval_keywords: [progressive disclosure, how much to read, full context load, context budget, escalation, when to read everything]
---

# L4 — Progressive Disclosure Policy

Context is a budget. The source project's own runtime contract works the
same way (its packages route every command through one canonical `SKILL.md`
that pointers "read and defer to … never duplicate"); this harness applies
the identical discipline to itself.

## The five rules

1. **Always enter through L0.** Every session starts at
   `context/L0_bootstrap.md`, then L2, then L3. Never begin a task by
   globbing or reading the repo tree wholesale.

2. **Route-scoped loading only.** After L3 classification, load exactly
   the files listed for the chosen route — preferably in ONE call via
   `scripts/route_pack.py <task_type>` (entry-only: `route_show.py` or a
   grep of that route's `- id:` block), never a wholesale Read of
   `ROUTES.yaml`. A file not on the route list is presumed
   irrelevant until proven otherwise. The same grep-entry rule applies to
   `INDEX.yaml`: grep the path or a retrieval keyword and read only the
   matched entry; the whole-file read (~23.5k tokens) is reserved for
   `scripts/index_diff.py`, which does the mechanical MT-5 sweep for ~0.

3. **Escalate one layer at a time, with a stated reason.** Only open a
   deeper layer (rubric → playbook → example → dataset record) when the
   current layer is demonstrably insufficient for the decision at hand,
   and say in one line WHY before opening it. Silent over-reading is the
   context analogue of a silent pass.

4. **Datasets are retrieval-by-ID, never bulk reads.** `TE-###`, `FM-###`,
   `EC-###`, `RE-###` records are looked up by grepping the stable ID or
   the frontmatter `retrieval_keywords` — never by reading a whole JSONL
   file into context. If codebase-memory indexing is available, prefer it
   (`docs/codebase_memory_indexing.md`), but treat results as advisory and
   verify load-bearing hits by opening the specific record.

5. **Stay inside the current phase.** L2's allowed/forbidden list bounds
   every route. A task that requires forbidden-phase material is a HALT
   (report which gate blocks it), not a reason to read more files hunting
   for permission.

## When full-context load IS allowed

Three sanctioned exceptions — each mirrors an observable practice in the
source repo:

1. **Architecture review.** A deliberate whole-system adversarial review
   (the precedent: the 2026-07-01 four-lens design review read the entire
   spec and produced 34 findings). Declare the review up front; the
   output must be a findings document, not ad-hoc edits.

2. **Release review.** Before any release-grade event (version bump,
   public flip, standard revision) — the precedent is the source repo's
   pre-release discipline: full test suite + validate on all packages +
   reviewer round before shipping. Reading everything to verify
   consistency is correct here; skipping it is the violation.

3. **Unresolved ambiguity.** When the routed files plus one recorded
   escalation still leave the decision ambiguous, widening the read is
   allowed — AFTER stating what was loaded, what question remains, and
   why the route list did not answer it. Record the gap afterwards via
   `ROUTE-memory-update` (a friction report), so the route list improves
   instead of the exception becoming the norm.

## Anti-patterns

- Reading `L5_full_context_map.md` as a table of contents to walk every
  directory "for background". L5 is a map for targeted lookup only.
- Loading multiple routes' file lists "just in case" for a single task.
- Re-reading files already summarized in the conversation instead of
  trusting the summary + spot-checking the load-bearing line.
- Treating rule 3's one-line reason as boilerplate — if the reason is
  "for completeness", stop; that is not a reason.
