"""Authority-backed identities for normalized public subjects.

A public subject UUID is issued only from an authority identifier.  In particular,
a display name is never an identity input.
"""

from __future__ import annotations

from contextlib import nullcontext
from dataclasses import dataclass
import re
import sqlite3
from typing import Final
from uuid import UUID, uuid5
from .models import SubjectKind


class IdentityError(ValueError):
    """Raised when an authority or review identity is invalid."""


# These are fixed, per-kind UUIDv5 namespaces.  They are protocol constants, not
# generated at import time, so IDs remain stable across deployments.
AUTHORITY_NAMESPACES: Final[dict[SubjectKind, UUID]] = {
    SubjectKind.SCHOOL: UUID("6e3fa25a-22c6-5e3d-9574-6a4b5a0d6c11"),
    SubjectKind.REGION: UUID("6209bdff-d75a-5ec9-85cb-ec9ab51ce2a1"),
    SubjectKind.ORGANIZATION: UUID("f1c7f2d1-7d6a-5130-b6cc-3df92f0a6e9f"),
    SubjectKind.VENUE: UUID("8d515bd8-57c4-5c6d-8610-152d50e01ae9"),
    SubjectKind.PROGRAM: UUID("85181500-0411-50dc-9db0-1ea655c2c4c5"),
    SubjectKind.UNIVERSITY: UUID("e04ef0d3-a763-58b1-98eb-8fe21f1e19de"),
}

AUTHORITY_NAMESPACE_NAMES: Final[dict[SubjectKind, str]] = {
    SubjectKind.SCHOOL: "school.neis.go.kr",
    SubjectKind.REGION: "region.korea.go.kr",
    SubjectKind.ORGANIZATION: "organization.registry.go.kr",
    SubjectKind.VENUE: "localdata.go.kr",
    SubjectKind.PROGRAM: "event.registry.go.kr",
    SubjectKind.UNIVERSITY: "university.ac.kr",
}

_REVIEW_NAMESPACE: Final = UUID("9ef69bbc-dd8a-5ebb-bc74-91b9eab612eb")
_KEY_PATTERNS: Final[dict[SubjectKind, re.Pattern[str]]] = {
    SubjectKind.SCHOOL: re.compile(r"[A-Z0-9]{10}"),
    SubjectKind.REGION: re.compile(r"\d{2,10}"),
    SubjectKind.ORGANIZATION: re.compile(r"[a-z0-9][a-z0-9._:-]{2,127}"),
    SubjectKind.VENUE: re.compile(r"[A-Z0-9][A-Z0-9._:-]{2,127}"),
    SubjectKind.PROGRAM: re.compile(r"[a-z0-9][a-z0-9._:/-]{2,255}"),
    SubjectKind.UNIVERSITY: re.compile(r"[A-Z0-9]{10}"),
}


@dataclass(frozen=True, slots=True)
class AuthorityIdentity:
    """The validated authority namespace/key pair for one primary subject."""

    kind: SubjectKind
    namespace: str
    key: str

    def __post_init__(self) -> None:
        if not isinstance(self.kind, SubjectKind):
            raise IdentityError("kind must be a SubjectKind")
        if not isinstance(self.namespace, str):
            raise IdentityError("authority namespace must be a string")
        if not isinstance(self.key, str):
            raise IdentityError("authority key must be a string")
        expected_namespace = AUTHORITY_NAMESPACE_NAMES[self.kind]
        if self.namespace != expected_namespace:
            raise IdentityError(
                f"{self.kind.value} must use authority namespace {expected_namespace!r}"
            )
        if not _KEY_PATTERNS[self.kind].fullmatch(self.key):
            raise IdentityError(f"invalid {self.kind.value} authority key")

    @property
    def subject_uuid(self) -> UUID:
        """Return the UUIDv5 derived from the fixed kind namespace and authority key."""

        return uuid5(AUTHORITY_NAMESPACES[self.kind], self.key)


def authority_subject_uuid(kind: SubjectKind | str, namespace: str, key: str) -> UUID:
    """Derive an authority subject UUID after validating its full identity tuple."""

    try:
        subject_kind = kind if isinstance(kind, SubjectKind) else SubjectKind(kind)
    except (TypeError, ValueError) as error:
        raise IdentityError("kind must be a supported subject kind") from error
    return AuthorityIdentity(subject_kind, namespace, key).subject_uuid


def school_authority_key(neis_school_code: str) -> str:
    """Validate and return a canonical ten-character NEIS school code."""

    if not isinstance(neis_school_code, str):
        raise IdentityError("NEIS school code must be a string")
    key = neis_school_code.strip().upper()
    AuthorityIdentity(SubjectKind.SCHOOL, AUTHORITY_NAMESPACE_NAMES[SubjectKind.SCHOOL], key)
    return key


