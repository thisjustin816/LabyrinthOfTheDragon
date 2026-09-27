// Bank 7, alongside save.c and main_menu.data.c. Banks 0-2 are nearly full,
// and this screen reads its palette tables out of main_menu.data.c directly,
// so the code and that data have to share a bank.
#pragma bank 7

#include <gb/gb.h>
#include <gb/cgb.h>
#include <stdint.h>

#include "core.h"
#include "hero_select.h"
#include "main_menu.h"
#include "player.h"
#include "save.h"
#include "sound.h"
#include "title_screen.h"
#include "version.h"

uint8_t cursor = 0;

Timer menu_walk_timer;
uint8_t menu_walk_frame;

// `draw_tilemap` honors the `bank` field, so the tilemap itself can stay in
// bank 1 with the rest of the INCBIN'd art.
Tilemap save_select_tilemap = { 20, 18, BANK_1, tilemap_save_select };

/**
 * Cached per-slot summary, read once when the screen is initialized so that
 * cursor movement and sprite animation never have to touch SRAM.
 */
static bool slot_used[SAVE_SLOT_COUNT];
static uint8_t slot_class[SAVE_SLOT_COUNT];

/**
 * When set, choosing a slot erases it instead of playing it.
 */
static bool erase_mode;

/**
 * When set, erase mode is asking "ERASE THIS FILE?" about the slot under the
 * cursor, and `erase_yes` says which answer is lit.
 */
static bool erase_prompt;
static bool erase_yes;

// Layout of the save select art (see res/tilemaps/save_select.tilemap). Each
// slot occupies two rows: a name row and a stats row.
#define SLOT_NAME_ROW(i) (4 + ((i) << 2))
#define SLOT_STAT_ROW(i) (5 + ((i) << 2))
#define NAME_COL 6
#define NAME_LEN 6

// A cleared game (dragon slain, credits seen) gets a crown in the cell between
// the class sprite and the name. 0x1E was a blank cell in the font; the crown
// is drawn there in assets/tiles/font.png. draw_text maps it to tile
// 0x1E + FONT_OFFSET = 0x9E.
#define CLEAR_MARK_COL 5
#define CLEAR_MARK "\x1e"

// Stats row: the hero's level and floor with the pause menu's labels, as "L50"
// and "B8", drawn over the tilemap's HP, ATK, and DEF icons. It starts under
// the name and ends under the clock.
#define STATS_COL NAME_COL
#define STATS_LEN 12

// Clock on the name row, drawn as HH:MM.
#define CLOCK_COL 13
#define CLOCK_LEN 5

// The ERASE / BACK button: a box in the three rows below the last slot, built
// from the border tiles and attribute flips the slot boxes use so it reads as
// one of them rather than as a caption. The art bakes the word into row 16 at
// cols 13-17; draw_frame blanks that. Every label is padded to the interior
// width so the box holds its shape whichever word is showing.
#define ACTION_BOX_COL 10
#define ACTION_BOX_TOP_ROW 15
#define ACTION_LABEL_ROW 16
#define ACTION_BOX_BOTTOM_ROW 17
#define ACTION_LABEL_COL (ACTION_BOX_COL + 1)
#define ACTION_LABEL_LEN 7
#define BUTTON_WIDTH (ACTION_LABEL_LEN + 2)
#define BUTTON_HEIGHT 3
#define ACTION_LABEL_ART_COL 13
#define ACTION_LABEL_ART_ROW 16
#define ACTION_LABEL_ART_LEN 5
#define LABEL_ERASE " ERASE "
#define LABEL_BACK "  BACK "

// The erase prompt. The question takes the header row, which it fills
// exactly, and the answers take the button row: the ERASE button reads NO, and
// YES gets a box of the same shape to its left, so YES sits left of NO as it
// does in the map menu's QUIT prompt. The YES box draws its frame and its
// label in palette 2, which this screen otherwise leaves spare. The ERASE
// button needs a second palette only for its red armed look, and YES is only
// ever gold or gray.
#define HEADER_TEXT "CHOOSE YOUR FILE"
#define PROMPT_TEXT "ERASE THIS FILE?"
#define YES_BOX_COL 1
#define LABEL_YES "  YES  "
#define LABEL_NO "   NO  "

