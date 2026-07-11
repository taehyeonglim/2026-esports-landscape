# Operations runbook

## Service levels and ownership

Source freshness tiers are inclusive maximum ages: **1h**, **6h**, **24h**, and **72h**. Each source is assigned exactly one registered tier; unknown tiers are stale and fail closed. The primary steward owns intake, review queues, scheduled publication, and incident coordination. The alternate steward assumes those duties when the primary is unavailable and records the handoff, current pointer, open reviews, and budget state.

Review cadence: triage new and failed items daily; review provisional, stale, and policy-affected items at least weekly; review source allowlists, independence clusters, and policy hashes monthly; perform a quarterly recovery drill and ADR review.

## Publication gate

A release may proceed only at these thresholds:

| Measure | Required |
| --- | ---: |
| Core coverage | >= 99% |
| False publications | 0 |
| Automatic mismerges | 0 |
| Quality-field coverage | >= 98% |
| Required schema-field coverage | 100% |

The same gate also requires valid schema, references, and checksums; zero PII findings and overdue reviews; `stop_requested=false`; and budget `PASS`. Missing measurement is a failure, not a default.

## Stop and withdrawal

Any steward may request a stop for suspected PII, invalid evidence, corruption, policy breach, or gate regression. On stop: freeze pointer advancement, preserve the control-plane audit record, open an incident, and assess the current public snapshot. For a harmful published record, issue an emergency **removal-only** snapshot from the last verified current pointer; it may delete unchanged records but may not modify or add records. If removal-only publication is unsafe, remove the public pointer and serve no current snapshot until recovery validates a replacement.

## Budget runbook

| Budget state | Action |
| --- | --- |
| `PASS` | Continue normal review and publish only after the full gate passes. |
| `SOFT` | Do not publish automatically. Primary steward reviews the budget event, reduces scope or obtains documented approval, then reruns the full gate. |
| `HARD` | Stop publication immediately, quarantine the affected candidate(s), notify both stewards, remediate or withdraw, and require a new `PASS` result before resuming. |

No budget state overrides the PII, quality, or stop controls.
