"""Fail-closed PDF extraction with a lazy optional ``pypdf`` dependency."""

from __future__ import annotations

from io import BytesIO
import hashlib

from esports_data.pii import scan_text

from .json import ExtractResult, ExtractStatus, facts_from_items, fingerprint_bytes
_MAX_EXTRACTED_TEXT_CHARS = 2_000_000
_ALLOWED_PAGE_RESOURCE_KEYS = frozenset({"/Font", "/ProcSet"})


def _resolved(value: object) -> object:
    get_object = getattr(value, "get_object", None)
    return get_object() if callable(get_object) else value


def _mapping(value: object) -> object | None:
    value = _resolved(value)
    return value if hasattr(value, "get") and hasattr(value, "keys") else None


def _page_value(page: object, key: str) -> object | None:
    value = page.get(key) if hasattr(page, "get") else None
    if value is not None:
        return value
    get_inheritable = getattr(page, "get_inheritable", None)
    return get_inheritable(key) if callable(get_inheritable) else None


def _profile_status(reader: object) -> ExtractStatus | None:
    """Reject PDF surfaces whose text cannot be completely PII-screened."""

    trailer = _mapping(getattr(reader, "trailer", None))
    if trailer is None:
        return ExtractStatus.UNSUPPORTED
    if "/Info" in trailer:
        return ExtractStatus.PII_BLOCKED
    root = _mapping(trailer.get("/Root"))
    if root is None:
        return ExtractStatus.UNSUPPORTED
    if any(
        key in root
        for key in ("/Metadata", "/Names", "/AF", "/AcroForm", "/OpenAction", "/AA")
    ):
        return ExtractStatus.PII_BLOCKED
    for page in reader.pages:
        page_dictionary = _mapping(page)
        if page_dictionary is None:
            return ExtractStatus.UNSUPPORTED
        if any(key in page_dictionary for key in ("/Annots", "/AF", "/A", "/AA")):
            return ExtractStatus.PII_BLOCKED
        resources = _page_value(page, "/Resources")
        if resources is None:
            continue
        resources = _mapping(resources)
        if resources is None or set(resources) - _ALLOWED_PAGE_RESOURCE_KEYS:
            return ExtractStatus.UNSUPPORTED
    return None


def extract_pdf(document: bytes, *, salt: str | bytes, max_bytes: int = 8_000_000) -> ExtractResult:
    """Return only a digest-backed fact after bounded PDF text screening.

    PDF text is deliberately never returned.  It is used transiently only to
    reject PII-bearing documents and to distinguish zero-text files.
    """

    fingerprint = fingerprint_bytes(document) if isinstance(document, bytes) else ""
    if not isinstance(document, bytes) or not isinstance(max_bytes, int) or not 0 < max_bytes <= 20_000_000 or len(document) > max_bytes:
        return ExtractResult(ExtractStatus.OVERSIZE, fingerprint)
    try:
        from pypdf import PdfReader
    except ImportError:
        return ExtractResult(ExtractStatus.UNSUPPORTED, fingerprint)
    try:
        reader = PdfReader(BytesIO(document))
        if reader.is_encrypted:
            return ExtractResult(ExtractStatus.ENCRYPTED, fingerprint)
        profile_status = _profile_status(reader)
        if profile_status is not None:
            return ExtractResult(profile_status, fingerprint)
        text_parts: list[str] = []
        text_length = 0
        for page in reader.pages:
            page_text = page.extract_text() or ""
            if not isinstance(page_text, str):
                return ExtractResult(ExtractStatus.MALFORMED, fingerprint)
            text_length += len(page_text) + (1 if text_parts else 0)
            if text_length > _MAX_EXTRACTED_TEXT_CHARS:
                return ExtractResult(ExtractStatus.OVERSIZE, fingerprint)
            text_parts.append(page_text)
        text = "\n".join(text_parts)
    except Exception:
        return ExtractResult(ExtractStatus.MALFORMED, fingerprint)
    if not text.strip():
        return ExtractResult(ExtractStatus.ZERO_TEXT, fingerprint)
    if not scan_text(text).is_clean:
        return ExtractResult(ExtractStatus.PII_BLOCKED, fingerprint)
    text_digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return facts_from_items(
        [{"predicate": "document_text_digest", "value": text_digest, "locator": "pdf:text", "evidence": text_digest}],
        salt=salt,
        fingerprint=fingerprint,
    )