// Border tiles and the flips that orient them, lifted from the slot boxes in
// the art. The frame draws in palette 3, not the label's palette 1: the border
// tile's outline and the label's text ink are the same color index, and the
// label needs white there, which would force a white outline.
#define BOX_CORNER 0x90
#define BOX_EDGE_H 0x91
#define BOX_EDGE_V 0x92
#define ATTR_BOX 0x0B           // palette 3, bank 1, no flip
#define ATTR_YES_BOX 0x0A       // palette 2, bank 1, no flip
#define ATTR_FLIP_X 0x20        // for the right-hand side
#define ATTR_FLIP_Y 0x40        // for the bottom edge

// Text drawn over the art's blank rows: a header above the slots. The art
// leaves rows 0-2 and 15-17 empty; the ERASE button and the version sit in the
// lower block.
#define HEADER_ROW 1
#define HEADER_COL 2
#define HEADER_LEN 16

// The game's version from tools/version2h, such as v1.1.4+, at the bottom left
// and level with the button label. Its nine columns reach the button at col 10
// and hold a three-digit patch with the "+" of a build that isn't a release.
// The erase prompt's YES box covers it while the prompt is up.
#define VERSION_COL 1
#define VERSION_LEN 9

// BG attributes for runtime text: font tiles live in VRAM bank 1.
#define ATTR_HEADER_TEXT 0x08   // palette 0
#define ATTR_LABEL_TEXT 0x09    // palette 1
#define ATTR_VERSION_TEXT 0x0F  // palette 7

// Text shown in a slot that holds no game. The box interior runs from col 2 to
// col 17, so the string is padded to that full width: it centers the words and
// clears the row in one pass, crown cell included.
#define SLOT_INNER_COL 2
#define SLOT_INNER_LEN 16
#define EMPTY_SLOT_TEXT "  - NEW GAME -  "
#define EMPTY_SLOT_LEN SLOT_INNER_LEN

// Sprite palette assignments. Palette 1 is the grayed out "deselected" entry
// from hero_palettes; 2-5 are the real class colors from hero_colors, indexed
// by PlayerClass.
#define PALETTE_HERO_DIM 1
#define PALETTE_HERO_BASE 2

static const uint8_t hero_sprite_base[] = {
  SPRITE_HERO1, SPRITE_HERO2, SPRITE_HERO3,
};

// The numbers on this screen are formatted by hand rather than with sprintf.
// SDCC passes a value cast to char or uint8_t as a single byte rather than
// promoting it, so a "%u" fed one reads the neighboring argument as its high
// byte and prints garbage, such as "1024" for 4 seconds. GBDK's stdio.h warns
// about exactly this.

/**
 * Writes the level and floor row: "Lnn" under the name, with the level in one
 * or two digits as the pause menu draws it, and "Bn" under the end of the
 * clock, the floor counted down from B1 as the pause menu counts it. One
 * digit covers every floor.
 */
static void draw_level_floor(
  uint8_t col, uint8_t row, uint8_t level, uint8_t floor
) {
  char buf[STATS_LEN + 1] = "L         B ";
  uint8_t k = 1;
  if (level > 99)
    level = 99;
  if (level >= 10)
    buf[k++] = '0' + level / 10;
  buf[k] = '0' + level % 10;
  buf[STATS_LEN - 1] = '0' + floor;
  core.draw_text(VRAM_BACKGROUND_XY(col, row), buf, STATS_LEN);
}

/**
 * Draws elapsed play time as HH:MM. The play clock stops at 65535 seconds, so
 * this tops out at 18:12 and the hours always fit in two digits.
 */
static void draw_clock(uint8_t col, uint8_t row, uint16_t seconds) {
  char buf[6];
  const uint16_t total_mins = seconds / 60;
  const uint8_t hours = (uint8_t)(total_mins / 60);
  const uint8_t mins = (uint8_t)(total_mins - hours * 60);
  buf[0] = '0' + hours / 10;
  buf[1] = '0' + hours % 10;
  buf[2] = ':';
  buf[3] = '0' + mins / 10;
  buf[4] = '0' + mins % 10;
  buf[5] = 0;
  core.draw_text(VRAM_BACKGROUND_XY(col, row), buf, CLOCK_LEN);
}

