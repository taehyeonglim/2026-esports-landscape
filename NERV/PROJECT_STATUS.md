# Project status

- Last updated: **2026-10-04 KST**; maintainer handoff: **Codex**.
- Canonical branch: **main** at **a2fc24d2debdd1d8cf20e8e3c5588f6859d1913c**. Social-thumbnail work is verified on **feat/social-thumbnail**, based on that commit, and awaits commit/push/merge and signed deployment. Data remains the owner-approved October refresh from PR #26.
- Current live public release remains `315722acb895598dd26debff04c89c8bcea78218d3b35a345c857b741e63400e`; the new thumbnail is a verified candidate, not yet deployed.

## Product and data

- Static HTML/CSS/ES modules and GitHub Pages remain the public architecture; [map explorer contract](../docs/map-explorer.md).
- Added a **1730×909 PNG** social thumbnail with large Korean typography, lime 2026 and an illuminated cyan Korean map illustration. Homepage and research HTML each declare their own canonical/title/description plus shared absolute HTTPS Open Graph and large-image card metadata, actual dimensions and alternative text. [Asset and generation prompt](../docs/social-preview.md). Decorative relief/highlights are not geographic data or case markers.
- Public home fills the first viewport with a map workspace. Desktop results open in a 400px right panel; compact results use an expandable nonmodal bottom sheet with short-screen fallback. Summary/featured sections remain below. Filters preview a draft and apply/cancel transactionally. Shared broadcast colors/logo, URL keys and archival data remain intact; no new external runtime dependencies.
- Map labels use self-hosted Korean **Pretendard Medium (500)** with a thin 2px halo, tighter spacing and separately styled regular/tabular counts. The prior Pretendard Std font has no Hangul glyphs; the new unmodified upstream subset covers all 17 region names. Other page typography is unchanged; [font source, checksum and license](../styles/fonts/SOURCES.txt).
- School-level choices, comparisons, state/shared URLs and research totals use [one alias mapping](../src/school-level.js). `고` and `고등학교` now include all **13 high-school cases (7 original + 6 newer)**; mixed/audience/unknown labels remain distinct. Raw archival values and source lineage are unchanged.
- Selected map regions retain density fill, including zero matches, with dashed outlines and lime labels. SVG fitting includes labels/leader lines. Panel close, detail return and viewport changes preserve filters, list position, expansion and focus; direct URLs open the intended panel.
- Archival graph: **243 records / 17 regions / 246 sources**, data cutoff **2026-10-04**. Immutable 230-record baseline and five legacy additions remain intact.
- Public case search/comparison/map summaries: **83 cases / 86 case sources**. All **160 legacy regional display references** remain excluded and separated in the research appendix; no reference is reintroduced or duplicated.
- Geographic typology: **36 regional cases**, **23 coordinate-eligible cases**, **13 regional cases without coordinates**, two nationwide/adjacent and 45 unknown scopes. Map summaries count documents, not activity rankings or venue pins.
- Owner explicitly approved the [October batch](../reports/2026-10-04-refresh.v1.json): **eight new school event cases and two existing-program evidence updates**. [Approved overlay](../data/approved-reviews.v1.json) now holds ten approvals and eleven additional sources. Existing notes are preserved; event dates and publication dates are distinct; planned events are not claimed completed.
- Every archival operational status remains `needs_review`. Approval covers the stated evidence changes, not ongoing operation. This is targeted official-source catch-up, not a nationwide census or complete re-verification of the prior 75 cases.
- Added two exact-host [site evidence publishers](../config/site-evidence-publishers.v1.json); the protected snapshot registry remains at 18 education authorities. Human confirmation, PII screening, source ownership and prior-hash controls remain active.
- Workbench default/review dates now use `Asia/Seoul`; valid Korean review dates are no longer rejected as future dates near the UTC boundary. Extraction and validation logs report the full approved projection.

## Verified release and delivery

