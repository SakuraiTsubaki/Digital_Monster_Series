#!/usr/bin/env python3
"""Validate profile-derived technique parameters and MoveInfo coverage."""
from __future__ import annotations

import argparse
import csv
import re
from collections import Counter
from pathlib import Path


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--parameters", type=Path, required=True)
    ap.add_argument("--move-info", type=Path, required=True)
    args = ap.parse_args()

    data = rows(args.parameters)
    assert len(data) == 2557, len(data)
    assert [int(x["dm_technique_id"]) for x in data] == list(range(1, 2558))

    for row in data:
        power = int(row["power"])
        accuracy = int(row["accuracy"])
        pp = int(row["pp"])
        assert 0 <= power <= 511
        assert 0 <= accuracy <= 100
        assert 1 <= pp <= 255
        assert row["type"].startswith("TYPE_")
        assert row["category"] in {
            "DAMAGE_CATEGORY_PHYSICAL",
            "DAMAGE_CATEGORY_SPECIAL",
            "DAMAGE_CATEGORY_STATUS",
        }
        assert row["effect"].startswith("EFFECT_")
        assert row["effect_status"]
        assert row["evidence_signals"]
        assert row["derivation_version"] == "profile-derived-v1"

    assert len({int(x["power"]) for x in data}) >= 20
    assert len({x["type"] for x in data}) >= 8
    assert not all(
        int(x["power"]) == 70 and int(x["accuracy"]) == 100 and int(x["pp"]) == 15
        for x in data
    )

    text = args.move_info.read_text(encoding="utf-8")
    ids = [int(x) for x in re.findall(r"\[DM_MOVE_(\d{4})\]", text)]
    assert ids == list(range(1, 2558)), (len(ids), ids[:3], ids[-3:])
    assert text.count("[DM_MOVE_BOOTSTRAP_ATTACK]") == 1
    assert text.count("| profile-derived-v1 |") == 2557

    effects = Counter(x["effect_status"] for x in data)
    categories = Counter(x["category"] for x in data)
    print("Profile-derived techniques verified")
    print(f"  techniques: {len(data)}")
    print(f"  unique powers: {len({int(x['power']) for x in data})}")
    print(f"  types used: {len({x['type'] for x in data})}")
    print(f"  categories: {dict(categories)}")
    print(f"  effect status: {dict(effects)}")
    print("  fixed gameplay-v0 70/100/15 table: not active")


if __name__ == "__main__":
    main()
