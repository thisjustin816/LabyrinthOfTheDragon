// Bank 30, not 2: this file only talks to map.c through four entry points,
// which are BANKED; everything else here is static or only called from
// inside this file. sound.c lives in bank 30 too, which makes the
// play_sound() calls below intra-bank.
#pragma bank 30

#include <stdio.h>

#include "item.h"
#include "map.h"
#include "player.h"
#include "sound.h"

#define MAP_MENU_X 0x00
#define MAP_MENU_Y 0x0E

#define CURSOR_TILE_ID 0x8Au
#define CURSOR_SPRITE_ID 16

// VRAM bank 1, plus the palette slot show_map_menu() loads the cursor's colors
// into. Spelled with the constant rather than the literal 0b00001100 so
// CURSOR_ATTR always names the same slot TORCH_GAUGE_PALETTE does, even if
// that value changes.
#define CURSOR_ATTR (0b00001000 | TORCH_GAUGE_PALETTE)

// The option box at the bottom of the art has three free rows above its
// border. The first two carry the four options as a 2x2 grid and the third
// carries transient messages. The art bakes "RETURN" into the second option
// row, so whichever label lands there is padded wide enough to clear it. Every
// label is drawn at runtime as the art's list-marker glyph followed by the
// text; the 16x16 hand cursor sprite sits two tiles to the left of the marker.
//
// The menu tilemap is drawn at window row MAP_MENU_Y, so tilemap row N sits at
// window row MAP_MENU_Y + N, and a label on tilemap row N wants its hand at
// sprite y (N + 2) * 8.
#define OPTION_ROW_1 (MAP_MENU_Y + 0x0E)
#define OPTION_ROW_2 (MAP_MENU_Y + 0x0F)
#define MESSAGE_ROW (MAP_MENU_Y + 0x10)

#define RETURN_LABEL_COL 4
#define ITEMS_LABEL_COL 13
#define SAVE_LABEL_COL 4
#define QUIT_LABEL_COL 13

#define CURSOR_X_LEFT 14
#define CURSOR_X_RIGHT 86
#define CURSOR_Y_ROW_1 ((0x0E + 2) * 8)
#define CURSOR_Y_ROW_2 ((0x0F + 2) * 8)

// Per-option icons, chosen from what the game's own art already means rather
// than one pictogram repeated in front of every option.
//
// QUIT and SAVE are unmodified, pre-existing font glyphs, not new art:
//   - 0x1D (door + outward arrow) is pixel-identical to the live FLEE icon in
//     the battle menu. The static tilemap bakes this same tile in front of
//     "RETURN" on the second option row, one column before the word, but
//     "walking out the door" reads as leaving the game rather than as backing
//     out of a menu, so it is drawn on QUIT here instead.
//   - 0x1C (a disk) is pixel-identical to an unused tile drawn next to a baked
//     but never-wired "SAVE" label elsewhere in the battle tileset.
// RETURN and ITEMS have no icon anywhere in the game's art (checked against
// every tile in every asset sheet, rotations and mirrors included), so these
// two are new, drawn to match the door and disk's 4-tone weight rather than
// the thinner 2-tone style text glyphs use:
//   - 0x1F is a filled left arrow (font cell was an unreferenced, unidentified
//     glyph; safe to redraw, verified unused by any tilemap or string).
//   - 0x7C is a flask, traced from the confirmed live ITEM icon in the battle
//     menu (same shape, ported to font scale).
#define ICON_RETURN "\x1f"
#define ICON_SAVE "\x1c"
#define ICON_QUIT "\x1d"
#define ICON_ITEMS "\x7c"

// Cycling arrows for the item picker. The font had no usable pair: '>' is the
// sparkle that also serves as the MP icon, and '<' was a stubby arrowhead that
// reads as a diamond at this size. '<' is redrawn as a clean triangle and its
// mirror goes in cell 0x0E, which nothing referenced.
#define ARROW_LEFT '<'
#define ARROW_RIGHT '\x0e'

#define MESSAGE_COL 3
#define MESSAGE_LEN 16

#define NAME_X 1
#define NAME_Y 0xF
#define CLASS_X 0xB
#define LEVEL_X 0x11

