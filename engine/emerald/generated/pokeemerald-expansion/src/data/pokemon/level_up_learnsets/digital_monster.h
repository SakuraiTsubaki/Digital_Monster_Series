#define LEVEL_UP_MOVE(lvl, moveLearned) {.move = moveLearned, .level = lvl}
#define LEVEL_UP_END {.move = LEVEL_UP_MOVE_END, .level = 0}

static const struct LevelUpMove sNoneLevelUpLearnset[] = {
    LEVEL_UP_MOVE(1, DM_MOVE_BOOTSTRAP_ATTACK),
    LEVEL_UP_END
};


#include "digital_monster_part_1.h"
#include "digital_monster_part_2.h"
#include "digital_monster_part_3.h"
#include "digital_monster_part_4.h"
