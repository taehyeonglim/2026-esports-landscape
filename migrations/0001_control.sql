PRAGMA foreign_keys = ON;

CREATE TABLE system_state (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
) STRICT;

CREATE TABLE mutation_request (
    command_id TEXT PRIMARY KEY,
    request_kind TEXT NOT NULL,
    input_revision TEXT NOT NULL,
    policy_version TEXT NOT NULL,
    policy_epoch INTEGER NOT NULL CHECK (policy_epoch >= 0),
    status TEXT NOT NULL CHECK (status IN ('queued', 'running', 'applied', 'rejected', 'failed')),
    payload_json TEXT NOT NULL CHECK (json_valid(payload_json)),
    receipt_json TEXT CHECK (receipt_json IS NULL OR json_valid(receipt_json)),
    error_code TEXT,
    parent_git_sha TEXT CHECK (
        parent_git_sha IS NULL OR (
            length(parent_git_sha) = 40
            AND parent_git_sha = lower(parent_git_sha)
            AND parent_git_sha NOT GLOB '*[^0-9a-f]*'
        )
    ),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    started_at TEXT,
    applied_at TEXT,
    applied_sequence INTEGER,
    CHECK (status != 'queued' OR parent_git_sha IS NULL),
    CHECK (status NOT IN ('running', 'applied') OR parent_git_sha IS NOT NULL),
    CHECK ((status = 'applied') = (receipt_json IS NOT NULL)),
    CHECK ((status = 'applied') = (applied_sequence IS NOT NULL)),
    CHECK (status != 'applied' OR applied_at IS NOT NULL),
    CHECK (status != 'applied' OR COALESCE(json_extract(receipt_json, '$.command_id') = command_id, 0)),
    CHECK (status != 'applied' OR COALESCE(json_extract(receipt_json, '$.status') = 'applied', 0)),
    CHECK (status != 'applied' OR COALESCE(json_extract(receipt_json, '$.applied_at') = applied_at, 0)),
    CHECK (status != 'applied' OR applied_sequence >= 1),
    CHECK (status != 'failed' OR error_code = 'handler_failed'),
    CHECK (status != 'failed' OR receipt_json IS NULL)
) STRICT;
CREATE INDEX mutation_request_status_idx ON mutation_request(status, created_at);
CREATE UNIQUE INDEX mutation_request_applied_sequence_uidx
    ON mutation_request(applied_sequence)
    WHERE applied_sequence IS NOT NULL;
CREATE TRIGGER mutation_request_terminal_append_only_delete
BEFORE DELETE ON mutation_request WHEN OLD.status IN ('applied', 'failed')
BEGIN SELECT RAISE(ABORT, 'terminal mutation request is append-only'); END;
CREATE TRIGGER mutation_request_parent_git_sha_queue_only
BEFORE INSERT ON mutation_request WHEN NEW.parent_git_sha IS NOT NULL
BEGIN SELECT RAISE(ABORT, 'mutation request parent git SHA may only bind on first apply'); END;
CREATE TRIGGER mutation_request_identity_payload_immutable
BEFORE UPDATE OF command_id, request_kind, input_revision, policy_version, policy_epoch, payload_json ON mutation_request
WHEN NEW.command_id IS NOT OLD.command_id
OR NEW.request_kind IS NOT OLD.request_kind
OR NEW.input_revision IS NOT OLD.input_revision
OR NEW.policy_version IS NOT OLD.policy_version
OR NEW.policy_epoch IS NOT OLD.policy_epoch
OR NEW.payload_json IS NOT OLD.payload_json
BEGIN SELECT RAISE(ABORT, 'mutation request command identity and payload are immutable'); END;
CREATE TRIGGER mutation_request_parent_git_sha_bound_on_first_apply
BEFORE UPDATE OF parent_git_sha ON mutation_request
WHEN NEW.parent_git_sha IS NOT OLD.parent_git_sha
AND (
    OLD.status <> 'queued'
    OR OLD.parent_git_sha IS NOT NULL
    OR NEW.status NOT IN ('running', 'failed')
    OR NEW.parent_git_sha IS NULL
)
BEGIN SELECT RAISE(ABORT, 'mutation request parent git SHA may only bind on first apply'); END;
CREATE TRIGGER mutation_request_terminal_immutable
BEFORE UPDATE ON mutation_request
WHEN OLD.status IN ('applied', 'failed')
AND (
    NEW.command_id IS NOT OLD.command_id
    OR NEW.request_kind IS NOT OLD.request_kind
    OR NEW.input_revision IS NOT OLD.input_revision
    OR NEW.policy_version IS NOT OLD.policy_version
    OR NEW.policy_epoch IS NOT OLD.policy_epoch
    OR NEW.status IS NOT OLD.status
    OR NEW.payload_json IS NOT OLD.payload_json
    OR NEW.receipt_json IS NOT OLD.receipt_json
    OR NEW.error_code IS NOT OLD.error_code
    OR NEW.created_at IS NOT OLD.created_at
    OR NEW.started_at IS NOT OLD.started_at
    OR NEW.applied_at IS NOT OLD.applied_at
    OR NEW.applied_sequence IS NOT OLD.applied_sequence
    OR NEW.parent_git_sha IS NOT OLD.parent_git_sha
)
BEGIN SELECT RAISE(ABORT, 'terminal mutation request is append-only'); END;
CREATE TRIGGER mutation_request_status_forward_only
BEFORE UPDATE OF status ON mutation_request
WHEN NOT (
    (OLD.status = 'queued' AND NEW.status = 'running')
    OR (OLD.status = 'running' AND NEW.status = 'applied')
    OR (OLD.status = 'queued' AND NEW.status = 'failed')
)
BEGIN SELECT RAISE(ABORT, 'mutation request status transition is invalid'); END;
CREATE TRIGGER mutation_request_applied_sequence_required
BEFORE UPDATE OF status ON mutation_request
WHEN NEW.status = 'applied'
AND NEW.applied_sequence IS NULL
BEGIN SELECT RAISE(ABORT, 'applied mutation request requires monotonic sequence'); END;
CREATE TRIGGER mutation_request_applied_sequence_insert_guard
BEFORE INSERT ON mutation_request
WHEN NEW.applied_sequence IS NOT NULL
BEGIN SELECT RAISE(ABORT, 'mutation request applied sequence is adapter-owned'); END;
CREATE TRIGGER mutation_request_applied_sequence_monotonic
BEFORE UPDATE OF applied_sequence ON mutation_request
WHEN NEW.applied_sequence IS NOT NULL
AND (
    OLD.applied_sequence IS NOT NULL
    OR NEW.status <> 'applied'
    OR NEW.applied_sequence <> (SELECT COALESCE(MAX(applied_sequence), 0) + 1 FROM mutation_request)
)
BEGIN SELECT RAISE(ABORT, 'applied mutation request sequence must be immutable and monotonic'); END;

