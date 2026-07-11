"""Pure RSS and Atom discovery with pre-persistence PII screening."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from xml.etree import ElementTree

from esports_data.fetch import clean_discovery_url, safe_title_digest
from esports_data.sanitize import SanitizedUrl, sanitize_url


class RssError(str, Enum):
    MALFORMED_XML = "malformed_xml"
    UNSUPPORTED_FEED = "unsupported_feed"
    EMPTY_FEED = "empty_feed"


@dataclass(frozen=True, slots=True)
class RssEntry:
    """A transient clean URL and sanitized metadata suitable for persistence."""

    url: str
    url_record: SanitizedUrl
    title_digest: str | None


@dataclass(frozen=True, slots=True)
class RssParseResult:
    entries: tuple[RssEntry, ...]
    error: RssError | None = None


def parse_rss_or_atom(document: bytes | str, *, base_url: str, salt: str | bytes) -> RssParseResult:
    """Extract unique item links from one RSS or Atom document deterministically."""
    if not isinstance(document, (bytes, str)) or len(document) > 2_000_000:
        return RssParseResult((), RssError.MALFORMED_XML)
    lowered = document.lower()
    dtd_markers = (b"<!doctype", b"<!entity") if isinstance(lowered, bytes) else ("<!doctype", "<!entity")
    if any(marker in lowered for marker in dtd_markers):
        return RssParseResult((), RssError.MALFORMED_XML)

    try:
        root = ElementTree.fromstring(document)
    except (ElementTree.ParseError, TypeError, UnicodeError):
        return RssParseResult((), RssError.MALFORMED_XML)
    root_name = _local_name(root.tag)
    if root_name not in {"rss", "feed", "rdf"}:
        return RssParseResult((), RssError.UNSUPPORTED_FEED)

    entries: list[RssEntry] = []
    seen: set[str] = set()
    for node in root.iter():
        if _local_name(node.tag) not in {"item", "entry"}:
            continue
        link = _entry_link(node)
        entry = _safe_entry(link, _child_text(node, "title"), base_url, salt)
        if entry is not None and entry.url not in seen:
            seen.add(entry.url)
            entries.append(entry)
    if not entries:
        return RssParseResult((), RssError.EMPTY_FEED)
    return RssParseResult(tuple(entries))


def _entry_link(node: ElementTree.Element[str]) -> str | None:
    for child in node:
        if _local_name(child.tag) != "link":
            continue
        href = child.get("href")
        if href and child.get("rel", "alternate") in {"alternate", ""}:
            return href
        if child.text and child.text.strip():
            return child.text.strip()
    return None


def _child_text(node: ElementTree.Element[str], name: str) -> str | None:
    for child in node:
        if _local_name(child.tag) == name and child.text:
            return child.text.strip()
    return None


def _safe_entry(raw_url: str | None, title: str | None, base_url: str, salt: str | bytes) -> RssEntry | None:
    if not raw_url:
        return None
    clean_url = clean_discovery_url(raw_url, base_url)
    if clean_url is None:
        return None
    title_digest = safe_title_digest(title, salt=salt)
    return RssEntry(clean_url, sanitize_url(clean_url, salt=salt), title_digest)


def _local_name(tag: object) -> str:
    return tag.rsplit("}", 1)[-1].casefold() if isinstance(tag, str) else ""
