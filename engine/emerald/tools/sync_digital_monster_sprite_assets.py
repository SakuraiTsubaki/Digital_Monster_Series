#!/usr/bin/env python3
"""Sync validated Digital Monster battle sprites into a pokeemerald-expansion checkout.

Authored assets stay in engine/emerald/assets/gameplay-v0/sprites.  This tool
materializes engine-facing graphics and patches only SpeciesInfo entries whose
front/back/palette set is complete.  Icons deliberately remain on the existing
placeholder path until the icon-palette runtime is expanded.
"""
from __future__ import annotations

import argparse
import binascii
import json
import shutil
import struct
import zlib
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
EMERALD = PROJECT_ROOT / "engine" / "emerald"
CATALOG_PATH = EMERALD / "generated" / "sprite-catalog.json"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


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
        raise SystemExit(f"{src}: front source must be indexed-color PNG")
    if interlace != 0:
        raise SystemExit(f"{src}: interlaced PNG is not supported")
    if width != 64 or height != 64:
        raise SystemExit(f"{src}: expected 64x64 front source, found {width}x{height}")

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


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one match, found {count}")
    return text.replace(old, new, 1)


def patch_species_info(engine: Path, species_id: int, internal_name: str) -> None:
    path = (
        engine
        / "src/data/pokemon/species_info"
        / species_part(species_id)
    )
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
    block = replace_once(
        block,
        "        .frontPic = gMonFrontPic_CircledQuestionMark,",
        f"        .frontPic = gDigitalMonsterFrontPic_{internal_name},",
        f"{internal_name} frontPic",
    )
    block = replace_once(
        block,
        "        .frontPicSize = MON_COORDS_SIZE(40, 40),",
        "        .frontPicSize = MON_COORDS_SIZE(64, 64),",
        f"{internal_name} frontPicSize",
    )
    block = replace_once(
        block,
        "        .frontPicYOffset = 12,",
        "        .frontPicYOffset = 0,",
        f"{internal_name} frontPicYOffset",
    )
    block = replace_once(
        block,
        "        .backPic = gMonBackPic_CircledQuestionMark,",
        f"        .backPic = gDigitalMonsterBackPic_{internal_name},",
        f"{internal_name} backPic",
    )
    block = replace_once(
        block,
        "        .backPicSize = MON_COORDS_SIZE(40, 40),",
        "        .backPicSize = MON_COORDS_SIZE(64, 64),",
        f"{internal_name} backPicSize",
    )
    block = replace_once(
        block,
        "        .backPicYOffset = 12,",
        "        .backPicYOffset = 0,",
        f"{internal_name} backPicYOffset",
    )
    block = replace_once(
        block,
        "        .palette = gMonPalette_CircledQuestionMark,",
        f"        .palette = gDigitalMonsterPalette_{internal_name},",
        f"{internal_name} palette",
    )
    block = replace_once(
        block,
        "        .shinyPalette = gMonShinyPalette_CircledQuestionMark,",
        f"        .shinyPalette = gDigitalMonsterPalette_{internal_name},",
        f"{internal_name} shinyPalette",
    )
    path.write_text(text[:start] + block + text[end:], encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("engine", type=Path)
    args = parser.parse_args()
    engine = args.engine.resolve()

    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    declarations = [
        "// Generated at build time from validated Digital Monster sprite assets.",
        "// Icons intentionally remain on the question-mark placeholder until",
        "// the icon palette runtime is expanded beyond the stock shared palettes.",
        "",
    ]

    integrated = 0
    for entry in catalog["entries"]:
        assets = entry["assets"]
        required = ("front", "back", "normal_palette")
        if not all(assets.get(key) is not None for key in required):
            continue

        species_id = int(entry["species_id"])
        internal = entry["internal_name"]
        slug = internal.lower()
        out_dir = engine / "graphics/digital_monster" / slug
        out_dir.mkdir(parents=True, exist_ok=True)

        front_src = EMERALD / assets["front"]["path"]
        back_src = EMERALD / assets["back"]["path"]
        pal_src = EMERALD / assets["normal_palette"]["path"]

        duplicate_indexed_png_frame(front_src, out_dir / "anim_front.png")
        shutil.copyfile(back_src, out_dir / "back.png")
        shutil.copyfile(pal_src, out_dir / "normal.pal")

        declarations.extend(
            [
                f'const u32 gDigitalMonsterFrontPic_{internal}[] = '
                f'INCGFX_U32("graphics/digital_monster/{slug}/anim_front.png", ".4bpp.smol");',
                f'const u32 gDigitalMonsterBackPic_{internal}[] = '
                f'INCGFX_U32("graphics/digital_monster/{slug}/back.png", ".4bpp.smol");',
                f'const u16 gDigitalMonsterPalette_{internal}[] = '
                f'INCGFX_U16("graphics/digital_monster/{slug}/normal.pal", ".gbapal");',
                "",
            ]
        )
        patch_species_info(engine, species_id, internal)
        integrated += 1

    graphics_header = engine / "src/data/graphics/digital_monster.h"
    graphics_header.parent.mkdir(parents=True, exist_ok=True)
    graphics_header.write_text("\n".join(declarations).rstrip() + "\n", encoding="utf-8")

    print("Digital Monster battle sprite sync complete")
    print(f"  battle-ready species integrated: {integrated}")
    print("  icon sprites: placeholder until icon-palette runtime expansion")


if __name__ == "__main__":
    main()
