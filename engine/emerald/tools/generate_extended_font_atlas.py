#!/usr/bin/env python3
"""Prepare/validate Digital Monster extended Japanese font atlas templates.

The script does not invent glyph artwork. It creates deterministic 2-bit indexed
PNG templates with the exact dimensions/palette required by pokeemerald-expansion
and emits a placement manifest for the 642 required characters.

Populate each cell from a verified Japanese glyph source, then rerun with
--validate to ensure dimensions/indexing remain exact.
"""
from __future__ import annotations
import argparse, csv, struct, zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
GLYPH_MAP = ROOT / "engine/emerald/generated/digital-monster-glyph-map.csv"
OUT = ROOT / "engine/emerald/generated/font-atlas"

PALETTE = [
    (0x90,0xC8,0xFF),
    (0x38,0x38,0x38),
    (0xD8,0xD8,0xD8),
    (0xFF,0xFF,0xFF),
]
COUNT = 642
COLS = 16
ROWS = 41

def chunk(kind: bytes, payload: bytes) -> bytes:
    return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)

def write_indexed_png(path: Path, width: int, height: int) -> None:
    # 2-bit indexed PNG, background palette index 0.
    row_bytes = (width * 2 + 7) // 8
    raw = b"".join(b"\x00" + bytes(row_bytes) for _ in range(height))
    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", width, height, 2, 3, 0, 0, 0)
    plte = b"".join(bytes(rgb) for rgb in PALETTE)
    path.write_bytes(sig + chunk(b"IHDR", ihdr) + chunk(b"PLTE", plte) + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))

def png_size(path: Path) -> tuple[int,int,int,int]:
    data=path.read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise SystemExit(f"{path}: not PNG")
    w,h,depth,ctype=struct.unpack(">IIBB",data[16:26])
    return w,h,depth,ctype

def read_map():
    with GLYPH_MAP.open(encoding="utf-8-sig", newline="") as f:
        rows=list(csv.DictReader(f))
    assert len(rows)==COUNT, len(rows)
    return rows

def emit_manifest(rows):
    OUT.mkdir(parents=True,exist_ok=True)
    p=OUT/"placement.csv"
    with p.open("w",encoding="utf-8",newline="") as f:
        w=csv.writer(f)
        w.writerow(["local_index","glyph_id_hex","char","codepoint","column","row","halfwidth_x","y","fullwidth_x"])
        for i,r in enumerate(rows):
            w.writerow([i,r["glyph_id_hex"],r["char"],r["codepoint"],i%COLS,i//COLS,(i%COLS)*8,(i//COLS)*16,(i%COLS)*16])

def validate():
    expected={
        "digital_monster_japanese_normal.png":(128,656,2,3),
        "digital_monster_japanese_small.png":(128,656,2,3),
        "digital_monster_japanese_short.png":(256,656,2,3),
    }
    for name,exp in expected.items():
        got=png_size(OUT/name)
        if got != exp:
            raise SystemExit(f"{name}: {got} != {exp}")
    rows=read_map()
    assert int(rows[0]["glyph_id_decimal"])==0x200
    assert int(rows[-1]["glyph_id_decimal"])==0x481
    print("Digital Monster extended Japanese atlas layout verified")
    print("  mapped glyphs: 642")
    print("  padded capacity: 656")
    print("  halfwidth: 128x656 / 8x16")
    print("  fullwidth: 256x656 / 16x16")

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--templates",action="store_true")
    ap.add_argument("--validate",action="store_true")
    args=ap.parse_args()
    rows=read_map()
    OUT.mkdir(parents=True,exist_ok=True)
    emit_manifest(rows)
    if args.templates:
        write_indexed_png(OUT/"digital_monster_japanese_normal.png",128,656)
        write_indexed_png(OUT/"digital_monster_japanese_small.png",128,656)
        write_indexed_png(OUT/"digital_monster_japanese_short.png",256,656)
    if args.validate:
        validate()
    if not args.templates and not args.validate:
        print("placement manifest generated; use --templates and/or --validate")

if __name__=="__main__":
    main()
