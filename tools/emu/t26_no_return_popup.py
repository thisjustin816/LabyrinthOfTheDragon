"""T26 - the floor 1 stairs warn before that first one-way step.

Floor 1's stairs down to floor 2 are the point of no return: there is no
route back up once you take them. So "There is no going back!"
(str_floor_common_no_return) fires as a popup at (12,4), the tile just before
the stairs door, the first time the player steps onto it after beating the
boss. It must not fire before the boss is beaten (the boss NPC blocks the
tile anyway) and must fire only once per floor visit.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "playtest"))
from lotd import *
from helpers import *
from starts import start_on
import drive

chk = Checker("t26_no_return_popup")

g, st = start_on(1, class_id=2, level=15, tag="t26")   # 2 = monk, floor1 boss gate is 8

# The boss (NPC_1) stands at (12,5); talk to it from below.
g.teleport(12, 6, "UP")
g.tick(4)
g.interact()
chk("T26 the floor 1 boss fight starts",
    g.wait_for(lambda: g.gs() == GS["BATTLE"] and g.rd8(SYM["battle_state"]) == 2, 1800),
    f"gs={g.gs()}")

outcome = drive.resolve_battle(g, use_buffs=True)
chk("T26 the boss fight is won", outcome == "victory", outcome)
drive.dismiss_after_win(g)
g.wait_map_idle(900)

# The NPC is invisible and DOOR_3 open after the win: walk from where it stood onto
# the warning tile at (12,4).
g.teleport(12, 5, "UP")
g.tick(4)
g.step("UP")
pages = read_textbox(g)
chk("T26 the no-going-back warning shows on the first step onto (12,4)",
    any("no going" in p.lower() for p in pages), pages)
chk("T26 the player is standing on the warning tile", g.pos() == (12, 4), str(g.pos()))

# Step off and back on: it must not repeat this visit.
g.step("DOWN")
g.tick(10)
g.step("UP")
g.tick(20)
chk("T26 the player is back on the warning tile, on the map",
    g.gs() == GS["WORLD_MAP"] and g.pos() == (12, 4), f"gs={g.gs()} pos={g.pos()}")
ms = g.ms()
chk("T26 stepping onto (12,4) again this visit shows no textbox",
    ms not in (MS["TEXTBOX"], MS["TEXTBOX_OPEN"]), f"ms={ms}")

g.close()
chk.summary()
