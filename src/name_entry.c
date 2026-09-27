// Bank 7 with the rest of the menu screens: banks 0-2 are nearly full.
#pragma bank 7

#include <gb/gb.h>
#include <gb/cgb.h>
#include <stdint.h>

#include "core.h"
#include "encounter.h"
#include "hero_select.h"
#include "item.h"
#include "main_menu.h"
#include "name_entry.h"
#include "player.h"
#include "sound.h"

/**
 * Names are at most six characters: the field the art draws, and the width
 * the save select shows.
 */
#define NAME_MAX 6

// Layout of res/tilemaps/name_entry.tilemap: a six-cell name field on row 2
// from column 7, and five character rows (A-P, Q-Z, a-p, q-z, symbols) each
// starting at column 2. Rows 14-17 are empty backdrop.
#define FIELD_COL 7
#define FIELD_ROW 2
#define GRID_COL 2
#define GRID_ROWS 5

// This grid's symbol row is 12 wide but the art's box is cut for 16, the
// same width as the A-P and a-p rows, so four cells already sit blank after
// the last symbol. END lives there as a real, cursor-selectable grid entry:
// land on it and press A, same as START.
#define END_LABEL_COL 15
#define END_LABEL_LEN 3
#define END_LABEL "END"

// The underscore, drawn in the empty cells of the name field. Not 0x5C, which
// is the small block the pause menu uses as its AGL icon.
#define EMPTY_CHAR 0x5F

// A new game can start on a lower floor, to test it without playing the floors
// before it. SELECT cycles this label, in the empty rows under the grid, from
// START B2 to START B8 and back to blank for floor 1.
#define START_ROW 15
#define START_COL 6
#define START_LEN 8

// BG attributes: font tiles live in VRAM bank 1.
#define ATTR_GRID 0x0F           // palette 7, as the art has it
#define ATTR_GRID_SELECTED 0x0E  // palette 6
#define ATTR_START 0x08          // palette 0, the hint color

static const uint8_t grid_row_y[GRID_ROWS] = { 6, 7, 9, 10, 12 };
// The last entry in the symbol row is the END cell, not a 13th symbol.
static const uint8_t grid_row_len[GRID_ROWS] = { 16, 10, 16, 10, 13 };
static const char symbols[] = "@%&\'()*+,-./";
#define SYMBOL_ROW (GRID_ROWS - 1)
#define END_COL (sizeof(symbols) - 1)

Tilemap name_entry_tilemap = { 20, 18, BANK_1, tilemap_name_entry };

// 0: hints, 1: backdrop (tile 0 in VRAM bank 0, made solid at init).
static const palette_color_t backdrop_palettes[] = {
  RGB_SAVE_NAVY, RGB_SAVE_NAVY, RGB_SAVE_NAVY, RGB_SAVE_HINT,
  RGB_SAVE_NAVY, RGB_SAVE_NAVY, RGB_SAVE_NAVY, RGB_SAVE_NAVY,
};

// 6: the highlighted grid cell (inverted), 7: boxes and text, in the save
// select's selected-slot colors.
static const palette_color_t text_palettes[] = {
  RGB_SAVE_NAVY, RGB_SAVE_BROWN, RGB_SAVE_ORANGE, RGB_SAVE_GOLD,
  RGB_SAVE_NAVY, RGB_SAVE_GOLD, RGB_SAVE_ORANGE, RGB_SAVE_BROWN,
};

/**
 * What a new game started on a lower floor carries, from B2 on: about the level
 * a full first run reaches that floor at, a magic key for each of the floor's
 * key-locked chests, and every item a first run gathers on the floors before
 * it without using any. Those floors hold more key-locked chests than they
 * give keys, so a first run opens each floor's in order until its keys run
 * out.
 */
typedef struct FloorStart {
  uint8_t level;
  uint8_t magic_keys;
  uint8_t items[INVENTORY_LEN];
} FloorStart;

