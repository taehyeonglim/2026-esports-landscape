# Codex collaboration rules

This repository uses `NERV/` as the shared handoff surface between Codex, Claude Code, and human maintainers.

## Required context

Before making a material change, read:

1. `README.md`
2. `NERV/README.md`
3. `NERV/PROJECT_STATUS.md`
4. The newest entries in `NERV/HANDOFF_LOG.md`

Repository files, Git history, and test output are authoritative. NERV is a curated briefing layer and must be corrected when it disagrees with those sources.

## Mandatory NERV closeout and delivery routine

The repository owner's standing instruction is that a Codex project session does not end with task-owned work left only in the working tree, in a local commit, on an unmerged branch, or in an open PR.

Before the final response for work that changes code, data, documentation, configuration, GitHub state, release state, or another durable project decision:

1. Inspect Git status and preserve unrelated user changes.
2. Run verification proportional to the change.
3. Update `NERV/PROJECT_STATUS.md` with the current date, canonical branch/commit, verified progress, test results, blockers, and next priorities.
4. Prepend a concise entry to `NERV/HANDOFF_LOG.md` using its template.
5. Stage only task-owned files and commit them intentionally.
6. Push the task branch to `origin`.
7. Open the appropriate PR, make it ready when the work is verified, and merge it into the default branch. Do not stop at commit-only, push-only, or open-PR-only state.
8. Synchronize the local default branch, verify that it matches the remote default branch, and clean up the merged task branch when safe.
9. Check the resulting CI/release state and record it accurately in NERV. A policy gate that blocks deployment must never be described as a successful deployment.
10. Mention the NERV handoff, commit, merge, push, and any remaining blocker in the final response.

If authentication, conflicts, failed verification, required human input, or a policy gate makes commit, push, or merge impossible, do not bypass the protection. Record the exact blocker in NERV, preserve a recoverable branch when possible, and report the incomplete delivery explicitly before ending.

A purely conversational or read-only turn with no durable project decision does not require an empty commit. Any durable decision or progress that the next session needs must be handed off and delivered through the routine above.

## Safety and hygiene

- Preserve unrelated user changes and call them out in the workspace note when they affect the next agent.
- Do not put secrets, credentials, personal data, raw external response bodies, full article titles collected only for transient review, or chat transcripts in NERV.
- Keep NERV concise. Link to canonical repository files instead of copying long specifications.
- Update an existing status statement instead of accumulating contradictory snapshots in `PROJECT_STATUS.md`.
- Keep `HANDOFF_LOG.md` newest-first and append-only except for correcting factual errors.
