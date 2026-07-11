CREATE TABLE legacy_entry_map (
    legacy_id INTEGER NOT NULL,
    v2_subject_id TEXT REFERENCES subject(subject_id) ON DELETE RESTRICT,
    staging_partition TEXT,
    state TEXT NOT NULL CHECK (state IN ('staged', 'mapped', 'excluded')),
    reason TEXT,
    audited_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    PRIMARY KEY (legacy_id),
    CHECK (
        (state = 'mapped' AND v2_subject_id IS NOT NULL AND staging_partition IS NULL) OR
        (state = 'staged' AND v2_subject_id IS NULL AND staging_partition IS NOT NULL) OR
        (state = 'excluded' AND v2_subject_id IS NULL AND staging_partition IS NULL AND reason IS NOT NULL)
    )
) STRICT;
CREATE UNIQUE INDEX legacy_entry_map_subject_idx
ON legacy_entry_map(v2_subject_id) WHERE state = 'mapped';
CREATE INDEX legacy_entry_map_partition_idx
ON legacy_entry_map(staging_partition) WHERE state = 'staged';

CREATE TRIGGER legacy_entry_map_no_delete
BEFORE DELETE ON legacy_entry_map
BEGIN SELECT RAISE(ABORT, 'legacy entry audit is append-only'); END;
