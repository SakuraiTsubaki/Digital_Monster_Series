#!/usr/bin/env python3
"""Verify the committed Japanese Digimon census against a fresh official scrape."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MASTER = ROOT / "master"


def json_load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def text(value):
    return "" if value is None else str(value)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live-master", required=True, type=Path)
    args = parser.parse_args()

    live_rows = json_load(args.live_master)
    part_paths = sorted(MASTER.glob("digimon_master.part-*.json"))
    committed_rows = [row for path in part_paths for row in json_load(path)]
    committed_csv = csv_rows(MASTER / "digimon_master.csv")

    live_ids = [row["directory_name"] for row in live_rows]
    committed_ids = [row["directory_name"] for row in committed_rows]
    csv_ids = [row["directory_name"] for row in committed_csv]
    assert len(live_ids) == len(set(live_ids)), "fresh scrape contains duplicate directory_name"
    assert len(committed_ids) == len(set(committed_ids)), "committed JSON contains duplicate directory_name"
    assert len(csv_ids) == len(set(csv_ids)), "committed CSV contains duplicate directory_name"
    assert set(committed_ids) == set(live_ids), "committed JSON census differs from fresh official scrape"
    assert set(csv_ids) == set(live_ids), "committed CSV census differs from fresh official scrape"

    live_by_id = {row["directory_name"]: row for row in live_rows}
    committed_by_id = {row["directory_name"]: row for row in committed_rows}
    csv_by_id = {row["directory_name"]: row for row in committed_csv}
    core_fields = (
        "name_ja", "name_roman", "level_raw", "level_normalized", "type_raw",
        "type_normalized", "attribute_raw", "attribute_normalized",
        "special_moves_raw", "main_image_url", "has_additional_illustrations",
    )
    json_only_fields = (
        "detail_url", "http_status", "special_moves", "additional_illustration_urls",
        "all_official_image_urls",
    )
    for directory_name in live_ids:
        live = live_by_id[directory_name]
        committed = committed_by_id[directory_name]
        csv_row = csv_by_id[directory_name]
        for field in core_fields:
            assert text(committed.get(field)) == text(live.get(field)), (directory_name, field, "JSON")
            assert text(csv_row.get(field)) == text(live.get(field)), (directory_name, field, "CSV")
        for field in json_only_fields:
            assert committed.get(field) == live.get(field), (directory_name, field, "JSON")
        live_profile = live.get("profile_ja")
        assert committed.get("profile_ja_available_on_official_page") == bool(live_profile)
        assert committed.get("profile_ja_char_count") == len(live_profile or "")
        assert committed.get("profile_ja_sha256") == (
            hashlib.sha256(live_profile.encode("utf-8")).hexdigest() if live_profile else None
        )

    manifest = json_load(MASTER / "manifest.json")
    assert manifest["record_count"] == len(committed_rows)
    assert manifest["part_count"] == len(part_paths) == len(manifest["parts"])
    assert sum(part["records"] for part in manifest["parts"]) == len(committed_rows)
    for entry, path in zip(manifest["parts"], part_paths, strict=True):
        assert entry["path"] == path.name
        assert entry["records"] == len(json_load(path))
        assert entry["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()

    validation = json_load(ROOT / "reports/validation.json")
    for field in (
        "official_displayed_count", "listing_rows_received", "unique_directory_names",
        "successfully_parsed_detail_pages",
    ):
        assert validation[field] == len(committed_rows), (field, validation[field])
    assert validation["missing_count_vs_official_display"] == 0
    assert validation["failed_pages"] == []
    assert validation["duplicate_directory_names_in_listing"] == []

    expected_moves = [
        (row["directory_name"], str(index), move)
        for row in committed_rows
        for index, move in enumerate(row.get("special_moves") or [], 1)
    ]
    actual_moves = [
        (row["directory_name"], row["move_order"], row["move_raw"])
        for row in csv_rows(ROOT / "moves/special_moves.csv")
    ]
    assert sorted(actual_moves) == sorted(expected_moves), "special move manifest differs from committed master"

    expected_images = [
        (row["directory_name"], str(index), "True" if index == 1 else "False", url)
        for row in committed_rows
        for index, url in enumerate(row.get("all_official_image_urls") or [], 1)
    ]
    actual_images = [
        (row["directory_name"], row["image_order"], row["is_main"], row["image_url"])
        for row in csv_rows(ROOT / "images/image_manifest.csv")
    ]
    assert sorted(actual_images) == sorted(expected_images), "image manifest differs from committed master"

    for filename, field in (
        ("levels.json", "level_raw"),
        ("types.json", "type_raw"),
        ("attributes.json", "attribute_raw"),
    ):
        payload = json_load(ROOT / "taxonomy" / filename)
        actual = {entry["raw_value"]: entry["count"] for entry in payload["detail_page_values"]}
        assert actual == dict(Counter(row.get(field) for row in committed_rows)), filename

    print("Committed official Digimon dataset verified")
    print(f"  Digimon: {len(committed_rows)}")
    print(f"  special moves: {len(actual_moves)}")
    print(f"  image URLs: {len(actual_images)}")
    print(f"  JSON parts: {len(part_paths)}")


if __name__ == "__main__":
    main()
