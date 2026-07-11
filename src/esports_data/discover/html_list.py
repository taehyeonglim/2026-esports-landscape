"""Pure static HTML anchor extraction; this module never drives a browser."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from html.parser import HTMLParser

from esports_data.fetch import clean_discovery_url, safe_title_digest
from esports_data.sanitize import SanitizedUrl, sanitize_url


class HtmlListError(str, Enum):
    MALFORMED_HTML = "malformed_html"
    EMPTY_LIST = "empty_list"


@dataclass(frozen=True, slots=True)
class HtmlListEntry:
    url: str
    url_record: SanitizedUrl
    title_digest: str | None


@dataclass(frozen=True, slots=True)
class HtmlListParseResult:
    entries: tuple[HtmlListEntry, ...]
    error: HtmlListError | None = None


class _AnchorParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.anchors: list[tuple[str, str | None]] = []
        self._href: str | None = None
        self._text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.casefold() != "a" or self._href is not None:
            return
        attributes = dict(attrs)
        href = attributes.get("href")
        if href:
            self._href = href
            self._text = [attributes["title"]] if attributes.get("title") else []

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() == "a" and self._href is not None:
            title = " ".join(part.strip() for part in self._text if part.strip()) or None
            self.anchors.append((self._href, title))
            self._href = None
            self._text = []


def parse_html_list(document: bytes | str, *, base_url: str, salt: str | bytes) -> HtmlListParseResult:
    """Extract unique static anchors; titles are returned only as safe digests."""

    try:
        source = document.decode("utf-8") if isinstance(document, bytes) else document
        if not isinstance(source, str):
            raise TypeError
        parser = _AnchorParser()
        parser.feed(source)
        parser.close()
        if parser._href is not None:
            return HtmlListParseResult((), HtmlListError.MALFORMED_HTML)
    except (UnicodeError, TypeError):
        return HtmlListParseResult((), HtmlListError.MALFORMED_HTML)

    entries: list[HtmlListEntry] = []
    seen: set[str] = set()
    for raw_url, title in parser.anchors:
        clean_url = clean_discovery_url(raw_url, base_url)
        if clean_url is None or clean_url in seen:
            continue
        seen.add(clean_url)
        title_digest = safe_title_digest(title, salt=salt)
        entries.append(HtmlListEntry(clean_url, sanitize_url(clean_url, salt=salt), title_digest))
    if not entries:
        return HtmlListParseResult((), HtmlListError.EMPTY_LIST)
    return HtmlListParseResult(tuple(entries))