---
id: DOC-publication-status
layer: doc
purpose: Publication status + public-safe posture - what the repo's visibility IS (public, verified), the never-include list checked on every commit, and the repeatable public-safety review required before major releases.
read_when: Before any push or release, when a file mentions visibility/privacy posture, and MANDATORY before any major publication event.
depends_on: [HARNESS.yaml, README.md]
used_by: [ROUTE-repo-maintenance, ROUTE-pr-review, SCRIPT-check-adaptive-harness]
tags: [publication, public-safe, security, review-checklist, gitignore]
retrieval_keywords: [publication status, repo public, make public, public safety review, review checklist, secrets, gitignore, publish, privacy policy]
---

# Publication Status and Public-Safety Policy

**Status: PUBLIC** — `github.com/WenyuChiou/fable-method-harness`,
visibility verified via the GitHub API on 2026-07-06. This file supersedes
the former `docs/private_repo_setup.md` ("private remote REQUIRED"), whose
posture the repository's real state had outgrown; an agent must never again
be told the repo is private while it is public. History of the old policy
remains in git.

Binding constraints (`HARNESS.yaml`): `public_safe_after_human_review`,
`no_secrets`, `no_hidden_reasoning`.

## 1. Public-safe posture

- The repo is public; every commit is immediately world-readable. Write
  accordingly — there is no "we'll clean it before the flip" buffer anymore.
- **Public safety review must be repeated before any major publication
  event** (release tag, README relaunch, external announcement): a human
  walks section 3 on the actual tree at the actual candidate commit.
- Generated review reports stay OUT of the repo: `reports/` is gitignored
  because reports can embed telemetry harvested from the operator's local
  `~/.claude` harness (see `.gitignore`).

## 2. Never-include list (checked on EVERY commit)

The following must never appear in this repo, in any file, at any commit:

- Secrets: API keys, tokens, credentials, `.env` contents, auth cookies.
- Personal contact info: phone numbers, personal emails, addresses,
  messaging handles.
- Private chat exports or session transcripts of private conversations.
- Proprietary or private system prompts, and any "hidden internals" of any
  model or agent product.
- Hidden reasoning traces (chain-of-thought) — invented OR captured.
- Local telemetry or scan output from the operator's machine (hook logs,
  settings contents, audit reports) — these live under gitignored paths or
  in the operator's private dotfiles repo, never here.

Everything here must be reconstructable by an observer of the source repo's
public artifacts; if it isn't, it doesn't belong.

## 3. Public-safety review checklist (repeatable)

A human reviewer walks every item on the actual file tree at the actual
candidate commit (not from memory):

- [ ] **Secret scan clean** — automated scanner over full history, not just HEAD.
- [ ] **Never-include sweep** — grep for keys/tokens/emails/phones/chat
      markers; open every hit; zero tolerated.
- [ ] **Provenance audit** — every claim/example/dataset record traces to a
      `source_artifact` or is explicitly marked synthetic.
- [ ] **No hidden-reasoning content** — prompts/ contains only fragments
      reconstructable from observable work orders.
- [ ] **Third-party content check** — no verbatim quoted material beyond the
      source repo's own NOTICE carve-out.
- [ ] **People check** — no identifying details of uninvolved private individuals.
- [ ] **License decided** — a deliberate license file exists.
- [ ] **`.gitignore` intact** — the required ignore set (section 4) present,
      not weakened.
- [ ] **Retrieval smoke test passes** (`docs/retrieval_smoke_test.md`).
- [ ] **Human sign-off recorded** — the release/publication commit names the
      reviewer and checklist date.

Any unchecked box = the publication event halts. Halt is a success.

## Outstanding items ledger (append-only)

- **License: DECIDED — MIT** (human decision 2026-07-06, OPT-20260706-011
  closed): `LICENSE` committed at repo root, plain MIT (the source repo's
  NOTICE carve-out was mhc-specific quoted material; this repo carries none).
- **Full-history secret scan: EXECUTED 2026-07-06** — gitleaks 8.30.1 over
  the complete git history (22 commits, ~1.05 MB scanned): **no leaks
  found** (OPT-20260706-012 closed). Re-run at each future release gate;
  the finding is point-in-time, not perpetual.

## 4. Required `.gitignore`

The repo-root `.gitignore` must contain at least these classes (see the
actual file for exact patterns): secrets/credentials (`.env`, `*.key`,
`*.pem`, `secrets/`, `credentials*`, `*token*`), language/tool caches,
OS junk, local scratch and logs, private local state (`local/`,
`*.local.md`, `private/`), and generated review reports (`reports/`).
Additions are welcome; removals require the section-3 review.
