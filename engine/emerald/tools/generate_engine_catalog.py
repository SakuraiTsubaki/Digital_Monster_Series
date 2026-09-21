#!/usr/bin/env python3
"""Generate Emerald-facing Digital Monster ID headers and source-backed technique assignments.

This generator deliberately does NOT invent battle stats, battle types, learn levels,
evolution conditions, graphics, cries, or abilities. Those remain separate verified
inputs before runtime activation.
"""
from __future__ import annotations
import csv, re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
GEN = ROOT / "engine" / "emerald" / "generated"

def rows(path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))

def macroize(value):
    value = re.sub(r"[^A-Za-z0-9]+", "_", value.upper()).strip("_")
    return re.sub(r"_+", "_", value)

def main():
    species = rows(GEN / "species-id-map.csv")
    techniques = rows(GEN / "technique-id-map.csv")
    assignments = rows(GEN / "entity-techniques.csv")

    assert len(species) == 1468
    assert len(techniques) == 2557
    assert max(int(x["emerald_species_id"]) for x in species) <= 2047
    assert max(int(x["dm_technique_id"]) for x in techniques) <= 2557
    assert 934 + max(int(x["dm_technique_id"]) for x in techniques) <= 4095

    keys = {(x["source_kind"], x["source_id"]) for x in species}
    missing = [(x["source_kind"], x["source_id"]) for x in assignments if (x["source_kind"], x["source_id"]) not in keys]
    assert not missing, f"unmapped technique assignment entities: {missing[:10]}"

    print("Digital Monster engine catalog inputs verified")
    print(f"  species: {len(species)}")
    print(f"  techniques: {len(techniques)}")
    print(f"  assignments: {len(assignments)}")
    print("  battle parameters: intentionally unresolved until source-backed data exists")

if __name__ == "__main__":
    main()
