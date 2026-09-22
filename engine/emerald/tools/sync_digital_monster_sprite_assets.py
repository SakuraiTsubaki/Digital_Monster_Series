#!/usr/bin/env python3
"""Apply the donor-Pokémon sprite baseline to a pinned pokeemerald-expansion checkout.

Digital Monster runtime species keep their own stats, names and learnsets, but
battle graphics are borrowed from stock Pokémon donors.  The explicit mapping
lives in generated/donor-sprite-map.csv.

The former authored-Digimon sprite experiment under assets/gameplay-v0/sprites
is intentionally *not* activated here.  Those files are provenance/reference
only unless a future per-species override is explicitly enabled.

For the baseline this tool:
* patches all DM0001..DM1468 SpeciesInfo graphics fields;
* reuses donor front/back/icon art and donor normal/shiny palettes;
* copies donor size/y-offset/icon-palette metadata;
* emits one graphics declaration set per actually-used donor, not per DM;
* leaves the stock shared icon-palette runtime intact.
"""
from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
EMERALD = PROJECT_ROOT / "engine" / "emerald"
DONOR_MAP = EMERALD / "generated" / "donor-sprite-map.csv"

DM_COUNT = 1468
DONOR_MIN = 1
DONOR_MAX = 386

POINTER_FIELDS = ("frontPic", "backPic", "palette", "shinyPalette", "iconSprite")
COPY_FIELDS = (
    "frontPicSize",
    "frontPicYOffset",
    "backPicSize",
    "backPicYOffset",
    "iconPalIndex",
)


def species_part(species_id: int) -> str:
    if 1 <= species_id <= 367:
        return "digital_monster_part_1.h"
    if species_id <= 734:
        return "digital_monster_part_2.h"
    if species_id <= 1101:
        return "digital_monster_part_3.h"
    if species_id <= 1468:
        return "digital_monster_part_4.h"
    raise SystemExit(f"invalid Digital Monster species id {species_id}")


def load_mapping() -> list[dict[str, str]]:
    with DONOR_MAP.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))

    if len(rows) != DM_COUNT:
        raise SystemExit(f"{DONOR_MAP}: expected {DM_COUNT} rows, found {len(rows)}")

    ids = [int(row["species_id"]) for row in rows]
    if ids != list(range(1, DM_COUNT + 1)):
        raise SystemExit(f"{DONOR_MAP}: species IDs must be exactly 1..{DM_COUNT}")

    for row in rows:
        sid = int(row["species_id"])
        expected = f"DM{sid:04d}"
        if row["internal_name"] != expected:
            raise SystemExit(
                f"{DONOR_MAP}: species {sid} internal_name is {row['internal_name']!r}, expected {expected}"
            )
        donor_id = int(row["donor_species_id"])
        if not DONOR_MIN <= donor_id <= DONOR_MAX:
            raise SystemExit(
                f"{DONOR_MAP}: species {sid} donor {donor_id} outside {DONOR_MIN}..{DONOR_MAX}"
            )
        if row["palette_preset"] != "base":
            raise SystemExit(
                f"{DONOR_MAP}: baseline only accepts palette_preset=base; "
                f"species {sid} has {row['palette_preset']!r}"
            )

    return rows


def parse_species_enum(engine: Path) -> dict[str, int]:
    text = (engine / "include/constants/species.h").read_text(encoding="utf-8")
    values: dict[str, int] = {}
    aliases: dict[str, str] = {}

    for raw in text.splitlines():
        m = re.match(r"\s*(SPECIES_[A-Z0-9_]+)\s*=\s*([^,]+),", raw)
        if not m:
            continue
        name, rhs = m.groups()
        rhs = rhs.strip()
        if rhs.isdigit():
            values[name] = int(rhs)
        elif re.fullmatch(r"SPECIES_[A-Z0-9_]+", rhs):
            aliases[name] = rhs

    pending = dict(aliases)
    while pending:
        progress = False
        for name, target in list(pending.items()):
            if target in values:
                values[name] = values[target]
                del pending[name]
                progress = True
        if not progress:
            break

    return values


def load_donor_blocks(
    engine: Path,
    enum_values: dict[str, int],
    required_donors: set[int],
) -> dict[int, tuple[str, str]]:
    donors: dict[int, tuple[str, str]] = {}
    base = engine / "src/data/pokemon/species_info"

    for gen in (1, 2, 3):
        path = base / f"gen_{gen}_families.h"
        text = path.read_text(encoding="utf-8")
        for m in re.finditer(
            r"^\s*\[(SPECIES_[A-Z0-9_]+)\]\s*=\s*\n\s*\{\n",
            text,
            flags=re.M,
        ):
            constant = m.group(1)
            donor_id = enum_values.get(constant)
            if donor_id is None or not DONOR_MIN <= donor_id <= DONOR_MAX:
                continue

            end = text.find("\n    },", m.end())
            if end < 0:
                raise SystemExit(f"{path}: could not find end of {constant} block")
            end += len("\n    },")

            donors.setdefault(donor_id, (constant, text[m.start():end]))

    missing = sorted(required_donors.difference(donors))
    if missing:
        raise SystemExit(
            "used donors missing conventional Gen I-III SpeciesInfo blocks: "
            + ", ".join(str(x) for x in missing[:20])
            + (" ..." if len(missing) > 20 else "")
        )
    return donors


def field_value(block: str, field: str) -> str:
    m = re.search(
        rf"^\s*\.{re.escape(field)}\s*=\s*(.+),\s*$",
        block,
        flags=re.M,
    )
    if not m:
        raise SystemExit(f"donor block missing .{field}")
    return m.group(1).strip()


