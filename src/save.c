// Bank 7 has the most headroom; banks 0-2 are nearly full and every entry
// point here is BANKED, so the code can live anywhere.
#pragma bank 7

#include "save.h"

/**
 * Slot the live game is bound to.
 */
uint8_t active_save_slot = 0;

//------------------------------------------------------------------------------
// Floor script state
//------------------------------------------------------------------------------

/**
 * Floor script globals that carry puzzle progress. They are plain WRAM, so they
 * can be read from any bank, but each floor's `on_init` resets its own, which
 * is why `apply_script_state` runs from the `on_init` trampoline rather than
 * with the rest of the restore.
 *
 * floor1's `special_encounter` is deliberately absent: the floor re-arms it in
 * `on_load` on every load (including after death), so leaving it alone matches
 * the game.
 */
extern uint8_t puzzle_count;          // floor4.c: sconce pairs solved
extern FlameColor lever1_flame;       // floor5.c: boss door flame puzzle
extern FlameColor lever2_flame;
extern FlameColor lever3_flame;
extern uint8_t active_portal;         // floor6.c: portal routing
extern uint8_t puzzle_state;          // floor7.c: lever state machine
extern bool switch_lever_1;           // floor7.c: floor switches stepped on
extern bool switch_lever_2;
extern bool switch_door_6;
extern bool switch_door_8;
extern uint8_t mini_bosses_defeated;  // floor8.c
extern uint8_t current_mini_boss;     // floor8.c
extern uint8_t healing_mirrors_used;  // floor8.c
extern bool special_enc_1;            // floor3.c: one-shot goblin ambushes
extern bool special_enc_2;
extern bool special_enc_3;
extern bool special_enc_4;

/**
 * Byte assignments within `SaveGame::script_state`. Add a slot here for any
 * new floor global that represents progress and bump `SAVE_VERSION`.
 */
typedef enum ScriptStateSlot {
  SCRIPT_PUZZLE_COUNT,
  SCRIPT_ACTIVE_PORTAL,
  SCRIPT_PUZZLE_STATE,
  SCRIPT_MINI_BOSSES_DEFEATED,
  SCRIPT_CURRENT_MINI_BOSS,
  SCRIPT_HEALING_MIRRORS_USED,
  SCRIPT_LEVER1_FLAME,
  SCRIPT_LEVER2_FLAME,
  SCRIPT_LEVER3_FLAME,
  /**
   * floor7.c switches, one bit each: switch_lever_1, switch_lever_2,
   * switch_door_6, switch_door_8.
   */
  SCRIPT_FLOOR7_SWITCHES,
  /**
   * floor3.c special_enc_1..4, one bit each.
   */
  SCRIPT_FLOOR3_AMBUSHES,
  SCRIPT_STATE_USED,
} ScriptStateSlot;

/**
 * Compile time assertion that every slot fits in the array.
 */
typedef char script_state_fits[
  (SCRIPT_STATE_USED <= SCRIPT_STATE_LEN) ? 1 : -1];

/**
 * Copies the floor script globals into a save.
 */
static void capture_script_state(SaveGame *s) {
  uint8_t *st = s->script_state;

  for (uint8_t k = 0; k < SCRIPT_STATE_LEN; k++)
    st[k] = 0;

  st[SCRIPT_PUZZLE_COUNT] = puzzle_count;
  st[SCRIPT_ACTIVE_PORTAL] = active_portal;
  st[SCRIPT_PUZZLE_STATE] = puzzle_state;
  st[SCRIPT_MINI_BOSSES_DEFEATED] = mini_bosses_defeated;
  st[SCRIPT_CURRENT_MINI_BOSS] = current_mini_boss;
  st[SCRIPT_HEALING_MIRRORS_USED] = healing_mirrors_used;
  st[SCRIPT_LEVER1_FLAME] = (uint8_t)lever1_flame;
  st[SCRIPT_LEVER2_FLAME] = (uint8_t)lever2_flame;
  st[SCRIPT_LEVER3_FLAME] = (uint8_t)lever3_flame;

  uint8_t bits = 0;
  if (switch_lever_1) bits |= FLAG(0);
  if (switch_lever_2) bits |= FLAG(1);
  if (switch_door_6) bits |= FLAG(2);
  if (switch_door_8) bits |= FLAG(3);
  st[SCRIPT_FLOOR7_SWITCHES] = bits;

  bits = 0;
  if (special_enc_1) bits |= FLAG(0);
  if (special_enc_2) bits |= FLAG(1);
  if (special_enc_3) bits |= FLAG(2);
  if (special_enc_4) bits |= FLAG(3);
  st[SCRIPT_FLOOR3_AMBUSHES] = bits;
}

