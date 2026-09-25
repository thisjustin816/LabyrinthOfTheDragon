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

#endif