static const FloorStart floor_starts[] = {
  // Level, keys, then the items in ItemId order: Potion, Ether, Remedy,
  // ATK up, DEF up, Elixir, Regen, Haste.
  { 14, 0, {  3, 1, 0, 0, 0, 0, 0, 0 } },  // B2
  { 20, 2, {  6, 1, 1, 0, 0, 0, 0, 0 } },  // B3
  { 30, 2, {  7, 2, 1, 0, 0, 0, 1, 0 } },  // B4
  { 35, 3, {  8, 4, 1, 0, 0, 0, 2, 0 } },  // B5
  { 45, 3, { 11, 7, 2, 0, 0, 1, 2, 0 } },  // B6
  { 48, 0, { 15, 8, 2, 0, 0, 2, 5, 0 } },  // B7
  { 52, 0, { 16, 8, 2, 1, 1, 5, 8, 2 } },  // B8
};

#define LAST_START_FLOOR (sizeof(floor_starts) / sizeof(floor_starts[0]) + 1)

// PLAYER_NAME_LEN rather than NAME_MAX + 1: default_hero_name() fills the whole
// player-name buffer, and only the first NAME_MAX characters are editable here.
static char name[PLAYER_NAME_LEN];
static uint8_t name_len;
static uint8_t row;
static uint8_t col;
// The floor a new game starts on, from 1 to LAST_START_FLOOR.
static uint8_t start_floor;

/**
 * Redraws the name field: the typed characters, then underscores.
 */
static void draw_field(void) {
  uint8_t *vram = VRAM_BACKGROUND_XY(FIELD_COL, FIELD_ROW);
  VBK_REG = VBK_TILES;
  for (uint8_t k = 0; k < NAME_MAX; k++, vram++)
    set_vram_byte(vram, (k < name_len ? name[k] : EMPTY_CHAR) + FONT_OFFSET);
}

/**
 * Shows the floor a new game starts on, or blanks the label for floor 1.
 */
static void draw_start_floor(void) {
  char label[] = "START B0";
  if (start_floor > 1)
    label[START_LEN - 1] = '0' + start_floor;
  else
    label[0] = 0;
  core.draw_text(VRAM_BACKGROUND_XY(START_COL, START_ROW), label, START_LEN);
}

static void set_cell_attr(uint8_t r, uint8_t c, uint8_t attr) {
  VBK_REG = VBK_ATTRIBUTES;
  if (r == SYMBOL_ROW && c == END_COL) {
    // END is three tiles wide, sitting past the real symbols rather than at
    // GRID_COL + c like every other cell.
    for (uint8_t k = 0; k < END_LABEL_LEN; k++)
      set_vram_byte(VRAM_BACKGROUND_XY(END_LABEL_COL + k, grid_row_y[r]), attr);
  } else {
    set_vram_byte(VRAM_BACKGROUND_XY(GRID_COL + c, grid_row_y[r]), attr);
  }
  VBK_REG = VBK_TILES;
}

static void move_grid_cursor(uint8_t r, uint8_t c) {
  set_cell_attr(row, col, ATTR_GRID);
  row = r;
  col = c;
  set_cell_attr(row, col, ATTR_GRID_SELECTED);
}

/**
 * @return The character under the grid cursor.
 */
static char grid_char(void) {
  switch (row) {
  case 0:
    return 'A' + col;
  case 1:
    return 'Q' + col;
  case 2:
    return 'a' + col;
  case 3:
    return 'q' + col;
  default:
    return symbols[col];
  }
}

/**
 * Hands the typed name to start_game(); an empty field keeps the class
 * default. Shared by START and by pressing A on the grid's END cell.
 */
static void confirm_name(void) {
  for (uint8_t k = 0; k < PLAYER_NAME_LEN; k++)
    new_hero_name[k] = k < name_len ? name[k] : 0;
  play_sound(sfx_hero_selected);
  start_game();
}

