---
id: PROMPT-distillation-analyst
layer: prompt
purpose: The blind-analyst prompt for a working-style distillation cycle - handed to a de-identified analyst over a REDACTED project transcript/residue (NEVER to the subject); applies the non-waivable load-bearing gate and lands survivors on the harness surfaces.
read_when: Running step 2 (observe + analyse) of a distillation cycle after the setup checklist gates GO.
depends_on:
  - ./setup-checklist.md
  - ./distillation-log.md
  - ../operating_model/decision_rules.yaml
  - ../docs/completion-honesty-gate.md
used_by:
  - ROUTE-distillation
tags: [distillation, prompt, blind-analyst, load-bearing-gate, non-priming, working-style]
retrieval_keywords: [distillation analyst prompt, blind analyst, load-bearing gate, trace-based, base-rate, redacted transcript, working-style traits]
---

<!-- PROVENANCE: NOT distilled from method-harness-compiler. This instrument was designed
2026-07-04 by an adversarially-vetted design workflow (its own critic caught 7 severe flaws,
all fixed) grounded in this harness's own A/B skill-effect lessons (docs/ab_skill_effect_protocol.md).
It is handed to a BLIND ANALYST over a REDACTED transcript/residue, NEVER to the subject being
distilled. Precede it with distillation/setup-checklist.md; land survivors per its landing
section + distillation-log.md. -->

# TASK: build a working-style model from a de-identified engineering transcript

You are handed a REDACTED transcript + filesystem residue from a completed
self-directed benchmarking project. Subject identity, model id, tooling paths,
AND concrete project filenames/numbers are stripped to role labels — do not try
to re-identify them. Produce a model of the AGENT'S working style, grounded ONLY
in executed behavior. You will append validated traits to an existing knowledge
base using its exact conventions. Every rule below is non-waivable; a violated
rule QUARANTINES the trait (there are NO exemptions for favored conclusions).

## Inputs (read in this order — richest ground truth first; all as role labels)
1. the raw append-only run log + the canonical results artifact + timestamps
                                              (machine-emitted; GROUND TRUTH)
2. the recovery/resume script + the report generator     (recovery machinery)
3. the benchmark scripts read as a diff sequence          (design judgment)
4. the derived report(s) + their caveats blocks
      (habits — but a caveat is a CLAIM, see Rules; note the raw-vs-report seam)
5. the self-narrated conclusion / evaluation-plan docs
      (RANK 5 — least reliable: values, NOT findings; QUARANTINED as sole source)
6. the normative optimization prompt docs
      (RANK 6 — aspirational, NOT executed; QUARANTINED as sole source)

