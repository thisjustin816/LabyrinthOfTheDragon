"""T42 - a healing mirror used before a death stays used, and looks it.

Each of floor 8's six mirrors heals once, and healing_mirrors_used survives a
death on purpose. The trip back down reloads the floor, though, and the reload
clears the palette that dulls a spent mirror, so it looked new and then
answered "The mirror has lost its luster..." on_init dulls every spent mirror
again.

A hero uses the first mirror, floor 8 loads afresh as the trip back down would
load it, and the two mirrors of the bottom hall are compared: the used one is
dull and still refuses, the unused one is bright and still heals.

Loading a save runs on_init before the save's script state is put back, so
save_load() restores healing_mirrors_used first; otherwise on_init drew the
mirrors of the game played before the QUIT. A mirror used after the save
must look fresh once the save loads, and one used before it must look spent,
as drawn on screen rather than only in the override table.
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "playtest"))
from lotd import *
from helpers import *
from starts import start_on

chk = Checker("t42_floor8_mirrors")
USED = SYM["healing_mirrors_used"]
MIRROR_1, MIRROR_2 = (5, 27), (11, 27)            # where you stand, facing up
DULL = 4                                          # floor8.c dull_healing_mirror()
HP, MAX_HP = PL + POFF["hp"], PL + POFF["max_hp"]


def palette_above(g, spot):
    """The palette override on the mirror above `spot`, or None."""
    x, y = spot
    return tile_overrides(g).get((0, x, y - 1), (None, None))[1]


def use_mirror(g, spot):
    """Face the mirror hurt, press A, and return (text, healed)."""
    g.wr16(HP, 1)
    g.teleport(spot[0], spot[1], "UP")
    g.tick(4)
    g.press("a", wait=12)
    pages = read_textbox(g)
    g.wait_map_idle(300)
    return " ".join(pages), g.rd16(HP) == g.rd16(MAX_HP)


g, _ = start_on(8, class_id=1, level=50, tag="t42")
text, healed = use_mirror(g, MIRROR_1)
chk("T42 the first mirror heals and goes dull", healed and g.rd8(USED) & 1 and
    palette_above(g, MIRROR_1) == DULL,
    f"text={text!r} healed={healed} used={g.rd8(USED):#04x} palette={palette_above(g, MIRROR_1)}")

chk("T42 floor 8 loads afresh", reenter_floor(g, 8, 8, 29), f"pos={g.pos()} floor={current_floor(g)}")
chk("T42 the used mirror stays used", g.rd8(USED) & 1, f"used={g.rd8(USED):#04x}")
chk("T42 and is drawn dull again", palette_above(g, MIRROR_1) == DULL,
    f"palette={palette_above(g, MIRROR_1)}")
chk("T42 while the unused mirror is drawn as it always was", palette_above(g, MIRROR_2) is None,
    f"palette={palette_above(g, MIRROR_2)}")

text, healed = use_mirror(g, MIRROR_1)
chk("T42 the used mirror still refuses", not healed and "luster" in text.lower(),
    f"text={text!r} healed={healed}")
# The text oracle decodes with tile_char() as well, so only a literal shows
# that the ellipsis glyph reads as an ellipsis.
chk("T42 and says so word for word, ellipsis and all", text == "The mirror has lost its luster\u2026",
    f"text={text!r}")
text, healed = use_mirror(g, MIRROR_2)
chk("T42 and the unused one still heals", healed and palette_above(g, MIRROR_2) == DULL,
    f"text={text!r} healed={healed}")
g.close()


def drawn_above(g, spot):
    """The palettes the screen draws the mirror above `spot` in."""
    return drawn_palettes(g, spot[0], spot[1] - 1)


def quit_and_load(g):
    """QUIT from the pause menu, as the manual says to go back to a save,
    and load slot 0 again without a power cycle."""
    g.press("start", wait=14)
    g.press("down", wait=8)
    g.press("right", wait=8)                      # QUIT, the far corner
    g.press("a", wait=12)
    g.press("left", wait=8)                       # YES
    g.press("a", wait=12)
    at_title = g.wait_for(lambda: g.gs() == GS["TITLE"], 600)
    g.boot_to_save_select()
    g.tick(10)
    g.save_select_pick(0)
    g.wait_map_idle(900)
    g.tick(30)
    return at_title and current_floor(g) == 8


# The save is the floor 8 arrival, with every mirror unused.
g, _ = start_on(8, class_id=1, level=50, tag="t42q")
text, healed = use_mirror(g, MIRROR_1)
g.teleport(8, 29, "UP")
g.tick(10)
chk("T42 QUIT after using a mirror the save never saw, then load the save", quit_and_load(g),
    f"gs={g.gs()} floor={current_floor(g)}")
chk("T42 the loaded game has the mirror unused", not g.rd8(USED) & 1 and palette_above(g, MIRROR_1) is None,
    f"used={g.rd8(USED):#04x} palette={palette_above(g, MIRROR_1)}")
chk("T42 and the screen draws it fresh, not in the spent palette", DULL not in drawn_above(g, MIRROR_1),
    f"drawn={drawn_above(g, MIRROR_1)}")
text, healed = use_mirror(g, MIRROR_1)
chk("T42 and it heals", healed, f"text={text!r}")

g.teleport(8, 29, "UP")
g.tick(10)
menu_save(g, chk, "T42 save with the mirror spent")
chk("T42 QUIT and load that save", quit_and_load(g), f"gs={g.gs()} floor={current_floor(g)}")
chk("T42 the screen draws the mirror spent", drawn_above(g, MIRROR_1) == [DULL],
    f"drawn={drawn_above(g, MIRROR_1)} used={g.rd8(USED):#04x}")
text, healed = use_mirror(g, MIRROR_1)
chk("T42 and it still refuses", not healed and "luster" in text.lower(), f"text={text!r}")
g.close()
chk.summary()
