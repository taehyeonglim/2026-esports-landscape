"""Loading and validation for the public-source control-plane registry."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Iterable, Mapping
from urllib.parse import urlsplit
import tomllib

from .pii import scan_text, scan_url


class SourceTier(str, Enum):
    """Registry tiers with distinct operational guarantees."""

    CORE = "core"
    DISCOVERY = "discovery"


class CheckpointResult(str, Enum):
    """Terminal outcomes for a scheduled source checkpoint."""

    SUCCESS = "success"
    CANCELLED = "cancelled"
    DROPPED = "dropped"
    TIMEOUT = "timeout"
    FORBIDDEN = "forbidden"
    BLOCKED = "blocked"
    EMPTY_PARSE = "empty_parse"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class SourceRecord:
    """A public source that is permitted to enter the collection pipeline."""

    source_id: str
    name: str
    tier: SourceTier
    adapter: str
    access_basis: str
    owner: str
    slo_tier: str
    active: bool
    endpoint: str
    publisher_id: str
    control_cluster: str
    origin_cluster: str
    authority_scopes: frozenset[str]
    canonical_origin: tuple[str, str, int]
    approval_reason: str | None = None
    denominator_changed: bool = False

    def __post_init__(self) -> None:
        if (
            any(
                type(value) is not str or not value.strip()
                for value in (
                    self.source_id, self.name, self.adapter, self.access_basis, self.owner,
                    self.slo_tier, self.endpoint, self.publisher_id, self.control_cluster,
                    self.origin_cluster,
                )
            )
            or type(self.active) is not bool
            or type(self.denominator_changed) is not bool
            or type(self.authority_scopes) is not frozenset
            or not self.authority_scopes
            or any(type(scope) is not str or not scope.strip() for scope in self.authority_scopes)
            or type(self.canonical_origin) is not tuple
            or len(self.canonical_origin) != 3
        ):
            raise RegistryValidationError("source provenance fields have invalid types")
        scheme, host, port = self.canonical_origin
        if type(scheme) is not str or type(host) is not str or type(port) is not int:
            raise RegistryValidationError("source canonical_origin must be (str, str, int)")
        if scheme != "https" or not host or host != host.encode("idna").decode("ascii").lower() or port != 443:
            raise RegistryValidationError("source canonical_origin must be canonical HTTPS on port 443")


@dataclass(frozen=True, slots=True)
class SourceRegistry:
    """Validated registry restricted to the compiled 18-source core allowlist.

    Discovery/non-core provenance requires a future explicit source-controlled
    allowlist; ``approval_reason`` alone never authorizes it.
    """

    sources: tuple[SourceRecord, ...]

    def __post_init__(self) -> None:
        if type(self.sources) is not tuple or any(
            type(source) is not SourceRecord for source in self.sources
        ):
            raise RegistryValidationError("registry sources must be SourceRecord tuple")
        _validate_registry(self.sources)

    def by_id(self, source_id: str) -> SourceRecord:
        """Return one configured source or raise ``KeyError``."""
        return {source.source_id: source for source in self.sources}[source_id]
    def active_by_id(self, source_id: str) -> SourceRecord:
        """Return one active configured source or raise ``KeyError``."""
        source = self.by_id(source_id)
        if not source.active:
            raise KeyError(source_id)
        return source

    @property
    def active_core_sources(self) -> tuple[SourceRecord, ...]:
        """Return active core sources that define rolling coverage."""
        return tuple(source for source in self.sources if source.active and source.tier is SourceTier.CORE)


class RegistryValidationError(ValueError):
    """Raised when a registry cannot safely define collection behavior."""


CORE_SOURCE_IDS = frozenset(
    {
        "moe",
        "seoul",
        "busan",
        "daegu",
        "incheon",
        "gwangju",
        "daejeon",
        "ulsan",
        "sejong",
        "gyeonggi",
        "gangwon",
        "chungbuk",
        "chungnam",
        "jeonbuk",
        "jeonnam",
        "gyeongbuk",
        "gyeongnam",
        "jeju",
    }
)
SLO_TIER_NAMES = frozenset({"realtime", "priority", "standard", "archive"})
ADAPTER_NAMES = frozenset({"official_website", "public_api"})
ACCESS_BASES = frozenset({"official_public_website", "official_open_data_api"})
CORE_PUBLIC_HOSTS = {
    "moe": "www.moe.go.kr",
    "seoul": "www.sen.go.kr",
    "busan": "www.pen.go.kr",
    "daegu": "www.dge.go.kr",
    "incheon": "www.ice.go.kr",
    "gwangju": "www.gen.go.kr",
    "daejeon": "www.dje.go.kr",
    "ulsan": "www.use.go.kr",
    "sejong": "www.sje.go.kr",
    "gyeonggi": "www.goe.go.kr",
    "gangwon": "www.gwe.go.kr",
    "chungbuk": "www.cbe.go.kr",
    "chungnam": "www.cne.go.kr",
    "jeonbuk": "www.jbe.go.kr",
    "jeonnam": "www.jne.go.kr",
    "gyeongbuk": "www.gbe.go.kr",
    "gyeongnam": "www.gne.go.kr",
    "jeju": "www.jje.go.kr",
}
CORE_SOURCE_PROVENANCE = {
    "moe": ("moe", "moe-national-control", "moe-public-origin", frozenset({"national:program", "national:organization"})),
    "seoul": ("seoul", "seoul-education-control", "seoul-public-origin", frozenset({"seoul:school", "seoul:program"})),
    "busan": ("busan", "busan-education-control", "busan-public-origin", frozenset({"busan:school", "busan:program"})),
    "daegu": ("daegu", "daegu-education-control", "daegu-public-origin", frozenset({"daegu:school", "daegu:program"})),
    "incheon": ("incheon", "incheon-education-control", "incheon-public-origin", frozenset({"incheon:school", "incheon:program"})),
    "gwangju": ("gwangju", "gwangju-education-control", "gwangju-public-origin", frozenset({"gwangju:school", "gwangju:program"})),
    "daejeon": ("daejeon", "daejeon-education-control", "daejeon-public-origin", frozenset({"daejeon:school", "daejeon:program"})),
    "ulsan": ("ulsan", "ulsan-education-control", "ulsan-public-origin", frozenset({"ulsan:school", "ulsan:program"})),
    "sejong": ("sejong", "sejong-education-control", "sejong-public-origin", frozenset({"sejong:school", "sejong:program"})),
    "gyeonggi": ("gyeonggi", "gyeonggi-education-control", "gyeonggi-public-origin", frozenset({"gyeonggi:school", "gyeonggi:program"})),
    "gangwon": ("gangwon", "gangwon-education-control", "gangwon-public-origin", frozenset({"gangwon:school", "gangwon:program"})),
    "chungbuk": ("chungbuk", "chungbuk-education-control", "chungbuk-public-origin", frozenset({"chungbuk:school", "chungbuk:program"})),
    "chungnam": ("chungnam", "chungnam-education-control", "chungnam-public-origin", frozenset({"chungnam:school", "chungnam:program"})),
    "jeonbuk": ("jeonbuk", "jeonbuk-education-control", "jeonbuk-public-origin", frozenset({"jeonbuk:school", "jeonbuk:program"})),
    "jeonnam": ("jeonnam", "jeonnam-education-control", "jeonnam-public-origin", frozenset({"jeonnam:school", "jeonnam:program"})),
    "gyeongbuk": ("gyeongbuk", "gyeongbuk-education-control", "gyeongbuk-public-origin", frozenset({"gyeongbuk:school", "gyeongbuk:program"})),
    "gyeongnam": ("gyeongnam", "gyeongnam-education-control", "gyeongnam-public-origin", frozenset({"gyeongnam:school", "gyeongnam:program"})),
    "jeju": ("jeju", "jeju-education-control", "jeju-public-origin", frozenset({"jeju:school", "jeju:program"})),
}




def load_source_registry(path: str | Path) -> SourceRegistry:
    """Load a TOML registry and reject incomplete, private, or unapproved entries."""
    with Path(path).open("rb") as source_file:
        data = tomllib.load(source_file)
    entries = data.get("source")
    unknown = data.get("unknown", {})
    if not isinstance(entries, list) or not isinstance(unknown, dict):
        raise RegistryValidationError("registry must contain [[source]] entries and [unknown]")
    if unknown.get("allowed") is not False:
        raise RegistryValidationError("unknown sources must fail closed")

    records = tuple(_parse_source(entry) for entry in entries)
    _validate_registry(records)
    return SourceRegistry(records)


def checkpoint_succeeded(
    *,
    result: CheckpointResult | str,
    http_status: int | None,
    parser_invariant: bool,
) -> bool:
    """Return true only for a 200/304 response satisfying its parser invariant."""
    try:
        normalized_result = CheckpointResult(result)
    except ValueError:
        return False
    return (
        normalized_result is CheckpointResult.SUCCESS
        and http_status in {200, 304}
        and parser_invariant
    )


def rolling_due_coverage(
    checkpoints: Mapping[str, Iterable[bool]],
    registry: SourceRegistry,
    *,
    minimum_samples_per_source: int = 1,
) -> float | None:
    """Compute equal-weight source coverage for the rolling due-checkpoint window.

    Every active core source must have at least ``minimum_samples_per_source``
    due checkpoints.  Coverage is the arithmetic mean of those per-source
    success rates, so high-volume sources receive no extra weight. ``None``
    means that the rolling window is incomplete and must fail closed.
    """
    if minimum_samples_per_source < 1:
        raise ValueError("minimum_samples_per_source must be at least 1")

    source_coverages: list[float] = []
    for source in registry.active_core_sources:
        samples = tuple(checkpoints.get(source.source_id, ()))
        if not all(isinstance(sample, bool) for sample in samples):
            raise ValueError("checkpoint samples must be booleans")
        if len(samples) < minimum_samples_per_source:
            return None
        source_coverages.append(sum(samples) / len(samples))
    return None if not source_coverages else sum(source_coverages) / len(source_coverages)


def meets_coverage_target(
    checkpoints: Mapping[str, Iterable[bool]],
    registry: SourceRegistry,
    *,
    target: float = 0.99,
    minimum_samples_per_source: int = 1,
) -> bool:
    """Return whether a measured rolling coverage meets the inclusive target."""
    coverage = rolling_due_coverage(
        checkpoints, registry, minimum_samples_per_source=minimum_samples_per_source
    )
    return coverage is not None and coverage >= target


def _parse_source(entry: Any) -> SourceRecord:
    if not isinstance(entry, dict):
        raise RegistryValidationError("each source entry must be a TOML table")
    required = (
        "id", "name", "tier", "adapter", "access_basis", "owner", "slo_tier", "active",
        "endpoint", "publisher_id", "control_cluster", "origin_cluster", "authority_scopes",
    )
    missing = [key for key in required if key not in entry]
    if missing:
        raise RegistryValidationError(f"source missing required keys: {', '.join(missing)}")
    text_keys = tuple(key for key in required if key not in {"active", "authority_scopes"})
    if not all(type(entry[key]) is str and entry[key].strip() for key in text_keys):
        raise RegistryValidationError("source text fields must be non-empty strings")
    if type(entry["active"]) is not bool:
        raise RegistryValidationError("source active must be boolean")
    if type(entry.get("denominator_changed", False)) is not bool:
        raise RegistryValidationError("source denominator_changed must be boolean")
    raw_scopes = entry["authority_scopes"]
    if (
        type(raw_scopes) is not list
        or not raw_scopes
        or any(type(scope) is not str or not scope.strip() for scope in raw_scopes)
    ):
        raise RegistryValidationError("source authority_scopes must be a non-empty string array")
    approval_reason = entry.get("approval_reason")
    if approval_reason is not None and (type(approval_reason) is not str or not approval_reason.strip()):
        raise RegistryValidationError("approval_reason must be a non-empty string when provided")
    try:
        tier = SourceTier(entry["tier"])
    except ValueError as error:
        raise RegistryValidationError(f"invalid source tier: {entry['tier']}") from error
    return SourceRecord(
        source_id=entry["id"], name=entry["name"], tier=tier, adapter=entry["adapter"],
        access_basis=entry["access_basis"], owner=entry["owner"], slo_tier=entry["slo_tier"],
        active=entry["active"], endpoint=entry["endpoint"], publisher_id=entry["publisher_id"],
        control_cluster=entry["control_cluster"], origin_cluster=entry["origin_cluster"],
        authority_scopes=frozenset(raw_scopes), canonical_origin=_canonical_origin(entry["endpoint"]),
        approval_reason=approval_reason, denominator_changed=entry.get("denominator_changed", False),
    )


def _canonical_origin(endpoint: str) -> tuple[str, str, int]:
    parsed = urlsplit(endpoint)
    try:
        port = parsed.port
    except ValueError as error:
        raise RegistryValidationError("source endpoint has invalid port") from error
    if (
        parsed.scheme != "https"
        or not parsed.netloc
        or parsed.username
        or "@" in parsed.netloc
        or parsed.password
        or parsed.query
        or parsed.fragment
        or port not in {None, 443}
        or not parsed.hostname
    ):
        raise RegistryValidationError("source endpoint must be HTTPS without credentials, query, fragment, or nondefault port")
    try:
        host = parsed.hostname.encode("idna").decode("ascii").lower()
    except UnicodeError as error:
        raise RegistryValidationError("source endpoint host must be IDNA canonicalizable") from error
    return ("https", host, 443)


def _validate_registry(records: tuple[SourceRecord, ...]) -> None:
    source_ids = [record.source_id for record in records]
    if len(source_ids) != len(set(source_ids)):
        raise RegistryValidationError("source ids must be unique")
    if len(records) != len(CORE_SOURCE_IDS) or any(
        record.tier is not SourceTier.CORE for record in records
    ):
        raise RegistryValidationError("only the compiled 18-source core allowlist is permitted")
    core_ids = set(source_ids)
    if core_ids != CORE_SOURCE_IDS:
        raise RegistryValidationError("core registry must contain the ministry and all 17 provincial offices")
    invalid_adapters = {record.adapter for record in records} - ADAPTER_NAMES
    if invalid_adapters:
        raise RegistryValidationError(f"unsupported source adapter: {sorted(invalid_adapters)!r}")
    invalid_access_bases = {record.access_basis for record in records} - ACCESS_BASES
    if invalid_access_bases:
        raise RegistryValidationError(f"unsupported access basis: {sorted(invalid_access_bases)!r}")
    invalid_slo_tiers = {record.slo_tier for record in records} - SLO_TIER_NAMES
    if invalid_slo_tiers:
        raise RegistryValidationError(f"unsupported SLO tier: {sorted(invalid_slo_tiers)!r}")
    for record in records:
        if (not record.active or record.denominator_changed) and not record.approval_reason:
            raise RegistryValidationError("inactive sources and denominator changes require approval_reason")
        if record.canonical_origin != _canonical_origin(record.endpoint):
            raise RegistryValidationError(f"source {record.source_id} canonical origin does not match endpoint")
        if record.tier is SourceTier.CORE:
            expected = CORE_SOURCE_PROVENANCE[record.source_id]
            provenance = (
                record.publisher_id, record.control_cluster, record.origin_cluster, record.authority_scopes,
            )
            if provenance != expected:
                raise RegistryValidationError(f"core source {record.source_id} has unapproved provenance")
            if record.canonical_origin[1] != CORE_PUBLIC_HOSTS[record.source_id]:
                raise RegistryValidationError(f"core source {record.source_id} must use its official public host")
        if not scan_url(record.endpoint).is_clean or not scan_text(
            f"{record.name} {record.owner} {record.access_basis}"
        ).is_clean:
            raise RegistryValidationError(f"source {record.source_id} contains disallowed PII")
