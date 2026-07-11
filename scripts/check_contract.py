#!/usr/bin/env python3
"""Fail-closed legacy/v3 migration and immutable-source contract checker."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import re
from pathlib import Path
from typing import Any

QUALITY_FIELDS = ("resource_type", "source_ids", "operational_status", "status_provenance", "status_checked_at", "review")
PARTITIONS = ("published", "private", "review", "rejected")


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} root is not an object")
    return value


def ids(document: dict[str, Any], label: str) -> list[str]:
    entries = document.get("entries")
    if not isinstance(entries, list):
        raise ValueError(f"{label}.entries is not a list")
    values = [item.get("id") for item in entries if isinstance(item, dict)]
    if len(values) != len(entries) or any(not isinstance(item, str) or not item for item in values):
        raise ValueError(f"{label} has an invalid entry id")
    return values


def region_ids(document: dict[str, Any], label: str) -> list[str]:
    regions = document.get("regions")
    if not isinstance(regions, list):
        raise ValueError(f"{label}.regions is not a list")
    values = [item.get("id") for item in regions if isinstance(item, dict)]
    if len(values) != len(regions) or any(not isinstance(item, str) or not item for item in values):
        raise ValueError(f"{label} has an invalid region id")
    if len(set(values)) != len(values):
        raise ValueError(f"{label} has a duplicate region id")
    return values


def present(value: Any) -> bool:
    return value is not None and value != "" and value != [] and value != {}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--v2", type=Path, required=True)
    ap.add_argument("--v3", type=Path, required=True)
    ap.add_argument("--region-geo", type=Path, required=True, help="v2 region-id keyed GeoJSON FeatureCollections")
    ap.add_argument("--legacy", type=Path, help="extracted original v2 JSON; defaults to --v2")
    ap.add_argument("--partition", type=Path, required=True, help="JSON object with published/private/review/rejected integer counts")
    ap.add_argument("--index", type=Path, required=True)
    ap.add_argument("--expected-index-sha256", required=True)
    ap.add_argument("--quality-fields", nargs="*", default=list(QUALITY_FIELDS))
    ap.add_argument("--required-fields", nargs="*", default=list(QUALITY_FIELDS))
    ap.add_argument("--quality-minimum", type=float, default=98.0)
    args = ap.parse_args()
    if (
        tuple(args.quality_fields) != QUALITY_FIELDS
        or tuple(args.required_fields) != QUALITY_FIELDS
        or args.quality_minimum != 98.0
    ):
        raise ValueError("quality contract overrides are not permitted")
    expected_index_hash = args.expected_index_sha256.lower()
    if re.fullmatch(r"[a-f0-9]{64}", expected_index_hash) is None:
        raise ValueError("expected index hash must be SHA-256")

    failures: list[str] = []
    v2, v3 = load(args.v2), load(args.v3)
    legacy = load(args.legacy) if args.legacy else v2
    region_geo = load(args.region_geo)
    partition = load(args.partition)
    try:
        legacy_ids, v2_ids, v3_ids = ids(legacy, "legacy"), ids(v2, "v2"), ids(v3, "v3")
    except ValueError as exc:
        failures.append(str(exc))
        legacy_ids = v2_ids = v3_ids = []
    try:
        v2_region_ids = region_ids(v2, "v2")
    except ValueError as exc:
        failures.append(str(exc))
        v2_region_ids = []
    duplicate_ids = len(v3_ids) - len(set(v3_ids))
    lost_ids = len(set(legacy_ids) - set(v3_ids))
    unexpected_ids = len(set(v3_ids) - set(legacy_ids))
    partition_total = (
        sum(partition[name] for name in PARTITIONS)
        if all(type(partition.get(name)) is int and partition[name] >= 0 for name in PARTITIONS)
        else -1
    )
    actual_hash = hashlib.sha256(args.index.read_bytes()).hexdigest()
    v2_meta = v2.get("meta") if isinstance(v2.get("meta"), dict) else {}
    v3_meta = v3.get("meta") if isinstance(v3.get("meta"), dict) else {}
    if v2.get("schema_version") != 2 or len(v2_ids) != 230 or v2_meta.get("entry_count") != 230:
        failures.append("V2_COUNT_OR_VERSION")
    if v3.get("schema_version") != 3 or len(v3_ids) != 230 or v3_meta.get("entry_count") != 230:
        failures.append("V3_COUNT_OR_VERSION")
    if (
        not isinstance(v2.get("regions"), list)
        or not isinstance(v3.get("regions"), list)
        or len(v2["regions"]) != 17
        or len(v3["regions"]) != 17
        or v2_meta.get("region_count") != 17
        or v3_meta.get("region_count") != 17
    ):
        failures.append("REGION_COUNT")
    if (
        len(region_geo) != 17
        or set(region_geo) != set(v2_region_ids)
        or any(not isinstance(value, dict) or value.get("type") != "FeatureCollection" for value in region_geo.values())
    ):
        failures.append("REGION_GEO_CONTRACT")
    if v3_meta.get("source_schema_version") != 2:
        failures.append("V3_BASELINE_PROVENANCE")
    if partition_total != 230:
        failures.append("PARTITION_TOTAL")
    if duplicate_ids:
        failures.append("DUPLICATE_ID")
    if lost_ids or unexpected_ids or set(legacy_ids) != set(v2_ids):
        failures.append("ID_NOT_1_TO_1")
    if actual_hash != expected_index_hash:
        failures.append("INDEX_HASH_CHANGED")
    entries = v3.get("entries", [])
    quality = {field: sum(1 for entry in entries if isinstance(entry, dict) and present(entry.get(field))) for field in args.quality_fields}
    required_missing = {field: sum(1 for entry in entries if not isinstance(entry, dict) or field not in entry) for field in args.required_fields}
    if any(required_missing.values()):
        failures.append("V3_REQUIRED_FIELD_MISSING")
    if any(100 * count / len(entries) < args.quality_minimum for count in quality.values()) if entries else True:
        failures.append("V3_QUALITY_BELOW_MINIMUM")
    report = {"status": "PASS" if not failures else "HARD", "reason_codes": failures, "v2_entries": len(v2_ids), "v3_entries": len(v3_ids), "partition": {name: partition[name] if type(partition.get(name)) is int else None for name in PARTITIONS}, "partition_total": partition_total, "regions": {"v2": len(v2.get("regions", [])) if isinstance(v2.get("regions"), list) else 0, "v3": len(v3.get("regions", [])) if isinstance(v3.get("regions"), list) else 0, "region_geo": len(region_geo)}, "id_parity": {"duplicates": duplicate_ids, "lost": lost_ids, "unexpected": unexpected_ids}, "index": {"sha256": actual_hash, "expected_sha256": expected_index_hash, "unchanged": actual_hash == expected_index_hash}, "v3_required_fields": {field: {"missing": count, "total": len(entries)} for field, count in required_missing.items()}, "v3_quality_fields": {field: {"present": count, "total": len(entries), "percent": round(100 * count / len(entries), 2) if entries else 0.0} for field, count in quality.items()}}
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if not failures else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, json.JSONDecodeError):
        print(json.dumps({"status": "HARD", "reason_codes": ["CONTRACT_INPUT_INVALID"]}, sort_keys=True), file=sys.stderr)
        raise SystemExit(2)
    except Exception:
        print(json.dumps({"status": "HARD", "reason_codes": ["CONTRACT_EXECUTION_FAILED"]}, sort_keys=True), file=sys.stderr)
        raise SystemExit(3)
