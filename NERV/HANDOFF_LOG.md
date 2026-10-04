# Handoff log

Newest entries go first. Keep entries concise and link to durable artifacts.

## 2026-10-04 — Codex — Deliver refined map typography and the release-blocking filter fix

**Outcome**

- Typography **ab57226 → 140facd** ([PR #32](https://github.com/taehyeonglim/2026-esports-landscape/pull/32)) and school-level correction **ca3dd13 → e2db70f** ([PR #33](https://github.com/taehyeonglim/2026-esports-landscape/pull/33)) were committed, pushed and merged. Main synchronized; both implementation branches removed locally/remotely.
- Map labels now use Korean Pretendard Medium, a thin halo and lighter spaced tabular counts. The first release assessment blocked the existing school-level alias omission; the correction unifies filtering/URLs/research totals without changing archival values or merging mixed labels.
- Exact-source reassessment genuinely approved all seven checks. Signed Pages deployment and live readback completed; no release protection was bypassed.

**Verification**

- Local, independent-review and Actions gates passed: **48 JS, 135 Python, six static, 170 public-browser and one administrator test**, deterministic extraction and reproducible hashes.
- [Push CI 37169626916](https://github.com/taehyeonglim/2026-esports-landscape/actions/runs/37169626916) succeeded. [Signed run 37169830327](https://github.com/taehyeonglim/2026-esports-landscape/actions/runs/37169830327): build, release gate and deploy all succeeded; coordinator recorded deployed.
- Live release `315722acb895598dd26debff04c89c8bcea78218d3b35a345c857b741e63400e` (62 assets); **18 exact live file hashes matched**. Live desktop/mobile typography and high-school filtering, plus research `고 13건`, confirmed. Original 22 untracked copies retain baseline hashes.
- Evidence, including the actual rejection and subsequent approval, is backed up privately in `artifacts/map-typography/`. Archival data, geometry, dependencies, release policy, private drafts and unrelated PR #16 remain intact.

**Remaining work**

- No implementation delivery blocker. This NERV-only closeout changes no public artifact; subsequent documentation CI is separate. Operating-status and data-review backlog remains unchanged.

**References**

- [Production site](https://taehyeonglim.github.io/2026-esports-landscape/)
- [Map explorer and school-level contract](../docs/map-explorer.md)
- [Font source and checksum](../styles/fonts/SOURCES.txt)

## 2026-10-04 — Codex — Correct the school-level omission blocking typography delivery

**Outcome**

- Typography commit **ab57226** was pushed and merged as **140facd** through [PR #32](https://github.com/taehyeonglim/2026-esports-landscape/pull/32). Main was synchronized and the task branch removed locally/remotely.
- Its actual Astra assessment passed design but rejected usability: the existing `고` filter returned 7 cases and omitted 6 equivalent `고등학교` cases. The signed deploy was not dispatched; no review, receipt or policy was bypassed.
- A shared read-time alias mapping now unifies choices, matching, state, short/full shared URLs and research totals. All 13 high-school cases are included. Mixed/audience/unknown values and exact archival source records remain intact; font styling is unchanged.

**Verification**

- Combined release gate passed: **48 JS, 135 Python, six static, 170 public-browser and one administrator test**, deterministic extraction/release hashes. New regression passes in all five browsers and includes the formerly omitted case.
- Candidate release `315722acb895598dd26debff04c89c8bcea78218d3b35a345c857b741e63400e` (62 assets). Actual rejection and both verification generations are preserved privately in `artifacts/map-typography/`.
- [Typography push CI 37168866877](https://github.com/taehyeonglim/2026-esports-landscape/actions/runs/37168866877) succeeded. Prior live artifact remains release `34920dc148c612c49456bf0bb68efdd1a8d34f18cb78cb736f54270715898150`; new design is not yet deployed.

**Remaining work**

- Commit/push/merge this correction, run exact-main Astra reassessment and signed deployment, verify live assets and close out NERV. Original 22 untracked copies and unrelated PR #16 remain preserved.

**References**

- [School-level normalizer](../src/school-level.js)
- [Map explorer contract](../docs/map-explorer.md)
- [Signed release process](../docs/astra-release.md)

## 2026-10-04 — Codex — Refine map label typography

**Outcome**

- Replaced Korean system-font fallback on map labels with self-hosted Pretendard Medium; reduced bold weight/outline and gave document counts separate lighter/tabular styling and spacing. Selection still highlights both region and count.
- Added the unmodified official Korean font subset with upstream commit/checksum and existing OFL license. Data, geometry, other-page typography, dependencies and release policy are unchanged.

**Verification**

- Complete local release gate passed: 46 JS, 135 Python, six static, 165 public-browser and one administrator scenario; deterministic extraction and reproducible hashes.
- All 17 region names have native glyph coverage. Desktop/mobile manual checks and filter/zero/reset count assertions passed.
- Candidate release `0bc62020d1be1f67f10dfc0193dd201e4d88489ae1289c0ac3b2991c1e4e7c33` (61 assets). Evidence is backed up privately under original workspace `artifacts/map-typography/`; all 22 unrelated copies are preserved.

**Remaining work**

- Pre-merge record: commit/push/merge, exact-main Astra assessment and signed Pages deployment, live asset readback, main synchronization and NERV delivery closeout.

**References**

- [Font source and checksum](../styles/fonts/SOURCES.txt)
- [Signed release process](../docs/astra-release.md)

## 2026-10-04 — Codex — Deliver the fullscreen map workspace to Pages

**Outcome**

- Committed **eed4fc5**, pushed and merged [PR #30](https://github.com/taehyeonglim/2026-esports-landscape/pull/30) as **79d4c84**. Synchronized local main and removed the merged implementation branch locally/remotely.
- First viewport now presents the full map with an on-demand desktop drawer or expandable mobile bottom sheet. Transactional filters, direct URLs, map density, detail/source access and scroll/focus restoration are verified.
- Genuine Astra approval passed all seven checks. Signed Pages deployment and independent live verification completed. Public data, research assets, dependencies, release policy, original 22 untracked copies and unrelated PR #16 remain intact.

**Verification**

- Full local, independent-review and Actions gates passed: 46 JS, 135 Python, six static, 165 public-browser and one administrator test; deterministic extraction and reproducible hashes.
- [Push CI 37167550642](https://github.com/taehyeonglim/2026-esports-landscape/actions/runs/37167550642) succeeded. [Signed run 37167922215](https://github.com/taehyeonglim/2026-esports-landscape/actions/runs/37167922215): build, signature gate and deployment succeeded.
- Live release `34920dc148c612c49456bf0bb68efdd1a8d34f18cb78cb736f54270715898150`; 11 exact asset hashes matched. Live desktop/mobile inspection verified region selection, panel behavior/expansion, source link and detail return. QA is backed up privately in original workspace `artifacts/fullscreen-map/`.

**Remaining work**

- No implementation delivery blocker. This NERV-only closeout changes no reviewed public assets; subsequent documentation CI is separate. Existing operating-status and data-review work remains unchanged.

**References**

- [Production site](https://taehyeonglim.github.io/2026-esports-landscape/)
- [Map explorer contract](../docs/map-explorer.md)
- [Signed release process](../docs/astra-release.md)

## 2026-10-04 — Codex — Implement and verify the fullscreen map workspace

**Outcome**

- Rebuilt the first viewport around the map. Desktop uses a closed-by-default 400px results drawer; compact screens keep a map above an expandable half-height sheet, with full-height results on short screens. Summary/featured sections remain below.
- Filters now preview a draft and apply/cancel atomically. Preserved shareable URLs, selected density, source links, list scroll/focus and sheet expansion. SVG bounds include labels and leader lines.
- Preserved all public data/research assets, dependency and release policy, original 22 untracked files and unrelated discovery PR #16. Implementation uses an isolated worktree.

**Verification**

- Complete `CI=1 npm run verify:release`: 46 JS, 135 Python, six static, 165 public-browser and one administrator test passed; deterministic extraction/release hashes passed.
- Manual desktop/mobile inspection and automated six-width/landscape checks cover canvas size, map containment, drawers/sheets, filters, detail/source access, URL navigation, focus restoration, independent scrolling, errors, accessibility and reduced motion.
- Candidate release `34920dc148c612c49456bf0bb68efdd1a8d34f18cb78cb736f54270715898150` (60 assets); original untracked hashes unchanged.

**Remaining work**

- Pre-merge record: commit/push/merge the task branch, obtain exact-main Astra approval and signed Pages deployment, verify live assets and complete NERV delivery closeout.
- Existing operating-status and data-review backlog remains separate.

**References**

- [Map explorer contract](../docs/map-explorer.md)
- [Signed release process](../docs/astra-release.md)

## 2026-10-04 — Codex — Deliver the esports broadcast design to Pages

**Outcome**

- Committed **8b1f935**, pushed and merged [PR #28](https://github.com/taehyeonglim/2026-esports-landscape/pull/28) as **7a7cb18**. Synchronized local main and removed the merged implementation branch locally/remotely.
- Home and research now share the black/navy broadcast design with cyan/lime accents. Genuine Astra review approved all seven checks; signed Pages delivery and live confirmation completed.
- Preserved all public data, 83-case/160-reference partition, URL and uncertainty contracts, dependency/release policy, original 22 untracked files, private drafts and unrelated PR #16. QA evidence is backed up privately in the original workspace.

**Verification**

- Full local, independent-review and Actions gates passed: 45 JS, 135 Python, six static, 150 public-browser and one administrator scenario; deterministic extraction and reproducible hashes.
- [Push CI 37165954495](https://github.com/taehyeonglim/2026-esports-landscape/actions/runs/37165954495) passed its build. [Signed run 37166166213](https://github.com/taehyeonglim/2026-esports-landscape/actions/runs/37166166213): build, signature gate and deployment succeeded.
- Live release `dc321c1d6f13c9e664caf6fa985d6c8338c3c16d580356f759161bb8cb2a6553`; 11 exact asset hashes matched. Live desktop/mobile checks confirmed the design, count, selection, detail/source link and research page.

**Remaining work**

- No delivery blocker. This NERV-only closeout changes no reviewed public assets. Existing operating-status and school-level normalization work remains separate.

**References**

- [Production site](https://taehyeonglim.github.io/2026-esports-landscape/)
- [Public UI contract](../docs/map-explorer.md)
- [Signed release process](../docs/astra-release.md)

## 2026-10-04 — Codex — Implement and verify the esports broadcast design

**Outcome**

- Replaced the public site's light workspace with shared black/navy panels, cyan navigation, lime selections and amber review status. Restyled the compact title/stat band, tactical map, case cards, comparison, summary/featured cards and research page using existing fonts/logo and CSS/SVG decoration.
- Preserved URL/data contracts, 83-case/160-reference partition, factual uncertainty and release policy. Map selection retains density colors, including zero cases. Fixed immediate detail positioning after the taller title exposed a delayed-frame source-visibility regression.
- Preserved the original 22 untracked workspace copies, private workbench drafts and unrelated PR #16. Work was isolated outside the synchronized Documents folder.

**Verification**

- Full `npm run verify:release`: 45 JS, 135 Python, six static, 150 public-browser and one administrator scenario; deterministic extraction and reproducible hashes passed. U4 passed three targeted repetitions after the fix.
- Desktop/mobile visual review and six responsive widths covered map, search, details/source links, filter sheet, comparison, empty results and research. Accessibility and reduced-motion checks passed in five browser projects.
- Candidate release: `dc321c1d6f13c9e664caf6fa985d6c8338c3c16d580356f759161bb8cb2a6553` (60 assets). No data, dependencies or media assets changed.

**Remaining work**

- Pre-merge record: push/merge the task branch, obtain a genuine exact-main Astra review and signed Pages delivery, then verify live assets and update this handoff. No deployment success is claimed here.
- Existing data-review backlog remains separate.

**References**

- [Public UI contract](../docs/map-explorer.md)
- [Shared design tokens](../styles/tokens.css)
- [Signed release process](../docs/astra-release.md)

## 2026-10-04 — Codex — Deliver the October data refresh to Pages

**Outcome**

- Committed **29e6428**, pushed and merged [PR #26](https://github.com/taehyeonglim/2026-esports-landscape/pull/26) as **be4806c**. Synchronized local main and removed the merged task branch locally/remotely.
- Genuine Astra review approved all seven checks. Signed Pages delivery now serves **83 cases**, **243 archival records**, **246 sources** and cutoff **2026-10-04**. Every operational status remains `needs_review`; five candidates remain pending.
- Preserved the original 22 untracked copies byte-for-byte, the 235 private drafts and unrelated PR #16. Backed up the task's approval database and verification evidence privately before worktree cleanup.

**Verification**

- Full release gate passed locally, independently and in Actions: 45 JS, 135 Python, six static, 150 public-browser and one administrator scenario; deterministic extraction and reproducible release hashes.
- [Signed run 37163915208](https://github.com/taehyeonglim/2026-esports-landscape/actions/runs/37163915208): build, signature gate and deployment succeeded. [Push CI 37163694221](https://github.com/taehyeonglim/2026-esports-landscape/actions/runs/37163694221) passed its build.
- Live release `eff4117b2ad726ad5efa2a10d2f97383f074f152e7f8293db72fe6eb2e5c13b3`; exact home/research/data/app/CSS hashes matched. Live browser confirmed the new case, count, date and source link.

**Remaining work**

- No delivery blocker. Resolve five deferred candidates and review actual operating status; 109 data gaps and 45 unknown scopes remain.
- Astra's nonblocking school-level label normalization finding is recorded in status. This documentation-only closeout does not change the reviewed release assets.

**References**

- [Approved October batch](../reports/2026-10-04-refresh.v1.json)
- [Production site](https://taehyeonglim.github.io/2026-esports-landscape/)
- [Signed release process](../docs/astra-release.md)

## 2026-10-04 — Codex — Apply owner-approved October data refresh

**Outcome**

- Applied the explicitly approved eight new school event cases and two existing-program updates: **75→83 cases**, **235→243 archival records**, **246 sources**, cutoff **2026-10-04**. Preserved the 160 excluded references, original notes and every `needs_review` operational status.
- Added exact-host site evidence authorities without extending the protected 18-publisher registry, added an official KeSPA discovery surface, and fixed KST review dates. Candidate ledger is 195 URLs: 13 accepted, 97 duplicate, 80 rejected and five pending.
- Preserved the original workspace's 22 untracked copies, private 235-draft workbench and unrelated discovery PR #16.

**Verification**

- Full release gate: 45 JS, 135 Python, six static, 150 public browser and one administrator scenario; deterministic extraction and reproducible hashes passed.
- Desktop/mobile inspection verified a newly added case's source link, dates and uncertainty. Exact proposal/approval comparison passed; 233 existing records and all 160 reference records are unchanged. Updated an obsolete Jeju-count regression before the complete passing rerun.

**Remaining work**

- Pre-merge record: push/merge the branch, obtain a genuine exact-main Astra assessment and signed Pages deployment, then record actual run/live hashes. This entry does not claim the new batch is deployed.
- Five deferred candidates, operating-status checks, 109 data gaps and 45 unknown scopes remain.

**References**

- [October batch and deferred reasons](../reports/2026-10-04-refresh.v1.json)
- [Approved reviews](../data/approved-reviews.v1.json)
- [Review workbench](../docs/review-workbench.md)

## 2026-10-04 — Codex — Deliver the map-first explorer to Pages

**Outcome**

- Committed as **b637103**, pushed and merged [PR #24](https://github.com/taehyeonglim/2026-esports-landscape/pull/24) as **373d541**. Synchronized local main and removed the merged task branch.
- Genuine Astra review approved all seven checks with no blockers. Signed Pages delivery and live verification completed; no human approval or factual-status changes were invented.
- Original workspace's 22 untracked copies, private workbench data and unrelated discovery PR #16 were preserved.

**Verification**

- Full gate passed: 45 JS, 131 Python, six static contracts, 150 public browser, one administrator, deterministic extraction and reproducible release hashes.
- [Signed run 37161681814](https://github.com/taehyeonglim/2026-esports-landscape/actions/runs/37161681814): build, release gate and deployment succeeded. [Push CI](https://github.com/taehyeonglim/2026-esports-landscape/actions/runs/37161432558) also passed its build.
- Live release `3ed0917ed68d48f7b2663af1bab66a21480285558c903e9e4300ebdb7db520eb`; exact hashes matched home, research, data, app JS and main CSS. Live map selection returned the expected Seoul cases.

**Remaining work**

- No implementation delivery blocker. Existing operating-status review, 109 data gaps and 45 unknown scopes remain separate priorities.
- This NERV/README closeout records the completed release without changing its public assets. Keep the existing signed gate and preserve the workspace copies.

**References**

- [Implementation PR #24](https://github.com/taehyeonglim/2026-esports-landscape/pull/24)
- [Production site](https://taehyeonglim.github.io/2026-esports-landscape/)
- [Map explorer contract](../docs/map-explorer.md)

## 2026-10-04 — Codex — Implement and verify the map-first explorer

**Outcome**

- Rebuilt home around a desktop map/results split and compact map/list switching below 1024px. Filtered map counts retain a fixed scale and a separate zero state; region labels and 17 accessible buttons select results.
- Details retain the desktop map, expose sources before extra metadata, preserve full case limitations in a disclosure and restore list scroll/focus. Added empty-result recovery, data retry and pending-search cancellation.
- Preserved existing URLs, 75-case/160-reference partition, all factual statuses, public data and release authorization. Original workspace's 22 untracked copies remain untouched.

**Verification**

- `npm run verify:release`: 45 JS, 131 Python, six static, 150 public-browser and one administrator scenario passed; deterministic extraction and reproducible release hashes passed.
- Desktop and compact visual inspection covered map, results, details/source links and empty states. WebKit/iOS label hit targets and debounced-query reset have regression coverage; no human study approval is claimed.
- Candidate release: `3ed0917ed68d48f7b2663af1bab66a21480285558c903e9e4300ebdb7db520eb`.

**Remaining work**

- This is the pre-merge verification record. Push/merge the task branch, run exact-main Astra assessment and signed deployment, then record actual CI/live readback.
- Existing factual-review backlog, private drafts and unrelated discovery PR #16 remain unchanged.

**References**

- [Map explorer contract](../docs/map-explorer.md)
- [Browser scenarios](../tests/browser.e2e.mjs)
- [Signed release process](../docs/astra-release.md)

## 2026-09-05 — Codex — Deliver genuine Astra-approved automatic Pages deployment

**Outcome**

- Implemented and installed the local GPT-6 Astra → signed receipt → independent Actions build/gate → Pages deployment pipeline through PRs #19–#22. All implementation branches were pushed and merged; local main synchronized.
- Real reviews found and blocked defects. Corrected filter reset, stale typology, missing limitations, unsupported reference/duplicate aggregation and Linux iOS first-result visibility before final approval.
- Final deployed source **828366c19dd842e9fce2aa369842afd3d18f3949**; Astra **7/7 approved**; no human approval or owner override fabricated.

**Verification**

- [Run 33969332429](https://github.com/taehyeonglim/2026-esports-landscape/actions/runs/33969332429): build, signed gate and deployment all succeeded. Live release ID and exact home/research/data hashes matched.
- Full local and remote release verification: 43 JS, 131 Python, six static contracts, 120 public browser and one administrator scenario, plus reproducibility checks.
- Scheduler enabled at 15-minute intervals; public key registered, credentials/private key remain local. Existing Pages branch protection preserved.

**Remaining work**

- Mac must remain awake/online with valid Codex/GitHub sessions. Future rejection or verification errors stop deployment; inspect local status/review artifacts and fix the source.
- All operating statuses remain unverified. Preserve 235 archival records, count 75 case records, and treat 160 reference anchors separately.
- Unrelated PR #16, 22 user workspace copies and private workbench drafts are preserved. This coordination-only closeout does not change public release assets; its CI is tracked in Actions.

**References**

- [Deployment run](https://github.com/taehyeonglim/2026-esports-landscape/actions/runs/33969332429)
- [AI release guide](../docs/astra-release.md)
- [Latest implementation PR #22](https://github.com/taehyeonglim/2026-esports-landscape/pull/22)

## 2026-09-05 — Codex — Fix independent Linux mobile gate after Astra approval

**Outcome**

- Third actual Astra review approved all seven checks for `97bdd79` (PR #21). The coordinator signed and dispatched run 33968760867.
- Independent push CI 33968581254 caught an iOS-WebKit viewport regression (first card 674.15625px versus 664px viewport). Cancelled the signed dispatch before deployment; no approval bypass or deployment success is claimed.
- Shortened hero/disclosure copy to restore first-result visibility without weakening the test. Reconciled README statistics with 75 cases and 160 archival references.

**Verification**

- Full local suite passed: 43 JS, 131 Python, 6 static, 120 public browser, 1 administrator, reproducibility. New source requires a fresh model receipt and Linux validation.

**Remaining work**

- Merge correction, run the automatic review again, and confirm actual deployment and live hashes.

**References**

- [Failed independent build](https://github.com/taehyeonglim/2026-esports-landscape/actions/runs/33968581254)
- [Cancelled signed dispatch](https://github.com/taehyeonglim/2026-esports-landscape/actions/runs/33968760867)

## 2026-09-05 — Codex — Separate unsupported reference anchors after Astra rejection

**Outcome**

- Second real Astra review rejected the `32aa258` release. It found unsupported regional participation anchors, duplicate Gunsan event counting, and scope/coordinate conflation; no signed dispatch occurred.
- Preserve the 235-record archival graph and IDs, but exclude all 160 legacy regional display anchors from case search/comparison/map aggregates. Research explicitly separates those references; case count is 75. Coordinate eligibility is 23, with five additional regional cases lacking coordinates.
- Update U2/U3 automation targets to case records; retain pending human approval. No operational facts were approved.

**Verification**

- Full release verification passed: 43 JS, 131 Python, 6 static, 120 public browser, 1 administrator, reproducible hashes. Reference partition, duplicate exclusion and off-map regression scenarios passed.

**Remaining work**

- Merge this correction and obtain a fresh model verdict before deployment. Earlier push build success is not deployment success.

**References**

- [Partition policy and automation](../docs/astra-release.md)
- [Public record projection](../src/record-scope.js)

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
