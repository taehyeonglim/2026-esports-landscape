"""Required-claim verification and append-only re-verification planning.

This module deliberately evaluates each required claim.  It never promotes a
record because some other candidate evidence happened to be strong.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from hashlib import sha256
import json
import sqlite3
from typing import Iterable, Mapping
from uuid import NAMESPACE_URL, uuid4, uuid5

from .db import authorize_review_transition, clear_review_transition_authorization, immediate_transaction
from .lineage import EvidenceLineage, EvidenceSetAssessment, assess_evidence_set
from .models import CandidateStatus, PublicationStatus
from .policy import PublisherPolicy, PolicySnapshot, canonical_policy_hash
from .registry import SourceRegistry

class VerificationStatus(str, Enum):
    """Claim and record visibility states, ordered from least to most publishable."""

    REVERIFICATION_PENDING = CandidateStatus.REVERIFICATION_PENDING.value
    PRIVATE = CandidateStatus.PRIVATE.value
    PROVISIONAL = PublicationStatus.PROVISIONAL.value
    VERIFIED = PublicationStatus.VERIFIED.value


class VerificationReasonCode(str, Enum):
    """Auditable decision reasons; no status is inferred as a fallback."""

    OFFICIAL_DIRECT_CLAIM = "official_direct_claim"
    INDEPENDENT_TRUSTED_DIRECT_SOURCES = "independent_trusted_direct_sources"
    MISSING_CLAIM_EVIDENCE = "missing_claim_evidence"
    AUTHORITY_SCOPE_MISMATCH = "authority_scope_mismatch"
    DIRECT_EVIDENCE_REQUIRED = "direct_evidence_required"
    TRUSTED_INDEPENDENT_SOURCES_REQUIRED = "trusted_independent_sources_required"
    REVERIFICATION_INPUT_CHANGED = "reverification_input_changed"


@dataclass(frozen=True, slots=True)
class RequiredClaim:
    """A claim which must be assessed before its record can be published."""

    claim_id: str
    authority_scope: str


@dataclass(frozen=True, slots=True)
class ClaimEvidence:
    """Evidence assigned to exactly one claim and carrying its verification facts."""

    claim_id: str
    evidence_id: str
    publisher_id: str | None
    origin_publisher_id: str | None
    url: str
    authority_scopes: frozenset[str]
    is_direct: bool
    is_official: bool
    is_trusted: bool

    def lineage(self) -> EvidenceLineage:
        """Return the lineage-only representation used for independence checks."""
        return EvidenceLineage(
            evidence_id=self.evidence_id,
            publisher_id=self.publisher_id,
            origin_publisher_id=self.origin_publisher_id,
            url=self.url,
        )


@dataclass(frozen=True, slots=True)
class ClaimDecision:
    """An immutable, append-only decision payload for one required claim."""

    claim_id: str
    status: VerificationStatus
    reason_code: VerificationReasonCode
    evidence_set_hash: str
    lineage_assessment: EvidenceSetAssessment
    policy_hash: str
    publisher_hash: str
    registry_hash: str

    def payload(self) -> dict[str, object]:
        """Return a JSON-safe event payload suitable for append-only storage."""
        return {
            "claim_id": self.claim_id,
            "status": self.status.value,
            "reason_code": self.reason_code.value,
            "evidence_set_hash": self.evidence_set_hash,
            "lineage_assessment": _lineage_payload(self.lineage_assessment),
            "policy_hash": self.policy_hash,
            "publisher_hash": self.publisher_hash,
            "registry_hash": self.registry_hash,
        }

    @property
    def decision_hash(self) -> str:
        """Hash this immutable payload for an append-only event chain."""
        return _hash_payload(self.payload())


@dataclass(frozen=True, slots=True)
class RecordDecision:
    """The lowest required-claim status determines the record's status."""

    status: VerificationStatus
    claim_decisions: tuple[ClaimDecision, ...]


@dataclass(frozen=True, slots=True)
class ReverificationAction:
    """An append-only instruction; it never mutates an earlier decision."""

    claim_id: str
    status: VerificationStatus
    reason_code: VerificationReasonCode
    prior_decision_hash: str
    previous_policy_hash: str
    current_policy_hash: str
    previous_publisher_hash: str
    current_publisher_hash: str
    previous_registry_hash: str
    current_registry_hash: str

    def payload(self) -> dict[str, str]:
        return {
            "claim_id": self.claim_id,
            "status": self.status.value,
            "reason_code": self.reason_code.value,
            "prior_decision_hash": self.prior_decision_hash,
            "previous_policy_hash": self.previous_policy_hash,
            "current_policy_hash": self.current_policy_hash,
            "previous_publisher_hash": self.previous_publisher_hash,
            "current_publisher_hash": self.current_publisher_hash,
            "previous_registry_hash": self.previous_registry_hash,
            "current_registry_hash": self.current_registry_hash,
        }


