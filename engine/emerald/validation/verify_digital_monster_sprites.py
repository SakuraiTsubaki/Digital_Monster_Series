#!/usr/bin/env python3
"""Validate authored Digital Monster gameplay sprite assets using only stdlib."""
from __future__ import annotations

import json
import struct
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
EMERALD = PROJECT_ROOT / "engine" / "emerald"
SPRITE_ROOT = EMERALD / "assets" / "gameplay-v0" / "sprites"
SPEC_PATH = SPRITE_ROOT / "sprite-spec.json"
CATALOG_PATH = EMERALD / "generated" / "sprite-catalog.json"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def read_png(path: Path) -> dict[str, int | bool]:
    data = path.read_bytes()
    if not data.startswith(PNG_SIGNATURE):
        raise SystemExit(f"{path}: not a PNG file")
    pos = len(PNG_SIGNATURE)
    width = height = bit_depth = color_type = None
    palette_colors = 0
    transparent_index0 = False
    while pos + 12 <= len(data):
        length = struct.unpack(">I", data[pos:pos + 4])[0]
        kind = data[pos + 4:pos + 8]
        payload = data[pos + 8:pos + 8 + length]
        pos += 12 + length
        if kind == b"IHDR":
            width, height, bit_depth, color_type = struct.unpack(">IIBB", payload[:10])
        elif kind == b"PLTE":
            if length % 3:
                raise SystemExit(f"{path}: malformed PLTE chunk")
            palette_colors = length // 3
        elif kind == b"tRNS":
            transparent_index0 = bool(payload) and payload[0] == 0
        elif kind == b"IEND":
            break
    if width is None or height is None:
        raise SystemExit(f"{path}: missing IHDR")
    return {
        "width": width,
        "height": height,
        "bit_depth": bit_depth,
        "color_type": color_type,
        "palette_colors": palette_colors,
        "transparent_index0": transparent_index0,
    }


def verify_png(path: Path, spec: dict) -> None:
    info = read_png(path)
    expected = (spec["width"], spec["height"])
    actual = (info["width"], info["height"])
    if actual != expected:
        raise SystemExit(f"{path}: expected {expected[0]}x{expected[1]}, found {actual[0]}x{actual[1]}")
    if info["color_type"] != 3:
        raise SystemExit(f"{path}: expected indexed-color PNG (color type 3)")
    if not (1 <= info["palette_colors"] <= spec["max_palette_colors"]):
        raise SystemExit(
            f"{path}: palette has {info['palette_colors']} colors; "
            f"expected <= {spec['max_palette_colors']}"
        )
    if spec.get("transparent_palette_index") == 0 and not info["transparent_index0"]:
        raise SystemExit(f"{path}: palette index 0 must be transparent via tRNS")


def verify_jasc_palette(path: Path, expected_colors: int) -> None:
    lines = path.read_text(encoding="ascii").splitlines()
    if len(lines) < 3 or lines[0] != "JASC-PAL" or lines[1] != "0100":
        raise SystemExit(f"{path}: expected JASC-PAL 0100")
    try:
        count = int(lines[2])
    except ValueError as exc:
        raise SystemExit(f"{path}: invalid palette color count") from exc
    if count != expected_colors or len(lines[3:]) != expected_colors:
        raise SystemExit(f"{path}: expected exactly {expected_colors} palette colors")
    for i, line in enumerate(lines[3:], start=0):
        parts = line.split()
        if len(parts) != 3:
            raise SystemExit(f"{path}: palette row {i} is not RGB")
        rgb = [int(x) for x in parts]
        if any(x < 0 or x > 255 for x in rgb):
            raise SystemExit(f"{path}: palette row {i} has out-of-range RGB")


def main() -> None:
    spec = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    source_spec = spec["source_assets"]

    if catalog["species_total"] != 1468:
        raise SystemExit("sprite catalog species_total must be 1468")
    if catalog.get("placeholder_runtime_species") != 0:
        raise SystemExit("runtime sprite placeholders must be zero after donor fallback integration")
    active_overrides = int(catalog.get("active_override_species", -1))
    donor_fallback = int(catalog.get("donor_fallback_species", -1))
    if active_overrides < 0 or donor_fallback < 0:
        raise SystemExit("sprite catalog is missing donor fallback runtime counts")
    if active_overrides + donor_fallback != catalog["species_total"]:
        raise SystemExit("sprite catalog runtime counts do not cover all species")

    checked = 0
    for entry in catalog["entries"]:
        if entry["asset_status"] == "source_only":
            continue

        assets = entry["assets"]
        for key in ("front", "back", "icon"):
            asset = assets[key]
            if asset is None:
                continue
            path = EMERALD / asset["path"]
            verify_png(path, source_spec[key])

        pal = assets["normal_palette"]
        if pal is not None:
            verify_jasc_palette(
                EMERALD / pal["path"],
                int(source_spec["normal_palette"]["colors"]),
            )

        if entry["asset_status"] == "runtime_ready":
            missing = [key for key, value in assets.items() if value is None]
            if missing:
                raise SystemExit(
                    f"{entry['internal_name']}: runtime_ready but missing {', '.join(missing)}"
                )
        checked += 1

    print("Digital Monster sprite assets verified")
    print(f"  declared manifests: {catalog['declared_sprite_manifests']}")
    print(f"  runtime-ready species: {catalog['runtime_ready_species']}")
    print(f"  authored asset entries checked: {checked}")
    print(f"  active authored battle overrides: {active_overrides}")
    print(f"  donor fallback runtime species: {donor_fallback}")
    print(f"  placeholder runtime species: {catalog['placeholder_runtime_species']}")


if __name__ == "__main__":
    main()
