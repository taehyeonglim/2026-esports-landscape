# ADR 0001: Private SQLite control plane and public immutable projection

- **Status:** Accepted
- **Date:** 2026-07-11

## Context

The pipeline must retain reviewable operational state while publishing verifiable public data without exposing private candidates, raw source bytes, or PII. The dashboard consumes externalized baseline/v2 and v3 data; this ADR does not alter `index.html` or define a UI.

## Decision

Use private SQLite as the control plane for candidates, identity decisions, reviews, policy state, audit events, and recovery checkpoints. Publish only a sanitized immutable projection as `snapshots/<snapshot_id>/snapshot.json` with `manifest.json`; expose it through a small `current.json` pointer.

Each snapshot is content-addressed from canonical content plus schema hash, policy hash, revision, and epoch. Stage the complete bundle, fsync it, read it back, and verify its manifest before making it reachable. Write the SQLite checkpoint and its receipt in the **same commit**: the receipt binds checkpoint identity to snapshot ID, manifest hash, policy/schema hashes, revision, epoch, and gate report. A snapshot without that paired receipt is not publishable.

Update `current.json` last. The update is a compare-and-swap against the expected current snapshot ID under the pointer lock. A failed comparison leaves the prior pointer intact. Emergency publication is removal-only: records retained from the prior projection must be unchanged, and new records are forbidden.

## Consequences

- Public consumers receive reproducible, hash-verifiable files and never query SQLite.
- Private state can support review and recovery without becoming public data.
- Orphaned immutable bundles may exist after a crash but are harmless until a valid pointer references them.
- Publication is deliberately blocked when the checkpoint/receipt pair, gate, or CAS precondition is absent.

## Alternatives considered

1. **Publish SQLite directly:** rejected because it exposes control-plane structure and private/review data, is not browser-friendly, and is difficult to make immutable.
2. **Overwrite a single public JSON file:** rejected because readers can observe partial or unreceipted state and historical verification is lost.
3. **Public database/API as the source of truth:** rejected because it expands credentials, operational exposure, and outage coupling; the static projection is sufficient for consumers.
4. **Pointer before bundle verification:** rejected because it can make incomplete or corrupt content current.

## Re-evaluation triggers

Reassess this ADR when public data exceeds static-hosting limits, consumer queries require server-side access control, an atomic pointer primitive cannot be provided by the publication target, retention or privacy law changes, cross-region recovery requirements change, or schema/policy evolution makes a single SQLite control plane inadequate.
