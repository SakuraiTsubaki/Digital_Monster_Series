# Emerald battle rules adopted by Digital_Monster_Series

The Digital Monster replacement profile uses the Emerald/pokeemerald-expansion
runtime as its game engine. Engine rules and Digital Monster content values are
kept separate.

## Adopted engine rules

- Level: 1–100
- Active party: 6
- Equipped techniques: 4
- Stats: HP, Attack, Defense, Speed, Special Attack, Special Defense
- Battle-only stages: Accuracy and Evasion
- IV: 0–31 per stat
- EV: 0–252 per stat, 510 total
- Stat stages: 0–12, neutral 6 (= -6 through +6)
- Modern physical/special split under the pinned GEN_LATEST profile
- Six existing experience growth curves remain available

The exact Emerald stat calculations are retained:

- HP = floor(((2 × BaseHP + IV + floor(EV/4)) × Level) / 100) + Level + 10
- Other stats = NatureModifier(floor(((2 × BaseStat + IV + floor(EV/4)) × Level) / 100) + 5)

## Not assigned yet

The formulas are engine parameters; **BaseHP/BaseAttack/etc. are content
parameters**. No official dataset currently in this repository supplies a
single canonical six-stat combat table for all 1,468 entities, so those values
remain blank rather than borrowing Pokémon values or inventing numbers.

The same rule applies to:

- battle affinity/type mapping
- technique power / accuracy / PP / category / effects
- growth-curve assignment per entity
- Digivolution conditions
- abilities/passives
- capture semantics

This separation lets the Emerald engine become executable without corrupting
the official Digimon/Appmon source data.
