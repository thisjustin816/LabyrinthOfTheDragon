#pragma bank 7

#include <gb/gb.h>
#include <gb/cgb.h>
#include <stdint.h>
#include "main_menu.h"

/**
 * Save select background palettes. Font tiles draw their glyph in color 3 over
 * a color 1 backing, so "invisible backing" palettes repeat the backdrop in
 * colors 0-2. Palettes 4-6 (the slot boxes) are loaded separately from the
 * save_*_selected_palettes tables below.
 */
const uint16_t save_select_bg_palettes[] = {
  // 0 - Backdrop and header text (white on navy)
  RGB_SAVE_NAVY,
  RGB_SAVE_NAVY,
  RGB_SAVE_NAVY,
  RGB_WHITE,
  // 1 - ERASE label. The deselected slot colors, so the button's face is the
  // same gray as its frame: the frame's vertical tiles are only part-width and
  // render their remainder in the frame palette, so a different face color
  // shows up as a band inset behind the word.
  PALETTE_SAVE_DESELECTED,
  // 2 - The erase prompt's YES box. Navy, so the box can't show, until the
  // prompt loads its colors.
  RGB_SAVE_NAVY,
  RGB_SAVE_NAVY,
  RGB_SAVE_NAVY,
  RGB_SAVE_NAVY,
  // 3 - ERASE button frame. Overwritten by draw_action_label before the first
  // frame is shown; this entry only keeps the screen from flashing the title
  // screen's leftover palette if that order ever changes.
  RGB_SAVE_NAVY,
  RGB_SAVE_NAVY,
  RGB_SAVE_NAVY,
  RGB_SAVE_NAVY,
};

const uint16_t save_select_erase_palette[] = {
  RGB_SAVE_NAVY,
  RGB_SAVE_ERASE_RED,
  RGB_GRAY_MID,
  RGB_WHITE,
};

// Palette 3 draws the ERASE box's frame. It cannot share the label's palette:
// the border tile's outline and the label's text ink are both color 3, and the
// label needs that white to stay readable on its dark fill, which is what
// turned the frame white. These are the slot boxes' own colors, so the frame
// matches theirs, and it swaps to the selected set on focus the way they do.
const uint16_t save_select_box_palette[] = {
  PALETTE_SAVE_DESELECTED,
};

const uint16_t save_select_box_focus_palette[] = {
  PALETTE_SAVE_SELECTED,
};

// Armed: the frame turns red with the face so the whole button reads as one
// shape rather than a red band in a gray box.
const uint16_t save_select_box_erase_palette[] = {
  RGB_WHITE,
  RGB_SAVE_ERASE_RED,
  RGB_GRAY_MID,
  RGB_GRAY_DARK,
};

const uint16_t save_select_focus_palette[] = {
  RGB_SAVE_NAVY,
  RGB_SAVE_GOLD,
  RGB_SAVE_ORANGE,
  RGB_SAVE_BROWN,
};

const uint16_t save_select_version_palette[] = {
  RGB_SAVE_NAVY,
  RGB_SAVE_NAVY,
  RGB_SAVE_NAVY,
  RGB_SAVE_HINT,
};

const uint16_t save_1_selected_palettes[] = {
  PALETTE_SAVE_SELECTED,
  PALETTE_SAVE_DESELECTED,
  PALETTE_SAVE_DESELECTED,
};

const uint16_t save_2_selected_palettes[] = {
  PALETTE_SAVE_DESELECTED,
  PALETTE_SAVE_SELECTED,
  PALETTE_SAVE_DESELECTED,
};

const uint16_t save_3_selected_palettes[] = {
  PALETTE_SAVE_DESELECTED,
  PALETTE_SAVE_DESELECTED,
  PALETTE_SAVE_SELECTED,
};

const uint16_t save_none_selected_palettes[] = {
  PALETTE_SAVE_DESELECTED,
  PALETTE_SAVE_DESELECTED,
  PALETTE_SAVE_DESELECTED,
};

const uint16_t hero_palettes[] = {
  // Deselected Hero
  RGB(0, 0, 0),
  RGB_GRAY_LIGHT,
  RGB_GRAY_MID,
  RGB_GRAY_DARK,
  // Hero 1
  RGB(0, 0, 0),
  RGB8(245, 213, 135),
  RGB8(167, 75, 0),
  RGB8(8, 46, 54),
  // Hero 2
  RGB(0, 0, 0),
  RGB8(89, 60, 15),
  RGB8(131, 146, 32),
  RGB8(8, 46, 54),
  // Hero 3
  RGB(0, 0, 0),
  RGB8(200, 165, 45),
  RGB8(180, 69, 61),
  RGB8(61, 20, 97),
};