/**
 * Reads every slot out of SRAM and paints its summary row. Also fills in the
 * cached `slot_used` / `slot_class` tables.
 */
static void draw_slots(void) {
  for (uint8_t k = 0; k < SAVE_SLOT_COUNT; k++) {
    const uint8_t name_row = SLOT_NAME_ROW(k);
    const uint8_t stat_row = SLOT_STAT_ROW(k);

    const SaveGame *s = save_slot_open(k);

    if (!s) {
      slot_used[k] = false;
      slot_class[k] = CLASS_FIGHTER;

      // Wipe the whole stats row too, icons included: an empty slot showing
      // the tilemap's stat icons with no numbers reads as broken.
      core.draw_text(
        VRAM_BACKGROUND_XY(SLOT_INNER_COL, name_row),
        EMPTY_SLOT_TEXT, EMPTY_SLOT_LEN);
      core.draw_text(
        VRAM_BACKGROUND_XY(SLOT_INNER_COL, stat_row), "", SLOT_INNER_LEN);
      continue;
    }

    slot_used[k] = true;
    slot_class[k] = (uint8_t)s->player.player_class & 0x03;

    // Read straight out of SRAM; it stays mapped until save_slot_close().
    core.draw_text(
      VRAM_BACKGROUND_XY(NAME_COL, name_row), s->player.name, NAME_LEN);
    core.draw_text(
      VRAM_BACKGROUND_XY(CLEAR_MARK_COL, name_row),
      (s->flag_pages[FLAGS_GAME] & FLAG_GAME_COMPLETE) ? CLEAR_MARK : " ", 1);

    draw_clock(CLOCK_COL, name_row, s->play_seconds);

    // floor_index counts from 0; players count floors from 1.
    draw_level_floor(
      STATS_COL, stat_row, s->player.level, s->floor_index + 1);

    save_slot_close();
  }
}

/**
 * Paints the ERASE / BACK label to match the cursor and the current mode. The
 * label lights up gold while the cursor is on it (the same treatment the slot
 * boxes get), is red while erase mode is armed and the cursor is elsewhere,
 * and gray otherwise. While the erase prompt is up the button reads NO, and
 * it and the YES box are gold for the lit answer and gray for the other.
 */
static void draw_action_label(void) {
  const bool focused = erase_prompt
    ? !erase_yes
    : cursor == SAVE_SELECT_CURSOR_ERASE;
  const bool armed = erase_mode && !erase_prompt;

  core.draw_text(
    VRAM_BACKGROUND_XY(ACTION_LABEL_COL, ACTION_LABEL_ROW),
    erase_prompt ? LABEL_NO : erase_mode ? LABEL_BACK : LABEL_ERASE,
    ACTION_LABEL_LEN);

  core.load_bg_palette(
    focused ? save_select_focus_palette :
    armed ? save_select_erase_palette : save_select_bg_palettes + 4,
    1, 1);
  core.load_bg_palette(
    focused ? save_select_box_focus_palette :
    armed ? save_select_box_erase_palette : save_select_box_palette,
    3, 1);

  if (erase_prompt) {
    core.load_bg_palette(
      erase_yes ? save_select_box_focus_palette : save_select_box_palette,
      2, 1);
  }
}

/**
 * Draws a button's box in the three rows below the last slot, with its left
 * edge at `col`, and blanks its face. `frame` is the attribute byte for the
 * border and `face` the one for the label, both without flips.
 */
