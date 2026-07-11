"""Bounded registered-source retrieval with body-ephemeral extraction."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import http.client
import ipaddress
import socket
import time
import weakref
from typing import Any
from urllib.parse import urljoin, urlsplit, urlunsplit
import zlib

from esports_data.extract.html import extract_html
from esports_data.extract.json import ExtractResult, extract_json
from esports_data.extract.pdf import extract_pdf
from esports_data.extract.xml import extract_xml
from esports_data.pii import scan_text, scan_url
from esports_data.registry import SourceRegistry
from esports_data.policy import canonical_policy_hash
from esports_data.sanitize import InvalidExternalValueError, salted_digest, sanitize_url


class FetchStatus(str, Enum):
    """PII-free outcomes for a retrieval attempt."""

    SUCCESS = "success"
    NOT_MODIFIED = "not_modified"
    INVALID_URL = "invalid_url"
    DNS_REJECTED = "dns_rejected"
    DISALLOWED_REDIRECT = "disallowed_redirect"
    RESPONSE_TOO_LARGE = "response_too_large"
    DECOMPRESSED_TOO_LARGE = "decompressed_too_large"
    HTTP_ERROR = "http_error"
    RETRY_EXHAUSTED = "retry_exhausted"
    NETWORK_ERROR = "network_error"
    EXTRACTOR_ERROR = "extractor_error"


@dataclass(frozen=True, slots=True)
class FetchResult:
    """Safe response metadata; bodies and raw response validators never escape."""

    status: FetchStatus
    status_code: int | None = None
    etag_digest: str | None = None
    last_modified_digest: str | None = None


@dataclass(frozen=True, slots=True, weakref_slot=True)
class RegisteredFetchResult(FetchResult):
    """Safe registered-fetch output with process-local provenance attestation.

    The private token prevents accidental or forged provenance through the normal
    Python API; it is not a cryptographic process boundary. Cross-process workers
    require a future signed fetch receipt.
    """

    extraction: ExtractResult | None = None
    registry_hash: str | None = None
    source_id: str | None = None
    canonical_origin: tuple[str, str, int] | None = None
    url_path_digest: str | None = None
    extractor_kind: str | None = None
    extractor_version: str | None = None
    extraction_fingerprint: str | None = None

@dataclass(frozen=True, slots=True)
class _TransportResult:
    metadata: FetchResult
    body: bytes | None = None


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    """HTTPS transport whose TCP peer was approved by a single DNS lookup."""

    def __init__(
        self,
        host: str,
        peer: tuple[int, tuple[Any, ...]],
        *,
        timeout: float,
    ) -> None:
        super().__init__(host, port=443, timeout=timeout)
        self._peer = peer

    def connect(self) -> None:
        sock = socket.socket(self._peer[0], socket.SOCK_STREAM)
        try:
            sock.settimeout(self.timeout)
            sock.connect(self._peer[1])
            self.sock = self._context.wrap_socket(sock, server_hostname=self.host)
        except Exception:
            sock.close()
            raise


_EXTRACTORS = {
    "html": extract_html,
    "json": extract_json,
    "xml": extract_xml,
    "pdf": extract_pdf,
}
_EXTRACTOR_VERSIONS = {
    "html": "1",
    "json": "1",
    "xml": "1",
    "pdf": "1",
}
_ISSUED_ATTESTATIONS: dict[
    int, tuple[weakref.ReferenceType[RegisteredFetchResult], SourceRegistry]
] = {}


def _attest_registered_fetch(
    metadata: FetchResult,
    extraction: ExtractResult,
    *,
    registry: SourceRegistry,
    source_id: str,
    canonical_origin: tuple[str, str, int],
    url_path_digest: str,
    extractor_kind: str,
) -> RegisteredFetchResult:
    """Issue the in-process receipt immediately after extracting the fetched body."""
    result = RegisteredFetchResult(
        metadata.status,
        metadata.status_code,
        metadata.etag_digest,
        metadata.last_modified_digest,
        extraction,
        canonical_policy_hash(registry),
        source_id,
        canonical_origin,
        url_path_digest,
        extractor_kind,
        _EXTRACTOR_VERSIONS[extractor_kind],
        extraction.fingerprint,
    )
    _ISSUED_ATTESTATIONS[id(result)] = (weakref.ref(result), registry)
    return result


def _validate_registered_attestation(
    registry: SourceRegistry, result: object
) -> RegisteredFetchResult:
    """Validate an issued receipt before ingest; this is intentionally in-process only."""
    if not isinstance(registry, SourceRegistry) or type(result) is not RegisteredFetchResult:
        raise ValueError("registered fetch receipt is invalid")
    receipt = _ISSUED_ATTESTATIONS.get(id(result))
    if receipt is None or receipt[0]() is not result:
        raise ValueError("registered fetch receipt was not issued by this process")
    if receipt[1] is not registry or result.registry_hash != canonical_policy_hash(registry):
        raise ValueError("registered fetch receipt belongs to another registry")
    if result.status is not FetchStatus.SUCCESS or not isinstance(result.extraction, ExtractResult):
        raise ValueError("registered fetch receipt did not successfully extract")
    if (
        not isinstance(result.source_id, str)
        or not isinstance(result.canonical_origin, tuple)
        or not isinstance(result.url_path_digest, str)
        or result.extractor_kind not in _EXTRACTORS
        or result.extractor_version != _EXTRACTOR_VERSIONS[result.extractor_kind]
        or result.extraction_fingerprint != result.extraction.fingerprint
    ):
        raise ValueError("registered fetch receipt fields are invalid")
    source = registry.active_by_id(result.source_id)
    if source.canonical_origin != result.canonical_origin:
        raise ValueError("registered fetch receipt origin does not match source")
    return result


def fetch_and_process_registered(
    registry: SourceRegistry,
    source_id: str,
    url: str,
    extractor_kind: str,
    *,
    salt: str | bytes,
) -> RegisteredFetchResult:
    """Fetch an active registered source and run one fixed extractor internally.

    The requested URL must be HTTPS/443 on the active source's canonical origin.
    Each request pins its TCP connection to addresses approved by one DNS lookup.
    """
    if not isinstance(registry, SourceRegistry) or not isinstance(source_id, str):
        return RegisteredFetchResult(FetchStatus.INVALID_URL)
    try:
        source = registry.active_by_id(source_id)
    except KeyError:
        return RegisteredFetchResult(FetchStatus.INVALID_URL)
    extractor = _EXTRACTORS.get(extractor_kind) if type(extractor_kind) is str else None
    if (
        extractor is None
        or not _valid_salt(salt)
        or not _matches_origin(url, source.canonical_origin)
    ):
        return RegisteredFetchResult(FetchStatus.INVALID_URL)

    current_url = url
    redirects = 0
    while True:
        host = _canonical_host(urlsplit(current_url).hostname)
        peers = _resolve_global_peers(host, 443) if host else ()
        if not peers:
            return RegisteredFetchResult(FetchStatus.DNS_REJECTED)
        transport, redirect_to = _request_with_retries(
            current_url,
            peers,
            salt=salt,
            timeout_seconds=10.0,
            max_response_bytes=2_000_000,
            max_decompressed_bytes=8_000_000,
            retries=2,
        )
        if redirect_to is None:
            metadata = transport.metadata
            if metadata.status is not FetchStatus.SUCCESS or transport.body is None:
                return RegisteredFetchResult(
                    metadata.status,
                    metadata.status_code,
                    metadata.etag_digest,
                    metadata.last_modified_digest,
                )
            try:
                extraction = extractor(transport.body, salt=salt, max_bytes=8_000_000)
                sanitized_url = sanitize_url(current_url, salt=salt)
            except Exception:
                return RegisteredFetchResult(FetchStatus.EXTRACTOR_ERROR, metadata.status_code)
            return _attest_registered_fetch(
                metadata,
                extraction,
                registry=registry,
                source_id=source.source_id,
                canonical_origin=source.canonical_origin,
                url_path_digest=sanitized_url.path_digest,
                extractor_kind=extractor_kind,
            )
        redirects += 1
        target = urljoin(current_url, redirect_to)
        if redirects > 5 or not _matches_origin(target, source.canonical_origin):
            return RegisteredFetchResult(FetchStatus.DISALLOWED_REDIRECT)
        current_url = target


def _request_with_retries(
    url: str,
    peers: tuple[tuple[int, tuple[Any, ...]], ...],
    *,
    salt: str | bytes,
    timeout_seconds: float,
    max_response_bytes: int,
    max_decompressed_bytes: int,
    retries: int,
) -> tuple[_TransportResult, str | None]:
    parsed = urlsplit(url)
    host = _canonical_host(parsed.hostname)
    if host is None:
        return _TransportResult(FetchResult(FetchStatus.NETWORK_ERROR)), None
    headers = {
        "Accept-Encoding": "identity",
        "Host": host,
        "User-Agent": "esports-data-discovery/1.0",
    }
    path = parsed.path or "/"
    for attempt in range(retries + 1):
        connection = _PinnedHTTPSConnection(
            host, peers[attempt % len(peers)], timeout=timeout_seconds
        )
        try:
            connection.request("GET", path, headers=headers)
            response = connection.getresponse()
            try:
                status = response.status
                if status == 304:
                    return _TransportResult(FetchResult(FetchStatus.NOT_MODIFIED, status)), None
                if status in {301, 302, 303, 307, 308}:
                    return (
                        _TransportResult(FetchResult(FetchStatus.HTTP_ERROR, status)),
                        response.headers.get("Location"),
                    )
                if status == 429 or 500 <= status <= 599:
                    if attempt < retries:
                        time.sleep(min(2.0, 0.25 * (2**attempt)))
                        continue
                    return _TransportResult(FetchResult(FetchStatus.RETRY_EXHAUSTED, status)), None
                if status < 200 or status > 299:
                    return _TransportResult(FetchResult(FetchStatus.HTTP_ERROR, status)), None
                body_status, body = _read_body(response, max_response_bytes, max_decompressed_bytes)
                if body_status is not None:
                    return _TransportResult(FetchResult(body_status, status)), None
                return _TransportResult(
                    FetchResult(
                        FetchStatus.SUCCESS,
                        status,
                        _validator_digest(response.headers.get("ETag"), salt=salt),
                        _validator_digest(response.headers.get("Last-Modified"), salt=salt),
                    ),
                    body,
                ), None
            finally:
                response.close()
        except (TimeoutError, OSError, http.client.HTTPException):
            if attempt < retries:
                time.sleep(min(2.0, 0.25 * (2**attempt)))
                continue
            return _TransportResult(FetchResult(FetchStatus.NETWORK_ERROR)), None
        finally:
            connection.close()
    raise AssertionError("retry loop must return")


def _resolve_global_peers(host: str, port: int) -> tuple[tuple[int, tuple[Any, ...]], ...]:
    try:
        peers = tuple(
            (item[0], item[4])
            for item in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
        )
        if not peers or not all(ipaddress.ip_address(peer[1][0]).is_global for peer in peers):
            return ()
        return peers
    except (OSError, TypeError, ValueError, IndexError):
        return ()


def _matches_origin(value: str, origin: tuple[str, str, int]) -> bool:
    if not isinstance(value, str) or any(ord(character) <= 0x20 for character in value):
        return False
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError:
        return False
    return (
        parsed.scheme.lower() == "https" and parsed.username is None and parsed.password is None
        and not parsed.query and not parsed.fragment and port in {None, 443}
        and _canonical_host(parsed.hostname) == origin[1] and origin[0] == "https" and origin[2] == 443
    )


def _read_body(response: Any, max_response_bytes: int, max_decompressed_bytes: int) -> tuple[FetchStatus | None, bytes | None]:
    raw = response.read(max_response_bytes + 1)
    if len(raw) > max_response_bytes:
        return FetchStatus.RESPONSE_TOO_LARGE, None
    encoding = response.headers.get("Content-Encoding", "").lower().strip()
    if encoding in {"", "identity"}:
        return (None, raw) if len(raw) <= max_decompressed_bytes else (FetchStatus.DECOMPRESSED_TOO_LARGE, None)
    try:
        decoder = zlib.decompressobj(16 + zlib.MAX_WBITS) if encoding == "gzip" else zlib.decompressobj() if encoding == "deflate" else None
        if decoder is None:
            return FetchStatus.HTTP_ERROR, None
        decoded = decoder.decompress(raw, max_decompressed_bytes + 1)
        if len(decoded) <= max_decompressed_bytes:
            decoded += decoder.flush(max_decompressed_bytes + 1 - len(decoded))
        if not decoder.eof:
            return FetchStatus.HTTP_ERROR, None
    except (ValueError, zlib.error):
        return FetchStatus.HTTP_ERROR, None
    return (FetchStatus.DECOMPRESSED_TOO_LARGE, None) if len(decoded) > max_decompressed_bytes else (None, decoded)


def clean_discovery_url(raw_url: str, base_url: str) -> str | None:
    """Resolve a discovered link to a query-free, public HTTP(S) URL."""
    if not isinstance(raw_url, str) or not isinstance(base_url, str):
        return None
    try:
        parsed = urlsplit(urljoin(base_url, raw_url))
    except (TypeError, ValueError):
        return None
    if parsed.username or parsed.password:
        return None
    clean = urlunsplit((parsed.scheme.lower(), parsed.netloc, parsed.path, "", ""))
    return clean if _is_public_http_url(clean) and scan_url(clean).is_clean else None


def safe_title_digest(title: str | None, *, salt: str | bytes) -> str | None:
    """Return only an opaque digest for clean, non-empty external titles."""
    if not isinstance(title, str) or not title or not scan_text(title).is_clean:
        return None
    return salted_digest(title, salt=salt)


def _is_public_http_url(value: str) -> bool:
    if not isinstance(value, str) or any(ord(character) <= 0x20 for character in value):
        return False
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError:
        return False
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or port == 0:
        return False
    host = _canonical_host(parsed.hostname)
    if host is None:
        return False
    try:
        return ipaddress.ip_address(host).is_global
    except ValueError:
        return True


def _canonical_host(host: str | None) -> str | None:
    if not isinstance(host, str):
        return None
    try:
        normalized = host.rstrip(".").encode("idna").decode("ascii").lower()
    except UnicodeError:
        return None
    return normalized if normalized and normalized != "localhost" and "." in normalized else None


def _validator_digest(value: object, *, salt: str | bytes) -> str | None:
    if not isinstance(value, str) or len(value) > 512 or any(not 0x20 <= ord(character) <= 0x7E for character in value):
        return None
    return salted_digest(value, salt=salt)


def _valid_salt(salt: str | bytes) -> bool:
    try:
        salted_digest("fetch-metadata", salt=salt)
    except InvalidExternalValueError:
        return False
    return True