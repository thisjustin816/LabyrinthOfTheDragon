"""T15 - fleeing: the odds follow the AGL gap, and a pack that can't chase can't stop you.

roll_flee() lets the hero get away half the time, plus 1 in 16 for each point
of AGL over the fastest monster still able to chase, and never less than 1 in 8
or more than 7 in 8. A blinded or frightened monster can't chase, and with none
left the hero always gets away.

Each case fights floor 1's first random encounter from one savestate over
battle seeds, with every monster's AGL set against the hero's. The bands are
wide enough for the seeds' luck and narrow enough to tell the rule apart from a
coin flip, a sure escape, and no chance at all. A gap of 3 each way lands
between the clamps, at 176 and 80 in 256 (about 0.69 and 0.31), and gets more
seeds, since its bands have to exclude both a coin flip and the clamps.

Offsets from LabyrinthOfTheDragon.cdb: Encounter.monsters at +1,
sizeof(Monster) = 64, active +5, agl_base +28, agl +29, status_effects +34
(5 bytes each: active, effect, flag, duration, tier).

agl is recomputed from agl_base at the top of every round and debuffs is
rebuilt only on that monster's own turn, so the test writes the durable
fields: agl_base and a real perpetual effect.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "playtest"))
from lotd import *
from helpers import *

chk = Checker("t15_flee")
POST = SYM["battle_post_message"]
SEED = SYM["__rand_seed"]
MON0, MSIZE = SYM["encounter"] + 1, 64
ACTIVE, AGL_BASE, AGL, EFFECTS = 5, 28, 29, 34
EFFECT_SIZE, PERPETUAL = 5, 0xFF
BLIND = (0, 0x01)                    # DEBUFF_BLIND, FLAG_DEBUFF_BLIND (src/stats.h)
SCARED = (1, 0x02)                   # DEBUFF_SCARED, FLAG_DEBUFF_SCARED
MENU_FLEE = 3
SEEDS = [0x0B5D + 0x3A17 * k & 0xFFFF for k in range(40)]
MORE_SEEDS = [0x0B5D + 0x3A17 * k & 0xFFFF for k in range(160)]
FLED, BLOCKED = "And get away!", "But are blocked!"     # battle.player_flee_*, assets/strings.js

# (label, hero AGL, every monster's AGL, effect on every monster, seeds, check on the escape rate)
CASES = [
    ("8 AGL slower", 20, 28, None, SEEDS, lambda r: r <= 0.25),
    ("12 AGL slower", 20, 32, None, SEEDS, lambda r: 0 < r <= 0.25),
    ("3 AGL slower", 20, 23, None, MORE_SEEDS, lambda r: 0.20 <= r <= 0.42),
    ("even", 20, 20, None, SEEDS, lambda r: 0.3 <= r <= 0.7),
    ("3 AGL faster", 20, 17, None, MORE_SEEDS, lambda r: 0.58 <= r <= 0.80),
    ("8 AGL faster", 20, 12, None, SEEDS, lambda r: r >= 0.72),
    ("12 AGL faster", 20, 8, None, SEEDS, lambda r: 0.7 <= r < 1),
    ("slow, past a fast blinded pack", 3, 100, BLIND, SEEDS, lambda r: r == 1),
    ("slow, past a frightened pack", 3, 0, SCARED, SEEDS, lambda r: r == 1),
]
WHAT = {
    "8 AGL slower": "held to 1 in 8, well short of a coin flip",
    "12 AGL slower": "held to 1 in 8, never zero",
    "3 AGL slower": "80 in 256, short of a coin flip and above the 1 in 8 floor",
    "even": "a coin flip",
    "3 AGL faster": "176 in 256, past a coin flip and below the 7 in 8 ceiling",
    "8 AGL faster": "held to 7 in 8, well past a coin flip",
    "12 AGL faster": "held to 7 in 8, never certain",
    "slow, past a fast blinded pack": "certain: nothing can chase",
    "slow, past a frightened pack": "certain: nothing can chase",
}

def set_up(g, hero_agl, monster_agl, effect):
    g.wr8(PL + POFF["agl"], hero_agl)
    g.wr8(PL + POFF["agl_base"], hero_agl)
    g.wr16(PL + POFF["hp"], 99)
    for k in range(3):
        b = MON0 + k * MSIZE
        if not g.rd8(b + ACTIVE):
            continue
        g.wr8(b + AGL_BASE, monster_agl)
        g.wr8(b + AGL, monster_agl)
        e = b + EFFECTS
        for i in range(4 * EFFECT_SIZE):
            g.wr8(e + i, 0)
        if effect:
            g.wr8(e + 0, 1)
            g.wr8(e + 1, effect[0])
            g.wr8(e + 2, effect[1])
            g.wr8(e + 3, PERPETUAL)
            g.wr8(e + 4, 3)
    for i in range(24):
        g.wr8(POST + i, 0)


def flee(g):
    """Try to flee and read the outcome: True, False, or None when no flee line
    came (a monster took the hero's turn away first). Faster monsters act before
    the hero, so the line can wait behind three of their turns."""
    g.battle_menu_goto(MENU_FLEE)
    g.press("a", wait=14)
    for _ in range(900):
        g.tick(2)
        line = cstr(g, POST)
        if line == FLED:
            return True
        if line == BLOCKED:
            return False
        if g.gs() != GS["BATTLE"]:
            return None
    return None


g = Game(tag="t15")
g.boot_to_save_select(); g.save_select_pick(0); g.hero_select_pick(0); g.tick(20)
g.walk_until_battle()
chk("T15 a random encounter starts", g.wait_for(lambda: at_menu(g), 1500), f"gs={g.gs()}")
g.tick(10)
save_checkpoint(g, "t15_menu.state")

for label, hero_agl, monster_agl, effect, seeds, ok in CASES:
    got = []
    for seed in seeds:
        load_checkpoint(g, "t15_menu.state")
        g.wr16(SEED, seed)
        set_up(g, hero_agl, monster_agl, effect)
        out = flee(g)
        if out is not None:
            got.append(out)
    rate = sum(got) / len(got) if got else -1
    print(f"{label}: escaped {sum(got)} of {len(got)} ({len(seeds) - len(got)} without a flee line)")
    chk(f"T15 {label}: the escape is {WHAT[label]}", len(got) >= len(seeds) * 3 // 4 and ok(rate),
        f"escaped {sum(got)} of {len(got)}")
g.close()
chk.summary()
