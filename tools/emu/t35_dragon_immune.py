"""T35 - the dragon can't be killed outright.

Quivering Palm and Disintegrate roll a kill that ignores the target's HP, and
skip it against a monster with SPECIAL_INSTANT_KILL in special_immune. The
dragon sets it, so neither can end the final fight on that one roll; a cast
that connects still deals its ordinary damage instead of wasting the turn.

Each case fights the dragon from one savestate over battle seeds, as a level 60
hero. The dragon gets 60000 HP, more than either ability's ordinary damage
deals, so a cast that empties it is an outright kill, and no DEF or MDEF, so
nearly every cast connects.
"""
import os, re, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "playtest"))
from lotd import *
from helpers import *
import dragon

chk = Checker("t35_dragon_immune")
MONK, SORCERER = 2, 3
PRE, POST = SYM["battle_pre_message"], SYM["battle_post_message"]
SEED = SYM["__rand_seed"]
MON0 = SYM["encounter"] + 1
M_MAX_HP, M_HP, M_TARGET_HP = 12, 14, 16
M_DEF_BASE, M_DEF, M_MDEF_BASE, M_MDEF, M_SPECIAL_IMMUNE = 22, 23, 26, 27, 60
SPECIAL_INSTANT_KILL = 1 << 7        # src/player.h
SEEDS = [0x2468 + 0x3C5B * k & 0xFFFF for k in range(40)]
OUTRIGHT_ONLY = 60000

# (label, class, ability row, a word from its opening line, a word from its kill line)
CASES = [
    ("Quivering Palm", MONK, 5, "essence", "end them"),
    ("Disintegrate", SORCERER, 4, "DEATH", "are no"),
]


def damage_of(line):
    """The number in a line's "N damage", or None."""
    m = re.search(r"(\d+) damage", line)
    return int(m.group(1)) if m else None

def start_fight(cls, tag):
    """A level 60 hero on floor 8, at the menu of the dragon fight."""
    g = dragon.built(cls, 60, None, tag)
    dragon.engage(g, tag)
    g.wait_for(lambda: at_menu(g), 1200)
    return g, at_menu(g)


def set_up(g):
    """Full bars, and a dragon every cast connects with and only a kill empties."""
    for off in ("hp", "max_hp", "sp", "max_sp"):
        g.wr16(PL + POFF[off], 999)
    for off in (M_DEF_BASE, M_DEF, M_MDEF_BASE, M_MDEF):
        g.wr8(MON0 + off, 0)
    for off in (M_MAX_HP, M_HP, M_TARGET_HP):
        g.wr16(MON0 + off, OUTRIGHT_ONLY)


def attack(g, row, mine):
    """Cast `row` and read what it left: (line, target_hp)."""
    g.wr8(PRE, 0)
    g.wr8(POST, 0)
    if not cast(g, row):
        return None
    if not g.wait_for(lambda: mine in cstr(g, PRE), 600):
        return None
    g.tick(2)
    return cstr(g, POST), g.rd16(MON0 + M_TARGET_HP)


for n, (label, cls, row, mine, kill_word) in enumerate(CASES):
    g, ok = start_fight(cls, f"t35_{cls}")
    chk(f"T35 {label}: the dragon fight starts", ok,
        f"gs={g.gs()} ms={g.ms()} pos={g.pos()}")
    if n == 0:
        immune = g.rd8(MON0 + M_SPECIAL_IMMUNE)
        chk("T35 the dragon is immune to outright kills",
            immune & SPECIAL_INSTANT_KILL, f"special_immune={immune:#04x}")
    save_checkpoint(g, "t35_menu.state")
    kills, hits, misses, damaged = 0, 0, 0, 0
    for seed in SEEDS:
        load_checkpoint(g, "t35_menu.state")
        g.wr16(SEED, seed)
        set_up(g)
        out = attack(g, row, mine)
        if out is None:
            continue
        line, target_hp = out
        if target_hp == 0 or kill_word in line:
            kills += 1
        elif target_hp == OUTRIGHT_ONLY:
            misses += 1
        else:
            hits += 1
            damaged += damage_of(line) == OUTRIGHT_ONLY - target_hp
    g.close()
    print(f"{label}: kills={kills} hits={hits} misses={misses} damage lines={damaged}")
    chk(f"T35 {label}: never kills the dragon outright", kills == 0 and hits + misses > 0,
        f"kills={kills} of {kills + hits + misses}")
    chk(f"T35 {label}: every cast that connects deals its damage and says how much",
        hits > 0 and damaged == hits, f"hits={hits} damage lines={damaged}")
chk.summary()
