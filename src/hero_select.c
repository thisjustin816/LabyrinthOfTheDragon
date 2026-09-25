#pragma bank 1

#include <gb/gb.h>
#include <gb/cgb.h>
#include <stdint.h>
#include <stdio.h>

#include "core.h"
#include "floor.h"
#include "hero_select.h"
#include "name_entry.h"
#include "player.h"
#include "main_menu.h"
#include "map.h"
#include "save.h"
#include "sound.h"

#define HERO_OFFSET_X 8 + 33
#define HERO_OFFSET_Y 78 + 8

const palette_color_t selection_bg_palettes[] = {
  RGB_WHITE,
  RGB8(81, 108, 186),
  RGB8(3, 37, 135),
  RGB8(22, 6, 4),
};

const palette_color_t selection_palettes[] = {
  // 5 - Unselected Hero
  RGB8(40, 40, 40),
  RGB8(80, 80, 80),
  RGB8(140, 140, 140),
  RGB8(20, 20, 20),
};

static const uint8_t hero_tiles[] = {
  0x00, 0x01, 0x10, 0x11, // Druid
  0x20, 0x21, 0x30, 0x31, // Fighter
  0x40, 0x41, 0x50, 0x51, // Monk
  0x60, 0x61, 0x70, 0x71, // Sorcerer
};

static const uint8_t hero_sprite_x[] = {
  0, 8, 0, 8,
  24, 32, 24, 32,
  48, 56, 48, 56,
  72, 80, 72, 80,
};

static const uint8_t hero_sprite_y[] = {
  0, 0, 8, 8,
  0, 0, 8, 8,
  0, 0, 8, 8,
  0, 0, 8, 8,
};

// The art leaves rows 11-17 blank under the four heroes, so the pick screen can
// say what each one is instead of showing four silhouettes and a title. Drawn
// from the same box tiles and attributes the art's own title box uses, so the
// panel reads as part of the screen rather than pasted onto it.
#define INFO_TOP_ROW 11
#define INFO_BOTTOM_ROW 17
#define INFO_LEFT_COL 1
#define INFO_RIGHT_COL 18
#define INFO_TEXT_COL (INFO_LEFT_COL + 1)
#define INFO_TEXT_LEN (INFO_RIGHT_COL - INFO_LEFT_COL - 1)

#define BOX_CORNER 0x90
#define BOX_EDGE_H 0x91
#define BOX_EDGE_V 0x92
#define ATTR_BOX 0x08           // palette 0, vram bank 1, no flip
#define ATTR_BOX_X 0x28
#define ATTR_BOX_Y 0x48
#define ATTR_BOX_XY 0x68

/**
 * What the pick screen says about a class. Indexed by `selected_hero`, so the
 * order matches `hero_tiles` above: druid, fighter, monk, sorcerer.
 *
 * Literals rather than entries in strings.js: they are shown on this screen and
 * nowhere else, and the string tool pre-wraps every entry to the widest its
 * parameters could be, which these have none of.
 */
typedef struct HeroInfo {
  const char *name;
  const char *line1;
  const char *line2;
  const char *stats1;
  const char *stats2;
} HeroInfo;

// The numbers are what each class starts on at level 4, read off the stat
// tables; t13 checks them against assets/tables.csv so they cannot drift.
static const HeroInfo hero_info[] = {
  { "DRUID",    "Heals and wards.", "Hard to kill.",
    "HP:17  MP:10", "ATK:9  DEF:11" },
  { "FIGHTER",  "Hits hard and",    "takes a beating.",
    "HP:19  SP:7",  "ATK:15 DEF:14" },
  { "MONK",     "Strikes first,",   "dodges often.",
    "HP:17  SP:10", "ATK:15 DEF:11" },
  { "SORCERER", "Huge damage,",     "almost no armor.",
    "HP:13  MP:14", "ATK:9  DEF:8" },
};

static const uint8_t hero_attr[] = {
  0, 0, 0, 0,
  4, 4, 4, 4,
  4, 4, 4, 4,
  4, 4, 4, 4,
};

Tilemap hero_select_tilemap = { 20, 18, 1, tilemap_hero_select };

uint8_t selected_hero = 0;

/**
 * Name typed on the name entry screen, NUL padded. Empty keeps the class
 * default that init_player() assigns.
 */
char new_hero_name[PLAYER_NAME_LEN];

Timer selected_walk_timer;
uint8_t selected_walk_frame = 0;

/**
 * Draws the info panel's frame. Display must be off.
 */
static void draw_info_frame(void) {
  core.fill(VRAM_BACKGROUND_XY(INFO_LEFT_COL, INFO_TOP_ROW), 1, 1, BOX_CORNER, ATTR_BOX);
  core.fill(VRAM_BACKGROUND_XY(INFO_TEXT_COL, INFO_TOP_ROW),
    INFO_TEXT_LEN, 1, BOX_EDGE_H, ATTR_BOX);
  core.fill(VRAM_BACKGROUND_XY(INFO_RIGHT_COL, INFO_TOP_ROW), 1, 1, BOX_CORNER, ATTR_BOX_X);

  for (uint8_t r = INFO_TOP_ROW + 1; r < INFO_BOTTOM_ROW; r++) {
    core.fill(VRAM_BACKGROUND_XY(INFO_LEFT_COL, r), 1, 1, BOX_EDGE_V, ATTR_BOX);
    core.fill(VRAM_BACKGROUND_XY(INFO_TEXT_COL, r), INFO_TEXT_LEN, 1, FONT_SPACE, ATTR_BOX);
    core.fill(VRAM_BACKGROUND_XY(INFO_RIGHT_COL, r), 1, 1, BOX_EDGE_V, ATTR_BOX_X);
  }

  core.fill(VRAM_BACKGROUND_XY(INFO_LEFT_COL, INFO_BOTTOM_ROW), 1, 1, BOX_CORNER, ATTR_BOX_Y);
  core.fill(VRAM_BACKGROUND_XY(INFO_TEXT_COL, INFO_BOTTOM_ROW),
    INFO_TEXT_LEN, 1, BOX_EDGE_H, ATTR_BOX_Y);
  core.fill(VRAM_BACKGROUND_XY(INFO_RIGHT_COL, INFO_BOTTOM_ROW), 1, 1, BOX_CORNER, ATTR_BOX_XY);
}

