"""Fail-closed freshness and publisher-independence policy controls."""

from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass
from enum import Enum
from hashlib import sha256
import json
import math
from pathlib import Path
from .registry import CORE_SOURCE_PROVENANCE, SourceRecord, SourceRegistry, _validate_registry
from typing import Any, Mapping
import tomllib
from .models import SubjectKind
_REQUIRED_PREDICATES = frozenset({
    "official_status", "founded_year", "team_count", "event_date", "document_text_digest",
})


class FreshnessTier(str, Enum):
    """Maximum acceptable age for a source observation."""

    HOUR_1 = "1h"
    HOURS_6 = "6h"
    HOURS_24 = "24h"
    HOURS_72 = "72h"

    @property
    def maximum_age_hours(self) -> int:
        """Return the tier's inclusive age boundary in hours."""
        return {self.HOUR_1: 1, self.HOURS_6: 6, self.HOURS_24: 24, self.HOURS_72: 72}[self]


@dataclass(frozen=True, slots=True)
class FreshnessPolicy:
    """Named source SLO tiers and their maximum age limits."""

    tiers: Mapping[str, FreshnessTier]
    unknown_allowed: bool = False

    def maximum_age_hours(self, slo_tier: str) -> int | None:
        """Return a known limit; unknown tiers fail closed as ``None``."""
        tier = self.tiers.get(slo_tier)
        return tier.maximum_age_hours if tier else None

    def is_fresh(self, slo_tier: str, age_hours: float) -> bool:
        """Check freshness without permitting unregistered tiers or negative ages."""
        maximum_age = self.maximum_age_hours(slo_tier)
        return age_hours >= 0 and maximum_age is not None and age_hours <= maximum_age


@dataclass(frozen=True, slots=True)
class Publisher:
    """A publisher's control and origin axes for corroboration checks."""

    publisher_id: str
    control_cluster: str
    origin_cluster: str
    def __post_init__(self) -> None:
        if any(type(value) is not str or not value.strip() for value in (
            self.publisher_id, self.control_cluster, self.origin_cluster,
        )):
            raise PolicyValidationError("publisher provenance fields must be non-empty strings")


@dataclass(frozen=True, slots=True)
class PublisherPolicy:
    """Known publishers; unknown publishers never establish independence."""

    publishers: Mapping[str, Publisher]
    unknown_allowed: bool = False

    def are_independent(self, left_id: str, right_id: str) -> bool:
        """Require different publisher-control *and* origin clusters."""
        left = self.publishers.get(left_id)
        right = self.publishers.get(right_id)
        return bool(
            left
            and right
            and left.control_cluster != right.control_cluster
            and left.origin_cluster != right.origin_cluster
        )

@dataclass(frozen=True, slots=True)
class ClaimRequirementPolicy:
    """Required, PII-free predicate/scope-suffix contracts for every subject kind."""

    requirements: Mapping[str, Mapping[str, tuple[str, ...]]]
    unknown_allowed: bool = False



@dataclass(frozen=True, slots=True)
class PolicySnapshot:
    """All policy inputs whose canonical hash controls publication decisions."""

    freshness: FreshnessPolicy
    publishers: PublisherPolicy
    registry: SourceRegistry | None = None
    claims: ClaimRequirementPolicy | None = None


@dataclass(frozen=True, slots=True)
class PolicyChangeImpact:
    """Whether a policy update invalidates prior policy-derived decisions."""

    changed: bool
    requires_revalidation: bool
    changed_sections: tuple[str, ...]
    previous_hash: str
    current_hash: str


class PolicyValidationError(ValueError):
    """Raised when policy TOML is ambiguous or unsafe."""


