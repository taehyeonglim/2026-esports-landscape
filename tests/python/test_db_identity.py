from hashlib import sha256
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import UUID

from esports_data.db import connect
from esports_data.identity import (
    AUTHORITY_NAMESPACE_NAMES,
    AuthorityIdentity,
    IdentityError,
    PrimaryReviewIdentity,
    RelatedProposalIdentity,
    insert_authority_subject,
    subject_uuid,
)
from esports_data.migrate import migrate
from esports_data.models import Relation, ReviewStatus, SubjectKind
from esports_data.mutation import (
    ArtifactIncompleteError,
    MutationCommand,
    MutationError,
    PiiPersistenceError,
    apply,
    queue,
)
from esports_data.review import (
    PrimaryReview,
    ProposalStatus,
    PublicationCandidate,
    RelatedProposal,
    ReviewAction,
    ReviewCommand,
    ReviewError,
    apply_review_command_sqlite,
    publication_eligibility,
)


DIGEST = "a" * 64


class DatabaseAndIdentityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.connection = connect(Path(self.temp.name) / "control.sqlite")
        migrate(self.connection)

    def tearDown(self):
        self.connection.close()
        self.temp.cleanup()

    def authority(self, kind: SubjectKind) -> AuthorityIdentity:
        key = "ABCDEFGHIJ" if kind in {SubjectKind.SCHOOL, SubjectKind.UNIVERSITY} else "abc-key"
        if kind is SubjectKind.REGION:
            key = "123"
        if kind is SubjectKind.VENUE:
            key = "ABC-KEY"
        return AuthorityIdentity(kind, AUTHORITY_NAMESPACE_NAMES[kind], key)

    def subject(self, kind: SubjectKind, *, operator_subject_id: str | None = None) -> str:
        identity = self.authority(kind)
        return str(
            insert_authority_subject(
                self.connection,
                identity,
                canonical_name=f"Synthetic {kind.value}",
                provenance_digest=DIGEST,
                operator_subject_id=operator_subject_id,
            ).subject_id
        )

    def add_candidate(self, candidate_id: str) -> None:
        self.connection.execute(
            "INSERT INTO candidate(candidate_id, status, summary) VALUES (?, 'review', 'Synthetic')",
            (candidate_id,),
        )

    def add_review(self, candidate_id: str, review_id: str = "review-1") -> None:
        self.connection.execute(
            """INSERT INTO review_identity
               (review_identity_id, candidate_id, proposed_kind, hint_digest, reason_code, status)
               VALUES (?, ?, 'school', ?, 'authority_key_missing', 'active')""",
            (review_id, candidate_id, DIGEST),
        )
    def resolve_review(self, candidate_id: str, review_id: str, subject_id: str) -> None:
        apply_review_command_sqlite(
            self.connection,
            candidate_id,
            ReviewCommand(
                f"command-{review_id}",
                "reviewer-1",
                0,
                ReviewAction.RESOLVE_PRIMARY,
                review_id,
                subject_id,
            ),
            allowed_actors=("reviewer-1",),
        )

    def link_primary(self, candidate_id: str, subject_id: str, review_id: str = "primary-link") -> None:
        self.add_review(candidate_id, review_id)
        self.resolve_review(candidate_id, review_id, subject_id)

    def test_migrations_are_idempotent_and_venue_requires_organization_operator(self):
        self.assertEqual(migrate(self.connection), (1, 2))
        organization = self.subject(SubjectKind.ORGANIZATION)
        venue = self.subject(SubjectKind.VENUE, operator_subject_id=organization)
        self.connection.execute("INSERT INTO event(event_id, name) VALUES ('event', 'Synthetic event')")
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                "INSERT INTO occurrence(occurrence_id, event_id, starts_at, venue_subject_id) VALUES ('bad', 'event', '2026-01-01T00:00:00Z', ?)",
                (organization,),
            )
        self.connection.execute(
            "INSERT INTO occurrence(occurrence_id, event_id, starts_at, venue_subject_id) VALUES ('venue', 'event', '2026-01-01T00:00:00Z', ?)",
            (venue,),
        )

    def test_identity_repository_issues_all_six_authority_subjects(self):
        organization = None
        for kind in SubjectKind:
            with self.subTest(kind=kind):
                identity = self.authority(kind)
                if kind is SubjectKind.ORGANIZATION:
                    organization = self.subject(kind)
                    subject_id = organization
                elif kind is SubjectKind.VENUE:
                    self.assertIsNotNone(organization)
                    subject_id = self.subject(kind, operator_subject_id=organization)
                else:
                    subject_id = self.subject(kind)
                self.assertEqual(subject_id, str(subject_uuid(identity)))
                self.assertIsInstance(UUID(subject_id), UUID)
        with self.assertRaises(IdentityError):
            insert_authority_subject(
                self.connection,
                PrimaryReviewIdentity(SubjectKind.SCHOOL, "intake-1"),  # type: ignore[arg-type]
                canonical_name="Synthetic",
                provenance_digest=DIGEST,
            )

    def test_raw_subject_requires_authority_provenance_and_rejects_enum_drift(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                "INSERT INTO subject(subject_id, kind, canonical_name) VALUES ('00000000-0000-0000-0000-000000000000', 'school', 'Synthetic')"
            )
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                """INSERT INTO subject(subject_id, kind, authority_namespace, authority_key, provenance_digest, canonical_name)
                   VALUES ('00000000-0000-0000-0000-000000000000', 'drift', 'issuer', 'key', ?, 'Synthetic')""",
                (DIGEST,),
            )

    def test_candidate_active_primary_and_active_review_are_mutually_exclusive(self):
        subject_id = self.subject(SubjectKind.SCHOOL)
        self.add_candidate("candidate-1")
        self.add_review("candidate-1")
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                "INSERT INTO candidate_subject(candidate_id, subject_id, relation, active) VALUES ('candidate-1', ?, 'primary', 1)",
                (subject_id,),
            )
        self.resolve_review("candidate-1", "review-1", subject_id)
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                "INSERT INTO candidate_subject(candidate_id, subject_id, relation, active) VALUES ('candidate-1', ?, 'primary', 1)",
                (subject_id,),
            )
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute("UPDATE candidate_subject SET active = 2 WHERE candidate_id = 'candidate-1'")
    def test_resolve_primary_records_an_exact_immutable_identity_receipt(self):
        subject_id = self.subject(SubjectKind.SCHOOL)
        other_subject_id = self.subject(SubjectKind.REGION)
        self.add_candidate("receipt-bound")
        self.add_review("receipt-bound", "receipt-review")
        command = ReviewCommand(
            "receipt-command",
            "reviewer-1",
            0,
            ReviewAction.RESOLVE_PRIMARY,
            "receipt-review",
            subject_id,
        )
        apply_review_command_sqlite(
            self.connection, "receipt-bound", command, allowed_actors=("reviewer-1",)
        )
        receipt = self.connection.execute(
            """SELECT subject_id, review_identity_id, actor_id, command_id, resulting_version,
                      authority_identity_digest
               FROM identity_link_receipt WHERE candidate_id = 'receipt-bound'"""
        ).fetchone()
        self.assertEqual(
            tuple(receipt),
            (subject_id, "receipt-review", "reviewer-1", "receipt-command", 1, DIGEST),
        )
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                "UPDATE identity_link_receipt SET subject_id = ? WHERE candidate_id = 'receipt-bound'",
                (other_subject_id,),
            )
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                """INSERT INTO candidate_subject(candidate_id, subject_id, relation, active)
                   VALUES ('receipt-bound', ?, 'primary', 1)""",
                (other_subject_id,),
            )
        replay = apply_review_command_sqlite(
            self.connection, "receipt-bound", command, allowed_actors=("reviewer-1",)
        )
        self.assertTrue(replay.idempotent)

    def test_human_review_identity_receipt_is_adapter_only(self):
        subject_id = self.subject(SubjectKind.SCHOOL)
        self.add_candidate("forged-human-receipt")
        self.add_review("forged-human-receipt", "forged-review")
        with self.assertRaisesRegex(sqlite3.IntegrityError, "command adapter"):
            self.connection.execute(
                """INSERT INTO identity_link_receipt(
                       identity_link_receipt_id, candidate_id, subject_id, attestation_type,
                       review_identity_id, actor_id, command_id, resulting_version, authority_identity_digest)
                   VALUES ('forged-receipt', 'forged-human-receipt', ?, 'human_review',
                           'forged-review', 'attacker', 'forged-command', 1, ?)""",
                (subject_id, DIGEST),
            )

        command = ReviewCommand(
            "authorized-after-forgery",
            "reviewer-1",
            0,
            ReviewAction.RESOLVE_PRIMARY,
            "forged-review",
            subject_id,
        )
        result = apply_review_command_sqlite(
            self.connection, "forged-human-receipt", command, allowed_actors=("reviewer-1",)
        )
        self.assertFalse(result.idempotent)
        self.assertEqual(
            self.connection.execute(
                "SELECT count(*) FROM identity_link_receipt WHERE candidate_id = 'forged-human-receipt'"
            ).fetchone()[0],
            1,
        )

    def test_authority_mapping_receipt_keeps_trusted_raw_path_separate(self):
        subject_id = self.subject(SubjectKind.SCHOOL)
        self.add_candidate("authority-mapped")
        self.connection.execute(
            """INSERT INTO identity_link_receipt(
                   identity_link_receipt_id, candidate_id, subject_id, attestation_type,
                   actor_id, command_id, resulting_version, authority_identity_digest)
               VALUES ('authority-receipt', 'authority-mapped', ?, 'authority_mapping',
                       'authority-adapter', 'authority-command', 0, ?)""",
            (subject_id, DIGEST),
        )
        row = self.connection.execute(
            """SELECT attestation_type, review_identity_id
               FROM identity_link_receipt WHERE identity_link_receipt_id = 'authority-receipt'"""
        ).fetchone()
        self.assertEqual(tuple(row), ("authority_mapping", None))
    def test_resolve_primary_requires_an_exact_subject(self):
        with self.assertRaises(ReviewError):
            ReviewCommand(
                "missing-subject",
                "reviewer-1",
                0,
                ReviewAction.RESOLVE_PRIMARY,
                "review-missing-subject",
            )

    def test_publication_requires_one_active_primary_and_no_active_review(self):
        subject_id = self.subject(SubjectKind.SCHOOL)
        self.add_candidate("zero-primary")
        self.connection.execute(
            "INSERT INTO claim(claim_id, candidate_id, subject_id, predicate, value_json) VALUES ('claim-zero', 'zero-primary', ?, 'name', '{}')",
            (subject_id,),
        )
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute("INSERT INTO publication(publication_id, claim_id, status) VALUES ('pub-zero', 'claim-zero', 'verified')")

        self.add_candidate("review-blocked")
        self.add_review("review-blocked", "review-2")
        self.connection.execute(
            "INSERT INTO claim(claim_id, candidate_id, subject_id, predicate, value_json) VALUES ('claim-review', 'review-blocked', ?, 'name', '{}')",
            (subject_id,),
        )
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute("INSERT INTO publication(publication_id, claim_id, status) VALUES ('pub-review', 'claim-review', 'verified')")

    def test_related_proposal_is_non_blocking_after_primary_review_resolves(self):
        subject_id = self.subject(SubjectKind.SCHOOL)
        self.add_candidate("related-only")
        self.add_review("related-only", "review-3")
        self.connection.execute(
            """INSERT INTO identity_proposal
               (proposal_id, candidate_id, review_identity_id, proposed_kind, hint_digest, reason, status)
               VALUES ('proposal-1', 'related-only', 'review-3', 'school', ?, 'possible_match', 'active')""",
            (DIGEST,),
        )
        self.resolve_review("related-only", "review-3", subject_id)
        self.connection.execute(
            "INSERT INTO claim(claim_id, candidate_id, subject_id, predicate, value_json) VALUES ('claim-related', 'related-only', ?, 'name', '{}')",
            (subject_id,),
        )
        self.connection.execute("INSERT INTO publication(publication_id, claim_id, status) VALUES ('pub-related', 'claim-related', 'verified')")
    def test_raw_subject_uuid_and_identity_are_append_only(self):
        identity = self.authority(SubjectKind.SCHOOL)
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                """INSERT INTO subject(subject_id, kind, authority_namespace, authority_key,
                   provenance_digest, canonical_name)
                   VALUES ('00000000-0000-0000-0000-000000000000', 'school', ?, ?, ?, 'Synthetic')""",
                (identity.namespace, identity.key, DIGEST),
            )
        subject_id = self.subject(SubjectKind.SCHOOL)
        for statement in (
            "UPDATE subject SET authority_key = 'ZZZZZZZZZZ' WHERE subject_id = ?",
            "DELETE FROM subject WHERE subject_id = ?",
        ):
            with self.assertRaises(sqlite3.IntegrityError):
                self.connection.execute(statement, (subject_id,))
        organization = self.subject(SubjectKind.ORGANIZATION)
        venue = self.subject(SubjectKind.VENUE, operator_subject_id=organization)
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                "UPDATE subject SET operator_subject_id = NULL WHERE subject_id = ?",
                (venue,),
            )

    def test_review_status_and_supersedes_require_the_adapter_and_same_candidate(self):
        self.add_candidate("review-a")
        self.add_candidate("review-b")
        self.add_review("review-a", "review-a1")
        self.add_review("review-b", "review-b1")
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                "UPDATE review_identity SET status = 'resolved', resolved_at = '2026-01-01T00:00:00Z' WHERE review_identity_id = 'review-a1'"
            )
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                """INSERT INTO review_identity
                   (review_identity_id, candidate_id, proposed_kind, hint_digest, reason_code,
                    status, supersedes_id, resolved_at)
                   VALUES ('review-b-missing', 'review-b', 'school', ?, 'authority_key_missing',
                           'resolved', 'missing-review', '2026-01-01T00:00:00Z')""",
                (DIGEST,),
            )
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                """INSERT INTO review_identity
                   (review_identity_id, candidate_id, proposed_kind, hint_digest, reason_code,
                    status, supersedes_id, resolved_at)
                   VALUES ('review-b2', 'review-b', 'school', ?, 'authority_key_missing',
                           'resolved', 'review-a1', '2026-01-01T00:00:00Z')""",
                (DIGEST,),
            )
        self.connection.execute(
            """INSERT INTO identity_proposal
               (proposal_id, candidate_id, review_identity_id, proposed_kind, hint_digest,
                reason, status)
               VALUES ('proposal-a1', 'review-a', 'review-a1', 'school', ?,
                       'possible_match', 'active')""",
            (DIGEST,),
        )
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                "UPDATE identity_proposal SET status = 'rejected', resolved_at = '2026-01-01T00:00:00Z' WHERE proposal_id = 'proposal-a1'"
            )
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                """INSERT INTO identity_proposal
                   (proposal_id, candidate_id, review_identity_id, proposed_kind, hint_digest,
                    reason, status, supersedes_id)
                   VALUES ('proposal-b-cross', 'review-b', 'review-b1', 'school', ?,
                           'possible_match', 'active', 'proposal-a1')""",
                (DIGEST,),
            )
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                """INSERT INTO identity_proposal
                   (proposal_id, candidate_id, review_identity_id, proposed_kind, hint_digest,
                    reason, status)
                   VALUES ('proposal-cross', 'review-b', 'review-a1', 'school', ?,
                           'possible_match', 'active')""",
                (DIGEST,),
            )
    def test_review_history_and_aggregate_are_adapter_only(self):
        self.add_candidate("guarded-review")
        self.add_review("guarded-review", "guarded-primary")
        self.add_candidate("other")
        self.add_review("other", "other-primary")
        self.connection.execute(
            """INSERT INTO identity_proposal
               (proposal_id, candidate_id, review_identity_id, proposed_kind, hint_digest, reason, status)
               VALUES ('guarded-proposal', 'guarded-review', 'guarded-primary', 'school', ?,
                       'possible_match', 'active')""",
            (DIGEST,),
        )
        for statement, parameters in (
            ("DELETE FROM review_identity WHERE review_identity_id = ?", ("guarded-primary",)),
            ("UPDATE review_identity SET candidate_id = 'other' WHERE review_identity_id = ?", ("guarded-primary",)),
            ("UPDATE review_identity SET hint_digest = ? WHERE review_identity_id = ?", ("b" * 64, "guarded-primary")),
            ("UPDATE review_identity SET relation = 'primary' WHERE review_identity_id = ?", ("guarded-primary",)),
            ("DELETE FROM identity_proposal WHERE proposal_id = ?", ("guarded-proposal",)),
            ("UPDATE identity_proposal SET review_identity_id = ? WHERE proposal_id = ?", ("other-primary", "guarded-proposal")),
        ):
            with self.subTest(statement=statement), self.assertRaises(sqlite3.IntegrityError):
                self.connection.execute(statement, parameters)
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                "INSERT INTO review_aggregate(candidate_id) VALUES ('guarded-review')"
            )
        subject_id = self.subject(SubjectKind.SCHOOL)
        apply_review_command_sqlite(
            self.connection,
            "guarded-review",
            ReviewCommand(
                "guarded-resolve", "reviewer-1", 0, ReviewAction.RESOLVE_PRIMARY, "guarded-primary", subject_id
            ),
            allowed_actors=("reviewer-1",),
        )
        for statement in (
            "INSERT INTO review_aggregate(candidate_id, version) VALUES ('other', 1)",
            "UPDATE review_aggregate SET version = 0 WHERE candidate_id = 'guarded-review'",
            "UPDATE review_aggregate SET version = 2 WHERE candidate_id = 'guarded-review'",
            "DELETE FROM review_aggregate WHERE candidate_id = 'guarded-review'",
        ):
            with self.subTest(statement=statement), self.assertRaises(sqlite3.IntegrityError):
                self.connection.execute(statement)

    def test_successive_primary_reviews_and_old_command_replay_return_current_state(self):
        self.add_candidate("successive-review")
        self.add_review("successive-review", "review-first")
        subject_id = self.subject(SubjectKind.SCHOOL)
        first = ReviewCommand(
            "command-first", "reviewer-1", 0, ReviewAction.RESOLVE_PRIMARY, "review-first", subject_id
        )
        apply_review_command_sqlite(
            self.connection, "successive-review", first, allowed_actors=("reviewer-1",)
        )
        replay = apply_review_command_sqlite(
            self.connection, "successive-review", first, allowed_actors=("reviewer-1",)
        )
        self.assertTrue(replay.idempotent)
        self.assertEqual(replay.state.version, 1)

    def test_proposal_command_replay_after_primary_resolve_returns_terminal_state(self):
        self.add_candidate("proposal-replay")
        self.add_review("proposal-replay", "review-proposal")
        self.connection.execute(
            """INSERT INTO identity_proposal
               (proposal_id, candidate_id, review_identity_id, proposed_kind, hint_digest, reason, status)
               VALUES ('proposal-terminal', 'proposal-replay', 'review-proposal', 'school', ?,
                       'possible_match', 'active')""",
            (DIGEST,),
        )
        proposal = ReviewCommand(
            "command-proposal", "reviewer-1", 0, ReviewAction.ACCEPT_PROPOSAL, "proposal-terminal"
        )
        apply_review_command_sqlite(
            self.connection, "proposal-replay", proposal, allowed_actors=("reviewer-1",)
        )
        subject_id = self.subject(SubjectKind.SCHOOL)
        primary = ReviewCommand(
            "command-primary", "reviewer-1", 1, ReviewAction.RESOLVE_PRIMARY, "review-proposal", subject_id
        )
        apply_review_command_sqlite(
            self.connection, "proposal-replay", primary, allowed_actors=("reviewer-1",)
        )
        replay = apply_review_command_sqlite(
            self.connection, "proposal-replay", proposal, allowed_actors=("reviewer-1",)
        )
        self.assertTrue(replay.idempotent)
        self.assertEqual(replay.state.version, 2)
        self.assertEqual(replay.state.primary.status, ReviewStatus.RESOLVED)
        self.assertEqual(replay.state.proposals[0].status, ProposalStatus.ACCEPTED)

    def test_review_receipt_insert_requires_adapter_authorization(self):
        self.add_candidate("receipt-guard")
        self.add_review("receipt-guard", "review-receipt")
        command_json = json.dumps(
            {
                "action": "supersede_primary",
                "actor_id": "reviewer-1",
                "command_id": "forged-receipt",
                "expected_version": 0,
                "resolved_subject_id": None,
                "target_id": "review-receipt",
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        receipt_json = json.dumps(
            {"command_id": "forged-receipt", "resulting_version": 1},
            sort_keys=True,
            separators=(",", ":"),
        )
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                """INSERT INTO review_command_receipt
                   (command_id, candidate_id, command_json, receipt_json, resulting_version)
                   VALUES ('forged-receipt', 'receipt-guard', ?, ?, 1)""",
                (command_json, receipt_json),
            )
    def test_active_publication_claim_cannot_be_retargeted(self):
        subject_id = self.subject(SubjectKind.SCHOOL)
        self.add_candidate("publication-retarget")
        self.link_primary("publication-retarget", subject_id)
        for claim_id in ("claim-original", "claim-replacement"):
            self.connection.execute(
                """INSERT INTO claim(claim_id, candidate_id, subject_id, predicate, value_json)
                   VALUES (?, 'publication-retarget', ?, 'name', '{}')""",
                (claim_id, subject_id),
            )
        self.connection.execute(
            "INSERT INTO publication(publication_id, claim_id, status) VALUES ('publication-retarget', 'claim-original', 'verified')"
        )
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                "UPDATE publication SET claim_id = 'claim-replacement' WHERE publication_id = 'publication-retarget'"
            )

    def test_externalized_v2_baseline_dry_migration_leaves_database_unchanged(self):
        baseline = json.loads(
            (Path(__file__).resolve().parents[2] / "baseline/v2/site.v2.json").read_text()
        )
        entry_ids = {entry["id"] for entry in baseline["entries"]}
        region_ids = {region["id"] for region in baseline["regions"]}
        self.assertEqual((len(entry_ids), len(region_ids)), (230, 17))
        self.assertEqual(len(entry_ids), len(baseline["entries"]))
        dry_database = Path(self.temp.name) / "dry-control.sqlite"
        dry_connection = connect(dry_database)
        try:
            self.assertEqual(migrate(dry_connection, dry_run=True), (1, 2))
            self.assertIsNone(
                dry_connection.execute(
                    "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'schema_migration'"
                ).fetchone()
            )
        finally:
            dry_connection.close()

    def test_publication_requires_claim_primary_and_freezes_primary_and_reviews(self):
        primary = self.subject(SubjectKind.SCHOOL)
        related = self.subject(SubjectKind.REGION)
        self.add_candidate("published")
        self.link_primary("published", primary)
        self.connection.execute(
            "INSERT INTO candidate_subject(candidate_id, subject_id, relation) VALUES ('published', ?, 'related')",
            (related,),
        )
        self.connection.execute(
            "INSERT INTO claim(claim_id, candidate_id, subject_id, predicate, value_json) VALUES ('claim-related-subject', 'published', ?, 'name', '{}')",
            (related,),
        )
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                "INSERT INTO publication(publication_id, claim_id, status) VALUES ('pub-related-subject', 'claim-related-subject', 'verified')"
            )
        self.connection.execute(
            "INSERT INTO claim(claim_id, candidate_id, subject_id, predicate, value_json) VALUES ('claim-primary-subject', 'published', ?, 'name', '{}')",
            (primary,),
        )
        self.connection.execute(
            "INSERT INTO publication(publication_id, claim_id, status) VALUES ('pub-primary-subject', 'claim-primary-subject', 'verified')"
        )
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                "UPDATE candidate_subject SET active = 0 WHERE candidate_id = 'published' AND subject_id = ?",
                (primary,),
            )
        with self.assertRaises(sqlite3.IntegrityError):
            self.add_review("published", "review-published")

    def test_review_command_receipt_replays_after_restart(self):
        self.add_candidate("review-command")
        self.add_review("review-command", "review-4")
        subject_id = self.subject(SubjectKind.SCHOOL)
        command = ReviewCommand(
            "command-1", "reviewer-1", 0, ReviewAction.RESOLVE_PRIMARY, "review-4", subject_id
        )
        result = apply_review_command_sqlite(self.connection, "review-command", command, allowed_actors=("reviewer-1",))
        self.assertFalse(result.idempotent)
        database = Path(self.temp.name) / "control.sqlite"
        self.connection.close()
        self.connection = connect(database)
        replay = apply_review_command_sqlite(self.connection, "review-command", command, allowed_actors=("reviewer-1",))
        self.assertTrue(replay.idempotent)
        self.assertEqual(replay.state.version, 1)

    def test_mutation_is_idempotent_and_receipt_excludes_artifact_identity(self):
        for key, value in (("input_revision", "r1"), ("policy_version", "p1"), ("policy_epoch", "0")):
            self.connection.execute("INSERT INTO system_state(key, value) VALUES (?, ?)", (key, value))
        command = MutationCommand("cmd-1", "test", "r1", "p1", 0, {"safe": "aggregate"})
        calls = []
        backup_path = Path(self.temp.name) / "backup.sqlite"
        result = apply(
            self.connection,
            command,
            lambda _db, _payload: calls.append(True),
            parent_git_sha="a" * 40,
            backup_path=backup_path,
        )
        repeated = apply(
            self.connection,
            command,
            lambda _db, _payload: calls.append(True),
            parent_git_sha="a" * 40,
            backup_path=backup_path,
        )
        self.assertEqual(calls, [True])
        self.assertEqual(result.receipt, repeated.receipt)
        self.assertNotIn("backup_path", result.receipt.payload())
        self.assertNotIn("sqlite_file_sha256", result.receipt.payload())
        self.assertNotIn("receipt_hash", result.receipt.payload())
        self.assertEqual(
            result.checkpoint_artifact.sqlite_file_sha256,
            sha256(backup_path.read_bytes()).hexdigest(),
        )
        self.assertEqual(result.checkpoint_artifact.integrity_check, ("ok",))
        self.assertEqual(result.checkpoint_artifact.foreign_key_check, ())
        with self.assertRaises(MutationError):
            apply(
                self.connection,
                MutationCommand("cmd-1", "other", "r1", "p1", 0, {}),
                lambda *_: None,
                parent_git_sha="a" * 40,
                backup_path=Path(self.temp.name) / "x.sqlite",
            )

    def test_mapping_key_with_pii_is_rejected_before_queueing(self):
        with self.assertRaises(PiiPersistenceError):
            queue(self.connection, MutationCommand("pii-key", "test", "r1", "p1", 0, {
                "student name: Min": "safe",
            }))

    def test_unrelated_valid_sqlite_artifact_is_not_a_duplicate_checkpoint(self):
        for key, value in (("input_revision", "r1"), ("policy_version", "p1"), ("policy_epoch", "0")):
            self.connection.execute("INSERT INTO system_state(key, value) VALUES (?, ?)", (key, value))
        command = MutationCommand("artifact-match", "test", "r1", "p1", 0, {})
        backup_path = Path(self.temp.name) / "artifact-match.sqlite"
        apply(self.connection, command, lambda *_: None, parent_git_sha="a" * 40, backup_path=backup_path)
        backup_path.unlink()
        unrelated = sqlite3.connect(backup_path)
        unrelated.execute("CREATE TABLE unrelated (value TEXT)")
        unrelated.commit()
        unrelated.close()
        with self.assertRaises(ArtifactIncompleteError):
            apply(self.connection, command, lambda *_: None, parent_git_sha="a" * 40, backup_path=backup_path)

    def test_handler_failure_rolls_back_running_and_terminalizes_once(self):
        for key, value in (("input_revision", "r1"), ("policy_version", "p1"), ("policy_epoch", "0")):
            self.connection.execute("INSERT INTO system_state(key, value) VALUES (?, ?)", (key, value))
        command = MutationCommand("handler-crash", "test", "r1", "p1", 0, {})
        calls = []

        def failing_handler(connection, _payload):
            calls.append(True)
            connection.execute("INSERT INTO system_state(key, value) VALUES ('handler-write', 'no')")
            raise RuntimeError("handler crash")

        with self.assertRaisesRegex(RuntimeError, "handler crash"):
            apply(
                self.connection,
                command,
                failing_handler,
                parent_git_sha="a" * 40,
                backup_path=Path(self.temp.name) / "backup.sqlite",
            )
        row = self.connection.execute(
            "SELECT status, error_code FROM mutation_request WHERE command_id = ?",
            (command.command_id,),
        ).fetchone()
        self.assertEqual(tuple(row), ("failed", "handler_failed"))
        self.assertEqual(
            self.connection.execute(
                "SELECT count(*) FROM mutation_request WHERE status = 'running'"
            ).fetchone()[0],
            0,
        )
        self.assertIsNone(
            self.connection.execute(
                "SELECT value FROM system_state WHERE key = 'handler-write'"
            ).fetchone()
        )
        with self.assertRaisesRegex(MutationError, "previously failed"):
            apply(
                self.connection,
                command,
                lambda *_: calls.append("rerun"),
                parent_git_sha="a" * 40,
                backup_path=Path(self.temp.name) / "backup.sqlite",
            )
        self.assertEqual(calls, [True])

    def test_backup_failure_leaves_applied_and_duplicate_recovers_without_rerun(self):
        for key, value in (("input_revision", "r1"), ("policy_version", "p1"), ("policy_epoch", "0")):
            self.connection.execute("INSERT INTO system_state(key, value) VALUES (?, ?)", (key, value))
        command = MutationCommand("backup-crash", "test", "r1", "p1", 0, {})
        calls = []
        backup_path = Path(self.temp.name) / "backup.sqlite"
        with patch("esports_data.mutation.backup", side_effect=OSError("backup crash")):
            with self.assertRaises(ArtifactIncompleteError) as raised:
                apply(
                    self.connection,
                    command,
                    lambda *_: calls.append(True),
                    parent_git_sha="a" * 40,
                    backup_path=backup_path,
                )
        self.assertEqual(raised.exception.receipt.status, "applied")
        self.assertEqual(
            self.connection.execute(
                "SELECT status FROM mutation_request WHERE command_id = ?",
                (command.command_id,),
            ).fetchone()[0],
            "applied",
        )
        replay = apply(
            self.connection,
            command,
            lambda *_: calls.append("rerun"),
            parent_git_sha="a" * 40,
            backup_path=backup_path,
        )
        self.assertEqual(calls, [True])
        self.assertTrue(backup_path.exists())
        self.assertEqual(replay.receipt, raised.exception.receipt)
        self.assertEqual(replay.checkpoint_artifact.integrity_check, ("ok",))

    def test_queued_state_drift_is_checked_under_the_execution_writer_lock(self):
        for key, value in (("input_revision", "r1"), ("policy_version", "p1"), ("policy_epoch", "0")):
            self.connection.execute("INSERT INTO system_state(key, value) VALUES (?, ?)", (key, value))
        command = MutationCommand("state-drift", "test", "r1", "p1", 0, {})
        self.assertEqual(queue(self.connection, command), "queued")
        self.connection.execute("UPDATE system_state SET value = 'r2' WHERE key = 'input_revision'")
        calls = []
        with self.assertRaisesRegex(MutationError, "input revision"):
            apply(
                self.connection,
                command,
                lambda *_: calls.append(True),
                parent_git_sha="a" * 40,
                backup_path=Path(self.temp.name) / "backup.sqlite",
            )
        self.assertEqual(calls, [])
        self.assertEqual(
            self.connection.execute(
                "SELECT status FROM mutation_request WHERE command_id = ?",
                (command.command_id,),
            ).fetchone()[0],
            "queued",
        )

    def test_mutation_request_guards_terminal_history(self):
        for key, value in (("input_revision", "r1"), ("policy_version", "p1"), ("policy_epoch", "0")):
            self.connection.execute("INSERT INTO system_state(key, value) VALUES (?, ?)", (key, value))
        self.connection.execute(
            """INSERT INTO mutation_request
               (command_id, request_kind, input_revision, policy_version, policy_epoch, status, payload_json)
               VALUES ('forward', 'test', 'r1', 'p1', 0, 'queued', '{}')"""
        )
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute("UPDATE mutation_request SET status = 'applied' WHERE command_id = 'forward'")
        self.connection.execute(
            "UPDATE mutation_request SET status = 'running', parent_git_sha = ? WHERE command_id = 'forward'",
            ("a" * 40,),
        )
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute("UPDATE mutation_request SET status = 'failed' WHERE command_id = 'forward'")
        command = MutationCommand("append-only", "test", "r1", "p1", 0, {"safe": "aggregate"})
        apply(
            self.connection,
            command,
            lambda *_: None,
            parent_git_sha="a" * 40,
            backup_path=Path(self.temp.name) / "backup.sqlite",
        )
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute("DELETE FROM mutation_request WHERE command_id = 'append-only'")
        self.connection.execute(
            """INSERT INTO mutation_request
               (command_id, request_kind, input_revision, policy_version, policy_epoch, status, payload_json, error_code)
               VALUES ('failed-terminal', 'test', 'r1', 'p1', 0, 'failed', '{}', 'handler_failed')"""
        )
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute("DELETE FROM mutation_request WHERE command_id = 'failed-terminal'")
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                "UPDATE mutation_request SET error_code = 'other' WHERE command_id = 'failed-terminal'"
            )
    def test_review_candidates_require_exact_enum_and_bool_types(self):
        self.assertEqual(PrimaryReview("review-1", ReviewStatus.ACTIVE).status, ReviewStatus.ACTIVE)
        self.assertEqual(RelatedProposal("proposal-1", ProposalStatus.ACTIVE).status, ProposalStatus.ACTIVE)
        self.assertTrue(PublicationCandidate("candidate-1", Relation.PRIMARY, True).active)
        for constructor, args in (
            (PrimaryReview, ("review-1", "active")),
            (RelatedProposal, ("proposal-1", "active")),
            (PublicationCandidate, ("candidate-1", "primary", True)),
            (PublicationCandidate, ("candidate-1", Relation.PRIMARY, "active")),
            (PublicationCandidate, ("candidate-1", Relation.PRIMARY, 1)),
        ):
            with self.subTest(constructor=constructor.__name__, args=args):
                with self.assertRaises(ReviewError):
                    constructor(*args)
        self.assertFalse(publication_eligibility([], []).eligible)

    def test_identity_inputs_reject_wrong_types_blank_and_name_like_values(self):
        with self.assertRaises(IdentityError):
            AuthorityIdentity(SubjectKind.SCHOOL, "wrong.namespace", "ABCDEFGHIJ")
        with self.assertRaises(IdentityError):
            PrimaryReviewIdentity(SubjectKind.SCHOOL, "Synthetic School")
        with self.assertRaises(IdentityError):
            RelatedProposalIdentity("not-a-review", self.authority(SubjectKind.SCHOOL))  # type: ignore[arg-type]
