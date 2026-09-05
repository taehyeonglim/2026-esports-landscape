# Project status

- Last updated: **2026-09-05 KST**
- Maintainer handoff: **Codex**
- Canonical branch: **main**, verified remote base **6dd9ae1** before this implementation.
- Implementation branch: **agent/review-workbench**; delivery in progress.

## Product and data

- Static HTML/CSS/ES modules and GitHub Pages remain the public architecture.
- Public data remains **235 entries / 17 regions / 235 sources**, cutoff **2026-07-29**.
- All 235 operational statuses remain `needs_review`. No automated fact approvals or public status changes were made.
- The immutable 230-entry baseline and 5 legacy additions are preserved.
- Approved reviews/admissions now persist through deterministic extraction via `data/approved-reviews.v1.json` (currently empty).
- Corrections require prior-record hashes; new admissions require unused IDs, official evidence, and explicit human approval. PII and registered publisher/domain checks run before projection.
- Public detail shows review reasons/dates; URL-compatible evidence-review filtering distinguishes confirmed and due cases without erasing historical status.

## Local review operation

- Start: `PYTHONPATH=src python3 -m esports_data.cli admin --reviewer owner-reviewer`.
- Loopback-only API with session token/Origin checks; atomic candidate decisions and replay-safe approval commands in SQLite.
- Private database: `artifacts/workbench/reviews.sqlite3`; **235 unapproved drafts** and per-entry source-check results are prepared locally.
- The existing 179 candidate decisions are imported idempotently. Main's ledger remains 2 accepted / 97 duplicate / 80 rejected / 0 pending.
- Existing unrelated discovery **PR #16** remains open; it was not merged or reclassified by this implementation.
- Export creates a proposal bundle and hash manifest in `artifacts/workbench/export`; it does not publish or authorize `publish`.
- Existing subject/claim snapshot publication remains a distinct protected path. Do not claim site-review exports are snapshot publication receipts.

Canonical guide: [`../docs/review-workbench.md`](../docs/review-workbench.md).

## Rollout evidence and remaining work

Source reachability checks, not fact verification:

- Pilot: 30 entries; 7 with at least one fetched source, 23 unavailable through the sampled registered URLs.
- Whole corpus: 235 entries; 153 with at least one fetched source, 82 unavailable; 115 unique URLs attempted, 87 fetched.
- Up to 3 registered URLs per entry were checked; HTTP success does not confirm relevance or current operation.
- Six additional institutional discovery surfaces: five accessible, one failed; zero-link results are not evidence of absent activity.
- All checks produced reason codes and a next review date of 2026-12-04. **Human fact reviews completed: 0**.
- Complete the pilot's actual official-source/fact reviews, then the remaining 205. The original plan's human-review rollout is pending, not completed.
- Data gaps (109) and unresolved geographic scope (45) have not been adjudicated in this implementation.

Durable aggregate: [`../reports/review-rollout.v1.json`](../reports/review-rollout.v1.json). Raw documents, temporary titles, tokens, and personal information are excluded.

## Verification

Final local `npm run verify:release` passed:

- JavaScript: **30/30**.
- Python: **129/129**.
- Static contracts: **6/6**, including exclusion of private administration files.
- Public browser matrix: **110/110** across desktop Chromium/Firefox/WebKit and Android/iOS profiles.
- Local administrator browser scenario: **1/1**, including explicit approval, restart persistence, mobile width, unauthorized API and private-file rejection.
- Independent extraction, immutable baseline invariants, release hash reproducibility, input-only provenance changes, and output-mutation detection passed.
- `git diff --check` passed. Existing user files were preserved.

## Release gates

- Resource map and repository-owner release approval: recorded approved.
- AC01, usability, design, and browser-matrix human approval records: still pending.
- No owner override was invoked. A pending human gate must be reported as deployment blocked, even if all automated checks pass.
- Last recorded successful deployment remains the 2026-08-20 owner-authorized run [32314397324](https://github.com/taehyeonglim/2026-esports-landscape/actions/runs/32314397324); no new deployment is claimed here.
- This implementation's remote CI/merge outcome will be recorded during delivery closeout.

## Workspace note

Preserve the pre-existing untracked user files `data/site.v3 2.json` and `migrations/v2-to-v3 2.json`. They are not canonical inputs and are excluded from task commits.

Private runtime state under `artifacts/workbench/` is intentionally not published. Back it up privately before deleting artifacts; its unapproved drafts and source-check observations are not reconstructed from the public site JSON alone.
