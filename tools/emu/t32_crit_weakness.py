"""T32 - a critical hit still doubles on a weakness, and still ignores resistance.

damage_monster() picks one line per hit: a crit, else a resisted hit, else a
weakness, else a plain hit. A crit still applies the weakness, or it deals 19
or 20 sixteenths of its base to a weak monster where a plain hit deals double.
A crit doubles on a weakness and ignores resistance, and a basic attack never
doubles on a weakness (issue #41).

Each trial fights floor 2's bugbear from one savestate and one battle seed, so
the monk rolls the same d16 three times: against no aspects, a weakness to
everything, and a resistance to everything. Only seeds whose roll is a crit
count, for Flurry and for the free basic attack.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "playtest"))
from lotd import *
from helpers import *
from starts import start_on

chk = Checker("t32_crit_weakness")
MONK, FLURRY = 2, 3                  # monk3, src/player.data.c
PRE, POST = SYM["battle_pre_message"], SYM["battle_post_message"]
SEED = SYM["__rand_seed"]
MON0 = SYM["encounter"] + 1
M_MAX_HP, M_HP, M_TARGET_HP, M_PARAMETER = 12, 14, 16, 58
M_IMMUNE, M_RESIST, M_VULN = 30, 31, 32
EVERYTHING = 0xFF
SEEDS = [0x2A61 + 0x1F37 * k & 0xFFFF for k in range(48)]
WANTED = 3                           # crit seeds per attack

def set_up(g, resist=0, vuln=0):
    """Full bars, a bugbear that can't die or roar, and the aspects under test."""
    for off in ("hp", "max_hp", "sp", "max_sp"):
        g.wr16(PL + POFF[off], 200)
    for off in (M_MAX_HP, M_HP, M_TARGET_HP):
        g.wr16(MON0 + off, 60000)
    g.wr8(MON0 + M_PARAMETER, 0)
    g.wr8(MON0 + M_IMMUNE, 0)
    g.wr8(MON0 + M_RESIST, resist)
    g.wr8(MON0 + M_VULN, vuln)


def strike(g, flurry):
    """Flurry or the free basic attack. Returns its damage line, or None on a miss."""
    g.wr8(PRE, 0)
    g.wr8(POST, 0)
    if flurry:
        if not cast(g, FLURRY):
            return None
        mine = "flurry"
    else:
        g.battle_menu_goto(0); g.press("a", wait=12); g.press("a", wait=12)
        mine = "fists"
    if not g.wait_for(lambda: mine in cstr(g, PRE) and cstr(g, POST), 600):
        return None
    line = cstr(g, POST)
    return line if "damage" in line else None


def damage(line):
    for tok in (line or "").replace("!", " ").split():
        if tok.isdigit():
            return int(tok)
    return None


g, _ = start_on(2, class_id=MONK, level=30, abilities=0x3F, tag="t32_crit")
# NPC_1, the bugbear elite, stands at (3,5) (src/floor2.c).
g.teleport(3, 6, "UP"); g.tick(4)
g.interact()
chk("T32 the monk reaches the bugbear fight", g.wait_for(lambda: at_menu(g), 1800),
    f"gs={g.gs()}")
save_checkpoint(g, "t32_menu.state")

found = {True: [], False: []}
for flurry in (True, False):
    for seed in SEEDS:
        if len(found[flurry]) >= WANTED:
            break
        load_checkpoint(g, "t32_menu.state")
        g.wr16(SEED, seed)
        set_up(g)
        save_checkpoint(g, "t32_trial.state")
        plain = strike(g, flurry)
        if not plain or not plain.startswith("CRITICAL"):
            continue
        lines = [plain]
        for aspects in ({"vuln": EVERYTHING}, {"resist": EVERYTHING}):
            load_checkpoint(g, "t32_trial.state")
            set_up(g, **aspects)
            lines.append(strike(g, flurry))
        found[flurry].append((seed, *lines))
g.close()

fl, fight = found[True], found[False]
print("Flurry crits (seed, plain, weak, resistant):", fl)
print("basic-attack crits (seed, plain, weak, resistant):", fight)
chk("T32 the seeds give Flurry a critical hit", fl, str(len(fl)))
chk("T32 the seeds give the basic attack a critical hit", fight, str(len(fight)))
chk("T32 a Flurry crit on a weak monster still reads CRITICAL HIT",
    fl and all(w and w.startswith("CRITICAL") for _, _, w, _ in fl), str(fl))
chk("T32 and deals double the same crit on a monster with no weakness",
    fl and all(damage(w) == 2 * damage(p) for _, p, w, _ in fl), str(fl))
chk("T32 a Flurry crit still ignores resistance",
    fl and all(damage(r) == damage(p) for _, p, _, r in fl), str(fl))
chk("T32 a basic-attack crit on a weak monster is not doubled (issue #41)",
    fight and all(damage(w) == damage(p) for _, p, w, _ in fight), str(fight))
chk.summary()