@dataclass(frozen=True, slots=True)
class ReverificationPlan:
    """Only claims whose controlling inputs changed receive pending actions."""

    actions: tuple[ReverificationAction, ...]


def verify_required_claims(
    required_claims: Iterable[RequiredClaim],
    evidence: Iterable[ClaimEvidence],
    policy: PolicySnapshot | PublisherPolicy,
    *,
    registry_hash: str,
) -> RecordDecision:
    """Evaluate every required claim under directness, scope, and lineage rules.

    A direct official claim is verified.  Otherwise, provisional requires two
    direct, scope-authorized, trusted observations with at least one strictly
    independent lineage pair.  All other outcomes remain private.
    """
    requirements = tuple(required_claims)
    observations = tuple(evidence)
    publisher_policy, policy_hash = _policy_inputs(policy)
    publisher_hash = canonical_policy_hash(publisher_policy)
    _validate_inputs(requirements, observations, registry_hash)
    decisions = tuple(
        _verify_claim(requirement, tuple(item for item in observations if item.claim_id == requirement.claim_id),
                      publisher_policy, policy_hash, publisher_hash, registry_hash)
        for requirement in requirements
    )
    return RecordDecision(status=derive_record_status(decisions, requirements), claim_decisions=decisions)


def derive_record_status(
    decisions: Iterable[ClaimDecision], required_claims: Iterable[RequiredClaim]) -> VerificationStatus:
    """Return the strict minimum status, rejecting absent or duplicate decisions."""
    required_ids = [claim.claim_id for claim in required_claims]
    decisions_tuple = tuple(decisions)
    decision_ids = [decision.claim_id for decision in decisions_tuple]
    if not required_ids or len(required_ids) != len(set(required_ids)):
        raise ValueError("required claims must be non-empty and have unique ids")
    if len(decision_ids) != len(set(decision_ids)):
        raise ValueError("every required claim must have exactly one decision")
    decisions_by_id = dict(zip(decision_ids, decisions_tuple, strict=True))
    if len(decisions_by_id) != len(required_ids) or set(decisions_by_id) != set(required_ids):
        raise ValueError("every required claim must have exactly one decision")
    return min((decision.status for decision in decisions_by_id.values()), key=_status_rank)


def plan_reverification(
    decisions: Iterable[ClaimDecision],
    *,
    policy_hash: str,
    publisher_hash: str,
    registry_hash: str,
) -> ReverificationPlan:
    """Produce pending append-only actions for claims affected by input-hash changes."""
    _validate_hashes(policy_hash, publisher_hash, registry_hash)
    actions = tuple(
        ReverificationAction(
            claim_id=decision.claim_id,
            status=VerificationStatus.REVERIFICATION_PENDING,
            reason_code=VerificationReasonCode.REVERIFICATION_INPUT_CHANGED,
            prior_decision_hash=decision.decision_hash,
            previous_policy_hash=decision.policy_hash,
            current_policy_hash=policy_hash,
            previous_publisher_hash=decision.publisher_hash,
            current_publisher_hash=publisher_hash,
            previous_registry_hash=decision.registry_hash,
            current_registry_hash=registry_hash,
        )
        for decision in decisions
        if (decision.policy_hash, decision.publisher_hash, decision.registry_hash)
        != (policy_hash, publisher_hash, registry_hash)
    )
    return ReverificationPlan(actions=actions)


