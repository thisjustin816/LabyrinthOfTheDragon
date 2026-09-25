"""T56 - the hero vanishes into every brick-faced passage.

Four hidden passages open through a tile drawn as brick wall: floor 2's
B(22,4), floor 4's A(4,27), and floor 5's A(7,4) and A(25,23). Each tile
carries the background-priority bit, so the hero standing on it is drawn behind
the bricks, and only a few pixels show through the mortar, which is background
color 0. A tile without the bit leaves the whole hero in view.

Each check compares a frame with the hero against the same frame with every
sprite hidden, inside the hero's four sprite cells.
"""
import os, sys
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "playtest"))
from lotd import *
from helpers import reenter_floor
from starts import start_on

chk = Checker("t56_brick_passages")
SHADOW_OAM = SYM.get("shadow_OAM", 0xC000)
# (floor, map id, x, y): each passage's brick tile, entered from below.
BRICKS = [(2, 1, 22, 4), (4, 0, 4, 27), (5, 0, 7, 4), (5, 0, 25, 23)]
# The mortar shows 7 of the hero's pixels; a hero in plain view shows 140.
MAX_SHOWING = 16


def hero_pixels_showing(g):
    """How many of the hero's sprite-cell pixels the screen shows."""
    mem = g.pb.memory
    g.tick(20, True)
    with_hero = g.pb.screen.ndarray[:, :, :3].copy()
    mask = np.zeros((144, 160), bool)
    for k in range(4):                         # the hero is the first four sprites
        sy, sx = mem[SHADOW_OAM + 4 * k] - 16, mem[SHADOW_OAM + 4 * k + 1] - 8
        mask[max(sy, 0):max(sy + 8, 0), max(sx, 0):max(sx + 8, 0)] = True
    saved = [mem[SHADOW_OAM + 4 * k] for k in range(40)]
    for k in range(40):
        mem[SHADOW_OAM + 4 * k] = 0
        mem[0xFE00 + 4 * k] = 0
    g.pb.tick(1, True)
    without = g.pb.screen.ndarray[:, :, :3].copy()
    for k in range(40):
        mem[SHADOW_OAM + 4 * k] = saved[k]
    g.pb.tick(2, True)
    return int(((with_hero != without).any(axis=2) & mask).sum())


g, _ = start_on(2, level=30, tag="t56")
for floor, map_id, x, y in BRICKS:
    where = f"floor {floor} {'AB'[map_id]}({x},{y})"
    arrived = reenter_floor(g, floor, x, y + 1, map_id)
    stepped = arrived and g.step("UP") and g.wait_map_idle(200) and g.pos() == (x, y)
    chk(f"T56 the hero steps onto the brick tile at {where}", stepped, str(g.pos()))
    if stepped:
        showing = hero_pixels_showing(g)
        chk(f"T56 the hero is behind the bricks at {where}", showing <= MAX_SHOWING,
            f"{showing} pixels showing")
g.close()
chk.summary()
