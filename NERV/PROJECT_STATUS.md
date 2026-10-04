# Project status

- Last updated: **2026-10-04 KST**; maintainer handoff: **Codex**.
- Canonical branch: **main**. Latest deployed public UI implementation: **7a7cb186f4d313d10d3ac9dc3ad5a1469a86dfba**, merged through [PR #28](https://github.com/taehyeonglim/2026-esports-landscape/pull/28). Data remains the owner-approved October refresh from PR #26.
- This coordination closeout records actual delivery and changes no public release assets. Refer to Git for its containing main commit.

## Product and data

- Static HTML/CSS/ES modules and GitHub Pages remain the public architecture; [map explorer contract](../docs/map-explorer.md).
- Public UI now shares a black/navy broadcast theme across home, map, filters, cards, detail, comparison and research. Cyan denotes navigation, lime selection/metrics, and amber review uncertainty. Local fonts/logo, first-viewport exploration, public URLs and all factual data remain intact. No new runtime dependencies or media assets.
- Selected map regions retain their density fill, including zero matches, with dashed selection outlines. Detail positioning/focus runs immediately after rendering so long-title source links remain accessible without a delayed scroll.
- Archival graph: **243 records / 17 regions / 246 sources**, data cutoff **2026-10-04**. Immutable 230-record baseline and five legacy additions remain intact.
- Public case search/comparison/map summaries: **83 cases / 86 case sources**. All **160 legacy regional display references** remain excluded and separated in the research appendix; no reference is reintroduced or duplicated.
- Geographic typology: **36 regional cases**, **23 coordinate-eligible cases**, **13 regional cases without coordinates**, two nationwide/adjacent and 45 unknown scopes. Map summaries count documents, not activity rankings or venue pins.
- Owner explicitly approved the [October batch](../reports/2026-10-04-refresh.v1.json): **eight new school event cases and two existing-program evidence updates**. [Approved overlay](../data/approved-reviews.v1.json) now holds ten approvals and eleven additional sources. Existing notes are preserved; event dates and publication dates are distinct; planned events are not claimed completed.
- Every archival operational status remains `needs_review`. Approval covers the stated evidence changes, not ongoing operation. This is targeted official-source catch-up, not a nationwide census or complete re-verification of the prior 75 cases.
- Added two exact-host [site evidence publishers](../config/site-evidence-publishers.v1.json); the protected snapshot registry remains at 18 education authorities. Human confirmation, PII screening, source ownership and prior-hash controls remain active.
- Workbench default/review dates now use `Asia/Seoul`; valid Korean review dates are no longer rejected as future dates near the UTC boundary. Extraction and validation logs report the full approved projection.

## Verified release and delivery

- Broadcast redesign committed as **8b1f935**, pushed and squash-merged as **7a7cb18** through PR #28. Local main was synchronized with origin/main; the merged implementation branch was removed locally and remotely.
- Full verification passed locally, in the independent review checkout and in Actions: **45 JavaScript, 135 Python, six static contracts, 150 public-browser and one administrator scenario**, deterministic extraction and reproducible release hashes.
- Existing U4 source-visibility check found a delayed-frame detail scroll; corrected the actual positioning and passed three targeted repetitions plus the full suite. Added selected-density/zero-state assertions without relaxing acceptance checks.
- Genuine Astra assessment: **approved, 7/7 checks, no blockers**, exact source **7a7cb18**. This is release assessment, not factual certification or a human usability study.
- [Push CI 37165954495](https://github.com/taehyeonglim/2026-esports-landscape/actions/runs/37165954495): build succeeded, deployment skipped as designed. [Signed run 37166166213](https://github.com/taehyeonglim/2026-esports-landscape/actions/runs/37166166213): independent build, signature gate and Pages deployment all **succeeded** on 2026-10-04 KST.
- Live release ID: `dc321c1d6f13c9e664caf6fa985d6c8338c3c16d580356f759161bb8cb2a6553` (60 assets). Independent readback matched exact hashes for **11 assets**, covering both HTML pages, all four stylesheets, four changed scripts and public data. No data, geographic files, dependency manifests, media assets or release policy changed.
- Desktop/mobile live inspection confirmed the new design, 83-case count, region selection, retained desktop map, original source link, mobile list and research page. Automated layouts cover **320, 390, 720, 1023, 1024 and 1440px**; all five browser projects passed accessibility and reduced-motion checks.
- No delivery blocker remains. NERV-only closeout does not alter the reviewed public artifact; remaining data-review priorities below are separate.

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
- Normalize equivalent school-level labels (`고`/`고등학교`, `중`/`중학교`) in future filter/analysis work; Astra recorded this as a nonblocking limitation. The approved batch retains its reviewed values.
- Review current operating status for the 83 cases and resolve the five pending candidates. The 109 data gaps and 45 unknown scopes remain unresolved. Reference reintroduction needs specific regional evidence, duplicate checks and an explicit partition revision.
- Protected subject/claim snapshot publication remains a separate authorization path; workbench exports and AI Pages receipts are not snapshot publication receipts.

## Workspace note

Preserve all **22 untracked numbered copies** in the original workspace, including `data/site.v3 2.json`, `migrations/v2-to-v3 2.json`, 13 extra GeoJSON files and other copies. Their producer is unverified. None were deleted or committed.

Do not run in-place extraction in the original workspace: cleanup can remove extra GeoJSON files. This task uses an isolated worktree; the installed coordinator uses its own clone outside the synchronized Documents folder.

Private workbench state is intentionally not published. Back it up before deleting artifacts; unapproved drafts are not reconstructed from public JSON alone. The October batch used its own SQLite database and did not modify the original private drafts. Its approval database, UI evidence and verification/live-readback reports are backed up privately under `artifacts/october-2026-refresh/` in the original workspace.

Broadcast-design QA screenshots, verification logs and 11-asset live readback are backed up privately under `artifacts/esports-broadcast-design/` in the original workspace. All 22 original untracked copies still match their recorded hashes.
