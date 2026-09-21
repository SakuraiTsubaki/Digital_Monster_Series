#ifndef DIGITAL_MONSTER_CAPACITY_H
#define DIGITAL_MONSTER_CAPACITY_H

// Generated from the verified Digital_Monster_Series datasets.
// IDs are stable only for the current generated mapping files.

#define DM_DIGIMON_REFERENCE_COUNT 1320
#define DM_APPMON_COUNT 148
#define DM_ENTITY_COUNT 1468

#define DM_ENTITY_ID_BITS 11
#define DM_ENTITY_ID_MAX 2047
#define DM_ENTITY_ID_REMAINING 579

#define DM_TECHNIQUE_ASSIGNMENT_COUNT 2872
#define DM_TECHNIQUE_COUNT 2557
#define DM_TECHNIQUE_ID_BITS_CURRENT 11
#define DM_TECHNIQUE_ID_MAX_CURRENT 2047
#define DM_TECHNIQUE_ID_BITS_REQUIRED 12
#define DM_TECHNIQUE_ID_MAX_TARGET 4095
#define DM_TECHNIQUE_ID_OVERFLOW_AT_11_BITS 510

#if DM_ENTITY_COUNT > DM_ENTITY_ID_MAX
#error "Digital Monster entity catalog exceeds the Emerald species backing field"
#endif

#if DM_TECHNIQUE_COUNT > DM_TECHNIQUE_ID_MAX_TARGET
#error "Digital Monster technique catalog exceeds the planned 12-bit move field"
#endif

#endif // DIGITAL_MONSTER_CAPACITY_H
