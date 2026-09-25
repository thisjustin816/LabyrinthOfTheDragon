"""T43 - floor 7's elite gives a haste potion, an ATK up, and a DEF up.

Every earlier elite teaches an ability. Floor 7's comes after the last one, so
it pays in battle items instead: one of each buff a player can drink at the
start of a big fight. A hero with none of the three talks to the displacer
beast, wins, and reads the textbox that follows.
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "playtest"))
from lotd import *
from helpers import *
from starts import start_on

chk = Checker("t43_floor7_elite_kit")
ELITE = (2, 17)                                   # floor7.c NPC_2
MON0 = SYM["encounter"] + 1
M_HP, M_TARGET_HP = 14, 16
KIT = ["HASTE", "ATK_UP", "DEF_UP"]


def held(g):
    inv = SYM["inventory"]
    return {n: g.rd8(inv + 4 * i + 1) for i, n in enumerate(ITEM_NAMES) if n in KIT}


g, _ = start_on(7, class_id=1, level=60, abilities=0x3F, tag="t43")
for i, n in enumerate(ITEM_NAMES):
    if n in KIT:
        g.wr8(SYM["inventory"] + 4 * i + 1, 0)
chk("T43 the hero starts with none of the three", held(g) == dict.fromkeys(KIT, 0), str(held(g)))

g.teleport(ELITE[0], ELITE[1] + 1, "UP")
g.interact()
chk("T43 talking to the displacer beast starts the fight", g.wait_for(lambda: at_menu(g), 1200),
    f"gs={g.gs()}")
for _ in range(6):
    if g.gs() != GS["BATTLE"]:
        break
    g.wait_for(lambda: at_menu(g) or g.gs() != GS["BATTLE"], 2000)
    if g.gs() != GS["BATTLE"]:
        break
    g.wr16(MON0 + M_HP, 1)
    g.wr16(MON0 + M_TARGET_HP, 1)
    g.battle_menu_goto(0)
    g.press("a", wait=12)
    g.press("a", wait=12)
    for _ in range(300):
        if g.gs() != GS["BATTLE"] or at_menu(g):
            break
        g.press("a", hold=2, wait=8)
chk("T43 the elite is beaten", g.wait_for(lambda: g.gs() == GS["WORLD_MAP"], 1200), f"gs={g.gs()}")

# The map settles for a frame between the fight and the box, which
# read_textbox() would take for a box that never came.
g.wait_for(lambda: g.ms() in (MS["TEXTBOX"], MS["TEXTBOX_OPEN"]), 300)
pages = read_textbox(g, shot="t43_kit_text")
text = " ".join(pages)
chk("T43 the textbox names all three", all(w in text for w in ("haste potion", "ATK", "DEF")),
    f"pages={pages}")
chk("T43 and the hero holds one of each", held(g) == dict.fromkeys(KIT, 1), str(held(g)))
g.close()
chk.summary()