/**
 * Puts the floor script globals back from a save. Must run after the floor's
 * `on_init`, which resets them.
 */
static void apply_script_state(const SaveGame *s) {
  const uint8_t *st = s->script_state;

  puzzle_count = st[SCRIPT_PUZZLE_COUNT];
  active_portal = st[SCRIPT_ACTIVE_PORTAL];
  puzzle_state = st[SCRIPT_PUZZLE_STATE];
  mini_bosses_defeated = st[SCRIPT_MINI_BOSSES_DEFEATED];
  current_mini_boss = st[SCRIPT_CURRENT_MINI_BOSS];
  lever1_flame = (FlameColor)st[SCRIPT_LEVER1_FLAME];
  lever2_flame = (FlameColor)st[SCRIPT_LEVER2_FLAME];
  lever3_flame = (FlameColor)st[SCRIPT_LEVER3_FLAME];

  uint8_t bits = st[SCRIPT_FLOOR7_SWITCHES];
  switch_lever_1 = (bits & FLAG(0)) != 0;
  switch_lever_2 = (bits & FLAG(1)) != 0;
  switch_door_6 = (bits & FLAG(2)) != 0;
  switch_door_8 = (bits & FLAG(3)) != 0;

  bits = st[SCRIPT_FLOOR3_AMBUSHES];
  special_enc_1 = (bits & FLAG(0)) != 0;
  special_enc_2 = (bits & FLAG(1)) != 0;
  special_enc_3 = (bits & FLAG(2)) != 0;
  special_enc_4 = (bits & FLAG(3)) != 0;
}

void save_new_game(void) BANKED {
  for (uint8_t k = 0; k < 32; k++)
    flags[k] = 0;

  // Every other floor global is reset by its floor's on_load or on_init when
  // the floor loads; the mirrors are the one that persists on purpose across a
  // death, which also keeps them across a new game unless cleared here.
  healing_mirrors_used = 0;
}

//------------------------------------------------------------------------------
// SRAM slots
//------------------------------------------------------------------------------

/**
 * Compile time assertion that a slot is actually big enough to hold a save.
 * If `SaveGame` outgrows `SAVE_SLOT_SIZE` this declares an array of negative
 * length and the build fails here rather than corrupting the next slot.
 */
typedef char save_game_fits_in_slot[
  (sizeof(SaveGame) <= SAVE_SLOT_SIZE) ? 1 : -1];

/**
 * SRAM is memory mapped, so a slot can be addressed directly instead of being
 * copied into work RAM. Requires SRAM to be enabled.
 * @param slot Slot index.
 * @return Pointer to the slot in SRAM.
 */
static SaveGame *sram_slot(uint8_t slot) {
  return (SaveGame *)(SAVE_SRAM_BASE + (uint16_t)slot * (uint16_t)SAVE_SLOT_SIZE);
}

/**
 * Sums every byte of a save with the checksum field treated as zero.
 * @param s Save to sum.
 * @return The 8-bit checksum.
 */
static uint8_t checksum_of(const SaveGame *s) {
  const uint8_t *p = (const uint8_t *)s;
  uint8_t sum = 0;
  for (uint16_t k = 0; k < sizeof(SaveGame); k++, p++)
    sum += *p;
  // Undo the contribution of the stored checksum byte so that the result is
  // independent of whatever is currently sitting in that field.
  return sum - s->checksum;
}

