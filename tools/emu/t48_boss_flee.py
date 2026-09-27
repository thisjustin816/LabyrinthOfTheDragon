"""T48 - a boss can't run away, while a wandering monster still can.

A fight is won once every monster is gone, so a boss, an elite, or a gauntlet
fight that fled would open its door as if beaten. Those fights clear can_flee,
and monster_flee() fails the attempt for a monster that can't flee. The checks
frighten floor 8's gauntlet goblin and the dragon with a strong fear and replay
the round across battle seeds: each time one makes a run for it, the line says
it can't get away and the fight goes on. A frightened monster from one of floor
1's random fights still gets away.

Offsets from LabyrinthOfTheDragon.cdb: Encounter.monsters at +1, sizeof(Monster)
= 64, active +5, hp +14, target_hp +16, status_effects +34 (5 bytes each:
active, effect, flag, duration, tier), fled +57.
"""
import io, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "playtest"))
from lotd import *
from helpers import *
from starts import start_on
import dragon as D

chk = Checker("t48_boss_flee")
FIGHTER, MONK = 1, 2
SECOND_WIND = 0                                # fighter1, src/player.data.c
SEED = SYM["__rand_seed"]
SEEDS = [0x2C41 + 0x3B7F * k & 0xFFFF for k in range(24)]
MON0, M_SIZE = SYM["encounter"] + 1, 64
M_ACTIVE, M_HP, M_TARGET_HP, M_EFFECTS, M_FLED = 5, 14, 16, 34, 57
SCARED, S_TIER, PERPETUAL = (1, 0x02), 3, 0xFF   # DEBUFF_SCARED, FLAG_DEBUFF_SCARED
GOBLIN = (2, 27)                               # gauntlet fight tile, src/floor8.c
RUNS, CAUGHT, GONE = "makes a run for it", "But they cannot get away!", "And they get away!"


def frighten(g, slot):
    for off, value in enumerate((1, SCARED[0], SCARED[1], PERPETUAL, S_TIER)):
        g.wr8(MON0 + M_SIZE * slot + M_EFFECTS + off, value)


def active_slots(g):
    return [s for s in range(3) if g.rd8(MON0 + M_SIZE * s + M_ACTIVE)]


def flights(g, state, act, slots, hp=None, stop_at=None):
    """Replay the round from `state` across seeds with every monster in `slots`
    frightened, and collect what happened each time one made a run for it:
    (the flee's post line, the fled flags after the round, whether the battle
    went on). Stops early at the first flee whose post line is `stop_at`."""
    seen = []
    for seed in SEEDS:
        state.seek(0); g.pb.load_state(state)
        g.wr16(SEED, seed)
        keep_alive(g)
        for s in slots:
            frighten(g, s)
            if hp is not None:
                g.wr16(MON0 + M_SIZE * s + M_HP, hp); g.wr16(MON0 + M_SIZE * s + M_TARGET_HP, hp)
        act(g)
        post = next((p for pre, p, _ in round_messages(g) if RUNS in pre), None)
        if post is None:
            continue
        fled = [g.rd8(MON0 + M_SIZE * s + M_FLED) for s in slots]
        seen.append((post, fled, g.gs() == GS["BATTLE"]))
        if post == stop_at:
            break
    return seen


def boss_checks(name, seen):
    chk(f"T48 the frightened {name} makes a run for it", seen,
        f"{len(seen)} runs in {len(SEEDS)} seeds")
    chk(f"T48 the {name} never gets away",
        seen and all(post == CAUGHT and fled == [0] for post, fled, _ in seen),
        f"{len(seen)} runs: {sorted(set(post for post, _, _ in seen))}")
    chk(f"T48 the {name}'s fight goes on each time",
        seen and all(going for _, _, going in seen), f"{len(seen)} runs")


def second_wind(g):
    cast(g, SECOND_WIND, wait=1)


def fight(g):
    g.battle_menu_goto(0); g.press("a", wait=12); g.press("a", wait=1)


# --- floor 8's gauntlet goblin ------------------------------------------------
g, _ = start_on(8, class_id=FIGHTER, level=48, abilities=0x3F, tag="t48_gauntlet")
started = reenter_floor(g, 8, GOBLIN[0] + 1, GOBLIN[1])
if started:
    g.step("LEFT"); read_textbox(g)
    started = g.wait_for(lambda: at_menu(g), 1800)
chk("T48 the gauntlet goblin's fight starts", started, f"gs={g.gs()} pos={g.pos()}")
state = io.BytesIO(); g.pb.save_state(state)
boss_checks("gauntlet goblin", flights(g, state, second_wind, [0], hp=60000) if started else [])
g.close()

# --- the dragon ---------------------------------------------------------------
g = D.built(MONK, 47, None, "t48_dragon")
D.engage(g, "t48 dragon")
started = g.wait_for(lambda: at_menu(g), 600)
chk("T48 the dragon's fight starts", started, f"gs={g.gs()}")
state = io.BytesIO(); g.pb.save_state(state)
boss_checks("dragon", flights(g, state, fight, [0], hp=g.rd16(D.DRAGON_MAX)) if started else [])
g.close()

# --- a wandering monster on floor 1 -------------------------------------------
g, _ = start_on(1, class_id=FIGHTER, level=10, abilities=0x3F, tag="t48_random")
started = g.walk_until_battle(("UP", "DOWN", "LEFT", "RIGHT"), max_steps=400) and \
    g.wait_for(lambda: at_menu(g), 1800)
chk("T48 a random fight starts on floor 1", started, f"gs={g.gs()} pos={g.pos()}")
state = io.BytesIO(); g.pb.save_state(state)
slots = active_slots(g) if started else []
seen = flights(g, state, second_wind, slots, hp=60000, stop_at=GONE) if started else []
chk("T48 a frightened wandering monster can still get away",
    any(post == GONE and any(fled) for post, fled, _ in seen),
    f"{len(seen)} runs: {sorted(set(post for post, _, _ in seen))}")
g.close()

chk.summary()