def pointer_symbol(block: str, field: str) -> str:
    value = field_value(block, field)
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
        raise SystemExit(f"donor .{field} is not a direct symbol: {value}")
    return value


def graphics_declaration(graphics_text: str, symbol: str, alias: str) -> str:
    # Gen I-III Pokémon graphics declarations are one-statement INCGFX
    # definitions.  Pull the exact upstream path/format and only rename the
    # symbol, so the donor art remains byte-for-byte sourced from upstream.
    pattern = rf"[^\n;]*\b{re.escape(symbol)}\[\]\s*=\s*INCGFX_[^;]+;"
    m = re.search(pattern, graphics_text)
    if not m:
        raise SystemExit(f"graphics declaration not found for {symbol}")
    declaration = m.group(0).strip()
    return declaration.replace(symbol, alias, 1)


def donor_alias(field: str, donor_id: int) -> str:
    stems = {
        "frontPic": "FrontPic",
        "backPic": "BackPic",
        "palette": "Palette",
        "shinyPalette": "ShinyPalette",
        "iconSprite": "Icon",
    }
    return f"gDigitalMonsterDonor{stems[field]}_{donor_id:03d}"


def build_donor_graphics_header(
    engine: Path,
    donor_blocks: dict[int, tuple[str, str]],
    used_donors: list[int],
) -> None:
    graphics_path = engine / "src/data/graphics/pokemon.h"
    graphics_text = graphics_path.read_text(encoding="utf-8")

    out = [
        "// Generated at build time from the stock Pokémon donor graphics.",
        "// One declaration set per donor is shared by all mapped Digital Monsters.",
        "// Authored Digital Monster sprite experiments are not activated here.",
        "",
    ]

    for donor_id in used_donors:
        constant, block = donor_blocks[donor_id]
        out.append(f"// donor {donor_id}: {constant}")
        for field in POINTER_FIELDS:
            symbol = pointer_symbol(block, field)
            alias = donor_alias(field, donor_id)
            out.append(graphics_declaration(graphics_text, symbol, alias))
        out.append("")

    path = engine / "src/data/graphics/digital_monster.h"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")


def replace_field(block: str, field: str, value: str, label: str) -> str:
    pattern = rf"(^\s*\.{re.escape(field)}\s*=\s*).+(,\s*$)"
    out, count = re.subn(pattern, rf"\g<1>{value}\g<2>", block, count=1, flags=re.M)
    if count != 1:
        raise SystemExit(f"{label}: expected one .{field}, found {count}")
    return out


def patch_species_info(
    engine: Path,
    species_id: int,
    donor_id: int,
    donor_block: str,
) -> None:
    path = engine / "src/data/pokemon/species_info" / species_part(species_id)
    text = path.read_text(encoding="utf-8")
    start_marker = f"    [{species_id}] =\n    {{\n"
    start = text.find(start_marker)
    if start < 0:
        raise SystemExit(f"{path}: species block {species_id} not found")
    end = text.find("\n    }, /*", start)
    if end < 0:
        raise SystemExit(f"{path}: end of species block {species_id} not found")
    end += len("\n    },")

    block = text[start:end]

    for field in POINTER_FIELDS:
        block = replace_field(
            block,
            field,
            donor_alias(field, donor_id),
            f"DM{species_id:04d}",
        )

    for field in COPY_FIELDS:
        block = replace_field(
            block,
            field,
            field_value(donor_block, field),
            f"DM{species_id:04d}",
        )

    path.write_text(text[:start] + block + text[end:], encoding="utf-8")


def verify_no_placeholders(engine: Path) -> None:
    species_dir = engine / "src/data/pokemon/species_info"
    text = "\n".join(
        (species_dir / f"digital_monster_part_{part}.h").read_text(encoding="utf-8")
        for part in range(1, 5)
    )
    forbidden = {
        "front": "gMonFrontPic_CircledQuestionMark",
        "back": "gMonBackPic_CircledQuestionMark",
        "palette": "gMonPalette_CircledQuestionMark",
        "shiny palette": "gMonShinyPalette_CircledQuestionMark",
        "icon": "gMonIcon_QuestionMark",
    }
    remaining = {label: text.count(symbol) for label, symbol in forbidden.items()}
    remaining = {k: v for k, v in remaining.items() if v}
    if remaining:
        raise SystemExit(f"Digital Monster sprite placeholders remain: {remaining}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("engine", type=Path)
    args = parser.parse_args()
    engine = args.engine.resolve()

    mapping = load_mapping()
    used_donors = sorted({int(row["donor_species_id"]) for row in mapping})
    enum_values = parse_species_enum(engine)
    donor_blocks = load_donor_blocks(engine, enum_values, set(used_donors))

    build_donor_graphics_header(engine, donor_blocks, used_donors)

    family_counts: dict[str, int] = {}
    for row in mapping:
        species_id = int(row["species_id"])
        donor_id = int(row["donor_species_id"])
        _, donor_block = donor_blocks[donor_id]
        patch_species_info(engine, species_id, donor_id, donor_block)
        family = row["sprite_family"]
        family_counts[family] = family_counts.get(family, 0) + 1

    verify_no_placeholders(engine)

    print("Digital Monster donor sprite sync complete")
    print(f"  runtime species patched: {len(mapping)}")
    print(f"  unique Pokémon donors: {len(used_donors)}")
    print("  front/back/icon placeholders remaining: 0")
    print("  palette mode: donor base palettes")
    print("  authored Digital Monster sprite experiments: provenance only")
    print("  family classifications: " + ", ".join(
        f"{name}={count}" for name, count in sorted(family_counts.items())
    ))


if __name__ == "__main__":
    main()