CREATE TABLE subject (
    subject_id TEXT PRIMARY KEY CHECK (
        length(subject_id) = 36
        AND subject_id = lower(subject_id)
        AND substr(subject_id, 9, 1) = '-'
        AND substr(subject_id, 14, 1) = '-'
        AND substr(subject_id, 19, 1) = '-'
        AND substr(subject_id, 24, 1) = '-'
        AND replace(subject_id, '-', '') NOT GLOB '*[^0-9a-f]*'
        AND authority_subject_uuid(kind, authority_namespace, authority_key) IS NOT NULL
        AND subject_id = authority_subject_uuid(kind, authority_namespace, authority_key)
    ),
    kind TEXT NOT NULL CHECK (kind IN ('school', 'region', 'organization', 'venue', 'program', 'university')),
    authority_namespace TEXT NOT NULL CHECK (
        (kind = 'school' AND authority_namespace = 'school.neis.go.kr')
        OR (kind = 'region' AND authority_namespace = 'region.korea.go.kr')
        OR (kind = 'organization' AND authority_namespace = 'organization.registry.go.kr')
        OR (kind = 'venue' AND authority_namespace = 'localdata.go.kr')
        OR (kind = 'program' AND authority_namespace = 'event.registry.go.kr')
        OR (kind = 'university' AND authority_namespace = 'university.ac.kr')
    ),
    authority_key TEXT NOT NULL CHECK (length(authority_key) > 0),
    provenance_digest TEXT NOT NULL CHECK (
        length(provenance_digest) = 64
        AND provenance_digest = lower(provenance_digest)
        AND provenance_digest NOT GLOB '*[^0-9a-f]*'
    ),
    canonical_name TEXT NOT NULL,
    subtype TEXT,
    operator_subject_id TEXT REFERENCES subject(subject_id) ON DELETE RESTRICT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    UNIQUE(kind, authority_namespace, authority_key)
) STRICT;
CREATE TABLE subject_subtype (
    kind TEXT NOT NULL CHECK (kind IN ('school', 'region', 'organization', 'venue', 'program', 'university')),
    subtype TEXT NOT NULL,
    PRIMARY KEY (kind, subtype)
) STRICT;
CREATE TRIGGER subject_subtype_must_match_insert
BEFORE INSERT ON subject WHEN NEW.subtype IS NOT NULL
AND NOT EXISTS (SELECT 1 FROM subject_subtype WHERE kind = NEW.kind AND subtype = NEW.subtype)
BEGIN SELECT RAISE(ABORT, 'unknown subject subtype'); END;
CREATE TRIGGER subject_subtype_must_match_update
BEFORE UPDATE OF kind, subtype ON subject WHEN NEW.subtype IS NOT NULL
AND NOT EXISTS (SELECT 1 FROM subject_subtype WHERE kind = NEW.kind AND subtype = NEW.subtype)
BEGIN SELECT RAISE(ABORT, 'unknown subject subtype'); END;
CREATE TRIGGER venue_requires_operator_insert
BEFORE INSERT ON subject WHEN NEW.kind = 'venue'
AND (NEW.operator_subject_id IS NULL OR NOT EXISTS (
    SELECT 1 FROM subject WHERE subject_id = NEW.operator_subject_id AND kind = 'organization'
))
BEGIN SELECT RAISE(ABORT, 'venue requires organization operator'); END;
CREATE TRIGGER venue_requires_operator_update
BEFORE UPDATE OF kind, operator_subject_id ON subject WHEN NEW.kind = 'venue'
AND (NEW.operator_subject_id IS NULL OR NOT EXISTS (
    SELECT 1 FROM subject WHERE subject_id = NEW.operator_subject_id AND kind = 'organization'
))
BEGIN SELECT RAISE(ABORT, 'venue requires organization operator'); END;
CREATE TRIGGER non_venue_operator_must_be_null_insert
BEFORE INSERT ON subject WHEN NEW.kind <> 'venue' AND NEW.operator_subject_id IS NOT NULL
BEGIN SELECT RAISE(ABORT, 'only venues may have an operator'); END;
CREATE TRIGGER non_venue_operator_must_be_null_update
BEFORE UPDATE OF kind, operator_subject_id ON subject
WHEN NEW.kind <> 'venue' AND NEW.operator_subject_id IS NOT NULL
BEGIN SELECT RAISE(ABORT, 'only venues may have an operator'); END;
CREATE TRIGGER organization_operator_kind_immutable
BEFORE UPDATE OF kind ON subject
WHEN OLD.kind = 'organization'
AND NEW.kind <> 'organization'
AND EXISTS (
    SELECT 1 FROM subject
    WHERE kind = 'venue' AND operator_subject_id = OLD.subject_id
)
BEGIN SELECT RAISE(ABORT, 'venue operator must remain an organization'); END;
CREATE TRIGGER subject_identity_immutable
BEFORE UPDATE OF subject_id, kind, authority_namespace, authority_key, provenance_digest, operator_subject_id ON subject
BEGIN SELECT RAISE(ABORT, 'subject identity is append-only'); END;
CREATE TRIGGER subject_append_only_delete
BEFORE DELETE ON subject
BEGIN SELECT RAISE(ABORT, 'subject is append-only'); END;

CREATE TABLE candidate (
    candidate_id TEXT PRIMARY KEY,
    status TEXT NOT NULL CHECK (status IN ('private', 'review', 'rejected', 'reverification_pending')),
    summary TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
) STRICT;
CREATE TABLE candidate_subject (
    candidate_id TEXT NOT NULL REFERENCES candidate(candidate_id) ON DELETE CASCADE,
    subject_id TEXT NOT NULL REFERENCES subject(subject_id) ON DELETE RESTRICT,
    relation TEXT NOT NULL CHECK (relation IN ('primary', 'related')),
    active INTEGER NOT NULL DEFAULT 1 CHECK (typeof(active) = 'integer' AND active IN (0, 1)),
    PRIMARY KEY(candidate_id, subject_id)
) STRICT;
CREATE UNIQUE INDEX candidate_one_active_primary_idx
ON candidate_subject(candidate_id) WHERE relation = 'primary' AND active = 1;

