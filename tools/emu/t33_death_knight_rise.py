"""T33 - a death knight can rise from any killing blow the hero lands.

A death knight gets one chance per fight, 3 in 16, to rise at a quarter of its
HP from a killing blow. Quivering Palm and Disintegrate set the knight's HP to
0 directly, and the area attacks run their own damage loops, so the roll
lives in fell_monster(), which every kill goes through, and the rise's line
shows even after an area attack that skips its own.

Each case fights floor 8's death knight from one savestate and tries battle
seeds until the knight rises. At level 81 Quivering Palm kills outright 3 times
in 8 and Disintegrate 4 in 8, and their ordinary damage goes through
damage_monster(), so the knight gets 60000 HP that only an outright kill can
take. Fireball and Cleave get a knight left at 1 HP. Flurry against 1 HP is the
control, a single-target kill through damage_monster().
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "playtest"))
from lotd import *
from helpers import *
from knight import start_fight

chk = Checker("t33_death_knight_rise")
FIGHTER, MONK, SORCERER = 1, 2, 3
PRE, POST = SYM["battle_pre_message"], SYM["battle_post_message"]
SEED = SYM["__rand_seed"]
MON0 = SYM["encounter"] + 1
M_MAX_HP, M_HP, M_TARGET_HP = 12, 14, 16
M_DEF_BASE, M_DEF, M_MDEF_BASE, M_MDEF, M_PARAMETER = 22, 23, 26, 27, 58
REVIVE_USED = 1 << 1                 # DEATH_KNIGHT_REVIVE_USED, src/monster.h
SEEDS = [0x1357 + 0x2B7D * k & 0xFFFF for k in range(120)]
OUTRIGHT_ONLY = 60000                # more HP than either ability's damage branch deals

# (label, class, ability row, a word from its opening line, the knight's HP)
CASES = [
    ("Quivering Palm", MONK, 5, "essence", OUTRIGHT_ONLY),
    ("Disintegrate", SORCERER, 4, "DEATH", OUTRIGHT_ONLY),
    ("Fireball", SORCERER, 1, "EXPLOSION", 1),
    ("Cleave", FIGHTER, 2, "cleave", 1),
    ("Flurry, the control", MONK, 3, "flurry", 1),
]

def set_up(g, knight_hp):
    """Full bars, and a knight every attack connects with, at `knight_hp`."""
    for off in ("hp", "max_hp", "sp", "max_sp"):
        g.wr16(PL + POFF[off], 999)
    for off in (M_DEF_BASE, M_DEF, M_MDEF_BASE, M_MDEF):
        g.wr8(MON0 + off, 0)
    if knight_hp > g.rd16(MON0 + M_MAX_HP):
        g.wr16(MON0 + M_MAX_HP, knight_hp)
    g.wr16(MON0 + M_HP, knight_hp)
    g.wr16(MON0 + M_TARGET_HP, knight_hp)


def attack(g, row, mine):
    """Cast `row` and read what it left: (line, target_hp, max_hp, parameter)."""
    g.wr8(PRE, 0)
    g.wr8(POST, 0)
    if not cast(g, row):
        return None
    if not g.wait_for(lambda: mine in cstr(g, PRE), 600):
        return None
    g.tick(2)
    return (cstr(g, POST), g.rd16(MON0 + M_TARGET_HP), g.rd16(MON0 + M_MAX_HP),
            g.rd8(MON0 + M_PARAMETER))


for label, cls, row, mine, knight_hp in CASES:
    g, ok = start_fight(cls, 81, f"t33_{cls}_{row}")
    chk(f"T33 {label}: the fight with floor 8's death knight starts", ok,
        f"gs={g.gs()} ms={g.ms()} pos={g.pos()}")
    save_checkpoint(g, "t33_menu.state")
    kills, rise = 0, None
    for seed in SEEDS:
        load_checkpoint(g, "t33_menu.state")
        g.wr16(SEED, seed)
        set_up(g, knight_hp)
        out = attack(g, row, mine)
        if out is None:
            continue
        line, target_hp, max_hp, parameter = out
        if target_hp == 0 or "revives" in line:
            kills += 1
        if "revives" in line:
            rise = out
            break
    g.close()
    print(f"{label}: kills={kills} rise={rise}")
    chk(f"T33 {label}: kills the knight", kills >= 1, str(kills))
    chk(f"T33 {label}: a kill lets the knight rise", rise is not None, f"kills={kills}")
    if rise:
        line, target_hp, max_hp, parameter = rise
        chk(f"T33 {label}: it rises at a quarter of its HP, with its rise spent",
            target_hp == max_hp // 4 and parameter & REVIVE_USED,
            f"target_hp={target_hp} max_hp={max_hp} parameter={parameter:#04x}")
chk.summary()
