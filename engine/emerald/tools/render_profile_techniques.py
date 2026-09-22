#!/usr/bin/env python3
"""Render all 2,557 profile-derived Digital Monster MoveInfo entries."""
from __future__ import annotations

import argparse
import csv
from pathlib import Path


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def c_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--parameters", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()

    data = rows(args.parameters)
    if len(data) != 2557:
        raise SystemExit(f"expected 2557 technique rows, got {len(data)}")

    out: list[str] = []
    out.append("// Generated profile-derived-v1 Digital Monster MoveInfo entries.")
    out.append("// Official Japanese technique names are preserved; gameplay values are project interpretations.")
    out.append("")

    for row in data:
        move_id = int(row["dm_technique_id"])
        name = c_escape(row["name_ja"])
        out.extend([
            f"    [DM_MOVE_{move_id:04d}] =",
            "    {",
            f'        .name = COMPOUND_STRING("{name}"),',
            '        .description = COMPOUND_STRING("Profile-derived Digital Monster technique."),',
            f'        .effect = {row["effect"]},',
            f'        .power = {row["power"]},',
            f'        .type = {row["type"]},',
            f'        .accuracy = {row["accuracy"]},',
            f'        .pp = {row["pp"]},',
            f'        .target = {row["target"]},',
            f'        .priority = {row["priority"]},',
            f'        .category = {row["category"]},',
        ])
        if row["effect_argument"]:
            out.append(f'        {row["effect_argument"]}')
        if row["makes_contact"] == "true":
            out.append("        .makesContact = TRUE,")
        if row["effect"] == "EFFECT_RESTORE_HP":
            out.append("        .healingMove = TRUE,")
            out.append("        .snatchAffected = TRUE,")
        if row["effect"] == "EFFECT_PROTECT":
            out.append("        .ignoresProtect = TRUE,")
        out.extend([
            "        .battleAnimScript = gBattleAnimMove_Pound,",
            f'    }}, /* {name} | {row["derivation_version"]} | {row["effect_status"]} */',
            "",
        ])

    out.extend([
        "    [DM_MOVE_BOOTSTRAP_ATTACK] =",
        "    {",
        '        .name = COMPOUND_STRING("DM-Bootstrap"),',
        '        .description = COMPOUND_STRING("Temporary fallback attack."),',
        "        .effect = EFFECT_HIT,",
        "        .power = 40,",
        "        .type = TYPE_NORMAL,",
        "        .accuracy = 100,",
        "        .pp = 35,",
        "        .target = TARGET_SELECTED,",
        "        .priority = 0,",
        "        .category = DAMAGE_CATEGORY_PHYSICAL,",
        "        .battleAnimScript = gBattleAnimMove_Pound,",
        "    },",
        "",
    ])

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(out), encoding="utf-8")
    print("Profile-derived MoveInfo rendered")
    print(f"  technique entries: {len(data)}")
    print("  bootstrap entries: 1")
    print(f"  output: {args.output}")


if __name__ == "__main__":
    main()