def load_freshness_policy(path: str | Path) -> FreshnessPolicy:
    """Load four named freshness tiers from TOML."""
    with Path(path).open("rb") as policy_file:
        data = tomllib.load(policy_file)
    raw_tiers = data.get("tier")
    unknown = data.get("unknown", {})
    if not isinstance(raw_tiers, dict) or not isinstance(unknown, dict):
        raise PolicyValidationError("freshness policy requires [tier] and [unknown] tables")
    if unknown.get("allowed") is not False:
        raise PolicyValidationError("unknown freshness tiers must fail closed")
    try:
        tiers = {name: FreshnessTier(value) for name, value in raw_tiers.items()}
    except (TypeError, ValueError) as error:
        raise PolicyValidationError("freshness tiers must use 1h, 6h, 24h, or 72h") from error
    if set(tiers.values()) != set(FreshnessTier):
        raise PolicyValidationError("freshness policy must define 1h, 6h, 24h, and 72h")
    if any(not isinstance(name, str) or not name.strip() for name in tiers):
        raise PolicyValidationError("freshness tier names must be non-empty")
    return FreshnessPolicy(tiers=tiers)


def load_publisher_policy(path: str | Path) -> PublisherPolicy:
    """Load publisher clusters, rejecting unknown-permissive configurations."""
    with Path(path).open("rb") as policy_file:
        data = tomllib.load(policy_file)
    entries = data.get("publisher")
    unknown = data.get("unknown", {})
    if not isinstance(entries, list) or not isinstance(unknown, dict):
        raise PolicyValidationError("publisher policy requires [[publisher]] and [unknown]")
    if unknown.get("allowed") is not False:
        raise PolicyValidationError("unknown publishers must fail closed")
    publishers: dict[str, Publisher] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise PolicyValidationError("publisher entries must be tables")
        try:
            publisher = Publisher(
                publisher_id=_nonempty(entry, "id"),
                control_cluster=_nonempty(entry, "control_cluster"),
                origin_cluster=_nonempty(entry, "origin_cluster"),
            )
        except KeyError as error:
            raise PolicyValidationError(f"publisher missing {error.args[0]}") from error
        if publisher.publisher_id in publishers:
            raise PolicyValidationError("publisher ids must be unique")
        publishers[publisher.publisher_id] = publisher
    if not publishers:
        raise PolicyValidationError("publisher policy requires at least one publisher")
    expected_publishers = {
        source_id: (provenance[1], provenance[2])
        for source_id, provenance in CORE_SOURCE_PROVENANCE.items()
    }
    actual_publishers = {
        publisher_id: (publisher.control_cluster, publisher.origin_cluster)
        for publisher_id, publisher in publishers.items()
    }
    if actual_publishers != expected_publishers:
        raise PolicyValidationError("publisher policy must exactly match approved source provenance")
    return PublisherPolicy(publishers=publishers)

def load_claim_requirement_policy(path: str | Path) -> ClaimRequirementPolicy:
    """Load the complete fail-closed required-claim contract."""
    with Path(path).open("rb") as policy_file:
        data = tomllib.load(policy_file)
    entries = data.get("kind")
    unknown = data.get("unknown", {})
    if (set(data) != {"kind", "unknown"} or not isinstance(entries, list)
            or not isinstance(unknown, dict) or set(unknown) != {"allowed"}):
        raise PolicyValidationError("claims policy requires only [[kind]] and fail-closed [unknown]")
    if unknown["allowed"] is not False:
        raise PolicyValidationError("unknown claim kinds, predicates, and suffixes must fail closed")
    known_kinds = {kind.value for kind in SubjectKind}
    requirements: dict[str, dict[str, tuple[str, ...]]] = {}
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {
            "name", "required_predicates", "authority_scope_suffixes",
        }:
            raise PolicyValidationError("claim kind entries must contain only required fields")
        try:
            kind = _nonempty(entry, "name")
            predicates = entry["required_predicates"]
            suffixes = entry["authority_scope_suffixes"]
        except KeyError as error:
            raise PolicyValidationError(f"claim kind missing {error.args[0]}") from error
        if kind not in known_kinds or kind in requirements:
            raise PolicyValidationError("claim kinds must be known and unique")
        if (not isinstance(predicates, list) or not isinstance(suffixes, list)
                or not predicates or not suffixes
                or any(type(item) is not str or not item.strip() for item in predicates + suffixes)
                or len(predicates) != len(set(predicates)) or len(suffixes) != len(set(suffixes))):
            raise PolicyValidationError("claim predicates and suffixes must be unique non-empty lists")
        if ("official_status" not in predicates or not set(predicates) <= _REQUIRED_PREDICATES
                or set(suffixes) != {kind}):
            raise PolicyValidationError("claims policy must include official_status and known matching scope suffixes")
        requirements[kind] = {predicate: tuple(suffixes) for predicate in predicates}
    if set(requirements) != known_kinds:
        raise PolicyValidationError("claims policy must define every subject kind exactly once")
    return ClaimRequirementPolicy(requirements=requirements)



