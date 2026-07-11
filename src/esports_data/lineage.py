"""Fail-closed lineage checks for corroborating public evidence.

Independence requires both a different editorial/control cluster and a different
original-evidence cluster.  A different URL alone never establishes either fact.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from hashlib import sha256
import json
from itertools import combinations
from typing import Iterable

from .policy import PublisherPolicy


class AxisRelation(str, Enum):
    """The comparison result for one lineage axis."""

    DIFFERENT = "different"
    SAME = "same"
    UNKNOWN = "unknown"
    MISSING = "missing"


class LineageReasonCode(str, Enum):
    """Explicit, non-permissive reason codes for lineage outcomes."""

    INDEPENDENT = "independent"
    CONTROL_SAME = "control_same"
    ORIGIN_SAME = "origin_same"
    CONTROL_UNKNOWN = "control_unknown"
    ORIGIN_UNKNOWN = "origin_unknown"
    CONTROL_MISSING = "control_missing"
    ORIGIN_MISSING = "origin_missing"


@dataclass(frozen=True, slots=True)
class EvidenceLineage:
    """The publisher and original-evidence identities behind one observation.

    ``origin_publisher_id`` must name the organization that produced the original
    evidence, not an outlet which merely republished it.  It is intentionally
    separate from ``publisher_id`` so syndicated press releases remain one origin.
    """

    evidence_id: str
    publisher_id: str | None
    origin_publisher_id: str | None
    url: str


@dataclass(frozen=True, slots=True)
class LineageAssessment:
    """Pairwise control/origin assessment; only two DIFFERENT axes are independent."""

    left_evidence_id: str
    right_evidence_id: str
    control: AxisRelation
    origin: AxisRelation
    independent: bool
    reason_code: LineageReasonCode


@dataclass(frozen=True, slots=True)
class EvidenceSetAssessment:
    """The pairwise lineage results for one canonical evidence set."""

    evidence_set_hash: str
    assessments: tuple[LineageAssessment, ...]

    @property
    def has_independent_pair(self) -> bool:
        return any(assessment.independent for assessment in self.assessments)

    @property
    def independent_pair_count(self) -> int:
        return sum(assessment.independent for assessment in self.assessments)


def canonical_evidence_set_hash(evidence: Iterable[EvidenceLineage]) -> str:
    """Hash semantic evidence lineage in a URL-order-independent canonical form."""
    entries = tuple(evidence)
    _validate_evidence(entries)
    payload = [asdict(item) for item in sorted(entries, key=_evidence_sort_key)]
    canonical = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return sha256(canonical.encode("utf-8")).hexdigest()


def assess_lineage(
    left: EvidenceLineage, right: EvidenceLineage, publisher_policy: PublisherPolicy
) -> LineageAssessment:
    """Assess two observations, treating absent or unregistered identities as unsafe."""
    _validate_evidence((left, right))
    control = _axis_relation(left.publisher_id, right.publisher_id, publisher_policy, "control_cluster")
    origin = _axis_relation(
        left.origin_publisher_id, right.origin_publisher_id, publisher_policy, "origin_cluster"
    )
    independent = control is AxisRelation.DIFFERENT and origin is AxisRelation.DIFFERENT
    return LineageAssessment(
        left_evidence_id=left.evidence_id,
        right_evidence_id=right.evidence_id,
        control=control,
        origin=origin,
        independent=independent,
        reason_code=_reason_code(control, origin),
    )


def assess_evidence_set(
    evidence: Iterable[EvidenceLineage], publisher_policy: PublisherPolicy
) -> EvidenceSetAssessment:
    """Assess every pair in a canonical evidence set without counting URL diversity."""
    entries = tuple(evidence)
    return EvidenceSetAssessment(
        evidence_set_hash=canonical_evidence_set_hash(entries),
        assessments=tuple(assess_lineage(left, right, publisher_policy) for left, right in combinations(entries, 2)),
    )


def _axis_relation(
    left_id: str | None, right_id: str | None, policy: PublisherPolicy, cluster_field: str
) -> AxisRelation:
    if left_id is None or right_id is None:
        return AxisRelation.MISSING
    left = policy.publishers.get(left_id)
    right = policy.publishers.get(right_id)
    if left is None or right is None:
        return AxisRelation.UNKNOWN
    left_cluster = getattr(left, cluster_field, None)
    right_cluster = getattr(right, cluster_field, None)
    if not all(isinstance(cluster, str) and cluster.strip() for cluster in (left_cluster, right_cluster)):
        return AxisRelation.UNKNOWN
    return AxisRelation.SAME if left_cluster == right_cluster else AxisRelation.DIFFERENT


def _reason_code(control: AxisRelation, origin: AxisRelation) -> LineageReasonCode:
    if control is AxisRelation.MISSING:
        return LineageReasonCode.CONTROL_MISSING
    if origin is AxisRelation.MISSING:
        return LineageReasonCode.ORIGIN_MISSING
    if control is AxisRelation.UNKNOWN:
        return LineageReasonCode.CONTROL_UNKNOWN
    if origin is AxisRelation.UNKNOWN:
        return LineageReasonCode.ORIGIN_UNKNOWN
    if control is AxisRelation.SAME:
        return LineageReasonCode.CONTROL_SAME
    if origin is AxisRelation.SAME:
        return LineageReasonCode.ORIGIN_SAME
    return LineageReasonCode.INDEPENDENT


def _validate_evidence(evidence: tuple[EvidenceLineage, ...]) -> None:
    seen: set[str] = set()
    for item in evidence:
        if not isinstance(item, EvidenceLineage):
            raise TypeError("evidence entries must be EvidenceLineage instances")
        if not all(isinstance(value, str) and value.strip() for value in (item.evidence_id, item.url)):
            raise ValueError("evidence_id and url must be non-empty strings")
        if item.evidence_id in seen:
            raise ValueError("evidence ids must be unique within an evidence set")
        seen.add(item.evidence_id)
        for publisher_id in (item.publisher_id, item.origin_publisher_id):
            if publisher_id is not None and (
                not isinstance(publisher_id, str) or not publisher_id.strip()
            ):
                raise ValueError("publisher ids must be non-empty strings when provided")


def _evidence_sort_key(item: EvidenceLineage) -> tuple[str, str, str, str]:
    return (item.evidence_id, item.publisher_id or "", item.origin_publisher_id or "", item.url)
