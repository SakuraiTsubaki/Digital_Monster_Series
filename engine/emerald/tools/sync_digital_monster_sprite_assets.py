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
* reuses donor front/back/icon art without changing pixel indices;
* applies deterministic family palette presets to battle normal/shiny palettes;
* copies donor size/y-offset/icon-palette metadata;
* shares graphics per donor and palettes per (donor, preset) pair;
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

GRAPHICS_FIELDS = ("frontPic", "backPic", "iconSprite")
PALETTE_FIELDS = ("palette", "shinyPalette")
ALLOWED_PRESETS = {
    "base",
    "undead",
    "beast",
    "machine",
    "angel",
    "demon",
    "dragon",
    "aquatic",
    "insect",
    "holy",
    "dark",
}

# tint RGB, tint mix, saturation multiplier, brightness multiplier.
# These are intentionally moderate: donor pixel shapes and contrast remain intact.
PRESET_TUNING = {
    "undead": ((116, 105, 148), 0.32, 0.72, 0.88),
    "beast": ((166, 112, 58), 0.22, 1.08, 0.98),
    "machine": ((130, 155, 168), 0.32, 0.58, 1.02),
    "angel": ((224, 220, 190), 0.26, 0.68, 1.10),
    "demon": ((142, 54, 95), 0.34, 1.10, 0.84),
    "dragon": ((190, 82, 58), 0.22, 1.12, 0.96),
    "aquatic": ((58, 142, 205), 0.34, 1.03, 0.96),
    "insect": ((105, 160, 64), 0.30, 1.10, 0.94),
    "holy": ((222, 190, 88), 0.28, 0.90, 1.08),
    "dark": ((64, 63, 104), 0.40, 0.80, 0.76),
}

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
        preset = row["palette_preset"]
        if preset not in ALLOWED_PRESETS:
            raise SystemExit(
                f"{DONOR_MAP}: species {sid} has unsupported palette_preset {preset!r}"
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


def index_graphics_declarations(graphics_text: str) -> dict[str, str]:
    # The existing sync path already relies on Pokémon INCGFX declarations
    # being single-line statements. Index them once instead of rescanning the
    # multi-megabyte graphics table for every donor field.
    pattern = re.compile(
        r"\b([A-Za-z_][A-Za-z0-9_]*)\[\]\s*=\s*INCGFX_[^;]+;"
    )
    declarations: dict[str, str] = {}
    for line in graphics_text.splitlines():
        m = pattern.search(line)
        if m:
            declarations[m.group(1)] = line.strip()
    return declarations


def graphics_declaration(
    graphics_index: dict[str, str],
    symbol: str,
    alias: str,
) -> str:
    declaration = graphics_index.get(symbol)
    if declaration is None:
        raise SystemExit(f"graphics declaration not found for {symbol}")
    return declaration.replace(symbol, alias, 1)


def donor_alias(field: str, donor_id: int) -> str:
    stems = {
        "frontPic": "FrontPic",
        "backPic": "BackPic",
        "iconSprite": "Icon",
    }
    return f"gDigitalMonsterDonor{stems[field]}_{donor_id:03d}"


def palette_alias(field: str, donor_id: int, preset: str) -> str:
    stem = "Palette" if field == "palette" else "ShinyPalette"
    preset_name = preset[:1].upper() + preset[1:]
    return f"gDigitalMonsterDonor{stem}_{donor_id:03d}_{preset_name}"


def palette_source_path(graphics_index: dict[str, str], symbol: str) -> str:
    declaration = graphics_index.get(symbol)
    if declaration is None:
        raise SystemExit(f"graphics declaration not found for {symbol}")
    m = re.search(r'INCGFX_U16\("([^"]+\.pal)"', declaration)
    if not m:
        raise SystemExit(f"palette source path not found for {symbol}: {declaration}")
    return m.group(1)


def load_jasc_palette(path: Path) -> list[tuple[int, int, int]]:
    lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines()]
    if len(lines) < 4 or lines[0] != "JASC-PAL":
        raise SystemExit(f"{path}: expected JASC-PAL")
    try:
        count = int(lines[2])
    except ValueError as exc:
        raise SystemExit(f"{path}: invalid JASC-PAL color count") from exc
    rows = lines[3:3 + count]
    if len(rows) != count:
        raise SystemExit(f"{path}: truncated JASC-PAL")
    colors: list[tuple[int, int, int]] = []
    for row in rows:
        parts = row.split()
        if len(parts) != 3:
            raise SystemExit(f"{path}: invalid palette row {row!r}")
        rgb = tuple(int(value) for value in parts)
        if any(value < 0 or value > 255 for value in rgb):
            raise SystemExit(f"{path}: RGB value outside 0..255")
        colors.append(rgb)
    if len(colors) != 16:
        raise SystemExit(f"{path}: expected 16 colors, found {len(colors)}")
    return colors


def clamp8(value: float) -> int:
    return max(0, min(255, int(round(value))))


def transform_rgb(rgb: tuple[int, int, int], preset: str) -> tuple[int, int, int]:
    if preset == "base":
        return rgb

    tint, mix, saturation, brightness = PRESET_TUNING[preset]
    r, g, b = rgb
    luma = 0.299 * r + 0.587 * g + 0.114 * b

    # Keep near-black outlines near-black. For visible colors, retain donor
    # luminance/contrast while gently steering the palette toward its family.
    if max(rgb) <= 16:
        return tuple(clamp8(channel * brightness) for channel in rgb)

    saturated = (
        luma + (r - luma) * saturation,
        luma + (g - luma) * saturation,
        luma + (b - luma) * saturation,
    )
    mix_scale = min(1.0, max(0.0, (luma - 16.0) / 96.0))
    effective_mix = mix * mix_scale
    mixed = tuple(
        channel * (1.0 - effective_mix) + target * effective_mix
        for channel, target in zip(saturated, tint)
    )
    return tuple(clamp8(channel * brightness) for channel in mixed)


