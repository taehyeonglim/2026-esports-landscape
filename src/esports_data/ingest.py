"""Atomic, PII-gated persistence of extractor output.

Raw fetch bytes and external strings belong only to callers.  This module writes
only sanitized URL components, opaque digests, and already-screened typed facts.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import json
import re
import sqlite3
from uuid import uuid4

from esports_data.db import immediate_transaction
from esports_data.fetch import RegisteredFetchResult, _validate_registered_attestation
from esports_data.models import CandidateStatus, SubjectKind
from esports_data.policy import canonical_policy_hash
from esports_data.registry import SourceRecord, SourceRegistry
from esports_data.pii import scan_text
from esports_data.sanitize import SanitizedUrl
from .extract.json import ExtractResult, ExtractStatus, ExtractedFact, _valid_value


class IngestStatus(str, Enum):
    INSERTED = "inserted"
    DUPLICATE = "duplicate"
    REJECTED = "rejected"


class IngestError(ValueError):
    """Raised before mutation when an ingest request crosses a safety boundary."""


@dataclass(frozen=True, slots=True)
class IngestResult:
    status: IngestStatus
    source_id: str | None = None
    revision_id: str | None = None
    candidate_id: str | None = None
    fact_ids: tuple[str, ...] = ()
    reason_code: str | None = None


_HEX = re.compile(r"[0-9a-f]{64}\Z")
_VERSION = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}\Z")
_TIME = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z")
_TEXT_FACT_PREDICATES = frozenset({
    "program_name", "organization_name", "school_name", "event_name", "location_name",
})
_AUTHORITY_TEXT_UNVERIFIED = "authority_text_unverified"


def ingest_extraction(
    connection: sqlite3.Connection,
    *,
    registry: SourceRegistry,
    registered_fetch: RegisteredFetchResult,
    retrieved_at: str,
    salt: str | bytes,
    proposed_kind: SubjectKind,
    hint_digest: str,
    reason_code: str,
) -> IngestResult:
    """Persist one successful extraction as a candidate-only review aggregate.

    A matching source/content fingerprint returns the existing revision without
    creating a candidate, candidate fact, or review identity.  Ingest never
    creates an authority subject, claim, evidence, or publication.
    """
    source_record, source, registered_fetch = _validated_source(
        registry, registered_fetch
    )
    registry_hash = canonical_policy_hash(registry)
    _validate_request(
        retrieved_at,
        registered_fetch.extractor_version,
        registered_fetch.extraction_fingerprint,
        registered_fetch.extraction,
        proposed_kind,
        hint_digest,
        reason_code,
    )
    extraction = registered_fetch.extraction
    fetch_fingerprint = registered_fetch.extraction_fingerprint
    extractor_version = registered_fetch.extractor_version
    if extraction.status is not ExtractStatus.SUCCESS:
        return IngestResult(IngestStatus.REJECTED)
    if any(fact.predicate in _TEXT_FACT_PREDICATES for fact in extraction.facts):
        return IngestResult(IngestStatus.REJECTED, reason_code=_AUTHORITY_TEXT_UNVERIFIED)

    with immediate_transaction(connection):
        persisted_source_id = _get_or_create_source(
            connection, source_record, registry_hash, source, retrieved_at
        )
        existing = connection.execute(
            "SELECT revision_id FROM source_revision WHERE source_id = ? AND content_digest = ?",
            (persisted_source_id, fetch_fingerprint),
        ).fetchone()
        if existing is not None:
            return IngestResult(IngestStatus.DUPLICATE, persisted_source_id, existing[0])

        revision_id = str(uuid4())
        connection.execute(
            "INSERT INTO source_revision(revision_id, source_id, retrieved_at, content_digest, extractor_version) VALUES (?, ?, ?, ?, ?)",
            (revision_id, persisted_source_id, retrieved_at, fetch_fingerprint, extractor_version),
        )
        candidate_id = str(uuid4())
        connection.execute(
            "INSERT INTO candidate(candidate_id, status, summary) VALUES (?, ?, ?)",
            (candidate_id, CandidateStatus.REVIEW.value, f"extract:{fetch_fingerprint}"),
        )
        connection.execute(
            """INSERT INTO review_identity
               (review_identity_id, candidate_id, relation, proposed_kind, hint_digest, reason_code, status)
               VALUES (?, ?, 'primary', ?, ?, ?, 'active')""",
            (str(uuid4()), candidate_id, proposed_kind.value, hint_digest, reason_code),
        )
        fact_ids: list[str] = []
        for fact in extraction.facts:
            fact_id = str(uuid4())
            connection.execute(
                """INSERT INTO candidate_fact
                   (fact_id, candidate_id, revision_id, predicate, value_json, locator_digest, excerpt_digest)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    fact_id,
                    candidate_id,
                    revision_id,
                    fact.predicate,
                    json.dumps(fact.value, separators=(",", ":"), ensure_ascii=False, sort_keys=True),
                    fact.locator_digest,
                    fact.evidence_digest,
                ),
            )
            fact_ids.append(fact_id)
        return IngestResult(
            IngestStatus.INSERTED,
            persisted_source_id,
            revision_id,
            candidate_id,
            tuple(fact_ids),
        )