/**
 * Fills the info panel in for whichever hero is highlighted.
 */
static void draw_hero_info(void) {
  const HeroInfo *h = hero_info + (selected_hero & 0x03);
  uint8_t row = INFO_TOP_ROW + 1;
  core.draw_text(VRAM_BACKGROUND_XY(INFO_TEXT_COL, row++), h->name, INFO_TEXT_LEN);
  core.draw_text(VRAM_BACKGROUND_XY(INFO_TEXT_COL, row++), h->line1, INFO_TEXT_LEN);
  core.draw_text(VRAM_BACKGROUND_XY(INFO_TEXT_COL, row++), h->line2, INFO_TEXT_LEN);
  core.draw_text(VRAM_BACKGROUND_XY(INFO_TEXT_COL, row++), h->stats1, INFO_TEXT_LEN);
  core.draw_text(VRAM_BACKGROUND_XY(INFO_TEXT_COL, row), h->stats2, INFO_TEXT_LEN);
}

static void init_hero_select_impl(void) {
  DISPLAY_OFF;

  core.load_font();
  core.load_all_heros();

  core.load_sprite_palette(hero_colors, 0, 4);
  core.load_sprite_palette(selection_palettes, 4, 2);
  core.load_bg_palette(selection_bg_palettes, 0, 1);

  core.draw_tilemap(hero_select_tilemap, VRAM_BACKGROUND);


  for (uint8_t k = 0; k < 16; k++) {
    set_sprite_tile(k, hero_tiles[k]);
    set_sprite_prop(k, hero_attr[k]);
    move_sprite(k,
      hero_sprite_x[k] + HERO_OFFSET_X,
      hero_sprite_y[k] + HERO_OFFSET_Y);
  }

  selected_hero = 0;
  selected_walk_frame = 0;
  init_timer(selected_walk_timer, 12);

  draw_info_frame();
  draw_hero_info();

  DISPLAY_ON;
}

void start_game(void) NONBANKED {
  // init_world_map() leaves bank 2 paged in, so restore whatever the caller
  // was running from before returning to it.
  const uint8_t _prev_bank = CURRENT_BANK;

  DISPLAY_OFF;

  for (uint8_t k = 0; k < 16; k++)
    move_sprite(k, 0, 0);

  save_new_game();
  init_player(selected_hero);
  if (new_hero_name[0]) {
    for (uint8_t k = 0; k < PLAYER_NAME_LEN; k++)
      player.name[k] = new_hero_name[k];
  }
  play_seconds = 0;
  new_game_intro = true;
  set_active_floor(&bank_floor1);

  // Commit the new character to its slot straight away so the save select
  // screen shows the game even if the player never reaches a save point.
  save_write(active_save_slot);

  init_world_map();

  game_state = GAME_STATE_WORLD_MAP;

  SWITCH_ROM(_prev_bank);
}

void change_hero(void) {
  for (uint8_t k = 0; k < 16; k++) {
    set_sprite_prop(k, 4);
    set_sprite_tile(k, hero_tiles[k]);
  }

  for (uint8_t j = 0; j < 4; j++) {
    set_sprite_prop(selected_hero * 4 + j, selected_hero);
  }

  draw_hero_info();
  selected_walk_frame = 0;
}

static void update_hero_select_impl(void) {
  if (was_pressed(J_LEFT) || was_pressed(J_UP)) {
    selected_hero = selected_hero == 0 ? 3 : selected_hero - 1;
    play_sound(sfx_menu_move);
    change_hero();
  } else if (was_pressed(J_RIGHT) || was_pressed(J_DOWN)) {
    selected_hero = (selected_hero + 1) & 0x03;
    play_sound(sfx_menu_move);
    change_hero();
  } else if (was_pressed(J_B)) {
    DISPLAY_OFF;
    hide_sprites();
    game_state = GAME_STATE_SAVE_SELECT;
    init_save_select();
  } else if (was_pressed(J_START) || was_pressed(J_A)) {
    play_sound(sfx_hero_selected);
    init_name_entry();
    game_state = GAME_STATE_NAME_ENTRY;
    return;
  }

  if (!update_timer(selected_walk_timer))
    return;

  reset_timer(selected_walk_timer);
  selected_walk_frame = (selected_walk_frame + 1) & 0x1;

  for (uint8_t k = 0; k < 4; k++) {
    uint8_t id = k + selected_hero * 4;
    uint8_t offset = selected_walk_frame ? 2 : 0;
    set_sprite_tile(id, hero_tiles[id] + offset);
  }
}

void init_hero_select(void) NONBANKED {
  const uint8_t _prev_bank = CURRENT_BANK;
  SWITCH_ROM(BANK_1);
  init_hero_select_impl();
  SWITCH_ROM(_prev_bank);
}

void update_hero_select(void) NONBANKED {
  const uint8_t _prev_bank = CURRENT_BANK;
  SWITCH_ROM(BANK_1);
  update_hero_select_impl();
  SWITCH_ROM(_prev_bank);
}
