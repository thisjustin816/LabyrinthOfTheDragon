"""T45 - floor 8's gauntlet: bones mark the waiting fights, each fight opens
with its boss's line from its home floor, and a win leaves dimmer bones.

The gauntlet hall's six fights are the bosses of floors 1 to 6. The map draws a
pile of bones on each fight's tile in the bright bone palette. Stepping onto
one plays the roar and the line that boss used on its own floor, and the fight
starts only once the line closes. A win repaints the bones in the floor's own
palette, and the tile starts nothing after that. A save keeps the repaint along
with the win, and a fresh load of the floor, as after a death, brings every
fight back with its bright bones.

Each fight is entered from the floor tile to its right, on a floor loaded
afresh with the hero standing there, so the screen shows the tile as the game
drew it. The roars are caught with a breakpoint on each sound's entry point,
since play_sound() leaves nothing behind to read.
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "playtest"))
from lotd import *
from helpers import *
from starts import start_on
from drive import resolve_battle, dismiss_after_win
from text_oracle import expected_pages, normalize

chk = Checker("t45_gauntlet")
MONK = 2
BONES = 0xC0                         # graphic 48's first tile (map_tile_lookup, src/core.c)
BRIGHT, DIM = 5, 2                   # floor 8's bone palette, and its floor palette
MON0 = SYM["encounter"] + 1
M_TYPE, M_HP, M_TARGET_HP = 0, 14, 16
BATTLE_MENU = 2                      # BATTLE_STATE_MENU, src/battle.h

ROARS = {"sfx_monster_attack1": "attack1", "sfx_monster_attack2": "attack2"}
# (name, tile, MonsterType, (namespace, key) of its line, roar)
FIGHTS = [
    ("goblin", (2, 27), 1, ("floor_common", "growl"), "attack1"),
    ("owlbear", (14, 27), 4, ("floor2", "boss_msg"), "attack2"),
    ("gelatinous cube", (3, 22), 5, ("floor3", "boss"), "attack2"),
    ("displacer beast", (13, 22), 6, ("floor4", "boss"), "attack2"),
    ("death knight", (4, 17), 8, ("floor5", "boss"), "attack2"),
    ("mind flayer", (12, 17), 9, ("floor6", "boss"), "attack2"),
]


def drawn(g, tile):
    """(first BG tile, palettes) the screen draws map tile `tile` with."""
    x, y = tile
    return vram_byte(g, screen_cells(g, x, y)[0], 0), drawn_palettes(g, x, y)


def enter(g, tile):
    """Step onto `tile` from the tile to its right. Returns (pages read while
    the map was up, roars heard, whether a battle started after them)."""
    heard = sounds_heard(g)
    mark = len(heard)
    g.step("LEFT")
    pages = read_textbox(g) if g.ms() in (MS["TEXTBOX"], MS["TEXTBOX_OPEN"]) else []
    roars = [ROARS[sound] for _, sound in heard[mark:] if sound in ROARS]
    fought = g.wait_for(lambda: g.gs() == GS["BATTLE"] and g.rd8(SYM["battle_state"]) == BATTLE_MENU, 900)
    return pages, roars, fought


g, _ = start_on(8, class_id=MONK, level=60, abilities=0x3F, tag="t45")
save_checkpoint(g, "t45_floor8.state")

for name, (x, y), mtype, line, roar in FIGHTS:
    load_checkpoint(g, "t45_floor8.state")
    chk(f"T45 {name}: floor 8 loads with the hero beside the fight",
        reenter_floor(g, 8, x + 1, y), f"pos={g.pos()}")
    tile, pals = drawn(g, (x, y))
    chk(f"T45 {name}: its tile shows bright bones", tile == BONES and pals == [BRIGHT],
        f"tile={tile:#04x} palettes={pals}")
    pages, roars, fought = enter(g, (x, y))
    want = [normalize(p) for p in expected_pages(*line)]
    chk(f"T45 {name}: stepping on shows its home floor's line before the fight",
        [normalize(p) for p in pages] == want, f"pages={pages} want={want}")
    chk(f"T45 {name}: with its home floor's roar", roars == [roar], f"roars={roars}")
    chk(f"T45 {name}: then the fight starts against it",
        fought and g.rd8(MON0 + M_TYPE) == mtype,
        f"fought={fought} type={g.rd8(MON0 + M_TYPE)} want={mtype}")

# Beat the goblin and look at its bones.
name, goblin, _, line, _ = FIGHTS[0]
load_checkpoint(g, "t45_floor8.state")
reenter_floor(g, 8, goblin[0] + 1, goblin[1])
pages, roars, fought = enter(g, goblin)
keep_alive(g)
g.wr16(MON0 + M_HP, 1)
g.wr16(MON0 + M_TARGET_HP, 1)
result = resolve_battle(g)
dismiss_after_win(g)
chk("T45 the goblin falls", result == "victory" and g.pos() == goblin, f"result={result} pos={g.pos()}")
tile, pals = drawn(g, goblin)
chk("T45 the beaten goblin's bones stay, in the floor's colors", tile == BONES and pals == [DIM],
    f"tile={tile:#04x} palettes={pals}")
others = {(xx, yy): tile_overrides(g).get((0, xx, yy)) for _, (xx, yy), *_ in FIGHTS[1:]}
chk("T45 the five fights not yet won keep their bright bones", all(v is None for v in others.values()),
    str(others))
g.step("RIGHT")
pages, roars, fought = enter(g, goblin)
chk("T45 the beaten goblin's tile starts nothing", not pages and not roars and not fought
    and g.gs() == GS["WORLD_MAP"], f"pages={pages} roars={roars} fought={fought} gs={g.gs()}")

menu_save(g, chk, "T45 a save on the beaten goblin's tile")
g = reload_slot(g, 0, "t45_reload")
tile, pals = drawn(g, goblin)
chk("T45 loading the save keeps the goblin's bones dim", tile == BONES and pals == [DIM],
    f"tile={tile:#04x} palettes={pals}")
g.step("RIGHT")
pages, roars, fought = enter(g, goblin)
chk("T45 and its tile still starts nothing", not pages and not fought, f"pages={pages} fought={fought}")

chk("T45 a fresh load of the floor, as after a death", reenter_floor(g, 8, goblin[0] + 1, goblin[1]),
    f"pos={g.pos()}")
tile, pals = drawn(g, goblin)
chk("T45 brings the goblin back with bright bones", tile == BONES and pals == [BRIGHT],
    f"tile={tile:#04x} palettes={pals}")
pages, roars, fought = enter(g, goblin)
chk("T45 and its line and fight with them",
    [normalize(p) for p in pages] == [normalize(p) for p in expected_pages(*line)] and fought,
    f"pages={pages} fought={fought}")
g.close()
chk.summary()
