
    [DM_MOVE_BOOTSTRAP_ATTACK] =
    {
        .name = COMPOUND_STRING("DM-Bootstrap"),
        .description = COMPOUND_STRING("Temporary playtest attack."),
        .effect = EFFECT_HIT,
        .power = 40,
        .type = TYPE_NORMAL,
        .accuracy = 100,
        .pp = 35,
        .target = TARGET_SELECTED,
        .priority = 0,
        .category = DAMAGE_CATEGORY_PHYSICAL,
        .battleAnimScript = gBattleAnimMove_Pound,
    },
