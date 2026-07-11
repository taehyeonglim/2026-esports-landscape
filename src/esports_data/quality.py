"""Fail-closed publication quality gate."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Mapping

from .models import BudgetStatus

CORE_COVERAGE_MINIMUM = 0.99
QUALITY_FIELDS_MINIMUM = 0.98
GATE_CHECK_NAMES = (
    "core_coverage",
    "false_publications",
    "automatic_mismerges",
    "schema_required_field_coverage",
    "quality_field_coverage",
    "schema_valid",
    "references_valid",
    "checksums_valid",
    "pii_findings",
    "overdue_count",
    "stop_requested",
    "budget_status",
)


class GateState(str, Enum):
    PASS = "pass"
    FAIL = "fail"


@dataclass(frozen=True, slots=True)
class GateCheck:
    """One explicit, auditable publication condition."""

    name: str
    passed: bool
    actual: float | int | str | bool | None
    required: float | int | str | bool


@dataclass(frozen=True, slots=True)
class GateReport:
    """A complete quality decision; unknown or malformed inputs fail closed."""

    state: GateState
    checks: tuple[GateCheck, ...]

    @property
    def passed(self) -> bool:
        return self.state is GateState.PASS

    def as_dict(self) -> dict[str, Any]:
        return {"state": self.state.value, "passed": self.passed, "checks": [asdict(check) for check in self.checks]}


@dataclass(frozen=True, slots=True)
class QualityInputs:
    """Aggregate-only inputs required for a publication decision.

    ``required_field_coverage`` is intentionally separate from
    ``quality_field_coverage``: schema-required fields must be complete, while
    the defined quality-field denominator permits at most two percent missing.
    """

    core_coverage: float | None
    false_publications: int | None
    automatic_mismerges: int | None
    required_field_coverage: float | None
    quality_field_coverage: float | None
    schema_valid: bool | None
    references_valid: bool | None
    checksums_valid: bool | None
    pii_findings: int | None
    overdue_count: int | None
    stop_requested: bool | None
    budget_status: BudgetStatus | str | None


def evaluate_gate(inputs: QualityInputs | Mapping[str, Any]) -> GateReport:
    """Evaluate every publication invariant without defaulting missing values.

    Any absent, invalid, or unknown value fails its individual condition, so a
    caller cannot accidentally publish when an upstream measurement is missing.
    """
    values = asdict(inputs) if isinstance(inputs, QualityInputs) else dict(inputs) if isinstance(inputs, Mapping) else {}
    budget = _budget_passes(values.get("budget_status"))
    checks = (
        _minimum("core_coverage", values.get("core_coverage"), CORE_COVERAGE_MINIMUM),
        _equals("false_publications", values.get("false_publications"), 0),
        _equals("automatic_mismerges", values.get("automatic_mismerges"), 0),
        _minimum("schema_required_field_coverage", values.get("required_field_coverage"), 1.0),
        _minimum("quality_field_coverage", values.get("quality_field_coverage"), QUALITY_FIELDS_MINIMUM),
        _equals("schema_valid", values.get("schema_valid"), True),
        _equals("references_valid", values.get("references_valid"), True),
        _equals("checksums_valid", values.get("checksums_valid"), True),
        _equals("pii_findings", values.get("pii_findings"), 0),
        _equals("overdue_count", values.get("overdue_count"), 0),
        _equals("stop_requested", values.get("stop_requested"), False),
        GateCheck("budget_status", budget, values.get("budget_status"), BudgetStatus.PASS.value),
    )
    return GateReport(GateState.PASS if all(check.passed for check in checks) else GateState.FAIL, checks)

def is_publishable_gate(report: object, *, emergency: bool = False) -> bool:
    """Return whether a complete, canonical report authorizes this operation."""
    if not isinstance(report, GateReport):
        return False
    if tuple(check.name for check in report.checks) != GATE_CHECK_NAMES:
        return False
    expected = (
        _minimum("core_coverage", report.checks[0].actual, CORE_COVERAGE_MINIMUM),
        _equals("false_publications", report.checks[1].actual, 0),
        _equals("automatic_mismerges", report.checks[2].actual, 0),
        _minimum("schema_required_field_coverage", report.checks[3].actual, 1.0),
        _minimum("quality_field_coverage", report.checks[4].actual, QUALITY_FIELDS_MINIMUM),
        _equals("schema_valid", report.checks[5].actual, True),
        _equals("references_valid", report.checks[6].actual, True),
        _equals("checksums_valid", report.checks[7].actual, True),
        _equals("pii_findings", report.checks[8].actual, 0),
        _equals("overdue_count", report.checks[9].actual, 0),
        _equals("stop_requested", report.checks[10].actual, False),
        GateCheck("budget_status", _budget_passes(report.checks[11].actual),
                  report.checks[11].actual, BudgetStatus.PASS.value),
    )
    if emergency and report.state is GateState.FAIL:
        expected = (
            *expected[:10],
            _equals("stop_requested", report.checks[10].actual, True),
            expected[11],
        )
    elif report.state is not GateState.PASS:
        return False
    if report.checks != expected:
        return False
    failed = tuple(check.name for check in report.checks if not check.passed)
    return not failed or emergency and failed == ("stop_requested",)


def _minimum(name: str, actual: Any, minimum: float) -> GateCheck:
    passed = isinstance(actual, (int, float)) and not isinstance(actual, bool) and 0 <= actual <= 1 and actual >= minimum
    return GateCheck(name, passed, actual, minimum)


def _equals(name: str, actual: Any, required: Any) -> GateCheck:
    return GateCheck(name, type(actual) is type(required) and actual == required, actual, required)


def _budget_passes(value: Any) -> bool:
    try:
        return BudgetStatus(value) is BudgetStatus.PASS
    except (TypeError, ValueError):
        return False
