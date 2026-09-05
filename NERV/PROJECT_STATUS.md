# Project status

- Last updated: **2026-09-05 KST**
- Maintainer handoff: **Codex**
- Canonical branch: **main**.
- Latest implementation commit: **116a5e20fa17cb9ee2d220ecb2d7c89bbcf044ee**, squash-merged through [PR #17](https://github.com/taehyeonglim/2026-esports-landscape/pull/17).
- Implementation was committed as `77bd4fc`, pushed, merged, and local main synchronized with origin/main; the merged implementation branch was deleted.

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
- Post-merge validation and JavaScript tests passed again in a clean detached checkout of `116a5e2`.

## Release gates

- Owner instruction on 2026-09-05 delegates release assessment to **gpt-6-astra**, high reasoning. Signed AI approval replaces the mandatory human-study gate for this route; individual fact review and protected snapshot publication remain distinct.
- Implementation on `agent/astra-release`, based on canonical main `52acdfbff03e71f4555c5d14ef7c1c034b351ec2`; commit/merge and first AI deployment are pending at this snapshot.
- [AI release guide](../docs/astra-release.md): local authenticated Codex runner, 15-minute macOS polling, full verification and screenshots, seven-check structured verdict, Ed25519 receipt, exact source/artifact/policy binding, independent Actions rebuild and verification, live readback.
- Model availability was verified by an actual local `gpt-6-astra` structured-output execution. No API key or ChatGPT credential is transferred to GitHub.
- New local gate passed: JavaScript **41**, existing Python **129**, static **6**, public-browser **110**, administrator **1**, reproducible hashes. Two additional runner failure/rejection tests and eight workflow contracts passed; malformed/tampered/expired/wrong-model/wrong-build approvals are rejected.
- Human AC01/usability/design/browser fixtures remain pending and unchanged. No owner override is invoked by the AI coordinator.
- Earlier human-gated run 33965821923 failed AC01 and skipped deployment. It remains historical evidence, not the outcome of this new policy.
- Next: merge implementation, register the public verification key, install the local scheduler, obtain a genuine model verdict and confirm the resulting Pages deployment. The Mac must remain awake/online with valid local Codex and GitHub sessions.

## Workspace note

Preserve the initial untracked user files `data/site.v3 2.json` and `migrations/v2-to-v3 2.json`. After local main synchronization, 20 additional untracked numbered copies appeared (22 total), including 13 `geo/regions/* 2.geojson` files and copies under data/, migrations/, and reports/. Their producer was not established. None were deleted or committed.

Extra GeoJSON copies conflict with the exact-17-file validation contract. Do not run in-place extraction in this workspace: its existing cleanup can delete extra GeoJSON files. Use a clean checkout for build/verification until the owner reconciles these copies. The merged tracked graph was verified separately and has exactly 17 region files.

Private runtime state under `artifacts/workbench/` is intentionally not published. Back it up privately before deleting artifacts; its unapproved drafts and source-check observations are not reconstructed from the public site JSON alone.
