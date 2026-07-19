"""Apply a human review decision to one weekly discovery candidate."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from .weekly_discovery import DiscoveryError, _atomic_json, _empty_candidates, _empty_seen, load_document


DECISIONS = ("accepted", "duplicate", "rejected")


def review(
    candidate_id: str,
    decision: str,
    *,
    entry_id: str | None,
    reviewed_at: str,
    site_path: Path,
    seen_path: Path,
    candidates_path: Path,
) -> dict[str, str]:
    if decision not in DECISIONS:
        raise DiscoveryError("invalid_decision")
    site = json.loads(site_path.read_text(encoding="utf-8"))
    entry_ids = {entry.get("id") for entry in site.get("entries", [])}
    if entry_id is not None and entry_id not in entry_ids:
        raise DiscoveryError("unknown_entry")
    if decision == "accepted" and entry_id is None:
        raise DiscoveryError("accepted_requires_entry")

    seen = load_document(seen_path, _empty_seen())
    candidates = load_document(candidates_path, _empty_candidates())
    candidate = next((item for item in candidates["candidates"] if item.get("id") == candidate_id), None)
    if candidate is None or candidate.get("status") != "needs_review":
        raise DiscoveryError("candidate_not_reviewable")
    ledger_item = next(
        (item for item in seen["items"] if item.get("url_sha256") == candidate.get("url_sha256")),
        None,
    )
    if ledger_item is None or ledger_item.get("decision") != "needs_review":
        raise DiscoveryError("ledger_mismatch")

    candidate["status"] = decision
    candidate["reviewed_at"] = reviewed_at
    ledger_item["decision"] = decision
    ledger_item["reviewed_at"] = reviewed_at
    if entry_id is not None:
        candidate["entry_id"] = entry_id
        if entry_id not in ledger_item["entry_ids"]:
            ledger_item["entry_ids"].append(entry_id)
            ledger_item["entry_ids"].sort()

    _atomic_json(seen_path, seen)
    _atomic_json(candidates_path, candidates)
    return {"candidate_id": candidate_id, "decision": decision}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Record a weekly discovery review decision")
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--decision", required=True, choices=DECISIONS)
    parser.add_argument("--entry-id")
    parser.add_argument("--reviewed-at")
    parser.add_argument("--site", default="data/site.v3.json")
    parser.add_argument("--seen", default="data/discovery/seen.v1.json")
    parser.add_argument("--candidates", default="data/discovery/candidates.v1.json")
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        args = build_parser().parse_args(argv)
        reviewed_at = args.reviewed_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        print(json.dumps(review(
            args.candidate,
            args.decision,
            entry_id=args.entry_id,
            reviewed_at=reviewed_at,
            site_path=Path(args.site),
            seen_path=Path(args.seen),
            candidates_path=Path(args.candidates),
        ), ensure_ascii=False, sort_keys=True))
        return 0
    except (DiscoveryError, OSError, ValueError, json.JSONDecodeError):
        print(json.dumps({"outcome": "blocked", "reason": "review_failed"}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
