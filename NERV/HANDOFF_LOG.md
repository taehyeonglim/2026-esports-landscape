# Handoff log

Newest entries go first. Keep entries concise and link to durable artifacts.

## 2026-09-05 — Codex — Fix defects found by the first real Astra review

**Outcome**

- PR #19 merged as `894488c`; scheduler installed with local credentials and signing key, public key registered in GitHub. First actual Astra review rejected the release and correctly produced no deployment dispatch.
- Addressed three concrete findings: review-filter reset, stale research typology counts, and missing case-level evidence limitations. Improved screenshot readability and added regressions.

**Verification**

- Complete local release gate passed: 42 JS, 131 Python, 6 static, 115 public-browser, 1 administrator, reproducible hashes.
- Push CI 33967255150 passed build and skipped deployment as designed.

**Remaining work**

- Merge this fix, update the local coordinator, and obtain a new model verdict. No new successful deployment is claimed yet.

**References**

- [Automation PR #19](https://github.com/taehyeonglim/2026-esports-landscape/pull/19)
- [AI release operation](../docs/astra-release.md)

## 2026-09-05 — Codex — Add owner-delegated GPT-6 Astra release gate

**Outcome**

- Implemented local GPT-6 Astra review and signed release dispatch, a trusted Actions verification gate, and macOS scheduler installer. Preserved human study fixtures and all factual review statuses.
- AI review authority is explicit in policy; no fallback approval on model, test, signature, or artifact failure. Credentials and signing key stay local.

**Verification**

- Actual Astra CLI structured-output probe succeeded. Complete release suite passed (41 JS, 129 Python, 6 static, 110 public browser, 1 administrator); two new runner fail-closed tests and workflow checks passed, as did updated reproducibility checks.

**Remaining work**

- This pre-merge snapshot does not claim deployment. Merge, local scheduler installation, real model assessment and Pages readback follow.
- Original workspace copies and unrelated discovery PR #16 are preserved.

**References**

- [AI release operation](../docs/astra-release.md)
- [Release policy](../config/astra-review-policy.v1.json)

## 2026-09-05 — Codex — Deliver review workbench and preserve workspace copies

**Outcome**

- Committed implementation as `77bd4fc`, pushed and squash-merged [PR #17](https://github.com/taehyeonglim/2026-esports-landscape/pull/17) as `116a5e2`; synchronized local main with origin/main and deleted the merged implementation branch.
- Preserved 22 untracked numbered copies observed after synchronization, including 13 extra GeoJSONs. Their origin is unverified. Use a clean checkout rather than in-place extraction until the copies are reconciled.

**Verification**

- Final complete local release gate passed (30 JavaScript, 129 Python, 6 static, 110 public-browser, 1 administrator scenarios and reproducible release hashes).
- Post-merge data validation and 30 JavaScript tests passed in a clean checkout of `116a5e2`.

**Remaining work**

- Human fact review of the 30-case pilot and remaining 205 cases remains pending. Link reachability and unapproved drafts are not fact approvals.
- Remote run 33965821923 passed build/full verification, failed the AC01 human approval gate (`AC01 human approval is not approved`), and skipped deploy. No owner override was invoked.

**References**

- [Implementation PR #17](https://github.com/taehyeonglim/2026-esports-landscape/pull/17)
- [Implementation CI run](https://github.com/taehyeonglim/2026-esports-landscape/actions/runs/33965821923)

## 2026-09-05 — Codex — Implement the local review and refresh workbench

**Outcome**

- Added deterministic approved corrections/admissions, registered official-source and PII checks, local SQLite review UI/API, proposal export, conservative event suggestions, and six institutional discovery surfaces.
- Added public review-date disclosure and shareable evidence-review filtering. Preserved all 235 public statuses and the existing data cutoff.
- Prepared 235 unapproved local drafts from bounded source checks. 153 entries had a fetched source; 82 require alternative source retrieval. These are not completed human fact reviews.

**Verification**

- Complete release verification passed: JavaScript 30, Python 129, static contracts 6, public browser scenarios 110, administrator scenario 1. Reproducible extraction/build/hash checks and diff hygiene passed.
- Existing untracked user files and unrelated discovery PR #16 were preserved.

**Remaining work**

- Deliver implementation branch through PR merge and record remote CI. Human fact review of the pilot and remaining entries is pending. Existing human deployment approvals remain pending; no override or successful deployment is claimed.

**References**

- [Review operations](../docs/review-workbench.md)
- [Rollout aggregate](../reports/review-rollout.v1.json)

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
