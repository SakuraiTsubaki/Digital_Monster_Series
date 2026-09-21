#!/usr/bin/env python3
"""Copy generated Digital Monster Emerald integration files into an engine checkout."""
from __future__ import annotations
import argparse, shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
GENERATED = ROOT / "engine" / "emerald" / "generated" / "pokeemerald-expansion"

FILES = {
    "include/constants/digital_monster_move_enum.inc":
        GENERATED / "include/constants/digital_monster_move_enum.inc",
    "src/data/digital_monster/moves_info.inc":
        GENERATED / "src/data/digital_monster/moves_info.inc",
}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("engine", type=Path)
    args=p.parse_args()
    for rel, src in FILES.items():
        dst=args.engine / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src,dst)
        print(f"{src.relative_to(ROOT)} -> {dst}")

if __name__=="__main__":
    main()
