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
        assert row["battle_type_status"] in {
            "resolved_profile_evidence",
            "unresolved_no_specialized_type_evidence",
            "unresolved_low_type_evidence",
        }
        assert row["ability_1"].startswith("ABILITY_")
        assert row["ability_2"].startswith("ABILITY_")
        assert row["ability_hidden"].startswith("ABILITY_")
        assert row["ability_status"] in {
            "resolved_profile_passive_evidence",
            "unresolved_no_passive_evidence",
            "unresolved_low_passive_evidence",
        }
        assert row["derivation_version"] == "profile-derived-v1"
        assert 3 <= int(row["catch_rate"]) <= 255
        assert 20 <= int(row["exp_yield"]) <= 65535
        ev_fields = [
            "ev_yield_hp", "ev_yield_attack", "ev_yield_defense",
            "ev_yield_speed", "ev_yield_sp_attack", "ev_yield_sp_defense",
        ]
        ev_values = [int(row[field]) for field in ev_fields]
        assert all(0 <= value <= 3 for value in ev_values), (row["species_id"], ev_values)
        assert sum(ev_values) <= 3, (row["species_id"], ev_values)
        assert row["ev_yield_status"] in {
            "resolved_profile_stat_evidence",
            "unresolved_no_stat_specialization_evidence",
        }
        if row["ev_yield_status"] == "resolved_profile_stat_evidence":
            assert sum(ev_values) >= 1
        else:
            assert sum(ev_values) == 0
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
    assert "// Generated gameplay-v0 SpeciesInfo entries" not in rendered
    resolved_abilities = sum(
        row["ability_status"] == "resolved_profile_passive_evidence"
        for row in data
    )
    assert resolved_abilities > 0
    rendered_abilities = re.findall(
        r"(?m)^\s*\.abilities\s*=\s*\{\s*(ABILITY_[A-Z0-9_]+)",
        rendered,
    )
    assert len(rendered_abilities) == 1468
    assert sum(x != "ABILITY_NONE" for x in rendered_abilities) == resolved_abilities

    gender_ratios = re.findall(
        r"(?m)^\s*\.genderRatio\s*=\s*([^,]+),$",
        rendered,
    )
    assert len(gender_ratios) == 1468, len(gender_ratios)
    assert set(gender_ratios) == {"PERCENT_FEMALE(50)"}, set(gender_ratios)

    ev_c_fields = [
        ("evYield_HP", "ev_yield_hp"),
        ("evYield_Attack", "ev_yield_attack"),
        ("evYield_Defense", "ev_yield_defense"),
        ("evYield_Speed", "ev_yield_speed"),
        ("evYield_SpAttack", "ev_yield_sp_attack"),
        ("evYield_SpDefense", "ev_yield_sp_defense"),
    ]
    for c_field, csv_field in ev_c_fields:
        rendered_values = [
            int(x)
            for x in re.findall(
                rf"(?m)^\s*\.{c_field}\s*=\s*(\d+),$",
                rendered,
            )
        ]
        assert len(rendered_values) == 1468, (c_field, len(rendered_values))
        assert rendered_values == [int(row[csv_field]) for row in data], c_field

    species_ids = [int(x) for x in re.findall(r"(?m)^\s*\[(\d+)\]\s*=", rendered)]
    assert species_ids == list(range(1, 1469))

    print("Profile-derived SpeciesInfo verified")
    print(f"  entities: {len(data)}")
    print(f"  unique BST totals: {len({int(x['bst']) for x in data})}")
    print(f"  unique type combinations: {len(type_pairs)}")
    print(f"  resolved battle types: {sum(x['battle_type_status'] == 'resolved_profile_evidence' for x in data)}")
    print(f"  resolved profile abilities: {resolved_abilities}")
    print("  runtime gender ratio: 50% female / 50% male (project gameplay override)")
    ev_total_counts = {}
    for row in data:
        total = sum(int(row[field]) for field in [
            "ev_yield_hp", "ev_yield_attack", "ev_yield_defense",
            "ev_yield_speed", "ev_yield_sp_attack", "ev_yield_sp_defense",
        ])
        ev_total_counts[total] = ev_total_counts.get(total, 0) + 1
    print(f"  EV-yield totals: {dict(sorted(ev_total_counts.items()))}")
    print("  each base stat: 1..255")
    print("  fixed BST total table: absent")


if __name__ == "__main__":
    main()
