"""T40 - the dragon and the gelatinous cube can't be knocked down.

A monster that is knocked down loses every turn until it is up, so a fighter
who trips a boss again each time it stands keeps it down for the whole fight.
The dragon and the cube set SPECIAL_TRIP in special_immune (src/player.h):
Trip Attack answers "They're completely immune!" without rolling to hit, and
Open Palm's blow still lands but never trips. The cube also keeps
SPECIAL_SLEET_STORM; the dragon does not, so Sleet Storm still makes it slip.

Each case fights from one savestate over battle seeds, as a level 60 hero with
every ability, against a monster with no DEF and more HP than any blow takes.
Floor 1's goblin boss sets neither flag and is the control: both abilities
have to knock it down, or a clean result for the other two proves nothing.
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "playtest"))
from lotd import *
from helpers import *
from starts import start_on
import dragon

chk = Checker("t40_trip_immune")
FIGHTER, MONK = 1, 2
TRIP_ATTACK, OPEN_PALM = 3, 1                # ability rows, src/player.data.c
PRE, POST = SYM["battle_pre_message"], SYM["battle_post_message"]
SEED = SYM["__rand_seed"]
MON0 = SYM["encounter"] + 1
M_MAX_HP, M_HP, M_TARGET_HP = 12, 14, 16
M_DEF_BASE, M_DEF, M_MDEF_BASE, M_MDEF = 22, 23, 26, 27
M_TRIP, M_SPECIAL_IMMUNE = 59, 60
SPECIAL_SLEET_STORM, SPECIAL_TRIP, SPECIAL_INSTANT_KILL = 1 << 3, 1 << 4, 1 << 7
SEEDS = [0x1357 + 0x2B3D * k & 0xFFFF for k in range(16)]
STURDY = 60000


def boss_fight(floor, npc):
    def start(cls, tag):
        g, _ = start_on(floor, class_id=cls, level=60, abilities=0x3F, tag=tag)
        g.teleport(npc[0], npc[1] + 1, "UP")
        g.interact()
        g.wait_for(lambda: at_menu(g), 1200)
        return g
    return start


def dragon_fight(cls, tag):
    g = dragon.built(cls, 60, None, tag)
    dragon.engage(g, tag)
    g.wait_for(lambda: at_menu(g), 1200)
    return g


# (monster, how to reach its fight, knocked down?, special_immune bits it has, bits it lacks)
CASES = [
    ("the goblin", boss_fight(1, (12, 5)), True, 0, SPECIAL_TRIP | SPECIAL_SLEET_STORM),
    ("the cube", boss_fight(3, (4, 14)), False, SPECIAL_TRIP | SPECIAL_SLEET_STORM, 0),
    ("the dragon", dragon_fight, False, SPECIAL_TRIP | SPECIAL_INSTANT_KILL, SPECIAL_SLEET_STORM),
]
# (hero, ability row, a word from its opening line, its name)
BLOWS = [(FIGHTER, TRIP_ATTACK, "legs", "Trip Attack"),
         (MONK, OPEN_PALM, "open palm", "Open Palm")]


def trials(g, row, word, name):
    """Cast `row` from the menu savestate once per seed. Returns (casts,
    knockdowns, blows that took HP, the result lines seen)."""
    save_checkpoint(g, f"{name}.state")
    casts, downs, landed, lines = 0, 0, 0, set()
    for seed in SEEDS:
        load_checkpoint(g, f"{name}.state")
        g.wr16(SEED, seed)
        for off in ("hp", "max_hp", "sp", "max_sp"):
            g.wr16(PL + POFF[off], 999)
        for off in (M_DEF_BASE, M_DEF, M_MDEF_BASE, M_MDEF):
            g.wr8(MON0 + off, 0)
        for off in (M_MAX_HP, M_HP, M_TARGET_HP):
            g.wr16(MON0 + off, STURDY)
        g.wr8(PRE, 0)
        g.wr8(POST, 0)
        if not cast(g, row) or not g.wait_for(lambda: word in cstr(g, PRE).lower(), 600):
            continue
        g.tick(2)
        casts += 1
        downs += g.rd8(MON0 + M_TRIP) > 0
        landed += g.rd16(MON0 + M_TARGET_HP) < STURDY
        lines.add(cstr(g, POST))
    return casts, downs, landed, lines


for label, start, knocked_down, has, lacks in CASES:
    for cls, row, word, ability in BLOWS:
        tag = f"t40_{cls}_{label.split()[-1]}"
        g = start(cls, tag)
        ok = at_menu(g)
        chk(f"T40 {ability} against {label}: the fight starts", ok,
            f"gs={g.gs()} ms={g.ms()} pos={g.pos()}")
        if not ok:
            g.close()
            continue
        if cls == FIGHTER:
            flags = g.rd8(MON0 + M_SPECIAL_IMMUNE)
            chk(f"T40 {label}'s special_immune is {has:#04x} among the knock-down and kill bits",
                flags & has == has and not flags & lacks, f"special_immune={flags:#04x}")
        casts, downs, landed, lines = trials(g, row, word, tag)
        g.close()
        print(f"{ability} against {label}: casts={casts} knockdowns={downs} landed={landed} lines={sorted(lines)}")
        if knocked_down:
            chk(f"T40 {ability} knocks down {label}", downs > 0, f"{downs} of {casts}")
            continue
        chk(f"T40 {ability} never knocks down {label}", casts > 0 and downs == 0,
            f"{downs} of {casts}")
        if row == TRIP_ATTACK:
            chk(f"T40 Trip Attack on {label} says it's immune and deals nothing",
                lines and all("immune" in line for line in lines) and landed == 0,
                f"lines={sorted(lines)} landed={landed}")
        else:
            chk(f"T40 Open Palm's blow still lands on {label}", landed > 0,
                f"{landed} of {casts}")
chk.summary()
