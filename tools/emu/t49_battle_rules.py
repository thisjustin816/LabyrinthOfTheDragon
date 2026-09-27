"""T49 - battle rules: a poison death gets its own line, a confused hero's blow
on themselves shakes the screen like any hit, Wild Magic never revives a
monster its own fireball felled, a queued Still Mind goes through fear, and
the hero's stats follow their status effects: blindness zeroes ATK whatever
slot an ATK Down sits in, a cure puts the stats back within its own round, and
nothing a fight left carries into the next one.

Each hero case sets a status on the hero, a fighter or a monk, in the savestate
of floor 8's gauntlet goblin fight, and replays the round across battle seeds
until the line in question comes up, or reads the stats once the round is
over. The goblin moves last, so the hero's own turn comes first. The Wild Magic
case casts it in a floor 1 random fight of two or three monsters, all at 1 HP,
across seeds: whenever a surge sends a fireball, every monster stays down, even
one whose own roll came up as an HP change. The carry-over case wins a floor 1
fight with a DEF up and an AGL down on the hero, then reads the stats and flags
at the next fight's first menu.

Offsets from LabyrinthOfTheDragon.cdb: Encounter.monsters at +1, sizeof(Monster)
= 64, active +5, hp +14, target_hp +16, atk +21, agl_base +28, agl +29,
status_effects +34, and Encounter.player_status_effects at +209. A status effect is 5 bytes: active,
effect, flag, duration, tier.
"""
import io, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "playtest"))
from lotd import *
from helpers import *
from starts import start_on
import drive

chk = Checker("t49_battle_rules")
FIGHTER, MONK, LEVEL = 1, 2, 48
STILL_MIND = 2                                 # monk2, src/player.data.c
REMEDY = drive.ITEM["REMEDY"]
SEED = SYM["__rand_seed"]
SEEDS = [0x2C41 + 0x3B7F * k & 0xFFFF for k in range(48)]
MON0, M_SIZE = SYM["encounter"] + 1, 64
M_ACTIVE, M_HP, M_TARGET_HP, M_ATK, M_AGL_BASE, M_AGL, M_EFFECTS = 5, 14, 16, 21, 28, 29, 34
P_EFFECTS = SYM["encounter"] + 209
BLIND, SCARED, POISONED, CONFUSED = (0, 0x01), (1, 0x02), (3, 0x08), (4, 0x10)   # src/stats.h
AGL_DOWN, ATK_DOWN, DEF_DOWN = (5, 0x20), (6, 0x40), (7, 0x80)
ATK_UP, DEF_UP = (14, 0x40), (15, 0x80)
S_TIER, PERPETUAL = 3, 0xFF
GOBLIN = (2, 27)                               # gauntlet fight tile, src/floor8.c
DIRS = ("UP", "DOWN", "LEFT", "RIGHT")


def put_effect(g, effects, slot, status):
    effect, flag = status
    for off, value in enumerate((1, effect, flag, PERPETUAL, S_TIER)):
        g.wr8(effects + 5 * slot + off, value)


def hero_effect(g, slot, status):
    put_effect(g, P_EFFECTS, slot, status)


def hero(g, stat):
    return g.rd8(PL + POFF[stat])


def fight(g):
    g.battle_menu_goto(0); g.press("a", wait=12); g.press("a", wait=1)


def play(g, state, seed, setup, act=fight, read=None):
    """The round from `state` on battle seed `seed`, `setup` applied first and
    the goblin out of reach of any blow: every line it showed, with read(g) at
    each. The round is over when it returns."""
    state.seek(0); g.pb.load_state(state)
    g.wr16(SEED, seed)
    keep_alive(g)
    g.wr16(MON0 + M_HP, 60000); g.wr16(MON0 + M_TARGET_HP, 60000)
    g.wr8(MON0 + M_AGL_BASE, 0); g.wr8(MON0 + M_AGL, 0)
    setup(g)
    act(g)
    return round_messages(g, read)


def replay(g, state, setup, words, read=None):
    """Replay the round from `state` across seeds until a line carrying
    `words` comes up. Returns (pre, post, read value when it came up, game
    state after the round), or None."""
    for seed in SEEDS:
        for pre, post, value in play(g, state, seed, setup, read=read):
            if words in pre:
                return pre, post, value, g.gs()
    return None


