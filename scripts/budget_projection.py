#!/usr/bin/env python3
"""Fail-closed $0 GitHub Actions budget projection gate."""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
from enum import Enum
import hashlib
import hmac
import json
import math
import sys
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

FORMULA_VERSION = "budget-projection-v4"


class JobKind(str, Enum):
    COLLECT = "collect"
    REPORT = "report"


def number(obj: dict[str, Any], key: str) -> float:
    value = obj.get(key)
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value) or value < 0:
        raise ValueError(f"{key} must be a finite non-negative number")
    return float(value)


def sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def parse_timestamp(value: Any, key: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{key} must be a non-empty ISO-8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{key} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{key} must include a timezone offset")
    return parsed.astimezone(timezone.utc)


def parse_cycle(cycle: dict[str, Any]) -> tuple[date, date, ZoneInfo]:
    for key in ("id", "start", "end", "timezone"):
        if not isinstance(cycle.get(key), str) or not cycle[key].strip():
            raise ValueError(f"billing cycle {key} is required")
    try:
        start = date.fromisoformat(cycle["start"])
        end = date.fromisoformat(cycle["end"])
        zone = ZoneInfo(cycle["timezone"])
    except (ValueError, ZoneInfoNotFoundError) as exc:
        raise ValueError("billing cycle dates or timezone are invalid") from exc
    if cycle["start"] != start.isoformat() or cycle["end"] != end.isoformat() or start > end:
        raise ValueError("billing cycle dates are invalid")
    return start, end, zone


def budget_measurements_digest(config: dict[str, Any]) -> str:
    measurements = {
        key: value
        for key, value in config.items()
        if key not in {"billing_evidence", "oracle"}
    }
    return sha256_hex(json.dumps(measurements, sort_keys=True, separators=(",", ":")))


def billing_evidence_payload(evidence: dict[str, Any]) -> str:
    fields = (
        "account", "repository", "issued_at", "expires_at", "cycle",
        "source_digest", "measurements_digest", "attestation_digest",
    )
    return json.dumps({field: evidence[field] for field in fields}, sort_keys=True, separators=(",", ":"))


def verify_billing_evidence(config: dict[str, Any], key: str | None, verifier_at: datetime) -> tuple[bool, dict[str, Any]]:
    evidence = config.get("billing_evidence")
    if not isinstance(evidence, dict) or not key:
        return False, {"verified": False}
    required = ("account", "repository", "issued_at", "expires_at", "cycle", "source_digest", "measurements_digest", "attestation_digest", "signature")
    if any(field not in evidence for field in required):
        return False, {"verified": False}
    if (
        not isinstance(config.get("account"), str)
        or not config["account"]
        or not isinstance(config.get("repository"), str)
        or not config["repository"]
        or evidence["account"] != config["account"]
        or evidence["repository"] != config["repository"]
    ):
        return False, {"verified": False}
    if not isinstance(evidence["cycle"], dict):
        return False, {"verified": False}
    try:
        issued_at = parse_timestamp(evidence["issued_at"], "issued_at")
        expires_at = parse_timestamp(evidence["expires_at"], "expires_at")
        start, end, zone = parse_cycle(evidence["cycle"])
    except ValueError:
        return False, {"verified": False}
    digests = (
        evidence["source_digest"],
        evidence["measurements_digest"],
        evidence["attestation_digest"],
    )
    if any(not isinstance(digest, str) or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest) for digest in digests):
        return False, {"verified": False}
    if evidence["measurements_digest"] != budget_measurements_digest(config):
        return False, {"verified": False}
    attestation = sha256_hex(json.dumps({field: evidence[field] for field in ("account", "repository", "issued_at", "expires_at", "cycle", "source_digest", "measurements_digest")}, sort_keys=True, separators=(",", ":")))
    expected_signature = hmac.new(key.encode("utf-8"), billing_evidence_payload(evidence).encode("utf-8"), hashlib.sha256).hexdigest()
    cycle_today = verifier_at.astimezone(zone).date()
    valid = (
        issued_at <= verifier_at <= expires_at
        and start <= cycle_today <= end
        and hmac.compare_digest(evidence["attestation_digest"], attestation)
        and isinstance(evidence["signature"], str)
        and hmac.compare_digest(evidence["signature"], expected_signature)
    )
    return valid, {"verified": valid, "cycle_id": evidence["cycle"]["id"], "verifier_at": verifier_at.isoformat()}


