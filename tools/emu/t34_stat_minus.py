"""T34 - a stat lowered for a roll stays itself instead of capping or wrapping.

Two monster rolls lower a stat first: the displacer beast's second tentacle
aims 7 below its ATK, and the will-o-wisp's terror rolls against 5 below the
hero's MDEF. Both use stat_minus(), which lowers a stat and stops at 0.
level_offset() is meant for levels: it caps at 99 and reads anything past 127
as negative, which it then raises to 1.

No stat gets past 127 in play, so each case forces one high and counts the
outcomes over battle seeds, with the wisp made to try its terror whenever it
doesn't drain. The monster hit table runs from 20% to 95%. A displacer beast
with ATK 150 against a hero with DEF 100 lands both tentacles about 9 times in
10, where aiming the second at ATK 1 would make that about 1 in 5. A wisp
against a hero with MDEF 140 lands its terror about 1 time in 5, where
rolling against MDEF 1 would make that about 19 in 20.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "playtest"))
from lotd import *
from helpers import *
from starts import start_on

chk = Checker("t34_stat_minus")
FIGHTER = 1
PRE, POST = SYM["battle_pre_message"], SYM["battle_post_message"]
SEED = SYM["__rand_seed"]
MON0 = SYM["encounter"] + 1
M_MAX_HP, M_HP, M_TARGET_HP, M_ATK_BASE, M_ATK, M_PARAMETER = 12, 14, 16, 20, 21, 58
ALWAYS = 8                           # a wisp tries its terror when d8() < parameter
SEEDS = [0x0B5D + 0x3A2F * k & 0xFFFF for k in range(60)]
WANTED = 20                          # outcomes to count per case

def start_fight(floor, level, tile, tag):
    """A fighter on `floor`, facing the monster at `tile` and starting its fight."""
    g, _ = start_on(floor, class_id=FIGHTER, level=level, abilities=0x3F, tag=tag)
    x, y = tile
    g.teleport(x, y + 1, "UP"); g.tick(4)
    g.interact()
    for _ in range(60):
        if at_menu(g):
            return g, True
        if g.ms() in (MS["TEXTBOX"], MS["TEXTBOX_OPEN"]):
            g.press("a", wait=20)
        g.tick(30)
    return g, at_menu(g)


def keep_up(g):
    """A hero and a monster that both outlast any round."""
    for off in ("hp", "max_hp"):
        g.wr16(PL + POFF[off], 999)
    for off in (M_MAX_HP, M_HP, M_TARGET_HP):
        g.wr16(MON0 + off, 60000)


def monster_line(g, mine):
    """Fight one round and return the monster's result line if its opening
    line contains `mine`, or None if it did something else."""
    g.wr8(PRE, 0)
    g.wr8(POST, 0)
    g.battle_menu_goto(0); g.press("a", wait=12); g.press("a", wait=12)
    for _ in range(900):
        pre = cstr(g, PRE)
        if "Will-o-wisp" in pre or "Displacer" in pre:
            g.tick(2)
            return cstr(g, POST) if mine in pre else None
        if at_menu(g) or g.gs() != GS["BATTLE"]:
            return None
        g.tick(1)
    return None


def count(g, mine, force):
    """Tally the monster's result lines for `mine` across the seeds."""
    save_checkpoint(g, "t34_menu.state")
    lines = []
    for seed in SEEDS:
        if len(lines) >= WANTED:
            break
        load_checkpoint(g, "t34_menu.state")
        g.wr16(SEED, seed)
        keep_up(g)
        force(g)
        line = monster_line(g, mine)
        if line:
            lines.append(line)
    return lines


def strong_displacer(g):
    g.wr8(MON0 + M_ATK_BASE, 150); g.wr8(MON0 + M_ATK, 150)
    g.wr8(PL + POFF["def_base"], 100); g.wr8(PL + POFF["def_"], 100)


def warded_hero(g):
    g.wr8(PL + POFF["mdef_base"], 140); g.wr8(PL + POFF["mdef"], 140)
    g.wr8(MON0 + M_PARAMETER, ALWAYS)


# Floor 4's boss, the displacer beast, stands at (28,21) (src/floor4.c).
g, ok = start_fight(4, 31, (28, 21), "t34_displacer")
chk("T34 the fighter reaches floor 4's displacer beast", ok, f"gs={g.gs()} pos={g.pos()}")
lines = count(g, "tentacles", strong_displacer)
g.close()
both = sum("twice" in l for l in lines)
print(f"displacer, ATK 150 against DEF 100: {both} of {len(lines)} rounds landed both", lines)
chk("T34 the displacer beast attacked often enough to count", len(lines) >= 12, str(len(lines)))
chk("T34 with ATK 150 its second tentacle aims at 143, so both land in most rounds",
    lines and both > len(lines) * 0.6, f"{both}/{len(lines)}")

# Floor 6's elite, the will-o-wisp, stands at (23,4) (src/floor6.c).
g, ok = start_fight(6, 45, (23, 4), "t34_wisp")
chk("T34 the fighter reaches floor 6's will-o-wisp", ok, f"gs={g.gs()} pos={g.pos()}")
lines = count(g, "passes through", warded_hero)
g.close()
landed = sum("Terror" in l for l in lines)
print(f"wisp terror against MDEF 140: {landed} of {len(lines)} landed", lines)
chk("T34 the wisp tried its terror often enough to count", len(lines) >= 12, str(len(lines)))
chk("T34 against MDEF 140 its terror rolls against 135, so it lands under half the time",
    lines and landed < len(lines) * 0.5, f"{landed}/{len(lines)}")
chk.summary()
