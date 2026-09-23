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
* leaves the stock shared icon-palette runtime intact;
* optionally activates an authored front/back/palette set only when override_asset explicitly names it.
"""
from __future__ import annotations

import argparse
import binascii
import csv
import json
import re
import shutil
import struct
import zlib
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
EMERALD = PROJECT_ROOT / "engine" / "emerald"
DONOR_MAP = EMERALD / "generated" / "donor-sprite-map.csv"
CATALOG_PATH = EMERALD / "generated" / "sprite-catalog.json"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"

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



def png_chunk(kind: bytes, payload: bytes) -> bytes:
    crc = binascii.crc32(kind)
    crc = binascii.crc32(payload, crc) & 0xFFFFFFFF
    return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", crc)


def paeth(a: int, b: int, c: int) -> int:
    p = a + b - c
    pa = abs(p - a)
    pb = abs(p - b)
    pc = abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    if pb <= pc:
        return b
    return c


def duplicate_indexed_png_frame(src: Path, dst: Path) -> None:
    data = src.read_bytes()
    if not data.startswith(PNG_SIGNATURE):
        raise SystemExit(f"{src}: not a PNG file")

    pos = len(PNG_SIGNATURE)
    chunks: list[tuple[bytes, bytes]] = []
    idat = bytearray()
    width = height = bit_depth = color_type = None
    compression = filter_method = interlace = None

    while pos + 12 <= len(data):
        length = struct.unpack(">I", data[pos:pos + 4])[0]
        kind = data[pos + 4:pos + 8]
        payload = data[pos + 8:pos + 8 + length]
        pos += 12 + length
        if kind == b"IHDR":
            width, height, bit_depth, color_type, compression, filter_method, interlace = struct.unpack(
                ">IIBBBBB", payload
            )
        elif kind == b"IDAT":
            idat.extend(payload)
        elif kind != b"IEND":
            chunks.append((kind, payload))
        if kind == b"IEND":
            break

    if None in (width, height, bit_depth, color_type, compression, filter_method, interlace):
        raise SystemExit(f"{src}: missing IHDR")
    if color_type != 3:
        raise SystemExit(f"{src}: front override must be indexed-color PNG")
    if interlace != 0:
        raise SystemExit(f"{src}: interlaced PNG is not supported")
    if width != 64 or height != 64:
        raise SystemExit(f"{src}: expected 64x64 front override, found {width}x{height}")

    row_bytes = (width * bit_depth + 7) // 8
    bpp = max(1, (bit_depth + 7) // 8)
    raw = zlib.decompress(bytes(idat))
    stride = 1 + row_bytes
    if len(raw) != height * stride:
        raise SystemExit(f"{src}: unexpected decompressed PNG size")

    rows: list[bytes] = []
    prev = bytearray(row_bytes)
    for y in range(height):
        scan = raw[y * stride:(y + 1) * stride]
        filter_type = scan[0]
        source = scan[1:]
        recon = bytearray(row_bytes)
        for x, value in enumerate(source):
            left = recon[x - bpp] if x >= bpp else 0
            up = prev[x]
            upper_left = prev[x - bpp] if x >= bpp else 0
            if filter_type == 0:
                result = value
            elif filter_type == 1:
                result = (value + left) & 0xFF
            elif filter_type == 2:
                result = (value + up) & 0xFF
            elif filter_type == 3:
                result = (value + ((left + up) // 2)) & 0xFF
            elif filter_type == 4:
                result = (value + paeth(left, up, upper_left)) & 0xFF
            else:
                raise SystemExit(f"{src}: unsupported PNG filter {filter_type}")
            recon[x] = result
        rows.append(bytes(recon))
        prev = recon

    doubled = b"".join(b"\x00" + row for row in (rows + rows))
    ihdr = struct.pack(
        ">IIBBBBB",
        width,
        height * 2,
        bit_depth,
        color_type,
        compression,
        filter_method,
        interlace,
    )

    out = bytearray(PNG_SIGNATURE)
    out.extend(png_chunk(b"IHDR", ihdr))
    for kind, payload in chunks:
        if kind != b"IHDR":
            out.extend(png_chunk(kind, payload))
    out.extend(png_chunk(b"IDAT", zlib.compress(doubled, level=9)))
    out.extend(png_chunk(b"IEND", b""))
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(out)


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


def load_override_catalog() -> dict[str, dict]:
    data = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    entries: dict[str, dict] = {}
    for entry in data.get("entries", []):
        internal = entry.get("internal_name")
        if not isinstance(internal, str) or not internal:
            raise SystemExit(f"{CATALOG_PATH}: override catalog entry missing internal_name")
        if internal in entries:
            raise SystemExit(f"{CATALOG_PATH}: duplicate override catalog entry {internal}")
        entries[internal] = entry
    return entries


def resolve_overrides(mapping: list[dict[str, str]]) -> dict[int, dict]:
    catalog = load_override_catalog()
    active: dict[int, dict] = {}

    for row in mapping:
        override = row["override_asset"].strip()
        if not override:
            continue

        species_id = int(row["species_id"])
        internal = row["internal_name"]
        if override != internal:
            raise SystemExit(
                f"{DONOR_MAP}: {internal} override_asset must be its own internal name, got {override!r}"
            )

        entry = catalog.get(override)
        if entry is None:
            raise SystemExit(
                f"{DONOR_MAP}: {internal} override_asset {override!r} has no sprite-catalog entry"
            )
        if int(entry.get("species_id", -1)) != species_id:
            raise SystemExit(f"{CATALOG_PATH}: {override} species_id does not match donor map")

        assets = entry.get("assets")
        if not isinstance(assets, dict):
            raise SystemExit(f"{CATALOG_PATH}: {override} has no assets object")
        missing = [
            key for key in ("front", "back", "normal_palette")
            if not isinstance(assets.get(key), dict) or not assets[key].get("path")
        ]
        if missing:
            raise SystemExit(
                f"{DONOR_MAP}: {internal} override requires front/back/normal_palette; "
                f"missing {', '.join(missing)}"
            )
        active[species_id] = entry

    return active


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


def override_alias(field: str, internal_name: str) -> str:
    stems = {
        "frontPic": "FrontPic",
        "backPic": "BackPic",
        "palette": "Palette",
    }
    return f"gDigitalMonsterOverride{stems[field]}_{internal_name}"


def materialize_override_assets(engine: Path, entry: dict) -> list[str]:
    internal = entry["internal_name"]
    slug = internal.lower()
    assets = entry["assets"]
    out_dir = engine / "graphics" / "digital_monster" / "overrides" / slug
    out_dir.mkdir(parents=True, exist_ok=True)

    front_src = EMERALD / assets["front"]["path"]
    back_src = EMERALD / assets["back"]["path"]
    palette_src = EMERALD / assets["normal_palette"]["path"]

    duplicate_indexed_png_frame(front_src, out_dir / "anim_front.png")
    shutil.copyfile(back_src, out_dir / "back.png")
    shutil.copyfile(palette_src, out_dir / "normal.pal")

    base = f"graphics/digital_monster/overrides/{slug}"
    return [
        f'const u32 {override_alias("frontPic", internal)}[] = '
        f'INCGFX_U32("{base}/anim_front.png", ".4bpp.smol");',
        f'const u32 {override_alias("backPic", internal)}[] = '
        f'INCGFX_U32("{base}/back.png", ".4bpp.smol");',
        f'const u16 {override_alias("palette", internal)}[] = '
        f'INCGFX_U16("{base}/normal.pal", ".gbapal");',
        "",
    ]


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
    active_overrides: dict[int, dict],
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

    out.append("// Explicit per-species battle overrides; icons stay on donor Pokémon.")
    for species_id in sorted(active_overrides):
        entry = active_overrides[species_id]
        out.append(f"// species override {species_id}: {entry['internal_name']}")
        out.extend(materialize_override_assets(engine, entry))

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
    override_entry: dict | None,
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

    label = f"DM{species_id:04d}"
    internal = override_entry["internal_name"] if override_entry is not None else None

    for field in ("frontPic", "backPic"):
        value = (
            override_alias(field, internal)
            if internal is not None
            else donor_alias(field, donor_id)
        )
        block = replace_field(block, field, value, label)

    # Icons deliberately remain donor-backed even when battle art is overridden.
    block = replace_field(block, "iconSprite", donor_alias("iconSprite", donor_id), label)

    if internal is not None:
        override_palette = override_alias("palette", internal)
        block = replace_field(block, "palette", override_palette, label)
        block = replace_field(block, "shinyPalette", override_palette, label)
        for field, value in (
            ("frontPicSize", "MON_COORDS_SIZE(64, 64)"),
            ("frontPicYOffset", "0"),
            ("backPicSize", "MON_COORDS_SIZE(64, 64)"),
            ("backPicYOffset", "0"),
        ):
            block = replace_field(block, field, value, label)
    else:
        for field in ("frontPicSize", "frontPicYOffset", "backPicSize", "backPicYOffset"):
            block = replace_field(block, field, field_value(donor_block, field), label)
        for field in PALETTE_FIELDS:
            block = replace_field(
                block,
                field,
                palette_alias(field, donor_id, palette_preset),
                label,
            )

    block = replace_field(
        block,
        "iconPalIndex",
        field_value(donor_block, "iconPalIndex"),
        label,
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
    active_overrides = resolve_overrides(mapping)
    used_donors = sorted({int(row["donor_species_id"]) for row in mapping})
    enum_values = parse_species_enum(engine)
    donor_blocks = load_donor_blocks(engine, enum_values, set(used_donors))

    build_donor_graphics_header(
        engine,
        donor_blocks,
        used_donors,
        mapping,
        active_overrides,
    )

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
            active_overrides.get(species_id),
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
    print(f"  explicit battle sprite overrides active: {len(active_overrides)}")
    print("  authored Digital Monster sprite experiments: provenance unless explicitly mapped")
    print("  family classifications: " + ", ".join(
        f"{name}={count}" for name, count in sorted(family_counts.items())
    ))


if __name__ == "__main__":
    main()