def _verify_claim(
    requirement: RequiredClaim,
    observations: tuple[ClaimEvidence, ...],
    publisher_policy: PublisherPolicy,
    policy_hash: str,
    publisher_hash: str,
    registry_hash: str,
) -> ClaimDecision:
    lineage = assess_evidence_set((item.lineage() for item in observations), publisher_policy)
    common = dict(
        claim_id=requirement.claim_id,
        evidence_set_hash=lineage.evidence_set_hash,
        lineage_assessment=lineage,
        policy_hash=policy_hash,
        publisher_hash=publisher_hash,
        registry_hash=registry_hash,
    )
    if not observations:
        return ClaimDecision(status=VerificationStatus.PRIVATE,
                             reason_code=VerificationReasonCode.MISSING_CLAIM_EVIDENCE, **common)
    scoped = tuple(item for item in observations if requirement.authority_scope in item.authority_scopes)
    if not scoped:
        return ClaimDecision(status=VerificationStatus.PRIVATE,
                             reason_code=VerificationReasonCode.AUTHORITY_SCOPE_MISMATCH, **common)
    official_direct = tuple(
        item for item in scoped if item.is_official is True and item.is_direct is True
    )
    if official_direct:
        return ClaimDecision(status=VerificationStatus.VERIFIED,
                             reason_code=VerificationReasonCode.OFFICIAL_DIRECT_CLAIM, **common)
    direct = tuple(item for item in scoped if item.is_direct is True)
    if not direct:
        return ClaimDecision(status=VerificationStatus.PRIVATE,
                             reason_code=VerificationReasonCode.DIRECT_EVIDENCE_REQUIRED, **common)
    trusted = tuple(item for item in direct if item.is_trusted is True)
    if len(trusted) < 2:
        return ClaimDecision(status=VerificationStatus.PRIVATE,
                             reason_code=VerificationReasonCode.TRUSTED_INDEPENDENT_SOURCES_REQUIRED, **common)
    trusted_lineage = assess_evidence_set((item.lineage() for item in trusted), publisher_policy)
    if not trusted_lineage.has_independent_pair:
        return ClaimDecision(status=VerificationStatus.PRIVATE,
                             reason_code=VerificationReasonCode.TRUSTED_INDEPENDENT_SOURCES_REQUIRED, **common)
    return ClaimDecision(status=VerificationStatus.PROVISIONAL,
                         reason_code=VerificationReasonCode.INDEPENDENT_TRUSTED_DIRECT_SOURCES, **common)


def _policy_inputs(policy: PolicySnapshot | PublisherPolicy) -> tuple[PublisherPolicy, str]:
    if isinstance(policy, PolicySnapshot):
        return policy.publishers, canonical_policy_hash(policy)
    if isinstance(policy, PublisherPolicy):
        return policy, canonical_policy_hash(policy)
    raise TypeError("policy must be PolicySnapshot or PublisherPolicy")


def _validate_inputs(
    requirements: tuple[RequiredClaim, ...], evidence: tuple[ClaimEvidence, ...], registry_hash: str
) -> None:
    if not requirements or len({item.claim_id for item in requirements}) != len(requirements):
        raise ValueError("required claims must be non-empty and have unique ids")
    for item in requirements:
        if not item.claim_id.strip() or not item.authority_scope.strip():
            raise ValueError("claim ids and authority scopes must be non-empty")
    _validate_hashes(registry_hash)
    evidence_ids: set[str] = set()
    claim_ids = {item.claim_id for item in requirements}
    for item in evidence:
        if not isinstance(item, ClaimEvidence):
            raise TypeError("evidence entries must be ClaimEvidence instances")
        if item.claim_id not in claim_ids:
            raise ValueError("evidence must belong to a required claim")
        if item.evidence_id in evidence_ids:
            raise ValueError("evidence ids must be unique")
        evidence_ids.add(item.evidence_id)
        if not item.authority_scopes or any(not scope.strip() for scope in item.authority_scopes):
            raise ValueError("evidence authority scopes must be non-empty")


def _validate_hashes(*hashes: str) -> None:
    if any(not isinstance(value, str) or not value.strip() for value in hashes):
        raise ValueError("policy, publisher, and registry hashes must be non-empty")


def _status_rank(status: VerificationStatus) -> int:
    return {
        VerificationStatus.REVERIFICATION_PENDING: 0,
        VerificationStatus.PRIVATE: 1,
        VerificationStatus.PROVISIONAL: 2,
        VerificationStatus.VERIFIED: 3,
    }[status]