static void draw_button(uint8_t col, uint8_t frame, uint8_t face) {
  const uint8_t right = col + BUTTON_WIDTH - 1;

  core.fill(VRAM_BACKGROUND_XY(col, ACTION_BOX_TOP_ROW),
    1, 1, BOX_CORNER, frame);
  core.fill(VRAM_BACKGROUND_XY(col + 1, ACTION_BOX_TOP_ROW),
    ACTION_LABEL_LEN, 1, BOX_EDGE_H, frame);
  core.fill(VRAM_BACKGROUND_XY(right, ACTION_BOX_TOP_ROW),
    1, 1, BOX_CORNER, frame | ATTR_FLIP_X);

  core.fill(VRAM_BACKGROUND_XY(col, ACTION_LABEL_ROW),
    1, 1, BOX_EDGE_V, frame);
  core.fill(VRAM_BACKGROUND_XY(col + 1, ACTION_LABEL_ROW),
    ACTION_LABEL_LEN, 1, FONT_SPACE, face);
  core.fill(VRAM_BACKGROUND_XY(right, ACTION_LABEL_ROW),
    1, 1, BOX_EDGE_V, frame | ATTR_FLIP_X);

  core.fill(VRAM_BACKGROUND_XY(col, ACTION_BOX_BOTTOM_ROW),
    1, 1, BOX_CORNER, frame | ATTR_FLIP_Y);
  core.fill(VRAM_BACKGROUND_XY(col + 1, ACTION_BOX_BOTTOM_ROW),
    ACTION_LABEL_LEN, 1, BOX_EDGE_H, frame | ATTR_FLIP_Y);
  core.fill(VRAM_BACKGROUND_XY(right, ACTION_BOX_BOTTOM_ROW),
    1, 1, BOX_CORNER, frame | ATTR_FLIP_X | ATTR_FLIP_Y);
}

/**
 * Draws the version at the bottom left, blanking the rest of its field.
 */
static void draw_version(void) {
  core.fill(VRAM_BACKGROUND_XY(VERSION_COL, ACTION_LABEL_ROW),
    VERSION_LEN, 1, FONT_SPACE, ATTR_VERSION_TEXT);
  core.draw_text(VRAM_BACKGROUND_XY(VERSION_COL, ACTION_LABEL_ROW),
    GAME_VERSION, VERSION_LEN);
}

/**
 * Draws the parts of the screen the art leaves blank: a solid backdrop, the
 * header, the ERASE button, and the version. Display must be off.
 */
static void draw_frame(void) {
  // The art's blank areas use BG tile 0, which is whatever the title screen
  // last left at 0x9000. Make it a solid color-0 tile so the backdrop is the
  // flat navy of palette 0 rather than a leftover graphic.
  VBK_REG = VBK_BANK_0;
  uint8_t *tile = VRAM_BG_TILES;
  for (uint8_t k = 0; k < 16; k++)
    *tile++ = 0;

  core.load_bg_palette(save_select_bg_palettes, 0, 4);
  core.load_bg_palette(save_select_version_palette, 7, 1);

  // Header: set the font bank/palette attributes, then text.
  core.fill(VRAM_BACKGROUND_XY(0, HEADER_ROW), 20, 1, FONT_SPACE, ATTR_HEADER_TEXT);
  core.draw_text(
    VRAM_BACKGROUND_XY(HEADER_COL, HEADER_ROW), HEADER_TEXT, HEADER_LEN);

  // Wipe the art's own ERASE label back to backdrop (tile 0 is the solid
  // color-0 tile filled in above); the button is drawn over it below.
  core.fill(
    VRAM_BACKGROUND_XY(ACTION_LABEL_ART_COL, ACTION_LABEL_ART_ROW),
    ACTION_LABEL_ART_LEN, 1, 0, 0);

  // The button's box. Only tiles and attributes here; draw_action_label paints
  // the word and swaps palette 1 to match the cursor.
  draw_button(ACTION_BOX_COL, ATTR_BOX, ATTR_LABEL_TEXT);

  draw_version();
}

/**
 * Recolors the slot boxes, the ERASE / BACK label, and the hero sprites to
 * match the highlighted entry. There is no cursor sprite: the highlighted entry
 * is the gold one.
 */
static void refresh_selection(void) {
  if (cursor == SAVE_SELECT_CURSOR_ERASE) {
    set_bkg_palette(4, 3, save_none_selected_palettes);
  } else {
    switch (cursor) {
    case SAVE_SELECT_CURSOR_SAVE1:
      set_bkg_palette(4, 3, save_1_selected_palettes);
      break;
    case SAVE_SELECT_CURSOR_SAVE2:
      set_bkg_palette(4, 3, save_2_selected_palettes);
      break;
    default:
      set_bkg_palette(4, 3, save_3_selected_palettes);
      break;
    }
  }

  for (uint8_t k = 0; k < SAVE_SLOT_COUNT; k++) {
    const uint8_t base = hero_sprite_base[k];

    // Empty slots have no character to show.
    if (!slot_used[k]) {
      for (uint8_t s = 0; s < 4; s++)
        move_sprite(base + s, 0, 0);
      continue;
    }

    const uint8_t prop = (cursor == k)
      ? PALETTE_HERO_BASE + slot_class[k]
      : PALETTE_HERO_DIM;

    for (uint8_t s = 0; s < 4; s++)
      set_sprite_prop(base + s, prop);
  }

  draw_action_label();
}

