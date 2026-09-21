#ifndef DIGITAL_MONSTER_ENGINE_RULES_H
#define DIGITAL_MONSTER_ENGINE_RULES_H

// Emerald runtime rules adopted by the Digital Monster replacement profile.
// Individual Digimon/Appmon base stats remain data inputs and are NOT defined here.

#define DM_LEVEL_MIN 1
#define DM_LEVEL_MAX 100

#define DM_PARTY_SIZE 6
#define DM_EQUIPPED_TECHNIQUES 4

#define DM_STAT_COUNT 6
#define DM_BATTLE_STAT_COUNT 8

#define DM_STAT_STAGE_MIN 0
#define DM_STAT_STAGE_NEUTRAL 6
#define DM_STAT_STAGE_MAX 12

#define DM_IV_MAX_PER_STAT 31
#define DM_EV_MAX_PER_STAT 252
#define DM_EV_MAX_TOTAL 510

#define DM_FRIENDSHIP_MAX 255
#define DM_NATURE_COUNT 25

#define DM_ENTITY_ID_BITS 11
#define DM_ENTITY_ID_MAX 2047
#define DM_TECHNIQUE_ID_BITS 12
#define DM_TECHNIQUE_ID_MAX 4095

#endif // DIGITAL_MONSTER_ENGINE_RULES_H
