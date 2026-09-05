"""Bounded weekly discovery with a durable reviewed-URL ledger.

External document bytes and titles are transient. Persisted candidates contain
only canonical public URLs, provenance IDs, timestamps, and opaque digests.
Nothing in this module can mutate the public site dataset.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from html import unescape
from html.parser import HTMLParser
import http.client
import ipaddress
import json
import os
from pathlib import Path
import re
import socket
import ssl
import tempfile
import tomllib
import unicodedata
from urllib.parse import parse_qsl, quote, unquote, urlencode, urljoin, urlsplit, urlunsplit
from xml.etree import ElementTree

from .pii import scan_text


SCHEMA_VERSION = 1
CANONICALIZATION_VERSION = 1
MAX_DOCUMENT_BYTES = 2_000_000
MAX_REDIRECTS = 4
KEYWORDS = ("e스포츠", "이스포츠", "esports", "e-sports", "e sports")
TRACKING_PARAMETERS = frozenset({
    "fbclid", "gclid", "dclid", "mc_cid", "mc_eid", "referrer",
    "spm", "igshid", "yclid",
})
URL_PATTERN = re.compile(r"https?://[^\s;,)\]]+")
SENSITIVE_QUERY_KEYS = frozenset({
    "address", "addr", "email", "handle", "name", "phone", "student", "tel",
})


class DiscoveryError(RuntimeError):
    """Raised when no trustworthy discovery checkpoint can be completed."""


@dataclass(frozen=True, slots=True)
class Surface:
    source_id: str
    kind: str
    endpoint: str


@dataclass(frozen=True, slots=True)
class DiscoveredLink:
    source_id: str
    url: str
    title_sha256: str | None
    event_sha256: str | None = None


@dataclass(frozen=True, slots=True)
class SurfaceResult:
    source_id: str
    status: str
    links: tuple[DiscoveredLink, ...]


class _HomepageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.anchors: list[tuple[str, str]] = []
        self.feeds: list[str] = []
        self._href: str | None = None
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {key.casefold(): value for key, value in attrs}
        lowered = tag.casefold()
        if lowered == "link":
            rel = (attributes.get("rel") or "").casefold().split()
            media_type = (attributes.get("type") or "").casefold()
            href = attributes.get("href")
            if href and "alternate" in rel and media_type in {
                "application/rss+xml", "application/atom+xml", "application/xml", "text/xml",
            }:
                self.feeds.append(href)
        if lowered == "a" and self._href is None and attributes.get("href"):
            self._href = attributes["href"]
            self._parts = [attributes["title"]] if attributes.get("title") else []

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() == "a" and self._href is not None:
            self.anchors.append((self._href, " ".join(part.strip() for part in self._parts if part.strip())))
            self._href = None
            self._parts = []


def _atomic_json(path: Path, value: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True) + "\n").encode()
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as output:
            output.write(payload)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def canonicalize_url(raw_url: str, base_url: str | None = None) -> str | None:
    """Keep document identity while removing fragments and known tracking data."""
    if not isinstance(raw_url, str) or not raw_url.strip():
        return None
    try:
        parsed = urlsplit(urljoin(base_url or raw_url, unescape(raw_url.strip())))
        host = parsed.hostname.encode("idna").decode("ascii").lower() if parsed.hostname else ""
        port = parsed.port
        decoded_path = unquote(parsed.path or "/", errors="strict")
    except (UnicodeError, ValueError):
        return None
    scheme = parsed.scheme.casefold()
    if scheme != "https" or not host or parsed.username or parsed.password or port not in {None, 443}:
        return None
    path = quote(decoded_path, safe="/%:@!$&'()*+,;=-._~")
    retained = []
    for key, value in parse_qsl(parsed.query, keep_blank_values=True):
        lowered = key.casefold()
        if lowered.startswith("utm_") or lowered in TRACKING_PARAMETERS:
            continue
        if (
            lowered in SENSITIVE_QUERY_KEYS
            or len(key) > 64
            or len(value) > 512
            or not scan_text(key).is_clean
            or not scan_text(value).is_clean
        ):
            return None
        retained.append((key, value))
    query = urlencode(sorted(retained), doseq=True, quote_via=quote)
    canonical = urlunsplit((scheme, host, path, query, ""))
    return canonical if len(canonical) <= 2048 else None


def normalized_title(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return "".join(character for character in normalized if character.isalnum())


def title_digest(value: str | None) -> str | None:
    if not isinstance(value, str) or not value.strip() or not scan_text(value).is_clean:
        return None
    normalized = normalized_title(value)
    return sha256(normalized.encode()).hexdigest() if normalized else None


def event_digest(title: str) -> str | None:
    """Conservative suggestion only: require explicit year, region and institution."""
    year = re.search(r"20[0-9]{2}", title)
    region = re.search(r"서울|부산|대구|인천|광주|대전|울산|세종|경기|강원|충북|충남|전북|전남|경북|경남|제주", title)
    institution = re.search(r"[가-힣]{2,}(?:교육청|학교|대학교|재단|협회)", title)
    event = re.search(r"[가-힣a-zA-Z0-9 ·-]*(?:e스포츠|이스포츠)[가-힣a-zA-Z0-9 ·-]*(?:대회|리그|캠프)", title)
    if not all((year, region, institution, event)): return None
    return title_digest('|'.join(part.group() for part in (year, region, institution, event)))


def relevant(value: str | None, url: str) -> bool:
    haystack = unicodedata.normalize("NFKC", f"{value or ''} {unquote(urlsplit(url).path)}").casefold()
    return any(keyword in haystack for keyword in KEYWORDS)


def _global_peers(host: str) -> tuple[tuple[int, tuple[object, ...]], ...]:
    try:
        peers = tuple((item[0], item[4]) for item in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM))
        if not peers or not all(ipaddress.ip_address(peer[1][0]).is_global for peer in peers):
            return ()
        return peers
    except (OSError, ValueError, IndexError):
        return ()


def _fetch_document(url: str, *, allowed_host: str | None = None) -> bytes:
    current = canonicalize_url(url)
    if current is None:
        raise DiscoveryError("invalid_url")
    for redirect_count in range(MAX_REDIRECTS + 1):
        parsed = urlsplit(current)
        if allowed_host and parsed.hostname != allowed_host:
            raise DiscoveryError("disallowed_origin")
        peers = _global_peers(parsed.hostname or "")
        if not peers:
            raise DiscoveryError("dns_rejected")
        family, address = peers[redirect_count % len(peers)]
        raw_socket = socket.socket(family, socket.SOCK_STREAM)
        connection: http.client.HTTPSConnection | None = None
        try:
            raw_socket.settimeout(12)
            raw_socket.connect(address)
            tls_socket = ssl.create_default_context().wrap_socket(raw_socket, server_hostname=parsed.hostname)
            connection = http.client.HTTPSConnection(parsed.hostname, timeout=12)
            connection.sock = tls_socket
            target = parsed.path or "/"
            if parsed.query:
                target += f"?{parsed.query}"
            connection.request("GET", target, headers={
                "Accept-Encoding": "identity",
                "Host": parsed.hostname,
                "User-Agent": "2026-esports-landscape-discovery/1.0",
            })
            response = connection.getresponse()
            if response.status in {301, 302, 303, 307, 308}:
                location = response.getheader("Location")
                response.close()
                target_url = canonicalize_url(location or "", current)
                if target_url is None:
                    raise DiscoveryError("invalid_redirect")
                if redirect_count == MAX_REDIRECTS:
                    raise DiscoveryError("redirect_limit")
                current = target_url
                continue
            if not 200 <= response.status < 300:
                response.close()
                raise DiscoveryError("http_error")
            body = response.read(MAX_DOCUMENT_BYTES + 1)
            response.close()
            if len(body) > MAX_DOCUMENT_BYTES:
                raise DiscoveryError("response_too_large")
            return body
        except (OSError, ssl.SSLError, http.client.HTTPException, TimeoutError) as error:
            raise DiscoveryError("network_error") from error
        finally:
            if connection is not None:
                connection.close()
            else:
                raw_socket.close()
    raise DiscoveryError("redirect_limit")


def parse_homepage(document: bytes, surface: Surface) -> tuple[tuple[DiscoveredLink, ...], tuple[str, ...]]:
    try:
        source = document.decode("utf-8")
    except UnicodeDecodeError:
        source = document.decode("euc-kr", errors="replace")
    parser = _HomepageParser()
    parser.feed(source)
    parser.close()
    links: dict[str, DiscoveredLink] = {}
    for raw_url, title in parser.anchors:
        canonical = canonicalize_url(raw_url, surface.endpoint)
        if canonical and relevant(title, canonical):
            links[canonical] = DiscoveredLink(surface.source_id, canonical, title_digest(title), event_digest(title))
    origin_host = urlsplit(surface.endpoint).hostname
    feeds = []
    for raw_feed in parser.feeds:
        canonical = canonicalize_url(raw_feed, surface.endpoint)
        if canonical and urlsplit(canonical).hostname == origin_host and canonical not in feeds:
            feeds.append(canonical)
    return tuple(links.values()), tuple(feeds[:3])


def _local_name(tag: object) -> str:
    return tag.rsplit("}", 1)[-1].casefold() if isinstance(tag, str) else ""


def parse_feed(document: bytes, surface: Surface) -> tuple[DiscoveredLink, ...]:
    lowered = document.lower()
    if b"<!doctype" in lowered or b"<!entity" in lowered:
        raise DiscoveryError("unsafe_xml")
    try:
        root = ElementTree.fromstring(document)
    except ElementTree.ParseError as error:
        raise DiscoveryError("malformed_feed") from error
    links: dict[str, DiscoveredLink] = {}
    for node in root.iter():
        if _local_name(node.tag) not in {"item", "entry"}:
            continue
        title = next((child.text.strip() for child in node if _local_name(child.tag) == "title" and child.text), "")
        raw_url = None
        for child in node:
            if _local_name(child.tag) != "link":
                continue
            raw_url = child.get("href") or (child.text.strip() if child.text else None)
            if raw_url:
                break
        canonical = canonicalize_url(raw_url or "", surface.endpoint)
        if canonical and relevant(title, canonical):
            links[canonical] = DiscoveredLink(surface.source_id, canonical, title_digest(title), event_digest(title))
    return tuple(links.values())


def load_surfaces(core_sources: Path, discovery_sources: Path) -> tuple[Surface, ...]:
    core = tomllib.loads(core_sources.read_text(encoding="utf-8"))
    discovery = tomllib.loads(discovery_sources.read_text(encoding="utf-8"))
    raw_surfaces = [Surface(row["id"], "homepage", row["endpoint"]) for row in core.get("source", []) if row.get("active") is True]
    raw_surfaces.extend(Surface(row["id"], row["kind"], row["endpoint"]) for row in discovery.get("source", []))
    surfaces = []
    for surface in raw_surfaces:
        endpoint = canonicalize_url(surface.endpoint)
        if surface.kind not in {"homepage", "rss", "sitemap"} or endpoint is None:
            raise DiscoveryError("invalid_surface")
        surfaces.append(Surface(surface.source_id, surface.kind, endpoint))
    if len({surface.source_id for surface in surfaces}) != len(surfaces):
        raise DiscoveryError("duplicate_source_id")
    return tuple(surfaces)


def scan_surface(surface: Surface) -> SurfaceResult:
    try:
        document = _fetch_document(surface.endpoint, allowed_host=urlsplit(surface.endpoint).hostname)
        if surface.kind == "sitemap":
            if b"<!doctype" in document.lower() or b"<!entity" in document.lower(): raise DiscoveryError("unsafe_xml")
            try: root = ElementTree.fromstring(document)
            except ElementTree.ParseError as error: raise DiscoveryError("malformed_sitemap") from error
            links = []
            for node in root.iter():
                if _local_name(node.tag) == "loc":
                    url = canonicalize_url(node.text or "", surface.endpoint)
                    if url and relevant(None,url): links.append(DiscoveredLink(surface.source_id,url,None))
            return SurfaceResult(surface.source_id,"success",tuple(links))
        if surface.kind == "rss":
            return SurfaceResult(surface.source_id, "success", parse_feed(document, surface))
        links, feeds = parse_homepage(document, surface)
        combined = {link.url: link for link in links}
        for feed_url in feeds:
            try:
                for link in parse_feed(_fetch_document(feed_url, allowed_host=urlsplit(surface.endpoint).hostname), surface):
                    combined[link.url] = link
            except DiscoveryError:
                continue
        return SurfaceResult(surface.source_id, "success", tuple(combined.values()))
    except DiscoveryError:
        return SurfaceResult(surface.source_id, "failed", ())


def _empty_seen() -> dict[str, object]:
    return {"canonicalization_version": CANONICALIZATION_VERSION, "items": [], "schema_version": SCHEMA_VERSION}


def _empty_candidates() -> dict[str, object]:
    return {"candidates": [], "schema_version": SCHEMA_VERSION}


def load_document(path: Path, empty: dict[str, object]) -> dict[str, object]:
    if not path.exists():
        return empty
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("schema_version") != SCHEMA_VERSION:
        raise DiscoveryError("invalid_state")
    return value


def bootstrap_seen(site_path: Path, seen: dict[str, object], *, imported_at: str) -> int:
    site = json.loads(site_path.read_text(encoding="utf-8"))
    by_url = {item["url_sha256"]: item for item in seen["items"]}
    added = 0
    for entry in site.get("entries", []):
        entry_title = title_digest(entry.get("name"))
        for raw_url in URL_PATTERN.findall(entry.get("source", "")):
            canonical = canonicalize_url(raw_url)
            if canonical is None:
                continue
            url_hash = sha256(canonical.encode()).hexdigest()
            item = by_url.get(url_hash)
            if item is None:
                item = {
                    "canonical_url": canonical,
                    "decision": "accepted",
                    "entry_ids": [],
                    "first_seen_at": imported_at,
                    "title_sha256": [],
                    "url_sha256": url_hash,
                }
                by_url[url_hash] = item
                added += 1
            if entry["id"] not in item["entry_ids"]:
                item["entry_ids"].append(entry["id"])
            if entry_title and entry_title not in item["title_sha256"]:
                item["title_sha256"].append(entry_title)
    for item in by_url.values():
        item["entry_ids"].sort()
        item["title_sha256"].sort()
    seen["items"] = sorted(by_url.values(), key=lambda item: item["canonical_url"])
    return added


def merge_discovery(
    seen: dict[str, object], candidates: dict[str, object], links: tuple[DiscoveredLink, ...], *, discovered_at: str,
) -> dict[str, int]:
    seen_by_hash = {item["url_sha256"]: item for item in seen["items"]}
    candidates_by_id = {item["id"]: item for item in candidates["candidates"]}
    known_titles = {digest for item in seen["items"] for digest in item.get("title_sha256", [])}
    discovered = duplicates = new = 0
    for link in sorted(links, key=lambda item: (item.url, item.source_id)):
        discovered += 1
        url_hash = sha256(link.url.encode()).hexdigest()
        if url_hash in seen_by_hash:
            duplicates += 1
            continue
        candidate_id = f"candidate-{url_hash[:16]}"
        possible_duplicate = link.title_sha256 in known_titles if link.title_sha256 else False
        candidates_by_id[candidate_id] = {
            "canonical_url": link.url,
            "discovered_at": discovered_at,
            "discovered_via": link.source_id,
            "id": candidate_id,
            "possible_duplicate": possible_duplicate,
            "event_sha256": link.event_sha256,
            "status": "needs_review",
            "title_sha256": link.title_sha256,
            "url_sha256": url_hash,
        }
        seen_by_hash[url_hash] = {
            "canonical_url": link.url,
            "decision": "needs_review",
            "entry_ids": [],
            "first_seen_at": discovered_at,
            "title_sha256": [link.title_sha256] if link.title_sha256 else [],
            "url_sha256": url_hash,
        }
        if link.title_sha256:
            known_titles.add(link.title_sha256)
        new += 1
    seen["items"] = sorted(seen_by_hash.values(), key=lambda item: item["canonical_url"])
    candidates["candidates"] = sorted(candidates_by_id.values(), key=lambda item: item["id"])
    return {"discovered": discovered, "duplicates": duplicates, "new_candidates": new}


def run(args: argparse.Namespace) -> dict[str, object]:
    now = datetime.fromisoformat(args.now.replace("Z", "+00:00")) if args.now else datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise DiscoveryError("invalid_now")
    date = now.astimezone(timezone.utc).date().isoformat()
    seen_path = Path(args.seen)
    candidates_path = Path(args.candidates)
    seen = load_document(seen_path, _empty_seen())
    candidates = load_document(candidates_path, _empty_candidates())
    bootstrapped = bootstrap_seen(Path(args.site), seen, imported_at=args.baseline_date)
    if args.bootstrap_only:
        _atomic_json(seen_path, seen)
        _atomic_json(candidates_path, candidates)
        return {"bootstrapped_urls": bootstrapped, "new_candidates": 0, "successful_surfaces": 0, "failed_surfaces": 0}
    surfaces = load_surfaces(Path(args.core_sources), Path(args.discovery_sources))
    results: list[SurfaceResult] = []
    with ThreadPoolExecutor(max_workers=min(args.workers, len(surfaces))) as executor:
        futures = {executor.submit(scan_surface, surface): surface for surface in surfaces}
        for future in as_completed(futures):
            results.append(future.result())
    successful = [result for result in results if result.status == "success"]
    if not successful:
        raise DiscoveryError("zero_successful_surfaces")
    links = tuple(link for result in successful for link in result.links)
    counts = merge_discovery(seen, candidates, links, discovered_at=date)
    if counts["new_candidates"] or bootstrapped:
        _atomic_json(seen_path, seen)
        _atomic_json(candidates_path, candidates)
    report = {
        "surface_results": [{"source_id":r.source_id,"status":r.status,"candidate_urls":len(r.links)} for r in sorted(results,key=lambda r:r.source_id)],
        "event_groups": len({c.get("event_sha256") for c in candidates["candidates"] if c.get("event_sha256")}),
        **counts,
        "bootstrapped_urls": bootstrapped,
        "failed_surfaces": len(results) - len(successful),
        "run_at": now.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "successful_surfaces": len(successful),
        "total_surfaces": len(results),
    }
    if args.report:
        _atomic_json(Path(args.report), report)
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Discover new school-esports source candidates")
    parser.add_argument("--site", default="data/site.v3.json")
    parser.add_argument("--seen", default="data/discovery/seen.v1.json")
    parser.add_argument("--candidates", default="data/discovery/candidates.v1.json")
    parser.add_argument("--core-sources", default="config/sources.toml")
    parser.add_argument("--discovery-sources", default="config/discovery-sources.toml")
    parser.add_argument("--baseline-date", default="2026-07-19")
    parser.add_argument("--now")
    parser.add_argument("--report")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--bootstrap-only", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        args = build_parser().parse_args(argv)
        if args.workers < 1 or args.workers > 8:
            raise DiscoveryError("invalid_workers")
        print(json.dumps(run(args), ensure_ascii=False, sort_keys=True))
        return 0
    except (DiscoveryError, OSError, ValueError, json.JSONDecodeError):
        print(json.dumps({"outcome": "blocked", "reason": "discovery_failed"}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
