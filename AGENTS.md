# Codex collaboration rules

This repository uses `NERV/` as the shared handoff surface between Codex, Claude Code, and human maintainers.

## Required context

Before making a material change, read:

1. `README.md`
2. `NERV/README.md`
3. `NERV/PROJECT_STATUS.md`
4. The newest entries in `NERV/HANDOFF_LOG.md`

Repository files, Git history, and test output are authoritative. NERV is a curated briefing layer and must be corrected when it disagrees with those sources.

## Required handoff after material work

Before the final response for work that changes code, data, documentation, configuration, GitHub state, release state, or another durable project decision:

1. Run verification proportional to the change.
2. Update `NERV/PROJECT_STATUS.md` with the current date, branch/commit, verified progress, test results, blockers, and next priorities.
3. Prepend a concise entry to `NERV/HANDOFF_LOG.md` using its template.
4. Distinguish clearly between completed, verified, pending, and blocked work. A policy gate that blocks deployment must never be described as a successful deployment.
5. Mention the NERV update in the final response.

Purely read-only questions that do not change project or external state do not require a handoff entry.

## Safety and hygiene

- Preserve unrelated user changes and call them out in the workspace note when they affect the next agent.
- Do not put secrets, credentials, personal data, raw external response bodies, full article titles collected only for transient review, or chat transcripts in NERV.
- Keep NERV concise. Link to canonical repository files instead of copying long specifications.
- Update an existing status statement instead of accumulating contradictory snapshots in `PROJECT_STATUS.md`.
- Keep `HANDOFF_LOG.md` newest-first and append-only except for correcting factual errors.
