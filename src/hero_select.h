#ifndef _HERO_SELECT_H
#define _HERO_SELECT_H

#include <gb/gb.h>

#include "player.h"

/**
 * Initializes the hero select screen.
 */
void init_hero_select(void) NONBANKED;

/**
 * Performs game loop updates for the hero select screen.
 */
void update_hero_select(void) NONBANKED;

/**
 * Class the player picked on the hero select screen.
 */
extern uint8_t selected_hero;

/**
 * Name typed on the name entry screen (NUL padded; empty = class default).
 */
extern char new_hero_name[PLAYER_NAME_LEN];

/**
 * Creates the character for `selected_hero` and enters the world map. Called
 * from the name entry screen.
 */
void start_game(void) NONBANKED;

#endif