CREATE TABLE review_identity (
    review_identity_id TEXT PRIMARY KEY,
    candidate_id TEXT NOT NULL REFERENCES candidate(candidate_id) ON DELETE CASCADE,
    relation TEXT NOT NULL DEFAULT 'primary' CHECK (relation = 'primary'),
    proposed_kind TEXT NOT NULL CHECK (proposed_kind IN ('school', 'region', 'organization', 'venue', 'program', 'university')),
    hint_digest TEXT NOT NULL CHECK (length(hint_digest) = 64 AND hint_digest = lower(hint_digest) AND hint_digest NOT GLOB '*[^0-9a-f]*'),
    reason_code TEXT NOT NULL CHECK (reason_code = 'authority_key_missing'),
    status TEXT NOT NULL CHECK (status IN ('active', 'resolved', 'superseded')),
    supersedes_id TEXT REFERENCES review_identity(review_identity_id) ON DELETE RESTRICT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    resolved_at TEXT,
    CHECK ((status = 'active') = (resolved_at IS NULL))
) STRICT;
CREATE UNIQUE INDEX review_identity_one_active_primary_idx
ON review_identity(candidate_id) WHERE status = 'active';

CREATE TABLE identity_proposal (
    proposal_id TEXT PRIMARY KEY,
    candidate_id TEXT NOT NULL REFERENCES candidate(candidate_id) ON DELETE CASCADE,
    review_identity_id TEXT NOT NULL REFERENCES review_identity(review_identity_id) ON DELETE RESTRICT,
    relation TEXT NOT NULL DEFAULT 'related' CHECK (relation = 'related'),
    proposed_kind TEXT NOT NULL CHECK (proposed_kind IN ('school', 'region', 'organization', 'venue', 'program', 'university')),
    hint_digest TEXT NOT NULL CHECK (length(hint_digest) = 64 AND hint_digest = lower(hint_digest) AND hint_digest NOT GLOB '*[^0-9a-f]*'),
    reason TEXT NOT NULL CHECK (reason IN ('possible_match', 'manual_match')),
    status TEXT NOT NULL CHECK (status IN ('active', 'accepted', 'rejected', 'superseded')),
    supersedes_id TEXT REFERENCES identity_proposal(proposal_id) ON DELETE RESTRICT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    resolved_at TEXT,
    CHECK ((status = 'active') = (resolved_at IS NULL))
) STRICT;
CREATE TRIGGER identity_proposal_review_must_belong_to_candidate_insert
BEFORE INSERT ON identity_proposal
WHEN NOT EXISTS (
    SELECT 1 FROM review_identity
    WHERE review_identity_id = NEW.review_identity_id AND candidate_id = NEW.candidate_id
)
BEGIN SELECT RAISE(ABORT, 'identity proposal review must belong to candidate'); END;
CREATE TRIGGER identity_proposal_review_must_belong_to_candidate_update
BEFORE UPDATE OF candidate_id, review_identity_id ON identity_proposal
WHEN NOT EXISTS (
    SELECT 1 FROM review_identity
    WHERE review_identity_id = NEW.review_identity_id AND candidate_id = NEW.candidate_id
)
BEGIN SELECT RAISE(ABORT, 'identity proposal review must belong to candidate'); END;
CREATE TRIGGER review_identity_initial_status_must_be_active
BEFORE INSERT ON review_identity WHEN NEW.status <> 'active'
BEGIN SELECT RAISE(ABORT, 'review identity must begin active'); END;
CREATE TRIGGER identity_proposal_initial_status_must_be_active
BEFORE INSERT ON identity_proposal WHEN NEW.status <> 'active'
BEGIN SELECT RAISE(ABORT, 'identity proposal must begin active'); END;
CREATE TRIGGER review_identity_supersedes_same_candidate_insert
BEFORE INSERT ON review_identity WHEN NEW.supersedes_id IS NOT NULL
AND NOT EXISTS (
    SELECT 1 FROM review_identity
    WHERE review_identity_id = NEW.supersedes_id AND candidate_id = NEW.candidate_id
)
BEGIN SELECT RAISE(ABORT, 'review supersedes identity must belong to candidate'); END;
CREATE TRIGGER review_identity_supersedes_same_candidate_update
BEFORE UPDATE OF candidate_id, supersedes_id ON review_identity WHEN NEW.supersedes_id IS NOT NULL
AND NOT EXISTS (
    SELECT 1 FROM review_identity
    WHERE review_identity_id = NEW.supersedes_id AND candidate_id = NEW.candidate_id
)
BEGIN SELECT RAISE(ABORT, 'review supersedes identity must belong to candidate'); END;
CREATE TRIGGER identity_proposal_supersedes_same_candidate_insert
BEFORE INSERT ON identity_proposal WHEN NEW.supersedes_id IS NOT NULL
AND NOT EXISTS (
    SELECT 1 FROM identity_proposal
    WHERE proposal_id = NEW.supersedes_id AND candidate_id = NEW.candidate_id
)
BEGIN SELECT RAISE(ABORT, 'proposal supersedes identity must belong to candidate'); END;
CREATE TRIGGER identity_proposal_supersedes_same_candidate_update
BEFORE UPDATE OF candidate_id, supersedes_id ON identity_proposal WHEN NEW.supersedes_id IS NOT NULL
AND NOT EXISTS (
    SELECT 1 FROM identity_proposal
    WHERE proposal_id = NEW.supersedes_id AND candidate_id = NEW.candidate_id
)
BEGIN SELECT RAISE(ABORT, 'proposal supersedes identity must belong to candidate'); END;
CREATE TABLE identity_link_receipt (
    identity_link_receipt_id TEXT PRIMARY KEY,
    candidate_id TEXT NOT NULL REFERENCES candidate(candidate_id) ON DELETE CASCADE,
    subject_id TEXT NOT NULL REFERENCES subject(subject_id) ON DELETE RESTRICT,
    attestation_type TEXT NOT NULL CHECK (attestation_type IN ('human_review', 'authority_mapping')),
    review_identity_id TEXT REFERENCES review_identity(review_identity_id) ON DELETE RESTRICT,
    actor_id TEXT NOT NULL,
    command_id TEXT NOT NULL,
    resulting_version INTEGER NOT NULL CHECK (resulting_version >= 0),
    authority_identity_digest TEXT NOT NULL CHECK (
        length(authority_identity_digest) = 64
        AND authority_identity_digest = lower(authority_identity_digest)
        AND authority_identity_digest NOT GLOB '*[^0-9a-f]*'
    ),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    UNIQUE(candidate_id, review_identity_id),
    CHECK (
        (attestation_type = 'human_review' AND review_identity_id IS NOT NULL)
        OR (attestation_type = 'authority_mapping' AND review_identity_id IS NULL)
    )
) STRICT;
CREATE TRIGGER identity_link_receipt_human_binding_insert
BEFORE INSERT ON identity_link_receipt
WHEN NEW.attestation_type = 'human_review'
AND NOT EXISTS (
    SELECT 1
    FROM review_identity ri
    JOIN subject s ON s.subject_id = NEW.subject_id
    WHERE ri.review_identity_id = NEW.review_identity_id
      AND ri.candidate_id = NEW.candidate_id
      AND ri.status = 'active'
      AND ri.proposed_kind = s.kind
      AND s.provenance_digest = NEW.authority_identity_digest
)
BEGIN SELECT RAISE(ABORT, 'human identity receipt must bind an active exact review and authority subject'); END;
CREATE TRIGGER identity_link_receipt_human_adapter_insert
BEFORE INSERT ON identity_link_receipt
WHEN NEW.attestation_type = 'human_review'
AND COALESCE(review_transition_authorized(
    NEW.candidate_id,
    NEW.review_identity_id,
    'active',
    'human_review_receipt',
    NEW.resulting_version - 1
), 0) = 0
BEGIN SELECT RAISE(ABORT, 'human identity receipt requires command adapter'); END;
CREATE TRIGGER identity_link_receipt_append_only_update
BEFORE UPDATE ON identity_link_receipt
BEGIN SELECT RAISE(ABORT, 'identity link receipt is append-only'); END;
CREATE TRIGGER identity_link_receipt_append_only_delete
BEFORE DELETE ON identity_link_receipt
BEGIN SELECT RAISE(ABORT, 'identity link receipt is append-only'); END;
CREATE TRIGGER review_identity_update_adapter_only
BEFORE UPDATE ON review_identity
WHEN NEW.review_identity_id IS NOT OLD.review_identity_id
OR NEW.candidate_id IS NOT OLD.candidate_id
OR NEW.relation IS NOT OLD.relation
OR NEW.proposed_kind IS NOT OLD.proposed_kind
OR NEW.hint_digest IS NOT OLD.hint_digest
OR NEW.reason_code IS NOT OLD.reason_code
OR NEW.supersedes_id IS NOT OLD.supersedes_id
OR NEW.created_at IS NOT OLD.created_at
OR OLD.status <> 'active'
OR NEW.status NOT IN ('resolved', 'superseded')
OR NEW.resolved_at IS NULL
OR (
    NEW.status = 'resolved'
    AND NOT EXISTS (
        SELECT 1 FROM identity_link_receipt
        WHERE candidate_id = NEW.candidate_id
          AND review_identity_id = NEW.review_identity_id
          AND attestation_type = 'human_review'
    )
)
OR COALESCE(review_transition_authorized(
    NEW.candidate_id,
    NEW.review_identity_id,
    OLD.status,
    NEW.status,
    (SELECT version FROM review_aggregate WHERE candidate_id = NEW.candidate_id)
), 0) = 0
BEGIN SELECT RAISE(ABORT, 'review update requires command adapter'); END;
CREATE TRIGGER review_identity_append_only_delete
BEFORE DELETE ON review_identity
BEGIN SELECT RAISE(ABORT, 'review identity is append-only'); END;
CREATE TRIGGER identity_proposal_update_adapter_only
BEFORE UPDATE ON identity_proposal
WHEN NEW.proposal_id IS NOT OLD.proposal_id
OR NEW.candidate_id IS NOT OLD.candidate_id
OR NEW.review_identity_id IS NOT OLD.review_identity_id
OR NEW.relation IS NOT OLD.relation
OR NEW.proposed_kind IS NOT OLD.proposed_kind
OR NEW.hint_digest IS NOT OLD.hint_digest
OR NEW.reason IS NOT OLD.reason
OR NEW.supersedes_id IS NOT OLD.supersedes_id
OR NEW.created_at IS NOT OLD.created_at
OR OLD.status <> 'active'
OR NEW.status NOT IN ('accepted', 'rejected', 'superseded')
OR NEW.resolved_at IS NULL
OR COALESCE(review_transition_authorized(
    NEW.candidate_id,
    NEW.proposal_id,
    OLD.status,
    NEW.status,
    (SELECT version FROM review_aggregate WHERE candidate_id = NEW.candidate_id)
), 0) = 0
BEGIN SELECT RAISE(ABORT, 'proposal update requires command adapter'); END;
CREATE TRIGGER identity_proposal_append_only_delete
BEFORE DELETE ON identity_proposal
BEGIN SELECT RAISE(ABORT, 'identity proposal is append-only'); END;