def canonical_policy_hash(
    policy: PolicySnapshot | FreshnessPolicy | PublisherPolicy | ClaimRequirementPolicy | SourceRegistry | Mapping[str, Any],
) -> str:
    """Return a stable SHA-256 hash of semantically ordered policy content."""
    canonical = json.dumps(
        _normalise(policy),
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return sha256(canonical.encode("utf-8")).hexdigest()


def assess_policy_change(previous: PolicySnapshot, current: PolicySnapshot) -> PolicyChangeImpact:
    """Identify policy sections that require revalidating published decisions."""
    previous_hash = canonical_policy_hash(previous)
    current_hash = canonical_policy_hash(current)
    changed_sections = tuple(
        section
        for section in ("freshness", "publishers", "registry", "claims")
        if _normalise(getattr(previous, section)) != _normalise(getattr(current, section))
    )
    return PolicyChangeImpact(
        changed=bool(changed_sections),
        requires_revalidation=bool(changed_sections),
        changed_sections=changed_sections,
        previous_hash=previous_hash,
        current_hash=current_hash,
    )


def _nonempty(entry: Mapping[str, Any], key: str) -> str:
    value = entry[key]
    if type(value) is not str or not value.strip():
        raise PolicyValidationError(f"publisher {key} must be a non-empty string")
    return value


def _normalise(value: Any) -> Any:
    if isinstance(value, SourceRegistry):
        if type(value.sources) is not tuple or any(type(record) is not SourceRecord for record in value.sources):
            raise PolicyValidationError("registry sources must be a tuple of SourceRecord values")
        try:
            _validate_registry(value.sources)
        except ValueError as error:
            raise PolicyValidationError("registry provenance is invalid") from error
    if isinstance(value, PublisherPolicy):
        if type(value.publishers) is not dict or type(value.unknown_allowed) is not bool:
            raise PolicyValidationError("publisher policy has invalid types")
        if value.unknown_allowed:
            raise PolicyValidationError("unknown publishers must fail closed")
        for publisher_id, publisher in value.publishers.items():
            if type(publisher_id) is not str or publisher_id != publisher.publisher_id or type(publisher) is not Publisher:
                raise PolicyValidationError("publisher policy has invalid provenance")
    if isinstance(value, PolicySnapshot) and value.registry is not None and type(value.registry) is not SourceRegistry:
        raise PolicyValidationError("policy snapshot registry must be a SourceRegistry")
    if isinstance(value, ClaimRequirementPolicy):
        if type(value.requirements) is not dict or type(value.unknown_allowed) is not bool or value.unknown_allowed:
            raise PolicyValidationError("claims policy must fail closed")
        if set(value.requirements) != {kind.value for kind in SubjectKind}:
            raise PolicyValidationError("claims policy must define every subject kind")
        for kind, predicates in value.requirements.items():
            if (type(predicates) is not dict or "official_status" not in predicates
                    or not set(predicates) <= _REQUIRED_PREDICATES):
                raise PolicyValidationError("claims policy has unknown predicates")
            for suffixes in predicates.values():
                if type(suffixes) is not tuple or suffixes != (kind,):
                    raise PolicyValidationError("claims policy has unknown scope suffixes")
    if isinstance(value, PolicySnapshot) and value.claims is not None:
        if type(value.claims) is not ClaimRequirementPolicy:
            raise PolicyValidationError("policy snapshot claims must be a ClaimRequirementPolicy")
        _normalise(value.claims)
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return _normalise(asdict(value))
    if isinstance(value, Mapping):
        if any(type(key) is not str for key in value):
            raise PolicyValidationError("policy mapping keys must be strings")
        return {key: _normalise(item) for key, item in value.items()}
    if isinstance(value, frozenset):
        return sorted(_normalise(item) for item in value)
    if isinstance(value, (tuple, list)):
        return [_normalise(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        raise PolicyValidationError("policy numbers must be finite")
    return value
