"""Deterministic normalization of v2 classifications and event occurrences."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
import hashlib
import re
from uuid import UUID
from zoneinfo import ZoneInfo

from .models import SubjectKind


class NormalizationError(ValueError):
    """Raised when a v2 value cannot be normalized without guessing."""


class Scope(str, Enum):
    REGIONAL = "regional"
    NATIONWIDE = "nationwide"
    ADJACENT = "adjacent"
    UNKNOWN = "unknown"


KST = ZoneInfo("Asia/Seoul")

_CATEGORY_KINDS = {
    "교육청대회·사업": SubjectKind.PROGRAM,
    "협회사업": SubjectKind.PROGRAM,
    "학교동아리·팀": SubjectKind.SCHOOL,
    "대학학과·전공·동아리": SubjectKind.UNIVERSITY,
    "경기장·인프라": SubjectKind.VENUE,
    "지자체정책·조례": SubjectKind.PROGRAM,
    "언론보도": SubjectKind.ORGANIZATION,
    "특성화고학과·과정": SubjectKind.SCHOOL,
}
_CATEGORY_ALIASES = {
    "education_event": "교육청대회·사업",
    "association_program": "협회사업",
    "school_club": "학교동아리·팀",
    "university": "대학학과·전공·동아리",
    "infrastructure": "경기장·인프라",
    "local_policy": "지자체정책·조례",
    "media": "언론보도",
    "vocational_program": "특성화고학과·과정",
}
_SCOPE_ALIASES = {
    "regional": Scope.REGIONAL,
    "nationwide": Scope.NATIONWIDE,
    "adjacent": Scope.ADJACENT,
    "unknown": Scope.UNKNOWN,
    "location_unknown": Scope.UNKNOWN,
}


@dataclass(frozen=True, slots=True)
class NormalizedClassification:
    """A primary kind and scope derived without name or proximity matching."""

    primary_kind: SubjectKind
    scope: Scope
    is_mappable: bool


def normalize_v2_classification(
    category: str,
    scope: str,
    *,
    source_system: str | None = None,
) -> NormalizedClassification:
    """Map a v2 category/scope pair to its primary kind.

    `localdata.go.kr` source data is always a venue.  Unknown locations remain
    off-map; no regional inference is performed.  The category map deliberately
    keeps a nationwide local-policy record as a program rather than assigning it
    to a regional government entity.
    """

    if not isinstance(category, str) or not isinstance(scope, str):
        raise NormalizationError("v2 category and scope must be strings")
    if source_system is not None and not isinstance(source_system, str):
        raise NormalizationError("source_system must be a string or None")
    canonical_category = _CATEGORY_ALIASES.get(category, category)
    try:
        normalized_scope = _SCOPE_ALIASES[scope]
    except KeyError as error:
        raise NormalizationError(f"unsupported v2 scope: {scope!r}") from error

    if source_system is not None and source_system.strip().casefold() == "localdata.go.kr":
        kind = SubjectKind.VENUE
    else:
        try:
            kind = _CATEGORY_KINDS[canonical_category]
        except KeyError as error:
            raise NormalizationError(f"unsupported v2 category: {category!r}") from error

    return NormalizedClassification(kind, normalized_scope, normalized_scope is Scope.REGIONAL)


def kst_date(value: date | datetime | str) -> date:
    """Convert an explicit occurrence value to its calendar date in KST."""

    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise NormalizationError("datetime occurrence values must include a timezone")
        return value.astimezone(KST).date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError as error:
            raise NormalizationError("occurrence dates must be ISO YYYY-MM-DD") from error
    raise NormalizationError("occurrence date must be date, datetime, or ISO date")


def occurrence_fingerprint(
    subject_id: UUID,
    occurrence_date: date | datetime | str,
    discriminator: str,
    *,
    version: str = "v1",
) -> str:
    """Return the exact, versioned fingerprint for one occurrence.

    The input is exactly subject UUID, KST calendar date, and a caller-supplied
    discriminator.  It performs no fuzzy matching or merge decision.
    """

    if not isinstance(subject_id, UUID):
        raise NormalizationError("subject_id must be a UUID")
    if not isinstance(version, str):
        raise NormalizationError("fingerprint version must be a string")
    if not re.fullmatch(r"v[1-9][0-9]*", version):
        raise NormalizationError("fingerprint version must have the form vN")
    if not isinstance(discriminator, str) or not discriminator:
        raise NormalizationError("discriminator must be a non-empty string")
    if "\n" in discriminator or "\0" in discriminator:
        raise NormalizationError("discriminator contains a reserved separator")
    payload = f"{version}\n{subject_id}\n{kst_date(occurrence_date).isoformat()}\n{discriminator}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