/**
 * Places the four sprites that make up a slot's 16x16 character.
 */
static void position_hero_sprites(uint8_t slot, uint8_t x, uint8_t y) {
  const uint8_t base = hero_sprite_base[slot];
  move_sprite(base + 0, x, y);
  move_sprite(base + 1, x + 8, y);
  move_sprite(base + 2, x, y + 8);
  move_sprite(base + 3, x + 8, y + 8);
}

static void init_save_select_impl(void) {
  DISPLAY_OFF;

  core.load_font();
  core.load_all_heros();

  core.draw_tilemap(save_select_tilemap, VRAM_BACKGROUND);
  draw_frame();

  erase_mode = false;
  erase_prompt = false;
  cursor = SAVE_SELECT_CURSOR_SAVE1;

  // Palette 1 is hero_palettes' grayed out entry; 2-5 are the class colors.
  set_sprite_palette(PALETTE_HERO_DIM, 1, hero_palettes);
  core.load_sprite_palette(hero_colors, PALETTE_HERO_BASE, 4);

  position_hero_sprites(0, HERO1_X, HERO1_Y);
  position_hero_sprites(1, HERO2_X, HERO2_Y);
  position_hero_sprites(2, HERO3_X, HERO3_Y);

  draw_slots();

  menu_walk_frame = 0;
  init_timer(menu_walk_timer, 12);

  refresh_selection();

  DISPLAY_ON;
}

/**
 * Animates the highlighted slot's character. Tile bases run 0x20 apart in
 * class order, and the walk frame is two tiles further on.
 */
static void update_hero_sprites(void) {
  if (update_timer(menu_walk_timer)) {
    reset_timer(menu_walk_timer);
    menu_walk_frame ^= 1;
  }

  for (uint8_t k = 0; k < SAVE_SLOT_COUNT; k++) {
    if (!slot_used[k])
      continue;

    const uint8_t tile = slot_class[k] << 5;
    const uint8_t step = (cursor == k && menu_walk_frame) ? 2 : 0;
    const uint8_t base = hero_sprite_base[k];

    set_sprite_tile(base + 0, tile + step);
    set_sprite_tile(base + 1, tile + step + 1);
    set_sprite_tile(base + 2, tile + step + 0x10);
    set_sprite_tile(base + 3, tile + step + 0x11);
  }
}

static void move_cursor(void) {
  if (was_pressed(J_UP)) {
    cursor = (cursor == SAVE_SELECT_CURSOR_SAVE1)
      ? SAVE_SELECT_CURSOR_ERASE
      : cursor - 1;
  } else if (was_pressed(J_DOWN)) {
    cursor = (cursor == SAVE_SELECT_CURSOR_ERASE)
      ? SAVE_SELECT_CURSOR_SAVE1
      : cursor + 1;
  } else {
    return;
  }

  play_sound(sfx_menu_move);
  refresh_selection();
}

/**
 * Hands off to the world map. NONBANKED because init_world_map() leaves bank 2
 * paged in, which would otherwise pull this file out from under itself.
 */
static void enter_world_map(void) NONBANKED {
  const uint8_t _prev_bank = CURRENT_BANK;
  init_world_map();
  game_state = GAME_STATE_WORLD_MAP;
  SWITCH_ROM(_prev_bank);
}

/**
 * Hands off to hero select to create a new character.
 */
static void enter_hero_select(void) NONBANKED {
  const uint8_t _prev_bank = CURRENT_BANK;
  init_hero_select();
  game_state = GAME_STATE_HERO_SELECT;
  SWITCH_ROM(_prev_bank);
}

static void hide_all_sprites(void) {
  for (uint8_t k = 0; k < 16; k++)
    move_sprite(k, 0, 0);
}

/**
 * Asks before erasing the file under the cursor. NO is lit first, so pressing
 * A through the prompt keeps the file.
 */
