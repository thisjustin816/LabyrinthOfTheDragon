#ifndef _MAIN_MENU_H
#define _MAIN_MENU_H

#include "core.h"

/**
 * Initializes the save select screen, reading each slot's summary from SRAM.
 */
void init_save_select(void) BANKED;

/**
 * Game loop update for the save select screen.
 */
void update_save_select(void) BANKED;

// Cursor and sprite related constants
#define SAVE_SELECT_CURSOR_SAVE1 0
#define SAVE_SELECT_CURSOR_SAVE2 1
#define SAVE_SELECT_CURSOR_SAVE3 2
#define SAVE_SELECT_CURSOR_ERASE 3

#define SPRITE_HERO1  1
#define SPRITE_HERO2  5
#define SPRITE_HERO3  9

#define HERO1_X 32
#define HERO1_Y 48

#define HERO2_X 32
#define HERO2_Y 80

#define HERO3_X 32
#define HERO3_Y 112

// Colors
#define RGB_BG_BLUE               RGB8(139, 163, 207)
#define RGB_BG_BLUE_FADE1         RGB8(100, 120, 160)
#define RGB_BG_BLUE_FADE2         RGB8(60, 80, 120)
#define RGB_BG_BLUE_DARK          RGB8(20, 40, 80)

// Save select colors. The box tiles use color 1 for the body, 2 for the border
// lines, 3 for the outline and text, and 0 only for the corner highlights.
#define RGB_SAVE_NAVY             RGB8(20, 22, 44)
#define RGB_SAVE_GOLD             RGB8(236, 212, 140)
#define RGB_SAVE_ORANGE           RGB8(184, 120, 40)
#define RGB_SAVE_BROWN            RGB8(64, 40, 16)
#define RGB_SAVE_ERASE_RED        RGB8(150, 40, 40)
#define RGB_SAVE_HINT             RGB8(150, 160, 190)

#define RGB_GRAY_DARK             RGB8(80, 80, 80)
#define RGB_GRAY_MID              RGB8(120, 120, 120)
#define RGB_GRAY_LIGHT            RGB8(180, 180, 180)

// The highlighted slot: warm gold body, orange border, brown text.
#define PALETTE_SAVE_SELECTED \
  RGB_WHITE, \
  RGB_SAVE_GOLD, \
  RGB_SAVE_ORANGE, \
  RGB_SAVE_BROWN

// Every other slot: neutral grays.
#define PALETTE_SAVE_DESELECTED \
  RGB_WHITE, \
  RGB_GRAY_LIGHT, \
  RGB_GRAY_MID, \
  RGB_GRAY_DARK

/**
 * Background palettes 0-3 for the save select screen: 0 the navy backdrop and
 * header text, 1 the ERASE button's face and label, 2 the erase prompt's YES
 * box, 3 the ERASE button's frame. `draw_action_label` reloads 1 and 3 on
 * every cursor move, and 2 while the prompt is up.
 */
extern const uint16_t save_select_bg_palettes[];

/**
 * Replacement for palette 1 while erase mode is armed: the label turns red.
 */
extern const uint16_t save_select_erase_palette[];

/**
 * The ERASE button's frame (palette 3), in the slot boxes' own colors:
 * `_box_palette` unfocused, `_box_focus_palette` while the cursor is on the
 * button, `_box_erase_palette` while erase mode is armed. The erase prompt's
 * YES box (palette 2) uses the first two for its frame and label alike.
 */
extern const uint16_t save_select_box_palette[];
extern const uint16_t save_select_box_focus_palette[];
extern const uint16_t save_select_box_erase_palette[];

/**
 * The ERASE / BACK label (palette 1) while the cursor is on it: the gold of
 * the selected slot box.
 */
extern const uint16_t save_select_focus_palette[];

/**
 * Background palette 7: the version at the bottom left, in the hint gray the
 * name entry screen uses.
 */
extern const uint16_t save_select_version_palette[];

extern const uint16_t save_1_selected_palettes[];
extern const uint16_t save_2_selected_palettes[];
extern const uint16_t save_3_selected_palettes[];
extern const uint16_t save_none_selected_palettes[];
extern const uint16_t hero_palettes[];

extern uint8_t cursor;

#endif
