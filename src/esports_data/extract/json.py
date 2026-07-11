"""Fail-closed JSON extraction for transient response bytes.

Only the explicit ``facts`` envelope is accepted.  Values are screened before
leaving this module; callers must treat the returned result as the sole
persistence input, never the JSON document.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
import re
from typing import Any, Iterable

from esports_data.pii import scan_text
from esports_data.sanitize import salted_digest


class ExtractStatus(str, Enum):
    SUCCESS = "success"
    OVERSIZE = "oversize"
    MALFORMED = "malformed"
    UNSUPPORTED = "unsupported"
    ENCRYPTED = "encrypted"
    ZERO_TEXT = "zero_text"
    PII_BLOCKED = "pii_blocked"


@dataclass(frozen=True, slots=True)
class ExtractedFact:
    """A typed, allowlisted fact whose locator and evidence are opaque digests."""

    predicate: str
    value: str | int | bool
    locator_digest: str
    evidence_digest: str


@dataclass(frozen=True, slots=True)
class ExtractResult:
    """Safe extractor output. ``fingerprint`` is a SHA-256 content fingerprint."""

    status: ExtractStatus
    fingerprint: str
    facts: tuple[ExtractedFact, ...] = ()


_TEXT_PREDICATES = frozenset({
    "program_name", "organization_name", "school_name", "event_name", "location_name",
})
_YEAR_PREDICATES = frozenset({"founded_year"})
_COUNT_PREDICATES = frozenset({"team_count"})
_BOOL_PREDICATES = frozenset({"official_status"})
_DATE_PREDICATES = frozenset({"event_date"})
_DIGEST_PREDICATES = frozenset({"document_text_digest"})
_MAX_FACTS = 10_000
_DATE = re.compile(r"\d{4}-\d{2}-\d{2}\Z")
_HEX_DIGEST = re.compile(r"[0-9a-f]{64}\Z")


def fingerprint_bytes(document: bytes) -> str:
    """Return the content hash without retaining the transient document."""

    return hashlib.sha256(document).hexdigest()


def extract_json(document: bytes, *, salt: str | bytes, max_bytes: int = 2_000_000) -> ExtractResult:
    """Extract the strict ``{"facts": [...]}`` JSON envelope from bytes."""

    fingerprint = fingerprint_bytes(document) if isinstance(document, bytes) else ""
    if not _valid_input(document, max_bytes):
        return ExtractResult(ExtractStatus.OVERSIZE, fingerprint)
    try:
        decoded = document.decode("utf-8")
        payload = json.loads(decoded)
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError):
        return ExtractResult(ExtractStatus.MALFORMED, fingerprint)
    if not isinstance(payload, dict) or set(payload) != {"facts"} or not isinstance(payload["facts"], list):
        return ExtractResult(ExtractStatus.UNSUPPORTED, fingerprint)
    try:
        return _result_from_items(payload["facts"], salt=salt, fingerprint=fingerprint)
    except RecursionError:
        return ExtractResult(ExtractStatus.MALFORMED, fingerprint)


def facts_from_items(items: Iterable[object], *, salt: str | bytes, fingerprint: str) -> ExtractResult:
    """Validate extractor-specific fact records into the common safe result."""

    try:
        return _result_from_items(items, salt=salt, fingerprint=fingerprint)
    except RecursionError:
        return ExtractResult(ExtractStatus.MALFORMED, fingerprint)


def _result_from_items(items: Iterable[object], *, salt: str | bytes, fingerprint: str) -> ExtractResult:
    facts: list[ExtractedFact] = []
    saw_item = False
    for index, item in enumerate(items):
        saw_item = True
        if index >= _MAX_FACTS:
            return ExtractResult(ExtractStatus.OVERSIZE, fingerprint)
        fact = _fact_from_item(item, locator=f"fact:{index}", salt=salt)
        if fact is None:
            return ExtractResult(ExtractStatus.PII_BLOCKED if _contains_text(item) else ExtractStatus.UNSUPPORTED, fingerprint)
        facts.append(fact)
    if not saw_item:
        return ExtractResult(ExtractStatus.ZERO_TEXT, fingerprint)
    return ExtractResult(ExtractStatus.SUCCESS, fingerprint, tuple(facts))


def _fact_from_item(item: object, *, locator: str, salt: str | bytes) -> ExtractedFact | None:
    if not isinstance(item, dict) or set(item) - {"predicate", "value", "evidence", "locator"}:
        return None
    predicate, value = item.get("predicate"), item.get("value")
    if not isinstance(predicate, str) or not _valid_value(predicate, value):
        return None
    evidence = item.get("evidence", "")
    source_locator = item.get("locator", locator)
    if not isinstance(evidence, str) or not isinstance(source_locator, str):
        return None
    if len(evidence) > 280 or len(source_locator) > 160 or not _clean_text(evidence) or not _clean_text(source_locator):
        return None
    return ExtractedFact(
        predicate=predicate,
        value=value,
        locator_digest=salted_digest(source_locator, salt=salt),
        evidence_digest=salted_digest(evidence or f"{predicate}:{value}", salt=salt),
    )


def _valid_value(predicate: str, value: object) -> bool:
    if predicate in _TEXT_PREDICATES:
        return isinstance(value, str) and 0 < len(value) <= 240 and _clean_text(value)
    if predicate in _YEAR_PREDICATES:
        return isinstance(value, int) and not isinstance(value, bool) and 1800 <= value <= 2100
    if predicate in _COUNT_PREDICATES:
        return isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= 100_000
    if predicate in _BOOL_PREDICATES:
        return isinstance(value, bool)
    if predicate in _DATE_PREDICATES:
        return isinstance(value, str) and bool(_DATE.fullmatch(value))
    if predicate in _DIGEST_PREDICATES:
        return isinstance(value, str) and bool(_HEX_DIGEST.fullmatch(value))
    return False


def _clean_text(value: str) -> bool:
    return bool(value) and scan_text(value).is_clean and "http://" not in value.casefold() and "https://" not in value.casefold()


def _contains_text(value: object) -> bool:
    if isinstance(value, str):
        return not scan_text(value).is_clean
    if isinstance(value, dict):
        return any(_contains_text(part) for part in value.values())
    if isinstance(value, list):
        return any(_contains_text(part) for part in value)
    return False


def _valid_input(document: object, max_bytes: int) -> bool:
    return isinstance(document, bytes) and isinstance(max_bytes, int) and 0 < max_bytes <= 20_000_000 and len(document) <= max_bytes
