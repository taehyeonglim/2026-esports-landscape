"""Pure sitemap XML URL extraction with privacy-safe URL records."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from xml.etree import ElementTree

from esports_data.fetch import clean_discovery_url
from esports_data.sanitize import SanitizedUrl, sanitize_url


class SitemapError(str, Enum):
    MALFORMED_XML = "malformed_xml"
    UNSUPPORTED_SITEMAP = "unsupported_sitemap"
    EMPTY_SITEMAP = "empty_sitemap"


@dataclass(frozen=True, slots=True)
class SitemapEntry:
    url: str
    url_record: SanitizedUrl


@dataclass(frozen=True, slots=True)
class SitemapParseResult:
    entries: tuple[SitemapEntry, ...]
    error: SitemapError | None = None


def parse_sitemap(document: bytes | str, *, base_url: str, salt: str | bytes) -> SitemapParseResult:
    """Extract unique URLs from a URL-set or sitemap index without fetching them."""

    try:
        root = ElementTree.fromstring(document)
    except (ElementTree.ParseError, TypeError, UnicodeError):
        return SitemapParseResult((), SitemapError.MALFORMED_XML)
    if _local_name(root.tag) not in {"urlset", "sitemapindex"}:
        return SitemapParseResult((), SitemapError.UNSUPPORTED_SITEMAP)

    entries: list[SitemapEntry] = []
    seen: set[str] = set()
    for node in root:
        if _local_name(node.tag) not in {"url", "sitemap"}:
            continue
        raw_url = next((child.text.strip() for child in node if _local_name(child.tag) == "loc" and child.text and child.text.strip()), None)
        clean_url = clean_discovery_url(raw_url, base_url) if raw_url else None
        if clean_url is not None and clean_url not in seen:
            seen.add(clean_url)
            entries.append(SitemapEntry(clean_url, sanitize_url(clean_url, salt=salt)))
    if not entries:
        return SitemapParseResult((), SitemapError.EMPTY_SITEMAP)
    return SitemapParseResult(tuple(entries))


def _local_name(tag: object) -> str:
    return tag.rsplit("}", 1)[-1].casefold() if isinstance(tag, str) else ""
