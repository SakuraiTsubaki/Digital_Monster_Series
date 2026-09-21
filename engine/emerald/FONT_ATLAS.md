# Extended Japanese atlas layout

Pinned engine font formats were verified from `tools/gbagfx/font.c`.

| Font | Stock PNG | Glyph | Format | Stock glyphs | Extended PNG |
|---|---:|---:|---|---:|---:|
| normal | 128×512 | 8×16 | .hwjpnfont | 512 | 128×656 |
| small | 128×512 | 8×16 | .hwjpnfont | 512 | 128×656 |
| short | 256×512 | 16×16 | .fwjpnfont | 512 | 256×656 |

The Digital Monster text corpus needs 642 additional characters. The converter
requires a glyph count divisible by 16, so each extended atlas reserves 656
slots (41 rows × 16), leaving 14 padded unused cells.

Extended glyph IDs remain `0x0200..0x0481`. Their atlas index is
`glyphId - 0x0200`.

The generator creates blank indexed-PNG templates and a deterministic placement
manifest only. **Blank templates are not game-ready glyph artwork.** This keeps
the repository from silently inventing Japanese glyph shapes. A verified source
font/glyph extraction still has to populate those cells before the extended
font runtime is activated.