CREATE TRIGGER candidate_subject_primary_insert_adapter_only
BEFORE INSERT ON candidate_subject
WHEN NEW.relation = 'primary' AND NEW.active = 1
AND (
    (SELECT count(*) FROM identity_link_receipt ilr
     WHERE ilr.candidate_id = NEW.candidate_id
       AND ilr.subject_id = NEW.subject_id
       AND ilr.attestation_type = 'human_review') <> 1
    OR COALESCE(review_transition_authorized(
        NEW.candidate_id,
        (SELECT review_identity_id FROM identity_link_receipt
         WHERE candidate_id = NEW.candidate_id
           AND subject_id = NEW.subject_id
           AND attestation_type = 'human_review'),
        'active',
        'primary_link',
        (SELECT COALESCE(version, 0) FROM review_aggregate WHERE candidate_id = NEW.candidate_id)
    ), 0) = 0
)
BEGIN SELECT RAISE(ABORT, 'active primary edge requires an adapter-owned exact identity receipt'); END;
CREATE TRIGGER candidate_subject_append_only_update
BEFORE UPDATE ON candidate_subject
BEGIN SELECT RAISE(ABORT, 'candidate subject link is append-only'); END;
CREATE TRIGGER candidate_subject_append_only_delete
BEFORE DELETE ON candidate_subject
BEGIN SELECT RAISE(ABORT, 'candidate subject link is append-only'); END;
CREATE TRIGGER no_active_review_with_active_primary_edge_insert
BEFORE INSERT ON review_identity
WHEN NEW.status = 'active'
AND EXISTS (
    SELECT 1 FROM candidate_subject
    WHERE candidate_id = NEW.candidate_id AND relation = 'primary' AND active = 1
)
BEGIN SELECT RAISE(ABORT, 'active primary review conflicts with active primary edge'); END;
CREATE TRIGGER no_active_review_with_active_primary_edge_update
BEFORE UPDATE OF candidate_id, status ON review_identity
WHEN NEW.status = 'active'
AND EXISTS (
    SELECT 1 FROM candidate_subject
    WHERE candidate_id = NEW.candidate_id AND relation = 'primary' AND active = 1
)
BEGIN SELECT RAISE(ABORT, 'active primary review conflicts with active primary edge'); END;

