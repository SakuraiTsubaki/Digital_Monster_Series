#!/usr/bin/env python3
"""Validate generated profile-derived species parameters and rendered SpeciesInfo."""
from __future__ import annotations

import argparse
import csv
import re
from collections import defaultdict
from pathlib import Path


STAT_FIELDS = [
    "base_hp",
    "base_attack",
    "base_defense",
    "base_speed",
    "base_sp_attack",
    "base_sp_defense",
]


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--parameters", type=Path, required=True)
    ap.add_argument("--species-dir", type=Path, required=True)
    args = ap.parse_args()

    data = rows(args.parameters)
    assert len(data) == 1468, len(data)
    assert [int(x["species_id"]) for x in data] == list(range(1, 1469))

    by_stage: dict[str, set[int]] = defaultdict(set)
    type_pairs = set()
    for row in data:
        values = [int(row[x]) for x in STAT_FIELDS]
        assert all(1 <= x <= 255 for x in values), (row["species_id"], values)
        assert int(row["bst"]) == sum(values)
        assert row["profile_sha256"] and len(row["profile_sha256"]) == 64
        assert row["evidence_signals"]
        assert row["battle_type_1"].startswith("TYPE_")
        assert row["derivation_version"] == "profile-derived-v1"
        assert 3 <= int(row["catch_rate"]) <= 255
        assert 20 <= int(row["exp_yield"]) <= 65535
        assert row["growth_rate"].startswith("GROWTH_")
        by_stage[row["official_level_or_grade"]].add(int(row["bst"]))
        type_pairs.add((row["battle_type_1"], row["battle_type_2"]))

    # Guard against reintroducing fixed total tables.
    multi_member_stages = [
        values for values in by_stage.values()
        if len(values) > 1
    ]
    assert multi_member_stages, "no stage has variable BST totals"
    assert len({int(x["bst"]) for x in data}) >= 20
    assert len(type_pairs) >= 8

    parts = sorted(args.species_dir.glob("digital_monster_part_*.h"))
    rendered = "\n".join(x.read_text(encoding="utf-8") for x in parts)
    assert rendered.count("profile_derived_v1_noncanonical") == 1468
    assert "project_generated_gameplay_v0_noncanonical" not in rendered

    species_ids = [int(x) for x in re.findall(r"(?m)^\s*\[(\d+)\]\s*=", rendered)]
    assert species_ids == list(range(1, 1469))

    print("Profile-derived SpeciesInfo verified")
    print(f"  entities: {len(data)}")
    print(f"  unique BST totals: {len({int(x['bst']) for x in data})}")
    print(f"  unique type combinations: {len(type_pairs)}")
    print("  each base stat: 1..255")
    print("  fixed BST total table: absent")


if __name__ == "__main__":
    main()
