import argparse
import copy
from dataclasses import replace
import hmac
import json
import os
from datetime import datetime, timedelta, timezone
import tempfile
import unittest
import socket
from hashlib import sha256
from inspect import signature
from pathlib import Path
from urllib.parse import urlsplit
from unittest.mock import MagicMock, patch

from jsonschema import Draft202012Validator

from esports_data.cli import _lock_is_verified, _validate_staged_artifacts, _validate_staged_replay, main
from esports_data import publish as publish_module
from esports_data.db import connect
from esports_data.fetch import fetch_and_process_registered
from esports_data.identity import AUTHORITY_NAMESPACE_NAMES, AuthorityIdentity, insert_authority_subject
from esports_data.ingest import ingest_extraction
from esports_data.migrate import migrate
from esports_data.models import SubjectKind
from esports_data.policy import (
    PolicySnapshot, PolicyValidationError, Publisher, PublisherPolicy, assess_policy_change, canonical_policy_hash,
    load_claim_requirement_policy, load_freshness_policy, load_publisher_policy,
)
from esports_data.publish import CompareAndSwapError, PublicationIndeterminateError, PublishError, canonical_json, publish_snapshot
from esports_data.quality import GateCheck, GateReport, GateState, QualityInputs, evaluate_gate
from esports_data.review import ReviewAction, ReviewCommand, apply_review_command_sqlite
from esports_data.verify import (
    ClaimEvidence, RequiredClaim, VerificationReasonCode, VerificationStatus,
    derive_record_status, plan_reverification, record_evidence_review,
    verify_candidate_from_db, verify_required_claims,
)
from esports_data.registry import RegistryValidationError, SourceRegistry, load_source_registry


HASH = sha256((Path(__file__).parents[2] / "schemas" / "snapshot-v3.schema.json").read_bytes()).hexdigest()
POLICY = PublisherPolicy({
    "official": Publisher("official", "official", "official"),
    "trusted-a": Publisher("trusted-a", "control-a", "origin-a"),
    "trusted-b": Publisher("trusted-b", "control-b", "origin-b"),
})


def evidence(evidence_id, publisher_id, *, official=False, direct=True, trusted=True, scope="scope"):
    return ClaimEvidence("claim", evidence_id, publisher_id, publisher_id, f"https://{evidence_id}.example.test", frozenset({scope}), direct, official, trusted)


def passing_gate():
    return evaluate_gate(QualityInputs(1, 0, 0, 1, .98, True, True, True, 0, 0, False, "pass"))


def projection(record_ids=("rec-one",), *, evidence_ids=("evi-one",), source_ids=("src-one",)):
    sources = [{"source_id": source_id, "tier": "core", "url": f"https://{source_id}.example.test"} for source_id in source_ids]
    evidence_items = [{"evidence_id": evidence_id, "source_id": source_ids[0], "url": f"https://{evidence_id}.example.test", "observed_at": "2026-01-01T00:00:00Z", "checksum": HASH} for evidence_id in evidence_ids]
    records = [{
        "record_id": record_id,
        "subject_id": "sub-one",
        "status": "verified",
        "claims": [{"claim_id": f"clm-{index}", "kind": "rank", "value": index, "evidence_id": evidence_ids[0], "source_id": source_ids[0]}],
        "evidence_ids": [evidence_ids[0]],
        "source_ids": [source_ids[0]],
    } for index, record_id in enumerate(record_ids)]
    return {"records": records, "evidence": evidence_items, "sources": sources}