CREATE TABLE review_aggregate (
    candidate_id TEXT PRIMARY KEY REFERENCES candidate(candidate_id) ON DELETE CASCADE,
    version INTEGER NOT NULL DEFAULT 0 CHECK (version >= 0),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
) STRICT;
CREATE TRIGGER review_aggregate_insert_adapter_only
BEFORE INSERT ON review_aggregate
WHEN NEW.version <> 0
OR review_transition_authorized(
    NEW.candidate_id,
    '__review_aggregate__',
    0,
    'increment',
    0
) = 0
BEGIN SELECT RAISE(ABORT, 'review aggregate insert requires command adapter'); END;
CREATE TRIGGER review_aggregate_update_adapter_only
BEFORE UPDATE ON review_aggregate
WHEN NEW.candidate_id IS NOT OLD.candidate_id
OR NEW.version <> OLD.version + 1
OR review_transition_authorized(
    NEW.candidate_id,
    '__review_aggregate__',
    OLD.version,
    'increment',
    OLD.version
) = 0
BEGIN SELECT RAISE(ABORT, 'review aggregate update requires command adapter'); END;
CREATE TRIGGER review_aggregate_append_only_delete
BEFORE DELETE ON review_aggregate
BEGIN SELECT RAISE(ABORT, 'review aggregate is append-only'); END;
CREATE TABLE review_command_receipt (
    command_id TEXT PRIMARY KEY,
    candidate_id TEXT NOT NULL REFERENCES candidate(candidate_id) ON DELETE CASCADE,
    command_json TEXT NOT NULL CHECK (json_valid(command_json)),
    receipt_json TEXT NOT NULL CHECK (json_valid(receipt_json)),
    resulting_version INTEGER NOT NULL CHECK (resulting_version >= 0),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    CHECK (json_extract(command_json, '$.command_id') = command_id),
    CHECK (json_extract(receipt_json, '$.command_id') = command_id),
    CHECK (json_extract(receipt_json, '$.resulting_version') = resulting_version)
) STRICT;
CREATE INDEX review_command_receipt_candidate_idx ON review_command_receipt(candidate_id, resulting_version);
CREATE TRIGGER review_command_receipt_insert_adapter_only
BEFORE INSERT ON review_command_receipt
WHEN review_transition_authorized(
    NEW.candidate_id,
    NEW.command_id,
    'active',
    'receipt',
    NEW.resulting_version
) = 0
BEGIN SELECT RAISE(ABORT, 'review command receipt insert requires command adapter'); END;
CREATE TRIGGER review_command_receipt_append_only_update
BEFORE UPDATE ON review_command_receipt
BEGIN SELECT RAISE(ABORT, 'review command receipt is append-only'); END;
CREATE TRIGGER review_command_receipt_append_only_delete
BEFORE DELETE ON review_command_receipt
BEGIN SELECT RAISE(ABORT, 'review command receipt is append-only'); END;

CREATE TABLE event (
    event_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    organizer_subject_id TEXT REFERENCES subject(subject_id) ON DELETE RESTRICT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
) STRICT;
CREATE TABLE occurrence (
    occurrence_id TEXT PRIMARY KEY,
    event_id TEXT NOT NULL REFERENCES event(event_id) ON DELETE RESTRICT,
    starts_at TEXT NOT NULL,
    ends_at TEXT,
    venue_subject_id TEXT REFERENCES subject(subject_id) ON DELETE RESTRICT,
    CHECK (ends_at IS NULL OR ends_at >= starts_at)
) STRICT;
CREATE TRIGGER occurrence_venue_must_be_venue_insert
BEFORE INSERT ON occurrence WHEN NEW.venue_subject_id IS NOT NULL
AND NOT EXISTS (
    SELECT 1 FROM subject WHERE subject_id = NEW.venue_subject_id AND kind = 'venue'
)
BEGIN SELECT RAISE(ABORT, 'occurrence venue must be a venue subject'); END;
CREATE TRIGGER occurrence_venue_must_be_venue_update
BEFORE UPDATE OF venue_subject_id ON occurrence WHEN NEW.venue_subject_id IS NOT NULL
AND NOT EXISTS (
    SELECT 1 FROM subject WHERE subject_id = NEW.venue_subject_id AND kind = 'venue'
)
BEGIN SELECT RAISE(ABORT, 'occurrence venue must be a venue subject'); END;
CREATE TABLE link (
    link_id TEXT PRIMARY KEY,
    from_subject_id TEXT NOT NULL REFERENCES subject(subject_id) ON DELETE RESTRICT,
    to_subject_id TEXT NOT NULL REFERENCES subject(subject_id) ON DELETE RESTRICT,
    relation TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    CHECK (from_subject_id <> to_subject_id),
    UNIQUE(from_subject_id, to_subject_id, relation)
) STRICT;

