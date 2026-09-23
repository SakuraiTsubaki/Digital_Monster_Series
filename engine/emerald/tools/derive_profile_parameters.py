#!/usr/bin/env python3
"""Derive Emerald-facing Digital Monster species parameters from official profile evidence.

The output deliberately does not redistribute Digimon Reference profile prose.
For each entity it stores only SHA-256, matched evidence signals, and project
gameplay interpretations. Official Japanese text is read from a temporary
full-census master JSON for Digimon and from the repository Appmon census.

This is an explainable first-pass interpreter, not a claim that the generated
numbers are official combat stats.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
EMERALD = ROOT / "engine" / "emerald"
GEN = EMERALD / "generated"
SPECIES_MAP = GEN / "species-id-map.csv"
APPMON_MASTER = ROOT / "appmon" / "appmon_master.csv"

STAGE_BASE = {
    "幼年期Ⅰ": 28,
    "幼年期Ⅱ": 38,
    "成長期": 58,
    "成熟期": 78,
    "完全体": 100,
    "究極体": 122,
    "アーマー体": 86,
    "ハイブリッド体": 94,
    "不明": 74,
    "並": 58,
    "超": 78,
    "極": 100,
    "神": 122,
    "－": 74,
}

GLOBAL_TERMS = [
    ("最強", 8), ("無敵", 8), ("究極", 5), ("絶大", 5), ("圧倒", 5),
    ("強大", 4), ("強力", 3), ("驚異", 3), ("凄まじ", 3), ("莫大", 4),
    ("超高", 3), ("超強", 4), ("神", 3), ("王", 2), ("皇帝", 3),
    ("弱い", -4), ("未熟", -4), ("不完全", -3), ("小型", -1),
]

STAT_TERMS = {
    "hp": [
        ("生命力", 5), ("体力", 4), ("持久", 4), ("不死", 5), ("再生", 4),
        ("回復", 3), ("巨体", 3), ("巨大", 2), ("タフ", 4), ("頑丈", 3),
        ("耐久", 4), ("長期戦", 4), ("生命", 2),
    ],
    "attack": [
        ("怪力", 6), ("腕力", 5), ("パワー", 4), ("力", 2), ("格闘", 4),
        ("拳", 3), ("パンチ", 3), ("キック", 3), ("爪", 3), ("牙", 3),
        ("剣", 3), ("刀", 3), ("斧", 3), ("槍", 3), ("斬", 3), ("突進", 3),
        ("破壊", 4), ("粉砕", 5), ("叩", 2), ("切断", 4),
    ],
    "defense": [
        ("防御", 5), ("装甲", 5), ("鎧", 4), ("甲殻", 4), ("盾", 4),
        ("硬い", 4), ("硬質", 4), ("頑丈", 4), ("耐久", 4), ("防壁", 5),
        ("バリア", 4), ("防ぐ", 3), ("無効", 4), ("鉄壁", 6), ("守り", 3),
    ],
    "speed": [
        ("最速", 7), ("高速", 5), ("超高速", 7), ("素早", 5), ("スピード", 4),
        ("俊敏", 5), ("機動", 4), ("瞬時", 4), ("一瞬", 3), ("瞬間", 3),
        ("飛翔", 3), ("飛行", 2), ("走", 2), ("加速", 4), ("敏捷", 5),
    ],
    "special_attack": [
        ("エネルギー", 3), ("ビーム", 4), ("レーザー", 4), ("波動", 4),
        ("衝撃波", 3), ("魔力", 5), ("魔法", 5), ("呪", 4), ("念", 4),
        ("炎", 3), ("火", 2), ("雷", 3), ("電撃", 4), ("電気", 3),
        ("氷", 3), ("冷気", 3), ("光", 3), ("闇", 3), ("毒", 3),
        ("音波", 4), ("データ", 2), ("電磁", 4), ("熱", 2), ("爆発", 3),
    ],
    "special_defense": [
        ("精神", 4), ("結界", 5), ("バリア", 4), ("耐性", 5), ("吸収", 4),
        ("無効", 4), ("再生", 3), ("回復", 3), ("神聖", 3), ("聖", 2),
        ("霊", 3), ("魔力", 2), ("防壁", 4), ("浄化", 4), ("守護", 4),
    ],
}

# TYPE_NORMAL is intentionally absent from semantic scoring. In profile-derived-v1
# it is the runtime placeholder for unresolved affinity, not a generic-taxonomy type.
TYPE_TERMS = {
    "TYPE_FIRE": ["炎", "火炎", "灼熱", "溶岩", "マグマ", "フレイム", "ファイア", "ブレイズ", "バーニング", "フレア", "ヒノタマ"],
    "TYPE_WATER": ["海", "深海", "水中", "海洋", "水棲", "水生", "アクア", "ウェーブ", "ウォーター", "タイダル", "オーシャン"],
    "TYPE_ELECTRIC": ["雷", "電撃", "電気", "電磁", "ライトニング", "サンダー", "エレクトリック", "スパーク", "ボルト"],
    "TYPE_GRASS": ["植物", "樹木", "森", "花", "草", "葉", "蔦", "種子"],
    "TYPE_ICE": ["氷", "冷気", "凍", "雪", "ブリザード", "フリーズ", "アイス", "フローズン"],
    "TYPE_FIGHTING": ["格闘", "武闘", "拳", "パンチ", "キック", "闘士", "戦士", "筋肉", "剣術", "剣士", "ナックル", "フィスト"],
    "TYPE_POISON": ["毒", "猛毒", "毒素", "ポイズン", "アシッド", "ヴェノム"],
    "TYPE_GROUND": ["大地", "地面", "地中", "土", "砂", "砂漠", "地震", "アース", "クエイク", "サンド"],
    "TYPE_FLYING": ["飛行", "飛翔", "翼", "空中", "大空", "天空", "鳥", "羽", "ウィング", "フェザー", "エアロ", "ハリケーン"],
    "TYPE_PSYCHIC": ["超能力", "精神", "念", "予知", "テレパシー", "催眠", "幻覚", "サイコ", "マインド"],
    "TYPE_BUG": ["昆虫", "甲虫", "幼虫", "蝶", "蛾", "蜂", "蟲"],
    "TYPE_ROCK": ["岩", "石", "鉱石", "鉱物", "クリスタル", "宝石", "ストーン"],
    "TYPE_GHOST": ["幽霊", "霊", "魂", "亡霊", "アンデッド", "死霊", "ゴースト", "ファントム", "ソウル", "スピリット"],
    "TYPE_DRAGON": ["竜", "龍", "ドラゴン", "恐竜", "ワイバーン"],
    "TYPE_DARK": ["闇", "暗黒", "悪魔", "魔王", "邪悪", "ダーク", "デーモン", "デビル", "ナイトメア", "ヘル"],
    "TYPE_STEEL": ["機械", "マシーン", "サイボーグ", "金属", "鋼", "鉄", "メカ", "アンドロイド", "機械化", "装甲", "メタル", "スチール", "アイアン"],
    "TYPE_FAIRY": ["妖精", "天使", "神聖", "聖なる", "聖", "フェアリー", "ホーリー", "セイント", "エンジェル"],
}

TYPE_STRONG_PROFILE_PHRASES = {
    "TYPE_FIRE": [
        "炎を放", "炎を吐", "炎を纏", "炎をまと", "炎を操",
        "火炎を放", "火炎を吐", "灼熱の炎", "爆炎",
        "全身から吹き出る熱い炎", "火炎瓶を投げ",
        "熱気を帯びた泡で攻撃", "エネルギーを熱線として吐き出",
        "黒き炎を巻き起こす",
    ],
    "TYPE_WATER": [
        "水中を", "海中を", "水流を", "水を操", "水圧", "津波",
        "液体を高圧で発射",
    ],
    "TYPE_ELECTRIC": [
        "電撃を放", "雷を放", "電気を纏", "電気をまと", "放電", "電磁",
    ],
    "TYPE_GRASS": [
        "植物を操", "樹木を操", "蔦を", "種子を", "花粉",
    ],
    "TYPE_ICE": [
        "氷を放", "氷を操", "冷気を", "凍らせ", "凍結", "氷結",
        "冷気の息を吐",
    ],
    "TYPE_FIGHTING": [
        "格闘技", "拳法", "武術", "肉弾戦", "近接戦闘",
        "一級の戦士", "格闘センス",
    ],
    "TYPE_POISON": [
        "毒液", "猛毒", "毒ガス", "毒を吐", "毒を放",
    ],
    "TYPE_GROUND": [
        "地中を", "大地を操", "地震を", "砂を操",
    ],
    "TYPE_FLYING": [
        "空を飛", "空中を飛", "飛翔する", "翼で飛",
        "飛行することも可能", "飛翔能力", "海上を飛び回る", "高速で飛",
        "乗せて飛ぶことができる",
    ],
    "TYPE_PSYCHIC": [
        "超能力", "念力", "精神攻撃", "催眠術",
    ],
    "TYPE_BUG": [
        "昆虫の", "甲虫の", "幼虫の",
    ],
    "TYPE_ROCK": [
        "岩石", "鉱石", "石化",
    ],
    "TYPE_GHOST": [
        "幽霊", "霊体", "亡霊", "魂を操",
    ],
    "TYPE_DRAGON": [
        "ドラゴンの", "竜の力", "龍の力",
    ],
    "TYPE_DARK": [
        "闇の力", "暗黒の力", "邪悪な力", "悪魔の力",
        "漆黒の闇", "悪と闇のみ", "闇だけに飲み込ませる",
    ],
    "TYPE_STEEL": [
        "金属の身体", "金属の体", "鋼の身体", "鋼の体",
        "鋼鉄の身体", "鋼鉄の体",
        "機械の身体", "機械の体", "サイボーグ",
    ],
    "TYPE_FAIRY": [
        "神聖な力", "聖なる力", "天使の力", "妖精の力",
    ],
}

STRUCTURAL_STEEL_PROFILE_PHRASES = [
    # Structural/body-integrated metal evidence. Generic "デジゾイド" or
    # "超金属" mentions are intentionally excluded because they often describe
    # a held weapon, claw, shield, Digimental, or other equipment rather than
    # the entity's own battle affinity.
    "全身がクロンデジゾイドの鎧で覆",
    "クロンデジゾイド製の鎧に身を包",
    "超金属「クロンデジゾイド」の鎧を身にまと",
    "クロンデジゾイド製のメタルヘッド",
    "ほぼ全身をメタル化",
    "ボディはブルーメタリックのクロンデジゾイドで作られて",
    "大地のメタル成分を取り込み、全身を超硬質化",
]


TYPE_FIELD_BONUS = {
    "アンデッド": {"TYPE_GHOST": 5, "TYPE_DARK": 3},
    "ゴースト": {"TYPE_GHOST": 6},
    "悪魔": {"TYPE_DARK": 5},
    "魔王": {"TYPE_DARK": 6},
    "魔神": {"TYPE_DARK": 6},
    "邪神": {"TYPE_DARK": 6},
    "魔人": {"TYPE_DARK": 5, "TYPE_PSYCHIC": 2},
    "鬼人": {"TYPE_DARK": 5, "TYPE_FIGHTING": 3},
    "天使": {"TYPE_FAIRY": 5, "TYPE_FLYING": 2},
    "妖精": {"TYPE_FAIRY": 5},
    "神人": {"TYPE_FAIRY": 5, "TYPE_FIGHTING": 3},
    "聖騎士": {"TYPE_FAIRY": 6, "TYPE_FIGHTING": 5},
    "暗黒騎士": {"TYPE_DARK": 7},
    "幻獣": {"TYPE_FAIRY": 5},
    "竜": {"TYPE_DRAGON": 5},
    "龍": {"TYPE_DRAGON": 5},
    "ドラゴン": {"TYPE_DRAGON": 5},
    "恐竜": {"TYPE_DRAGON": 3},
    "マシーン": {"TYPE_STEEL": 5},
    "機械": {"TYPE_STEEL": 5},
    "サイボーグ": {"TYPE_STEEL": 5},
    "武器": {"TYPE_STEEL": 5, "TYPE_FIGHTING": 3},
    "防具": {"TYPE_STEEL": 5},
    "昆虫": {"TYPE_BUG": 5},
    "幼虫": {"TYPE_BUG": 6},
    "植物": {"TYPE_GRASS": 5},
    "水棲": {"TYPE_WATER": 5},
    "水生": {"TYPE_WATER": 5},
    "海獣": {"TYPE_WATER": 4},
    "海人": {"TYPE_WATER": 5},
    "古代魚": {"TYPE_WATER": 5},
    "両生類": {"TYPE_WATER": 5},
    "甲殻類": {"TYPE_WATER": 5, "TYPE_BUG": 2},
    "鳥": {"TYPE_FLYING": 5},
    "獣人": {"TYPE_FIGHTING": 5},
    "戦士": {"TYPE_FIGHTING": 5},
    "聖": {"TYPE_FAIRY": 3},
    "岩": {"TYPE_ROCK": 4},
    "鉱物": {"TYPE_ROCK": 4},
    "爬虫類": {"TYPE_DRAGON": 4},
    "魔獣": {"TYPE_DARK": 4},
    "聖獣": {"TYPE_FAIRY": 4},
    "妖獣": {"TYPE_FAIRY": 3, "TYPE_DARK": 2},
    "火炎": {"TYPE_FIRE": 6},
    "鉱石": {"TYPE_ROCK": 5, "TYPE_STEEL": 2},
    "パペット": {"TYPE_GHOST": 2},
}

ABILITY_RULES = [
    ("ABILITY_REGENERATOR", [
        ("再生能力", 9), ("自己再生", 9), ("驚異的な再生", 8),
        ("傷を再生", 8), ("治癒能力", 8),
    ]),
    ("ABILITY_LEVITATE", [
        ("浮遊能力", 9), ("空中に浮遊", 8), ("宙に浮", 8), ("浮遊して", 7),
    ]),
    ("ABILITY_SPEED_BOOST", [
        ("加速し続け", 9), ("速度を上げ続け", 9), ("どんどん加速", 8),
    ]),
    ("ABILITY_STURDY", [
        ("破壊不能", 10), ("決して壊れ", 9), ("非常に頑丈", 8), ("強固な装甲", 8),
    ]),
    ("ABILITY_BATTLE_ARMOR", [
        ("全身を装甲", 8), ("全身を鎧", 8), ("重装甲", 8), ("甲殻に覆", 7),
    ]),
    ("ABILITY_INTIMIDATE", [
        ("威圧する", 8), ("威圧感", 7), ("恐怖を与", 8), ("相手を怯ませ", 8),
    ]),
    ("ABILITY_POISON_TOUCH", [
        ("毒の爪", 9), ("毒の牙", 9), ("触れた相手を毒", 10), ("猛毒を帯び", 8),
    ]),
    ("ABILITY_FLASH_FIRE", [
        ("炎を吸収", 10), ("火炎を吸収", 10),
    ]),
    ("ABILITY_WATER_ABSORB", [
        ("水を吸収", 10), ("水分を吸収", 9),
    ]),
    ("ABILITY_VOLT_ABSORB", [
        ("電気を吸収", 10), ("電撃を吸収", 10),
    ]),
    ("ABILITY_SWIFT_SWIM", [
        ("水中を高速", 9), ("高速で泳", 9), ("泳ぐ速度", 8),
    ]),
    ("ABILITY_HUGE_POWER", [
        ("怪力を誇", 9), ("驚異的な腕力", 9), ("桁外れの力", 9),
    ]),
    ("ABILITY_IRON_FIST", [
        ("拳闘の達人", 9), ("パンチを得意", 8), ("拳による攻撃を得意", 8),
    ]),
    ("ABILITY_SHARPNESS", [
        ("剣術の達人", 9), ("刀剣の達人", 9), ("斬撃を得意", 8),
    ]),
    ("ABILITY_MAGIC_BOUNCE", [
        ("攻撃を反射", 9), ("技を反射", 9), ("跳ね返す能力", 9),
    ]),
]

GROWTH_FAST_TERMS = ["急成長", "急速に成長", "成長が早", "成長速度", "短期間"]
GROWTH_SLOW_TERMS = ["長い年月", "長期間", "永い", "古代", "長寿", "成熟"]
GROWTH_ERRATIC_TERMS = ["不安定", "暴走", "変化し続け", "予測不能", "ランダム"]
GROWTH_FLUCTUATING_TERMS = ["環境によって", "状況によって", "条件によって", "変動"]

STAT_COLUMNS = [
    ("hp", "base_hp"),
    ("attack", "base_attack"),
    ("defense", "base_defense"),
    ("speed", "base_speed"),
    ("special_attack", "base_sp_attack"),
    ("special_defense", "base_sp_defense"),
]


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def clamp(value: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, value))


def stage_base(level: str) -> int:
    level = level or ""
    for key, value in STAGE_BASE.items():
        if key in level:
            return value
    return STAGE_BASE["不明"]


def score_terms(text: str, terms: list[tuple[str, int]], prefix: str) -> tuple[int, list[str]]:
    score = 0
    hits: list[str] = []
    for term, weight in terms:
        count = min(text.count(term), 3)
        if count:
            score += weight * count
            hits.append(f"{prefix}:{term}:{weight * count:+d}")
    return score, hits


def mask_profile_self_names(profile: str, names: list[str]) -> tuple[str, int]:
    """Exclude exact self-name mentions from profile keyword scoring.

    Entity names are not currently a gameplay-evidence input. Official profiles
    often repeat the subject's own name, and substrings inside that name (for
    example サンド in サンドリモン) must not be double-counted as profile
    semantics. The original profile remains untouched for SHA/evidence lineage.
    """
    masked = profile
    removed = 0
    unique_names = sorted(
        {name.strip() for name in names if name and name.strip()},
        key=len,
        reverse=True,
    )
    for name in unique_names:
        count = masked.count(name)
        if count:
            masked = masked.replace(name, "")
            removed += count
    return masked, removed


def type_scores(profile: str, official_type: str, moves: str) -> tuple[dict[str, int], list[str]]:
    scores = Counter()
    hits: list[str] = []
    for type_name, terms in TYPE_TERMS.items():
        for term in terms:
            p = min(profile.count(term), 3)
            m = min(moves.count(term), 3)
            if p:
                scores[type_name] += p * 2
                hits.append(f"type:{type_name}:{term}:profile:+{p * 2}")
            if m:
                scores[type_name] += m * 4
                hits.append(f"type:{type_name}:{term}:move:+{m * 4}")

    # Strong semantic phrases describe an actual elemental/combat behavior,
    # unlike generic nouns such as a habitat mention ("forest", "sea", etc.).
    # One explicit phrase is therefore enough to clear the normal threshold.
    for type_name, phrases in TYPE_STRONG_PROFILE_PHRASES.items():
        for phrase in phrases:
            count = min(profile.count(phrase), 2)
            if count:
                weight = count * 5
                scores[type_name] += weight
                hits.append(f"type:{type_name}:{phrase}:strong_profile:+{weight}")

    for token, bonuses in TYPE_FIELD_BONUS.items():
        if token in (official_type or ""):
            for type_name, weight in bonuses.items():
                scores[type_name] += weight
                hits.append(f"type:{type_name}:{token}:official_type:+{weight}")

    # Body-integrated or whole-body metal is direct Steel evidence. Keep this
    # separate from generic material/equipment mentions so it can support a
    # secondary Steel affinity without making every Digizoid weapon user Steel.
    structural_hits = [
        phrase for phrase in STRUCTURAL_STEEL_PROFILE_PHRASES
        if phrase in profile
    ]
    for phrase in structural_hits:
        scores["TYPE_STEEL"] += 5
        hits.append(f"type:TYPE_STEEL:{phrase}:structural_profile:+5")
    return dict(scores), hits


def choose_types(scores: dict[str, int]) -> tuple[str, str, list[str], str]:
    if not scores:
        return (
            "TYPE_NORMAL",
            "",
            ["type_placeholder:TYPE_NORMAL:no_specialized_affinity_evidence"],
            "unresolved_no_specialized_type_evidence",
        )
    ranked = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
    first, first_score = ranked[0]
    if first_score < 5:
        return (
            "TYPE_NORMAL",
            "",
            [f"type_candidate:{first}:{first_score}", "type_placeholder:TYPE_NORMAL:low_evidence"],
            "unresolved_low_type_evidence",
        )
    second = ""
    signals = [f"type_choice:{first}:{first_score}"]
    if len(ranked) > 1:
        candidate, score = ranked[1]
        if score >= 5 and score >= math.ceil(first_score * 0.65):
            second = candidate
            signals.append(f"type_choice:{candidate}:{score}")
    return first, second, signals, "resolved_profile_evidence"


def infer_ability(profile: str) -> tuple[str, str, list[str]]:
    scores = Counter()
    hits: list[str] = []
    for ability, terms in ABILITY_RULES:
        for term, weight in terms:
            count = min(profile.count(term), 2)
            if count:
                scores[ability] += weight * count
                hits.append(f"ability:{ability}:{term}:+{weight * count}")
    if not scores:
        return "ABILITY_NONE", "unresolved_no_passive_evidence", []
    ranked = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
    ability, score = ranked[0]
    if score < 7:
        return "ABILITY_NONE", "unresolved_low_passive_evidence", hits
    hits.append(f"ability_choice:{ability}:{score}")
    return ability, "resolved_profile_passive_evidence", hits


def growth_rate(profile: str, base: int, global_score: int) -> tuple[str, str]:
    if any(term in profile for term in GROWTH_ERRATIC_TERMS):
        return "GROWTH_ERRATIC", "growth:profile:erratic"
    if any(term in profile for term in GROWTH_FLUCTUATING_TERMS):
        return "GROWTH_FLUCTUATING", "growth:profile:fluctuating"
    if any(term in profile for term in GROWTH_FAST_TERMS):
        return "GROWTH_FAST", "growth:profile:fast"
    if any(term in profile for term in GROWTH_SLOW_TERMS):
        return "GROWTH_SLOW", "growth:profile:slow"
    if base >= 115 or global_score >= 12:
        return "GROWTH_SLOW", "growth:official_stage_plus_profile_power:slow"
    if base >= 90:
        return "GROWTH_MEDIUM_SLOW", "growth:official_stage_plus_profile_power:medium_slow"
    return "GROWTH_MEDIUM_FAST", "growth:official_stage_plus_profile_power:medium_fast"


def profile_digest(profile: str) -> str:
    return hashlib.sha256(profile.encode("utf-8")).hexdigest()


def derive_ev_yields(stat_scores: dict[str, int]) -> tuple[dict[str, int], str, list[str]]:
    """Map explicit official-profile stat emphasis to Emerald EV rewards.

    No level/grade table, BST threshold, hash or random assignment is used.
    Species with no stat-specialization evidence intentionally yield 0 EVs.
    """
    yields = {name: 0 for name, _ in STAT_COLUMNS}
    positive = [(name, max(0, stat_scores.get(name, 0))) for name, _ in STAT_COLUMNS]
    positive = [(name, score) for name, score in positive if score > 0]
    if not positive:
        return yields, "unresolved_no_stat_specialization_evidence", [
            "ev_yield:0:no_official_stat_specialization_evidence"
        ]

    positive.sort(
        key=lambda item: (
            -item[1],
            [name for name, _ in STAT_COLUMNS].index(item[0]),
        )
    )
    peak = positive[0][1]
    total = 1 + int(peak >= 8) + int(peak >= 16)
    cutoff = max(1, math.ceil(peak * 0.75))
    eligible = [name for name, score in positive if score >= cutoff]

    remaining = total
    index = 0
    while remaining:
        name = eligible[index % len(eligible)]
        if yields[name] < 3:
            yields[name] += 1
            remaining -= 1
        index += 1

    hits = [
        f"ev_yield:{name}:{value}:profile_stat_evidence"
        for name, value in yields.items()
        if value
    ]
    return yields, "resolved_profile_stat_evidence", hits


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--digimon-master-json", type=Path, required=True)
    ap.add_argument("--output", type=Path, default=GEN / "profile-derived-parameters.csv")
    args = ap.parse_args()

    species = rows(SPECIES_MAP)
    if len(species) != 1468:
        raise SystemExit(f"expected 1468 species-map rows, got {len(species)}")

    digimon_rows = json.loads(args.digimon_master_json.read_text(encoding="utf-8"))
    digimon = {x["directory_name"]: x for x in digimon_rows}
    if len(digimon) != 1320:
        raise SystemExit(f"expected 1320 Digimon profile rows, got {len(digimon)}")

    appmon_rows = rows(APPMON_MASTER)
    appmon = {f"appmon_{int(x['id']):03d}": x for x in appmon_rows}
    if len(appmon) != 148:
        raise SystemExit(f"expected 148 Appmon profile rows, got {len(appmon)}")

    out: list[dict[str, str | int]] = []
    for src in species:
        kind = src["source_kind"]
        source_id = src["source_id"]
        if kind == "digimon":
            meta = digimon[source_id]
            profile = meta.get("profile_ja") or ""
            official_type = meta.get("type_raw") or src.get("official_type") or ""
            moves_list = meta.get("special_moves") or []
            moves = " | ".join(moves_list)
        elif kind == "appmon":
            meta = appmon[source_id]
            profile = meta.get("profile_ja") or ""
            official_type = meta.get("app_name_ja") or src.get("official_type") or ""
            moves = meta.get("special_moves_ja") or ""
        else:
            raise SystemExit(f"unsupported source_kind: {kind}")

        if not profile.strip():
            raise SystemExit(f"{source_id}: missing official Japanese profile")

        expected_sha = ""
        if kind == "digimon":
            expected_sha = meta.get("profile_ja_sha256") or ""
        actual_sha = profile_digest(profile)
        if expected_sha and actual_sha != expected_sha:
            raise SystemExit(
                f"{source_id}: profile SHA mismatch: collected {actual_sha}, census {expected_sha}"
            )

        profile_for_scoring, self_name_mentions_ignored = mask_profile_self_names(
            profile,
            [src.get("name_ja") or "", meta.get("name_ja") or ""],
        )

        level = src.get("level_or_grade") or ""
        base = stage_base(level)
        global_score, global_hits = score_terms(profile_for_scoring, GLOBAL_TERMS, "power")

        stat_values: dict[str, int] = {}
        stat_evidence_scores: dict[str, int] = {}
        stat_hits_all: list[str] = []
        specialization_count = 0
        for stat_name, output_name in STAT_COLUMNS:
            score, hits = score_terms(profile_for_scoring + "\n" + moves, STAT_TERMS[stat_name], stat_name)
            stat_evidence_scores[stat_name] = score
            if score:
                specialization_count += 1
            stat_hits_all.extend(hits)
            value = clamp(round(base + global_score * 1.8 + score * 4.5), 1, 255)
            stat_values[output_name] = value
        if specialization_count == 0:
            stat_hits_all.append("stats:balanced:no_specialization_signal_in_official_text")

        ev_yields, ev_yield_status, ev_yield_hits = derive_ev_yields(stat_evidence_scores)

        tscores, thits = type_scores(profile_for_scoring, official_type, moves)
        type1, type2, type_choice_hits, type_status = choose_types(tscores)
        ability1, ability_status, ability_hits = infer_ability(profile_for_scoring)

        stat_list = [stat_values[x[1]] for x in STAT_COLUMNS]
        bst = sum(stat_list)
        avg = sum(stat_list) / len(stat_list)
        peak = max(stat_list)
        catch_rate = clamp(round(275 - avg * 1.15 - peak * 0.20 - max(0, global_score) * 1.8), 3, 255)
        exp_yield = clamp(round(20 + avg * 1.55 + peak * 0.45 + max(0, global_score) * 2.5), 20, 65535)
        growth, growth_signal = growth_rate(profile_for_scoring, base, global_score)

        self_name_hits = (
            [f"profile_self_name_mentions_ignored:{self_name_mentions_ignored}"]
            if self_name_mentions_ignored
            else []
        )
        evidence = self_name_hits + global_hits + stat_hits_all + ev_yield_hits + thits + type_choice_hits + ability_hits + [growth_signal]
        if not evidence:
            evidence = ["profile:read:no_keyword_specialization"]

        confidence_points = min(8, len(global_hits) + len(stat_hits_all)) + min(8, len(thits))
        confidence = "high" if confidence_points >= 10 else "medium" if confidence_points >= 4 else "low"
        if type_status != "resolved_profile_evidence" and confidence == "high":
            confidence = "medium"

        row = {
            "species_id": int(src["emerald_species_id"]),
            "source_kind": kind,
            "source_id": source_id,
            "name_ja": src["name_ja"],
            "official_detail_url": src["source_url"],
            "official_level_or_grade": level,
            "official_type_or_app_type": official_type,
            "official_attribute": src.get("official_attribute") or "",
            "profile_sha256": actual_sha,
            "profile_char_count": len(profile),
            "evidence_signals": " ; ".join(evidence[:64]),
            "base_hp": stat_values["base_hp"],
            "base_attack": stat_values["base_attack"],
            "base_defense": stat_values["base_defense"],
            "base_speed": stat_values["base_speed"],
            "base_sp_attack": stat_values["base_sp_attack"],
            "base_sp_defense": stat_values["base_sp_defense"],
            "bst": bst,
            "ev_yield_hp": ev_yields["hp"],
            "ev_yield_attack": ev_yields["attack"],
            "ev_yield_defense": ev_yields["defense"],
            "ev_yield_speed": ev_yields["speed"],
            "ev_yield_sp_attack": ev_yields["special_attack"],
            "ev_yield_sp_defense": ev_yields["special_defense"],
            "ev_yield_status": ev_yield_status,
            "battle_type_1": type1,
            "battle_type_2": type2,
            "battle_type_status": type_status,
            "ability_1": ability1,
            "ability_2": "ABILITY_NONE",
            "ability_hidden": "ABILITY_NONE",
            "ability_status": ability_status,
            "catch_rate": catch_rate,
            "exp_yield": exp_yield,
            "growth_rate": growth,
            "confidence": confidence,
            "derivation_version": "profile-derived-v1",
        }
        out.append(row)

    ids = [int(x["species_id"]) for x in out]
    if ids != list(range(1, 1469)):
        raise SystemExit("species IDs are not exactly 1..1468")

    resolved_normal = [
        x for x in out
        if x["battle_type_status"] == "resolved_profile_evidence"
        and (x["battle_type_1"] == "TYPE_NORMAL" or x["battle_type_2"] == "TYPE_NORMAL")
    ]
    if resolved_normal:
        sample = ", ".join(f"{x['species_id']}:{x['name_ja']}" for x in resolved_normal[:8])
        raise SystemExit(f"resolved TYPE_NORMAL is forbidden in profile-derived-v1: {sample}")

    fields = list(out[0].keys())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(out)

    unique_bst = len({int(x["bst"]) for x in out})
    unique_types = len({(x["battle_type_1"], x["battle_type_2"]) for x in out})
    print("Profile-derived species parameters generated")
    print(f"  entities: {len(out)}")
    print(f"  unique BST totals: {unique_bst}")
    print(f"  unique type combinations: {unique_types}")
    print(f"  resolved battle types: {sum(x['battle_type_status'] == 'resolved_profile_evidence' for x in out)}")
    print(f"  resolved profile abilities: {sum(x['ability_status'] == 'resolved_profile_passive_evidence' for x in out)}")
    ev_totals = Counter(
        sum(int(x[field]) for field in [
            "ev_yield_hp", "ev_yield_attack", "ev_yield_defense",
            "ev_yield_speed", "ev_yield_sp_attack", "ev_yield_sp_defense",
        ])
        for x in out
    )
    print(f"  EV-yield totals: {dict(sorted(ev_totals.items()))}")
    print(f"  BST range: {min(int(x['bst']) for x in out)}..{max(int(x['bst']) for x in out)}")
    print(f"  per-stat range: {min(min(int(x[c]) for c in [y[1] for y in STAT_COLUMNS]) for x in out)}.."
          f"{max(max(int(x[c]) for c in [y[1] for y in STAT_COLUMNS]) for x in out)}")
    print(f"  output: {args.output}")


if __name__ == "__main__":
    main()