class VerifyAndPublishTests(unittest.TestCase):
    def setUp(self):
        self.context = {
            "PUBLICATION_WORKFLOW_SHA": "c" * 40,
            "PUBLICATION_TARGET_SHA": "b" * 40,
            "PUBLICATION_ENVIRONMENT": "staging",
            "PUBLICATION_READBACK_ORIGIN": "https://public.example.test",
            "PUBLICATION_OUTPUT_DIR": "public",
        }
        self.environment = patch.dict(os.environ, self.context)
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def _authorized_publication(self, directory):
        base = Path(directory)
        database = base / "control.sqlite"
        database.write_bytes(b"staged database")
        schema_sha256 = sha256((Path(__file__).parents[2] / "schemas" / "snapshot-v3.schema.json").read_bytes()).hexdigest()
        request = {"content": projection(), "schema_hash": schema_sha256, "policy_hash": HASH, "revision": "r1", "epoch": 1, "correction_epoch": 1, "stop_epoch": 0, "expected_current": None}
        quality, budget = passing_gate().as_dict(), {"status": "PASS"}
        paths = {name: base / f"{name}.json" for name in ("request", "receipt", "quality", "budget")}
        paths["request"].write_bytes(canonical_json(request))
        paths["quality"].write_bytes(canonical_json(quality))
        paths["budget"].write_bytes(canonical_json(budget))
        receipt = {"command_id": "publish-001", "parent_git_sha": "b" * 40, "output_revision": "r1", "sqlite_file_sha256": sha256(database.read_bytes()).hexdigest(), "policy_hash": HASH, "correction_epoch": 1, "stop_epoch": 0, "schema_sha256": schema_sha256, "migration_sha256": "d" * 64, "changed_file_sha256": {"projection/request.json": sha256(paths["request"].read_bytes()).hexdigest(), "control.sqlite": sha256(database.read_bytes()).hexdigest()}}
        paths["receipt"].write_bytes(canonical_json(receipt))
        paths["database"] = database
        authorization = {
            "command_receipt_sha256": sha256(paths["receipt"].read_bytes()).hexdigest(), "parent_git_sha": receipt["parent_git_sha"], "output_revision": "r1", "sqlite_file_sha256": receipt["sqlite_file_sha256"], "policy_hash": HASH, "schema_sha256": schema_sha256, "migration_sha256": receipt["migration_sha256"], "correction_epoch": 1, "stop_epoch": 0,
            "projection_request_sha256": sha256(paths["request"].read_bytes()).hexdigest(), "quality_report_sha256": sha256(paths["quality"].read_bytes()).hexdigest(), "quality_passed": True, "budget_report_sha256": sha256(paths["budget"].read_bytes()).hexdigest(), "budget_status": "PASS", "expected_current": None, "operation": "normal", "repository": "owner/repository", "workflow_ref": "owner/repository/.github/workflows/publish.yml@refs/heads/main", "target_ref": "refs/heads/main", "workflow_sha": "c" * 40, "target_sha": "b" * 40, "environment": "staging", "output_dir": "public", "nonce_ledger": ".publication-nonces", "readback_origin": "https://public.example.test", "nonce": "test-nonce-" + sha256(str(base).encode()).hexdigest()[:16], "issued_at": datetime.now(timezone.utc).isoformat(), "freshness_seconds": 60,
        }
        authorization["signature_hmac_sha256"] = hmac.new(
            bytes.fromhex("1" * 64), canonical_json(authorization), "sha256",
        ).hexdigest()
        paths["authorization"] = base / "authorization.json"
        paths["authorization"].write_bytes(canonical_json(authorization))
        paths["result"] = base / "result.json"
        return paths, authorization

    def _resign(self, authorization):
        authorization["signature_hmac_sha256"] = hmac.new(
            bytes.fromhex("1" * 64),
            canonical_json({key: value for key, value in authorization.items() if key != "signature_hmac_sha256"}),
            "sha256",
        ).hexdigest()
        return authorization

    def _publish_args(self, paths, root):
        return ["publish", "--input", str(paths["request"]), "--authorization", str(paths["authorization"]), "--receipt", str(paths["receipt"]), "--quality-report", str(paths["quality"]), "--budget-report", str(paths["budget"]), "--output-dir", str(root), "--result-file", str(paths["result"]), "--database", str(paths["database"]), "--staged-file", f"projection/request.json={paths['request']}", "--staged-file", f"control.sqlite={paths['database']}", "--repository", "owner/repository", "--workflow-ref", "owner/repository/.github/workflows/publish.yml@refs/heads/main", "--target-ref", "refs/heads/main"]
    def test_signed_authorization_context_and_nonce_are_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            paths, authorization = self._authorized_publication(directory)
            root = Path(directory) / "public"
            arguments = self._publish_args(paths, root)
            with patch.dict(os.environ, {"PUBLICATION_AUTHORIZATION_KEY": "hex:" + "2" * 64}):
                self.assertEqual(main(arguments), 2)
            with patch.dict(os.environ, {"PUBLICATION_AUTHORIZATION_KEY": "hex:" + "1" * 64}):
                self.assertEqual(main(arguments + ["--repository", "other/repository"]), 2)
                self.assertEqual(main(arguments + ["--target-ref", "refs/heads/other"]), 2)
                self.assertEqual(main(arguments + ["--workflow-ref", "other/repository/.github/workflows/publish.yml@refs/heads/main"]), 2)
            paths["authorization"].write_bytes(canonical_json(
                {key: value for key, value in authorization.items() if key != "signature_hmac_sha256"}
            ))
            with patch.dict(os.environ, {"PUBLICATION_AUTHORIZATION_KEY": "hex:" + "1" * 64}):
                self.assertEqual(main(arguments), 2)
            emergency = self._resign({**authorization, "operation": "emergency"})
            paths["authorization"].write_bytes(canonical_json(emergency))
            with patch.dict(os.environ, {"PUBLICATION_AUTHORIZATION_KEY": "hex:" + "1" * 64}):
                self.assertEqual(main(arguments), 2)
            paths["authorization"].write_bytes(canonical_json(authorization))
            with patch.dict(os.environ, {"PUBLICATION_AUTHORIZATION_KEY": "hex:" + "1" * 64}):
                self.assertEqual(main(arguments), 0)
                self.assertEqual(main(arguments), 0)
            marker = root / ".publication-nonces" / f"{sha256(authorization['nonce'].encode()).hexdigest()}.json"
            self.assertTrue(marker.is_file())
            paths, _ = self._authorized_publication(directory)
            with patch.dict(os.environ, {"PUBLICATION_AUTHORIZATION_KEY": "hex:" + "1" * 64}):
                self.assertEqual(main(self._publish_args(paths, Path(directory) / "other-public")), 2)
            paths, _ = self._authorized_publication(directory)
            with patch.dict(os.environ, {
                "PUBLICATION_AUTHORIZATION_KEY": "hex:" + "1" * 64,
                "PUBLICATION_OUTPUT_DIR": "other-public",
            }):
                self.assertEqual(main(self._publish_args(paths, Path(directory) / "public")), 2)
            paths, authorization = self._authorized_publication(directory)
            paths["authorization"].write_bytes(canonical_json(self._resign({
                **authorization,
                "workflow_ref": "owner/repository/.github/workflows/other.yml@refs/heads/main",
            })))
            with patch.dict(os.environ, {"PUBLICATION_AUTHORIZATION_KEY": "hex:" + "1" * 64}):
                self.assertEqual(main(self._publish_args(paths, Path(directory) / "public")), 2)

    def test_signed_execution_context_and_secret_scope_are_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            paths, authorization = self._authorized_publication(directory)
            arguments = self._publish_args(paths, "public")
            for field, value in (
                ("workflow_sha", "d" * 40),
                ("target_sha", "d" * 40),
                ("environment", "production"),
                ("output_dir", "other-public"),
                ("nonce_ledger", ".other-nonces"),
                ("readback_origin", "https://other.example.test"),
                ("schema_sha256", "d" * 64),
            ):
                changed = self._resign({**authorization, field: value})
                paths["authorization"].write_bytes(canonical_json(changed))
                with patch.dict(os.environ, {"PUBLICATION_AUTHORIZATION_KEY": "hex:" + "1" * 64}):
                    self.assertEqual(main(arguments), 2)
            for workflow in ("publish.yml", "emergency-withdraw.yml"):
                text = (Path(__file__).parents[2] / ".github" / "workflows" / workflow).read_text()
                lines = text.splitlines()
                self.assertFalse(any(
                    line.startswith("      PUBLICATION_AUTHORIZATION_KEY:")
                    for line in lines
                ))
                self.assertEqual(sum(
                    line.startswith("          PUBLICATION_AUTHORIZATION_KEY:")
                    for line in lines
                ), 1)

    def test_successful_nonce_replay_rejects_resigned_different_artifact_binding(self):
        with tempfile.TemporaryDirectory() as directory:
            paths, authorization = self._authorized_publication(directory)
            root = Path(directory) / "public"
            with patch.dict(os.environ, {"PUBLICATION_AUTHORIZATION_KEY": "hex:" + "1" * 64}):
                self.assertEqual(main(self._publish_args(paths, root)), 0)

            paths, replay = self._authorized_publication(directory)
            request = json.loads(paths["request"].read_text())
            request["revision"] = "r2"
            paths["request"].write_bytes(canonical_json(request))
            receipt = json.loads(paths["receipt"].read_text())
            receipt["output_revision"] = "r2"
            receipt["changed_file_sha256"]["projection/request.json"] = sha256(paths["request"].read_bytes()).hexdigest()
            paths["receipt"].write_bytes(canonical_json(receipt))
            replay.update({
                "command_receipt_sha256": sha256(paths["receipt"].read_bytes()).hexdigest(),
                "output_revision": "r2",
                "projection_request_sha256": sha256(paths["request"].read_bytes()).hexdigest(),
            })
            paths["authorization"].write_bytes(canonical_json(self._resign(replay)))

            with patch.dict(os.environ, {"PUBLICATION_AUTHORIZATION_KEY": "hex:" + "1" * 64}):
                self.assertEqual(main(self._publish_args(paths, root)), 2)

    def test_staged_artifact_names_cannot_alias_one_local_file(self):
        with tempfile.TemporaryDirectory() as directory:
            artifact = Path(directory) / "control.sqlite"
            receipt_path = Path(directory) / "receipt.json"
            artifact.write_bytes(b"same bytes")
            receipt_path.write_text("{}")
            digest = sha256(artifact.read_bytes()).hexdigest()
            args = argparse.Namespace(
                staged_file=[
                    f"control.sqlite={artifact}",
                    f"projection/request.json={artifact}",
                ],
                database=str(artifact),
                receipt=str(receipt_path),
            )
            receipt = {
                "changed_file_sha256": {
                    "control.sqlite": digest,
                    "projection/request.json": digest,
                },
                "sqlite_file_sha256": digest,
            }
            with self.assertRaises(ValueError):
                _validate_staged_artifacts(args, receipt)

    def test_staged_publication_replay_rechecks_current_pointer_cas(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = {"snapshot_id": "a" * 64, "prior_pointer": "b" * 64}
            (root / "current.json").write_text(json.dumps({"snapshot_id": "c" * 64}))
            with self.assertRaises(ValueError):
                _validate_staged_replay(root, result)
            for allowed in ("b" * 64, "a" * 64):
                (root / "current.json").write_text(json.dumps({"snapshot_id": allowed}))
                _validate_staged_replay(root, result)
    def test_publication_authorization_binds_artifacts_and_result_is_pii_free(self):
        schema = json.loads((Path(__file__).parents[2] / "schemas" / "publication-authorization-v1.schema.json").read_text())
        with tempfile.TemporaryDirectory() as directory:
            paths, authorization = self._authorized_publication(directory)
            Draft202012Validator(schema).validate(authorization)
            with self.assertRaises(Exception):
                Draft202012Validator(schema).validate({**authorization, "containing_commit_sha": "f" * 40})
            with patch.dict(os.environ, {"PUBLICATION_AUTHORIZATION_KEY": "hex:" + "1" * 64}):
                self.assertEqual(main(self._publish_args(paths, Path(directory) / "public")), 0)
            result = json.loads(paths["result"].read_text())
            self.assertEqual(set(result), {"snapshot_id", "manifest_sha256", "prior_pointer", "current_pointer"})
            self.assertNotIn(paths["receipt"].read_text(), paths["result"].read_text())

    def test_publication_authorization_rejects_tampering_mismatch_expiry_and_self_asserted_gate(self):
        with tempfile.TemporaryDirectory() as directory:
            paths, _ = self._authorized_publication(directory)
            paths["request"].write_bytes(canonical_json({"tampered": True}))
            self.assertEqual(main(self._publish_args(paths, Path(directory) / "public")), 2)
            for artifact in ("quality", "receipt", "budget"):
                paths, _ = self._authorized_publication(directory)
                paths[artifact].write_bytes(canonical_json({"status": "HARD" if artifact == "budget" else "PASS"}))
                self.assertEqual(main(self._publish_args(paths, Path(directory) / "public")), 2)
            for field, value in (("policy_hash", "f" * 64), ("revision", "r2"), ("epoch", 2), ("correction_epoch", 2), ("stop_epoch", 2), ("expected_current", "f" * 64)):
                paths, authorization = self._authorized_publication(directory)
                request = json.loads(paths["request"].read_text())
                request[field] = value
                paths["request"].write_bytes(canonical_json(request))
                authorization["projection_request_sha256"] = sha256(paths["request"].read_bytes()).hexdigest()
                paths["authorization"].write_bytes(canonical_json(self._resign(authorization)))
                self.assertEqual(main(self._publish_args(paths, Path(directory) / "public")), 2)
            for field, value in (
                ("policy_hash", "f" * 64),
                ("issued_at", (datetime.now(timezone.utc) - timedelta(seconds=61)).isoformat()),
                ("freshness_seconds", 0),
                ("nonce", "tampered-nonce"),
                ("expected_current", "f" * 64),
            ):
                paths, authorization = self._authorized_publication(directory)
                authorization[field] = value
                paths["authorization"].write_bytes(canonical_json(self._resign(authorization)))
                self.assertEqual(main(self._publish_args(paths, Path(directory) / "public")), 2)
            paths, _ = self._authorized_publication(directory)
            request = json.loads(paths["request"].read_text())
            request["gate_inputs"] = {}
            paths["request"].write_bytes(canonical_json(request))
            self.assertEqual(main(self._publish_args(paths, Path(directory) / "public")), 2)
            paths, authorization = self._authorized_publication(directory)
            authorization["quality_passed"] = False
            paths["authorization"].write_bytes(canonical_json(self._resign(authorization)))
            self.assertEqual(main(self._publish_args(paths, Path(directory) / "public")), 2)
    def test_source_registry_publisher_provenance_is_explicit_and_fail_closed(self):
        root = Path(__file__).parents[2]
        source_path = root / "config" / "sources.toml"
        publisher_path = root / "config" / "publishers.toml"
        registry = load_source_registry(source_path)
        publishers = load_publisher_policy(publisher_path)

        self.assertEqual(len(registry.sources), 18)
        self.assertEqual(set(publishers.publishers), {record.publisher_id for record in registry.sources})
        for record in registry.sources:
            parsed = urlsplit(record.endpoint)
            self.assertEqual(record.canonical_origin, ("https", parsed.hostname, 443))
            self.assertEqual(parsed.scheme, "https")
            self.assertIsNone(parsed.port)
            self.assertFalse(parsed.query)
            self.assertFalse(parsed.fragment)
            self.assertIsNone(parsed.username)
            self.assertIsNone(parsed.password)
            publisher = publishers.publishers[record.publisher_id]
            self.assertEqual(
                (record.control_cluster, record.origin_cluster),
                (publisher.control_cluster, publisher.origin_cluster),
            )
            self.assertTrue(record.authority_scopes)
        claims_path = root / "config" / "claims.toml"
        claims = load_claim_requirement_policy(claims_path)
        self.assertEqual(set(claims.requirements), {kind.value for kind in SubjectKind})
        self.assertTrue(all("official_status" in requirements for requirements in claims.requirements.values()))
        with tempfile.TemporaryDirectory() as directory:
            changed_path = Path(directory) / "claims.toml"
            changed_path.write_text(claims_path.read_text().replace(
                'required_predicates = ["official_status"]',
                'required_predicates = ["official_status", "team_count"]', 1,
            ))
            changed = load_claim_requirement_policy(changed_path)
            self.assertNotEqual(canonical_policy_hash(claims), canonical_policy_hash(changed))
            baseline = PolicySnapshot(
                freshness=load_freshness_policy(root / "config" / "freshness.toml"),
                publishers=publishers, registry=registry, claims=claims,
            )
            impact = assess_policy_change(
                baseline,
                PolicySnapshot(
                    freshness=baseline.freshness, publishers=publishers, registry=registry, claims=changed,
                ),
            )
            self.assertEqual(impact.changed_sections, ("claims",))
            self.assertTrue(impact.requires_revalidation)
            invalid_path = Path(directory) / "invalid-claims.toml"
            invalid_path.write_text(claims_path.read_text().replace(
                'required_predicates = ["official_status"]', 'required_predicates = ["unknown"]', 1,
            ))
            with self.assertRaises(PolicyValidationError):
                load_claim_requirement_policy(invalid_path)

        source_text = source_path.read_text()
        with tempfile.TemporaryDirectory() as directory:
            candidate = Path(directory) / "sources.toml"
            candidate.write_text(source_text.replace('publisher_id = "moe"', 'publisher_id = "unknown"', 1))
            with self.assertRaises(RegistryValidationError):
                load_source_registry(candidate)
            candidate.write_text(source_text.replace('authority_scopes = ["national:program", "national:organization"]', 'authority_scopes = ["unknown:scope"]', 1))
            with self.assertRaises(RegistryValidationError):
                load_source_registry(candidate)
            candidate.write_text(source_text.replace('https://www.moe.go.kr/', 'https://www.moe.go.kr/?token=private', 1))
            with self.assertRaises(RegistryValidationError):
                load_source_registry(candidate)

            candidate.write_text(publisher_path.read_text().replace('id = "moe"', 'id = "unknown"', 1))
            with self.assertRaises(PolicyValidationError):
                load_publisher_policy(candidate)

    def test_independence_requires_both_provenance_axes(self):
        policy = PublisherPolicy({
            "left": Publisher("left", "control-a", "origin-a"),
            "same-control": Publisher("same-control", "control-a", "origin-b"),
            "same-origin": Publisher("same-origin", "control-b", "origin-a"),
            "independent": Publisher("independent", "control-b", "origin-b"),
        })
        self.assertFalse(policy.are_independent("left", "same-control"))
        self.assertFalse(policy.are_independent("left", "same-origin"))
        self.assertTrue(policy.are_independent("left", "independent"))
        self.assertFalse(policy.are_independent("left", "unknown"))
    def test_claim_truth_table_requires_scope_directness_trust_and_independence(self):
        required = [RequiredClaim("claim", "scope")]
        missing = verify_required_claims(required, [], POLICY, registry_hash=HASH)
        self.assertEqual(missing.status, VerificationStatus.PRIVATE)
        wrong_scope = verify_required_claims(required, [evidence("one", "official", official=True, scope="other")], POLICY, registry_hash=HASH)
        self.assertEqual(wrong_scope.claim_decisions[0].reason_code, VerificationReasonCode.AUTHORITY_SCOPE_MISMATCH)
        indirect = verify_required_claims(required, [evidence("one", "official", official=True, direct=False)], POLICY, registry_hash=HASH)
        self.assertEqual(indirect.claim_decisions[0].reason_code, VerificationReasonCode.DIRECT_EVIDENCE_REQUIRED)
        same_lineage = verify_required_claims(required, [evidence("one", "trusted-a"), evidence("two", "trusted-a")], POLICY, registry_hash=HASH)
        self.assertEqual(same_lineage.status, VerificationStatus.PRIVATE)
        provisional = verify_required_claims(required, [evidence("one", "trusted-a"), evidence("two", "trusted-b")], POLICY, registry_hash=HASH)
        self.assertEqual(provisional.status, VerificationStatus.PROVISIONAL)
        verified = verify_required_claims(required, [evidence("one", "official", official=True)], POLICY, registry_hash=HASH)
        self.assertEqual(verified.status, VerificationStatus.VERIFIED)

    def test_duplicate_claim_decisions_are_rejected_before_status_collapse(self):
        required = [RequiredClaim("claim", "scope"), RequiredClaim("other", "scope")]
        decision = verify_required_claims([required[0]], [evidence("one", "official", official=True)], POLICY, registry_hash=HASH).claim_decisions[0]
        with self.assertRaises(ValueError):
            derive_record_status((decision, decision), required)

    def test_policy_input_change_creates_pending_reverification_only_for_changed_claim(self):
        decision = verify_required_claims([RequiredClaim("claim", "scope")], [evidence("one", "official", official=True)], POLICY, registry_hash=HASH).claim_decisions
        self.assertFalse(plan_reverification(decision, policy_hash=decision[0].policy_hash, publisher_hash=decision[0].publisher_hash, registry_hash=HASH).actions)
        actions = plan_reverification(decision, policy_hash="b" * 64, publisher_hash=decision[0].publisher_hash, registry_hash=HASH).actions
        self.assertEqual(actions[0].status, VerificationStatus.REVERIFICATION_PENDING)
    def test_db_verifier_does_not_accept_self_asserted_evidence_fields(self):
        for verifier in (verify_candidate_from_db, record_evidence_review):
            parameters = set(signature(verifier).parameters)
            self.assertFalse({"official", "trusted", "publisher_id", "url", "authority_scopes"} & parameters)
        self.assertEqual(
            set(signature(verify_candidate_from_db).parameters),
            {"connection", "candidate_id", "registry", "policy"},
        )

    def test_db_verifier_materializes_only_authorized_reviewed_registry_evidence(self):
        root = Path(__file__).parents[2]
        registry = load_source_registry(root / "config" / "sources.toml")
        policy = PolicySnapshot(
            freshness=load_freshness_policy(root / "config" / "freshness.toml"),
            publishers=load_publisher_policy(root / "config" / "publishers.toml"),
            registry=registry, claims=load_claim_requirement_policy(root / "config" / "claims.toml"),
        )
        document = b'{"facts":[{"predicate":"official_status","value":true,"evidence":"Official program","locator":"program"}]}'

        with tempfile.TemporaryDirectory() as directory:
            connection = connect(Path(directory) / "control.sqlite")
            self.addCleanup(connection.close)
            migrate(connection)
            response = MagicMock(status=200, headers={})
            response.read.return_value = document
            with patch("esports_data.fetch._PinnedHTTPSConnection") as connection_class, patch(
                "esports_data.fetch.socket.getaddrinfo",
                return_value=[(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("8.8.8.8", 443))],
            ):
                connection_class.return_value.getresponse.return_value = response
                registered_fetch = fetch_and_process_registered(
                    registry,
                    "moe",
                    "https://www.moe.go.kr/notices/synthetic",
                    "json",
                    salt="test",
                )
            ingested = ingest_extraction(
                connection,
                registry=registry,
                registered_fetch=registered_fetch,
                retrieved_at="2026-01-01T00:00:00Z",
                salt="test",
                proposed_kind=SubjectKind.PROGRAM,
                hint_digest=HASH,
                reason_code="authority_key_missing",
            )
            candidate_id, fact_id = ingested.candidate_id, ingested.fact_ids[0]
            review_id = connection.execute(
                "SELECT review_identity_id FROM review_identity WHERE candidate_id = ?", (candidate_id,)
            ).fetchone()[0]
            self.assertEqual(verify_candidate_from_db(
                connection, candidate_id=candidate_id, registry=registry, policy=policy,
            ).status, VerificationStatus.PRIVATE)
            self.assertEqual(connection.execute("SELECT count(*) FROM claim").fetchone()[0], 0)
            subject_id = str(insert_authority_subject(
                connection,
                AuthorityIdentity(SubjectKind.PROGRAM, AUTHORITY_NAMESPACE_NAMES[SubjectKind.PROGRAM], "program-1"),
                canonical_name="National League", provenance_digest=HASH,
            ).subject_id)
            apply_review_command_sqlite(
                connection, candidate_id,
                ReviewCommand(
                    "resolve-1", "reviewer-1", 0, ReviewAction.RESOLVE_PRIMARY, review_id, subject_id
                ),
                allowed_actors=("reviewer-1",),
            )

            self.assertEqual(verify_candidate_from_db(
                connection, candidate_id=candidate_id, registry=registry, policy=policy,
            ).status, VerificationStatus.PRIVATE)
            self.assertEqual(connection.execute("SELECT count(*) FROM claim").fetchone()[0], 0)

            evidence_review_id = record_evidence_review(
                connection, fact_id=fact_id, authority_scope="national:program", direct=True,
                reviewer_receipt_digest="b" * 64, actor_id="reviewer-1", command_id="evidence-1",
                expected_version=0, allowed_actors=("reviewer-1",), registry=registry, policy=policy,
            )
            self.assertEqual(
                record_evidence_review(
                    connection, fact_id=fact_id, authority_scope="national:program", direct=True,
                    reviewer_receipt_digest="b" * 64, actor_id="reviewer-1", command_id="evidence-1",
                    expected_version=0, allowed_actors=("reviewer-1",), registry=registry, policy=policy,
                ),
                evidence_review_id,
            )
            with self.assertRaises(ValueError):
                record_evidence_review(
                    connection, fact_id=fact_id, authority_scope="national:program", direct=True,
                    reviewer_receipt_digest="b" * 64, actor_id="intruder", command_id="evidence-intruder",
                    expected_version=1, allowed_actors=("reviewer-1",), registry=registry, policy=policy,
                )
            with self.assertRaises(ValueError):
                record_evidence_review(
                    connection, fact_id=fact_id, authority_scope="national:program", direct=True,
                    reviewer_receipt_digest="b" * 64, actor_id="reviewer-1", command_id="evidence-stale",
                    expected_version=0, allowed_actors=("reviewer-1",), registry=registry, policy=policy,
                )
            with self.assertRaises(ValueError):
                record_evidence_review(
                    connection, fact_id=fact_id, authority_scope="national:program", direct=False,
                    reviewer_receipt_digest="b" * 64, actor_id="reviewer-1", command_id="evidence-1",
                    expected_version=0, allowed_actors=("reviewer-1",), registry=registry, policy=policy,
                )
            with self.assertRaises(Exception):
                connection.execute(
                    """INSERT INTO evidence_review(evidence_review_id, fact_id, authority_scope, direct,
                       reviewer_receipt_digest, policy_hash, status)
                       VALUES ('raw-review', ?, 'raw:scope', 1, ?, ?, 'active')""",
                    (fact_id, "e" * 64, canonical_policy_hash(policy)),
                )
            first = verify_candidate_from_db(
                connection, candidate_id=candidate_id, registry=registry, policy=policy,
            )
            self.assertEqual(first.status, VerificationStatus.VERIFIED)
            self.assertEqual(connection.execute("SELECT count(*) FROM claim").fetchone()[0], 1)
            self.assertEqual(connection.execute("SELECT count(*) FROM evidence").fetchone()[0], 1)
            self.assertEqual(connection.execute("SELECT count(*) FROM decision").fetchone()[0], 1)
            self.assertEqual(connection.execute("SELECT count(*) FROM publication").fetchone()[0], 1)
            self.assertEqual(
                connection.execute(
                    "SELECT input_hash FROM decision"
                ).fetchone()[0],
                first.claim_decisions[0].evidence_set_hash,
            )
            self.assertEqual(
                connection.execute(
                    """SELECT evidence_review_id FROM evidence_review
                       WHERE fact_id = ? AND authority_scope = ? AND status = 'active'""",
                    (fact_id, "national:program"),
                ).fetchone()[0],
                evidence_review_id,
            )

            rerun = verify_candidate_from_db(
                connection, candidate_id=candidate_id, registry=registry, policy=policy,
            )
            self.assertEqual(rerun, first)
            self.assertEqual(connection.execute("SELECT count(*) FROM claim").fetchone()[0], 1)
            self.assertEqual(connection.execute("SELECT count(*) FROM evidence").fetchone()[0], 1)
            self.assertEqual(connection.execute("SELECT count(*) FROM decision").fetchone()[0], 1)
            self.assertEqual(connection.execute("SELECT count(*) FROM publication").fetchone()[0], 1)

            record_evidence_review(
                connection, fact_id=fact_id, authority_scope="national:program", direct=False,
                reviewer_receipt_digest="c" * 64, actor_id="reviewer-1", command_id="evidence-2",
                expected_version=1, allowed_actors=("reviewer-1",), registry=registry, policy=policy,
            )
            self.assertEqual(verify_candidate_from_db(
                connection, candidate_id=candidate_id, registry=registry, policy=policy,
            ).status, VerificationStatus.PRIVATE)
            self.assertEqual(connection.execute("SELECT count(*) FROM decision").fetchone()[0], 1)

            record_evidence_review(
                connection, fact_id=fact_id, authority_scope="national:program", direct=True,
                reviewer_receipt_digest="d" * 64, actor_id="reviewer-1", command_id="evidence-3",
                expected_version=2, allowed_actors=("reviewer-1",), registry=registry, policy=policy,
            )
            self.assertEqual(verify_candidate_from_db(
                connection, candidate_id=candidate_id, registry=registry, policy=policy,
            ).status, VerificationStatus.VERIFIED)
            connection.execute(
                "UPDATE source SET registry_hash = ? WHERE registry_source_id = 'moe'",
                ("e" * 64,),
            )
            drifted = verify_candidate_from_db(
                connection, candidate_id=candidate_id, registry=registry, policy=policy,
            )
            self.assertEqual(drifted.status, VerificationStatus.REVERIFICATION_PENDING)
            self.assertEqual(connection.execute("SELECT count(*) FROM decision").fetchone()[0], 2)
            self.assertEqual(connection.execute("SELECT count(*) FROM publication").fetchone()[0], 2)
            self.assertIsNotNone(connection.execute("SELECT retracted_at FROM publication").fetchone()[0])
            self.assertEqual(connection.execute(
                "SELECT status FROM candidate WHERE candidate_id = ?", (candidate_id,)
            ).fetchone()[0], VerificationStatus.REVERIFICATION_PENDING.value)
            self.assertEqual(connection.execute(
                """SELECT count(*) FROM review_item
                   WHERE candidate_id = ? AND status = 'active' AND reason = 'reverification_input_changed'""",
                (candidate_id,),
            ).fetchone()[0], 1)
            connection.execute(
                "UPDATE source SET registry_hash = ? WHERE registry_source_id = 'moe'",
                (canonical_policy_hash(registry),),
            )
            restored = verify_candidate_from_db(
                connection, candidate_id=candidate_id, registry=registry, policy=policy,
            )
            self.assertEqual(restored.status, VerificationStatus.VERIFIED)
            self.assertEqual(connection.execute("SELECT count(*) FROM decision").fetchone()[0], 2)
            self.assertEqual(connection.execute(
                "SELECT count(*) FROM publication WHERE retracted_at IS NULL"
            ).fetchone()[0], 1)
            self.assertEqual(connection.execute(
                "SELECT count(*) FROM review_item WHERE candidate_id = ? AND status = 'active'",
                (candidate_id,),
            ).fetchone()[0], 0)
            self.assertEqual(connection.execute(
                "SELECT status FROM candidate WHERE candidate_id = ?", (candidate_id,)
            ).fetchone()[0], "review")
            self.assertGreaterEqual(connection.execute(
                """SELECT count(*) FROM review_item
                   WHERE candidate_id = ? AND status = 'resolved'
                     AND reason = 'reverification_input_changed'""",
                (candidate_id,),
            ).fetchone()[0], 1)
            for column, changed, original in (
                ("registry_source_id", "other-source", "moe"),
                ("publisher_id", "other-publisher", "moe"),
                ("control_cluster", "other-control", "moe-national-control"),
                ("origin_cluster", "other-origin", "moe-public-origin"),
                ("access_basis", "official_open_data_api", "official_public_website"),
                ("authority_scopes_json", '["other:scope"]', '["national:organization","national:program"]'),
                ("url_host", "other.example.test", "www.moe.go.kr"),
            ):
                connection.execute(f"UPDATE source SET {column} = ?", (changed,))
                self.assertEqual(
                    verify_candidate_from_db(connection, candidate_id=candidate_id, registry=registry, policy=policy).status,
                    VerificationStatus.REVERIFICATION_PENDING,
                    column,
                )
                connection.execute(f"UPDATE source SET {column} = ?", (original,))
                self.assertEqual(
                    verify_candidate_from_db(connection, candidate_id=candidate_id, registry=registry, policy=policy).status,
                    VerificationStatus.VERIFIED,
                    column,
                )
            inactive_registry = SourceRegistry(tuple(
                replace(
                    source,
                    active=False,
                    approval_reason="synthetic approved deactivation",
                ) if source.source_id == "moe" else source
                for source in registry.sources
            ))
            inactive_policy = PolicySnapshot(
                freshness=policy.freshness, publishers=policy.publishers,
                registry=inactive_registry, claims=policy.claims,
            )
            self.assertEqual(
                verify_candidate_from_db(
                    connection, candidate_id=candidate_id, registry=inactive_registry, policy=inactive_policy,
                ).status,
                VerificationStatus.REVERIFICATION_PENDING,
            )
    def test_publication_rejects_incomplete_or_forged_gate_reports(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(PublishError):
                publish_snapshot(
                    root, projection(), schema_hash=HASH, policy_hash=HASH, revision="r1", epoch=0,
                    gate=GateReport(GateState.PASS, ()), expected_current_id=None,
                )
            checks = list(passing_gate().checks)
            checks[1] = GateCheck("false_publications", True, 1, 0)
            with self.assertRaises(PublishError):
                publish_snapshot(
                    root, projection(), schema_hash=HASH, policy_hash=HASH, revision="r1", epoch=0,
                    gate=GateReport(GateState.PASS, tuple(checks)), expected_current_id=None,
                )
            self.assertTrue(evaluate_gate(QualityInputs(.99, 0, 0, 1, .98, True, True, True, 0, 0, False, "pass")).passed)
            self.assertFalse(evaluate_gate(QualityInputs(.989, 0, 0, 1, .98, True, True, True, 0, 0, False, "pass")).passed)
            self.assertFalse(evaluate_gate(QualityInputs(1, 0, 0, 1, .98, True, True, True, 0, 0, False, "PASS")).passed)
            self.assertFalse(evaluate_gate(QualityInputs(1, 0, 0, 1, .979, True, True, True, 0, 0, False, "pass")).passed)

    def test_schema_hash_must_identify_the_checked_in_schema(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(PublishError):
                publish_snapshot(
                    root, projection(), schema_hash="f" * 64, policy_hash=HASH, revision="r1", epoch=0,
                    gate=passing_gate(), expected_current_id=None,
                )

    def test_pointer_fsync_is_retried_before_recovered_success(self):
        with tempfile.TemporaryDirectory() as root:
            original_fsync = publish_module._fsync_directory
            root_path = Path(root)
            calls = 0

            def fail_once_after_replace(path):
                nonlocal calls
                if Path(path) == root_path:
                    calls += 1
                    if calls == 1:
                        raise OSError("directory sync failed")
                original_fsync(path)

            with patch.object(publish_module, "_fsync_directory", side_effect=fail_once_after_replace):
                published = publish_snapshot(
                    root, projection(), schema_hash=HASH, policy_hash=HASH, revision="r1", epoch=0,
                    gate=passing_gate(), expected_current_id=None,
                )
            self.assertEqual(calls, 2)
            self.assertEqual(
                json.loads((root_path / "current.json").read_text())["snapshot_id"], published["snapshot_id"],
            )

    def test_schema_and_immutable_cas_with_last_known_good(self):
        self.assertFalse(evaluate_gate({}).passed)
        schema = json.loads((Path(__file__).parents[2] / "schemas" / "snapshot-v3.schema.json").read_text())
        with tempfile.TemporaryDirectory() as root:
            first = publish_snapshot(root, projection(), schema_hash=HASH, policy_hash=HASH, revision="r1", epoch=0, gate=passing_gate(), expected_current_id=None)
            bundle = json.loads((Path(root) / "snapshots" / first["snapshot_id"] / "snapshot.json").read_text())
            Draft202012Validator(schema).validate(bundle)
            self.assertEqual(set(bundle), {"snapshot_id", "schema_hash", "policy_hash", "revision", "epoch", "records", "evidence", "sources"})
            with self.assertRaises(CompareAndSwapError):
                publish_snapshot(root, projection(), schema_hash=HASH, policy_hash=HASH, revision="r2", epoch=1, gate=passing_gate(), expected_current_id="wrong")
            self.assertEqual(json.loads((Path(root) / "current.json").read_text())["snapshot_id"], first["snapshot_id"])
            with self.assertRaises(PublishError):
                publish_snapshot(root, {**projection(), "revision": "injected"}, schema_hash=HASH, policy_hash=HASH, revision="r3", epoch=2, gate=passing_gate(), expected_current_id=first["snapshot_id"])

    def test_tampered_content_address_or_pointer_blocks_subsequent_publication(self):
        with tempfile.TemporaryDirectory() as root:
            first = publish_snapshot(root, projection(), schema_hash=HASH, policy_hash=HASH, revision="r1", epoch=0, gate=passing_gate(), expected_current_id=None)
            snapshot_path = Path(root) / "snapshots" / first["snapshot_id"] / "snapshot.json"
            manifest_path = snapshot_path.with_name("manifest.json")
            bundle = json.loads(snapshot_path.read_text())
            bundle["records"][0]["claims"][0]["value"] = 99
            snapshot_bytes = canonical_json(bundle)
            snapshot_path.write_bytes(snapshot_bytes)
            manifest = {"snapshot_id": first["snapshot_id"], "files": {"snapshot.json": sha256(snapshot_bytes).hexdigest()}}
            manifest["manifest_sha256"] = sha256(canonical_json(manifest)).hexdigest()
            manifest_path.write_bytes(canonical_json(manifest))
            pointer_path = Path(root) / "current.json"
            pointer = json.loads(pointer_path.read_text())
            pointer["manifest_sha256"] = manifest["manifest_sha256"]
            pointer_path.write_bytes(canonical_json(pointer))
            with self.assertRaises(PublishError):
                publish_snapshot(root, projection(), schema_hash=HASH, policy_hash=HASH, revision="r2", epoch=1, gate=passing_gate(), expected_current_id=first["snapshot_id"])

    def test_emergency_removal_is_stable_for_all_collections_and_revalidates_references(self):
        with tempfile.TemporaryDirectory() as root:
            initial = projection(("rec-one", "rec-two"), evidence_ids=("evi-one", "evi-two"), source_ids=("src-one", "src-two"))
            initial["records"][1]["claims"][0].update({"evidence_id": "evi-two", "source_id": "src-two"})
            initial["records"][1].update({"evidence_ids": ["evi-two"], "source_ids": ["src-two"]})
            first = publish_snapshot(root, initial, schema_hash=HASH, policy_hash=HASH, revision="r1", epoch=0, gate=passing_gate(), expected_current_id=None)
            reordered = copy.deepcopy(initial)
            reordered["records"].reverse()
            with self.assertRaises(PublishError):
                publish_snapshot(root, reordered, schema_hash=HASH, policy_hash=HASH, revision="r2", epoch=1, gate=passing_gate(), expected_current_id=first["snapshot_id"], emergency=True)
            removed = {key: value[:1] for key, value in initial.items()}
            second = publish_snapshot(root, removed, schema_hash=HASH, policy_hash=HASH, revision="r2", epoch=1, gate=passing_gate(), expected_current_id=first["snapshot_id"], emergency=True)
            self.assertNotEqual(second["snapshot_id"], first["snapshot_id"])
            invalid = projection()
            invalid["records"][0]["evidence_ids"] = ["evi-missing"]
            with self.assertRaises(PublishError):
                publish_snapshot(root, invalid, schema_hash=HASH, policy_hash=HASH, revision="r3", epoch=2, gate=passing_gate(), expected_current_id=second["snapshot_id"], emergency=True)
            added = copy.deepcopy(removed)
            added["records"].append(copy.deepcopy(initial["records"][1]))
            with self.assertRaises(PublishError):
                publish_snapshot(root, added, schema_hash=HASH, policy_hash=HASH, revision="r4", epoch=3, gate=passing_gate(), expected_current_id=second["snapshot_id"], emergency=True)
            mutated = copy.deepcopy(removed)
            mutated["records"][0]["claims"][0]["value"] = 99
            with self.assertRaises(PublishError):
                publish_snapshot(root, mutated, schema_hash=HASH, policy_hash=HASH, revision="r5", epoch=4, gate=passing_gate(), expected_current_id=second["snapshot_id"], emergency=True)
            mutated_evidence = copy.deepcopy(removed)
            mutated_evidence["evidence"][0]["checksum"] = "f" * 64
            with self.assertRaises(PublishError):
                publish_snapshot(root, mutated_evidence, schema_hash=HASH, policy_hash=HASH, revision="r6", epoch=5, gate=passing_gate(), expected_current_id=second["snapshot_id"], emergency=True)
            mutated_source = copy.deepcopy(removed)
            mutated_source["sources"][0]["url"] = "https://changed-source.example.test"
            with self.assertRaises(PublishError):
                publish_snapshot(root, mutated_source, schema_hash=HASH, policy_hash=HASH, revision="r7", epoch=6, gate=passing_gate(), expected_current_id=second["snapshot_id"], emergency=True)

    def test_lock_requires_the_approved_complete_file_hash(self):
        self.assertTrue(_lock_is_verified())
        with patch.object(Path, "read_bytes", return_value=b"requirements.lock tampered"):
            self.assertFalse(_lock_is_verified())
    def test_pointer_readback_rejects_a_replaced_unexpected_pointer(self):
        with tempfile.TemporaryDirectory() as root:
            original_write = publish_module._atomic_write

            def corrupt_pointer(path, payload):
                original_write(path, payload)
                path.write_text("{}")

            with patch.object(publish_module, "_atomic_write", side_effect=corrupt_pointer):
                with self.assertRaises(PublicationIndeterminateError):
                    publish_snapshot(root, projection(), schema_hash=HASH, policy_hash=HASH, revision="r1", epoch=0, gate=passing_gate(), expected_current_id=None)
