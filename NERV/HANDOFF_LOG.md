# Handoff log

Newest entries go first. Keep entries concise and link to durable artifacts.

## 2026-08-20 — Codex — Explain current data status in README

**Outcome**

- Added a README current-state summary covering 235 public cases, the 2026-07-29 data cutoff, 179 discovery candidates, the latest review result, and the 2026-08-20 deployment.
- Explained why discovery PRs and deployments do not automatically advance the public data date.
- Documented candidate decision semantics, PR #12's 41-candidate outcome, current RSS/article bias, and five concrete discovery improvements.

**Verification**

- Reconciled all README counts and dates against `data/site.v3.json`, `data/additions.v1.json`, and both discovery ledgers.
- Data validation passed; `git diff --check` passed.

**References**

- [GitHub PR #15](https://github.com/taehyeonglim/2026-esports-landscape/pull/15)

## 2026-08-20 — Codex — Deploy main through repository-owner override

**Outcome**

- Dispatched the audited GitHub Pages repository-owner override for `f5c03ae032a9` after the owner's explicit deployment instruction.
- Kept AC01, usability, design, and browser approval fixtures recorded as pending; the override did not represent them as approved.
- Successfully deployed the complete atomic Pages artifact in run 32314397324.

**Verification**

- Complete release verification, manifest verification, artifact upload, owner-override gate, and Pages deployment all passed.
- Home and research routes returned 200; the contract 404 route returned 404.
- Live JSON and release manifest returned `application/json`; the live `data/site.v3.json` SHA-256 matched the repository file.

**References**

- [GitHub Actions run 32314397324](https://github.com/taehyeonglim/2026-esports-landscape/actions/runs/32314397324)
- [Production site](https://taehyeonglim.github.io/2026-esports-landscape/)

## 2026-08-20 — Codex — Review weekly discovery PR #12

**Outcome**

- Reviewed all 41 new discovery candidates against the current public dataset, source policy, refreshed RSS metadata, and available official sources.
- Classified 22 repeated reports of already represented events/programs as duplicate and rejected 19 out-of-scope or media-only candidates.
- Final candidate ledger: 2 accepted, 97 duplicate, 80 rejected, and 0 needs-review.
- Added no public entries because no candidate-linked new case met the official-source admission standard; `data/site.v3.json` remains at 235 entries.

**Verification**

- Data validation passed for the deterministic 235-entry, 17-region graph.
- JavaScript tests: 26/26 passed.
- Python tests: 119/119 passed.
- `git diff --check` passed.

**References**

- Squash-merged [GitHub PR #12](https://github.com/taehyeonglim/2026-esports-landscape/pull/12) as `3e1a690fd415`.
- [Post-merge run 32313375605](https://github.com/taehyeonglim/2026-esports-landscape/actions/runs/32313375605) passed the complete build and release verification; the human gate failed closed and deployment was skipped because AC01 remains pending.

## 2026-08-16 — Codex — Diagnose the July 29 public data date

**Outcome**

- Confirmed that `자료 반영일` represents the public dataset cutoff sourced from `data/additions.v1.json.updated_at`, not a Git, review, build, or deploy timestamp.
- Confirmed that PR #9 changed only discovery ledgers and admitted no new public entries, so the cutoff remained 2026-07-29.
- Confirmed that the live Pages JSON is byte-identical to the current repository `data/site.v3.json` and contains the same date and 235-entry count.
- Confirmed that the last successful production deployment is [run 30446302924](https://github.com/taehyeonglim/2026-esports-landscape/actions/runs/30446302924) from 2026-07-29; later builds are stopped at the pending AC01 human gate.

**Verification**

- Traced the value through `data/additions.v1.json` → `scripts/extract-data.mjs` → `data/site.v3.json` → `src/app.js`.
- Compared SHA-256 hashes of the live and local `data/site.v3.json`; they match exactly.
- Reviewed Git history for the last public-data change and GitHub Actions history for the last successful Pages deployment.

**Publication path**

- Task branch: `agent/document-data-date`.
- Ready-for-merge [PR #11](https://github.com/taehyeonglim/2026-esports-landscape/pull/11) carries this diagnosis to `main`.

## 2026-08-16 — Codex — Make NERV delivery a mandatory closeout routine

**Outcome**

- Recorded the owner's standing instruction that Codex must not end project work before completing the NERV handoff and commit → push → PR merge → main synchronization routine.
- Added explicit blocked-delivery behavior so authentication, verification, conflicts, human input, and policy gates are reported rather than bypassed.
- Kept the exception limited to purely conversational/read-only turns with no durable project decision; no empty commit is required in that case.

**Verification**

- Reconciled the rule across `AGENTS.md`, `NERV/README.md`, and `NERV/PROJECT_STATUS.md`.
- Preserved the two pre-existing untracked user files and excluded them from delivery scope.

**Publication path**

- Task branch: `agent/enforce-nerv-closeout`.
- Ready-for-merge [PR #10](https://github.com/taehyeonglim/2026-esports-landscape/pull/10) carries this closeout rule to `main`.

## 2026-08-16 — Codex — Establish shared NERV handoff

**Outcome**

- Added the repository-local `NERV/` briefing surface for Codex, Claude Code, and human maintainers.
- Added root `AGENTS.md` so future Codex work refreshes the status and log after material changes.
- Added root `CLAUDE.md` so Claude Code reads NERV at task start and contributes the same handoff on completion.

**Verification**

- Checked that all new relative links resolve to existing repository files.
- Reconciled status figures directly from current JSON data, Git, and GitHub Actions state.
- Confirmed against the official Claude Code memory documentation that project-root `CLAUDE.md` loads at session start and supports `@path` imports.
- Preserved the two pre-existing untracked user files documented in `PROJECT_STATUS.md`.

**Publication**

- Committed and pushed to `main` as [`f473e4bfe3ce`](https://github.com/taehyeonglim/2026-esports-landscape/commit/f473e4bfe3ce18243e5a3f7dce387f124219421e).
- The full build passed in [run 31931308376](https://github.com/taehyeonglim/2026-esports-landscape/actions/runs/31931308376); deployment was skipped at the pending AC01 human gate.

## 2026-08-16 — Codex — Review and merge weekly discovery PR #9

**Outcome**

- Reviewed 101 pending discovery candidates: 50 duplicate and 51 rejected.
- Final candidate ledger: 2 accepted, 75 duplicate, 61 rejected, and 0 needs-review.
- Updated only `data/discovery/candidates.v1.json` and `data/discovery/seen.v1.json`; public site data was unchanged.
- Squash-merged [PR #9](https://github.com/taehyeonglim/2026-esports-landscape/pull/9) to main as `88d9d25a8c75` and removed its automation branch.

**Verification**

- Data validation passed.
- JavaScript tests: 26/26 passed.
- Python tests: 119/119 passed.
- [Post-merge run 31930460697](https://github.com/taehyeonglim/2026-esports-landscape/actions/runs/31930460697) passed the complete build/release verification and artifact upload.

**Blocked release state**

- Production deploy was skipped because AC01 human approval remains pending. This was the intended fail-closed policy result.

---

## Entry template

```markdown
## YYYY-MM-DD — Agent/person — Short task name

**Outcome**

- What was completed and where.

**Verification**

- Exact tests, checks, or external-state confirmation.

**Remaining / blocked**

- Concrete next work or named blocker. Omit when none.

**References**

- Commit, PR, run, issue, or canonical file links.
```
