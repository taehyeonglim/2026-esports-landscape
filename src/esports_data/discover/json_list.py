"""Pure extraction from explicitly supplied JSON URL lists."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import json

from esports_data.fetch import clean_discovery_url, safe_title_digest
from esports_data.sanitize import SanitizedUrl, sanitize_url


class JsonListError(str, Enum):
    MALFORMED_JSON = "malformed_json"
    INVALID_LIST = "invalid_list"
    EMPTY_LIST = "empty_list"


@dataclass(frozen=True, slots=True)
class JsonListEntry:
    url: str
    url_record: SanitizedUrl
    title_digest: str | None


@dataclass(frozen=True, slots=True)
class JsonListParseResult:
    entries: tuple[JsonListEntry, ...]
    error: JsonListError | None = None


def parse_json_list(document: bytes | str, *, base_url: str, salt: str | bytes) -> JsonListParseResult:
    """Extract URLs from a JSON array of strings or ``{"url", "title"}`` objects."""

    try:
        values = json.loads(document)
    except (json.JSONDecodeError, TypeError, UnicodeError):
        return JsonListParseResult((), JsonListError.MALFORMED_JSON)
    if not isinstance(values, list):
        return JsonListParseResult((), JsonListError.INVALID_LIST)

    entries: list[JsonListEntry] = []
    seen: set[str] = set()
    for value in values:
        raw_url, title = _item_fields(value)
        clean_url = clean_discovery_url(raw_url, base_url) if raw_url else None
        if clean_url is None or clean_url in seen:
            continue
        seen.add(clean_url)
        title_digest = safe_title_digest(title, salt=salt)
        entries.append(JsonListEntry(clean_url, sanitize_url(clean_url, salt=salt), title_digest))
    if not entries:
        return JsonListParseResult((), JsonListError.EMPTY_LIST)
    return JsonListParseResult(tuple(entries))


def _item_fields(value: object) -> tuple[str | None, str | None]:
    if isinstance(value, str):
        return value, None
    if not isinstance(value, dict) or set(value) - {"url", "title"}:
        return None, None
    raw_url = value.get("url")
    title = value.get("title")
    return (raw_url if isinstance(raw_url, str) else None, title if isinstance(title, str) else None)