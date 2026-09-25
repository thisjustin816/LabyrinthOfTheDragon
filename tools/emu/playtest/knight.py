"""The death knight fight's setup, shared by t33_death_knight_rise.py,
t36_fire_sounds.py, and t38_open_palm_text.py: a hero on floor 8 stepping onto
the death knight's tile.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import *
from starts import start_on

KNIGHT_TILE = (4, 17)                # MINI_BOSS_DKNIGHT, src/floor8.c


def start_fight(cls, level, tag):
    """A hero of class `cls` at `level` on floor 8, with every ability,
    stepping onto the death knight's tile. Returns (game, at the battle menu)."""
    g, _ = start_on(8, class_id=cls, level=level, abilities=0x3F, tag=tag)
    x, y = KNIGHT_TILE
    g.teleport(x, y + 1, "UP"); g.tick(4)
    g.step("UP")
    for _ in range(40):
        if at_menu(g):
            return g, True
        if g.ms() in (MS["TEXTBOX"], MS["TEXTBOX_OPEN"]):
            g.press("a", wait=20)
        g.tick(30)
    return g, at_menu(g)
