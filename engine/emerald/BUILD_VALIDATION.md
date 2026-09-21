# Emerald integration build gate

The project CI checks out the exact pinned `pokeemerald-expansion` commit,
applies the Digital Monster integration using exact checked replacements,
syncs all generated engine files, validates ID/storage invariants, and builds
with:

`make DIGITAL_MONSTER_SERIES=1`

The ROM binary is used only for build/size/hash validation inside the CI job
and is deleted instead of being published as an artifact.

Japanese extended-glyph rendering remains a separate gate: the 642 additional
glyph IDs are mapped, but their final normal/small/short atlas assets are not
yet activated by this build profile.