def _validated_source(
    registry: object,
    registered_fetch: object,
) -> tuple[SourceRecord, SanitizedUrl, RegisteredFetchResult]:
    try:
        result = _validate_registered_attestation(registry, registered_fetch)
    except (KeyError, ValueError) as error:
        raise IngestError("registered fetch provenance is invalid") from error
    try:
        source_record = registry.active_by_id(result.source_id)
    except KeyError as error:
        raise IngestError("source is not registered") from error
    if (
        result.canonical_origin != source_record.canonical_origin
        or not isinstance(result.url_path_digest, str)
        or not _HEX.fullmatch(result.url_path_digest)
    ):
        raise IngestError("registered fetch provenance does not match its source")
    scheme, host, _ = source_record.canonical_origin
    return source_record, SanitizedUrl(scheme, host, result.url_path_digest), result

def _validate_request(
    retrieved_at: object,
    extractor_version: object,
    fetch_fingerprint: object,
    extraction: object,
    proposed_kind: object,
    hint_digest: object,
    reason_code: object,
) -> None:
    if not isinstance(retrieved_at, str) or not _TIME.fullmatch(retrieved_at):
        raise IngestError("retrieved_at must be an ISO-8601 UTC timestamp")
    if not isinstance(extractor_version, str) or not _VERSION.fullmatch(extractor_version):
        raise IngestError("extractor_version is invalid")
    if not isinstance(fetch_fingerprint, str) or not _HEX.fullmatch(fetch_fingerprint):
        raise IngestError("fetch_fingerprint is invalid")
    if not isinstance(extraction, ExtractResult) or extraction.fingerprint != fetch_fingerprint:
        raise IngestError("fetch fingerprint does not match extractor output")
    if type(proposed_kind) is not SubjectKind:
        raise IngestError("proposed_kind must be a SubjectKind")
    if not isinstance(hint_digest, str) or not _HEX.fullmatch(hint_digest):
        raise IngestError("hint_digest is invalid")
    if reason_code != "authority_key_missing":
        raise IngestError("reason_code is invalid")
    if extraction.status is ExtractStatus.SUCCESS:
        if not extraction.facts:
            raise IngestError("successful extraction must contain facts")
        for fact in extraction.facts:
            _validate_fact(fact)


def _validate_fact(fact: object) -> None:
    if not isinstance(fact, ExtractedFact) or not _HEX.fullmatch(fact.locator_digest) or not _HEX.fullmatch(fact.evidence_digest):
        raise IngestError("fact evidence is not sanitized")
    _validate_no_pii_strings(fact.value)
    if not _valid_value(fact.predicate, fact.value):
        raise IngestError("fact is outside the typed allowlist")


def _validate_no_pii_strings(value: object) -> None:
    if isinstance(value, str):
        if not scan_text(value).is_clean:
            raise IngestError("fact value failed the PII gate")
        return
    if isinstance(value, list):
        for item in value:
            _validate_no_pii_strings(item)
        return
    if isinstance(value, dict):
        for key, item in value.items():
            _validate_no_pii_strings(key)
            _validate_no_pii_strings(item)

def _get_or_create_source(
    connection: sqlite3.Connection,
    source_record: SourceRecord,
    registry_hash: str,
    source: SanitizedUrl,
    retrieved_at: str,
) -> str:
    scopes_json = json.dumps(sorted(source_record.authority_scopes), separators=(",", ":"))
    provenance = (
        source_record.source_id,
        registry_hash,
        source_record.publisher_id,
        source_record.control_cluster,
        source_record.origin_cluster,
        source_record.access_basis,
        scopes_json,
        source.scheme,
        source.host,
        443,
    )
    row = connection.execute(
        """SELECT source_id, registry_source_id, registry_hash, publisher_id,
                  control_cluster, origin_cluster, access_basis, authority_scopes_json,
                  url_scheme, url_host, url_port
           FROM source
           WHERE url_scheme = ? AND url_host = ? AND url_port = ? AND url_path_digest IS ?""",
        (source.scheme, source.host, 443, source.path_digest),
    ).fetchone()
    if row is not None:
        if tuple(row[1:]) != provenance:
            raise IngestError("persisted source provenance drifted")
        return row[0]
    persisted_source_id = str(uuid4())
    connection.execute(
        """INSERT INTO source(
               source_id, registry_source_id, registry_hash, publisher_id,
               control_cluster, origin_cluster, access_basis, authority_scopes_json, source_kind,
               url_scheme, url_host, url_port, url_path_digest, retrieved_at
           ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            persisted_source_id,
            source_record.source_id,
            registry_hash,
            source_record.publisher_id,
            source_record.control_cluster,
            source_record.origin_cluster,
            source_record.access_basis,
            scopes_json,
            "extract",
            source.scheme,
            source.host,
            443,
            source.path_digest,
            retrieved_at,
        ),
    )
    return persisted_source_id
