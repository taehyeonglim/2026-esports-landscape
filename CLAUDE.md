# Claude Code project entrypoint

Load the shared handoff context on every session:

- @NERV/README.md
- @NERV/PROJECT_STATUS.md

Then read the newest entries in `NERV/HANDOFF_LOG.md` before starting material work.

`NERV/` is the handoff surface left by Codex and other agents. Treat it as orientation, not as a substitute for Git, source files, schemas, tests, or GitHub state. Verify any status that may have changed before acting.

When Claude Code completes material work, follow the same handoff protocol described in `NERV/README.md`: refresh `NERV/PROJECT_STATUS.md`, prepend `NERV/HANDOFF_LOG.md`, record verification, and preserve unrelated workspace changes.

This project is fail-closed. Do not bypass source policy, minor-data protections, immutable snapshot rules, or recorded human approval gates. The canonical operational rules are in `docs/source-policy.md`, `docs/operations.md`, and `docs/pages-release.md`.