#define draw_number_at(n, x, y) do { \
  sprintf(buf, "%u", (n)); \
  core.draw_text(VRAM_WINDOW_XY((x), (y)), buf, 3); \
  } while(0)

MapMenu map_menu;

// The hand cursor borrows TORCH_GAUGE_PALETTE while the menu is up, since the
// menu hides every map sprite and all eight sprite palettes are otherwise
// spoken for (hero, three flame colors, torch gauge, key HUD, two NPCs).
// These are the colors the battle menu's identical hand uses (palette 7 of
// data_battle_sprite_colors).
static const palette_color_t cursor_palette[] = {
  RGB_WHITE,
  RGB_BLACK,
  RGB_DARKGRAY,
  RGB_WHITE,
};

const palette_color_t main_menu_palette[] = {
  RGB_WHITE,
  RGB8(101, 128, 186),
  RGB8(3, 37, 135),
  RGB8(22, 6, 4),
};

static const Tilemap map_menu_tilemap = { 20, 18, BANK_1, tilemap_map_menu };

static void update_cursor(void) {
  uint8_t sx = CURSOR_X_LEFT;
  uint8_t sy = CURSOR_Y_ROW_1;

  switch (map_menu.cursor) {
  case MAP_MENU_CURSOR_ITEMS:
    sx = CURSOR_X_RIGHT;
    break;
  case MAP_MENU_CURSOR_SAVE:
    sy = CURSOR_Y_ROW_2;
    break;
  case MAP_MENU_CURSOR_QUIT:
    sx = CURSOR_X_RIGHT;
    sy = CURSOR_Y_ROW_2;
    break;
  default:
    break;
  }

  move_sprite(CURSOR_SPRITE_ID + 0, sx, sy);
  move_sprite(CURSOR_SPRITE_ID + 1, sx + 8, sy);
  move_sprite(CURSOR_SPRITE_ID + 2, sx, sy + 8);
  move_sprite(CURSOR_SPRITE_ID + 3, sx + 8, sy + 8);
}

static void hide_cursor(void) {
  move_sprite(CURSOR_SPRITE_ID + 0, 0, 0);
  move_sprite(CURSOR_SPRITE_ID + 1, 0, 0);
  move_sprite(CURSOR_SPRITE_ID + 2, 0, 0);
  move_sprite(CURSOR_SPRITE_ID + 3, 0, 0);
}

/**
 * Writes a transient message into the blank row below the menu options.
 * @param msg Message to show, or NULL to clear the row.
 */
static void set_menu_message(const char *msg) {
  core.draw_text(
    VRAM_WINDOW_XY(MESSAGE_COL, MESSAGE_ROW), msg ? msg : "", MESSAGE_LEN);
}

void update_map_menu_hp_sp(void) BANKED {
  core.print_fraction(VRAM_WINDOW_XY(0x6, 0x14), player.hp, player.max_hp);
  core.print_fraction(VRAM_WINDOW_XY(0x6, 0x15), player.sp, player.max_sp);
}

static void update_map_menu_stats(void) {
  char buf[16];

  // Name (drawn directly: a typed name may contain '%')
  core.draw_text(VRAM_WINDOW_XY(NAME_X, NAME_Y), player.name, 8);

  // Class
  switch (player.player_class) {
  case CLASS_DRUID:
    core.draw_text(VRAM_WINDOW_XY(CLASS_X, NAME_Y), str_misc_druid_short, 4);
    break;
  case CLASS_FIGHTER:
    core.draw_text(VRAM_WINDOW_XY(CLASS_X, NAME_Y), str_misc_fighter_short, 4);
    break;
  case CLASS_MONK:
    core.draw_text(VRAM_WINDOW_XY(CLASS_X, NAME_Y), str_misc_monk_short, 4);
    break;
  case CLASS_SORCERER:
    core.draw_text(VRAM_WINDOW_XY(CLASS_X, NAME_Y), str_misc_sorcerer_short, 4);
    break;
  default:
    core.draw_text(VRAM_WINDOW_XY(CLASS_X, NAME_Y), "TST", 4);
  }

  // Level
  sprintf(buf, "%u", player.level);
  core.draw_text(VRAM_WINDOW_XY(LEVEL_X, NAME_Y), buf, 2);

  // EXP / Next Level. The field stops at 11 characters because that is the
  // widest it can ever be ("65118/65118", the level 99 row of exp_by_level)
  // and because draw_text pads to its length: at 12 it would blank the F of
  // the FLR label baked into the next cell.
  sprintf(buf, "%u/%u", player.exp, player.next_level_exp);
  core.draw_text(VRAM_WINDOW_XY(0x4, 0x12), buf, 11);

  // SP/MP Label
  sprintf(buf, is_magic_class() ? "MP" : "SP");
  core.draw_text(VRAM_WINDOW_XY(0x2, 0x15), buf, 2);

  // HP & MP
  update_map_menu_hp_sp();

  // ATK, DEF, MATK, MDEF, AGL
  draw_number_at(player.atk_base, 0x6, 0x17);
  draw_number_at(player.def_base, 0x10, 0x17);
  draw_number_at(player.matk_base, 0x6, 0x18);
  draw_number_at(player.mdef_base, 0x10, 0x18);
  draw_number_at(player.agl_base, 0x10, 0x19);
}

