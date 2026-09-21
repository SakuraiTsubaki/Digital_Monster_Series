#ifndef DIGITAL_MONSTER_EXTENDED_FONTS_H
#define DIGITAL_MONSTER_EXTENDED_FONTS_H

#define DM_EXT_GLYPH_BASE 0x0200
#define DM_EXT_GLYPH_COUNT 642
#define DM_EXT_GLYPH_LAST 0x0481
#define DM_EXT_GLYPH_INDEX(glyphId) ((glyphId) - DM_EXT_GLYPH_BASE)

extern const u16 gDigitalMonsterFontNormalJapaneseGlyphs[];
extern const u16 gDigitalMonsterFontSmallJapaneseGlyphs[];
extern const u16 gDigitalMonsterFontShortJapaneseGlyphs[];

#endif // DIGITAL_MONSTER_EXTENDED_FONTS_H
