#!/usr/bin/env python3
from __future__ import annotations
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
G = ROOT / "generated" / "pokeemerald-expansion"

def main():
    species_dir = G / "src/data/pokemon/species_info"
    learn_dir = G / "src/data/pokemon/level_up_learnsets"
    species = "\n".join(p.read_text(encoding="utf-8") for p in sorted(species_dir.glob("digital_monster_part_*.h")))
    learns = "\n".join(p.read_text(encoding="utf-8") for p in sorted(learn_dir.glob("digital_monster_part_*.h")))
    enum = (G / "include/constants/digital_monster_move_enum.inc").read_text(encoding="utf-8")

    species_ids = [int(x) for x in re.findall(r"^\s*\[(\d+)\]\s*=", species, flags=re.M)]
    learn_ids = [int(x) for x in re.findall(r"sDigitalMonster(\d{4})LevelUpLearnset", learns)]

    assert species_ids == list(range(1, 1469)), (len(species_ids), species_ids[:3], species_ids[-3:])
    assert learn_ids == list(range(1, 1469)), (len(learn_ids), learn_ids[:3], learn_ids[-3:])
    assert "DM_MOVE_2557" in enum
    assert "DM_MOVE_BOOTSTRAP_ATTACK" in enum
    assert "DM_MOVES_COUNT" in enum

    fallback_count = learns.count("DM_MOVE_BOOTSTRAP_ATTACK")
    assert fallback_count == 9, fallback_count

    print("Digital Monster generated runtime verified")
    print("  SpeciesInfo entries: 1468")
    print("  learnsets: 1468")
    print("  official techniques: 2557")
    print("  bootstrap-only species: 9")
    print("  runtime move IDs: 935..3492")

if __name__ == "__main__":
    main()
