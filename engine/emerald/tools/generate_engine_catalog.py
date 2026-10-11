#!/usr/bin/env python3
"""Generate Emerald-facing IDs and source-backed technique assignments.

The generated files preserve official Japanese names and stable existing IDs. This
generator does not invent battle stats, evolution conditions, graphics, cries, or
abilities; those remain in their separately labelled gameplay interpretation layers.
"""
from __future__ import annotations

import csv
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
GEN = ROOT / "engine" / "emerald" / "generated"
POKE = GEN / "pokeemerald-expansion"
EXPECTED_SPECIES = 1473
EXPECTED_TECHNIQUES = 2567
EXPECTED_ASSIGNMENTS = 2882
RUNTIME_MOVE_OFFSET = 934


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def macroize(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9]+", "_", value.upper()).strip("_")
    return re.sub(r"_+", "_", value)


def c_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def write(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    species = rows(GEN / "species-id-map.csv")
    techniques = rows(GEN / "technique-id-map.csv")
    assignments = rows(GEN / "entity-techniques.csv")

    assert len(species) == EXPECTED_SPECIES
    assert len(techniques) == EXPECTED_TECHNIQUES
    assert len(assignments) == EXPECTED_ASSIGNMENTS
    assert [int(x["emerald_species_id"]) for x in species] == list(
        range(1, EXPECTED_SPECIES + 1)
    )
    assert [int(x["dm_technique_id"]) for x in techniques] == list(
        range(1, EXPECTED_TECHNIQUES + 1)
    )
    assert RUNTIME_MOVE_OFFSET + EXPECTED_TECHNIQUES <= 4095

    species_by_key = {
        (row["source_kind"], row["source_id"]): row for row in species
    }
    missing = [
        (row["source_kind"], row["source_id"])
        for row in assignments
        if (row["source_kind"], row["source_id"]) not in species_by_key
    ]
    assert not missing, f"unmapped technique assignment entities: {missing[:10]}"

    species_header = [
        "#ifndef DIGITAL_MONSTER_SPECIES_IDS_H",
        "#define DIGITAL_MONSTER_SPECIES_IDS_H",
        "",
        "// Generated stable IDs for the Digital_Monster_Series Emerald replacement profile.",
        "// This profile REPLACES the Pokémon species catalog; these are not appended Pokémon IDs.",
        "",
        "#define DM_SPECIES_NONE 0",
    ]
    for row in species:
        macro = macroize(row["source_id"])
        species_header.append(
            f'#define DM_SPECIES_{macro} {row["emerald_species_id"]} /* {row["name_ja"]} */'
        )
    species_header.extend([
        "",
        f"#define DM_SPECIES_COUNT {EXPECTED_SPECIES + 1}",
        f"#define DM_SPECIES_LAST {EXPECTED_SPECIES}",
        "",
        "#endif // DIGITAL_MONSTER_SPECIES_IDS_H",
    ])
    write(GEN / "digital-monster-species-ids.h", species_header)

    technique_header = [
        "#ifndef DIGITAL_MONSTER_TECHNIQUE_IDS_H",
        "#define DIGITAL_MONSTER_TECHNIQUE_IDS_H",
        "",
        "// Logical Digital Monster technique IDs are stable dataset IDs.",
        "// Runtime Emerald move IDs are offset by the pinned engine move count (935).",
        "#define DM_TECHNIQUE_NONE 0",
        "#define DM_RUNTIME_MOVE_BASE 935",
    ]
    for row in techniques:
        tid = int(row["dm_technique_id"])
        technique_header.append(
            f'#define DM_TECHNIQUE_{tid:04d} {tid} /* {row["name_ja"]} */'
        )
    technique_header.extend([
        "",
        f"#define DM_TECHNIQUE_COUNT {EXPECTED_TECHNIQUES + 1}",
        f"#define DM_TECHNIQUE_LAST {EXPECTED_TECHNIQUES}",
        "#define DM_TECHNIQUE_RUNTIME_ID(logicalId) (DM_RUNTIME_MOVE_BASE + (logicalId) - 1)",
        "",
        "#endif // DIGITAL_MONSTER_TECHNIQUE_IDS_H",
    ])
    write(GEN / "digital-monster-technique-ids.h", technique_header)

    display = [
        "#ifndef DIGITAL_MONSTER_DISPLAY_NAMES_H",
        "#define DIGITAL_MONSTER_DISPLAY_NAMES_H",
        "",
        "// Full official Japanese display strings. These are pointer-backed on purpose;",
        "// do not copy them into POKEMON_NAME_LENGTH / MOVE_NAME_LENGTH fixed buffers.",
        "",
        f"static const u8 *const gDigitalMonsterSpeciesDisplayNames[{EXPECTED_SPECIES + 1}] =",
        "{",
        '    [0] = COMPOUND_STRING("-"),',
    ]
    for row in species:
        display.append(
            f'    [{row["emerald_species_id"]}] = COMPOUND_STRING("{c_escape(row["name_ja"])}"),'
        )
    display.extend([
        "};",
        "",
        f"static const u8 *const gDigitalMonsterTechniqueDisplayNames[{EXPECTED_TECHNIQUES + 1}] =",
        "{",
        '    [0] = COMPOUND_STRING("-"),',
    ])
    for row in techniques:
        display.append(
            f'    [{row["dm_technique_id"]}] = COMPOUND_STRING("{c_escape(row["name_ja"])}"),'
        )
    display.extend(["};", "", "#endif // DIGITAL_MONSTER_DISPLAY_NAMES_H"])
    write(GEN / "digital-monster-display-names.h", display)

    assignment_header = [
        "#ifndef DIGITAL_MONSTER_TECHNIQUE_ASSIGNMENTS_H",
        "#define DIGITAL_MONSTER_TECHNIQUE_ASSIGNMENTS_H",
        "",
        '#include "digital-monster-species-ids.h"',
        '#include "digital-monster-technique-ids.h"',
        "",
        "struct DigitalMonsterTechniqueAssignment",
        "{",
        "    unsigned short speciesId;",
        "    unsigned short logicalTechniqueId;",
        "    unsigned short runtimeMoveId;",
        "    unsigned char sourceOrder;",
        "};",
        "",
        "static const struct DigitalMonsterTechniqueAssignment gDigitalMonsterOfficialTechniqueAssignments[] =",
        "{",
    ]
    for row in assignments:
        owner = species_by_key[(row["source_kind"], row["source_id"])]
        assignment_header.append(
            f'    {{ {owner["emerald_species_id"]}, DM_TECHNIQUE_{int(row["dm_technique_id"]):04d}, '
            f'{row["emerald_runtime_move_id"]}, {row["move_order"]} }}, '
            f'/* {row["name_ja"]}: {row["move_ja"]} */'
        )
    assignment_header.extend([
        "};",
        "",
        "#define DM_OFFICIAL_TECHNIQUE_ASSIGNMENT_COUNT (sizeof(gDigitalMonsterOfficialTechniqueAssignments) / sizeof(gDigitalMonsterOfficialTechniqueAssignments[0]))",
        "",
        "#endif // DIGITAL_MONSTER_TECHNIQUE_ASSIGNMENTS_H",
    ])
    write(GEN / "digital-monster-technique-assignments.h", assignment_header)

    enum_lines = [
        "// Generated Digital Monster move enum fragment.",
        "// Included inside enum Move when DIGITAL_MONSTER_SERIES is enabled.",
    ]
    for tid in range(1, EXPECTED_TECHNIQUES + 1):
        suffix = " = MOVES_COUNT_DYNAMAX" if tid == 1 else ""
        enum_lines.append(f"DM_MOVE_{tid:04d}{suffix},")
    enum_lines.extend(["DM_MOVE_BOOTSTRAP_ATTACK,", "DM_MOVES_COUNT,"])
    write(POKE / "include/constants/digital_monster_move_enum.inc", enum_lines)

    runtime_path = GEN / "technique-runtime-map.csv"
    with runtime_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=[
            "dm_technique_id", "emerald_runtime_move_id", "name_ja",
            "first_source_kind", "mapping_status",
        ])
        writer.writeheader()
        for row in techniques:
            writer.writerow({
                **row,
                "emerald_runtime_move_id": RUNTIME_MOVE_OFFSET + int(row["dm_technique_id"]),
            })

    print("Digital Monster engine catalog generated")
    print(f"  species: {len(species)}")
    print(f"  techniques: {len(techniques)}")
    print(f"  assignments: {len(assignments)}")
    print("  gameplay interpretation fields: generated separately")


if __name__ == "__main__":
    main()
