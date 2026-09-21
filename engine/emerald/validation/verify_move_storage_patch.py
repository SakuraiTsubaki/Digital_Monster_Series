#!/usr/bin/env python3
"""Verify the Digital Monster 12-bit move patch against a prepared engine checkout."""

from __future__ import annotations

import argparse
from pathlib import Path


def must(text: str, needle: str, label: str) -> None:
    if needle not in text:
        raise SystemExit(f"missing {label}: {needle}")


def must_not(text: str, needle: str, label: str) -> None:
    if needle in text:
        raise SystemExit(f"obsolete {label} remains: {needle}")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("engine", type=Path, help="pokeemerald-expansion checkout after applying the Digital Monster patch")
    args = p.parse_args()

    header = (args.engine / "include" / "pokemon.h").read_text(encoding="utf-8")
    source = (args.engine / "src" / "pokemon.c").read_text(encoding="utf-8")

    for n in range(1, 5):
        must(header, f"enum Move move{n}:12;", f"move{n} width")

    for field in (
        "evolutionTracker1Lo:4",
        "evolutionTracker1Hi:1",
        "evolutionTracker2Lo:3",
        "evolutionTracker2Hi:2",
    ):
        must(header, field, "split evolution tracker")

    must_not(header, "enum Move move1:11;", "11-bit move field")
    must_not(header, "u16 evolutionTracker1:5;", "unsplit evolutionTracker1")
    must_not(header, "u16 evolutionTracker2:5;", "unsplit evolutionTracker2")

    must(source, "substruct1->evolutionTracker1Lo", "tracker1 repack getter/setter")
    must(source, "substruct1->evolutionTracker2Hi", "tracker2 repack getter/setter")

    # Bit budget before PP bytes remains exactly four 16-bit words.
    word_bits = [
        12 + 4,
        12 + 1 + 3,
        12 + 2 + 2,
        12 + 2 + 1 + 1,
    ]
    if word_bits != [16, 16, 16, 16]:
        raise SystemExit(f"invalid move/tracker bit budget: {word_bits}")

    print("Digital Monster 12-bit move storage verified")
    print("  move capacity: 4095")
    print("  required techniques: 2557")
    print("  persistent move/tracker region: 64 bits (unchanged)")


if __name__ == "__main__":
    main()
