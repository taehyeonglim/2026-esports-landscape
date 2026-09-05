# GPT-6 Astra release automation

The repository owner delegates **release assessment** to `gpt-6-astra`, with high reasoning, under [`config/astra-review-policy.v1.json`](../config/astra-review-policy.v1.json). This replaces mandatory human study signoff for the signed AI release route. It does not create human approvals, approve individual factual corrections, or change the protected subject/claim publication system. Existing human fixtures remain pending.

## Operation

1. A local macOS LaunchAgent checks trusted `origin/main` every 15 minutes in a private independent clone. The Mac must be awake, logged in, online, and have valid `codex` ChatGPT and `gh` authentication. No API credential is copied to GitHub.
2. The runner installs locked dependencies and browser engines, runs `npm run verify:release`, and captures readable desktop, mobile, research, typology and case-detail screenshots.
3. A tool-disabled, ephemeral, read-only `codex exec --ignore-user-config --model gpt-6-astra` invocation reviews bounded public code/data, test evidence and images against seven checks. It receives no signing key or private workbench database.
4. Only an approved, complete structured result with no blockers is signed locally using Ed25519. The receipt binds source commit, release hash, policy hash, evidence hash, model, reasoning effort, execution identity and a maximum 24-hour validity window.
5. The runner dispatches Pages for that exact main SHA. Actions rebuilds and tests it independently. A separate read-only gate verifies the signature using `ASTRA_REVIEW_PUBLIC_KEY` and gate code from the workflow SHA. Only the deploy job receives Pages write/OIDC permissions.
6. The runner waits for Actions success and checks the live release ID and three public routes before recording `deployed`.

Push CI verifies the build; deployment waits for a signed dispatch. Missing/expired/tampered receipts, changed artifacts/policy, rejected model results and execution failures never grant AI approval. Legacy explicit human approval and owner override dispatches remain separate, auditable fallback mechanisms; the scheduler does not invoke them.

## Install and inspect

Prerequisites: Node 22+, Python 3, Git, `gh`, Codex CLI, and locally authenticated `codex`/`gh` sessions.

```sh
python3 automation/install-astra-agent.py
cat ~/.local/share/esports-astra-review/status.json
launchctl print gui/$(id -u)/com.taehyeong.esports-astra-review
```

The installer registers only the public key as a GitHub repository variable. The private key is mode 0600 beneath a mode 0700 directory. It installs a trusted coordinator copy outside the synchronized working folder. After changes to the coordinator, rerun the installer to update that copy. Model/tool failures retry after one hour; a rejection requires a new main commit. A file lock prevents overlapping runs.

Local verification logs, evidence, images, review JSON and receipts are kept under `~/.local/share/esports-astra-review/reviews/<SHA>/`. They are local review artifacts, not NERV content. Inspect specific blockers there and fix the source before retrying. Never edit a review into approval. To rotate keys, stop the agent, archive the old local keys securely, generate a new pair, and rerun the installer to register the new public key. Prior receipts then fail verification.

Disable automatic polling:

```sh
launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/com.taehyeong.esports-astra-review.plist
```

The public key authenticates the trusted local coordinator's assertion, not a cryptographic attestation from OpenAI. Protect the Mac and repository administration permissions. The reviewer provides an AI assessment; browser automation and screenshots do not establish real human usability study results or complete accessibility certification. All 235 currently unverified operation statuses remain disclosed as such.

## Archival records and case counts

Astra's second actual review identified unsupported regional display anchors and a duplicated event. `src/record-scope.js` conservatively excludes the entire legacy `visible-regional-*` family (160 records) from case search, map summaries and comparisons. The original 235-record graph, stable IDs and source lineage remain intact; 75 case records are displayed and 160 reference records are explicitly separated in the research appendix. The Gunsan event's auxiliary anchor is therefore not counted a second time. All operation statuses remain `needs_review`.

This is a presentation partition, not factual approval or deletion. A reference record must not be read as confirmed local participation or an exact venue. Reintroducing one requires specific official evidence, duplicate assessment and an explicit revision to the partition policy; an operational-status edit alone does not admit it. Geographic typology separately reports scope and coordinate eligibility (currently 28 regional cases, 23 coordinate-eligible and 5 without coordinates).
