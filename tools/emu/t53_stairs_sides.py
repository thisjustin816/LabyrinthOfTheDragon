"""T53 - a stairway is entered only through its opening.

Stairways are drawn into a wall and open toward the bottom of the screen.
Floor 2's lower level has the one stairway with open floor beside it: the
corridor at x=15 runs down past the stairs at B(14,8) to their landing. A step
left from (15,8) must bump like the wall around the stairs, while the corridor
still walks and a step up from the landing still takes them.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "playtest"))
from lotd import *
from helpers import *
from starts import start_on

chk = Checker("t53_stairs_sides")
MAP_A, MAP_B = 0, 1

g, st = start_on(2, tag="t53")
# A lit torch keeps random fights off these steps.
g.wr8(PL + POFF["has_torch"], 1)
g.wr8(PL + POFF["torch_gauge"], 32)
g.wr8(PL + POFF["torch_color"], 1)
heard = sounds_heard(g)


def active_map(g):
    return g.rd8(g.get16("active_map"))


chk("T53 floor 2's lower level loads with the hero beside the stairs, at B(15,8)",
    reenter_floor(g, 2, 15, 8, map_id=MAP_B) and active_map(g) == MAP_B,
    f"pos={g.pos()} map={active_map(g)}")

g.face("DOWN")
mark = len(heard)
moved = g.step("LEFT")
g.tick(30)
chk("T53 a step left from (15,8) doesn't take the stairs at (14,8)",
    not moved and g.pos() == (15, 8) and active_map(g) == MAP_B and g.ms() == MS["WAITING"],
    f"moved={moved} pos={g.pos()} map={active_map(g)} ms={g.ms()}")
bumps = [s for _, s in heard[mark:]]
chk("T53 the hero turns to the stairs and bumps, as into a wall",
    g.facing() == "LEFT" and bumps == ["sfx_wall_hit"], f"facing={g.facing()} heard={bumps}")

ok = g.step("UP") and g.step("UP")
chk("T53 the corridor beside the stairs walks up to (15,6)", ok and g.pos() == (15, 6), str(g.pos()))
ok = g.step("DOWN") and g.step("DOWN") and g.step("DOWN")
chk("T53 and back down past the stairs to the landing at (15,9)", ok and g.pos() == (15, 9), str(g.pos()))

ok = g.step("LEFT")
chk("T53 the landing walks left to (14,9), below the stairs", ok and g.pos() == (14, 9), str(g.pos()))
g.step("UP")
arrived = g.wait_map_idle(600)
# The stairs land on A(18,16) and walk the hero one step down, off them.
chk("T53 a step up from (14,9) takes the stairs to map A",
    arrived and active_map(g) == MAP_A and g.pos() == (18, 17) and current_floor(g) == 2,
    f"pos={g.pos()} map={active_map(g)} floor={current_floor(g)}")

g.close()
chk.summary()