/**
 * Draws the four option labels. SAVE overdraws the art's own marker +
 * "RETURN" on its row; the padding clears the leftover letters.
 */
static void draw_menu_options(void) {
  // Padded out to where ITEMS begins rather than to the end of the word:
  // backing out of the quit prompt redraws only these two labels, and "QUIT
  // THE GAME?" runs well past RETURN's own length, so padding tightly would
  // leave its trailing letters showing in the gap. The bottom row needs no
  // such care, because YES / NO occupy exactly the cells SAVE / QUIT redraw.
  core.draw_text(
    VRAM_WINDOW_XY(RETURN_LABEL_COL - 1, OPTION_ROW_1), ICON_RETURN "RETURN",
    ITEMS_LABEL_COL - RETURN_LABEL_COL);
  core.draw_text(
    VRAM_WINDOW_XY(ITEMS_LABEL_COL - 1, OPTION_ROW_1), ICON_ITEMS "ITEMS", 6);
  core.draw_text(
    VRAM_WINDOW_XY(SAVE_LABEL_COL - 1, OPTION_ROW_2), ICON_SAVE "SAVE", 7);
  core.draw_text(
    VRAM_WINDOW_XY(QUIT_LABEL_COL - 1, OPTION_ROW_2), ICON_QUIT "QUIT", 5);
  set_menu_message(NULL);
}

/**
 * Turns the option rows into the quit confirmation: the question replaces the
 * top row and YES / NO take the bottom one, in the same two columns the hand
 * already points at. The hand cannot move to the message row (it is 16px tall
 * and that row is the last one on screen), so the answer has to live on a row
 * the hand can reach.
 *
 * The two answers reuse the icons the options they replace already carry,
 * which is also what they mean here: the door with the outward arrow is the
 * QUIT icon and leaving is what YES does, and the back arrow is the RETURN
 * icon and backing out is what NO does. The font has no check or cross to
 * draw instead -- its only candidates are the letter X and a plus sign, both
 * of which read as text next to real icons.
 */
static void draw_quit_prompt(void) {
  core.draw_text(
    VRAM_WINDOW_XY(RETURN_LABEL_COL - 1, OPTION_ROW_1), "QUIT THE GAME?", 15);
  core.draw_text(
    VRAM_WINDOW_XY(SAVE_LABEL_COL - 1, OPTION_ROW_2), ICON_QUIT "YES", 7);
  core.draw_text(
    VRAM_WINDOW_XY(QUIT_LABEL_COL - 1, OPTION_ROW_2), ICON_RETURN "NO", 5);
  set_menu_message(NULL);
}

void init_map_menu(void) BANKED {
  core.draw_tilemap(map_menu_tilemap, VRAM_WINDOW_XY(MAP_MENU_X, MAP_MENU_Y));
  map_menu.cursor = MAP_MENU_CURSOR_RETURN;

  draw_menu_options();

  set_sprite_tile(CURSOR_SPRITE_ID + 0, CURSOR_TILE_ID + 0u);
  set_sprite_tile(CURSOR_SPRITE_ID + 1, CURSOR_TILE_ID + 1u);
  set_sprite_tile(CURSOR_SPRITE_ID + 2, CURSOR_TILE_ID + 2u);
  set_sprite_tile(CURSOR_SPRITE_ID + 3, CURSOR_TILE_ID + 3u);

  set_sprite_prop(CURSOR_SPRITE_ID + 0, CURSOR_ATTR);
  set_sprite_prop(CURSOR_SPRITE_ID + 1, CURSOR_ATTR);
  set_sprite_prop(CURSOR_SPRITE_ID + 2, CURSOR_ATTR);
  set_sprite_prop(CURSOR_SPRITE_ID + 3, CURSOR_ATTR);

  hide_cursor();

  update_map_menu_stats();
}

