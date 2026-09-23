#!/usr/bin/env python3
"""Build the deterministic Digital Monster gameplay sprite catalog.

The source manifests record provenance independently from gameplay assets.
A source-only manifest is valid and leaves the Pokémon donor fallback active.
An explicit override may use authored battle front/back/palette assets while
the runtime icon continues to use the mapped donor Pokémon.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
EMERALD = PROJECT_ROOT / "engine" / "emerald"
SPRITE_ROOT = EMERALD / "assets" / "gameplay-v0" / "sprites"
SPECIES_MAP = EMERALD / "generated" / "species-id-map.csv"
OUTPUT = EMERALD / "generated" / "sprite-catalog.json"

ASSET_KEYS = ("front", "back", "icon", "normal_palette")
VALID_STATUS = {"source_only", "partial", "runtime_ready"}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read_species_map() -> dict[int, dict[str, str]]:
    with SPECIES_MAP.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    if len(rows) != 1468:
        raise SystemExit(f"species-id-map.csv: expected 1468 rows, found {len(rows)}")
    return {int(row["emerald_species_id"]): row for row in rows}


def inspect_manifest(path: Path, species: dict[int, dict[str, str]]) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    species_id = int(data["species_id"])
    expected_internal = f"DM{species_id:04d}"
    row = species.get(species_id)
    if row is None:
        raise SystemExit(f"{path}: species_id {species_id} is not in species-id-map.csv")
    if data.get("internal_name") != expected_internal:
        raise SystemExit(f"{path}: expected internal_name {expected_internal}")
    if data.get("official_japanese_name") != row["name_ja"]:
        raise SystemExit(f"{path}: Japanese name does not match species-id-map.csv")
    if data.get("source_kind") != row["source_kind"] or data.get("source_id") != row["source_id"]:
        raise SystemExit(f"{path}: source identity does not match species-id-map.csv")

    status = data.get("asset_status")
    if status not in VALID_STATUS:
        raise SystemExit(f"{path}: invalid asset_status {status!r}")

    assets = data.get("assets")
    if not isinstance(assets, dict) or set(assets) != set(ASSET_KEYS):
        raise SystemExit(f"{path}: assets must contain exactly {', '.join(ASSET_KEYS)}")

    inspected = {}
    present = 0
    for key in ASSET_KEYS:
        rel = assets[key]
        if rel is None:
            inspected[key] = None
            continue
        asset_path = path.parent / rel
        if not asset_path.is_file():
            raise SystemExit(f"{path}: missing {key} asset: {rel}")
        present += 1
        inspected[key] = {
            "path": str(asset_path.relative_to(EMERALD)).replace("\\", "/"),
            "sha256": sha256(asset_path),
            "bytes": asset_path.stat().st_size,
        }

    expected_status = (
        "source_only" if present == 0 else
        "runtime_ready" if present == len(ASSET_KEYS) else
        "partial"
    )
    if status != expected_status:
        raise SystemExit(
            f"{path}: asset_status={status!r}, expected {expected_status!r} from present assets"
        )

    return {
        "species_id": species_id,
        "internal_name": expected_internal,
        "official_japanese_name": row["name_ja"],
        "source_kind": row["source_kind"],
        "source_id": row["source_id"],
        "source_reference": data["source_reference"],
        "source_image_url": data.get("source_image_url"),
        "asset_status": status,
        "assets": inspected,
    }


def build_catalog() -> dict:
    species = read_species_map()
    entries = []
    seen = set()
    for path in sorted(SPRITE_ROOT.glob("DM[0-9][0-9][0-9][0-9]/manifest.json")):
        entry = inspect_manifest(path, species)
        if entry["species_id"] in seen:
            raise SystemExit(f"duplicate sprite manifest for species {entry['species_id']}")
        seen.add(entry["species_id"])
        entries.append(entry)

    runtime_ready = sum(e["asset_status"] == "runtime_ready" for e in entries)
    partial = sum(e["asset_status"] == "partial" for e in entries)
    source_only = sum(e["asset_status"] == "source_only" for e in entries)

    return {
        "schema_version": 1,
        "profile": "gameplay-v0",
        "species_total": len(species),
        "declared_sprite_manifests": len(entries),
        "runtime_ready_species": runtime_ready,
        "partial_species": partial,
        "source_only_species": source_only,
        "placeholder_runtime_species": len(species) - runtime_ready,
        "entries": entries,
    }


def render(catalog: dict) -> str:
    return json.dumps(catalog, ensure_ascii=False, indent=2, sort_keys=False) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail if the committed sprite-catalog.json differs from current manifests",
    )
    args = parser.parse_args()

    output = render(build_catalog())
    if args.check:
        if not OUTPUT.is_file():
            raise SystemExit(f"missing generated catalog: {OUTPUT}")
        committed = OUTPUT.read_text(encoding="utf-8")
        if committed != output:
            raise SystemExit(
                "sprite-catalog.json is stale; run "
                "engine/emerald/tools/build_digital_monster_sprite_manifest.py"
            )
        print("Digital Monster sprite catalog verified")
        return

    OUTPUT.write_text(output, encoding="utf-8")
    print(f"wrote {OUTPUT}")


if __name__ == "__main__":
    main()
