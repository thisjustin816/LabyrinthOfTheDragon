"""T55 - the target cursor starts on the last monster targeted.

FIGHT and a single-target ability open their target step on the monster the
last single-target command was aimed at, as long as it still stands, and on
the first monster standing otherwise. Each fight starts that over.

Monster slots from LabyrinthOfTheDragon.cdb: 64 bytes each from encounter+1,
active at +5, max_hp at +12, hp at +14, target_hp at +16. BattleMenu:
active_menu +0, screen_cursor +1.
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "playtest"))
from lotd import *
from helpers import *
from starts import start_on, reseed
import drive

chk = Checker("t55_target_memory")
BM = SYM["battle_menu"]
MENU_FIGHT, MONSTER_SELECT = 1, 3
CURSOR_MONSTER_1 = 9
OPEN_PALM_ROW = 1


def slot(k):
    return SYM["encounter"] + 1 + 64 * k


def standing(g):
    return [k for k in range(3) if g.rd8(slot(k) + 5)]


def set_hp(g, k, hp):
    for off in (12, 14, 16):
        g.wr16(slot(k) + off, hp)


def next_menu(g):
    """Press through the round until the command menu is back, or the fight
    is over."""
    for frame in range(4000):
        if at_menu(g) or g.gs() != GS["BATTLE"]:
            break
        if frame % 10 == 0:
            g.pb.button_press("a")
        elif frame % 10 == 2:
            g.pb.button_release("a")
        g.tick(1)
    g.pb.button_release("a")
    g.tick(10)
    return at_menu(g)


def open_fight(g):
    """FIGHT's target step: returns the monster slot the cursor starts on."""
    g.battle_menu_goto(0)
    g.press("a", wait=14)
    return g.rd8(BM + 1) - CURSOR_MONSTER_1 if g.rd8(BM) == MENU_FIGHT else None


def aim(g, k):
    for _ in range(4):
        if g.rd8(BM + 1) == CURSOR_MONSTER_1 + k:
            return True
        g.press("right", wait=10)
    return g.rd8(BM + 1) == CURSOR_MONSTER_1 + k


def group_fight(g, tag):
    """A random fight with two or more monsters, from a fresh seed each try."""
    save_checkpoint(g, f"{tag}.state")
    for k in range(40):
        load_checkpoint(g, f"{tag}.state")
        reseed(g, 11 * k + 3)
        if g.walk_until_battle(("DOWN", "UP"), max_steps=200) and g.wait_for(lambda: at_menu(g), 1800):
            g.tick(10)
            if len(standing(g)) >= 2:
                return True
    return False


g, st = start_on(1, level=10, abilities=0x3F, tag="t55")
# A lit torch would keep the fights away; start_on leaves it out.
g.wr8(PL + POFF["torch_gauge"], 0)
chk("T55 a random fight with two or more monsters starts on floor 1", group_fight(g, "t55_map"),
    f"standing={standing(g)}")

up = standing(g)
first, last = up[0], up[-1]
# Open Palm's target: the middle monster of three, which neither the first-standing
# default nor the last target would land on.
middle = up[1] if len(up) == 3 else first
keep_alive(g)
for k in up:
    set_hp(g, k, 999)
chk("T55 the first FIGHT of a fight starts on the first monster standing", open_fight(g) == first,
    f"cursor slot={g.rd8(BM + 1) - CURSOR_MONSTER_1} standing={up}")
chk("T55 the cursor moves to the last monster", aim(g, last), str(g.rd8(BM + 1)))
g.press("a", wait=4)
chk("T55 the next round's menu comes up", next_menu(g))

keep_alive(g)
for k in up:
    set_hp(g, k, 999)
chk("T55 the next FIGHT starts on the monster just attacked", open_fight(g) == last,
    f"cursor slot={g.rd8(BM + 1) - CURSOR_MONSTER_1}")
g.press("b", wait=14)
g.battle_menu_goto(1)
g.press("a", wait=14)
for _ in range(8):
    if g.rd8(BM + 4) == OPEN_PALM_ROW:
        break
    g.press("down" if g.rd8(BM + 4) < OPEN_PALM_ROW else "up", wait=10)
g.press("a", wait=14)
chk("T55 Open Palm's target step starts on the same monster",
    g.rd8(BM) == MONSTER_SELECT and g.rd8(BM + 1) == CURSOR_MONSTER_1 + last,
    f"menu={g.rd8(BM)} cursor={g.rd8(BM + 1)}")
aim(g, middle)
g.press("a", wait=4)
chk("T55 the round after Open Palm comes up", next_menu(g))

keep_alive(g)
for k in up:
    set_hp(g, k, 999)
chk("T55 FIGHT then starts on the monster Open Palm hit", open_fight(g) == middle,
    f"cursor slot={g.rd8(BM + 1) - CURSOR_MONSTER_1}")

# Fell the remembered monster; the target step then starts on the first
# monster still standing.
set_hp(g, middle, 1)
for _ in range(20):
    g.press("a", wait=4)
    if not next_menu(g) or middle not in standing(g):
        break
    keep_alive(g)
    open_fight(g)
still = standing(g)
chk("T55 the remembered monster falls", at_menu(g) and middle not in still and still,
    f"standing={still}")
if at_menu(g) and still:
    chk("T55 FIGHT then starts on the first monster still standing", open_fight(g) == still[0],
        f"cursor slot={g.rd8(BM + 1) - CURSOR_MONSTER_1} standing={still}")
    g.press("b", wait=14)

# Win the fight, then check the next one starts over.
for k in still:
    set_hp(g, k, 1)
for _ in range(30):
    if g.gs() != GS["BATTLE"] or not at_menu(g):
        break
    keep_alive(g)
    open_fight(g)
    g.press("a", wait=4)
    next_menu(g)
drive.dismiss_after_win(g)
back = g.wait_map_idle(900) and current_floor(g) == 1
chk("T55 the fight is won and the map is back", back, f"gs={g.gs()} floor={current_floor(g)}")
if back:
    g.wr8(PL + POFF["torch_gauge"], 0)
    fought = group_fight(g, "t55_map2")
    chk("T55 another group fight starts", fought, f"standing={standing(g)}")
    if fought:
        chk("T55 a new fight's first FIGHT starts on its first monster standing",
            open_fight(g) == standing(g)[0], f"cursor slot={g.rd8(BM + 1) - CURSOR_MONSTER_1}")
g.close()
chk.summary()
