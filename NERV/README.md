# NERV handoff hub

NERV is the repository-local handoff folder for Codex, Claude Code, and human maintainers. Its purpose is to make the project's current position understandable without reconstructing every prior agent session.

## Reading order

1. [`PROJECT_STATUS.md`](PROJECT_STATUS.md) — current project snapshot, verified progress, blockers, and next priorities.
2. [`HANDOFF_LOG.md`](HANDOFF_LOG.md) — newest-first history of material work and decisions.
3. [`../README.md`](../README.md) — product, architecture, data model, and operating commands.
4. Relevant policy or contract documents linked from the status page.

## Source-of-truth hierarchy

When information conflicts, use this order:

1. Current repository files, schemas, and generated validation results
2. Git and GitHub state
3. NERV status and handoff notes
4. Old chat or agent recollection

NERV should be repaired immediately when a higher-ranked source disproves it.

## Update protocol

After any material change to code, data, documentation, configuration, pull requests, releases, or project decisions:

1. Verify the actual result.
2. Refresh `PROJECT_STATUS.md`; replace stale facts rather than stacking snapshots.
3. Prepend one entry to `HANDOFF_LOG.md` with outcome, changed surfaces, verification, remaining work, and durable references.
4. Record exact commit or PR identifiers when they exist.
5. Keep secrets, PII, raw external bodies, transient discovery titles, and chat transcripts out of NERV.

Read-only analysis with no durable project or external-state change does not need a log entry.

## Mandatory session closeout gate

For project work, NERV handoff is part of delivery rather than an optional note. The normal completion path is:

1. Verify the task result.
2. Refresh `PROJECT_STATUS.md` and prepend `HANDOFF_LOG.md`.
3. Commit only task-owned changes on a task branch.
4. Push the branch, open the PR, and merge it into the default branch.
5. Synchronize local `main`, verify it matches `origin/main`, and check CI/release state.

Do not describe a session as complete while its work exists only locally, only on a branch, or only in an open PR. When delivery is genuinely blocked, preserve the work, record the exact blocker here, and never bypass repository or human-approval protections.

## Status vocabulary

- **Completed**: the requested change exists in the intended destination.
- **Verified**: a named check independently confirmed the result.
- **Pending**: work is known but has not been completed.
- **Blocked**: a named dependency or policy gate prevents completion.