- Social-thumbnail candidate passed the complete local gate: **48 JavaScript, 135 Python, six static contracts, 170 public-browser and one administrator scenario**, deterministic extraction and reproducible release hashes. Candidate `8c720f770470a4d01513c7662fa0bfae03e5e4ed3c88fdbfe16255765d968359` has **63 assets**.
- Both built HTML heads were independently parsed without JavaScript; page identity, absolute image URL, alternative text and real PNG dimensions/checksum match. The build includes the **2,133,422-byte** image. Manual **600×315 and 320×168** previews confirm readable title/year and unclipped composition.
- Pending delivery: commit/push/merge, exact-main Astra review, signed Pages deployment and live crawler-style readback. Existing completed delivery below describes the previous release.

- Typography committed **ab57226**, pushed and merged as **140facd** through [PR #32](https://github.com/taehyeonglim/2026-esports-landscape/pull/32). The first actual Astra assessment rejected a pre-existing school-level omission; that release was **not deployed** and the gate was not bypassed.
- Alias correction committed **ca3dd13**, pushed and merged as **e2db70f** through [PR #33](https://github.com/taehyeonglim/2026-esports-landscape/pull/33). Local main was synchronized with origin/main; both merged implementation branches were removed locally/remotely.
- Complete verification passed locally, in the independent review checkout and in Actions: **48 JavaScript, 135 Python, six static contracts, 170 public-browser and one administrator scenario**, deterministic extraction and reproducible release hashes.
- Coverage includes font/label geometry, selected density, filter/zero/reset counts, original record immutability, alias/URL deduplication, the formerly omitted high-school case, 13-case UI/research totals, five browsers, mobile panels, keyboard/focus, accessibility and reduced motion.
- Genuine exact-source Astra reassessment of **e2db70f**: **approved, 7/7 checks, no blockers**. This is release assessment, not factual certification or human usability approval.
- [Push CI 37169626916](https://github.com/taehyeonglim/2026-esports-landscape/actions/runs/37169626916): build succeeded; deployment skipped as designed. [Signed run 37169830327](https://github.com/taehyeonglim/2026-esports-landscape/actions/runs/37169830327): build, release gate and Pages deploy all **succeeded** on 2026-10-04 KST. The trusted coordinator recorded `deployed`.
- Live release: `315722acb895598dd26debff04c89c8bcea78218d3b35a345c857b741e63400e` (**62 assets**). Independent readback matched **18 exact asset hashes**, including the Korean font/provenance/license, all changed runtime files, research, public data and national geometry.
- Live desktop and **390×844 mobile** inspection confirmed the new map typography, full-map/drawer/sheet layouts and high-school filter returning 13 cases. Live research also displays `고 13건`. All 17 region names have native font glyph coverage. Browser viewport was restored; original 22 untracked files retain exact baseline hashes.
- The preceding typography release has no unresolved blocker. Its NERV-only [push CI 37170517520](https://github.com/taehyeonglim/2026-esports-landscape/actions/runs/37170517520) and same-artifact [signed run 37170786415](https://github.com/taehyeonglim/2026-esports-landscape/actions/runs/37170786415) both succeeded on **a2fc24d**.

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

Private workbench state is intentionally not published. Back it up before deleting artifacts; unapproved drafts are not reconstructed from public JSON alone. The October batch used its own SQLite database and did not modify the original private drafts. Its approval database, UI evidence and verification/live-readback reports are backed up privately under `artifacts/october-2026-refresh/` in the original workspace.

Broadcast-design QA screenshots, verification logs and 11-asset live readback are backed up privately under `artifacts/esports-broadcast-design/` in the original workspace. All 22 original untracked copies still match their recorded hashes.

Fullscreen-map screenshots, verification logs, Astra assessment and 11-asset live readback are backed up privately under `artifacts/fullscreen-map/` in the original workspace. The original 22 untracked files retain their recorded hashes. No private workbench state was modified.

Map-typography QA, font coverage, both verification generations, the genuine rejected/approved assessments and 18-asset live readback are backed up privately under `artifacts/map-typography/` in the original workspace. The original 22 untracked copies and private workbench state remain intact. Rejection history is retained; no approval or deployment was fabricated.

Social-thumbnail work uses an isolated worktree outside Documents. Image generation, preview-size QA, metadata verification and full-gate evidence are backed up privately in original workspace `artifacts/social-thumbnail/`. All 22 unrelated untracked copies match their baseline hashes; the private workbench and discovery PR #16 remain untouched.