def event_authority_key(organizer_key: str, event_key: str) -> str:
    """Build a canonical event key from two opaque authority-issued components."""

    if not isinstance(organizer_key, str) or not isinstance(event_key, str):
        raise IdentityError("event authority components must be strings")
    organizer = organizer_key.strip().lower()
    event = event_key.strip().lower()
    if not organizer or not event or any("/" in item for item in (organizer, event)):
        raise IdentityError("event authority components must be non-empty opaque keys")
    key = f"{organizer}/{event}"
    AuthorityIdentity(SubjectKind.PROGRAM, AUTHORITY_NAMESPACE_NAMES[SubjectKind.PROGRAM], key)
    return key


def subject_uuid(identity: AuthorityIdentity) -> UUID:
    """Issue a primary UUID only from a validated authority identity."""

    if not isinstance(identity, AuthorityIdentity):
        raise IdentityError("primary subject UUIDs require an AuthorityIdentity")
    return authority_subject_uuid(identity.kind, identity.namespace, identity.key)
@dataclass(frozen=True, slots=True)
class AuthoritySubject:
    """A persisted subject issued from a validated authority identity."""

    subject_id: UUID
    identity: AuthorityIdentity
    provenance_digest: str


def insert_authority_subject(
    connection: sqlite3.Connection,
    identity: AuthorityIdentity,
    *,
    canonical_name: str,
    provenance_digest: str,
    subtype: str | None = None,
    operator_subject_id: str | None = None,
) -> AuthoritySubject:
    """Persist an authority-issued subject after validating its durable identity."""

    if not isinstance(identity, AuthorityIdentity):
        raise IdentityError("subjects require an AuthorityIdentity")
    if not isinstance(canonical_name, str) or not canonical_name.strip():
        raise IdentityError("canonical_name must be a non-empty string")
    if not isinstance(provenance_digest, str) or not re.fullmatch(
        r"[0-9a-f]{64}", provenance_digest
    ):
        raise IdentityError("provenance_digest must be a lowercase SHA-256 hex digest")
    if subtype is not None and not isinstance(subtype, str):
        raise IdentityError("subtype must be a string or None")
    if operator_subject_id is not None and not isinstance(operator_subject_id, str):
        raise IdentityError("operator_subject_id must be a string or None")

    issued_id = subject_uuid(identity)
    transaction = nullcontext(connection) if connection.in_transaction else _immediate(connection)
    with transaction:
        connection.execute(
            """INSERT INTO subject
               (subject_id, kind, authority_namespace, authority_key, provenance_digest,
                canonical_name, subtype, operator_subject_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                str(issued_id),
                identity.kind.value,
                identity.namespace,
                identity.key,
                provenance_digest,
                canonical_name,
                subtype,
                operator_subject_id,
            ),
        )
    return AuthoritySubject(issued_id, identity, provenance_digest)


class _immediate:
    """Small local transaction helper to avoid coupling identity to other adapters."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def __enter__(self) -> sqlite3.Connection:
        self.connection.execute("BEGIN IMMEDIATE")
        return self.connection

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> bool:
        if exc_type is None:
            self.connection.commit()
        else:
            self.connection.rollback()
        return False


@dataclass(frozen=True, slots=True)
class PrimaryReviewIdentity:
    """A non-publishable identity for an authority-less primary review."""

    kind: SubjectKind
    intake_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.kind, SubjectKind):
            raise IdentityError("kind must be a SubjectKind")
        if not isinstance(self.intake_id, str) or not re.fullmatch(
            r"[a-z0-9][a-z0-9._:-]{2,127}", self.intake_id
        ):
            raise IdentityError("intake_id must be an opaque identifier, not a name")

    @property
    def review_uuid(self) -> UUID:
        return uuid5(_REVIEW_NAMESPACE, f"primary-review:{self.kind.value}:{self.intake_id}")


@dataclass(frozen=True, slots=True)
class RelatedProposalIdentity:
    """An optional authority-backed proposal related to a primary review.

    This does not turn the authority-less review into a primary subject.
    """

    primary_review: PrimaryReviewIdentity
    proposed_subject: AuthorityIdentity

    def __post_init__(self) -> None:
        if not isinstance(self.primary_review, PrimaryReviewIdentity):
            raise IdentityError("primary_review must be a PrimaryReviewIdentity")
        if not isinstance(self.proposed_subject, AuthorityIdentity):
            raise IdentityError("proposed_subject must be an AuthorityIdentity")

    @property
    def proposal_uuid(self) -> UUID:
        return uuid5(
            _REVIEW_NAMESPACE,
            f"related-proposal:{self.primary_review.review_uuid}:{self.proposed_subject.subject_uuid}",
        )