CREATE TABLE source (
    source_id TEXT PRIMARY KEY,
    registry_source_id TEXT NOT NULL,
    registry_hash TEXT NOT NULL CHECK (
        length(registry_hash) = 64
        AND registry_hash = lower(registry_hash)
        AND registry_hash NOT GLOB '*[^0-9a-f]*'
    ),
    publisher_id TEXT NOT NULL,
    control_cluster TEXT NOT NULL,
    origin_cluster TEXT NOT NULL,
    access_basis TEXT NOT NULL CHECK (access_basis IN ('official_public_website', 'official_open_data_api')),
    authority_scopes_json TEXT NOT NULL CHECK (
        json_valid(authority_scopes_json)
        AND json_type(authority_scopes_json) = 'array'
        AND json_array_length(authority_scopes_json) > 0
    ),
    source_kind TEXT NOT NULL,
    url_scheme TEXT NOT NULL CHECK (url_scheme = 'https'),
    url_host TEXT NOT NULL CHECK (
        length(url_host) > 0
        AND url_host = lower(url_host)
        AND url_host NOT GLOB '*[^a-z0-9.-]*'
    ),
    url_port INTEGER NOT NULL CHECK (typeof(url_port) = 'integer' AND url_port = 443),
    url_path_digest TEXT,
    retrieved_at TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    UNIQUE(
        registry_source_id,
        registry_hash,
        publisher_id,
        control_cluster,
        origin_cluster,
        access_basis,
        authority_scopes_json,
        url_scheme,
        url_host,
        url_port,
        url_path_digest
    )
) STRICT;
CREATE UNIQUE INDEX source_canonical_url_idx
ON source(url_scheme, url_host, url_port, ifnull(url_path_digest, ''));
CREATE TABLE source_revision (
    revision_id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL REFERENCES source(source_id) ON DELETE RESTRICT,
    retrieved_at TEXT NOT NULL,
    content_digest TEXT NOT NULL,
    extractor_version TEXT NOT NULL,
    UNIQUE(source_id, content_digest)
) STRICT;
CREATE TABLE evidence_review (
    evidence_review_id TEXT PRIMARY KEY,
    fact_id TEXT NOT NULL REFERENCES candidate_fact(fact_id) ON DELETE RESTRICT,
    authority_scope TEXT NOT NULL,
    direct INTEGER NOT NULL CHECK (typeof(direct) = 'integer' AND direct IN (0, 1)),
    reviewer_receipt_digest TEXT NOT NULL CHECK (length(reviewer_receipt_digest) = 64 AND reviewer_receipt_digest = lower(reviewer_receipt_digest) AND reviewer_receipt_digest NOT GLOB '*[^0-9a-f]*'),
    policy_hash TEXT NOT NULL CHECK (length(policy_hash) = 64 AND policy_hash = lower(policy_hash) AND policy_hash NOT GLOB '*[^0-9a-f]*'),
    status TEXT NOT NULL CHECK (status IN ('active', 'superseded')),
    supersedes_id TEXT REFERENCES evidence_review(evidence_review_id) ON DELETE RESTRICT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
) STRICT;
CREATE UNIQUE INDEX evidence_review_one_active_fact_scope_idx
ON evidence_review(fact_id, authority_scope) WHERE status = 'active';
CREATE TRIGGER evidence_review_append_only_delete BEFORE DELETE ON evidence_review
BEGIN SELECT RAISE(ABORT, 'evidence review is append-only'); END;
CREATE TRIGGER evidence_review_immutable BEFORE UPDATE OF evidence_review_id, fact_id, authority_scope, direct, reviewer_receipt_digest, policy_hash, supersedes_id ON evidence_review
BEGIN SELECT RAISE(ABORT, 'evidence review fields are immutable'); END;
CREATE TRIGGER evidence_review_insert_adapter_only BEFORE INSERT ON evidence_review
WHEN review_transition_authorized(
    (SELECT candidate_id FROM candidate_fact WHERE fact_id = NEW.fact_id),
    NEW.evidence_review_id,
    'active',
    'active',
    (SELECT version FROM evidence_review_aggregate
     WHERE candidate_id = (SELECT candidate_id FROM candidate_fact WHERE fact_id = NEW.fact_id))
) = 0
BEGIN SELECT RAISE(ABORT, 'evidence review insert requires command adapter'); END;
CREATE TRIGGER evidence_review_status_adapter_only BEFORE UPDATE OF status ON evidence_review
WHEN OLD.status <> 'active'
OR NEW.status <> 'superseded'
OR review_transition_authorized(
    (SELECT candidate_id FROM candidate_fact WHERE fact_id = NEW.fact_id),
    NEW.evidence_review_id,
    OLD.status,
    NEW.status,
    (SELECT version FROM evidence_review_aggregate
     WHERE candidate_id = (SELECT candidate_id FROM candidate_fact WHERE fact_id = NEW.fact_id))
) = 0
BEGIN SELECT RAISE(ABORT, 'evidence review status transition requires command adapter'); END;
CREATE TABLE evidence_review_aggregate (
    candidate_id TEXT PRIMARY KEY REFERENCES candidate(candidate_id) ON DELETE CASCADE,
    version INTEGER NOT NULL DEFAULT 0 CHECK (version >= 0),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
) STRICT;
CREATE TABLE evidence_review_command_receipt (
    command_id TEXT PRIMARY KEY,
    fact_id TEXT NOT NULL REFERENCES candidate_fact(fact_id) ON DELETE RESTRICT,
    authority_scope TEXT NOT NULL,
    direct INTEGER NOT NULL CHECK (typeof(direct) = 'integer' AND direct IN (0, 1)),
    actor_id TEXT NOT NULL,
    policy_hash TEXT NOT NULL CHECK (length(policy_hash) = 64 AND policy_hash = lower(policy_hash) AND policy_hash NOT GLOB '*[^0-9a-f]*'),
    registry_hash TEXT NOT NULL CHECK (length(registry_hash) = 64 AND registry_hash = lower(registry_hash) AND registry_hash NOT GLOB '*[^0-9a-f]*'),
    expected_version INTEGER NOT NULL CHECK (expected_version >= 0),
    resulting_version INTEGER NOT NULL CHECK (resulting_version >= 0),
    resulting_evidence_review_id TEXT NOT NULL REFERENCES evidence_review(evidence_review_id) ON DELETE RESTRICT,
    command_json TEXT NOT NULL CHECK (json_valid(command_json)),
    receipt_json TEXT NOT NULL CHECK (json_valid(receipt_json)),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    CHECK (json_extract(command_json, '$.command_id') = command_id),
    CHECK (json_extract(command_json, '$.fact_id') = fact_id),
    CHECK (json_extract(command_json, '$.authority_scope') = authority_scope),
    CHECK (json_extract(command_json, '$.direct') = direct),
    CHECK (json_extract(command_json, '$.actor_id') = actor_id),
    CHECK (json_extract(command_json, '$.expected_version') = expected_version),
    CHECK (json_extract(receipt_json, '$.command_id') = command_id),
    CHECK (json_extract(receipt_json, '$.resulting_version') = resulting_version),
    CHECK (json_extract(receipt_json, '$.resulting_evidence_review_id') = resulting_evidence_review_id)
) STRICT;
CREATE INDEX evidence_review_command_receipt_fact_idx
ON evidence_review_command_receipt(fact_id, authority_scope, resulting_version);
CREATE TRIGGER evidence_review_command_receipt_append_only_update
BEFORE UPDATE ON evidence_review_command_receipt
BEGIN SELECT RAISE(ABORT, 'evidence review command receipt is append-only'); END;
CREATE TRIGGER evidence_review_command_receipt_append_only_delete
BEFORE DELETE ON evidence_review_command_receipt
BEGIN SELECT RAISE(ABORT, 'evidence review command receipt is append-only'); END;