void show_map_menu(void) BANKED {
  map_state = MAP_STATE_MENU;
  map_menu.state = MAP_MENU_OPEN;
  map_menu.cursor = MAP_MENU_CURSOR_RETURN;
  set_menu_message(NULL);

  LCDC_REG |= 0b00001000;
  move_bkg(0, 14 * 8);

  core.load_bg_palette(main_menu_palette, 7, 1);
  core.load_sprite_palette(cursor_palette, TORCH_GAUGE_PALETTE, 1);
  clear_map_sprites();
  update_cursor();

  play_sound(sfx_next_round);
}

static void hide_map_menu(void) {
  map_menu.state = MAP_MENU_CLOSED;
  reload_textbox_palette();
  reload_torch_gauge_palette();
  LCDC_REG &= 0b11110111;
  move_bkg(map_scroll_x, map_scroll_y);
  hide_cursor();
  play_sound(sfx_next_round);
}

// ---------------------------------------------------------------------------
// Field items (issue #70)
//
// Only the three items that change HP or SP directly work outside a battle.
// The buffs and the remedy live in encounter.player_status_effects, which
// reset_encounter() wipes when a fight starts, so drinking one in a corridor
// would do nothing; they are left out of the list rather than offered and
// silently wasted.
//
// The picker reuses the message row instead of opening a submenu, so no new
// menu art is needed: "< Potion x3 >" with LEFT / RIGHT to cycle.
// ---------------------------------------------------------------------------

static const ItemId field_items[] = { ITEM_POTION, ITEM_ETHER, ITEM_ELIXIR };
#define FIELD_ITEM_COUNT ((uint8_t)(sizeof(field_items) / sizeof(field_items[0])))

static uint8_t field_item;

static bool field_item_usable(ItemId id) {
  if (inventory[id].quantity == 0)
    return false;
  switch (id) {
  case ITEM_POTION:
    return player.hp < player.max_hp;
  case ITEM_ETHER:
    return player.sp < player.max_sp;
  case ITEM_ELIXIR:
    return player.hp < player.max_hp || player.sp < player.max_sp;
  default:
    return false;
  }
}

/**
 * @return How many field items are worth drinking right now.
 */
static uint8_t usable_field_items(void) {
  uint8_t n = 0;
  for (uint8_t k = 0; k < FIELD_ITEM_COUNT; k++)
    if (field_item_usable(field_items[k]))
      n++;
  return n;
}

/**
 * @return `true` if the player is carrying any field item at all, usable or
 *   not. Distinguishes "you have none" from "the bars they fill are full".
 */
static bool holding_field_items(void) {
  for (uint8_t k = 0; k < FIELD_ITEM_COUNT; k++)
    if (inventory[field_items[k]].quantity)
      return true;
  return false;
}

/**
 * @return The next usable entry starting at `from` and stepping by `step`, or
 *   FIELD_ITEM_COUNT when the player has nothing worth drinking.
 */
static uint8_t next_field_item(uint8_t from, int8_t step) {
  uint8_t k = from;
  for (uint8_t n = 0; n < FIELD_ITEM_COUNT; n++) {
    k = (uint8_t)((k + step + FIELD_ITEM_COUNT) % FIELD_ITEM_COUNT);
    if (field_item_usable(field_items[k]))
      return k;
  }
  return field_item_usable(field_items[from]) ? from : FIELD_ITEM_COUNT;
}

/**
 * Draws the selected item into the message row.
 *
 * The count is written a digit at a time rather than with sprintf: SDCC passes
 * a value cast to char or uint8_t as a single byte, so a "%u" fed one reads
 * the neighboring argument as its high byte.
 */