static void init_name_entry_impl(void) {
  DISPLAY_OFF;

  core.load_font();

  // The art's empty areas use BG tile 0 of VRAM bank 0; make it a solid
  // color-0 tile so they read as the flat backdrop of palette 1.
  VBK_REG = VBK_BANK_0;
  uint8_t *tile = VRAM_BG_TILES;
  for (uint8_t k = 0; k < 16; k++)
    *tile++ = 0;

  core.load_bg_palette(backdrop_palettes, 0, 2);
  core.load_bg_palette(text_palettes, 6, 2);
  core.draw_tilemap(name_entry_tilemap, VRAM_BACKGROUND);

  // The symbol row's own trailing gap, not a box of its own; see END_LABEL_COL.
  core.draw_text(
    VRAM_BACKGROUND_XY(END_LABEL_COL, grid_row_y[SYMBOL_ROW]), END_LABEL, END_LABEL_LEN);

  // The floor label's cells take the hint palette and start blank.
  core.fill(VRAM_BACKGROUND_XY(START_COL, START_ROW), START_LEN, 1, FONT_SPACE, ATTR_START);
  start_floor = 1;

  // Hero select's sprites are still positioned; hide them.
  for (uint8_t k = 0; k < 16; k++)
    move_sprite(k, 0, 0);

  // Start from the class default so START alone keeps the classic names.
  default_hero_name(selected_hero, name);
  name_len = 0;
  while (name_len < NAME_MAX && name[name_len])
    name_len++;
  draw_field();

  row = 0;
  col = 0;
  set_cell_attr(row, col, ATTR_GRID_SELECTED);

  DISPLAY_ON;
}

static void update_name_entry_impl(void) {
  if (was_pressed(J_START)) {
    confirm_name();
    return;
  }

  if (was_pressed(J_SELECT)) {
    start_floor = start_floor == LAST_START_FLOOR ? 1 : start_floor + 1;
    draw_start_floor();
    play_sound(sfx_menu_move);
    return;
  }

  if (was_pressed(J_A)) {
    if (row == SYMBOL_ROW && col == END_COL) {
      confirm_name();
      return;
    }
    if (name_len < NAME_MAX) {
      name[name_len++] = grid_char();
      draw_field();
      play_sound(sfx_menu_move);
    } else {
      play_sound(sfx_error);
    }
    return;
  }

  if (was_pressed(J_B)) {
    if (name_len) {
      name_len--;
      draw_field();
      play_sound(sfx_menu_move);
    } else {
      play_sound(sfx_error);
    }
    return;
  }

  uint8_t r = row;
  uint8_t c = col;
  if (was_pressed(J_UP))
    r = r ? r - 1 : GRID_ROWS - 1;
  else if (was_pressed(J_DOWN))
    r = r == GRID_ROWS - 1 ? 0 : r + 1;
  else if (was_pressed(J_LEFT))
    c = c ? c - 1 : grid_row_len[r] - 1;
  else if (was_pressed(J_RIGHT))
    c = c == grid_row_len[r] - 1 ? 0 : c + 1;
  else
    return;

  // Moving onto a shorter row clamps to its last character.
  if (c >= grid_row_len[r])
    c = grid_row_len[r] - 1;

  move_grid_cursor(r, c);
  play_sound(sfx_menu_move);
}

void init_name_entry(void) BANKED {
  init_name_entry_impl();
}

void update_name_entry(void) BANKED {
  update_name_entry_impl();
}

uint8_t ready_start_floor(void) BANKED {
  if (start_floor < 2)
    return 0;
  const FloorStart *start = floor_starts + (start_floor - 2);
  // Floors 2 to 6 each teach the next ability when their elite falls.
  grant_ability(start_floor > 6 ? ABILITY_ALL
    : (AbilityFlag)((1 << (start_floor - 1)) - 1));
  set_player_level(start->level);
  reset_player_stats();
  player.has_torch = true;
  // Floor 1 hands out the first key, so the key counter shows even at none.
  player.got_magic_key = true;
  player.magic_keys = start->magic_keys;
  for (uint8_t k = 0; k < INVENTORY_LEN; k++)
    add_items((ItemId)k, start->items[k]);
  return start_floor - 1;
}