def cache_entry_mb(entry: dict[str, Any]) -> float:
    has_bytes, has_mb = "bytes" in entry, "mb" in entry
    if has_bytes == has_mb:
        raise ValueError("each cache inventory entry must contain exactly one of bytes or mb")
    mb = number(entry, "bytes") / 1_000_000 if has_bytes else number(entry, "mb")
    if not isinstance(entry.get("key"), str) or not entry["key"]:
        raise ValueError("cache inventory key is required")
    if entry.get("role") not in {"current", "previous"}:
        raise ValueError("cache inventory role must be current or previous")
    parse_timestamp(entry.get("observed_at"), "cache observed_at")
    return mb


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("input", type=Path, help="PII-free budget JSON")
    ap.add_argument("--billing-evidence-key", help="Caller-supplied HMAC key for billing evidence verification")
    ap.add_argument("--verify-at", help="Explicit ISO-8601 verifier time (defaults to current UTC time)")
    args = ap.parse_args()
    raw = args.input.read_bytes()
    config = json.loads(raw)
    if not isinstance(config, dict):
        raise ValueError("budget input root must be an object")
    verifier_at = parse_timestamp(args.verify_at, "verify_at") if args.verify_at else datetime.now(timezone.utc)
    hard: list[str] = []
    soft: list[str] = []
    jobs = config.get("jobs")
    if not isinstance(jobs, list) or not jobs:
        raise ValueError("jobs must be a non-empty list")
    scheduled = 0
    collect_minutes = 0
    tiers: list[dict[str, Any]] = []
    for job in jobs:
        if not isinstance(job, dict):
            raise ValueError("each job must be an object")
        try:
            kind = JobKind(job["kind"])
        except (KeyError, ValueError) as exc:
            raise ValueError("job kind must be an explicit known kind") from exc
        runs = number(job, "runs")
        if runs != int(runs):
            raise ValueError("runs must be an integer")
        duration = math.ceil(number(job, "setup_p95") + number(job, "batch_p95"))
        minutes = int(runs) * duration
        scheduled += minutes
        if kind is JobKind.COLLECT:
            collect_minutes += minutes
        tiers.append({"kind": kind.value, "runs": int(runs), "minutes_per_run": duration, "scheduled_minutes": minutes})
    retry = math.ceil(0.05 * collect_minutes)
    projected = scheduled + retry
    account = config.get("account_minutes")
    if not isinstance(account, dict):
        raise ValueError("account_minutes must be an object")
    minute_headroom = number(account, "limit") - number(account, "other_mtd") - number(account, "other_confirmed_forecast")
    ceiling = min(1600, minute_headroom)
    if projected <= ceiling:
        minute_status = "PASS"
    elif projected <= min(1900, minute_headroom):
        minute_status = "SOFT"
        soft.append("MINUTE_SOFT_CAP")
    else:
        minute_status = "HARD"
        hard.append("MINUTE_HARD_CAP")
    storage = config.get("shared_storage")
    if not isinstance(storage, dict):
        raise ValueError("shared_storage must be an object")
    storage_limit = number(storage, "limit_gb_hours")
    current_stored = number(storage, "current_stored_gb")
    current_limit = number(storage, "current_stored_limit_gb")
    has_hours = "remaining_hours" in storage
    has_projected = "trusted_projected_gb_hours" in storage
    if has_hours == has_projected:
        raise ValueError("shared storage requires exactly one of remaining_hours or trusted_projected_gb_hours")
    project_remaining = current_stored * number(storage, "remaining_hours") if has_hours else number(storage, "trusted_projected_gb_hours")
    storage_headroom = storage_limit - number(storage, "accrued_gb_hours") - number(storage, "other_confirmed_remaining_gb_hours")
    if storage_headroom < 0 or project_remaining > storage_headroom:
        hard.append("SHARED_STORAGE_HEADROOM")
    if current_stored > current_limit:
        hard.append("SHARED_STORAGE_CURRENT_EXCEEDED")
    cache = config.get("cache")
    if not isinstance(cache, dict) or not isinstance(cache.get("inventory"), list):
        raise ValueError("cache inventory must be an array")
    inventory = cache["inventory"]
    if len(inventory) > 2:
        raise ValueError("cache inventory retains more than current and previous keys")
    roles: set[str] = set()
    cache_expected = 0.0
    for entry in inventory:
        if not isinstance(entry, dict):
            raise ValueError("each cache inventory entry must be an object")
        cache_expected += cache_entry_mb(entry)
        role = entry["role"]
        if role in roles:
            raise ValueError("cache inventory has duplicate retained role")
        roles.add(role)
    if cache_expected > 200 or cache_expected > number(cache, "repo_allowance_mb"):
        hard.append("CACHE_TWO_KEY_LIMIT")
    repo = config.get("repo")
    if not isinstance(repo, dict):
        raise ValueError("repo must be an object")
    if number(repo, "control_total_mb") > 500:
        hard.append("CONTROL_REPO_TOTAL_LIMIT")
    if number(repo, "control_growth_mb") > 50:
        hard.append("CONTROL_REPO_GROWTH_LIMIT")
    if number(repo, "projection_growth_mb") > 100:
        hard.append("PROJECTION_REPO_GROWTH_LIMIT")
    artifacts = config.get("artifacts", {})
    if not isinstance(artifacts, dict):
        raise ValueError("artifacts must be an object")
    if "largest_mb" in artifacts and number(artifacts, "largest_mb") > 100:
        hard.append("ARTIFACT_INDIVIDUAL_LIMIT")
    if "project_total_mb" in artifacts and number(artifacts, "project_total_mb") > 400:
        hard.append("ARTIFACT_PROJECT_TOTAL_LIMIT")
    billing = config.get("billing_control")
    if not isinstance(billing, dict):
        raise ValueError("billing_control must be an object")
    hard_budget = type(billing.get("hard_budget_usd")) in (int, float) and billing["hard_budget_usd"] == 0 and billing.get("stop_usage") is True
    if not hard_budget:
        hard.append("ZERO_COST_ENFORCEMENT_UNVERIFIED")
    evidence_verified, evidence_report = verify_billing_evidence(config, args.billing_evidence_key, verifier_at)
    if not evidence_verified:
        hard.append("BILLING_EVIDENCE_UNVERIFIED")
    status = "HARD" if hard else ("SOFT" if soft else "PASS")
    report = {
        "formula_version": FORMULA_VERSION,
        "input_sha256": hashlib.sha256(raw).hexdigest(),
        "status": status,
        "reason_codes": hard + soft,
        "billing_evidence": evidence_report,
        "minute": {"tiers": tiers, "scheduled": scheduled, "collect_minutes": collect_minutes, "retry_reserve": retry, "projected": projected, "account_headroom": minute_headroom, "status": minute_status},
        "shared_storage": {"current_stored_gb": current_stored, "current_stored_limit_gb": current_limit, "current_cap_status": "PASS" if current_stored <= current_limit else "HARD", "headroom_gb_hours": storage_headroom, "projected_gb_hours": project_remaining, "projection_basis": "remaining_hours" if has_hours else "trusted_projected_gb_hours"},
        "cache": {"inventory_complete": True, "inventory": inventory, "retained_key_count": len(inventory), "inventory_mb": cache_expected, "repo_allowance_mb": cache.get("repo_allowance_mb")},
        "repo": {"control_total_mb": repo.get("control_total_mb"), "control_growth_mb": repo.get("control_growth_mb"), "projection_growth_mb": repo.get("projection_growth_mb")},
        "zero_cost_enforcement": {"hard_budget_zero_stop": hard_budget},
    }
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if status == "PASS" else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, json.JSONDecodeError):
        print(json.dumps({"status": "HARD", "reason_codes": ["BUDGET_INPUT_INVALID"]}, sort_keys=True), file=sys.stderr)
        raise SystemExit(2)
    except Exception:
        print(json.dumps({"status": "HARD", "reason_codes": ["BUDGET_EXECUTION_FAILED"]}, sort_keys=True), file=sys.stderr)
        raise SystemExit(3)
