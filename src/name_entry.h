#ifndef _NAME_ENTRY_H
#define _NAME_ENTRY_H

#include "core.h"

/**
 * Initializes the name entry screen for `selected_hero`. Turns the display off
 * and back on. Follows hero select; START hands off to start_game().
 */
void init_name_entry(void) BANKED;

/**
 * Game loop update for the name entry screen.
 */
void update_name_entry(void) BANKED;

/**
 * Gives the new hero what a first run carries onto the floor picked with
 * SELECT on the name entry screen, and returns that floor's index, 0 for floor
 * 1. Floor 1, the default, changes nothing.
 */
uint8_t ready_start_floor(void) BANKED;

#endif
