# Project status

- Last updated: **2026-09-05 KST**; maintainer handoff: **Codex**.
- Canonical branch: **main**. Latest deployed implementation: **828366c19dd842e9fce2aa369842afd3d18f3949**, merged through [PR #22](https://github.com/taehyeonglim/2026-esports-landscape/pull/22).
- This coordination-only closeout records the delivered implementation and does not change public release assets. Refer to Git for its containing main commit.

## Product and data

- Static HTML/CSS/ES modules and GitHub Pages remain the public architecture.
- Archival graph: **235 records / 17 regions / 235 sources**, cutoff **2026-07-29**. Immutable 230-record baseline and five legacy additions remain intact.
- Public case search/comparison/map summaries: **75 cases**. All **160 legacy regional display references** are excluded from case aggregates and explicitly separated in the research appendix. Their IDs and source lineage remain archived; the Gunsan auxiliary event is not counted twice.
- Geographic typology separates **28 regional cases**, **23 coordinate-eligible cases**, and **five regional cases without coordinates**. Current map summaries are regional document counts, not activity rankings or venue pins.
- Every archival operational status remains `needs_review`. Case partitioning and AI release approval are not factual operating-status approvals.
- Review-filter reset, current typology, case-specific evidence limitations, and compact iOS first-result visibility were corrected after real model/CI findings.
- [Approved review overlay](../data/approved-reviews.v1.json) remains empty; existing source ownership, PII, prior-hash and official-evidence safeguards remain active.

## Automatic release operation

- Owner delegates release assessment to **gpt-6-astra**, high reasoning, under the [AI policy](../config/astra-review-policy.v1.json).
- Installed LaunchAgent: `com.taehyeong.esports-astra-review`, polling every **15 minutes** in an independent private clone. Mac must be awake, logged in, online, with valid local Codex and GitHub sessions.
- Local full verification and five screenshots precede a tool-disabled structured model review. A complete seven-check approval is signed with Ed25519 and bound to source, artifact, policy, evidence and a maximum 24-hour validity window.
- Public verification key is registered in GitHub. Private directory/key permissions verified **0700/0600**; ChatGPT credentials and private signing key stay on the Mac.
- Actions independently rebuilds and checks the signature using trusted workflow-source gate code. Only the deploy job receives Pages write/OIDC authority. Existing Pages branch protection remains active.
- Human study approval records remain pending. U2/U3 automation targets were replaced with case records; no human study or fact approval was invented. The scheduler never invokes the separate owner override.
- Guide: [Astra automation](../docs/astra-release.md). Local operational state: `~/.local/share/esports-astra-review/status.json`; private review evidence is under its `reviews/` directory, not NERV.

## Verified release

- Final genuine Astra review: **approved, 7/7 checks**, no blockers, exact source **828366c**.
- [Signed deployment run 33969332429](https://github.com/taehyeonglim/2026-esports-landscape/actions/runs/33969332429): independent build **success**, signed release gate **success**, Pages deploy **success**.
- Release ID: `b30a2c8b3631fd7961b0ec6e6bbfdf3e2af359bfed094c71ec18599bc4be1e54`.
- The coordinator confirmed the live release ID and public routes. Independent readback also verified exact hashes for home HTML, research HTML and public data JSON.
- Full verification passed: **43 JavaScript, 131 Python, six static contracts, 120 public-browser, one administrator scenario**, deterministic extraction and reproducible release hashes.
- Earlier reviews rejected genuine defects; the first approved candidate then failed Linux iOS layout CI and its dispatch was cancelled. Those were blocked attempts, not successful deployments; the newest handoff entries preserve their evidence.
- Changes were intentionally committed, pushed and merged in PRs #19–#22. Local main was synchronized; unrelated user files were preserved. This NERV closeout is delivered through its own main PR.

## Private review workbench and next priorities

- Loopback workbench: `PYTHONPATH=src python3 -m esports_data.cli admin --reviewer owner-reviewer`; private SQLite state remains under `artifacts/workbench/`.
- **235 unapproved drafts** from archival link checks remain local: 153 records had a fetched source; 82 need alternate retrieval; 115 unique URLs attempted, 87 fetched. Reachability does not establish relevance or current operation. No fact reviews were approved.
- Candidate ledger: 179 records, two accepted / 97 duplicate / 80 rejected / zero pending on main. Unrelated discovery **PR #16** remains open and untouched.
- Review actual official evidence for the 75 case records; assess reference reintroduction only with specific regional evidence, duplicate checks and explicit partition changes. Operational-status edits alone do not admit a reference.
- The 109 data gaps and 45 unknown scopes remain unresolved. Protected subject/claim snapshot publication remains a separate authorization path; workbench exports and AI Pages receipts are not snapshot publication receipts.

## Workspace note

Preserve all **22 untracked numbered copies** in the original workspace, including `data/site.v3 2.json`, `migrations/v2-to-v3 2.json`, 13 extra GeoJSON files and other data/migration/report copies. Their producer is unverified. None were deleted or committed.

Do not run in-place extraction in that workspace: existing cleanup can remove extra GeoJSON files. Use a clean checkout for validation. The installed coordinator uses its own clone outside the synchronized Documents folder.

Private workbench state is intentionally not published. Back it up privately before deleting artifacts; unapproved drafts are not reconstructed from public JSON alone.
