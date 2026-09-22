#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GENERATED = ROOT / "generated"
ENGINE_GEN = GENERATED / "pokeemerald-expansion"

EXPECTED_GLYPHS = 642
EXPECTED_PADDED = 656
EXPECTED_NORMAL_U16 = EXPECTED_PADDED * 16
EXPECTED_SMALL_U16 = EXPECTED_PADDED * 16
EXPECTED_SHORT_U16 = EXPECTED_PADDED * 32


def array_values(text: str, name: str) -> list[int]:
    m = re.search(rf"const u16 {re.escape(name)}\[\]\s*=\s*\{{(.*?)\}};", text, flags=re.S)
    if not m:
        raise SystemExit(f"array not found: {name}")
    return [int(x, 16) for x in re.findall(r"0x([0-9A-Fa-f]{4})", m.group(1))]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("engine", nargs="?", type=Path)
    args = ap.parse_args()

    with (GENERATED / "font-v0-source-map.csv").open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == EXPECTED_GLYPHS
    assert [int(x["local_index"]) for x in rows] == list(range(EXPECTED_GLYPHS))
    assert int(rows[0]["glyph_id_decimal"]) == 0x200
    assert int(rows[-1]["glyph_id_decimal"]) == 0x481
    assert all(x["source"] for x in rows)

    report = json.loads((GENERATED / "font-v0-report.json").read_text(encoding="utf-8"))
    assert report["coverage_complete"] is True
    assert report["mapped_glyphs"] == EXPECTED_GLYPHS

    arrays = (ENGINE_GEN / "src/data/digital_monster/extended_fonts.inc").read_text(encoding="utf-8")
    normal = array_values(arrays, "gDigitalMonsterFontNormalJapaneseGlyphs")
    small = array_values(arrays, "gDigitalMonsterFontSmallJapaneseGlyphs")
    short = array_values(arrays, "gDigitalMonsterFontShortJapaneseGlyphs")
    assert len(normal) == EXPECTED_NORMAL_U16, len(normal)
    assert len(small) == EXPECTED_SMALL_U16, len(small)
    assert len(short) == EXPECTED_SHORT_U16, len(short)

    if args.engine:
        engine = args.engine
        chars = (engine / "include/constants/characters.h").read_text(encoding="utf-8")
        text_c = (engine / "src/text.c").read_text(encoding="utf-8")
        cmap = (engine / "charmap.txt").read_text(encoding="utf-8")
        assert "#define EXT_CTRL_CODE_DM_GLYPH               0x1D" in chars
        assert "GetDigitalMonsterNormalJapaneseGlyph" in text_c
        assert "GetDigitalMonsterSmallJapaneseGlyph" in text_c
        assert "GetDigitalMonsterShortJapaneseGlyph" in text_c
        assert "case EXT_CTRL_CODE_DM_GLYPH:" in text_c
        assert "Digital_Monster_Series extended Japanese glyphs" in cmap
        assert cmap.count(" = FC 1D ") >= EXPECTED_GLYPHS

    print("Digital Monster font-v0 verified")
    print(f"  extended glyphs: {EXPECTED_GLYPHS}")
    print(f"  padded slots: {EXPECTED_PADDED}")
    print(f"  raw font data: {(len(normal)+len(small)+len(short))*2} bytes")
    print("  coverage: 642 / 642")

if __name__ == "__main__":
    main()
