#!/usr/bin/env python3
"""Apply the Digital_Monster_Series integration to the pinned pokeemerald-expansion tree.

This intentionally targets one exact upstream commit. It uses checked text
replacements rather than fuzzy patches, so upstream drift fails loudly.
"""
from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path

PINNED = "75b806a3ab57a81ff1eb6179288981f0b3cc3050"


def read(root: Path, rel: str) -> str:
    return (root / rel).read_text(encoding="utf-8")


def write(root: Path, rel: str, text: str) -> None:
    (root / rel).write_text(text, encoding="utf-8")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one match, found {count}")
    return text.replace(old, new, 1)


def sub_once(text: str, pattern: str, repl: str, label: str) -> str:
    text2, count = re.subn(pattern, repl, text, count=1, flags=re.M | re.S)
    if count != 1:
        raise SystemExit(f"{label}: expected one regex match, found {count}")
    return text2


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("engine", type=Path)
    args = p.parse_args()
    root = args.engine.resolve()

    head = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
    if head != PINNED:
        raise SystemExit(f"wrong upstream HEAD: {head}; expected {PINNED}")

    # 12-bit persistent move IDs without growing PokemonSubstruct1.
    rel = "include/pokemon.h"
    t = read(root, rel)
    pattern = r"""    enum Move move1:11; // 2047 moves\.\n    u16 evolutionTracker1:5;\n    enum Move move2:11; // 2047 moves\.\n    u16 evolutionTracker2:5;\n    enum Move move3:11; // 2047 moves\.\n    u16 unused_04:5;\n    enum Move move4:11; // 2047 moves\.\n    u16 unused_06:3;"""
    repl = """    enum Move move1:12; // 4095 moves.
    u16 evolutionTracker1Lo:4;
    enum Move move2:12; // 4095 moves.
    u16 evolutionTracker1Hi:1;
    u16 evolutionTracker2Lo:3;
    enum Move move3:12; // 4095 moves.
    u16 evolutionTracker2Hi:2;
    u16 unused_04:2;
    enum Move move4:12; // 4095 moves.
    u16 unused_06:2;"""
    t = sub_once(t, pattern, repl, "PokemonSubstruct1 move repack")
    write(root, rel, t)

    rel = "src/pokemon.c"
    t = read(root, rel)
    t = replace_once(
        t,
        """.tracker1 = substruct1->evolutionTracker1,
                    .tracker2 = substruct1->evolutionTracker2,""",
        """.tracker1 = substruct1->evolutionTracker1Lo
                              | (substruct1->evolutionTracker1Hi << 4),
                    .tracker2 = substruct1->evolutionTracker2Lo
                              | (substruct1->evolutionTracker2Hi << 3),""",
        "evolution tracker getter",
    )
    t = replace_once(
        t,
        """substruct1->evolutionTracker1 = evoTracker.tracker1;
            substruct1->evolutionTracker2 = evoTracker.tracker2;""",
        """substruct1->evolutionTracker1Lo = evoTracker.tracker1 & 0xF;
            substruct1->evolutionTracker1Hi = (evoTracker.tracker1 >> 4) & 0x1;
            substruct1->evolutionTracker2Lo = evoTracker.tracker2 & 0x7;
            substruct1->evolutionTracker2Hi = (evoTracker.tracker2 >> 3) & 0x3;""",
        "evolution tracker setter",
    )
    t = replace_once(
        t,
        '#if P_LVL_UP_LEARNSETS >= GEN_9\n#include "data/pokemon/level_up_learnsets/gen_9.h" // Scarlet/Violet',
        '#ifdef DIGITAL_MONSTER_SERIES\n#include "data/pokemon/level_up_learnsets/digital_monster.h"\n#elif P_LVL_UP_LEARNSETS >= GEN_9\n#include "data/pokemon/level_up_learnsets/gen_9.h" // Scarlet/Violet',
        "Digital Monster level-up learnset selection",
    )
    write(root, rel, t)

    # Replace Pokemon SpeciesInfo includes with the Digital Monster catalog.
    rel = "src/data/pokemon/species_info.h"
    t = read(root, rel)
    old = """    #include "species_info/gen_1_families.h"
    #include "species_info/gen_2_families.h"
    #include "species_info/gen_3_families.h"
    #include "species_info/gen_4_families.h"
    #include "species_info/gen_5_families.h"
    #include "species_info/gen_6_families.h"
    #include "species_info/gen_7_families.h"
    #include "species_info/gen_8_families.h"
    #include "species_info/gen_9_families.h"
"""
    new = """#ifdef DIGITAL_MONSTER_SERIES
    #include "species_info/digital_monster_families.h"
#else
    #include "species_info/gen_1_families.h"
    #include "species_info/gen_2_families.h"
    #include "species_info/gen_3_families.h"
    #include "species_info/gen_4_families.h"
    #include "species_info/gen_5_families.h"
    #include "species_info/gen_6_families.h"
    #include "species_info/gen_7_families.h"
    #include "species_info/gen_8_families.h"
    #include "species_info/gen_9_families.h"
#endif
"""
    t = replace_once(t, old, new, "SpeciesInfo catalog switch")
    write(root, rel, t)

    # Append Digital Monster techniques after the engine's stock move catalog.
    rel = "include/constants/moves.h"
    t = read(root, rel)
    t = replace_once(
        t,
        "    MOVES_COUNT_ALL = MOVES_COUNT_DYNAMAX,",
        """#ifdef DIGITAL_MONSTER_SERIES
#include "constants/digital_monster_move_enum.inc"
    MOVES_COUNT_ALL = DM_MOVES_COUNT,
#else
    MOVES_COUNT_ALL = MOVES_COUNT_DYNAMAX,
#endif""",
        "move catalog append",
    )
    write(root, rel, t)

    rel = "src/data/moves_info.h"
    t = read(root, rel)
    marker = "\n};\n"
    pos = t.rfind(marker)
    if pos < 0:
        raise SystemExit("moves_info: final array terminator not found")
    t = t[:pos] + '\n#ifdef DIGITAL_MONSTER_SERIES\n#include "digital_monster/moves_info.inc"\n#endif\n' + t[pos:]
    write(root, rel, t)

    # Disable Pokemon family/form systems whose numeric IDs overlap 1..1468.
    rel = "include/config/species_enabled.h"
    t = read(root, rel)
    marker = "// To disable specific families, replace P_GEN_x_POKEMON with FALSE.\n"
    safety = """#ifdef DIGITAL_MONSTER_SERIES
#undef P_GEN_1_POKEMON
#undef P_GEN_2_POKEMON
#undef P_GEN_3_POKEMON
#undef P_GEN_4_POKEMON
#undef P_GEN_5_POKEMON
#undef P_GEN_6_POKEMON
#undef P_GEN_7_POKEMON
#undef P_GEN_8_POKEMON
#undef P_GEN_9_POKEMON
#define P_GEN_1_POKEMON FALSE
#define P_GEN_2_POKEMON FALSE
#define P_GEN_3_POKEMON FALSE
#define P_GEN_4_POKEMON FALSE
#define P_GEN_5_POKEMON FALSE
#define P_GEN_6_POKEMON FALSE
#define P_GEN_7_POKEMON FALSE
#define P_GEN_8_POKEMON FALSE
#define P_GEN_9_POKEMON FALSE
#undef P_MEGA_EVOLUTIONS
#undef P_PRIMAL_REVERSIONS
#undef P_ULTRA_BURST_FORMS
#undef P_GIGANTAMAX_FORMS
#undef P_TERA_FORMS
#undef P_FUSION_FORMS
#undef P_REGIONAL_FORMS
#undef P_ALOLAN_FORMS
#undef P_GALARIAN_FORMS
#undef P_HISUIAN_FORMS
#undef P_PALDEAN_FORMS
#undef P_PIKACHU_EXTRA_FORMS
#undef P_COSPLAY_PIKACHU_FORMS
#undef P_CAP_PIKACHU_FORMS
#undef P_CROSS_GENERATION_EVOS
#undef P_GEN_2_CROSS_EVOS
#undef P_GEN_3_CROSS_EVOS
#undef P_GEN_4_CROSS_EVOS
#undef P_GEN_6_CROSS_EVOS
#undef P_GEN_8_CROSS_EVOS
#undef P_GEN_9_CROSS_EVOS
#define P_MEGA_EVOLUTIONS FALSE
#define P_PRIMAL_REVERSIONS FALSE
#define P_ULTRA_BURST_FORMS FALSE
#define P_GIGANTAMAX_FORMS FALSE
#define P_TERA_FORMS FALSE
#define P_FUSION_FORMS FALSE
#define P_REGIONAL_FORMS FALSE
#define P_ALOLAN_FORMS FALSE
#define P_GALARIAN_FORMS FALSE
#define P_HISUIAN_FORMS FALSE
#define P_PALDEAN_FORMS FALSE
#define P_PIKACHU_EXTRA_FORMS FALSE
#define P_COSPLAY_PIKACHU_FORMS FALSE
#define P_CAP_PIKACHU_FORMS FALSE
#define P_CROSS_GENERATION_EVOS FALSE
#define P_GEN_2_CROSS_EVOS FALSE
#define P_GEN_3_CROSS_EVOS FALSE
#define P_GEN_4_CROSS_EVOS FALSE
#define P_GEN_6_CROSS_EVOS FALSE
#define P_GEN_8_CROSS_EVOS FALSE
#define P_GEN_9_CROSS_EVOS FALSE
#endif

"""
    t = replace_once(t, marker, safety + marker, "species family safety gate")
    write(root, rel, t)

    rel = "include/config/pokemon.h"
    t = read(root, rel)
    marker = "#define P_CRIES_ENABLED                  TRUE        // If TRUE, Pokémon will have cries. Disabling this saves around a LOT of ROM space (over 25%!), but instead we recommend disabling individual unused Pokémon families in include/config/species_enabled.h.\n"
    override = """#ifdef DIGITAL_MONSTER_SERIES
#undef P_GENDER_DIFFERENCES
#undef P_CUSTOM_GENDER_DIFF_ICONS
#undef P_FOOTPRINTS
#undef P_CRIES_ENABLED
#define P_GENDER_DIFFERENCES FALSE
#define P_CUSTOM_GENDER_DIFF_ICONS FALSE
#define P_FOOTPRINTS FALSE
#define P_CRIES_ENABLED FALSE
#endif
"""
    t = replace_once(t, marker, marker + override, "species graphics safety gate")
    write(root, rel, t)

    rel = "include/config/overworld.h"
    t = read(root, rel)
    marker = "#define OW_POKEMON_OBJECT_EVENTS       TRUE       // Adds Object Event fields for every species. Can be used for NPCs using the OBJ_EVENT_GFX_SPECIES macro (eg. OBJ_EVENT_GFX_SPECIES(BULBASAUR))\n"
    override = """#ifdef DIGITAL_MONSTER_SERIES
#undef OW_POKEMON_OBJECT_EVENTS
#define OW_POKEMON_OBJECT_EVENTS FALSE
#endif
"""
    t = replace_once(t, marker, marker + override, "overworld species safety gate")
    write(root, rel, t)

    # Build flag -> C preprocessor define.
    rel = "Makefile"
    t = read(root, rel)
    marker = "CPPFLAGS := $(INCLUDE_CPP_ARGS) -Wno-trigraphs -DMODERN=1 -DTESTING=$(TEST) -D$(GAME_VERSION) -std=gnu17\n"
    override = """ifeq ($(DIGITAL_MONSTER_SERIES),1)
override CPPFLAGS += -DDIGITAL_MONSTER_SERIES=1
endif
"""
    t = replace_once(t, marker, marker + override, "Digital Monster build flag")
    write(root, rel, t)

    print("Applied Digital_Monster_Series integration to pinned engine.")

if __name__ == "__main__":
    main()
