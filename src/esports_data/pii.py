"""Deterministic, allowlist-first screening for minor PII."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re
from typing import Iterable
from urllib.parse import urlsplit


class PiiKind(str, Enum):
    """Minor-PII categories that cannot cross the persistence boundary."""

    PHONE = "phone"
    EMAIL = "email"
    ACCOUNT_HANDLE = "account_handle"
    STUDENT_NAME_MARKER = "student_name_marker"
    URL_QUERY_FRAGMENT = "url_query_fragment"
    PHOTO_CAPTION = "photo_caption"
    PRECISE_ADDRESS = "precise_address"


@dataclass(frozen=True, slots=True)
class PiiFinding:
    """A PII category and position, without retaining matched source text."""

    kind: PiiKind
    start: int
    end: int


@dataclass(frozen=True, slots=True)
class PiiScanResult:
    """The findings from one deterministic scan."""

    findings: tuple[PiiFinding, ...]

    @property
    def is_clean(self) -> bool:
        """Return whether no disallowed PII was found."""

        return not self.findings


_PHONE = re.compile(r"(?<!\w)(?:\+?\d{1,3}[ .-]?)?(?:\(?\d{2,4}\)?[ .-]?){2}\d{3,4}(?!\w)")
_EMAIL = re.compile(r"(?<![\w.+-])[\w.+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+(?![\w.-])")
_HANDLE = re.compile(r"(?<![\w@])@[A-Za-z0-9_]{2,32}\b")
_STUDENT_NAME = re.compile(r"(?:학생\s*(?:이름|성명|명)|student\s*name)\s*[:：-]?\s*\S+", re.IGNORECASE)
_PHOTO_CAPTION = re.compile(r"(?:photo\s*caption|사진\s*(?:설명|캡션))\s*[:：-]?\s*\S+", re.IGNORECASE)
_ADDRESS = re.compile(
    r"(?:\b\d{1,5}\s+[A-Za-z][A-Za-z .'-]{2,40}\s(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Lane|Ln)\b|"
    r"(?:서울|부산|대구|인천|광주|대전|울산|세종|경기|강원|충북|충남|전북|전남|경북|경남|제주)\S{0,20}(?:로|길)\s*\d+)",
    re.IGNORECASE,
)
_URL = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)


def _allowed(value: str, allowlist: frozenset[str]) -> bool:
    return value.casefold() in allowlist


def scan_url(url: str, *, allowlist: Iterable[str] = ()) -> PiiScanResult:
    """Find query or fragment data in a URL unless the full URL is allowlisted."""

    allowed = frozenset(item.casefold() for item in allowlist)
    if _allowed(url, allowed):
        return PiiScanResult(())
    parsed = urlsplit(url)
    if parsed.query or parsed.fragment:
        return PiiScanResult((PiiFinding(PiiKind.URL_QUERY_FRAGMENT, 0, len(url)),))
    return PiiScanResult(())


def scan_text(text: str, *, allowlist: Iterable[str] = ()) -> PiiScanResult:
    """Scan text for disallowed minor PII, honoring exact allowlisted matches first."""

    allowed = frozenset(item.casefold() for item in allowlist)
    findings: list[PiiFinding] = []
    patterns = (
        (PiiKind.PHONE, _PHONE),
        (PiiKind.EMAIL, _EMAIL),
        (PiiKind.ACCOUNT_HANDLE, _HANDLE),
        (PiiKind.STUDENT_NAME_MARKER, _STUDENT_NAME),
        (PiiKind.PHOTO_CAPTION, _PHOTO_CAPTION),
        (PiiKind.PRECISE_ADDRESS, _ADDRESS),
    )
    for kind, pattern in patterns:
        for match in pattern.finditer(text):
            if not _allowed(match.group(), allowed):
                findings.append(PiiFinding(kind, match.start(), match.end()))
    for match in _URL.finditer(text):
        if not _allowed(match.group(), allowed):
            findings.extend(
                PiiFinding(PiiKind.URL_QUERY_FRAGMENT, match.start(), match.end())
                for _ in scan_url(match.group()).findings
            )
    return PiiScanResult(tuple(sorted(findings, key=lambda item: (item.start, item.end, item.kind.value))))
