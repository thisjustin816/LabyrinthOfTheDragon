"""Constructed starts: drop a character onto any floor, ready to play it.

Playing every floor below to reach floor 7 costs hours per run and proves
nothing about floor 7. A suite starts here instead: the character arrives at
the level the floor itself demands, carrying what the floors below it would
have given, and the suite tests the floor rather than the walk to it.

The two numbers that make a start honest are the level and the ability list,
and both come from the game rather than from taste:

  * LEVEL is the floor's own boss gate, the `player.level < N` test in its
    on_npc_action. Below it the boss refuses to fight, so it is the minimum a
    player must reach, and starting there tests the floor at its intended
    difficulty instead of over-leveled.
  * ABILITIES is what the floors below have granted. Floors 2 to 6 each call
    teach_elite_ability() on their elite, so arriving at floor N carries ABILITY_0
    (innate) plus one bit per floor cleared, and everything from floor 7 on
    carries the full six.

Supplies are deliberately NOT modeled. A constructed start hands over whatever
`items` the caller asks for, and nothing about a real arrival's inventory
follows from it.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import *
from heroes import build_character, sram_for, CLASS_NAMES

# Each floor's boss gate, from the `player.level < N` test in its
# on_npc_action() in src/floor1.c to src/floor7.c. Floor 8's dragon has no
# gate, so its entry is a chosen level rather than a gate.
FLOOR_BOSS_GATE = {1: 8, 2: 15, 3: 18, 4: 24, 5: 32, 6: 34, 7: 36, 8: 60}

# ability_flags on arrival. ABILITY_0 is innate; floors 2-6 grant ABILITY_1 to
# ABILITY_5 in their elite_victory(), so the set is complete from floor 7 on.
ABILITIES_ON_ARRIVAL = {
    1: 0x01, 2: 0x01, 3: 0x03, 4: 0x07, 5: 0x0F, 6: 0x1F, 7: 0x3F, 8: 0x3F,
}

# Magic keys a start carries: the floor's key-locked treasure chests,
# which are the only locks a floor does not pay for itself. A key lock is a
# chest with BOTH `locked` and `magic_key_unlock` set (floor 1's locked chest
# has the second clear -- a script opens it) or a door with
# `magic_key_required` set.
#
# The key-locked doors are progression, and every floor that has them funds
# them itself: floors 1, 2 and 7 each grant exactly as many keys as they have
# key doors, reachable before the doors. Floor 7 is the one where that looked
# doubtful, since its keys sit inside the wings its key doors guard; a
# fixed-point reachability pass over its tilemap shows the chain resolves from
# zero keys, because the side rooms holding those keys open by plate and
# sconce rather than by key. So those floors start with none.
#
# The key-locked chests on floors 3 to 6 are optional treasure, and there the
# game runs 4 keys short (10 locks, 6 keys granted), so a straight-through
# player opens 6 of the 10 and the floor reset brings them back for the rest.
# These counts are a convenience, not a claim that a real arrival would be
# carrying them.
KEY_LOCKED_CHESTS = {1: 0, 2: 0, 3: 2, 4: 2, 5: 3, 6: 3, 7: 0, 8: 0}

MONK = 2


def start_on(floor, class_id=MONK, level=None, items=None, keys=None, tag=None,
             abilities=None):
    """Boot a game with a character standing at `floor`'s entrance.

    Returns (game, stats). `level` defaults to the floor's boss gate, `keys` to
    what the floor's locked chests need, `items` to nothing -- a caller that
    wants supplies must say so -- and `abilities` to what the floors below
    grant. A suite testing one ability's mechanics passes 0x3F.
    """
    level = FLOOR_BOSS_GATE[floor] if level is None else level
    keys = KEY_LOCKED_CHESTS[floor] if keys is None else keys
    abilities = ABILITIES_ON_ARRIVAL[floor] if abilities is None else abilities
    tag = tag or f"f{floor}_{CLASS_NAMES[class_id].lower()}"
    blob, st = build_character(class_id, level, floor=floor, items=items,
                               abilities=abilities, keys=keys, tag=tag)
    g = Game(tag=tag, sram=sram_for(blob))
    assert g.boot_to_save_select(), f"{tag}: never reached save select"
    g.save_select_pick(0)
    g.wait_map_idle(600)
    # The fade-in ends a frame before the floor's on_init sets up its
    # encounter ramp and puzzles, which would undo a poke made in between.
    g.wait_for(lambda: not g.rd8(SYM["execute_on_init"]), 60)
    assert current_floor(g) == floor, \
        f"{tag}: wanted floor {floor}, landed on {current_floor(g)}"
    # player_str already ends with the inventory and key count.
    log(f"=== start_on(floor {floor}, {CLASS_NAMES[class_id]}, level {level}) "
        f"pos={g.pos()} {player_str(g)}")
    return g, st


def reseed(g, frames):
    """Give the floor a different encounter sequence before the next step.

    map.c seeds the generator on the first move after a map loads, from a
    running frame count since power-on that update_map() keeps adding to
    for as long as init_random is set (map.c's start_move and update_map).
    So a floor's entire encounter sequence is decided by how many frames
    pass between arriving and taking the first step.

    A savestate restores all of that verbatim, which makes a reloaded
    checkpoint replay the same encounters tile for tile. Setting init_random back and idling `frames` frames advances the
    counter, so the next move seeds somewhere else and the retry is a real
    second attempt rather than a repeat of the first.
    """
    g.wr8(SYM["init_random"], 1)
    g.tick(frames)
