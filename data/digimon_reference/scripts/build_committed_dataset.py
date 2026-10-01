#!/usr/bin/env python3
"""Build the compact committed dataset from a verified full official scrape."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
from pathlib import Path


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def dump(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--chunk-size", type=int, default=220)
    args = parser.parse_args()

    source = args.source.resolve()
    output = args.output.resolve()
    master_dir = output / "master"
    master_dir.mkdir(parents=True, exist_ok=True)
    rows = load(source / "master/digimon_master.json")

    release = []
    for row in rows:
        item = dict(row)
        profile = item.get("profile_ja")
        item["profile_ja"] = None
        item["profile_ja_available_on_official_page"] = profile is not None
        item["profile_ja_char_count"] = len(profile) if profile is not None else None
        item["profile_ja_sha256"] = (
            hashlib.sha256(profile.encode("utf-8")).hexdigest() if profile is not None else None
        )
        item["profile_ja_omitted_from_bundle"] = profile is not None
        release.append(item)

    csv_fields = [
        "directory_name", "detail_url", "name_ja", "name_roman",
        "level_raw", "level_normalized", "type_raw", "type_normalized",
        "attribute_raw", "attribute_normalized", "special_moves_raw",
        "main_image_url", "has_additional_illustrations", "additional_illustration_count",
        "listing_level", "listing_level_2", "listing_level_order", "is_x_antibody",
        "icon_new", "icon_20th", "profile_ja_available_on_official_page",
        "profile_ja_char_count", "profile_ja_sha256", "profile_ja_omitted_from_bundle",
    ]
    with (master_dir / "digimon_master.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=csv_fields)
        writer.writeheader()
        for item in release:
            listing = item.get("listing_metadata") or {}
            writer.writerow({
                **{field: item.get(field) for field in csv_fields},
                "additional_illustration_count": len(item.get("additional_illustration_urls") or []),
                "listing_level": listing.get("level"),
                "listing_level_2": listing.get("level_2"),
                "listing_level_order": listing.get("level_order"),
                "is_x_antibody": listing.get("relate_word6") == "〇",
                "icon_new": bool(listing.get("icon_new")),
                "icon_20th": bool(listing.get("icon_20th")),
            })

    for old_part in master_dir.glob("digimon_master.part-*.json"):
        old_part.unlink()
    parts = []
    for index, start in enumerate(range(0, len(release), args.chunk_size), 1):
        path = master_dir / f"digimon_master.part-{index:02d}.json"
        chunk = release[start:start + args.chunk_size]
        dump(path, chunk)
        parts.append({
            "path": path.name,
            "records": len(chunk),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        })
    dump(master_dir / "manifest.json", {
        "format": "segmented_json_arrays",
        "record_count": len(release),
        "part_count": len(parts),
        "ordering": "official listing API order at collection time",
        "parts": parts,
    })

    for relative in (
        "taxonomy/levels.json", "taxonomy/types.json", "taxonomy/attributes.json",
        "moves/special_moves.csv", "images/image_manifest.csv",
        "reports/validation.json", "reports/validation.md",
        "reports/exceptions.json", "reports/exceptions.md", "reports/site_structure.md",
    ):
        destination = output / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source / relative, destination)

    validation = load(source / "reports/validation.json")
    exceptions = load(source / "reports/exceptions.json")
    move_total = sum(len(row.get("special_moves") or []) for row in rows)
    image_total = sum(len(row.get("all_official_image_urls") or []) for row in rows)
    attribute_missing = sum(row.get("attribute_raw") is None for row in rows)
    move_missing = sum(not (row.get("special_moves") or []) for row in rows)
    illustration_count = sum(bool(row.get("has_additional_illustrations")) for row in rows)
    readme = f"""# digimon.net 공식 디지몬 도감 전수조사

일본어판 `https://digimon.net/reference/`를 Master Reference로 삼아 {validation['collected_at_utc']}에 전체 목록과 상세 페이지를 순회한 데이터셋이다.

## 검증 결과

| 항목 | 수 |
|---|---:|
| 사이트 표시 등록 수 | {validation['official_displayed_count']} |
| 목록 API 응답 행 | {validation['listing_rows_received']} |
| 고유 `directory_name` | {validation['unique_directory_names']} |
| 상세 페이지 확인 성공 | {validation['successfully_parsed_detail_pages']} |
| 실패 페이지 | {len(validation['failed_pages'])} |
| 누락 개체 | {validation['missing_count_vs_official_display']} |

## 주요 집계

- 레벨 고유값: {len(set(row.get('level_raw') for row in rows))}개
- 타입 고유값: {len(set(row.get('type_raw') for row in rows))}개
- 속성 고유값: {len(set(row.get('attribute_raw') for row in rows))}개(null 포함)
- 속성 미기재: {attribute_missing}개
- 실질 필살기 미기재: {move_missing}개
- 필살기 항목: {move_total}개
- 공식 이미지 URL: {image_total}개
- 추가 일러스트 보유 개체: {illustration_count}개
- 일본어 이름 완전 중복 그룹: {len(exceptions['duplicate_exact_names'])}개

## 원문 처리

이름·레벨·타입·속성·필살기 표기는 일본어 원문 그대로 보존했다. `*_normalized`는 추정 변환 없이 현재 원문과 동일하다. 공식 프로필 문장은 {len(rows):,}개 페이지에서 존재 여부와 내용을 검증했지만, 사이트의 무단 전재 금지 고지를 존중하여 이 배포 묶음에는 전문을 복제하지 않고 `detail_url`, 글자 수와 SHA-256을 남겼다. 동봉된 재현 스크립트를 실행하면 공식 페이지에서 현재 값을 다시 확인할 수 있다.
"""
    (output / "README.md").write_text(readme, encoding="utf-8")
    print(f"Built committed official dataset: {len(rows)} Digimon, {len(parts)} JSON parts")


if __name__ == "__main__":
    main()
