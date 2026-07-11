#!/usr/bin/env python3
"""Extract and validate v2 site-data from legacy HTML or externalized JSON."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from html.parser import HTMLParser
from pathlib import Path

EXPECTED_VERSION = 2
EXPECTED_ENTRIES = 230
EXPECTED_REGIONS = 17


class SiteDataParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self._capture = False
        self._parts: list[str] = []
        self.matches = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag.lower() == "script" and attributes.get("type") == "application/json" and attributes.get("id") == "site-data":
            self.matches += 1
            self._capture = True

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "script" and self._capture:
            self._capture = False

    def handle_data(self, data: str) -> None:
        if self._capture:
            self._parts.append(data)

    @property
    def payload(self) -> str:
        return "".join(self._parts)


def load_embedded_json(source: bytes) -> dict:
    parser = SiteDataParser()
    # Incremental feeding avoids assumptions about physical HTML line length.
    try:
        html = source.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("source is not valid UTF-8") from exc
    for offset in range(0, len(html), 1024 * 1024):
        parser.feed(html[offset : offset + 1024 * 1024])
    parser.close()
    if parser.matches != 1:
        raise ValueError("expected exactly one site-data script")
    try:
        data = json.loads(parser.payload)
    except json.JSONDecodeError as exc:
        raise ValueError("site-data is not valid JSON") from exc
    if not isinstance(data, dict):
        raise ValueError("site-data root must be an object")
    return data


def load_source(source_path: Path) -> tuple[dict, str, str]:
    source = source_path.read_bytes()
    source_sha256 = hashlib.sha256(source).hexdigest()
    stripped = source.lstrip()
    if stripped.startswith(b"\xef\xbb\xbf"):
        stripped = stripped[3:].lstrip()
    if stripped.startswith((b"{", b"[")):
        try:
            data = json.loads(source)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("source JSON is invalid") from exc
        if not isinstance(data, dict):
            raise ValueError("source JSON root must be an object")
        return data, "json", source_sha256
    return load_embedded_json(source), "html", source_sha256


def validate_v2(data: dict) -> list[str]:
    meta = data.get("meta")
    entries = data.get("entries")
    regions = data.get("regions")
    if data.get("schema_version") != EXPECTED_VERSION:
        raise ValueError(f"schema_version must be {EXPECTED_VERSION}")
    if not isinstance(meta, dict) or meta.get("entry_count") != EXPECTED_ENTRIES:
        raise ValueError(f"meta.entry_count must be {EXPECTED_ENTRIES}")
    if not isinstance(regions, list) or len(regions) != EXPECTED_REGIONS or meta.get("region_count") != EXPECTED_REGIONS:
        raise ValueError(f"region count must be {EXPECTED_REGIONS}")
    if not all(isinstance(region, dict) for region in regions):
        raise ValueError("every region must be an object")
    region_ids = [region.get("id") for region in regions]
    if any(not isinstance(region_id, str) or not region_id for region_id in region_ids):
        raise ValueError("every region must have a non-empty string id")
    if len(set(region_ids)) != EXPECTED_REGIONS:
        raise ValueError("region ids must be unique")
    for region, region_id in zip(regions, region_ids, strict=True):
        if region.get("geojson_ref") != f"geo/regions/{region_id}.geojson":
            raise ValueError("region geojson_ref must match its id")
    if not isinstance(entries, list) or len(entries) != EXPECTED_ENTRIES:
        raise ValueError(f"entry count must be {EXPECTED_ENTRIES}")
    ids = [entry.get("id") for entry in entries if isinstance(entry, dict)]
    if len(ids) != len(entries) or any(not isinstance(value, str) or not value for value in ids):
        raise ValueError("every entry must have a non-empty string id")
    if len(set(ids)) != len(ids):
        raise ValueError("entry ids must be unique")
    return ids


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="legacy HTML containing #site-data or externalized v2 JSON")
    parser.add_argument("--output", type=Path, help="optional destination for deterministic v2 JSON")
    parser.add_argument("--ids-output", type=Path, help="optional deterministic newline-delimited ID list")
    args = parser.parse_args()
    data, source_format, source_sha256 = load_source(args.source)
    ids = validate_v2(data)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    if args.ids_output:
        args.ids_output.parent.mkdir(parents=True, exist_ok=True)
        args.ids_output.write_text("\n".join(ids) + "\n", encoding="utf-8")
    print(json.dumps({"schema_version": 2, "entry_count": len(ids), "region_count": len(data["regions"]), "source_format": source_format, "source_sha256": source_sha256, "ids": ids}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, json.JSONDecodeError):
        print("HARD EXTRACT_INVALID", file=sys.stderr)
        raise SystemExit(2)