def gba_bgr555(rgb: tuple[int, int, int]) -> int:
    r, g, b = rgb
    return (r >> 3) | ((g >> 3) << 5) | ((b >> 3) << 10)


def palette_declaration(
    engine: Path,
    graphics_index: dict[str, str],
    symbol: str,
    alias: str,
    preset: str,
) -> str:
    if preset == "base":
        return graphics_declaration(graphics_index, symbol, alias)

    source = engine / palette_source_path(graphics_index, symbol)
    colors = load_jasc_palette(source)
    transformed = [colors[0]]
    transformed.extend(transform_rgb(rgb, preset) for rgb in colors[1:])
    values = [gba_bgr555(rgb) for rgb in transformed]
    rows = [
        ", ".join(f"0x{value:04X}" for value in values[i:i + 8])
        for i in range(0, len(values), 8)
    ]
    body = ",\n    ".join(rows)
    return f"const u16 {alias}[] = {{\n    {body},\n}};"


def build_donor_graphics_header(
    engine: Path,
    donor_blocks: dict[int, tuple[str, str]],
    used_donors: list[int],
    mapping: list[dict[str, str]],
) -> None:
    graphics_path = engine / "src/data/graphics/pokemon.h"
    graphics_text = graphics_path.read_text(encoding="utf-8")
    graphics_index = index_graphics_declarations(graphics_text)

    out = [
        "// Generated at build time from the stock Pokémon donor graphics.",
        "// One declaration set per donor is shared by all mapped Digital Monsters.",
        "// Authored Digital Monster sprite experiments are not activated here.",
        "",
    ]

    for donor_id in used_donors:
        constant, block = donor_blocks[donor_id]
        out.append(f"// donor graphics {donor_id}: {constant}")
        for field in GRAPHICS_FIELDS:
            symbol = pointer_symbol(block, field)
            alias = donor_alias(field, donor_id)
            out.append(graphics_declaration(graphics_index, symbol, alias))
        out.append("")

    palette_pairs = sorted(
        {(int(row["donor_species_id"]), row["palette_preset"]) for row in mapping}
    )
    out.append("// Battle palette variants; icon palettes remain stock donor metadata.")
    for donor_id, preset in palette_pairs:
        constant, block = donor_blocks[donor_id]
        out.append(f"// donor palette {donor_id}: {constant} / {preset}")
        for field in PALETTE_FIELDS:
            symbol = pointer_symbol(block, field)
            alias = palette_alias(field, donor_id, preset)
            out.append(
                palette_declaration(engine, graphics_index, symbol, alias, preset)
            )
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


def patch_species_info_text(
    text: str,
    species_id: int,
    donor_id: int,
    donor_block: str,
    palette_preset: str,
) -> str:
    start_marker = f"    [{species_id}] =\n    {{\n"
    start = text.find(start_marker)
    if start < 0:
        raise SystemExit(f"DM{species_id:04d}: species block not found")
    end = text.find("\n    }, /*", start)
    if end < 0:
        raise SystemExit(f"DM{species_id:04d}: end of species block not found")
    end += len("\n    },")

    block = text[start:end]

    for field in GRAPHICS_FIELDS:
        block = replace_field(
            block,
            field,
            donor_alias(field, donor_id),
            f"DM{species_id:04d}",
        )

    for field in PALETTE_FIELDS:
        block = replace_field(
            block,
            field,
            palette_alias(field, donor_id, palette_preset),
            f"DM{species_id:04d}",
        )

    for field in COPY_FIELDS:
        block = replace_field(
            block,
            field,
            field_value(donor_block, field),
            f"DM{species_id:04d}",
        )

    return text[:start] + block + text[end:]


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

    build_donor_graphics_header(engine, donor_blocks, used_donors, mapping)

    species_dir = engine / "src/data/pokemon/species_info"
    part_texts = {
        f"digital_monster_part_{part}.h": (
            species_dir / f"digital_monster_part_{part}.h"
        ).read_text(encoding="utf-8")
        for part in range(1, 5)
    }

    family_counts: dict[str, int] = {}
    for row in mapping:
        species_id = int(row["species_id"])
        donor_id = int(row["donor_species_id"])
        _, donor_block = donor_blocks[donor_id]
        part = species_part(species_id)
        part_texts[part] = patch_species_info_text(
            part_texts[part],
            species_id,
            donor_id,
            donor_block,
            row["palette_preset"],
        )
        family = row["sprite_family"]
        family_counts[family] = family_counts.get(family, 0) + 1

    for part, text_value in part_texts.items():
        (species_dir / part).write_text(text_value, encoding="utf-8")

    verify_no_placeholders(engine)

    print("Digital Monster donor sprite sync complete")
    print(f"  runtime species patched: {len(mapping)}")
    print(f"  unique Pokémon donors: {len(used_donors)}")
    print("  front/back/icon placeholders remaining: 0")
    preset_counts: dict[str, int] = {}
    for row in mapping:
        preset = row["palette_preset"]
        preset_counts[preset] = preset_counts.get(preset, 0) + 1
    print("  palette mode: donor family presets for battle normal/shiny palettes")
    print("  palette presets: " + ", ".join(
        f"{name}={count}" for name, count in sorted(preset_counts.items())
    ))
    print("  icon palette mode: stock donor iconPalIndex")
    print("  authored Digital Monster sprite experiments: provenance only")
    print("  family classifications: " + ", ".join(
        f"{name}={count}" for name, count in sorted(family_counts.items())
    ))


if __name__ == "__main__":
    main()