CREATE TABLE candidate_fact (
    fact_id TEXT PRIMARY KEY,
    candidate_id TEXT NOT NULL REFERENCES candidate(candidate_id) ON DELETE RESTRICT,
    revision_id TEXT NOT NULL REFERENCES source_revision(revision_id) ON DELETE RESTRICT,
    predicate TEXT NOT NULL,
    value_json TEXT NOT NULL CHECK (json_valid(value_json)),
    locator_digest TEXT NOT NULL CHECK (length(locator_digest) = 64 AND locator_digest = lower(locator_digest) AND locator_digest NOT GLOB '*[^0-9a-f]*'),
    excerpt_digest TEXT NOT NULL CHECK (length(excerpt_digest) = 64 AND excerpt_digest = lower(excerpt_digest) AND excerpt_digest NOT GLOB '*[^0-9a-f]*'),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    CHECK (
        (predicate IN ('program_name', 'organization_name', 'school_name', 'event_name', 'location_name', 'event_date', 'document_text_digest') AND json_type(value_json) = 'text')
        OR (predicate IN ('founded_year', 'team_count') AND json_type(value_json) = 'integer')
        OR (predicate = 'official_status' AND json_type(value_json) IN ('true', 'false'))
    ),
    UNIQUE(candidate_id, revision_id, predicate, value_json, locator_digest, excerpt_digest)
) STRICT;
CREATE TRIGGER candidate_fact_append_only_update
BEFORE UPDATE ON candidate_fact
BEGIN SELECT RAISE(ABORT, 'candidate facts are append-only'); END;
CREATE TRIGGER candidate_fact_append_only_delete
BEFORE DELETE ON candidate_fact
BEGIN SELECT RAISE(ABORT, 'candidate facts are append-only'); END;
CREATE TABLE claim (
    claim_id TEXT PRIMARY KEY,
    candidate_id TEXT NOT NULL REFERENCES candidate(candidate_id) ON DELETE RESTRICT,
    subject_id TEXT NOT NULL REFERENCES subject(subject_id) ON DELETE RESTRICT,
    predicate TEXT NOT NULL,
    value_json TEXT NOT NULL CHECK (json_valid(value_json)),
    asserted_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
) STRICT;
CREATE TABLE evidence (
    evidence_id TEXT PRIMARY KEY,
    claim_id TEXT NOT NULL REFERENCES claim(claim_id) ON DELETE RESTRICT,
    revision_id TEXT NOT NULL REFERENCES source_revision(revision_id) ON DELETE RESTRICT,
    locator_digest TEXT,
    excerpt_digest TEXT,
    UNIQUE(claim_id, revision_id, locator_digest)
) STRICT;
CREATE TABLE lineage (
    lineage_id TEXT PRIMARY KEY,
    child_claim_id TEXT NOT NULL REFERENCES claim(claim_id) ON DELETE RESTRICT,
    parent_claim_id TEXT NOT NULL REFERENCES claim(claim_id) ON DELETE RESTRICT,
    relation TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    CHECK (child_claim_id <> parent_claim_id),
    UNIQUE(child_claim_id, parent_claim_id, relation)
) STRICT;
CREATE TABLE decision (
    decision_id TEXT PRIMARY KEY,
    claim_id TEXT NOT NULL REFERENCES claim(claim_id) ON DELETE RESTRICT,
    status TEXT NOT NULL CHECK (status IN ('verified', 'provisional', 'rejected')),
    policy_version TEXT NOT NULL,
    policy_epoch INTEGER NOT NULL CHECK (policy_epoch >= 0),
    rationale TEXT NOT NULL,
    input_hash TEXT NOT NULL CHECK (length(input_hash) = 64 AND input_hash = lower(input_hash) AND input_hash NOT GLOB '*[^0-9a-f]*'),
    decided_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    UNIQUE(claim_id, input_hash)
) STRICT;
CREATE INDEX decision_claim_idx ON decision(claim_id, decided_at);

