# Project status

- Last updated: **2026-09-05 KST**
- Maintainer handoff: **Codex**
- Canonical branch: **main**.
- Latest implementation commit: **97bdd7961c995d8f9c1d496e617faf67081eee1a**, reference partition squash-merged through [PR #21](https://github.com/taehyeonglim/2026-esports-landscape/pull/21).
- AI automation was committed as `120030e`, pushed and merged; local main synchronized. Follow-up fixes address actual Astra rejection findings.

## Product and data

- Static HTML/CSS/ES modules and GitHub Pages remain the public architecture.
- Archival data remains **235 records / 17 regions / 235 sources**, cutoff **2026-07-29**. Public case search/comparison uses **75 cases**; **160 legacy regional display references** are separated in the research appendix and excluded from case/map aggregates. The source graph and stable IDs remain intact.
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

- JavaScript: **43/43**.
- Python: **131/131**.
- Static contracts: **6/6**, including exclusion of private administration files.
- Public browser matrix: **120/120** across desktop Chromium/Firefox/WebKit and Android/iOS profiles.
- Local administrator browser scenario: **1/1**, including explicit approval, restart persistence, mobile width, unauthorized API and private-file rejection.
- Independent extraction, immutable baseline invariants, release hash reproducibility, input-only provenance changes, and output-mutation detection passed.
- `git diff --check` passed. Existing user files were preserved.
- Post-merge validation and JavaScript tests passed again in a clean detached checkout of `116a5e2`.

## Release gates

- Owner delegates release assessment to **gpt-6-astra**, high reasoning. Signed AI approval replaces the mandatory human-study gate for this route; fact approval and protected snapshot publication remain separate.
- [AI release guide](../docs/astra-release.md): full local verification, five screenshots, seven structured checks, Ed25519 source/artifact/policy binding, independent Actions rebuild and live readback.
- Installed LaunchAgent `com.taehyeong.esports-astra-review` polls every 15 minutes. Public key is registered in GitHub; private directory/key permissions are 0700/0600. Mac must be awake/online with valid local Codex and GitHub sessions.
- First actual review of `894488c` rejected reset, typology and detail-disclosure defects; fixes merged in PR #20 as `32aa2587c22121dc93f6be09fff1f9cd97309ca6`.
- Second actual review of `32aa258` rejected unsupported regional anchors, a duplicate Gunsan event and conflated scope/coordinate counts. Neither review signed or dispatched deployment.
- Follow-up `agent/astra-data-scope`: isolate 160 legacy reference anchors, retain 75 case records and all 235 archival IDs, report coordinate eligibility separately. U2/U3 automated navigation targets now use case records; human approval remains pending.
- Full local release gate passed: **43 JS, 131 Python, 6 static, 120 public-browser, 1 administrator**, reproducible hashes. Push CI 33967703649 passed build and skipped deploy as intended; no new successful deployment yet.
- Third actual Astra review of `97bdd79` **approved all seven checks**, with no blockers; a signed dispatch was created as run 33968760867.
- Independent push CI 33968581254 failed Linux iOS-WebKit cold-home layout: first card y=674.15625 exceeded the 664px viewport. The signed dispatch was cancelled before deployment rather than bypassing the failing build.
- Follow-up `agent/astra-mobile-fix` shortens mobile hero/disclosure copy while preserving uncertainty and reference exclusions. Full local release verification passed again (43 JS, 131 Python, 6 static, 120 public-browser, 1 admin, reproducibility). Test thresholds were not weakened.
- Next: merge the layout correction, obtain a fresh source-bound model approval and pass Linux CI before deployment/readback. Reintroducing reference records requires explicit source/duplicate review, not an operational-status edit alone.

## Workspace note

Preserve the initial untracked user files `data/site.v3 2.json` and `migrations/v2-to-v3 2.json`. After local main synchronization, 20 additional untracked numbered copies appeared (22 total), including 13 `geo/regions/* 2.geojson` files and copies under data/, migrations/, and reports/. Their producer was not established. None were deleted or committed.

Extra GeoJSON copies conflict with the exact-17-file validation contract. Do not run in-place extraction in this workspace: its existing cleanup can delete extra GeoJSON files. Use a clean checkout for build/verification until the owner reconciles these copies. The merged tracked graph was verified separately and has exactly 17 region files.

Private runtime state under `artifacts/workbench/` is intentionally not published. Back it up privately before deleting artifacts; its unapproved drafts and source-check observations are not reconstructed from the public site JSON alone.
