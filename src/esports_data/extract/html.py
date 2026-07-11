"""Fail-closed HTML metadata extraction from transient bytes."""

from __future__ import annotations

from html.parser import HTMLParser

from .json import (
    _BOOL_PREDICATES,
    _COUNT_PREDICATES,
    _DATE_PREDICATES,
    _DIGEST_PREDICATES,
    _TEXT_PREDICATES,
    _YEAR_PREDICATES,
    ExtractResult,
    ExtractStatus,
    facts_from_items,
    fingerprint_bytes,
)

_KNOWN_PREDICATES = (
    _TEXT_PREDICATES
    | _YEAR_PREDICATES
    | _COUNT_PREDICATES
    | _BOOL_PREDICATES
    | _DATE_PREDICATES
    | _DIGEST_PREDICATES
)


class _FactParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.items: list[dict[str, object]] = []
        self.seen_candidate = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {key.casefold(): value for key, value in attrs}
        if tag.casefold() == "meta":
            predicate = attributes.get("name") or attributes.get("property")
            content = attributes.get("content")
            if predicate in _KNOWN_PREDICATES:
                self.seen_candidate = True
                self.items.append({"predicate": predicate, "value": content, "locator": f"meta:{predicate}", "evidence": content or ""})
        elif tag.casefold() == "data" and "data-predicate" in attributes:
            predicate = attributes["data-predicate"]
            value = attributes.get("value")
            if predicate in _KNOWN_PREDICATES:
                self.seen_candidate = True
                self.items.append({"predicate": predicate, "value": value, "locator": f"data:{predicate}", "evidence": value or ""})


def extract_html(document: bytes, *, salt: str | bytes, max_bytes: int = 2_000_000) -> ExtractResult:
    """Extract allowlisted ``meta`` and ``data-predicate`` facts only.

    HTML body text, titles, links, scripts, and parser errors never cross this
    boundary.
    """

    fingerprint = fingerprint_bytes(document) if isinstance(document, bytes) else ""
    if not isinstance(document, bytes) or not isinstance(max_bytes, int) or not 0 < max_bytes <= 20_000_000 or len(document) > max_bytes:
        return ExtractResult(ExtractStatus.OVERSIZE, fingerprint)
    try:
        text = document.decode("utf-8")
    except UnicodeDecodeError:
        return ExtractResult(ExtractStatus.MALFORMED, fingerprint)
    parser = _FactParser()
    try:
        parser.feed(text)
        parser.close()
    except Exception:
        return ExtractResult(ExtractStatus.MALFORMED, fingerprint)
    if not parser.seen_candidate:
        return ExtractResult(ExtractStatus.ZERO_TEXT, fingerprint)
    return facts_from_items(parser.items, salt=salt, fingerprint=fingerprint)
