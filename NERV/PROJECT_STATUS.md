# Project status

- Last updated: **2026-08-16 15:17 KST**
- Maintainer handoff: **Codex**
- Branch: **main**
- Latest product/data commit: **88d9d25a8c75** (`data: weekly source discovery (#9)`)
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

PR #9 was reviewed and squash-merged on 2026-08-16.

- Candidate ledger (`data/discovery/candidates.v1.json`): **138 total**
- Accepted: **2**
- Duplicate: **75**
- Rejected: **61**
- Needs review: **0**
- The weekly discovery workflow remains scheduled for Monday 09:00 KST.
- Discovery never mutates `data/site.v3.json` automatically; accepted publication additions require a separate human-reviewed change.

Durable reference: [GitHub PR #9](https://github.com/taehyeonglim/2026-esports-landscape/pull/9)

## Verification baseline

Latest verified baseline, 2026-08-16:

- Data validation: passed for the deterministic 235-entry, 17-region graph.
- JavaScript unit tests: **26/26 passed**.
- Python tests: **119/119 passed**.
- Post-merge GitHub Actions build: dependency setup, Playwright installation, complete release verification, manifest verification, Pages configuration, and artifact upload all passed.
- The deployment job was skipped because the recorded **AC01 human approval is pending**. The workflow's final conclusion is therefore failure by policy, not a build or data regression.

Durable reference: [GitHub Actions run 31930460697](https://github.com/taehyeonglim/2026-esports-landscape/actions/runs/31930460697)

## Release and approval state

- `data/resource-map.v1.json`: approved.
- Repository-owner release approval: approved.
- AC01 human approval: pending.
- Usability approval: pending.
- Design approval: pending.
- Browser-matrix approval record: pending.
- Production deployment must remain blocked until the recorded human gates are satisfied or the repository owner explicitly performs the audited manual override path.
- The current main-only discovery change does not alter public site content.

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