def gauntlet_goblin(class_id, tag, items=None):
    """A hero of `class_id` in the gauntlet goblin's fight, and its savestate."""
    g, _ = start_on(8, class_id=class_id, level=LEVEL, abilities=0x3F, items=items, tag=tag)
    started = reenter_floor(g, 8, GOBLIN[0] + 1, GOBLIN[1])
    if started:
        g.step("LEFT"); read_textbox(g)
        started = g.wait_for(lambda: at_menu(g), 1800)
    state = io.BytesIO(); g.pb.save_state(state)
    return g, started, state


g, started, state = gauntlet_goblin(FIGHTER, "t49", items={"REMEDY": 4})
chk("T49 the gauntlet goblin's fight starts", started, f"gs={g.gs()} pos={g.pos()}")


def dying_of_poison(g):
    hero_effect(g, 0, POISONED)
    g.wr16(SYM["player"] + POFF["hp"], 1)


seen = replay(g, state, dying_of_poison, "succumb") if started else None
chk("T49 a hero killed by poison on their own turn reads \"You succumb to the poison!\"",
    seen and seen[0] == "You succumb to the poison!", f"line={seen and seen[0]!r}")
chk("T49 and the battle ends in their death", seen and seen[3] != GS["BATTLE"],
    f"gs after={seen and seen[3]}")

seen = replay(g, state, lambda g: hero_effect(g, 0, CONFUSED), "damage to yourself",
              read=lambda g: g.rd8(SYM["player_was_hit"])) if started else None
chk("T49 a confused hero's blow on themselves shakes the screen", seen and seen[2] == 1,
    f"line={seen and seen[0]!r} player_was_hit={seen and seen[2]}")


def blind_and_weakened(g):
    for effects in (P_EFFECTS, MON0 + M_EFFECTS):
        put_effect(g, effects, 0, BLIND)
        put_effect(g, effects, 1, ATK_DOWN)


if started:
    play(g, state, SEEDS[0], blind_and_weakened)
chk("T49 blindness zeroes the hero's ATK with an ATK Down in a later slot",
    started and hero(g, "atk") == 0, f"atk={hero(g, 'atk')} base={hero(g, 'atk_base')}")
chk("T49 and the goblin's", started and g.rd8(MON0 + M_ATK) == 0, f"atk={g.rd8(MON0 + M_ATK)}")


def lowered_and_raised(g):
    hero_effect(g, 0, DEF_DOWN)
    hero_effect(g, 1, ATK_UP)


used = started and bool(play(g, state, SEEDS[0], lowered_and_raised,
                             act=lambda g: drive.use_battle_item(g, REMEDY)))
chk("T49 the hero drinks a Remedy against a DEF down", used and drive.item_qty(g, REMEDY) == 3,
    f"qty={drive.item_qty(g, REMEDY)}")
chk("T49 the Remedy puts DEF back within its own round, before the hero's next turn",
    used and hero(g, "def_") == hero(g, "def_base"),
    f"def={hero(g, 'def_')} base={hero(g, 'def_base')}")
chk("T49 and leaves the ATK up in place", used and hero(g, "atk") > hero(g, "atk_base"),
    f"atk={hero(g, 'atk')} base={hero(g, 'atk_base')}")
g.close()

g, started, state = gauntlet_goblin(MONK, "t49_monk")
chk("T49 the monk's gauntlet goblin fight starts", started, f"gs={g.gs()} pos={g.pos()}")
lines = play(g, state, SEEDS[0], lowered_and_raised,
             act=lambda g: cast(g, STILL_MIND, wait=1)) if started else []
cast_it = any("You become one" in pre for pre, _, _ in lines)
chk("T49 the monk casts Still Mind against a DEF down", cast_it, str([pre for pre, _, _ in lines]))
chk("T49 Still Mind puts DEF back within its own round",
    cast_it and hero(g, "def_") == hero(g, "def_base"),
    f"def={hero(g, 'def_')} base={hero(g, 'def_base')}")
chk("T49 and leaves the ATK up in place", cast_it and hero(g, "atk") > hero(g, "atk_base"),
    f"atk={hero(g, 'atk')} base={hero(g, 'atk_base')}")

blocked = []
for seed in SEEDS[:24] if started else []:
    lines = play(g, state, seed, lambda g: hero_effect(g, 0, SCARED),
                 act=lambda g: cast(g, STILL_MIND, wait=1))
    if not any("You become one" in pre for pre, _, _ in lines):
        blocked.append((seed, [pre for pre, _, _ in lines][:2]))