static void open_erase_prompt(void) {
  erase_prompt = true;
  erase_yes = false;
  draw_action_label();
  core.draw_text(
    VRAM_BACKGROUND_XY(HEADER_COL, HEADER_ROW), PROMPT_TEXT, HEADER_LEN);
  draw_button(YES_BOX_COL, ATTR_YES_BOX, ATTR_YES_BOX);
  core.draw_text(
    VRAM_BACKGROUND_XY(YES_BOX_COL + 1, ACTION_LABEL_ROW), LABEL_YES,
    ACTION_LABEL_LEN);
  play_sound(sfx_menu_move);
}

/**
 * Takes the prompt down and goes back to erase mode, with the cursor still on
 * the file.
 */
static void close_erase_prompt(void) {
  erase_prompt = false;
  core.draw_text(
    VRAM_BACKGROUND_XY(HEADER_COL, HEADER_ROW), HEADER_TEXT, HEADER_LEN);
  // Tile 0 is the solid backdrop tile draw_frame makes. The version was under
  // the YES box, so it goes back on top.
  core.fill(VRAM_BACKGROUND_XY(YES_BOX_COL, ACTION_BOX_TOP_ROW),
    BUTTON_WIDTH, BUTTON_HEIGHT, 0, 0);
  draw_version();
  draw_action_label();
  play_sound(sfx_menu_move);
}

/**
 * Runs the erase prompt. LEFT and RIGHT move between YES and NO, as they do in
 * the map menu's QUIT prompt, and A or START answers. B, UP, and DOWN back
 * out.
 */
static void update_erase_prompt(void) {
  if (was_pressed(J_B) || was_pressed(J_UP) || was_pressed(J_DOWN)) {
    close_erase_prompt();
    return;
  }

  if (was_pressed(J_LEFT) || was_pressed(J_RIGHT)) {
    erase_yes = !erase_yes;
    draw_action_label();
    play_sound(sfx_menu_move);
    return;
  }

  if (!was_pressed(J_A) && !was_pressed(J_START))
    return;

  if (!erase_yes) {
    close_erase_prompt();
    return;
  }

  save_erase(cursor);
  play_sound(sfx_wall_hit);
  // Repaint the whole screen with the display off rather than poking VRAM
  // mid-frame. The repaint also ends erase mode and takes the prompt down.
  init_save_select_impl();
}

/**
 * Handles the A button.
 */
static void confirm_selection(void) {
  if (cursor == SAVE_SELECT_CURSOR_ERASE) {
    // Toggle erase mode and drop the cursor onto the first slot so the next
    // press acts on something.
    erase_mode = !erase_mode;
    if (erase_mode)
      cursor = SAVE_SELECT_CURSOR_SAVE1;
    play_sound(sfx_menu_move);
    refresh_selection();
    return;
  }

  if (erase_mode) {
    if (!slot_used[cursor]) {
      play_sound(sfx_error);
      return;
    }
    open_erase_prompt();
    return;
  }

  if (!slot_used[cursor]) {
    // Empty slot: bind it and build a character.
    active_save_slot = cursor;
    play_sound(sfx_hero_selected);
    DISPLAY_OFF;
    hide_all_sprites();
    enter_hero_select();
    return;
  }

  if (!save_load(cursor)) {
    play_sound(sfx_error);
    return;
  }

  play_sound(sfx_hero_selected);
  DISPLAY_OFF;
  hide_all_sprites();
  enter_world_map();
}

static void update_save_select_impl(void) {
  if (erase_prompt) {
    update_erase_prompt();
    update_hero_sprites();
    return;
  }

  if (was_pressed(J_A) || was_pressed(J_START)) {
    confirm_selection();
    return;
  }

  if (was_pressed(J_B)) {
    if (erase_mode) {
      erase_mode = false;
      refresh_selection();
      play_sound(sfx_menu_move);
      return;
    }
    // Back out to the title.
    play_sound(sfx_menu_move);
    hide_all_sprites();
    return_to_title_screen();
    game_state = GAME_STATE_TITLE;
    return;
  }

  move_cursor();
  update_hero_sprites();
}

void init_save_select(void) BANKED {
  init_save_select_impl();
}

void update_save_select(void) BANKED {
  update_save_select_impl();
}