static void draw_field_item(void) {
  char buf[MESSAGE_LEN + 1];
  const Item *item = inventory + field_items[field_item];
  uint8_t n = item->quantity;
  uint8_t i = 0;
  // With one usable item there is nowhere to cycle to, so the arrows go blank
  // rather than inviting a press that does nothing. Spaces, not omission, so
  // the name stays in the same column either way.
  const bool cycles = usable_field_items() > 1;

  buf[i++] = cycles ? ARROW_LEFT : ' ';
  buf[i++] = ' ';
  // Stop early enough for the seven bytes the tail always needs: ' ', 'x', up
  // to two digits, ' ', the right arrow and the NUL.
  for (const char *p = item->name; *p && i < MESSAGE_LEN - 6; p++)
    buf[i++] = *p;
  buf[i++] = ' ';
  buf[i++] = 'x';
  if (n > 99)
    n = 99;
  if (n >= 10)
    buf[i++] = '0' + n / 10;
  buf[i++] = '0' + n % 10;
  buf[i++] = ' ';
  buf[i++] = cycles ? ARROW_RIGHT : ' ';
  buf[i] = 0;

  set_menu_message(buf);
}

/**
 * Drinks the selected item. Mirrors the battle formulas in item.c.
 */
static void use_field_item(void) {
  const ItemId id = field_items[field_item];
  Item *item = inventory + id;

  if (id == ITEM_ELIXIR) {
    player.hp = player.max_hp;
    player.sp = player.max_sp;
  } else if (id == ITEM_POTION) {
    uint16_t h = POTION_HEAL_FACTOR * player.max_hp;
    h >>= 4;
    player.hp = (player.hp + h > player.max_hp) ? player.max_hp : player.hp + h;
  } else {
    uint16_t h = ETHER_HEAL_FACTOR * player.max_sp;
    h >>= 4;
    player.sp = (player.sp + h > player.max_sp) ? player.max_sp : player.sp + h;
  }

  item->quantity--;
  player_hp_and_sp_updated = true;
  update_map_menu_hp_sp();
  play_sound(sfx_heal);

  // Stay on the same item while it is still worth drinking; topping the bar
  // off moves on, and running out of everything closes the picker.
  if (!field_item_usable(field_items[field_item]))
    field_item = next_field_item(field_item, 1);
  if (field_item >= FIELD_ITEM_COUNT) {
    map_menu.state = MAP_MENU_OPEN;
    set_menu_message(NULL);
    update_cursor();
    return;
  }
  draw_field_item();
}

/**
 * Handles input while the item picker is open.
 */
static void update_field_items(void) {
  if (was_pressed(J_B) || was_pressed(J_START)) {
    map_menu.state = MAP_MENU_OPEN;
    set_menu_message(NULL);
    update_cursor();
    play_sound(sfx_menu_move);
    return;
  }

  if (was_pressed(J_LEFT) || was_pressed(J_RIGHT)) {
    const uint8_t next =
      next_field_item(field_item, was_pressed(J_LEFT) ? -1 : 1);
    if (next < FIELD_ITEM_COUNT && next != field_item) {
      field_item = next;
      draw_field_item();
      play_sound(sfx_menu_move);
    }
    return;
  }

  if (was_pressed(J_A))
    use_field_item();
}

/**
 * Moves the cursor for a D-pad press. The four options are a 2x2 grid:
 *
 *   RETURN   ITEMS
 *   SAVE     QUIT
 *
 * UP and DOWN swap rows, LEFT and RIGHT swap columns, both keeping the other
 * axis where it is.
 */
static void move_menu_cursor(void) {
  // Column 0 is RETURN / SAVE, column 1 is ITEMS / QUIT.
  const bool right_column = map_menu.cursor == MAP_MENU_CURSOR_ITEMS ||
    map_menu.cursor == MAP_MENU_CURSOR_QUIT;
  const bool bottom_row = map_menu.cursor == MAP_MENU_CURSOR_SAVE ||
    map_menu.cursor == MAP_MENU_CURSOR_QUIT;

  bool want_right = right_column;
  bool want_bottom = bottom_row;

  if (was_pressed(J_UP) || was_pressed(J_DOWN))
    want_bottom = !bottom_row;
  else if (was_pressed(J_LEFT) || was_pressed(J_RIGHT))
    want_right = !right_column;

  if (want_bottom)
    map_menu.cursor = want_right ? MAP_MENU_CURSOR_QUIT : MAP_MENU_CURSOR_SAVE;
  else
    map_menu.cursor = want_right ? MAP_MENU_CURSOR_ITEMS : MAP_MENU_CURSOR_RETURN;
}

