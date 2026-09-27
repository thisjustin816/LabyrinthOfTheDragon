"""T13 - the hero select panel and the name entry screen.

Checks every class's panel against its own source (name, description, and
level 4 stats), then the name entry field's class default and typing a
custom name.
"""
from lotd import *
chk = Checker("t13_name_entry")
g = Game(tag="t13")
g.boot_to_save_select(); g.save_select_pick(0)
assert g.gs() == GS["HERO_SELECT"], g.gs()

# The pick screen names the highlighted class and says what it is, in a panel
# on rows 11-16 built from the art's own frame tiles.
def panel(row):
    return g.bg_text(2, row, 16).rstrip()
chk("T13 hero panel names the first class", panel(12) == "DRUID", repr(panel(12)))
chk("T13 hero panel describes it", len(panel(13)) > 4 and len(panel(14)) > 4,
    repr((panel(13), panel(14))))
chk("T13 hero panel shows the class's starting stats",
    panel(15).startswith("HP:") and panel(16).startswith("ATK:"),
    repr((panel(15), panel(16))))
_c = [g.pb.tilemap_background[c, r] for r in (11, 17) for c in (1, 18)]
chk("T13 hero panel is framed with the art's corner tile", all(t == 0x90 for t in _c),
    str([hex(t) for t in _c]))
g.press("right", wait=14)
chk("T13 moving the pick changes the panel", panel(12) == "FIGHTER", repr(panel(12)))
g.press("left", wait=14)
chk("T13 and back again", panel(12) == "DRUID", repr(panel(12)))

# Every class's panel against its sources: the description exactly as
# src/hero_select.c spells it, since draw_text drops anything past 16
# characters without a word, and the level 4 stats from assets/tables.csv.
import os, re, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "playtest"))
from heroes import stats_for
_src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, os.pardir, "src", "hero_select.c")).read()
classes = re.findall(r'\{ "(\w+)",\s*"([^"]*)",\s*"([^"]*)",', _src)
chk("T13 src/hero_select.c lists four classes", len(classes) == 4, str(classes))
for k, (name, line1, line2) in enumerate(classes):
    st = stats_for(k, 4)
    # The druid and the sorcerer are the game's magic classes (is_magic_class
    # in src/player.h), so their pool is labeled MP everywhere else it shows.
    pool = "MP" if name in ("DRUID", "SORCERER") else "SP"
    want = {"HP": st["max_hp"], pool: st["max_sp"], "ATK": st["atk_base"], "DEF": st["def_base"]}
    shown = [panel(r) for r in range(12, 17)]
    got = {key: int(v) for key, v in re.findall(r"(HP|SP|MP|ATK|DEF):(\d+)", " ".join(shown[3:]))}
    chk(f"T13 {name}: the panel shows its name and whole description", shown[:3] == [name, line1, line2], repr(shown[:3]))
    chk(f"T13 {name}: and its level 4 stats from the tables, with its pool labeled {pool}", got == want, f"shown {got}, tables {want}")
    g.press("right", wait=14)
chk("T13 four steps right wrap back to the first class", panel(12) == "DRUID", repr(panel(12)))

g.press("b", wait=14)
chk("T13 B on hero select goes back to the file screen", g.wait_for(lambda: g.gs() == GS["SAVE_SELECT"], 120), f"gs={g.gs()}")
chk("T13 and every sprite is hidden on the way out", not any(0 < g.rd8(0xFE00 + 4 * k) < 160 for k in range(40)))
g.tick(10); g.save_select_pick(0)
chk("T13 the file screen leads back to hero select", g.wait_for(lambda: g.gs() == GS["HERO_SELECT"], 120), f"gs={g.gs()}"); g.tick(6)
g.press("a", wait=12)
chk("T13 A on hero select opens the name entry screen", g.wait_for(lambda: g.gs() == GS["NAME_ENTRY"], 120), f"gs={g.gs()}")
g.tick(6); g.shot("name_entry_default")
def field():  # the six-cell name field on row 2 from col 7; empty cells are the art's low underscore (0xDC)
    return [g.pb.tilemap_background[7 + k, 2] for k in range(6)]
def field_text():
    return "".join(chr(t - 0x80) if 0xA0 <= t < 0xFF and t != 0xDC else "_" for t in field())
chk("T13 field pre-filled with the class default 'Lyra' plus two underscores", field_text() == "Lyra__", field_text())
# No hint box at all: the symbol row is 12 wide but the art's grid box is cut
# for 16, so four cells already sit blank after the last symbol. END lives
# there as a real, selectable 13th cell in that row, the way Pokemon's naming
# screen tucks its own END graphic into the letter grid rather than
# explaining a button below it.
# PyBoy reports the blank tile as 0x100, not 0x00: this game addresses BG
# tiles in signed mode, and tile 0 there sits at 0x9000, a different pattern
# table slot than tile 0 in unsigned mode. Every other tile check in this file
# reads through core.h's FONT_OFFSET instead, so this one spot needs it named.
BLANK_TILE = 0x100
chk("T13 rows 14-17 are bare backdrop, no hint box drawn",
    all(g.pb.tilemap_background[c, r] == BLANK_TILE for r in (14, 15, 16, 17) for c in (0, 19)),
    str([hex(g.pb.tilemap_background[c, r]) for r in (14, 15, 16, 17) for c in (0, 19)]))
chk("T13 END sits in the symbol row's own trailing gap", g.bg_text(15, 12, 3) == "END",
    repr(g.bg_text(15, 12, 3)))