chk("T49 a strong fear never stops a queued Still Mind, as paralysis and confusion don't",
    started and not blocked, f"{len(blocked)} of 24 rounds lost to the fear: {blocked[:3]}")
g.close()

# --- what one fight leaves on the hero ----------------------------------------
g, _ = start_on(1, class_id=FIGHTER, level=10, tag="t49_carry")
started = g.walk_until_battle(DIRS, max_steps=400) and g.wait_for(lambda: at_menu(g), 1800)
chk("T49 a random fight starts on floor 1 for the carry-over case", started,
    f"gs={g.gs()} pos={g.pos()}")
if started:
    hero_effect(g, 0, DEF_UP)
    hero_effect(g, 1, AGL_DOWN)
    while g.gs() == GS["BATTLE"]:
        keep_alive(g)
        for s in range(3):
            g.wr16(MON0 + M_SIZE * s + M_TARGET_HP, 1)
        fight(g) if at_menu(g) else round_messages(g)
    g.wait_map_idle(600)
left = (hero(g, "def_") > hero(g, "def_base"), hero(g, "agl") < hero(g, "agl_base"))
chk("T49 the fight ends with the hero's DEF up and AGL down", started and left == (True, True),
    f"def={hero(g, 'def_')}/{hero(g, 'def_base')} agl={hero(g, 'agl')}/{hero(g, 'agl_base')}")
started = started and g.walk_until_battle(DIRS, max_steps=400) and \
    g.wait_for(lambda: at_menu(g), 1800)
chk("T49 the next random fight starts", started, f"gs={g.gs()} pos={g.pos()}")
now = tuple(hero(g, stat) for stat in ("def_", "agl", "buffs", "debuffs"))
chk("T49 the next fight's first menu finds the stats at their bases and no effect flags",
    started and now == (hero(g, "def_base"), hero(g, "agl_base"), 0, 0),
    f"def, agl, buffs, debuffs = {now}, bases {hero(g, 'def_base')}, {hero(g, 'agl_base')}")
g.close()

# --- Wild Magic's fireball and a later HP roll --------------------------------
SORCERER, WILD_MAGIC = 3, 5                    # sorcerer5, src/player.data.c
g, _ = start_on(1, class_id=SORCERER, level=10, abilities=0x3F, tag="t49_wild")
started = False
for _ in range(12):
    if not g.walk_until_battle(DIRS, max_steps=400):
        break
    if not g.wait_for(lambda: at_menu(g), 1800):
        break
    if len([s for s in range(3) if g.rd8(MON0 + M_SIZE * s + M_ACTIVE)]) >= 2:
        started = True
        break
    while g.gs() == GS["BATTLE"]:              # a lone monster: fight it off, walk on
        keep_alive(g)
        for s in range(3):
            g.wr16(MON0 + M_SIZE * s + M_TARGET_HP, 1)
        fight(g) if at_menu(g) else round_messages(g)
    g.wait_map_idle(600)
chk("T49 a random fight with two or more monsters starts on floor 1", started,
    f"gs={g.gs()} pos={g.pos()}")
state = io.BytesIO(); g.pb.save_state(state)
fireballs, revived = 0, []
for seed in [0x1D05 + 0x2F4B * k & 0xFFFF for k in range(160)] if started else []:
    state.seek(0); g.pb.load_state(state)
    g.wr16(SEED, seed)
    keep_alive(g)
    slots = [s for s in range(3) if g.rd8(MON0 + M_SIZE * s + M_ACTIVE)]
    for s in slots:
        g.wr16(MON0 + M_SIZE * s + M_HP, 1); g.wr16(MON0 + M_SIZE * s + M_TARGET_HP, 1)
    cast(g, WILD_MAGIC, wait=1)
    lines = round_messages(g)
    if not any("storm of magic" in pre and "fireball" in post for pre, post, _ in lines):
        continue
    fireballs += 1
    alive = [s for s in slots if g.gs() == GS["BATTLE"]
             and g.rd8(MON0 + M_SIZE * s + M_ACTIVE) and g.rd16(MON0 + M_SIZE * s + M_TARGET_HP)]
    if alive:
        revived.append((seed, alive))
chk("T49 Wild Magic sent a fireball in some of the rounds", fireballs > 0, f"{fireballs} fireballs")
chk("T49 every monster a surge's fireball felled stays down", fireballs and not revived,
    f"{len(revived)} of {fireballs} fireball rounds left a monster standing: {revived[:4]}")
g.close()
chk.summary()
