#!/usr/bin/env python3
"""Derive Digital Monster technique gameplay parameters from official evidence.

Priority:
1. Official Japanese technique name.
2. The sentence(s) in official Japanese owner profiles that explicitly mention
   that technique.
3. Profile-derived owner battle parameters as a fallback context.

No hash/random assignment is used. Raw Digimon profile prose is never written
to the output; only SHA-backed derived evidence signals are retained.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean

from derive_profile_parameters import TYPE_TERMS, clamp

ROOT = Path(__file__).resolve().parents[3]
EMERALD = ROOT / "engine" / "emerald"
GEN = EMERALD / "generated"
TECHNIQUES = GEN / "technique-id-map.csv"
ASSIGNMENTS = GEN / "entity-techniques.csv"
APPMON_MASTER = ROOT / "appmon" / "appmon_master.csv"

PHYSICAL_TERMS = [
    "パンチ", "キック", "クロー", "爪", "牙", "バイト", "ソード", "ブレード",
    "剣", "刀", "斬", "スラッシュ", "ハンマー", "ナックル", "タックル",
    "ラッシュ", "クラッシュ", "テイル", "ホーン", "ドリル", "槍", "突進",
]
SPECIAL_TERMS = [
    "ビーム", "レーザー", "ブラスト", "ブラスター", "キャノン", "バースト",
    "ボール", "ウェーブ", "波動", "ブレス", "フレイム", "ファイア", "サンダー",
    "ライトニング", "アイス", "ブリザード", "アクア", "エネルギー", "光", "闇",
    "魔", "データ", "電撃", "衝撃波", "ノヴァ", "ストーム",
]
STATUS_TERMS = [
    "ヒール", "リカバー", "回復", "レストア", "ガード", "シールド", "バリア",
    "プロテクト", "ブースト", "封印", "スリープ", "催眠",
    "コンフューズ", "混乱", "リフレクト",
]
STATUS_CONTEXT_TERMS = [
    "能力を上げ", "攻撃力を上げ", "防御力を上げ", "素早さを上げ",
    "能力を下げ", "攻撃力を下げ", "防御力を下げ", "素早さを下げ",
    "力を溜め", "力をため", "チャージする", "エネルギーを蓄え",
    "強化する", "強化させ", "回復する", "回復させ", "治癒する",
    "守る", "防ぐ", "バリアを張", "封印する", "動きを封じ",
    "眠らせ", "混乱させ", "幻惑する",
]
RECOVER_TERMS = ["ヒール", "リカバー", "回復", "レストア", "治癒"]
PROTECT_TERMS = ["プロテクト", "シールド", "ガード", "防御壁"]
CONFUSE_TERMS = ["コンフューズ", "混乱", "幻惑"]
SELF_STATUS_TERMS = RECOVER_TERMS + PROTECT_TERMS + ["ブースト", "強化"]

POWER_TERMS = [
    ("プチ", -3), ("ミニ", -2), ("ベビー", -2),
    ("メガ", 2), ("ギガ", 3), ("テラ", 4), ("グランド", 2),
    ("アルティメット", 4), ("ファイナル", 4), ("マキシマム", 4),
    ("オメガ", 4), ("デストロイ", 4), ("ブレイカー", 3), ("クラッシャー", 3),
    ("バースト", 3), ("ブラスター", 3), ("キャノン", 2), ("ノヴァ", 3),
    ("エクスプロージョン", 4), ("インパクト", 2), ("必殺", 4), ("一撃", 4),
    ("最大", 3), ("究極", 4), ("強力", 2), ("絶大", 4), ("破壊", 3),
]

CONTACT_TERMS = [
    "パンチ", "キック", "クロー", "爪", "牙", "バイト", "ソード", "ブレード",
    "剣", "刀", "斬", "ハンマー", "ナックル", "タックル", "テイル", "ホーン",
    "ドリル", "槍", "突進",
]
FAST_TERMS = ["クイック", "先制", "瞬速", "神速", "高速"]

TYPE_NAME_WEIGHTS = 6
TYPE_CONTEXT_WEIGHTS = 3
TYPE_OWNER_WEIGHTS = 2


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def profile_sentences(profile: str, move_name: str) -> tuple[str, bool]:
    sentences = [x.strip() for x in re.split(r"(?<=[。！？])|\n+", profile) if x.strip()]
    matched = [x for x in sentences if move_name and move_name in x]
    if matched:
        return " ".join(matched), True
    return "", False


def count_terms(text: str, terms: list[str]) -> int:
    return sum(min(text.count(term), 3) for term in terms)


def type_score(move_name: str, context: str, owner_rows: list[dict[str, str]]) -> tuple[str, str, list[str]]:
    scores: Counter[str] = Counter()
    evidence: list[str] = []
    for type_name, terms in TYPE_TERMS.items():
        for term in terms:
            n = min(move_name.count(term), 3)
            c = min(context.count(term), 3)
            if n:
                scores[type_name] += n * TYPE_NAME_WEIGHTS
                evidence.append(f"type:{type_name}:{term}:name:+{n * TYPE_NAME_WEIGHTS}")
            if c:
                scores[type_name] += c * TYPE_CONTEXT_WEIGHTS
                evidence.append(f"type:{type_name}:{term}:profile_context:+{c * TYPE_CONTEXT_WEIGHTS}")

    if scores:
        best, value = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))[0]
        return best, "resolved_name_or_profile_context", evidence + [f"type_choice:{best}:{value}"]

    owner_scores: Counter[str] = Counter()
    for row in owner_rows:
        if row.get("battle_type_status") != "resolved_profile_evidence":
            continue
        for field in ("battle_type_1", "battle_type_2"):
            value = row.get(field) or ""
            if value:
                owner_scores[value] += TYPE_OWNER_WEIGHTS
    if owner_scores:
        best, value = sorted(owner_scores.items(), key=lambda kv: (-kv[1], kv[0]))[0]
        return best, "inherited_profile_derived_owner_type", [f"type_owner_context:{best}:{value}"]

    return "TYPE_NORMAL", "unresolved_type_placeholder", ["type_placeholder:TYPE_NORMAL:no_direct_or_owner_evidence"]


def category_score(move_name: str, context: str, owner_rows: list[dict[str, str]]) -> tuple[str, list[str]]:
    p = count_terms(move_name, PHYSICAL_TERMS) * 4 + count_terms(context, PHYSICAL_TERMS) * 2
    s = count_terms(move_name, SPECIAL_TERMS) * 4 + count_terms(context, SPECIAL_TERMS) * 2
    st_name = count_terms(move_name, STATUS_TERMS) * 5
    st_context = count_terms(context, STATUS_CONTEXT_TERMS) * 4
    st = st_name + st_context

    evidence = [
        f"category_scores:physical={p}:special={s}:status={st}",
        f"status_evidence:name={st_name}:context={st_context}",
    ]
    if st >= 5 and st > max(p, s):
        return "DAMAGE_CATEGORY_STATUS", evidence + ["category:status:name_evidence"]
    if p > s:
        return "DAMAGE_CATEGORY_PHYSICAL", evidence + ["category:physical:text_evidence"]
    if s > p:
        return "DAMAGE_CATEGORY_SPECIAL", evidence + ["category:special:text_evidence"]

    attacks = [int(x["base_attack"]) for x in owner_rows if x.get("base_attack")]
    specials = [int(x["base_sp_attack"]) for x in owner_rows if x.get("base_sp_attack")]
    avg_atk = mean(attacks) if attacks else 80
    avg_spa = mean(specials) if specials else 80
    if avg_atk > avg_spa:
        return "DAMAGE_CATEGORY_PHYSICAL", evidence + [f"category:physical:owner_profile_stats:{avg_atk:.1f}>{avg_spa:.1f}"]
    return "DAMAGE_CATEGORY_SPECIAL", evidence + [f"category:special:owner_profile_stats:{avg_spa:.1f}>={avg_atk:.1f}"]


def intensity_score(move_name: str, context: str) -> tuple[int, list[str]]:
    score = 0
    evidence: list[str] = []
    for term, weight in POWER_TERMS:
        n = min(move_name.count(term), 2)
        c = min(context.count(term), 2)
        if n:
            score += weight * n
            evidence.append(f"power:{term}:name:{weight * n:+d}")
        if c:
            score += weight * c
            evidence.append(f"power:{term}:profile_context:{weight * c:+d}")
    return score, evidence


def choose_effect(category: str, move_name: str, context: str) -> tuple[str, str, str, int, str, list[str]]:
    if category != "DAMAGE_CATEGORY_STATUS":
        priority = 1 if any(x in move_name for x in FAST_TERMS) else 0
        return "EFFECT_HIT", "TARGET_SELECTED", "", priority, "resolved_damage_core_only", ["effect:hit"]

    joined = move_name + "\n" + context
    if any(x in joined for x in RECOVER_TERMS):
        return "EFFECT_RESTORE_HP", "TARGET_USER", "", 0, "resolved_recovery_evidence", ["effect:restore_hp"]
    if any(x in move_name for x in PROTECT_TERMS):
        arg = ".argument = { .protectMethod = PROTECT_NORMAL },"
        return "EFFECT_PROTECT", "TARGET_USER", arg, 4, "resolved_protect_name_evidence", ["effect:protect"]
    if any(x in joined for x in CONFUSE_TERMS):
        return "EFFECT_CONFUSE", "TARGET_SELECTED", "", 0, "resolved_confuse_evidence", ["effect:confuse"]

    target = "TARGET_USER" if any(x in move_name for x in SELF_STATUS_TERMS) else "TARGET_SELECTED"
    return "EFFECT_DO_NOTHING", target, "", 0, "unresolved_status_effect", ["effect:placeholder_do_nothing"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--digimon-master-json", type=Path, required=True)
    ap.add_argument("--species-parameters", type=Path, required=True)
    ap.add_argument("--output", type=Path, default=GEN / "profile-derived-techniques.csv")
    args = ap.parse_args()

    techniques = rows(TECHNIQUES)
    assignments = rows(ASSIGNMENTS)
    species_params = rows(args.species_parameters)
    if len(techniques) != 2557:
        raise SystemExit(f"expected 2557 techniques, got {len(techniques)}")
    if len(assignments) != 2872:
        raise SystemExit(f"expected 2872 technique assignments, got {len(assignments)}")
    if len(species_params) != 1468:
        raise SystemExit(f"expected 1468 species parameter rows, got {len(species_params)}")

    digimon_list = json.loads(args.digimon_master_json.read_text(encoding="utf-8"))
    digimon = {x["directory_name"]: x for x in digimon_list}
    appmon = {f"appmon_{int(x['id']):03d}": x for x in rows(APPMON_MASTER)}
    param_by_key = {(x["source_kind"], x["source_id"]): x for x in species_params}

    profile_by_key: dict[tuple[str, str], str] = {}
    for key, value in digimon.items():
        profile_by_key[("digimon", key)] = value.get("profile_ja") or ""
    for key, value in appmon.items():
        profile_by_key[("appmon", key)] = value.get("profile_ja") or ""

    assignments_by_move: dict[int, list[dict[str, str]]] = defaultdict(list)
    for row in assignments:
        assignments_by_move[int(row["dm_technique_id"])].append(row)

    out: list[dict[str, str | int]] = []
    for tech in techniques:
        move_id = int(tech["dm_technique_id"])
        move_name = tech["name_ja"]
        owners = assignments_by_move.get(move_id, [])
        if not owners:
            raise SystemExit(f"move {move_id} {move_name}: no owners")

        owner_params = []
        context_parts: list[str] = []
        direct_mentions = 0
        for owner in owners:
            key = (owner["source_kind"], owner["source_id"])
            params = param_by_key.get(key)
            if params:
                owner_params.append(params)
            profile = profile_by_key.get(key, "")
            if not profile:
                continue
            ctx, direct = profile_sentences(profile, move_name)
            if direct:
                direct_mentions += 1
                context_parts.append(ctx)

        context = " ".join(context_parts)
        move_type, type_status, type_evidence = type_score(move_name, context, owner_params)
        category, category_evidence = category_score(move_name, context, owner_params)
        intensity, power_evidence = intensity_score(move_name, context)

        effect, target, effect_argument, priority, effect_status, effect_evidence = choose_effect(
            category, move_name, context
        )

        if category == "DAMAGE_CATEGORY_STATUS":
            power = 0
            accuracy = 0 if target == "TARGET_USER" else 100
            pp = 15
        else:
            offense_field = "base_attack" if category == "DAMAGE_CATEGORY_PHYSICAL" else "base_sp_attack"
            offense_values = [int(x[offense_field]) for x in owner_params if x.get(offense_field)]
            offense = mean(offense_values) if offense_values else 80
            power = clamp(round(25 + offense * 0.55 + intensity * 5), 10, 300)
            if any(x in (move_name + context) for x in ["必中", "必ず命中", "追尾", "ロックオン", "ホーミング"]):
                accuracy = 100
                power_evidence.append("accuracy:explicit_tracking_or_sure_hit:100")
            elif power <= 80:
                accuracy = 100
            elif power <= 120:
                accuracy = 95
            elif power <= 170:
                accuracy = 90
            else:
                accuracy = 85

            if power <= 60:
                pp = 30
            elif power <= 90:
                pp = 20
            elif power <= 130:
                pp = 15
            elif power <= 180:
                pp = 10
            else:
                pp = 5

        makes_contact = (
            category == "DAMAGE_CATEGORY_PHYSICAL"
            and any(term in move_name for term in CONTACT_TERMS)
        )

        evidence = (
            type_evidence
            + category_evidence
            + power_evidence
            + effect_evidence
            + [f"owners:{len(owners)}", f"direct_profile_mentions:{direct_mentions}"]
        )

        out.append({
            "dm_technique_id": move_id,
            "emerald_runtime_move_id": 934 + move_id,
            "name_ja": move_name,
            "owner_count": len(owners),
            "direct_profile_mention_count": direct_mentions,
            "evidence_signals": " ; ".join(evidence[:64]),
            "type": move_type,
            "type_status": type_status,
            "category": category,
            "power": power,
            "accuracy": accuracy,
            "pp": pp,
            "effect": effect,
            "effect_argument": effect_argument,
            "effect_status": effect_status,
            "target": target,
            "priority": priority,
            "makes_contact": "true" if makes_contact else "false",
            "derivation_version": "profile-derived-v1",
        })

    if [int(x["dm_technique_id"]) for x in out] != list(range(1, 2558)):
        raise SystemExit("technique IDs are not exactly 1..2557")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(out[0].keys()))
        writer.writeheader()
        writer.writerows(out)

    powers = [int(x["power"]) for x in out]
    types = Counter(x["type"] for x in out)
    cats = Counter(x["category"] for x in out)
    effects = Counter(x["effect_status"] for x in out)
    print("Profile-derived techniques generated")
    print(f"  techniques: {len(out)}")
    print(f"  direct profile mentions: {sum(int(x['direct_profile_mention_count']) for x in out)}")
    print(f"  power range: {min(powers)}..{max(powers)}")
    print(f"  unique power values: {len(set(powers))}")
    print(f"  types used: {len(types)}")
    print(f"  unresolved type placeholders: {sum(x['type_status'] == 'unresolved_type_placeholder' for x in out)}")
    print(f"  categories: {dict(cats)}")
    print(f"  effect status: {dict(effects)}")
    print(f"  output: {args.output}")


if __name__ == "__main__":
    main()
