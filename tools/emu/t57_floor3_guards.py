"""T57 - floor 3's goblin guards wait on bones that dim once they have fought.

A goblin guard waits on the tile in front of each of the floor's four skull
buttons and attacks the first time the hero steps there after the floor loads.
The map draws a pile of bones on each of those tiles in the bright bone
palette, and the fight repaints them in the dim one. A save keeps the repaint
along with the guard's flag, and a fresh load of the floor, as after a death,
brings every guard back on bright bones.

Each guard's tile is entered from the floor tile below it, on a floor loaded
afresh with the hero standing there, so the screen shows the tile as the game
drew it.
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "playtest"))
from lotd import *
from helpers import *
from starts import start_on
from drive import resolve_battle, dismiss_after_win

chk = Checker("t57_floor3_guards")
MONK, GOBLIN = 2, 1
BONES = 0xC0                         # graphic 48's first tile (map_tile_lookup, src/core.c)
BRIGHT, DIM = 3, 4                   # floor 3's bright and dim bone palettes
MON0 = SYM["encounter"] + 1
M_TYPE, M_HP, M_TARGET_HP = 0, 14, 16
GUARDS = [(3, 26), (9, 26), (22, 3), (28, 3)]


def drawn(g, tile):
    """(first BG tile, palettes) the screen draws map tile `tile` with."""
    x, y = tile
    return vram_byte(g, screen_cells(g, x, y)[0], 0), drawn_palettes(g, x, y)


def enter(g):
    """Step up onto the guard's tile. Returns whether a fight against a goblin
    started."""
    g.step("UP")
    return g.wait_for(lambda: g.gs() == GS["BATTLE"] and at_menu(g), 900) and g.rd8(MON0 + M_TYPE) == GOBLIN


g, _ = start_on(3, class_id=MONK, level=30, tag="t57")
for x, y in GUARDS:
    chk(f"T57 floor 3 loads with the hero below the guard at ({x},{y})",
        reenter_floor(g, 3, x, y + 1), f"pos={g.pos()}")
    tile, pals = drawn(g, (x, y))
    chk(f"T57 the guard's tile at ({x},{y}) shows bright bones", tile == BONES and pals == [BRIGHT],
        f"tile={tile:#04x} palettes={pals}")

guard = GUARDS[0]
reenter_floor(g, 3, guard[0], guard[1] + 1)
chk("T57 stepping onto the bones starts a fight with the goblin guard", enter(g),
    f"gs={g.gs()} type={g.rd8(MON0 + M_TYPE)}")
keep_alive(g)
g.wr16(MON0 + M_HP, 1)
g.wr16(MON0 + M_TARGET_HP, 1)
result = resolve_battle(g)
dismiss_after_win(g)
chk("T57 the guard falls", result == "victory" and g.pos() == guard, f"result={result} pos={g.pos()}")
g.step("DOWN")
tile, pals = drawn(g, guard)
chk("T57 the fought guard's bones stay, dimmed", tile == BONES and pals == [DIM],
    f"tile={tile:#04x} palettes={pals}")
others = {xy: tile_overrides(g).get((0,) + xy) for xy in GUARDS[1:]}
chk("T57 the three guards not yet fought keep their bright bones", all(v is None for v in others.values()),
    str(others))
chk("T57 the fought guard's tile starts nothing", not enter(g) and g.gs() == GS["WORLD_MAP"],
    f"gs={g.gs()}")

menu_save(g, chk, "T57 a save on the fought guard's tile")
g = reload_slot(g, 0, "t57_reload")
g.step("DOWN")
tile, pals = drawn(g, guard)
chk("T57 loading the save keeps the guard's bones dim", tile == BONES and pals == [DIM],
    f"tile={tile:#04x} palettes={pals}")
chk("T57 and its tile still starts nothing", not enter(g) and g.gs() == GS["WORLD_MAP"], f"gs={g.gs()}")

chk("T57 a fresh load of the floor, as after a death", reenter_floor(g, 3, guard[0], guard[1] + 1),
    f"pos={g.pos()}")
tile, pals = drawn(g, guard)
chk("T57 brings the guard back on bright bones", tile == BONES and pals == [BRIGHT],
    f"tile={tile:#04x} palettes={pals}")
chk("T57 and its fight with them", enter(g), f"gs={g.gs()}")
g.close()
chk.summary()
