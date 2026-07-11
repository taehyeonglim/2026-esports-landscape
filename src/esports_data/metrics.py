"""PII-free operational metric aggregation and JSON reporting."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from typing import Any, Mapping

from .quality import GateReport


@dataclass(frozen=True, slots=True)
class MetricsReport:
    """Aggregate operational health only; records and personal fields are excluded."""

    coverage: Mapping[str, float | int | None]
    slo: Mapping[str, int | float]
    queue: Mapping[str, int]
    budget: Mapping[str, int | str]
    gate: Mapping[str, int | str]
    quarantine: Mapping[str, int]
    rollback: Mapping[str, int]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.as_dict(), allow_nan=False, ensure_ascii=True, separators=(",", ":"), sort_keys=True)


def aggregate_metrics(
    *,
    due_checkpoints: int,
    successful_checkpoints: int,
    overdue_sources: int,
    slo_due: int,
    slo_met: int,
    queue_pending: int,
    queue_failed: int,
    budget_status: str,
    budget_remaining: int,
    gate_report: GateReport,
    quarantined: int,
    rollback_count: int,
) -> MetricsReport:
    """Build a validated aggregate report without accepting raw record payloads."""
    counts = {
        "due_checkpoints": due_checkpoints,
        "successful_checkpoints": successful_checkpoints,
        "overdue_sources": overdue_sources,
        "slo_due": slo_due,
        "slo_met": slo_met,
        "queue_pending": queue_pending,
        "queue_failed": queue_failed,
        "budget_remaining": budget_remaining,
        "quarantined": quarantined,
        "rollback_count": rollback_count,
    }
    if any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in counts.values()):
        raise ValueError("metric counts must be non-negative integers")
    if successful_checkpoints > due_checkpoints or slo_met > slo_due:
        raise ValueError("successful measurements cannot exceed their denominators")
    if budget_status not in {"pass", "soft", "hard"}:
        raise ValueError("budget_status must be pass, soft, or hard")
    return MetricsReport(
        coverage={
            "due_checkpoints": due_checkpoints,
            "successful_checkpoints": successful_checkpoints,
            "ratio": _ratio(successful_checkpoints, due_checkpoints),
            "overdue_sources": overdue_sources,
        },
        slo={"due": slo_due, "met": slo_met, "ratio": _ratio(slo_met, slo_due)},
        queue={"pending": queue_pending, "failed": queue_failed},
        budget={"status": budget_status, "remaining": budget_remaining},
        gate={"state": gate_report.state.value, "failed_checks": sum(not check.passed for check in gate_report.checks)},
        quarantine={"count": quarantined},
        rollback={"count": rollback_count},
    )


def metrics_json(report: MetricsReport) -> str:
    """Serialize an aggregate report as canonical, PII-free JSON."""
    return report.to_json()


def _ratio(numerator: int, denominator: int) -> float | None:
    return None if denominator == 0 else numerator / denominator
