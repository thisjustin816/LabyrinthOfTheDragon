#include <gb/gb.h>
#include <gb/cgb.h>
#include <rand.h>
#include <stdint.h>

#include "battle.h"
#include "credits.h"
#include "core.h"
#include "hero_select.h"
#include "main_menu.h"
#include "map.h"
#include "name_entry.h"
#include "sound.h"
#include "stats.h"
#include "test.h"
#include "title_screen.h"

GameState game_state = GAME_STATE_TITLE;
uint16_t play_seconds;

/**
 * VBlank counter used to drive `play_seconds`.
 */
static uint8_t play_frames;

uint8_t joypad_down;
uint8_t joypad_pressed;
uint8_t joypad_released;

/**
 * Initial game modes. The test modes jump straight to a development state.
 */
#define GAME_MODE_NORMAL 1
#define GAME_MODE_HERO_SELECT 2
#define GAME_MODE_TEST_LEVEL 3
#define GAME_MODE_TEST_BATTLE 4
#define GAME_MODE_TEST_CREDITS 5

/**
 * Selects the initial game mode, one of the GAME_MODE_* values above. A switch
 * on a const variable would compile the other modes as unreachable code, which
 * SDCC warns about, so the preprocessor picks the mode.
 */
#define INITIAL_MODE GAME_MODE_NORMAL

/**
 * Uncomment to enable sound effect testing when pressing the 'B' button.
 */
// #define SFX_TEST

/**
 * Random seed for the game. At 0, every frame on the title, file, hero, and
 * name screens adds to the running count (map.c's new_seed) that seeds the
 * dice on a map's first move. Any other value seeds the dice with it at
 * power-on and leaves those screens out of the count.
 */
#define RANDOM_SEED 0

/**
 * Initializes the core game engine.
 */
static inline void initialize(void) {
  initarand(RANDOM_SEED);
  hide_window();

#if INITIAL_MODE == GAME_MODE_NORMAL
  init_title_screen();
  game_state = GAME_STATE_TITLE;
#elif INITIAL_MODE == GAME_MODE_HERO_SELECT
  init_hero_select();
  game_state = GAME_STATE_HERO_SELECT;
#elif INITIAL_MODE == GAME_MODE_TEST_LEVEL
  test_level();
#elif INITIAL_MODE == GAME_MODE_TEST_BATTLE
  test_battle();
#elif INITIAL_MODE == GAME_MODE_TEST_CREDITS
  init_credits();
#else
#error "INITIAL_MODE must be one of the GAME_MODE_* values"
#endif
}

/**
 * Executes core gameloop logic.
 */
static inline void game_loop(void) {
  switch (game_state) {
  case GAME_STATE_TITLE:
    update_title_screen();
    break;
  case GAME_STATE_SAVE_SELECT:
    update_save_select();
    break;
  case GAME_STATE_HERO_SELECT:
    update_hero_select();
    break;
  case GAME_STATE_WORLD_MAP:
    update_world_map();
    break;
  case GAME_STATE_BATTLE:
    update_battle();
    break;
  case GAME_STATE_CREDITS:
    update_credits();
    break;
  case GAME_STATE_NAME_ENTRY:
    update_name_entry();
    break;
  }
}

/**
 * Counts a frame on the screens before play toward the map's seed, when
 * RANDOM_SEED is 0.
 */
static inline void count_seed_frame(void) {
#if RANDOM_SEED == 0
  switch (game_state) {
  case GAME_STATE_TITLE:
  case GAME_STATE_SAVE_SELECT:
  case GAME_STATE_HERO_SELECT:
  case GAME_STATE_NAME_ENTRY:
    new_seed++;
    break;
  }
#endif
}

/**
 * Executes rendering logic that must occur during a VBLANK.
 */
static inline void render(void) {
  switch (game_state) {
  case GAME_STATE_WORLD_MAP:
    draw_world_map();
    break;
  case GAME_STATE_BATTLE:
    draw_battle();
    break;
  case GAME_STATE_TEST:
    return;
  }
}

/**
 * Reads and updates the joypad state.
 */
static inline void update_joypad(void) {
  uint8_t last = joypad_down;
  joypad_down = joypad();
  joypad_pressed = ~last & joypad_down;
  joypad_released = last & ~joypad_down;
}

/**
 * Main function for the game. Handles initialization, game loop setup, and
 * joypad state updates.
 */
void main(void) {
  if (_cpu == CGB_TYPE)
    cpu_fast();
  else {
    while(1) {}
  }

  disable_interrupts();
  DISPLAY_OFF;

  sound_init();

  LCDC_REG = LCDCF_OFF
    | LCDCF_OBJON
    | LCDCF_BGON
    | LCDCF_WINON
    | LCDCF_WIN9C00;
  initialize();

  DISPLAY_ON;

  enable_interrupts();

  while (1) {
    update_joypad();

    #ifdef SFX_TEST
    if (was_pressed(J_B))
      play_sound(sfx_test);
    #endif

    count_seed_frame();
    game_loop();
    vsync();

    // ~59.7 VBlanks per second on a CGB; close enough for a play clock.
    if (++play_frames >= 60) {
      play_frames = 0;
      if (play_seconds < 0xFFFF)
        play_seconds++;
    }

    render();
  }
}
