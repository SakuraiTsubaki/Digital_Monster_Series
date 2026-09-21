#!/usr/bin/env python3
from __future__ import annotations

import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GEN = ROOT / "generated"

ENTITY_MAX = (1 << 11) - 1
TECHNIQUE_LOGICAL_MAX = 2557
TECHNIQUE_RUNTIME_MAX = (1 << 12) - 1
EXPECTED_ENTITIES = 1468
EXPECTED_TECHNIQUES = 2557


def ids(path: Path, column: str) -> list[int]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return [int(row[column]) for row in csv.DictReader(f)]


def require_contiguous(values: list[int], expected: int, label: str) -> None:
    assert len(values) == expected, f"{label}: expected {expected}, got {len(values)}"
    assert values == list(range(1, expected + 1)), f"{label}: IDs are not contiguous 1..{expected}"


def main() -> None:
    species = ids(GEN / "species-id-map.csv", "emerald_species_id")
    techniques = ids(GEN / "technique-id-map.csv", "dm_technique_id")

    require_contiguous(species, EXPECTED_ENTITIES, "entities")
    require_contiguous(techniques, EXPECTED_TECHNIQUES, "techniques")

    assert max(species) <= ENTITY_MAX
    assert max(techniques) <= TECHNIQUE_LOGICAL_MAX
    assert 934 + max(techniques) <= TECHNIQUE_RUNTIME_MAX
    assert max(techniques) > ((1 << 11) - 1), "12-bit move expansion is no longer demonstrated"

    print("Digital Monster Emerald capacity verified")
    print(f"  entities   : {len(species)} / {ENTITY_MAX} (11-bit)")
    print(f"  techniques : {len(techniques)} logical, runtime 935..{934 + max(techniques)} / {TECHNIQUE_RUNTIME_MAX} (12-bit)")


if __name__ == "__main__":
    main()
