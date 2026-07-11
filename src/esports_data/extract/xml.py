"""Fail-closed XML fact-envelope extraction from transient bytes."""

from __future__ import annotations

import xml.etree.ElementTree as ElementTree

from .json import ExtractResult, ExtractStatus, facts_from_items, fingerprint_bytes


def extract_xml(document: bytes, *, salt: str | bytes, max_bytes: int = 2_000_000) -> ExtractResult:
    """Extract ``<facts><fact .../></facts>`` records using the stdlib parser."""

    fingerprint = fingerprint_bytes(document) if isinstance(document, bytes) else ""
    if not isinstance(document, bytes) or not isinstance(max_bytes, int) or not 0 < max_bytes <= 20_000_000 or len(document) > max_bytes:
        return ExtractResult(ExtractStatus.OVERSIZE, fingerprint)
    try:
        text = document.decode("utf-8")
    except UnicodeDecodeError:
        return ExtractResult(ExtractStatus.MALFORMED, fingerprint)
    if "<!DOCTYPE" in text:
        return ExtractResult(ExtractStatus.UNSUPPORTED, fingerprint)
    try:
        root = ElementTree.fromstring(text)
    except (ElementTree.ParseError, RecursionError):
        return ExtractResult(ExtractStatus.MALFORMED, fingerprint)
    if root.tag != "facts" or root.text and root.text.strip():
        return ExtractResult(ExtractStatus.UNSUPPORTED, fingerprint)
    items: list[dict[str, object]] = []
    for index, element in enumerate(root):
        if element.tag != "fact" or element.text and element.text.strip() or element.tail and element.tail.strip():
            return ExtractResult(ExtractStatus.UNSUPPORTED, fingerprint)
        if set(element.attrib) - {"predicate", "value", "evidence", "locator"}:
            return ExtractResult(ExtractStatus.UNSUPPORTED, fingerprint)
        predicate = element.attrib.get("predicate")
        value: object = element.attrib.get("value")
        if predicate in {"founded_year", "team_count"} and isinstance(value, str) and value.isascii() and value.isdecimal():
            value = int(value)
        elif predicate == "official_status" and value in {"true", "false"}:
            value = value == "true"
        items.append({
            "predicate": predicate,
            "value": value,
            "evidence": element.attrib.get("evidence", ""),
            "locator": element.attrib.get("locator", f"fact:{index}"),
        })
    return facts_from_items(items, salt=salt, fingerprint=fingerprint)