chk("T13 and nowhere else in the row", g.bg_text(2, 12, 12) == "@%&'()*+,-./",
    repr(g.bg_text(2, 12, 12)))
def read_attr(game, col, row):
    vbk = game.pb.memory[0xFF4F]; game.pb.memory[0xFF4F] = 1
    try: return game.pb.memory[0x9800 + row * 32 + col]
    finally: game.pb.memory[0xFF4F] = vbk & 1
def attr(col, row):
    return read_attr(g, col, row)
chk("T13 grid cursor starts on 'A' (palette 6 highlight)", attr(2, 6) == 0x0E and attr(3, 6) == 0x0F, f"{attr(2,6):#04x} {attr(3,6):#04x}")
# delete the default
for _ in range(4): g.press("b", wait=6)
chk("T13 B x4 clears the field", field_text() == "______", field_text())
g.press("b", wait=6); chk("T13 B on an empty field is a no-op", field_text() == "______", field_text())
# type "K-o%": K = row 0 col 10; '-' = symbols row (4) col 9; 'o' = row 2 col 14; '%' = row 4 col 1
# The symbol row is 13 wide, not 12: its last slot is the END cell, not a
# 13th symbol.
ROWS = [16, 10, 16, 10, 13]
cur = [0, 0]
def goto(r, c):
    while cur[0] != r:
        g.press("down" if (r - cur[0]) % 5 <= 2 else "up", wait=5)
        cur[0] = (cur[0] + 1) % 5 if (r - cur[0]) % 5 <= 2 else (cur[0] - 1) % 5
        cur[1] = min(cur[1], ROWS[cur[0]] - 1)
    while cur[1] != c:
        step = 1 if (c - cur[1]) % ROWS[r] <= ROWS[r] // 2 else -1
        g.press("right" if step > 0 else "left", wait=5); cur[1] = (cur[1] + step) % ROWS[r]
def type_char(r, c):
    goto(r, c); g.press("a", wait=6)
type_char(0, 10)   # K
type_char(4, 9)    # -
type_char(2, 14)   # o
type_char(4, 1)    # %
chk("T13 typed 'K-o%' via the grid", field_text() == "K-o%__", field_text())
chk("T13 highlight moved with the cursor (row 12 col 3 = '%')", attr(3, 12) == 0x0E and attr(2, 6) == 0x0F, f"{attr(3,12):#04x}")
# fill to six and confirm the seventh is refused
type_char(0, 0); type_char(1, 9)   # A, Z
chk("T13 six characters fill the field", field_text() == "K-o%AZ", field_text())
type_char(0, 1); chk("T13 seventh character refused", field_text() == "K-o%AZ", field_text())
g.shot("name_entry_typed")
g.press("start", wait=12)
chk("T13 START starts the game", g.wait_for(lambda: g.gs() == GS["WORLD_MAP"] and g.ms() == MS["WAITING"], 600), f"gs={g.gs()} ms={g.ms()}")
PL = SYM["player"]; name = bytes(g.rd8(PL + k) for k in range(8)).split(b"\0")[0]
chk("T13 player.name is the typed name", name == b"K-o%AZ", repr(name))
sv = parse_save(g.slot(0)); chk("T13 initial save carries the typed name", sv["name"] == "K-o%AZ", sv["name"])

# the pause menu draws it literally: through sprintf, the '%' would start a format
g.press("start", wait=14); g.tick(4)
row = g.window_text(1, 0xF, 8); g.shot("pause_menu_typed_name")
chk("T13 pause menu shows the name with its '%' intact", row.startswith("K-o%AZ"), repr(row))
g.press("b", wait=14); g.wait_map_idle(200)
# save select shows it too
g = g.power_cycle(tag="t13b")
assert g.boot_to_save_select(); g.tick(10)
chk("T13 save select shows the typed name", g.slot_text(0).strip().startswith("K-o%AZ"), repr(g.slot_text(0)))
g.save_select_pick(0); g.wait_map_idle(900); g.tick(20)
chk("T13 reload works with the typed name", g.ms() == MS["WAITING"], str(g.ms()))
g.close()

g2 = Game(tag="t13c")
g2.boot_to_save_select(); g2.save_select_pick(0)   # -> hero select
for _ in range(2): g2.press("right", wait=6)       # hero 2 = monk
g2.press("a", wait=12)
assert g2.wait_for(lambda: g2.gs() == GS["NAME_ENTRY"], 120), g2.gs()
g2.tick(6)
for _ in range(6): g2.press("b", wait=6)   # clear the class default
for _ in range(4): g2.press("down", wait=8)  # onto the symbol row
for _ in range(15):
    if read_attr(g2, 15, 12) == 0x0E:
        break
    g2.press("right", wait=6)
chk("T13c reached the END cell", read_attr(g2, 15, 12) == 0x0E, "")
g2.press("a", wait=40)
# The new game opens on floor 1's intro box, which has to close first.
chk("T13c A on END confirms, same as START",
    g2.wait_for(lambda: g2.gs() == GS["WORLD_MAP"] and not g2.rd8(SYM["execute_on_init"]), 600)
    and g2.close_textboxes() == MS["WAITING"],
    f"gs={g2.gs()} ms={g2.ms()}")
name2 = bytes(g2.rd8(SYM["player"] + k) for k in range(8)).split(b"\0")[0]
chk("T13c an empty field still keeps the class default", name2 == b"Ken",
    repr(name2))
g2.close(); chk.summary()
