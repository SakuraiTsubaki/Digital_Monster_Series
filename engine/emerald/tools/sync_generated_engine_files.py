#!/usr/bin/env python3
"""Sync all generated Digital Monster integration files into a pokeemerald-expansion checkout."""
from __future__ import annotations
import argparse, shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
GENERATED = ROOT / "engine" / "emerald" / "generated" / "pokeemerald-expansion"

def main():
    p = argparse.ArgumentParser()
    p.add_argument("engine", type=Path)
    args = p.parse_args()

    files = sorted(x for x in GENERATED.rglob("*") if x.is_file())
    if not files:
        raise SystemExit("no generated engine files found")

    for src in files:
        rel = src.relative_to(GENERATED)
        dst = args.engine / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
        print(f"{rel}")

    print(f"synced {len(files)} generated files")

if __name__ == "__main__":
    main()
