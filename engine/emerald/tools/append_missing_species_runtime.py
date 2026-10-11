#!/usr/bin/env python3
"""Append runtime scaffolding for newly mapped entities without renumbering IDs."""
from __future__ import annotations

import argparse
import csv
import re
from collections import defaultdict
from pathlib import Path


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def species_block(row: dict[str, str]) -> str:
    sid = int(row["species_id"])
    types = row["battle_type_1"]
    if row["battle_type_2"]:
        types += ", " + row["battle_type_2"]
    return f"""    [{sid}] =
    {{
        .baseHP        = {row['base_hp']},
        .baseAttack    = {row['base_attack']},
        .baseDefense   = {row['base_defense']},
        .baseSpeed     = {row['base_speed']},
        .baseSpAttack  = {row['base_sp_attack']},
        .baseSpDefense = {row['base_sp_defense']},
        .types = MON_TYPES({types}),
        .catchRate = {row['catch_rate']},
        .expYield = {row['exp_yield']},
        .evYield_HP = {row['ev_yield_hp']},
        .evYield_Attack = {row['ev_yield_attack']},
        .evYield_Defense = {row['ev_yield_defense']},
        .evYield_Speed = {row['ev_yield_speed']},
        .evYield_SpAttack = {row['ev_yield_sp_attack']},
        .evYield_SpDefense = {row['ev_yield_sp_defense']},
        .genderRatio = PERCENT_FEMALE(50),
        .eggCycles = 20,
        .friendship = STANDARD_FRIENDSHIP,
        .growthRate = {row['growth_rate']},
        .eggGroups = MON_EGG_GROUPS(EGG_GROUP_NO_EGGS_DISCOVERED),
        .abilities = {{ {row['ability_1']}, {row['ability_2']}, {row['ability_hidden']} }},
        .bodyColor = BODY_COLOR_GRAY,
        .noFlip = TRUE,
        .speciesName = _("DM{sid:04d}"),
        .cryId = CRY_PORYGON,
        .natDexNum = NATIONAL_DEX_NONE,
        .categoryName = _("Digital"),
        .height = 0,
        .weight = 0,
        .description = gFallbackPokedexText,
        .pokemonScale = 256,
        .pokemonOffset = 0,
        .trainerScale = 256,
        .trainerOffset = 0,
        .frontPic = gMonFrontPic_CircledQuestionMark,
        .frontPicSize = MON_COORDS_SIZE(40, 40),
        .frontPicYOffset = 12,
        .frontAnimFrames = sAnims_TwoFramePlaceHolder,
        .frontAnimId = ANIM_V_SQUISH_AND_BOUNCE,
        .backPic = gMonBackPic_CircledQuestionMark,
        .backPicSize = MON_COORDS_SIZE(40, 40),
        .backPicYOffset = 12,
        .backAnimId = BACK_ANIM_NONE,
        .palette = gMonPalette_CircledQuestionMark,
        .shinyPalette = gMonShinyPalette_CircledQuestionMark,
        .iconSprite = gMonIcon_QuestionMark,
        .iconPalIndex = 0,
        .pokemonJumpType = PKMN_JUMP_TYPE_NONE,
        SHADOW(-1, 0, SHADOW_SIZE_M)
        .levelUpLearnset = sDigitalMonster{sid:04d}LevelUpLearnset,
        .teachableLearnset = sNoneTeachableLearnset,
        .eggMoveLearnset = sNoneEggMoveLearnset,
    }}, /* {row['name_ja']} | profile_derived_v1_noncanonical */
"""


def learnset_block(sid: int, assignments: list[dict[str, str]]) -> str:
    lines = [
        f"static const struct LevelUpMove sDigitalMonster{sid:04d}LevelUpLearnset[] = {{"
    ]
    if assignments:
        for assignment in sorted(assignments, key=lambda x: int(x["move_order"])):
            level = 1 + (int(assignment["move_order"]) - 1) * 9
            tid = int(assignment["dm_technique_id"])
            lines.append(
                f"    LEVEL_UP_MOVE({level:2d}, DM_MOVE_{tid:04d}), /* {assignment['move_ja']} */"
            )
    else:
        lines.append("    LEVEL_UP_MOVE( 1, DM_MOVE_BOOTSTRAP_ATTACK),")
    lines.extend(["    LEVEL_UP_END", "};", ""])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--parameters", type=Path, required=True)
    parser.add_argument("--species-dir", type=Path, required=True)
    parser.add_argument("--learnset-dir", type=Path, required=True)
    parser.add_argument("--assignments", type=Path, required=True)
    args = parser.parse_args()

    params = rows(args.parameters)
    by_id = {int(row["species_id"]): row for row in params}
    assignment_rows = rows(args.assignments)
    assignments_by_key: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in assignment_rows:
        assignments_by_key[(row["source_kind"], row["source_id"])].append(row)

    species_paths = sorted(args.species_dir.glob("digital_monster_part_*.h"))
    learnset_paths = sorted(args.learnset_dir.glob("digital_monster_part_*.h"))
    if not species_paths or not learnset_paths:
        raise SystemExit("generated SpeciesInfo or learnset parts are missing")
    species_text = "\n".join(path.read_text(encoding="utf-8") for path in species_paths)
    learnset_text = "\n".join(path.read_text(encoding="utf-8") for path in learnset_paths)
    existing_species = {int(x) for x in re.findall(r"^\s*\[(\d+)\]\s*=", species_text, re.M)}
    existing_learnsets = {int(x) for x in re.findall(r"sDigitalMonster(\d{4})LevelUpLearnset", learnset_text)}
    missing_species = sorted(set(by_id) - existing_species)
    missing_learnsets = sorted(set(by_id) - existing_learnsets)
    if missing_species != missing_learnsets:
        raise SystemExit("SpeciesInfo and learnset missing-ID sets differ")

    if missing_species:
        species_last = species_paths[-1]
        learnset_last = learnset_paths[-1]
        species_last.write_text(
            species_last.read_text(encoding="utf-8").rstrip()
            + "\n"
            + "".join(species_block(by_id[sid]) for sid in missing_species),
            encoding="utf-8",
        )
        learnset_last.write_text(
            learnset_last.read_text(encoding="utf-8").rstrip()
            + "\n\n"
            + "\n".join(
                learnset_block(
                    sid,
                    assignments_by_key[(by_id[sid]["source_kind"], by_id[sid]["source_id"])],
                )
                for sid in missing_species
            ),
            encoding="utf-8",
        )

    print(f"Runtime scaffolding appended for {len(missing_species)} species")


if __name__ == "__main__":
    main()
