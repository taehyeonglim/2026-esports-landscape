# Recovery runbook

## Durable recovery units

A recoverable control-plane state is a verified SQLite checkpoint/backup paired with its publication receipt. The pair records the database checkpoint identity, `snapshot_id`, manifest hash, schema hash, policy hash, revision, epoch, gate report, and current-pointer value. Neither member alone authorizes recovery.

Before recovery, take a fresh copy of available state, run SQLite `integrity_check` and foreign-key checks, and verify every receipt hash against its immutable bundle. Never repair a database by editing a published bundle or receipt.

## Crash matrix

| Failure point | Required action |
| --- | --- |
| Before SQLite commit | Roll back; no receipt or pointer may be created. |
| After SQLite commit, before checkpoint/receipt pair | Checkpoint and reconstruct the receipt from committed audit data; do not publish until paired and verified. |
| After pair, before immutable bundle is complete | Discard incomplete staging; retain prior pointer; rebuild the identical bundle from the paired state. |
| After verified bundle, before pointer update | Keep the bundle immutable but unreachable; retain prior pointer and retry only with the recorded expected pointer. |
| During/after pointer update | Read and validate `current.json`; if it is unreadable or mismatched, remove the pointer and recover from the last valid ancestor. |
| Database corruption or lost current bundle | Restore the newest valid checkpoint/receipt pair, then replay forward. |

## Forward replay

Recovery starts at the newest valid ancestor: a checkpoint/receipt pair whose database checks, receipt, bundle manifest, snapshot bytes, and policy/schema hashes all verify. Replay committed, ordered mutations forward from that ancestor, reapplying sanitization, identity, policy, review, and quality decisions. Recreate snapshots deterministically, verify each bundle, and update the pointer only with the expected prior snapshot ID (CAS). Do not mutate an old snapshot to make it match current state.

## Pointer and PII incidents

Immutable snapshots are never edited. In an emergency, a replacement snapshot is removal-only: surviving records must be byte-for-byte unchanged from the prior public content. If that cannot safely remove the exposure, delete the public `current.json` pointer only; do not redirect it to an unverified bundle.

For a PII incident: (1) request stop and disable pointer advancement; (2) identify affected opaque record/evidence IDs without copying PII into tickets; (3) remove affected public records by a verified removal-only snapshot or remove the pointer; (4) delete the affected control-plane values and rotate/revoke tokens, deploy keys, webhooks, credentials, and any secret that could expose the material; (5) purge GitHub Pages deployment artifacts/caches by deploying a clean state or disabling Pages until clean; (6) verify public URLs and Pages no longer expose the data; (7) document the incident with safe metadata and require steward review before restart.