/**
 * Withdraws the quit confirmation and puts the options back.
 */
static void cancel_quit_prompt(void) {
  map_menu.state = MAP_MENU_OPEN;
  map_menu.cursor = MAP_MENU_CURSOR_QUIT;
  draw_menu_options();
  update_cursor();
  play_sound(sfx_menu_move);
}

/**
 * Runs the quit confirmation. YES sits in the left column and NO in the right,
 * so the hand moves between them with LEFT and RIGHT exactly as it does
 * between SAVE and QUIT. UP, DOWN and B all back out.
 */
static void update_quit_prompt(void) {
  if (was_pressed(J_B) || was_pressed(J_START) ||
      was_pressed(J_UP) || was_pressed(J_DOWN)) {
    cancel_quit_prompt();
    return;
  }

  if (joypad_pressed & (J_LEFT | J_RIGHT)) {
    map_menu.cursor = map_menu.cursor == MAP_MENU_CURSOR_SAVE
      ? MAP_MENU_CURSOR_QUIT
      : MAP_MENU_CURSOR_SAVE;
    update_cursor();
    play_sound(sfx_menu_move);
    return;
  }

  if (!was_pressed(J_A))
    return;

  if (map_menu.cursor == MAP_MENU_CURSOR_SAVE) {
    map_menu.state = MAP_MENU_QUIT;
    play_sound(sfx_next_round);
  } else {
    cancel_quit_prompt();
  }
}

void update_map_menu(void) BANKED {
  if (map_menu.state == MAP_MENU_CLOSED || map_menu.state == MAP_MENU_QUIT)
    return;

  // The picker takes every button while it is open, including B and START,
  // which back out to the options rather than closing the whole menu.
  if (map_menu.state == MAP_MENU_ITEMS) {
    update_field_items();
    return;
  }

  // The quit confirmation is a two-option picker on the bottom row, so it owns
  // the D-pad and both buttons while it is up rather than falling through to
  // the 2x2 grid below.
  if (map_menu.state == MAP_MENU_CONFIRM_QUIT) {
    update_quit_prompt();
    return;
  }

  if (was_pressed(J_START) || was_pressed(J_B)) {
    play_sound(sfx_menu_move);
    hide_map_menu();
    return;
  }

  if (joypad_pressed & (J_LEFT | J_RIGHT | J_UP | J_DOWN)) {
    // A message answers the option it came from, so moving off that option
    // retires it. Left up, it also collides with the hand: the sprite is 16px
    // tall, so on the bottom row it reaches down into the message line.
    set_menu_message(NULL);
    move_menu_cursor();
    update_cursor();
    play_sound(sfx_menu_move);
    return;
  }

  if (!was_pressed(J_A))
    return;

  switch (map_menu.cursor) {
  case MAP_MENU_CURSOR_RETURN:
    play_sound(sfx_menu_move);
    hide_map_menu();
    break;
  case MAP_MENU_CURSOR_ITEMS:
    // Issue #70: potions, ethers and elixirs can be drunk between fights, so
    // the player is not forced into a battle on low health.
    field_item = next_field_item(FIELD_ITEM_COUNT - 1, 1);
    if (field_item >= FIELD_ITEM_COUNT) {
      // Holding a full stack of ethers on a full SP bar is the common case
      // here, and "NOTHING TO USE" reads as a bug when the items are right
      // there in the inventory. Say which of the two it is.
      set_menu_message(
        holding_field_items() ? "NONE WOULD HELP" : "NO ITEMS TO USE");
      play_sound(sfx_error);
      break;
    }
    map_menu.state = MAP_MENU_ITEMS;
    draw_field_item();
    play_sound(sfx_menu_move);
    break;
  case MAP_MENU_CURSOR_QUIT:
    // Quitting drops the game in progress, so it asks first. The cursor
    // stays where it is, which is NO -- the answer that costs nothing.
    map_menu.state = MAP_MENU_CONFIRM_QUIT;
    draw_quit_prompt();
    play_sound(sfx_menu_move);
    break;
  }
}
