// Bank 7 with the rest of the menu screens: banks 0-2 are nearly full.
#pragma bank 7

#include <gb/gb.h>
#include <gb/cgb.h>
#include <stdint.h>

#include "core.h"
#include "hero_select.h"
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

// BG attributes: font tiles live in VRAM bank 1.
#define ATTR_GRID 0x0F           // palette 7, as the art has it
#define ATTR_GRID_SELECTED 0x0E  // palette 6

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

// PLAYER_NAME_LEN rather than NAME_MAX + 1: default_hero_name() fills the whole
// player-name buffer, and only the first NAME_MAX characters are editable here.
static char name[PLAYER_NAME_LEN];
static uint8_t name_len;
static uint8_t row;
static uint8_t col;

/**
 * Redraws the name field: the typed characters, then underscores.
 */
static void draw_field(void) {
  uint8_t *vram = VRAM_BACKGROUND_XY(FIELD_COL, FIELD_ROW);
  VBK_REG = VBK_TILES;
  for (uint8_t k = 0; k < NAME_MAX; k++, vram++)
    set_vram_byte(vram, (k < name_len ? name[k] : EMPTY_CHAR) + FONT_OFFSET);
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
