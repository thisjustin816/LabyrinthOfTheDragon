#ifndef _TEXTBOX_H
#define _TEXTBOX_H

#include "text_writer.h"

/**
 * State enumeration for the animated pop-up textbox.
 */
typedef enum TextBoxState {
  TEXT_BOX_CLOSED,
  TEXT_BOX_OPENING,
  TEXT_BOX_OPEN,
  TEXT_BOX_CLOSING,
} TextBoxState;

/**
 * Animated pop-up text box.
 */
typedef struct TextBox {
  /**
   * Initializes the text box.
   */
  const void (*init)(void);
  /**
   * Opens the textbox and starts printing the given text.
   */
  const void (*open)(const char *text);
  /**
   * Called to render updates for the textbox.
   */
  const void (*update)(void);
  /**
   * Current state of the textbox.
   */
  TextBoxState state;
  /**
   * Current y position for the window (which contains the text box).
   */
  uint8_t y;
  /**
   * Text to be written to the text box.
   */
  const char *text;
} TextBox;

/**
 * Animated pop-up text box. Uses the `TextWriter` under the hood to animate
 * text for interaction on the world map or in cutscenes.
 */
extern TextBox textbox;

/**
 * Palette used by the text box.
 *
 * This is bank 2 data, so only bank 2 code can hand the pointer to
 * `core.load_bg_palette()`. Callers elsewhere use
 * `reload_textbox_palette()`.
 */
extern const palette_color_t textbox_palette[4];

/**
 * Loads the text box's palette back into BG palette 7.
 *
 * Whatever borrows that slot while the box is hidden gives it back through
 * here. `core.load_bg_palette()` lives in ROM0 and dereferences the palette
 * pointer with the caller's bank still mapped, so a caller in another bank
 * reads its own bank at `textbox_palette`'s address and loads whatever happens
 * to sit there. Being BANKED, this function switches to bank 2 first.
 */
void reload_textbox_palette(void) BANKED;

#endif
