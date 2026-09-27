#ifndef _SAVE_H
#define _SAVE_H

#include "core.h"
#include "item.h"
#include "map.h"
#include "player.h"

/**
 * Number of save slots held in cartridge SRAM.
 */
#define SAVE_SLOT_COUNT 3

/**
 * Bytes reserved for each slot. Slots are placed at fixed strides so that
 * growing `SaveGame` never silently shifts the slots that follow it. A
 * compile time assertion in `save.c` enforces `sizeof(SaveGame) <= this`.
 */
#define SAVE_SLOT_SIZE 512

/**
 * Base address of cartridge SRAM (all slots live in SRAM bank 0).
 */
#define SAVE_SRAM_BASE 0xA000u

/**
 * Bytes of floor script state carried in a save. The byte assignments are the
 * `ScriptStateSlot` enum in `save.c`.
 */
#define SCRIPT_STATE_LEN 12

/**
 * Identifies an initialized slot. Bumping `SAVE_VERSION` invalidates every
 * existing save, which is the correct thing to do whenever the layout of
 * `SaveGame` (or of `Player`) changes.
 */
#define SAVE_MAGIC 0x4C44u
#define SAVE_VERSION 4

/**
 * A complete snapshot of a game in progress.
 *
 * Only one floor's worth of object state exists at a time: `set_active_floor`
 * calls `reset_map_objects`, which rebuilds every chest/lever/door/sconce flag
 * from the floor's ROM defaults. So a save is a snapshot of the *current*
 * floor rather than of all eight.
 */
typedef struct SaveGame {
  /**
   * `SAVE_MAGIC` when the slot holds a game.
   */
  uint16_t magic;
  /**
   * `SAVE_VERSION` the slot was written with.
   */
  uint8_t version;
  /**
   * 8-bit sum of every byte of this struct, computed with this field zeroed.
   */
  uint8_t checksum;

  /**
   * The player. Stored whole; `Player` contains no pointers, so a byte copy
   * round-trips safely.
   */
  Player player;
  /**
   * Inventory quantities. `inventory[]` is statically initialized with ids and
   * name pointers and is indexed by `ItemId`, so only counts need saving.
   */
  uint8_t inventory[INVENTORY_LEN];
  /**
   * The global flag pages (`flags[]`). Page FLAGS_GAME holds the game-wide
   * bits such as FLAG_GAME_COMPLETE; the rest are unused.
   */
  uint8_t flag_pages[32];

  /**
   * Elapsed play time in seconds, shown as the clock on the save select screen.
   */
  uint16_t play_seconds;

  /**
   * Index into `floor_table`, *not* `Floor::id`.
   */
  uint8_t floor_index;
  /**
   * `MapId` of the active map within the floor.
   */
  uint8_t map_id;
  /**
   * Map scroll origin. Hero position is this plus `HERO_[XY]_OFFSET`.
   */
  int8_t map_x;
  int8_t map_y;
  /**
   * Direction the hero faces.
   */
  uint8_t hero_direction;

  /**
   * Per-floor object state.
   */
  uint8_t flags_chest_open;
  uint8_t flags_chest_locked;
  uint8_t flags_lever_on;
  uint8_t flags_lever_stuck;
  uint16_t flags_door_locked;
  uint8_t flags_sconce_lit;
  uint8_t npc_visible;
  uint8_t sconce_colors[8];

  /**
   * Floor script globals that hold puzzle progress (floor 4's solved-pair
   * count, floor 5's lever flame colors, floor 7's lever state machine and
   * floor switches, floor 8's mini-boss bitmask, ...). Every floor's `on_init`
   * resets its own, so without these a reload leaves the object flags advanced
   * but the script behind them at zero: on floor 4 that would be a soft
   * lock, and on floor 5 the boss door puzzle could no longer be solved from
   * what the flames showed. See `capture_script_state` in `save.c`.
   */
  uint8_t script_state[SCRIPT_STATE_LEN];
  /**
   * The tile/palette override table. Floors 6-8 draw puzzle state (floor 7's
   * "eyes", floor 6's portal highlights) with `set_tile_at`, which lives here
   * and is wiped by `reset_map_objects`.
   */
  TileOverrideHashEntry overrides[TILE_HASHTABLE_SIZE];
} SaveGame;

/**
 * Slot the current game is bound to. Set when a game is started or loaded and
 * used as the destination for in-game saves.
 */
extern uint8_t active_save_slot;

/**
 * @return `true` if the slot holds a valid, current-version game.
 * @param slot Slot to test.
 */
bool save_slot_used(uint8_t slot) BANKED;

/**
 * Opens a slot for reading, for the save select screen. SRAM is memory mapped,
 * so this hands back a pointer into it rather than copying a 446-byte save
 * into scarce work RAM. SRAM is left enabled; the caller must pair every
 * successful call with `save_slot_close()` and must not hold the pointer past
 * that.
 * @param slot Slot to read.
 * @return Pointer to the slot, or `NULL` if it holds no valid game (in which
 *  case SRAM is already closed again).
 */
const SaveGame *save_slot_open(uint8_t slot) BANKED;

/**
 * Closes a slot opened with `save_slot_open()`, disabling SRAM.
 */
void save_slot_close(void) BANKED;

/**
 * Clears the game-wide state a new game must not inherit from the one played
 * before it in the same power-on: the flag pages (FLAG_GAME_COMPLETE among
 * them) and the floor script globals that no floor's `on_init` resets. Called
 * when a new character is created, before its first save is written.
 */
void save_new_game(void) BANKED;

/**
 * Writes the live game state to a slot.
 * @param slot Slot to write.
 * @return `true` on success.
 */
bool save_write(uint8_t slot) BANKED;

/**
 * Restores a slot into the live game state. On success the caller must bring up
 * the map graphics with `init_world_map()` and set `game_state`.
 * @param slot Slot to load.
 * @return `true` on success. The live state is untouched on failure.
 */
bool save_load(uint8_t slot) BANKED;

/**
 * Clears a slot.
 * @param slot Slot to erase.
 */
void save_erase(uint8_t slot) BANKED;

// Implemented in map.c, which owns the statics this needs (`floor_bank`,
// `active_map`, `maps[]`) and the floor callback trampolines.

/**
 * @return Index into `floor_table` of the active floor, or 0 if unknown.
 */
uint8_t map_floor_index(void) BANKED;

/**
 * Copies the map system's state into a save.
 */
void map_capture_state(SaveGame *s) BANKED;

/**
 * Applies a save's map state: loads the floor, restores position and object
 * flags. Must run before `init_world_map()`. Marks a deferred second phase
 * that `map.c` runs right after the floor's `on_init` (see below).
 */
void map_restore_state(const SaveGame *s) NONBANKED;

/**
 * Second phase of a restore: puts the saved tile override table back and
 * repaints the overridden tiles in view. Floor `on_init` callbacks wipe that
 * table (via `set_active_floor`) and reset their puzzle counters, so this can
 * only run after it has. `map.c` calls `save_apply_deferred()` at that point,
 * which reopens the slot and hands it here (and to the script state restore).
 */
void map_apply_deferred_state(const SaveGame *s) BANKED;

/**
 * Reopens `active_save_slot` and applies its deferred state. Called by `map.c`
 * from the `on_init` trampoline; not for general use.
 */
void save_apply_deferred(void) BANKED;

// Implemented in player.c.

/**
 * Rebuilds `class_abilities` / `player_abilities` from the player's class and
 * ability flags. Those arrays hold pointers and so cannot be saved directly.
 */
void player_refresh_abilities(void) BANKED;

#endif
