#ifndef _TITLE_SCREEN_H
#define _TITLE_SCREEN_H

#include <gb/gb.h>

/**
 * Initializes the game's title screen.
 */
void init_title_screen(void) BANKED;

/**
 * Game loop update handler for the title screen.
 */
void update_title_screen(void) BANKED;

/**
 * Returns to the main title (skipping the intro), e.g. when backing out of the
 * save select screen.
 */
void return_to_title_screen(void) BANKED;

#endif
