# Data contract

## Scope and authority

`baseline/v2/site.v2.json` is the externalized, read-only v2 baseline. It contains **230** `entries` and **17** `regions`; those counts are migration invariants. Reviewed records created after that baseline live in `data/additions.v1.json`. `data/site.v3.json` is the generated v3 projection of the baseline plus those additions. Public releases are immutable snapshot bundles (`snapshots/<snapshot_id>/snapshot.json` plus `manifest.json`) selected only through `current.json`.

The dashboard has already externalized its baseline. This contract does **not** authorize an `index.html` change or a UI reimplementation.

## v2 → v3 mapping

| v2 | v3 | Rule |
| --- | --- | --- |
| `schema_version: 2` | `schema_version: 3` | Version changes only through the migration. |
| `meta.entry_count`, `meta.region_count` | published entry total, 17 regions, `meta.source_schema_version: 2`, and extraction/addition provenance | The v2 migration remains exactly 230 rows; `meta.entry_count` equals the generated baseline-plus-additions total. |
| `regions[]` | `regions[]` | Preserve region IDs and geographic/source metadata. |
| `entries[]` | `entries[]` | Preserve all 230 legacy rows and stable IDs; append only reviewed `data/additions.v1.json` records, then attach v3 lineage/evidence fields. |
| entry `evidence_ids` / source text | normalized evidence and source references | Every publishable claim must resolve to retained evidence and source IDs. |

A public immutable snapshot adds its `snapshot_id`, `schema_hash`, `policy_hash`, `revision`, and `epoch`; its manifest hashes every published byte. The mutable `data/site.v3.json` is not itself a publication receipt.

## Record identity and lifecycle

Every normalized subject has a stable opaque ID and exactly one kind:

`school`, `region`, `organization`, `venue`, `program`, or `university`.

Identity resolution is conservative: it may merge only when the kind and authoritative identity evidence agree; uncertain candidates stay separate and enter review. Source-to-subject relationships are `primary` or `related`.

`status` is lifecycle/publication state (`verified` or `provisional`). `confidence` is an evidence assessment (for example `high`, `medium`, or `low`). They are separate fields: confidence never silently upgrades status, and status never erases the evidence assessment.

## Required and quality fields

A published record requires `record_id`, `subject_id`, `status`, one or more claims, and non-empty `evidence_ids` and `source_ids`. Each claim requires `claim_id`, `kind`, `value`, `evidence_id`, and `source_id`. Evidence requires `evidence_id`, `source_id`, public `url`, `observed_at`, and a checksum. Sources require `source_id`, `tier`, and public `url`.

Publication fails closed unless all required schema fields are complete (100%), quality-field coverage is at least 98%, core coverage is at least 99%, false publications and automatic mismerges are both 0, all references/checksums/schema validation pass, PII findings and overdue reviews are 0, no stop is requested, and the budget result is `PASS`.
