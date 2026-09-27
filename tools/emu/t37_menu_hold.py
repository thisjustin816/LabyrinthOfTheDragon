"""T37 - a direction held from one battle menu into the next leaves the new
menu's cursor alone.

Holding DOWN to step from FIGHT to TECH arms the cursor-repeat timer in
on_dpad(), and the ability list polls the same timer. A thumb that lingers on
DOWN for a third of a second after TECH opens must not slide the cursor off
the first row: the hold has to be released and pressed again. A fresh press
moves at once and a fresh hold repeats, even one rolled onto from the held
direction without letting go. The same holds for a direction held through the
B that closes a submenu, and for one held as a battle starts or as a new round
hands the main menu back, since both open it too.
"""
import io
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "playtest"))
from lotd import *
from helpers import *
from starts import start_on

chk = Checker("t37_menu_hold")
MONK = 2
BM = SYM["battle_menu"]
MENU_MAIN, MENU_ABILITY = 0, 2                  # BattleMenuType, src/battle.h
CURSOR_MAIN_FIGHT, CURSOR_MAIN_ABILITY = 0, 1   # BattleScreenCursor, src/battle.h
MON0, MON_STRIDE = SYM["encounter"] + 1, 64     # Encounter.monsters[3], src/encounter.h
M_ACTIVE, M_HP, M_TARGET_HP = 5, 14, 16


def active_menu(g):
    return g.rd8(BM)


def screen_cursor(g):
    return g.rd8(BM + 1)


def row(g):
    return g.rd8(BM + 4)


def press_while_held(g, held, btn, before, after):
    """Hold `held`, press `btn` `before` frames in, and keep `held` down for
    `after` more frames before letting go."""
    g.pb.button_press(held); g.tick(before)
    g.pb.button_press(btn); g.tick(2); g.pb.button_release(btn)
    g.tick(after)
    g.pb.button_release(held); g.tick(2)


g, _ = start_on(5, class_id=MONK, level=38, abilities=0x1F, tag="t37")
keep_alive(g)
on_map = io.BytesIO(); g.pb.save_state(on_map)

# A direction held as a battle starts: the step that rolls the fight is taken
# with DOWN (or UP), which stays down through the battle's opening.
# The repeat timer is left as any earlier press leaves it, counting down from
# 20. One never pressed this power-on sits at 0 and waits 255 frames before a
# held direction repeats, which would hide the carried-over hold.
STEPS, CHANCE = STATIC["map_encounters.steps"], STATIC["map_encounters.current_chance"]
CURSOR_TIMER = STATIC["battle.cursor_timer"]    # Timer.counter, src/core.h
held = None
for d in ("down", "up"):
    on_map.seek(0); g.pb.load_state(on_map)
    g.wr8(STEPS, 200)                           # past the safe steps
    g.wr8(CHANCE, 255)                          # and certain to roll a fight
    g.wr8(CURSOR_TIMER, 20)
    g.pb.button_press(d)
    if g.wait_for(lambda: g.gs() == GS["BATTLE"], 120):
        held = d
        break
    g.pb.button_release(d)
    g.tick(2)
chk("T37 a step taken with a direction held starts a fight", held is not None, f"gs={g.gs()} pos={g.pos()}")
if held:
    g.wait_for(lambda: at_menu(g), 1800)
    g.tick(40)
    cursor = screen_cursor(g)
    g.pb.button_release(held)
    g.tick(2)
    chk("T37 the direction held into the fight leaves the main cursor on FIGHT",
        active_menu(g) == MENU_MAIN and cursor == CURSOR_MAIN_FIGHT, f"menu={active_menu(g)} cursor={cursor}")
    g.press("down", wait=10)
    chk("T37 and a fresh press after it moves the cursor", screen_cursor(g) == CURSOR_MAIN_ABILITY,
        f"cursor={screen_cursor(g)}")

