#!/usr/bin/env python3
"""Apply profile-derived species parameters to generated pokeemerald-expansion SpeciesInfo."""
from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path

FIELD_PATTERNS = {
    "base_hp": r"(?m)^(\s*\.baseHP\s*=\s*)\d+(,)$",
    "base_attack": r"(?m)^(\s*\.baseAttack\s*=\s*)\d+(,)$",
    "base_defense": r"(?m)^(\s*\.baseDefense\s*=\s*)\d+(,)$",
    "base_speed": r"(?m)^(\s*\.baseSpeed\s*=\s*)\d+(,)$",
    "base_sp_attack": r"(?m)^(\s*\.baseSpAttack\s*=\s*)\d+(,)$",
    "base_sp_defense": r"(?m)^(\s*\.baseSpDefense\s*=\s*)\d+(,)$",
    "catch_rate": r"(?m)^(\s*\.catchRate\s*=\s*)\d+(,)$",
    "exp_yield": r"(?m)^(\s*\.expYield\s*=\s*)\d+(,)$",
    "growth_rate": r"(?m)^(\s*\.growthRate\s*=\s*)GROWTH_[A-Z_]+(,)$",
}


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def replace_one(block: str, pattern: str, value: str, label: str) -> str:
    block2, count = re.subn(pattern, rf"\g<1>{value}\g<2>", block, count=1)
    if count != 1:
        raise SystemExit(f"{label}: expected one match, found {count}")
    return block2


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--parameters", type=Path, required=True)
    ap.add_argument("--species-dir", type=Path, required=True)
    args = ap.parse_args()

    params = rows(args.parameters)
    if len(params) != 1468:
        raise SystemExit(f"expected 1468 parameter rows, got {len(params)}")
    by_id = {int(x["species_id"]): x for x in params}
    if sorted(by_id) != list(range(1, 1469)):
        raise SystemExit("parameter IDs are not 1..1468")

    paths = sorted(args.species_dir.glob("digital_monster_part_*.h"))
    if not paths:
        raise SystemExit("no Digital Monster SpeciesInfo part files found")

    applied: set[int] = set()
    block_re = re.compile(
        r"(?ms)^(\s*\[(\d+)\]\s*=\s*\n\s*\{.*?^\s*\},\s*/\*.*?\*/\s*)$"
    )

    for path in paths:
        text = path.read_text(encoding="utf-8")

        def repl(match: re.Match[str]) -> str:
            block = match.group(1)
            sid = int(match.group(2))
            if sid not in by_id:
                return block
            row = by_id[sid]
            if sid in applied:
                raise SystemExit(f"species {sid}: duplicate SpeciesInfo block")

            for field, pattern in FIELD_PATTERNS.items():
                block = replace_one(block, pattern, row[field], f"species {sid} {field}")

            type_args = row["battle_type_1"]
            if row["battle_type_2"]:
                type_args += ", " + row["battle_type_2"]
            block, count = re.subn(
                r"(?m)^(\s*\.types\s*=\s*)MON_TYPES\([^)]*\)(,)$",
                rf"\g<1>MON_TYPES({type_args})\g<2>",
                block,
                count=1,
            )
            if count != 1:
                raise SystemExit(f"species {sid} types: expected one match, found {count}")

            ev_fields = [
                ("evYield_HP", "ev_yield_hp"),
                ("evYield_Attack", "ev_yield_attack"),
                ("evYield_Defense", "ev_yield_defense"),
                ("evYield_Speed", "ev_yield_speed"),
                ("evYield_SpAttack", "ev_yield_sp_attack"),
                ("evYield_SpDefense", "ev_yield_sp_defense"),
            ]
            if re.search(r"(?m)^\s*\.evYield_HP\s*=", block):
                for c_field, csv_field in ev_fields:
                    block, count = re.subn(
                        rf"(?m)^(\s*\.{c_field}\s*=\s*)\d+(,)$",
                        rf"\g<1>{row[csv_field]}\g<2>",
                        block,
                        count=1,
                    )
                    if count != 1:
                        raise SystemExit(
                            f"species {sid} {c_field}: expected one match, found {count}"
                        )
            else:
                ev_lines = "".join(
                    f"        .{c_field} = {row[csv_field]},\n"
                    for c_field, csv_field in ev_fields
                )
                block, count = re.subn(
                    r"(?m)^(\s*\.expYield\s*=\s*\d+,\n)",
                    lambda m: m.group(1) + ev_lines,
                    block,
                    count=1,
                )
                if count != 1:
                    raise SystemExit(
                        f"species {sid} EV insertion: expected one expYield match, found {count}"
                    )

            ability_args = ", ".join(
                [row["ability_1"], row["ability_2"], row["ability_hidden"]]
            )
            block, count = re.subn(
                r"(?m)^(\s*\.abilities\s*=\s*)\{[^}]*\}(,)$",
                rf"\g<1>{{ {ability_args} }}\g<2>",
                block,
                count=1,
            )
            if count != 1:
                raise SystemExit(f"species {sid} abilities: expected one match, found {count}")

            block = block.replace(
                "project_generated_gameplay_v0_noncanonical",
                "profile_derived_v1_noncanonical",
            )
            applied.add(sid)
            return block

        new_text = block_re.sub(repl, text)
        new_text = new_text.replace(
            "// Generated gameplay-v0 SpeciesInfo entries",
            "// Generated profile-derived-v1 SpeciesInfo entries",
        )
        path.write_text(new_text, encoding="utf-8")

    if applied != set(range(1, 1469)):
        missing = sorted(set(range(1, 1469)) - applied)
        raise SystemExit(f"SpeciesInfo parameters not applied for: {missing[:20]}")

    print("Profile-derived parameters applied to SpeciesInfo")
    print(f"  entries updated: {len(applied)}")
    print(f"  source: {args.parameters}")


if __name__ == "__main__":
    main()
