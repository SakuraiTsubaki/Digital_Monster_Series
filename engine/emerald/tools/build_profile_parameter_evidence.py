#!/usr/bin/env python3
"""Build the source-evidence ledger for profile-derived Digital Monster parameters.

This tool deliberately does not invent gameplay values. It records whether the
Japanese official profile text needed for a parameter decision is available and
pins that text by SHA-256 without redistributing Digimon Reference profiles.

Appmon profiles are already present in the repository's official census. The
Digimon Reference bundle intentionally omits profile text, so a refresh job may
supply a local JSON cache containing profile_ja for each directory_name.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
EMERALD = ROOT / "engine" / "emerald"
GEN = EMERALD / "generated"
SPECIES_MAP = GEN / "species-id-map.csv"
APPMON_MASTER = ROOT / "appmon" / "appmon_master.csv"
DIGIMON_MASTER_DIR = ROOT / "data" / "digimon_reference" / "master"


def csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def load_digimon_metadata() -> dict[str, dict]:
    out: dict[str, dict] = {}
    for path in sorted(DIGIMON_MASTER_DIR.glob("digimon_master.part-*.json")):
        for row in json.loads(path.read_text(encoding="utf-8")):
            out[row["directory_name"]] = row
    if len(out) != 1320:
        raise SystemExit(f"expected 1320 Digimon metadata rows, found {len(out)}")
    return out


def load_appmon() -> dict[str, dict[str, str]]:
    rows = csv_rows(APPMON_MASTER)
    if len(rows) != 148:
        raise SystemExit(f"expected 148 Appmon rows, found {len(rows)}")
    return {f"appmon_{int(row['id']):03d}": row for row in rows}


def load_profile_from_cache(cache: Path | None, source_id: str) -> str | None:
    if cache is None:
        return None
    path = cache / f"{source_id}.json"
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    value = payload.get("profile_ja")
    return value if isinstance(value, str) and value.strip() else None


def digest(text: str | None) -> str:
    if not text:
        return ""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--digimon-profile-cache",
        type=Path,
        help="optional directory of official Digimon detail JSON files containing profile_ja",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=GEN / "profile-parameter-evidence.csv",
    )
    args = parser.parse_args()

    species = csv_rows(SPECIES_MAP)
    if len(species) != 1468:
        raise SystemExit(f"expected 1468 mapped entities, found {len(species)}")

    digimon = load_digimon_metadata()
    appmon = load_appmon()

    fields = [
        "species_id",
        "source_kind",
        "source_id",
        "name_ja",
        "official_detail_url",
        "official_level_or_grade",
        "official_type_or_app_type",
        "official_attribute",
        "special_moves",
        "profile_available",
        "profile_source",
        "profile_char_count",
        "profile_sha256",
        "parameter_resolution_status",
    ]
    output: list[dict[str, str]] = []
    ready = 0

    for row in species:
        kind = row["source_kind"]
        source_id = row["source_id"]
        profile: str | None = None
        profile_source = ""
        profile_sha = ""
        profile_char_count = ""
        special_moves = ""

        if kind == "digimon":
            meta = digimon[source_id]
            cached = load_profile_from_cache(args.digimon_profile_cache, source_id)
            if cached:
                profile = cached
                profile_source = "official_detail_cache"
                profile_sha = digest(profile)
                expected_sha = meta.get("profile_ja_sha256") or ""
                if expected_sha and profile_sha != expected_sha:
                    raise SystemExit(
                        f"{source_id}: cached profile SHA-256 {profile_sha} "
                        f"does not match census {expected_sha}"
                    )
            else:
                profile_source = "official_profile_omitted_from_repository_bundle"
                profile_sha = meta.get("profile_ja_sha256") or ""
                if meta.get("profile_ja_char_count") is not None:
                    profile_char_count = str(meta["profile_ja_char_count"])
            special_moves = " | ".join(meta.get("special_moves") or [])
        elif kind == "appmon":
            meta = appmon[source_id]
            profile = meta.get("profile_ja") or None
            profile_source = "official_appmon_census"
            profile_sha = digest(profile)
            special_moves = meta.get("special_moves_ja") or ""
        else:
            raise SystemExit(f"unsupported source_kind {kind!r}")

        if profile is not None:
            profile_char_count = str(len(profile))
            ready += 1
            status = "profile_ready_for_parameter_analysis"
        else:
            status = "needs_official_japanese_profile_text"

        output.append(
            {
                "species_id": row["emerald_species_id"],
                "source_kind": kind,
                "source_id": source_id,
                "name_ja": row["name_ja"],
                "official_detail_url": row["source_url"],
                "official_level_or_grade": row["level_or_grade"],
                "official_type_or_app_type": row["official_type"],
                "official_attribute": row["official_attribute"],
                "special_moves": special_moves,
                "profile_available": "true" if profile is not None else "false",
                "profile_source": profile_source,
                "profile_char_count": profile_char_count,
                "profile_sha256": profile_sha,
                "parameter_resolution_status": status,
            }
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(output)

    print("Profile-derived parameter evidence ledger built")
    print(f"  entities: {len(output)}")
    print(f"  profiles available for analysis: {ready}")
    print(f"  profiles still requiring official text: {len(output) - ready}")
    print(f"  output: {args.output}")


if __name__ == "__main__":
    main()