def _hash_payload(payload: Mapping[str, object]) -> str:
    encoded = json.dumps(payload, allow_nan=False, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return sha256(encoded.encode("utf-8")).hexdigest()


def _lineage_payload(assessment: EvidenceSetAssessment) -> dict[str, object]:
    return {
        "evidence_set_hash": assessment.evidence_set_hash,
        "assessments": [
            {
                **asdict(item),
                "control": item.control.value,
                "origin": item.origin.value,
                "reason_code": item.reason_code.value,
            }
            for item in assessment.assessments
        ],
    }
@dataclass(frozen=True, slots=True)
class RequiredPredicate:
    """DB-bound predicate/scope contract; evidence attributes are never caller input."""

    predicate: str
    authority_scope: str


def record_evidence_review(connection: sqlite3.Connection, *, fact_id: str, authority_scope: str,
                           direct: bool, reviewer_receipt_digest: str, actor_id: str, command_id: str,
                           expected_version: int, allowed_actors: Iterable[str], registry: SourceRegistry,
                           policy: PolicySnapshot) -> str:
    """Apply one authorized, versioned evidence-review command or replay it exactly."""
    allowed = frozenset(allowed_actors)
    if (not isinstance(registry, SourceRegistry) or not isinstance(policy, PolicySnapshot)
            or policy.registry != registry or policy.claims is None or type(direct) is not bool
            or not _is_digest(reviewer_receipt_digest) or not isinstance(actor_id, str)
            or not actor_id or actor_id not in allowed or not isinstance(command_id, str)
            or not command_id or type(expected_version) is not int or expected_version < 0):
        raise ValueError("evidence review command is invalid or unauthorized")
    registry_hash, policy_hash = canonical_policy_hash(registry), canonical_policy_hash(policy)
    command_payload = {
        "actor_id": actor_id,
        "authority_scope": authority_scope,
        "command_id": command_id,
        "direct": direct,
        "expected_version": expected_version,
        "fact_id": fact_id,
        "policy_hash": policy_hash,
        "registry_hash": registry_hash,
        "reviewer_receipt_digest": reviewer_receipt_digest,
    }
    command_json = json.dumps(command_payload, sort_keys=True, separators=(",", ":"))
    with immediate_transaction(connection):
        previous = connection.execute(
            """SELECT command_json, receipt_json, resulting_evidence_review_id, resulting_version,
                      fact_id, authority_scope, direct, actor_id, policy_hash, registry_hash, expected_version
               FROM evidence_review_command_receipt WHERE command_id = ?""",
            (command_id,),
        ).fetchone()
        if previous is not None:
            expected_receipt = json.dumps({
                "command_id": command_id,
                "resulting_evidence_review_id": str(previous[2]),
                "resulting_version": previous[3],
            }, sort_keys=True, separators=(",", ":"))
            persisted_command = (
                previous[0] == command_json
                and previous[1] == expected_receipt
                and (str(previous[4]), str(previous[5]), int(previous[6]), str(previous[7]),
                     str(previous[8]), str(previous[9]), int(previous[10]))
                == (fact_id, authority_scope, int(direct), actor_id, policy_hash, registry_hash, expected_version)
            )
            review = connection.execute(
                """SELECT fact_id, authority_scope, direct, reviewer_receipt_digest, policy_hash, status
                   FROM evidence_review WHERE evidence_review_id = ?""",
                (previous[2],),
            ).fetchone()
            if (not persisted_command or review is None
                    or (str(review[0]), str(review[1]), int(review[2]), str(review[4]), str(review[5]))
                    != (fact_id, authority_scope, int(direct), policy_hash, "active")
                    or str(review[3]) != reviewer_receipt_digest):
                raise ValueError("evidence review replay receipt is corrupt or semantically inconsistent")
            aggregate = connection.execute(
                "SELECT version FROM evidence_review_aggregate WHERE candidate_id = (SELECT candidate_id FROM candidate_fact WHERE fact_id = ?)",
                (fact_id,),
            ).fetchone()
            if aggregate is None or int(aggregate[0]) < int(previous[3]):
                raise ValueError("evidence review replay linkage is corrupt")
            return str(previous[2])
        row = connection.execute(
            """SELECT f.candidate_id, s.registry_source_id, s.registry_hash, s.publisher_id,
                      s.control_cluster, s.origin_cluster, s.access_basis, s.authority_scopes_json,
                      s.url_scheme, s.url_host, s.url_port
               FROM candidate_fact f JOIN source_revision r ON r.revision_id = f.revision_id
               JOIN source s ON s.source_id = r.source_id WHERE f.fact_id = ?""", (fact_id,)
        ).fetchone()
        if (row is None or row[2] != registry_hash
                or not _persisted_source_matches_registry(
                    registry, source_id=row[1], publisher_id=row[3], control_cluster=row[4],
                    origin_cluster=row[5], access_basis=row[6], authority_scopes_json=row[7],
                    url_scheme=row[8], url_host=row[9], url_port=row[10],
                )
                or authority_scope not in json.loads(row[7])):
            raise ValueError("fact source provenance is unavailable")
        candidate_id = str(row[0])
        connection.execute(
            "INSERT OR IGNORE INTO evidence_review_aggregate(candidate_id) VALUES (?)", (candidate_id,)
        )
        version = connection.execute(
            "SELECT version FROM evidence_review_aggregate WHERE candidate_id = ?", (candidate_id,)
        ).fetchone()[0]
        if version != expected_version:
            raise ValueError("evidence review command has a stale expected version")
        old = connection.execute(
            "SELECT evidence_review_id FROM evidence_review WHERE fact_id = ? AND authority_scope = ? AND status = 'active'",
            (fact_id, authority_scope),
        ).fetchone()
        review_id = str(uuid4())
        try:
            if old:
                authorize_review_transition(connection, candidate_id, str(old[0]), version, "superseded")
                connection.execute(
                    "UPDATE evidence_review SET status = 'superseded' WHERE evidence_review_id = ?", (old[0],)
                )
            authorize_review_transition(connection, candidate_id, review_id, version, "active")
            connection.execute(
                """INSERT INTO evidence_review(evidence_review_id, fact_id, authority_scope, direct,
                   reviewer_receipt_digest, policy_hash, status, supersedes_id)
                   VALUES (?, ?, ?, ?, ?, ?, 'active', ?)""",
                (review_id, fact_id, authority_scope, int(direct), reviewer_receipt_digest, policy_hash,
                 old[0] if old else None),
            )
        finally:
            clear_review_transition_authorization(connection)
        resulting_version = version + 1
        connection.execute(
            """UPDATE evidence_review_aggregate SET version = ?, updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
               WHERE candidate_id = ? AND version = ?""",
            (resulting_version, candidate_id, version),
        )
        receipt_json = json.dumps({
            "command_id": command_id,
            "resulting_evidence_review_id": review_id,
            "resulting_version": resulting_version,
        }, sort_keys=True, separators=(",", ":"))
        connection.execute(
            """INSERT INTO evidence_review_command_receipt(
                   command_id, fact_id, authority_scope, direct, actor_id, policy_hash, registry_hash,
                   expected_version, resulting_version, resulting_evidence_review_id, command_json, receipt_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (command_id, fact_id, authority_scope, int(direct), actor_id, policy_hash, registry_hash,
             expected_version, resulting_version, review_id, command_json, receipt_json),
        )
    return review_id


def verify_candidate_from_db(connection: sqlite3.Connection, *, candidate_id: str,
                             registry: SourceRegistry, policy: PolicySnapshot) -> RecordDecision:
    """Verify and publish from persisted provenance and policy-owned requirements only.

    ``verify_required_claims`` is a pure unit helper and MUST NOT be used by
    CLI or DB publication paths.
    """
    if (not isinstance(registry, SourceRegistry) or not isinstance(policy, PolicySnapshot)
            or policy.registry != registry or policy.claims is None):
        raise ValueError("DB verification contract is invalid")
    policy_hash = canonical_policy_hash(policy)
    publisher_hash, registry_hash = canonical_policy_hash(policy.publishers), canonical_policy_hash(registry)
    with immediate_transaction(connection):
        primaries = connection.execute(
            """SELECT cs.subject_id, s.kind FROM candidate_subject cs JOIN subject s ON s.subject_id = cs.subject_id
               WHERE cs.candidate_id = ? AND cs.relation = 'primary' AND cs.active = 1""",
            (candidate_id,),
        ).fetchall()
        pending_identity = connection.execute(
            "SELECT 1 FROM review_identity WHERE candidate_id = ? AND status = 'active'", (candidate_id,)
        ).fetchone()
        identity_proven = (
            len(primaries) == 1
            and _has_exact_identity_receipt(
                connection, candidate_id, str(primaries[0][0])
            )
        )
        if len(primaries) != 1 or pending_identity or not identity_proven:
            prior_active = _has_active_db_publication(connection, candidate_id)
            _retract_active_publications_for_reverification(connection, candidate_id)
            predicates = (
                tuple(policy.claims.requirements.get(primaries[0][1], {}).keys())
                if len(primaries) == 1 else ()
            )
            return (
                _db_reverification_pending(predicates, policy_hash, publisher_hash, registry_hash)
                if prior_active
                else _db_private(predicates, policy_hash, publisher_hash, registry_hash)
            )
        required = _derive_required_predicates(connection, candidate_id, primaries[0][1], policy.claims)
        if required is None:
            prior_active = _has_active_db_publication(connection, candidate_id)
            _retract_active_publications_for_reverification(connection, candidate_id)
            predicates = tuple(policy.claims.requirements[primaries[0][1]].keys())
            return (
                _db_reverification_pending(predicates, policy_hash, publisher_hash, registry_hash)
                if prior_active
                else _db_private(predicates, policy_hash, publisher_hash, registry_hash)
            )
        materializations = []
        decisions = []
        for required_item in required:
            rows = connection.execute(
                """SELECT f.fact_id, f.revision_id, f.value_json, f.locator_digest, f.excerpt_digest,
                          r.content_digest, s.registry_hash, s.publisher_id, s.control_cluster,
                          s.origin_cluster, s.access_basis, s.authority_scopes_json, s.url_scheme,
                          s.url_host, er.evidence_review_id, er.direct, er.reviewer_receipt_digest,
                          er.policy_hash, s.registry_source_id, s.url_port
                   FROM candidate_fact f JOIN source_revision r ON r.revision_id = f.revision_id
                   JOIN source s ON s.source_id = r.source_id
                   LEFT JOIN evidence_review er ON er.fact_id = f.fact_id AND er.authority_scope = ?
                     AND er.status = 'active'
                   WHERE f.candidate_id = ? AND f.predicate = ? ORDER BY f.fact_id""",
                (required_item.authority_scope, candidate_id, required_item.predicate),
            ).fetchall()
            prior_publishable = _has_prior_db_decision(
                connection, candidate_id, required_item.predicate, primaries[0][0]
            )
            decision, input_hash = _db_decide(
                required_item, rows, policy, policy_hash, publisher_hash, registry_hash,
                derived_requirements=required, prior_publishable=prior_publishable,
            )
            decisions.append(decision)
            materializations.append((required_item, rows, decision, input_hash))
        result = RecordDecision(
            derive_record_status(decisions, (RequiredClaim(item.predicate, item.authority_scope) for item in required)),
            tuple(decisions),
        )
        if result.status in {VerificationStatus.VERIFIED, VerificationStatus.PROVISIONAL}:
            for item, rows, decision, input_hash in materializations:
                _materialize_db_decision(connection, candidate_id, primaries[0][0], item, rows, decision, input_hash, policy_hash)
            _reactivate_exact_publications(connection, candidate_id)
        elif _has_active_db_publication(connection, candidate_id):
            _retract_active_publications_for_reverification(connection, candidate_id)
        return result


def _has_exact_identity_receipt(
    connection: sqlite3.Connection, candidate_id: str, subject_id: str
) -> bool:
    """Require one immutable receipt whose command, review, subject, and authority all agree."""
    rows = connection.execute(
        """SELECT ilr.review_identity_id, ilr.actor_id, ilr.command_id, ilr.resulting_version,
                  ilr.authority_identity_digest, ri.status, s.provenance_digest,
                  rcr.command_json, rcr.resulting_version
           FROM identity_link_receipt ilr
           JOIN review_identity ri ON ri.review_identity_id = ilr.review_identity_id
           JOIN subject s ON s.subject_id = ilr.subject_id
           JOIN review_command_receipt rcr ON rcr.command_id = ilr.command_id
           WHERE ilr.candidate_id = ?
             AND ilr.subject_id = ?
             AND ilr.attestation_type = 'human_review'""",
        (candidate_id, subject_id),
    ).fetchall()
    if len(rows) != 1:
        return False
    row = rows[0]
    try:
        command = json.loads(row[7])
    except (TypeError, json.JSONDecodeError):
        return False
    return (
        row[5] == "resolved"
        and row[4] == row[6]
        and int(row[3]) == int(row[8])
        and command == {
            "action": "resolve_primary",
            "actor_id": row[1],
            "command_id": row[2],
            "expected_version": int(row[3]) - 1,
            "resolved_subject_id": subject_id,
            "target_id": row[0],
        }
    )

def _db_private(predicates, policy_hash, publisher_hash, registry_hash):
    empty = assess_evidence_set((), PublisherPolicy({}))
    return RecordDecision(VerificationStatus.PRIVATE, tuple(
        ClaimDecision(predicate, VerificationStatus.PRIVATE, VerificationReasonCode.MISSING_CLAIM_EVIDENCE,
                      _hash_payload({"predicate": predicate}), empty, policy_hash, publisher_hash, registry_hash)
        for predicate in predicates
    ))


def _db_reverification_pending(predicates, policy_hash, publisher_hash, registry_hash):
    empty = assess_evidence_set((), PublisherPolicy({}))
    return RecordDecision(VerificationStatus.REVERIFICATION_PENDING, tuple(
        ClaimDecision(
            predicate,
            VerificationStatus.REVERIFICATION_PENDING,
            VerificationReasonCode.REVERIFICATION_INPUT_CHANGED,
            _hash_payload({"predicate": predicate, "state": "reverification_pending"}),
            empty,
            policy_hash,
            publisher_hash,
            registry_hash,
        )
        for predicate in predicates
    ))

def _derive_required_predicates(connection, candidate_id, subject_kind, claims_policy):
    """Derive each requirement from exactly one active reviewed, suffix-authorized scope."""
    requirements = claims_policy.requirements.get(subject_kind)
    if requirements is None:
        return None
    derived = []
    for predicate, suffixes in requirements.items():
        scopes = {
            row[0] for row in connection.execute(
                """SELECT DISTINCT er.authority_scope FROM candidate_fact f
                   JOIN source_revision r ON r.revision_id = f.revision_id
                   JOIN source s ON s.source_id = r.source_id
                   JOIN evidence_review er ON er.fact_id = f.fact_id AND er.status = 'active'
                   WHERE f.candidate_id = ? AND f.predicate = ?
                     AND EXISTS (
                         SELECT 1 FROM json_each(s.authority_scopes_json)
                         WHERE value = er.authority_scope
                     )""",
                (candidate_id, predicate),
            )
        }
        matching_scopes = {
            scope for scope in scopes
            if any(scope.endswith(f":{suffix}") for suffix in suffixes)
        }
        if len(scopes) != 1 or len(matching_scopes) != 1:
            return None
        derived.append(RequiredPredicate(predicate, matching_scopes.pop()))
    return tuple(derived)


def _db_decide(item, rows, policy, policy_hash, publisher_hash, registry_hash, *, derived_requirements, prior_publishable):
    payload = [{
        "predicate": item.predicate,
        "scope": item.authority_scope,
        "value": json.loads(row[2]),
        "fact_id": row[0],
        "revision_id": row[1],
        "content_digest": row[5],
        "publisher": row[7],
        "control": row[8],
        "origin": row[9],
        "access_basis": row[10],
        "source_scopes": json.loads(row[11]),
        "url_scheme": row[12],
        "url_host": row[13],
        "review_id": row[14],
        "direct_receipt": row[16],
        "direct": row[15],
        "source_registry_hash": row[6],
        "review_policy_hash": row[17],
    } for row in rows]
    input_hash = _hash_payload({
        "derived_requirements": [
            {"predicate": requirement.predicate, "authority_scope": requirement.authority_scope}
            for requirement in derived_requirements
        ],
        "facts": payload,
        "policy_hash": policy_hash,
        "publisher_hash": publisher_hash,
        "registry_hash": registry_hash,
    })
    values = {row[2] for row in rows}
    valid = [
        row for row in rows
        if row[6] == registry_hash
        and row[17] == policy_hash
        and row[15] == 1
        and item.authority_scope in json.loads(row[11])
        and _persisted_source_matches_registry(
            policy.registry, source_id=row[18], publisher_id=row[7], control_cluster=row[8],
            origin_cluster=row[9], access_basis=row[10], authority_scopes_json=row[11],
            url_scheme=row[12], url_host=row[13], url_port=row[19],
        )
        and row[7] in policy.publishers.publishers
        and (
            policy.publishers.publishers[row[7]].control_cluster,
            policy.publishers.publishers[row[7]].origin_cluster,
        ) == (row[8], row[9])
    ]
    lineage = assess_evidence_set(
        (EvidenceLineage(row[0], row[7], row[7], f"{row[12]}://{row[13]}") for row in valid),
        policy.publishers,
    )
    common = dict(claim_id=item.predicate, evidence_set_hash=input_hash, lineage_assessment=lineage,
                  policy_hash=policy_hash, publisher_hash=publisher_hash, registry_hash=registry_hash)
    if not rows:
        return ClaimDecision(status=VerificationStatus.PRIVATE, reason_code=VerificationReasonCode.MISSING_CLAIM_EVIDENCE, **common), input_hash
    if len(values) != 1:
        return ClaimDecision(status=VerificationStatus.PRIVATE, reason_code=VerificationReasonCode.MISSING_CLAIM_EVIDENCE, **common), input_hash
    hash_drift = any(
        row[6] != registry_hash
        or (row[14] is not None and row[17] != policy_hash)
        or not _persisted_source_matches_registry(
            policy.registry, source_id=row[18], publisher_id=row[7], control_cluster=row[8],
            origin_cluster=row[9], access_basis=row[10], authority_scopes_json=row[11],
            url_scheme=row[12], url_host=row[13], url_port=row[19],
        )
        for row in rows
    )
    if hash_drift:
        status = VerificationStatus.REVERIFICATION_PENDING if prior_publishable else VerificationStatus.PRIVATE
        return ClaimDecision(
            status=status,
            reason_code=VerificationReasonCode.REVERIFICATION_INPUT_CHANGED,
            **common,
        ), input_hash
    if any(row[10] in {"official_public_website", "official_open_data_api"} for row in valid):
        return ClaimDecision(status=VerificationStatus.VERIFIED, reason_code=VerificationReasonCode.OFFICIAL_DIRECT_CLAIM, **common), input_hash
    if lineage.has_independent_pair:
        return ClaimDecision(status=VerificationStatus.PROVISIONAL, reason_code=VerificationReasonCode.INDEPENDENT_TRUSTED_DIRECT_SOURCES, **common), input_hash
    return ClaimDecision(status=VerificationStatus.PRIVATE, reason_code=VerificationReasonCode.TRUSTED_INDEPENDENT_SOURCES_REQUIRED, **common), input_hash


def _materialize_db_decision(connection, candidate_id, subject_id, item, rows, decision, input_hash, policy_hash):
    claim_id = str(uuid5(NAMESPACE_URL, f"{candidate_id}:{subject_id}:{item.predicate}:{rows[0][2]}"))
    publication_id = str(uuid5(NAMESPACE_URL, f"publication:{claim_id}:{input_hash}"))
    if connection.execute("SELECT 1 FROM decision WHERE claim_id = ? AND input_hash = ?", (claim_id, input_hash)).fetchone():
        connection.execute("UPDATE publication SET retracted_at = NULL WHERE publication_id = ?", (publication_id,))
        return
    connection.execute("INSERT OR IGNORE INTO claim(claim_id, candidate_id, subject_id, predicate, value_json) VALUES (?, ?, ?, ?, ?)",
                       (claim_id, candidate_id, subject_id, item.predicate, rows[0][2]))
    for row in rows:
        evidence_id = str(uuid5(NAMESPACE_URL, f"{claim_id}:{row[1]}:{row[3]}"))
        connection.execute("INSERT OR IGNORE INTO evidence(evidence_id, claim_id, revision_id, locator_digest, excerpt_digest) VALUES (?, ?, ?, ?, ?)",
                           (evidence_id, claim_id, row[1], row[3], row[4]))
    connection.execute("INSERT INTO decision(decision_id, claim_id, status, policy_version, policy_epoch, rationale, input_hash) VALUES (?, ?, ?, ?, 0, ?, ?)",
                       (str(uuid4()), claim_id, decision.status.value, policy_hash, decision.reason_code.value, input_hash))
    connection.execute("INSERT OR IGNORE INTO publication(publication_id, claim_id, status) VALUES (?, ?, ?)",
                       (publication_id, claim_id, decision.status.value))


def _reactivate_exact_publications(connection, candidate_id):
    connection.execute(
        "UPDATE candidate SET status = ? WHERE candidate_id = ?",
        (CandidateStatus.REVIEW.value, candidate_id),
    )
    connection.execute(
        """UPDATE review_item SET status = 'resolved',
               resolved_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
           WHERE candidate_id = ? AND status = 'active' AND reason = 'reverification_input_changed'""",
        (candidate_id,),
    )


def _has_active_db_publication(connection, candidate_id):
    return connection.execute(
        """SELECT 1 FROM publication p JOIN claim c ON c.claim_id = p.claim_id
           WHERE c.candidate_id = ? AND p.retracted_at IS NULL""",
        (candidate_id,),
    ).fetchone() is not None


def _retract_active_publications_for_reverification(connection, candidate_id):
    connection.execute(
        """UPDATE publication SET retracted_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
           WHERE retracted_at IS NULL
             AND claim_id IN (SELECT claim_id FROM claim WHERE candidate_id = ?)""",
        (candidate_id,),
    )
    connection.execute(
        "UPDATE candidate SET status = ? WHERE candidate_id = ?",
        (CandidateStatus.REVERIFICATION_PENDING.value, candidate_id),
    )
    if connection.execute(
        """SELECT 1 FROM review_item
           WHERE candidate_id = ? AND status = 'active' AND reason = 'reverification_input_changed'""",
        (candidate_id,),
    ).fetchone() is None:
        connection.execute(
            "INSERT INTO review_item(review_item_id, candidate_id, status, reason) VALUES (?, ?, 'active', 'reverification_input_changed')",
            (str(uuid4()), candidate_id),
        )


def _has_prior_db_decision(connection, candidate_id, predicate, subject_id):
    return connection.execute(
        """SELECT 1 FROM decision d JOIN claim c ON c.claim_id = d.claim_id
           WHERE c.candidate_id = ? AND c.subject_id = ? AND c.predicate = ?
             AND d.status IN ('verified', 'provisional')""",
        (candidate_id, subject_id, predicate),
    ).fetchone() is not None


def _persisted_source_matches_registry(
    registry: SourceRegistry, *, source_id, publisher_id, control_cluster, origin_cluster,
    access_basis, authority_scopes_json, url_scheme, url_host, url_port,
) -> bool:
    try:
        source = registry.active_by_id(source_id)
        scopes = frozenset(json.loads(authority_scopes_json))
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return False
    return (
        (url_scheme, url_host, url_port) == source.canonical_origin
        and publisher_id == source.publisher_id
        and control_cluster == source.control_cluster
        and origin_cluster == source.origin_cluster
        and access_basis == source.access_basis
        and scopes == source.authority_scopes
    )


def _is_digest(value):
    return isinstance(value, str) and len(value) == 64 and all(char in "0123456789abcdef" for char in value)
