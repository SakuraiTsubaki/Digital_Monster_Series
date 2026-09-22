#!/usr/bin/env python3
"""Guard the Digital Monster parameter policy against legacy random/fixed-BST rules."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEGACY = ROOT / "balance" / "gameplay-v0-rules.json"
CURRENT = ROOT / "balance" / "profile-derived-v1-rules.json"


def main() -> None:
    legacy = json.loads(LEGACY.read_text(encoding="utf-8"))
    current = json.loads(CURRENT.read_text(encoding="utf-8"))

    assert legacy["status"] == "deprecated_for_battle_parameters"
    assert legacy["replacement"] == "profile-derived-v1"
    assert "entity_tiers" not in legacy
    assert "archetypes" not in legacy
    assert "archetype_assignment" not in legacy

    stats = current["stats"]
    assert stats["per_stat_storage_bits"] == 8
    assert stats["per_stat_min"] == 0
    assert stats["per_stat_max"] == 255
    assert stats["bst_total_limit"] is None
    assert stats["fixed_bst_by_level_or_grade"] is False

    prohibited = set(current["prohibited_methods"])
    required = {
        "hash_based_archetype_assignment",
        "random_stat_assignment",
        "fixed_bst_table_by_level_or_grade",
        "fixed_bst_cap",
        "stage_or_grade_only_battle_type_mapping",
        "fixed_neutral_type_as_final_data",
        "unrelated_pokemon_parameter_fallback",
    }
    assert required <= prohibited, required - prohibited

    text = CURRENT.read_text(encoding="utf-8")
    assert "FNV-1a" not in text
    assert "neutral_v0" not in text

    print("Profile-derived parameter policy verified")
    print("  per-stat storage: u8 / 0..255")
    print("  BST total limit: none")
    print("  fixed BST by level/grade: disabled")
    print("  hash/random role assignment: prohibited")


if __name__ == "__main__":
    main()