on_map.seek(0); g.pb.load_state(on_map)
chk("T37 a fight starts on floor 5",
    g.walk_until_battle(("UP", "DOWN", "LEFT", "RIGHT"), max_steps=400) and g.wait_for(lambda: at_menu(g), 1800),
    f"gs={g.gs()}")
start = io.BytesIO(); g.pb.save_state(start)

# DOWN carries the cursor from FIGHT to TECH, A opens TECH while DOWN is still
# down, and DOWN stays down for two thirds of a second more.
press_while_held(g, "down", "a", 6, 40)
chk("T37 TECH opened", active_menu(g) == MENU_ABILITY, f"menu={active_menu(g)}")
chk("T37 the DOWN held over from the main menu leaves the cursor on the first ability",
    row(g) == 0, f"row={row(g)}")
g.press("down", wait=10)
chk("T37 a fresh press moves it one row", row(g) == 1, f"row={row(g)}")
g.press("up", wait=10)
g.pb.button_press("down"); g.tick(40); g.pb.button_release("down"); g.tick(2)
chk("T37 a fresh hold still repeats", row(g) >= 2, f"row={row(g)}")

# LEFT held while A opens TECH, then a thumb rolled onto DOWN with no frame
# between: only the held-over LEFT waits for its release, so DOWN moves and
# repeats as any fresh hold does.
start.seek(0); g.pb.load_state(start)
g.press("down", wait=10)                        # the main cursor onto TECH
g.pb.button_press("left"); g.tick(4)
g.press("a", wait=14)                           # TECH, LEFT still down
chk("T37 TECH opened with LEFT held", active_menu(g) == MENU_ABILITY and row(g) == 0,
    f"menu={active_menu(g)} row={row(g)}")
g.pb.button_press("down"); g.tick(2)
g.pb.button_release("left"); g.tick(40)
g.pb.button_release("down"); g.tick(2)
chk("T37 a roll from the held-over LEFT onto DOWN moves and repeats", row(g) >= 2, f"row={row(g)}")

# UP held while B closes TECH: the main cursor stays on TECH.
start.seek(0); g.pb.load_state(start)
g.press("down", wait=10); g.press("a", wait=14)
chk("T37 TECH opened again", active_menu(g) == MENU_ABILITY, f"menu={active_menu(g)}")
press_while_held(g, "up", "b", 6, 40)
chk("T37 back on the main menu", active_menu(g) == MENU_MAIN, f"menu={active_menu(g)}")
chk("T37 the UP held through B leaves the main cursor on TECH",
    screen_cursor(g) == CURSOR_MAIN_ABILITY, f"cursor={screen_cursor(g)}")

# DOWN held from the attack's confirmation through the whole round: the main
# menu the next round opens keeps its cursor on FIGHT. The foes get HP enough
# to outlast the blow, so the round ends with the fight still on.
start.seek(0); g.pb.load_state(start)
for k in range(3):
    m = MON0 + k * MON_STRIDE
    if g.rd8(m + M_ACTIVE):
        g.wr16(m + M_HP, 60000)
        g.wr16(m + M_TARGET_HP, 60000)
g.press("down", wait=10)                        # a press and back, as a player
g.press("up", wait=10)                          # browsing the menu leaves the timer
g.press("a", wait=12)                           # FIGHT, to its target
g.pb.button_press("down")
g.tick(4)
g.press("a", wait=2)                            # attack, DOWN still down
g.wait_for(lambda: not at_menu(g), 120)
back = g.wait_for(lambda: at_menu(g), 3000)
keep_alive(g)
g.tick(40)
cursor = screen_cursor(g)
g.pb.button_release("down")
g.tick(2)
chk("T37 the next round opens the main menu", back and active_menu(g) == MENU_MAIN,
    f"menu={active_menu(g)} gs={g.gs()}")
chk("T37 the DOWN held through the round leaves the cursor on FIGHT", cursor == CURSOR_MAIN_FIGHT,
    f"cursor={cursor}")
g.close()

chk.summary()
