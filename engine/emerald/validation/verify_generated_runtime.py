#!/usr/bin/env python3
from __future__ import annotations

import csv
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
G = ROOT / "generated" / "pokeemerald-expansion"
DONOR_MAP = ROOT / "generated" / "donor-sprite-map.csv"

EXPECTED_SPECIES = 1468
ALLOWED_FAMILIES = {
    "base",
    "undead",
    "beast",
    "machine",
    "angel",
    "demon",
    "dragon",
    "aquatic",
    "insect",
    "holy",
    "dark",
}


def verify_donor_map() -> tuple[int, int]:
    with DONOR_MAP.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))

    assert len(rows) == EXPECTED_SPECIES, len(rows)
    ids = [int(row["species_id"]) for row in rows]
    assert ids == list(range(1, EXPECTED_SPECIES + 1))

    donors = set()
    for row in rows:
        sid = int(row["species_id"])
        assert row["internal_name"] == f"DM{sid:04d}"
        donor_id = int(row["donor_species_id"])
        assert 1 <= donor_id <= 386
        assert row["donor_species_constant"].startswith("SPECIES_")
        assert row["sprite_family"] in ALLOWED_FAMILIES
        assert row["palette_preset"] in ALLOWED_FAMILIES
        assert row["palette_preset"] == row["sprite_family"]
        donors.add(donor_id)

    first = rows[0]
    assert first["internal_name"] == "DM0001"
    assert first["donor_species_id"] == "169"
    assert first["donor_species_constant"] == "SPECIES_CROBAT"
    assert first["sprite_family"] == "undead"
    assert first["palette_preset"] == "undead"

    return len(rows), len(donors)


def main():
    species_dir = G / "src/data/pokemon/species_info"
    learn_dir = G / "src/data/pokemon/level_up_learnsets"
    species = "\n".join(
        p.read_text(encoding="utf-8")
        for p in sorted(species_dir.glob("digital_monster_part_*.h"))
    )
    learns = "\n".join(
        p.read_text(encoding="utf-8")
        for p in sorted(learn_dir.glob("digital_monster_part_*.h"))
    )
    enum = (G / "include/constants/digital_monster_move_enum.inc").read_text(
        encoding="utf-8"
    )

    species_ids = [
        int(x) for x in re.findall(r"^\s*\[(\d+)\]\s*=", species, flags=re.M)
    ]
    learn_ids = [
        int(x)
        for x in re.findall(r"sDigitalMonster(\d{4})LevelUpLearnset", learns)
    ]

    assert species_ids == list(range(1, EXPECTED_SPECIES + 1)), (
        len(species_ids),
        species_ids[:3],
        species_ids[-3:],
    )
    assert learn_ids == list(range(1, EXPECTED_SPECIES + 1)), (
        len(learn_ids),
        learn_ids[:3],
        learn_ids[-3:],
    )
    assert "DM_MOVE_2557" in enum
    assert "DM_MOVE_BOOTSTRAP_ATTACK" in enum
    assert "DM_MOVES_COUNT" in enum

    fallback_count = learns.count("DM_MOVE_BOOTSTRAP_ATTACK")
    assert fallback_count == 9, fallback_count

    donor_rows, unique_donors = verify_donor_map()

    print("Digital Monster generated runtime verified")
    print(f"  SpeciesInfo entries: {EXPECTED_SPECIES}")
    print(f"  learnsets: {EXPECTED_SPECIES}")
    print("  official techniques: 2557")
    print("  bootstrap-only species: 9")
    print("  runtime move IDs: 935..3492")
    print(f"  donor sprite mappings: {donor_rows}")
    print(f"  unique Gen I-III Pokémon donors used: {unique_donors}")
    print("  DM0001 donor: SPECIES_CROBAT")
    print("  palette preset mode: sprite_family")


if __name__ == "__main__":
    main()
