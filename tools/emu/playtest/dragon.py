"""The dragon fight's setup, shared by t27_evade_sound.py, t35_dragon_immune.py,
t36_fire_sounds.py, and t40_trip_immune.py: a built character on floor 8 with
the gauntlet cleared, walked up to the dragon and into the battle.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import *
import drive

MON0 = SYM["encounter"] + 1                  # Encounter.monsters[0]
DRAGON_MAX = MON0 + 12                       # Monster.max_hp
DRAGON = (8, 3)


def built(cid, level, items, tag):
    """A game with a built character of class `cid` standing on floor 8, the
    gauntlet cleared (heroes.build_hero opens DOOR_1 and hides the beholder)."""
    from heroes import build_hero, sram_for
    blob, _ = build_hero(cid, level, items=items, tag=tag)
    g = Game(tag=tag, sram=sram_for(blob))
    assert g.boot_to_save_select()
    g.save_select_pick(0)
    g.tick(60)
    return g


def engage(g, note, shot=None):
    """Walk from anywhere in the chamber to the dragon, check its line against
    strings.js through the text oracle, and wait for the battle. A line that
    doesn't match stops the suite. Returns the dragon's max HP."""
    f8 = Floor(8, open_doors={("A", 8, 9)}, npc_visible=g.get("npc_visible"))
    if g.pos()[1] > 8:
        assert cross_exit(g, f8, "A", ("A", 8, 9), "A", (8, 5), f"{note}: to the chamber")
    path, facing = f8.path("A", g.pos(), "A", DRAGON, face_adjacent=True)
    assert drive.run_path(g, f8, "A", path, f"{note}: up to the dragon") is True
    g.wait_map_idle(300); g.step(facing); g.wait_map_idle(200)
    g.press("a", wait=20)
    pages = read_textbox(g, shot=shot)
    log(f"  intro ({note}): \"{' / '.join(pages) or '(no text captured)'}\"")
    assert check_oracle(pages, ("floor8", "boss"), f"intro ({note})"), \
        f"{note}: the dragon's line doesn't match strings.js"
    assert g.wait_for(lambda: g.gs() == GS["BATTLE"], 600), f"{note}: no battle gs={g.gs()}"
    return g.rd16(DRAGON_MAX)


def keep_up(g):
    """The dragon back at full HP, for a suite whose hero would otherwise end
    the fight before the attack it is watching for has come up."""
    full = g.rd16(DRAGON_MAX)
    g.wr16(MON0 + 14, full)                  # Monster.hp
    g.wr16(MON0 + 16, full)                  # Monster.target_hp
