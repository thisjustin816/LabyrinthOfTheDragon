"""T61 - a standing NPC walls off its tile, and the pathfinder routes around it.

map.c's tile lookup makes a visible NPC's tile a wall and lets the hero onto
it once the NPC is hidden. nav.py reads each floor's NPCs from its source and
takes the game's npc_visible byte, so a planned route and the game agree.
Floor 8's beholder stands in the open hall on the straight way up from the
floor's entrance to the door below the dragon, so a route that ignored it
would walk into it and stop.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "playtest"))
from lotd import *
from helpers import *
from starts import start_on
from nav import load_npcs
import drive

chk = Checker("t61_nav_npcs")
DRAGON, BEHOLDER = (8, 3), (8, 11)
BEHOLDER_BIT = 0x02                               # NPC_2 in src/floor8.c's npcs[]
BELOW_DOOR, BELOW_BEHOLDER = (8, 10), (8, 12)


def tiles(start, path):
    """Every tile a path steps on, in order."""
    x, y = start
    out = []
    for d in path:
        dx, dy = DIRS_XY[d]
        x, y = x + dx, y + dy
        out.append((x, y))
    return out


def walk(f, goal, note):
    """Plan from the hero to `goal` on `f`, walk it, and return
    (tiles stepped on, whether the hero got there)."""
    start = g.pos()
    path = f.path("A", start, "A", goal)
    if path is None:
        return None, False
    done = drive.run_path(g, f, "A", path, note)
    return tiles(start, path), done is True and g.pos() == goal


chk("T61 nav reads floor 8's NPCs from src/floor8.c: the dragon and the beholder",
    load_npcs(8) == {("A", *DRAGON): 0x01, ("A", *BEHOLDER): BEHOLDER_BIT}, str(load_npcs(8)))

g, _ = start_on(8, tag="t61")
# A lit torch keeps random fights off these steps.
g.wr8(PL + POFF["has_torch"], 1)
g.wr8(PL + POFF["torch_gauge"], 32)
g.wr8(PL + POFF["torch_color"], 1)
visible = g.get("npc_visible")
chk("T61 the beholder stands when the hero arrives at (8,29)",
    g.pos() == (8, 29) and visible & BEHOLDER_BIT, f"pos={g.pos()} npc_visible={visible:#04x}")

f = Floor(8, npc_visible=visible)
stepped, arrived = walk(f, BELOW_DOOR, "up past the beholder")
chk("T61 the route up to the door goes around the beholder, not through it",
    stepped is not None and BEHOLDER not in stepped, f"route={stepped}")
chk("T61 and the hero walks it to (8,10)", arrived, f"pos={g.pos()}")

stepped, arrived = walk(f, BELOW_BEHOLDER, "back around to below the beholder")
chk("T61 back around to (8,12), below the beholder", arrived, f"pos={g.pos()} route={stepped}")
moved = g.step("UP")
g.tick(30)
chk("T61 where a step up bumps into the beholder", not moved and g.pos() == BELOW_BEHOLDER,
    f"moved={moved} pos={g.pos()}")

# Hidden as floor8.c hides it: set_npc_invisible() clears the bit and has the
# hero's neighboring tiles read again.
g.set("npc_visible", visible & ~BEHOLDER_BIT)
g.set("refresh_local_tiles", 1)
g.tick(2)
f = Floor(8, npc_visible=g.get("npc_visible"))
stepped, arrived = walk(f, BELOW_DOOR, "across the hidden beholder's tile")
chk("T61 with the beholder hidden, the route goes straight across its tile",
    stepped == [BEHOLDER, BELOW_DOOR], f"route={stepped}")
chk("T61 and the hero walks it", arrived, f"pos={g.pos()}")

g.close()
chk.summary()
