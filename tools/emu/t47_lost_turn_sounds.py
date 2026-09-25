"""T47 - a lost turn plays the fail sound, and a confused blow the melee hit.

The battle writes its own line in place of an action when a monster or the hero
loses a turn to lying prone, getting up, paralysis, fear, or a confused daze,
when a monster slips on Sleetstorm's ice, and when the monsters block the hero's
escape. Each plays the fail sound a monster already makes when it wastes a turn
on its own, like the goblin picking its nose. A confused blow on oneself plays
the melee hit sound.

Each case sets a status on floor 8's gauntlet goblin or on the hero, a fighter,
in the fight's savestate, and replays the round across battle seeds until the
line comes up. The check reads battle_sfx when the line appears. While the
goblin's statuses are tested the hero casts Second Wind, which leaves the goblin
alone, and while the hero's are tested it attacks.

Offsets from LabyrinthOfTheDragon.cdb: Encounter.monsters at +1, sizeof(Monster)
= 64, agl_base +28, agl +29, status_effects +34, trip_turns +59, and
Encounter.player_status_effects at +209. A status effect is 5 bytes: active,
effect, flag, duration, tier.
"""
import io, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "playtest"))
from lotd import *
from helpers import *
from starts import start_on

chk = Checker("t47_lost_turn_sounds")
FIGHTER, LEVEL = 1, 48
SECOND_WIND_ROW = 0                            # fighter1, src/player.data.c
MENU_FIGHT, MENU_FLEE = 0, 3
SECOND_WIND, FIGHT, FLEE = "Second Wind", "FIGHT", "FLEE"
SEED = SYM["__rand_seed"]
SEEDS = [0x2C41 + 0x3B7F * k & 0xFFFF for k in range(48)]
MON0 = SYM["encounter"] + 1
M_HP, M_TARGET_HP, M_AGL_BASE, M_AGL, M_EFFECTS, M_TRIP = 14, 16, 28, 29, 34, 59
P_EFFECTS = SYM["encounter"] + 209
SCARED, PARALYZED, CONFUSED = (1, 0x02), (2, 0x04), (4, 0x10)   # src/stats.h
S_TIER, PERPETUAL = 3, 0xFF
SLEET_STORM = 0x08                             # SPECIAL_SLEET_STORM, src/player.h
GOBLIN = (2, 27)                               # gauntlet fight tile, src/floor8.c
FAIL, MELEE = SYM["sfx_monster_fail"], SYM["sfx_monster_attack1"]
NAMES = {FAIL: "the fail sound", MELEE: "the melee hit sound"}


def effect_at(g, addr, status):
    effect, flag = status
    for off, value in enumerate((1, effect, flag, PERPETUAL, S_TIER)):
        g.wr8(addr + off, value)


def monster_effect(status):
    return lambda g: effect_at(g, MON0 + M_EFFECTS, status)


def hero_effect(status):
    return lambda g: effect_at(g, P_EFFECTS, status)


def monster_trip(turns):
    return lambda g: g.wr8(MON0 + M_TRIP, turns)


def hero_trip(turns):
    return lambda g: g.wr8(SYM["player"] + POFF["trip_turns"], turns)


def sleet_storm(g):
    flags = SYM["player"] + POFF["special_flags"]
    g.wr8(flags, g.rd8(flags) | SLEET_STORM)


def fast_goblin(g):
    g.wr8(MON0 + M_AGL_BASE, 255); g.wr8(MON0 + M_AGL, 255)


# (case, setup, the hero's action, words its line carries, sound)
CASES = [
    ("the goblin lying prone", monster_trip(2), SECOND_WIND, "lies prone", FAIL),
    ("the goblin getting up", monster_trip(1), SECOND_WIND, "gets up", FAIL),
    ("the goblin slipping on the ice", sleet_storm, SECOND_WIND, "slips on the ice", FAIL),
    ("the goblin paralyzed", monster_effect(PARALYZED), SECOND_WIND, "can't move", FAIL),
    ("the goblin frozen by fear", monster_effect(SCARED), SECOND_WIND, "shivers in fear", FAIL),
    ("the goblin confused into a stupor", monster_effect(CONFUSED), SECOND_WIND,
     "stares aimlessly", FAIL),
    ("the goblin confused into hitting itself", monster_effect(CONFUSED), SECOND_WIND,
     "attacks itself", MELEE),
    ("the hero lying prone", hero_trip(2), FIGHT, "You lie prone", FAIL),
    ("the hero getting up", hero_trip(1), FIGHT, "You get up", FAIL),
    ("the hero paralyzed", hero_effect(PARALYZED), FIGHT, "You are paralyzed", FAIL),
    ("the hero frozen by fear", hero_effect(SCARED), FIGHT, "You shiver", FAIL),
    ("the hero confused into mumbling", hero_effect(CONFUSED), FIGHT, "You mumble", FAIL),
    ("the hero confused into hitting itself", hero_effect(CONFUSED), FIGHT,
     "damage to yourself", MELEE),
    ("the hero blocked from fleeing", fast_goblin, FLEE, "But are blocked!", FAIL),
]


def act(g, action):
    """Give the hero's command: Second Wind off the ability menu, or FIGHT or
    FLEE off the main menu."""
    if action == FIGHT:
        g.battle_menu_goto(MENU_FIGHT); g.press("a", wait=12); g.press("a", wait=1)
    elif action == FLEE:
        g.battle_menu_goto(MENU_FLEE); g.press("a", wait=1)
    else:
        cast(g, SECOND_WIND_ROW, wait=1)


g, _ = start_on(8, class_id=FIGHTER, level=LEVEL, abilities=0x3F, tag="t47")
started = reenter_floor(g, 8, GOBLIN[0] + 1, GOBLIN[1])
if started:
    g.step("LEFT")
    read_textbox(g)
    started = g.wait_for(lambda: at_menu(g), 1800)
chk("T47 the gauntlet goblin's fight starts", started, f"gs={g.gs()} pos={g.pos()}")
state = io.BytesIO(); g.pb.save_state(state)

for case, setup, action, words, sound in CASES:
    seen, trial = None, None
    for trial, seed in enumerate(SEEDS if started else []):
        state.seek(0); g.pb.load_state(state)
        g.wr16(SEED, seed)
        keep_alive(g)
        g.wr16(MON0 + M_HP, 60000); g.wr16(MON0 + M_TARGET_HP, 60000)
        setup(g)
        act(g, action)
        seen = next(((pre, post, sfx) for pre, post, sfx in round_messages(g)
                     if words in pre or words == post), None)
        if seen:
            break
    if seen:
        pre, post, sfx = seen
        detail = f"seed {trial}: {pre!r} / {post!r} played {NAMES.get(sfx, hex(sfx))}"
    else:
        detail = f"never came up in {len(SEEDS)} seeds"
    chk(f"T47 {case} plays {NAMES[sound]}", seen and seen[2] == sound, detail)

g.close()
chk.summary()