/**
 * Validates a slot. Requires SRAM to be enabled.
 * @param slot Slot to test.
 * @return `true` if the slot holds a valid, current-version save.
 */
static bool slot_is_valid(uint8_t slot) {
  if (slot >= SAVE_SLOT_COUNT)
    return false;

  const SaveGame *s = sram_slot(slot);
  if (s->magic != SAVE_MAGIC || s->version != SAVE_VERSION)
    return false;

  return s->checksum == checksum_of(s);
}

/**
 * Enables SRAM and selects the bank the slots live in.
 *
 * SRAM is deliberately left disabled outside of these calls: a cartridge whose
 * RAM is enabled when power is cut is the classic way to corrupt a save.
 */
static void sram_open(void) {
  ENABLE_RAM;
  SWITCH_RAM(0);
}

static void sram_close(void) {
  DISABLE_RAM;
}

bool save_slot_used(uint8_t slot) BANKED {
  sram_open();
  const bool valid = slot_is_valid(slot);
  sram_close();
  return valid;
}

const SaveGame *save_slot_open(uint8_t slot) BANKED {
  sram_open();
  if (slot_is_valid(slot))
    return sram_slot(slot);

  sram_close();
  return NULL;
}

void save_slot_close(void) BANKED {
  sram_close();
}

bool save_write(uint8_t slot) BANKED {
  if (slot >= SAVE_SLOT_COUNT)
    return false;

  sram_open();

  SaveGame *s = sram_slot(slot);

  s->magic = SAVE_MAGIC;
  s->version = SAVE_VERSION;
  s->checksum = 0;

  s->player = player;

  for (uint8_t k = 0; k < INVENTORY_LEN; k++)
    s->inventory[k] = inventory[k].quantity;

  for (uint8_t k = 0; k < 32; k++)
    s->flag_pages[k] = flags[k];

  s->play_seconds = play_seconds;

  map_capture_state(s);
  capture_script_state(s);

  s->checksum = checksum_of(s);

  const bool ok = slot_is_valid(slot);
  sram_close();

  if (ok)
    active_save_slot = slot;

  return ok;
}

bool save_load(uint8_t slot) BANKED {
  sram_open();

  if (!slot_is_valid(slot)) {
    sram_close();
    return false;
  }

  const SaveGame *s = sram_slot(slot);

  player = s->player;

  for (uint8_t k = 0; k < INVENTORY_LEN; k++)
    inventory[k].quantity = s->inventory[k];

  for (uint8_t k = 0; k < 32; k++)
    flags[k] = s->flag_pages[k];

  play_seconds = s->play_seconds;

  // `player_abilities` holds pointers derived from the class and ability flags,
  // so it has to be rebuilt rather than restored.
  player_refresh_abilities();

  // Floor 8's on_init draws the spent mirrors from this and never resets it, so
  // it has to be in place before the floor loads, not put back with the rest
  // of the script state after on_init. Left to then, on_init would draw the
  // mirrors of whatever game ran before this one.
  healing_mirrors_used = s->script_state[SCRIPT_HEALING_MIRRORS_USED];

  // Loads the floor (which resets object flags to their ROM defaults) and then
  // applies the saved position and flags over the top.
  map_restore_state(s);

  sram_close();

  player_hp_and_sp_updated = true;
  active_save_slot = slot;

  return true;
}

void save_apply_deferred(void) BANKED {
  sram_open();
  if (slot_is_valid(active_save_slot)) {
    const SaveGame *s = sram_slot(active_save_slot);
    apply_script_state(s);
    map_apply_deferred_state(s);
  }
  sram_close();
}

void save_erase(uint8_t slot) BANKED {
  if (slot >= SAVE_SLOT_COUNT)
    return;

  sram_open();

  // Clearing the magic is enough to retire the slot, but wiping it outright
  // keeps stale data from ever being resurrected by a checksum collision.
  uint8_t *p = (uint8_t *)sram_slot(slot);
  for (uint16_t k = 0; k < SAVE_SLOT_SIZE; k++, p++)
    *p = 0;

  sram_close();
}
