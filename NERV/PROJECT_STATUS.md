# Project status

- Last updated: **2026-10-04 KST**; maintainer handoff: **Codex**.
- Canonical branch: **main**. Latest deployed public UI implementation: **79d4c84839ef3dfbad0c81db58f4655600c0888d**, merged through [PR #30](https://github.com/taehyeonglim/2026-esports-landscape/pull/30). Data remains the owner-approved October refresh from PR #26.
- This NERV coordination closeout records completed delivery and changes no public release assets. Refer to Git for its containing main commit.

## Product and data

- Static HTML/CSS/ES modules and GitHub Pages remain the public architecture; [map explorer contract](../docs/map-explorer.md).
- Public home fills the first viewport with a map workspace. Desktop results open in a 400px right panel; compact results use an expandable nonmodal bottom sheet with short-screen fallback. Summary/featured sections remain below. Filters preview a draft and apply/cancel transactionally. Shared broadcast colors, local fonts/logo, URLs, data and research remain intact; no new runtime dependencies or media assets.
- Selected map regions retain density fill, including zero matches, with dashed outlines and lime labels. SVG fitting includes labels/leader lines. Panel close, detail return and viewport changes preserve filters, list position, expansion and focus; direct URLs open the intended panel.
- Archival graph: **243 records / 17 regions / 246 sources**, data cutoff **2026-10-04**. Immutable 230-record baseline and five legacy additions remain intact.
- Public case search/comparison/map summaries: **83 cases / 86 case sources**. All **160 legacy regional display references** remain excluded and separated in the research appendix; no reference is reintroduced or duplicated.
- Geographic typology: **36 regional cases**, **23 coordinate-eligible cases**, **13 regional cases without coordinates**, two nationwide/adjacent and 45 unknown scopes. Map summaries count documents, not activity rankings or venue pins.
- Owner explicitly approved the [October batch](../reports/2026-10-04-refresh.v1.json): **eight new school event cases and two existing-program evidence updates**. [Approved overlay](../data/approved-reviews.v1.json) now holds ten approvals and eleven additional sources. Existing notes are preserved; event dates and publication dates are distinct; planned events are not claimed completed.
- Every archival operational status remains `needs_review`. Approval covers the stated evidence changes, not ongoing operation. This is targeted official-source catch-up, not a nationwide census or complete re-verification of the prior 75 cases.
- Added two exact-host [site evidence publishers](../config/site-evidence-publishers.v1.json); the protected snapshot registry remains at 18 education authorities. Human confirmation, PII screening, source ownership and prior-hash controls remain active.
- Workbench default/review dates now use `Asia/Seoul`; valid Korean review dates are no longer rejected as future dates near the UTC boundary. Extraction and validation logs report the full approved projection.

## Verified release and delivery

- Fullscreen map committed as **eed4fc5**, pushed and squash-merged as **79d4c84** through [PR #30](https://github.com/taehyeonglim/2026-esports-landscape/pull/30). Local main was synchronized with origin/main; the merged implementation branch was removed locally and remotely.
- Full verification passed locally, in the independent review checkout and in Actions: **46 JavaScript, 135 Python, six static contracts, 165 public-browser and one administrator scenario**, deterministic extraction and reproducible release hashes.
- Browser coverage includes 320, 390, 720, 1023, 1024 and 1440px, short landscape, label/geometry containment, 400px drawer, half-height sheet/expansion, filter draft cancellation, shared URLs, keyboard/focus restoration, independent scrolling, accessibility and reduced motion.
- Genuine Astra assessment: **approved, 7/7 checks, no blockers**, exact source **79d4c84**. This is release assessment, not factual certification or a human usability study.
- [Push CI 37167550642](https://github.com/taehyeonglim/2026-esports-landscape/actions/runs/37167550642): build succeeded, deployment skipped as designed. [Signed run 37167922215](https://github.com/taehyeonglim/2026-esports-landscape/actions/runs/37167922215): independent build, signature gate and Pages deployment all **succeeded** on 2026-10-04 KST.
- Live release: `34920dc148c612c49456bf0bb68efdd1a8d34f18cb78cb736f54270715898150` (60 assets). Independent readback matched exact hashes for **11 assets**, including all changed public files, research assets, public data and national map geometry. Data, research implementation, dependencies and release policy are unchanged.
- Live desktop/mobile inspection confirmed the full map, region selection and count, right drawer, bottom sheet/expansion, original source link and detail return. Original 22 untracked files retain exact baseline hashes.
- No delivery blocker remains. This NERV-only followup does not alter the reviewed public artifact; its subsequent CI is separate from the completed implementation release above.

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

Fullscreen-map screenshots, verification logs, Astra assessment and 11-asset live readback are backed up privately under `artifacts/fullscreen-map/` in the original workspace. The original 22 untracked files retain their recorded hashes. No private workbench state was modified.
