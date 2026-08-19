# Project status

- Last updated: **2026-08-20 KST**
- Maintainer handoff: **Codex**
- Canonical branch: **main**
- Latest product/data commit: **3e1a690fd415** (`data: weekly source discovery (#12)`)
- Latest coordination commit: **f5c03ae032a9** (`docs: close out discovery review (#13)`)
- Remote state at update: **main matches origin/main**

## Mission

Build and operate an evidence-centered static website for searching and comparing public information about school esports across South Korea's 17 first-level regions, while keeping collection, review, privacy, lineage, and publication fail-closed.

## Current product and data

- Static HTML/CSS/ES-module frontend deployed through GitHub Pages.
- Search-first workspace, advanced filters, shareable URL state, desktop/mobile detail views, regional map, 17-region comparison matrix, and research/methodology page are implemented.
- `data/site.v3.json`: schema v3, **235 public entries**, **17 regions**, and **235 source records**.
- Public entry lineage: **230-entry immutable v2 baseline + 5 reviewed additions**.
- All 235 public entries still have `operational_status=needs_review`; confidence does not replace operational verification.
- Current known evidence gaps: **109** `data_gaps` records and **27** `negative_evidence` records.

Canonical references:

- Product and commands: [`../README.md`](../README.md)
- Public-data contract: [`../docs/data-contract.md`](../docs/data-contract.md)
- Source and minor-data policy: [`../docs/source-policy.md`](../docs/source-policy.md)
- Operations and release gates: [`../docs/operations.md`](../docs/operations.md), [`../docs/pages-release.md`](../docs/pages-release.md)

## Discovery queue

PR #12's 41 new candidates were reviewed and squash-merged on 2026-08-20. Existing-event coverage was classified as duplicate; candidates outside scope or lacking a specific official source were rejected rather than admitted from media coverage alone.

- Candidate ledger (`data/discovery/candidates.v1.json`): **179 total**
- Accepted: **2**
- Duplicate: **97**
- Rejected: **80**
- Needs review: **0**
- The weekly discovery workflow remains scheduled for Monday 09:00 KST.
- Discovery never mutates `data/site.v3.json` automatically; accepted publication additions require a separate human-reviewed change.
- No new public entry was admitted in this review because the apparently new local cases lacked a candidate-linked official source meeting the repository's admission standard. The public dataset remains at 235 entries.

Durable reference: [GitHub PR #12](https://github.com/taehyeonglim/2026-esports-landscape/pull/12)

## Public data date semantics

- The UI's `자료 반영일 2026.07.29` is the public dataset cutoff, not the latest Git commit, discovery review, build, or deployment time.
- `scripts/extract-data.mjs` copies `data/additions.v1.json.updated_at` into `data/site.v3.json.meta.data_updated_at`; `src/app.js` renders that value without modification.
- The live Pages JSON and the current repository `data/site.v3.json` are byte-identical and both contain `data_updated_at=2026-07-29` with 235 entries.
- PR #9 changed only the discovery candidate and seen ledgers. It admitted no new public entries, so it correctly did not advance the public data cutoff.
- The latest successful production deployment is the 2026-08-20 repository-owner override run from commit `f5c03ae032a9`. The override deployed after the complete automated release verification without claiming that pending study approvals were complete.

Durable references: [live public JSON](https://taehyeonglim.github.io/2026-esports-landscape/data/site.v3.json), [successful Pages run 32314397324](https://github.com/taehyeonglim/2026-esports-landscape/actions/runs/32314397324)

## Verification baseline

Latest verified baseline, 2026-08-20:

- Data validation: passed for the deterministic 235-entry, 17-region graph.
- JavaScript unit tests: **26/26 passed**.
- Python tests: **119/119 passed**.
- Weekly discovery candidates: **179 total, 0 needs-review**.
- PR #12 post-merge GitHub Actions build: dependency setup, Playwright installation, complete release verification, manifest verification, Pages configuration, and artifact upload all passed.
- The deployment job was skipped because the recorded **AC01 human approval is pending**. The workflow's final conclusion is therefore failure by policy, not a build or data regression.

Durable reference: [GitHub Actions run 32313375605](https://github.com/taehyeonglim/2026-esports-landscape/actions/runs/32313375605)

The coordination-only commit `f473e4bfe3ce` also passed the full build job in [run 31931308376](https://github.com/taehyeonglim/2026-esports-landscape/actions/runs/31931308376); its deployment was likewise skipped at the pending human gate.

## Release and approval state

- `data/resource-map.v1.json`: approved.
- Repository-owner release approval: approved.
- AC01 human approval: pending.
- Usability approval: pending.
- Design approval: pending.
- Browser-matrix approval record: pending.
- Production deployment must remain blocked until the recorded human gates are satisfied or the repository owner explicitly performs the audited manual override path.
- The current main-only discovery change does not alter public site content.
- On 2026-08-20 the repository owner explicitly invoked the audited `workflow_dispatch` override for `f5c03ae032a9`. Build, release verification, override validation, artifact upload, and Pages deployment all passed in run 32314397324.
- Post-deploy smoke checks passed for the home page, research page, JSON and manifest content types, and the expected 404 response. The live `data/site.v3.json` is byte-identical to the repository copy.

## Agent closeout routine

The repository owner requires project sessions to finish with a durable NERV handoff and completed delivery:

1. Verify the change.
2. Update NERV status and handoff log.
3. Commit task-owned files on a task branch.
4. Push, open the PR, and merge it to `main`.
5. Synchronize local `main`, verify remote parity, and record CI/release state.

Commit-only, branch-only, push-only, and open-PR-only states are not normal completion. If a real blocker prevents delivery, it must be recorded in NERV and reported without bypassing protections.

## Next priorities

1. Continue the weekly discovery cycle and review any new queue without admitting media-only or policy-ambiguous evidence.
2. Independently re-check the operational status of the 235 public entries, prioritizing high-impact and stale sources.
3. Reduce the 109 documented data gaps and resolve the 45 entries whose geographic scope remains unknown.
4. Complete and record AC01, usability, design, and browser-matrix human reviews before the next intended production deployment.
5. Update pinned GitHub Actions that still emit the Node.js 20 deprecation warning before it becomes a hard compatibility issue.

## Workspace note

At this update, the main worktree contains two pre-existing untracked user files:

- `data/site.v3 2.json`
- `migrations/v2-to-v3 2.json`

They are not canonical project inputs. Preserve them and do not delete, overwrite, stage, or treat them as generated truth without explicit owner direction. `AGENTS.md`, `CLAUDE.md`, and `NERV/` are the tracked coordination surface for future agents.
