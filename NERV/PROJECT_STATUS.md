# Project status

- Last updated: **2026-10-04 KST**; maintainer handoff: **Codex**.
- Canonical branch: **main**, task base **5a7b20617ff9b4f84b18e7d5e9dc7d9a9c193c8e**. October refresh is verified on `data/october-2026-refresh`; merge and signed deployment are pending in this pre-merge record.
- Latest verified deployed implementation remains **373d541ba5db5dcfc32c69be8144587846f1779f**, [PR #24](https://github.com/taehyeonglim/2026-esports-landscape/pull/24), until a fresh exact-main release passes.

## Product and data

- Static HTML/CSS/ES modules and GitHub Pages remain the public architecture; [map explorer contract](../docs/map-explorer.md).
- Archival graph: **243 records / 17 regions / 246 sources**, data cutoff **2026-10-04**. Immutable 230-record baseline and five legacy additions remain intact.
- Public case search/comparison/map summaries: **83 cases / 86 case sources**. All **160 legacy regional display references** remain excluded and separated in the research appendix; no reference is reintroduced or duplicated.
- Geographic typology: **36 regional cases**, **23 coordinate-eligible cases**, **13 regional cases without coordinates**, two nationwide/adjacent and 45 unknown scopes. Map summaries count documents, not activity rankings or venue pins.
- Owner explicitly approved the [October batch](../reports/2026-10-04-refresh.v1.json): **eight new school event cases and two existing-program evidence updates**. [Approved overlay](../data/approved-reviews.v1.json) now holds ten approvals and eleven additional sources. Existing notes are preserved; event dates and publication dates are distinct; planned events are not claimed completed.
- Every archival operational status remains `needs_review`. Approval covers the stated evidence changes, not ongoing operation. This is targeted official-source catch-up, not a nationwide census or complete re-verification of the prior 75 cases.
- Added two exact-host [site evidence publishers](../config/site-evidence-publishers.v1.json); the protected snapshot registry remains at 18 education authorities. Human confirmation, PII screening, source ownership and prior-hash controls remain active.
- Workbench default/review dates now use `Asia/Seoul`; valid Korean review dates are no longer rejected as future dates near the UTC boundary. Extraction and validation logs report the full approved projection.

## Verification and delivery

- `npm run verify:release` passed: **45 JavaScript, 135 Python, six static contracts, 150 public-browser and one administrator scenario**, deterministic extraction and reproducible release hashes.
- Actual desktop/mobile inspection confirmed the newly admitted case, official link, separate event/publication dates and uncertainty disclosure. Original 233 unaffected records and all 160 references are unchanged; the two amended notes retain their original text.
- The first browser run exposed an obsolete fixed three-case expectation for Jeju; the test now derives the expected six cases from the public partition and the complete rerun passed.
- Candidate release ID: `eff4117b2ad726ad5efa2a10d2f97383f074f152e7f8293db72fe6eb2e5c13b3` (60 assets).
- Task branch push/PR/merge and genuine exact-main Astra review are the next delivery steps. No deployment success is claimed for this batch yet.
- Previous signed deployment [37161681814](https://github.com/taehyeonglim/2026-esports-landscape/actions/runs/37161681814) succeeded for source 373d541. Old live release ID: `3ed0917ed68d48f7b2663af1bab66a21480285558c903e9e4300ebdb7db520eb`.

## Automatic release operation

- Owner delegates release assessment to **gpt-6-astra**, high reasoning, under the [AI policy](../config/astra-review-policy.v1.json). Genuine seven-check approval, signed Ed25519 receipt and independent Actions build/gate are required.
- Installed LaunchAgent `com.taehyeong.esports-astra-review` polls every **15 minutes** in an independent private clone. Mac must be awake, logged in, online, with valid local Codex/GitHub sessions.
- Private credentials/key remain on the Mac. Only the Pages deploy job receives write/OIDC authority. Human study fixtures remain pending; no owner override or human study approval is invented.
- Guide: [Astra automation](../docs/astra-release.md). Private operational state: `~/.local/share/esports-astra-review/status.json`; review evidence is under its `reviews/` directory, not NERV.

## Review backlog and next priorities

- Candidate ledger: **195 records — 13 accepted / 97 duplicate / 80 rejected / five pending**. This refresh adds 16 targeted URLs, accepts 11 after owner approval, and defers four ambiguous/inconsistent school identities plus one attachment-dependent source. Follow the batch report for exact URLs/reasons.
- KeSPA's official school-program homepage is now a discovery surface. Discovery still does not auto-publish facts. Unrelated discovery **PR #16** remains open and untouched.
- Loopback workbench: `PYTHONPATH=src python3 -m esports_data.cli admin --reviewer owner-reviewer`.
- Original **235 unapproved link-check drafts** remain private: 153 records had a fetched source; 82 need alternate retrieval; 115 unique URLs attempted, 87 fetched. These drafts were not substituted for the ten explicit batch approvals.
- Review current operating status for the 83 cases and resolve the five pending candidates. The 109 data gaps and 45 unknown scopes remain unresolved. Reference reintroduction needs specific regional evidence, duplicate checks and an explicit partition revision.
- Protected subject/claim snapshot publication remains a separate authorization path; workbench exports and AI Pages receipts are not snapshot publication receipts.

## Workspace note

Preserve all **22 untracked numbered copies** in the original workspace, including `data/site.v3 2.json`, `migrations/v2-to-v3 2.json`, 13 extra GeoJSON files and other copies. Their producer is unverified. None were deleted or committed.

Do not run in-place extraction in the original workspace: cleanup can remove extra GeoJSON files. This task uses an isolated worktree; the installed coordinator uses its own clone outside the synchronized Documents folder.

Private workbench state is intentionally not published. Back it up before deleting artifacts; unapproved drafts are not reconstructed from public JSON alone. The October batch uses its own SQLite database and does not modify the original private drafts.