CREATE TABLE review_item (
    review_item_id TEXT PRIMARY KEY,
    candidate_id TEXT REFERENCES candidate(candidate_id) ON DELETE RESTRICT,
    claim_id TEXT REFERENCES claim(claim_id) ON DELETE RESTRICT,
    status TEXT NOT NULL CHECK (status IN ('active', 'resolved', 'superseded')),
    reason TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    resolved_at TEXT,
    CHECK ((candidate_id IS NOT NULL) <> (claim_id IS NOT NULL)),
    CHECK ((status = 'active') = (resolved_at IS NULL))
) STRICT;
CREATE TABLE correction (
    correction_id TEXT PRIMARY KEY,
    claim_id TEXT NOT NULL REFERENCES claim(claim_id) ON DELETE RESTRICT,
    replacement_claim_id TEXT REFERENCES claim(claim_id) ON DELETE RESTRICT,
    reason TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
) STRICT;
CREATE TABLE publication (
    publication_id TEXT PRIMARY KEY,
    claim_id TEXT NOT NULL REFERENCES claim(claim_id) ON DELETE RESTRICT,
    status TEXT NOT NULL CHECK (status IN ('verified', 'provisional')),
    published_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    retracted_at TEXT,
    CHECK (retracted_at IS NULL OR retracted_at >= published_at)
) STRICT;
CREATE UNIQUE INDEX active_publication_claim_idx ON publication(claim_id) WHERE retracted_at IS NULL;
CREATE TRIGGER publication_requires_eligible_candidate_insert
BEFORE INSERT ON publication
WHEN NEW.retracted_at IS NULL
AND (
    (SELECT count(*) FROM candidate_subject cs
     JOIN claim c ON c.candidate_id = cs.candidate_id
     WHERE c.claim_id = NEW.claim_id
       AND cs.subject_id = c.subject_id
       AND cs.relation = 'primary'
       AND cs.active = 1) <> 1
    OR (
        SELECT count(*)
        FROM identity_link_receipt ilr
        JOIN claim c ON c.candidate_id = ilr.candidate_id
        JOIN subject s ON s.subject_id = ilr.subject_id
        WHERE c.claim_id = NEW.claim_id
          AND ilr.subject_id = c.subject_id
          AND ilr.attestation_type = 'human_review'
          AND ilr.authority_identity_digest = s.provenance_digest
    ) <> 1
    OR EXISTS (
        SELECT 1 FROM review_identity ri
        JOIN claim c ON c.candidate_id = ri.candidate_id
        WHERE c.claim_id = NEW.claim_id AND ri.status = 'active'
    )
)
BEGIN SELECT RAISE(ABORT, 'publication requires its subject as the sole active primary and no active review'); END;
CREATE TRIGGER publication_requires_eligible_candidate_activate
BEFORE UPDATE OF retracted_at ON publication
WHEN OLD.retracted_at IS NOT NULL AND NEW.retracted_at IS NULL
AND (
    (SELECT count(*) FROM candidate_subject cs
     JOIN claim c ON c.candidate_id = cs.candidate_id
     WHERE c.claim_id = NEW.claim_id
       AND cs.subject_id = c.subject_id
       AND cs.relation = 'primary'
       AND cs.active = 1) <> 1
    OR (
        SELECT count(*)
        FROM identity_link_receipt ilr
        JOIN claim c ON c.candidate_id = ilr.candidate_id
        JOIN subject s ON s.subject_id = ilr.subject_id
        WHERE c.claim_id = NEW.claim_id
          AND ilr.subject_id = c.subject_id
          AND ilr.attestation_type = 'human_review'
          AND ilr.authority_identity_digest = s.provenance_digest
    ) <> 1
    OR EXISTS (
        SELECT 1 FROM review_identity ri
        JOIN claim c ON c.candidate_id = ri.candidate_id
        WHERE c.claim_id = NEW.claim_id AND ri.status = 'active'
    )
)
BEGIN SELECT RAISE(ABORT, 'publication requires its subject as the sole active primary and no active review'); END;
CREATE TRIGGER active_publication_claim_immutable
BEFORE UPDATE OF claim_id ON publication
WHEN OLD.retracted_at IS NULL
AND NEW.claim_id IS NOT OLD.claim_id
BEGIN SELECT RAISE(ABORT, 'active publication claim is immutable'); END;
CREATE TRIGGER published_candidate_primary_immutable_update
BEFORE UPDATE OF candidate_id, subject_id, relation, active ON candidate_subject
WHEN OLD.relation = 'primary' AND OLD.active = 1
AND EXISTS (
    SELECT 1 FROM publication p
    JOIN claim c ON c.claim_id = p.claim_id
    WHERE p.retracted_at IS NULL AND c.candidate_id = OLD.candidate_id
)
BEGIN SELECT RAISE(ABORT, 'retract publications before changing an active primary'); END;
CREATE TRIGGER published_candidate_primary_immutable_delete
BEFORE DELETE ON candidate_subject
WHEN OLD.relation = 'primary' AND OLD.active = 1
AND EXISTS (
    SELECT 1 FROM publication p
    JOIN claim c ON c.claim_id = p.claim_id
    WHERE p.retracted_at IS NULL AND c.candidate_id = OLD.candidate_id
)
BEGIN SELECT RAISE(ABORT, 'retract publications before changing an active primary'); END;
CREATE TRIGGER published_candidate_review_requires_retraction_insert
BEFORE INSERT ON review_identity
WHEN NEW.status = 'active'
AND EXISTS (
    SELECT 1 FROM publication p
    JOIN claim c ON c.claim_id = p.claim_id
    WHERE p.retracted_at IS NULL AND c.candidate_id = NEW.candidate_id
)
BEGIN SELECT RAISE(ABORT, 'retract publications before creating an active review'); END;
CREATE TRIGGER published_candidate_review_requires_retraction_update
BEFORE UPDATE OF candidate_id, status ON review_identity
WHEN NEW.status = 'active'
AND EXISTS (
    SELECT 1 FROM publication p
    JOIN claim c ON c.claim_id = p.claim_id
    WHERE p.retracted_at IS NULL AND c.candidate_id = NEW.candidate_id
)
BEGIN SELECT RAISE(ABORT, 'retract publications before creating an active review'); END;

CREATE TRIGGER source_revision_append_only_update BEFORE UPDATE ON source_revision
BEGIN SELECT RAISE(ABORT, 'source_revision is append-only'); END;
CREATE TRIGGER source_revision_append_only_delete BEFORE DELETE ON source_revision
BEGIN SELECT RAISE(ABORT, 'source_revision is append-only'); END;
CREATE TRIGGER claim_append_only_update BEFORE UPDATE ON claim
BEGIN SELECT RAISE(ABORT, 'claim is append-only'); END;
CREATE TRIGGER claim_append_only_delete BEFORE DELETE ON claim
BEGIN SELECT RAISE(ABORT, 'claim is append-only'); END;
CREATE TRIGGER evidence_append_only_update BEFORE UPDATE ON evidence
BEGIN SELECT RAISE(ABORT, 'evidence is append-only'); END;
CREATE TRIGGER evidence_append_only_delete BEFORE DELETE ON evidence
BEGIN SELECT RAISE(ABORT, 'evidence is append-only'); END;
CREATE TRIGGER lineage_append_only_update BEFORE UPDATE ON lineage
BEGIN SELECT RAISE(ABORT, 'lineage is append-only'); END;
CREATE TRIGGER lineage_append_only_delete BEFORE DELETE ON lineage
BEGIN SELECT RAISE(ABORT, 'lineage is append-only'); END;
CREATE TRIGGER decision_append_only_update BEFORE UPDATE ON decision
BEGIN SELECT RAISE(ABORT, 'decision is append-only'); END;
CREATE TRIGGER decision_append_only_delete BEFORE DELETE ON decision
BEGIN SELECT RAISE(ABORT, 'decision is append-only'); END;