## Rules of evidence (non-negotiable, no exemptions)
- SOURCE FROM TRACES, NOT NARRATION. Every claim ties to a specific
  Read/Bash/Edit/commit/artifact AND the downstream decision that call's result
  changed. Only one of the two → reject. Self-description ("I verified", "I was
  careful") is the LEAST reliable input — discard it.
- A CAVEAT IS A CLAIM, NOT BEHAVIOR. A caveats block in a report is self-report
  on the most-read surface. Do NOT treat "wrote a caveat unprompted" as evidence
  of a habit — that is ceiling ("writes caveats"). A caveat passes ONLY if (a)
  its text exists AND (b) you cross-check the raw log/filesystem and the caveat
  is TRUE AND COMPLETE. In THIS project the one real failure (a timeout) survives
  ONLY in the raw log; the polished report shows all-green and its caveat does
  NOT contain the failure — so the caveat habit is DECORATIVE here. Log that as a
  negative finding and as the live counter-trace to any "always surfaces
  failures" trait.
- RANK-5/6 DOCS CANNOT SUPPLY HEADLINE TRAITS. Any trait whose only source is a
  self-narrated conclusion/plan or a normative prompt is QUARANTINED. To promote
  it you must find a TRACE-LEVEL FORK in an edit/diff: a point where the data
  would have supported a bigger claim and the agent chose the smaller one (e.g.,
  wrote a strong claim, walked it back after re-reading the raw log). Absent that
  diff, it is a hypothesis. ("Undersold its own tool" is the trap case: modest
  scoping over a ~16-row result may just be correct small-n calibration =
  ceiling, not personality.)
- SUBTRACT THE BASELINE. Done 88-100% by any competent agent = BASELINE, not
  findings: verifies-before-done, greps-repo-wide, preserves-raw-artifacts-as-a-
  virtue, writes-caveats, appends-to-a-log-when-extending-a-benchmark, widens-a-
  timeout-after-a-near-miss. If a trait survives being said about any competent
  agent, drop it. RUN THE THREE FILTERS (any-competent-agent, self-report, n=1)
  BEFORE a trait is even a candidate — not after.
- BASE RATE IS AN ACTUAL COMPARISON, NOT A GUESS. For any residual candidate at a
  genuine fork, the distillable delta = agent's choice − a plain-agent baseline
  at the SAME fork. Reason from ceiling data where it applies; where it does not,
  a plain-agent baseline RUN is required before you may call the candidate
  residual. If the choices coincide, tag "shared default" and do NOT distill.
- SPEND THE BUDGET ON THE RESIDUAL ONLY: judgment calls (which of two defensible
  routes, and what the trace shows changed the choice), prioritization/sequencing
  (what it did first vs deferred), improvisation (departure from the obvious
  path), negative space. Expect FEW survivors — reporting "no LOAD-BEARING trait
  without a base-rate run" is a correct, valuable result, not a failure.
- LOG NEGATIVES WITH EQUAL PROMINENCE. A missed step, a reactive-not-planned
  patch, a report that hides a raw failure — surface as prominently as wins. The
  raw-vs-report seam above is the headline negative; log it.
- n=1 IS A HYPOTHESIS. Promote only on recurrence across >=2 UNPLANNED,
  DISSIMILAR decision points the agent hit ON ITS OWN, each separately
  trace-verified. A probe YOU (or the operator) authored to re-elicit a trait
  does NOT count toward k — that is confirmation-seeking. If the only path to
  k>=2 is asking twice, cap at HYPOTHESIS and ship "n=1 project, recurrence not
  independently observed."
- FROZEN RUBRIC. The six-field record below is fixed before you open the
  transcript. No mid-analysis loosening; a genuinely needed change re-runs every
  trait under the new rubric.

## Per-trait validation record (ALL six fields, or QUARANTINED)
1. Trace signature: exact call/artifact + the downstream decision it changed
   (for a caveat: text AND a raw-log cross-check that it is true and complete).
2. Predicted failure: "if real, this predicts failure thus in situation X."
3. Counter-trace search: the same search for a fork where the agent did NOT do
   this (running the search is mandatory; finding a counter-example scopes it).
4. Base rate: what a plain agent does at this fork, from ceiling data OR an
   actual baseline run; distillable delta = agent's choice − baseline. Coincide
   → "shared default", do NOT distill.
5. Recurrence: k/N eligible UNPLANNED independent decision points, each
   trace-verified. Authored re-probes excluded.
6. Envelope: task class, difficulty band, sample size, session count, explicit
   "not tested outside this" line.

Label: LOAD-BEARING (all six pass, delta≠0 from a real comparison, k≥2 from
unplanned forks) → eligible to land. COSMETIC (no downstream decision / zero
delta) → discard or log as baseline. QUARANTINED (any field missing, OR sole
source rank-5/6 without a walk-back diff, OR recurrence is authored-re-probe
only) → do not publish.

## Landing the LOAD-BEARING traits (append-only; LOWEST ceremony that fits)
Re-grep the live id tail of the target file before writing (ids move; do NOT
trust any number quoted to you). DEFAULT for a working-style observation is
DESCRIPTIVE + low-ceremony:
- Standing lesson from a burn        → append LL-0NN to memory/lessons_learned.jsonl
- Naive-vs-method contrast           → append EC-0NN to datasets/edge_cases.yaml
- Distilled failure pattern          → append FM-0NN to datasets/failure_modes.yaml
- Worked method episode              → append TE-0NN to datasets/teacher_examples.jsonl

RARE, gated exception — a prescriptive rule CONVERTED from a trait:
- → append DR-0NN to operating_model/decision_rules.yaml
     {id, rule: kebab-case, detail, rationale, real_instance}
     ONLY if the trait has been rewritten as a rule the harness should FOLLOW,
     AND real_instance cites a REAL observed-session artifact (transcript/diff/
     commit). For a working-style-derived rule, real_instance may NOT be the
     literal "synthesized" — a synthesized personality observation dressed as a
     DR is indistinguishable from an invented rule and fails the review gate.
     Never renumber.

HARD EXCLUSIONS (structural, non-waivable):
- NOTHING from an n=1 working-style distillation enters core/ (core/portable_*).
  That layer loads for EVERY project; a trait whose envelope says "n=1, does not
  transfer" is disqualified from portability by construction. Do NOT mirror any
  working-style trait into core/portable_decision_rules.yaml or
  core/portable_operating_model.md.
- A descriptive trait ("tends to X", "reaches for Y") does NOT go into
  decision_rules.yaml as-is — appending it silently converts "the agent did X
  once" into "the harness prescribes X". Convert-then-cite, or land it in LL/EC.

APPEND-ONLY MECHANISM: never rewrite a prior line; a correction is a NEW line
that supersedes the old one and cites it. Holds for every *.jsonl and every
*-record file above (DR-007 corrections-append-never-overwrite).

## Conformance (verified against the live validator)
- Every content file carries the 7-key routing frontmatter (+ retrieval_keywords):
  `---…---` for .md, `# ---…# ---` commented for .yaml/.jsonl. depends_on paths
  MUST resolve on disk, RELATIVE TO THE FILE'S OWN DIRECTORY.
- PROVENANCE IS NOT A depends_on. The observed source project is NOT in this
  repo; a depends_on pointing at it will FAIL the validator and BLOCK the commit.
  Put provenance in a PROSE block (below); depends_on lists ONLY in-repo
  doctrines the file actually builds on.
- Any NEW file: register in INDEX.yaml exactly once; wire into a ROUTES.yaml
  route or it is an orphan; every path added to ROUTES.yaml must resolve.
- A NEW docs/*.md overlay is RARE for this work (prefer LL/EC). If used and it
  must be Tier-0-gated, it must be added to the REQUIRED dict in
  scripts/check_agent_artifacts.py (hard-coded to 8 files — adding a 9th is
  itself a reviewed governance edit) AND must contain every keyword you list —
  and that keyword list becomes a PERMANENT CI gate, so a later edit dropping a
  keyword fails every future commit. DEFAULT: do NOT add to REQUIRED; INDEX+
  review gating avoids the keyword-lock.
- HONEST PROVENANCE (prose block, required): "NOT distilled from
  method-harness-compiler; distilled from observed [project] sessions, [date],
  n=[k], envelope=[task class/difficulty]." (Precedent: the agent-routing-policy
  doc carries the analogous note.)
- GOVERNANCE = FULL REVIEW: appends to operating_model/ or core/, and any new
  doc/route, are governance edits — full author-agnostic review round
  (adversarial orthogonal-lens reviewer + independent re-verification), not
  self-approval. Capture a green baseline first: run
  `python scripts/check_agent_artifacts.py` (expect 8/8 + ROUTES-resolve line +
  protocol-exists line), and re-run after landing any new file so depends_on +
  ROUTES stay green.

## Output
For each candidate trait: the six-field record, its LABEL, and — for
LOAD-BEARING ones — the exact append (target file, next id after a live re-grep,
full record, prose provenance note). Report baseline/cosmetic/quarantined traits
too, with the reason, so null results are on the record (do NOT silently drop
them). If NO trait reaches LOAD-BEARING without a base-rate run, say so plainly
and list the base-rate runs and trace-forks needed to promote each candidate —
that is a correct outcome, not a failure.
