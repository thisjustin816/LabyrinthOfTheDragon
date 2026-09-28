# Ideas for 2.0

Nothing here is decided. This is a place to write things down so they aren't lost. The notes under each idea record what the code already has that bears on it.

## Music and updated sound effects

- Music
- Updated sound effects

Notes from the code:

- `src/sound.c` drives channels 1, 2, and 4 only (`nr1x`, `nr2x`, `nr4x`). Nothing touches the wave channel, and there is no music player. Music probably means adopting a driver such as hUGEDriver, or reworking the register-timer scheme, and deciding how effects and music share channels.
- `sfx_test` is a leftover that `main.c` still plays.
- Music will need ROM bank space. `tools/emu/audit/banks.py` reports what is left.
- The 1.1 changelog reuses existing sounds for 19 abilities. Those are candidates for sounds of their own.

## New Game+

- Everyone, heroes and monsters, moves up a tier.
- No starting over from floor 1.
- A second crown on the file.

Notes from the code:

- Power tiers are `C_TIER`, `B_TIER`, `A_TIER`, and `S_TIER` (`stats.h`). S is the top, so anything already at S needs a rule.
- A death currently wakes the hero on floor 1, and the stairs off floor 1 are one way. Skipping floor 1 means changing both the death path and how a new run picks its floor.
- The first crown is one tile between the class sprite and the name (`main_menu.c`). A second needs another tile, and the name-entry art box is already tight (`name_entry.c`).
- A cleared game is `FLAG_GAME_COMPLETE` on the `FLAGS_GAME` page. That page's other bits are unused, so a clear count could live there.
- Changing the `SaveGame` or `Player` layout needs a `SAVE_VERSION` bump, which invalidates existing saves.

## Save and quit

- Replace the save point with save and quit, so a run is more like a roguelike and a save can't be reloaded.

Notes from the code:

- Saving is a SAVE command in the menu, and QUIT is a separate command. Three slots of 512 bytes each live in SRAM.
- A save is a snapshot of the current floor only (`save.h`).
- A slot that is erased on load (and on death) can reuse the file screen's erase path.
- Decide what a death does to the slot, and whether Game Over still returns to floor 1.

## Loose ends found while looking

- `CLASS_TEST` is a debug class with placeholder abilities ("You try a thing."). It could be removed.
- `BUFF_UNUSED_0` to `BUFF_UNUSED_2` are free status effect slots.
- Floor 1 and floor 2 have alternate layouts in the data (`floor_one_v2`, `floor_two_v2`), and floor 2's original layout has an unused sign.
