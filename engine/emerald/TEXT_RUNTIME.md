# Digital Monster Japanese text runtime

The pinned Emerald engine already includes Japanese hiragana/katakana fonts and
renders glyph IDs through `u16`, but the source charmap remains primarily a
single-byte table. The current Digital Monster official Japanese names require
845 unique characters. 642 are not directly represented by that charmap; 600
of those are Han characters.

## Encoding plan

Existing one-byte Japanese characters remain unchanged.

Digital Monster-only extended characters are assigned IDs beginning at
`0x0200`. A new extended control code uses:

`FC 1D <low byte> <high byte>`

The generated charmap fragment and glyph-ID map are in `generated/`.

## Name storage

Do **not** increase Pokémon nickname storage just to fit official species
names. Nicknames are save data; official display names are ROM data and have
different requirements.

The project therefore keeps nickname/save compatibility separate and stores
the complete Japanese species and technique names in pointer-backed tables:
`digital-monster-display-names.h`.

This also avoids truncating long official names such as mode/X-antibody
variants.

## Remaining work

The renderer hook is prepared, but the 642 extended glyph images still need to
be provided for the Japanese normal/small/short fonts and the relevant UI name
lookup sites must be switched to the pointer-backed display-name tables before
the Japanese runtime profile is considered build-ready.
