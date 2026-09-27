"""T17 - issue #70: healing items can be used from the pause menu.

The menu is a 2x2 grid:

    RETURN   ITEMS
    SAVE     QUIT

ITEMS opens a picker in the message row rather than a submenu, so no new menu
art was needed. Only potion, ether and elixir appear: the buffs and the remedy
live in encounter.player_status_effects, which reset_encounter() wipes when a
fight starts, so drinking one outside a battle would do nothing.
"""
from lotd import *

chk = Checker("t17_field_items")
PL, MM, INV = SYM["player"], SYM["map_menu"], SYM["inventory"]
MENU_ROW_1, MENU_ROW_2, MSG_ROW = 28, 29, 30
CURSOR_RETURN, CURSOR_SAVE, CURSOR_QUIT, CURSOR_ITEMS = 0, 1, 2, 3
STATE_OPEN, STATE_ITEMS = 1, 4


g = Game(tag="t17")
g.boot_to_save_select(); g.save_select_pick(0); g.hero_select_pick(0); g.tick(20)

# potion x3, ether x2, elixir x1; hurt and out of SP so everything is usable
for slot, qty in ((0, 3), (1, 2), (5, 1)):
    g.wr8(INV + 4 * slot + 1, qty)
g.wr16(PL + POFF["hp"], 5)
g.wr16(PL + POFF["sp"], 1)

g.press("start", wait=16)
row1 = g.window_text(0, MENU_ROW_1, 20)
row2 = g.window_text(0, MENU_ROW_2, 20)
print("menu row 1:", repr(row1))
print("menu row 2:", repr(row2))
chk("T17 row 1 shows RETURN and ITEMS", "RETURN" in row1 and "ITEMS" in row1, repr(row1))
chk("T17 row 2 shows SAVE and QUIT", "SAVE" in row2 and "QUIT" in row2, repr(row2))
g.shot("menu_with_items")

# --- the 2x2 grid walks properly
g.press("right", wait=10)
chk("T17 RIGHT from RETURN reaches ITEMS", g.rd8(MM + 1) == CURSOR_ITEMS, str(g.rd8(MM + 1)))
g.press("down", wait=10)
chk("T17 DOWN from ITEMS reaches QUIT", g.rd8(MM + 1) == CURSOR_QUIT, str(g.rd8(MM + 1)))
g.press("left", wait=10)
chk("T17 LEFT from QUIT reaches SAVE", g.rd8(MM + 1) == CURSOR_SAVE, str(g.rd8(MM + 1)))
g.press("up", wait=10)
chk("T17 UP from SAVE reaches RETURN", g.rd8(MM + 1) == CURSOR_RETURN, str(g.rd8(MM + 1)))
g.press("right", wait=10)

# --- the picker
g.press("a", wait=16)
msg = g.window_text(0, MSG_ROW, 20)
chk("T17 A on ITEMS opens the picker", g.rd8(MM) == STATE_ITEMS, str(g.rd8(MM)))
chk("T17 the picker starts on the potion", "Potion" in msg, repr(msg))
# The cycling arrows are drawn either side of the name while there is more than
# one usable item to cycle to. '<' is the redrawn left triangle and its mirror
# sits in font cell 0x0E, which window_text() cannot represent (it renders any
# cell that isn't text as '?'), so these read the window tiles directly.
ARROW_L_TILE, ARROW_R_TILE = 0x80 + ord("<"), 0x80 + 0x0E


def msg_row_tiles():
    tm = g.pb.tilemap_window
    return [tm[c, MSG_ROW] for c in range(20)]


arrows = msg_row_tiles()
chk("T17 both cycle arrows show with three usable items",
    ARROW_L_TILE in arrows and ARROW_R_TILE in arrows,
    str([hex(t) for t in arrows]))
g.shot("item_picker")

g.press("right", wait=10)
chk("T17 RIGHT cycles to the ether", "Ether" in g.window_text(0, MSG_ROW, 20),
    repr(g.window_text(0, MSG_ROW, 20)))
g.press("right", wait=10)
chk("T17 RIGHT again reaches the elixir", "Elixir" in g.window_text(0, MSG_ROW, 20),
    repr(g.window_text(0, MSG_ROW, 20)))
g.press("left", wait=10); g.press("left", wait=10)
chk("T17 LEFT cycles back to the potion", "Potion" in g.window_text(0, MSG_ROW, 20),
    repr(g.window_text(0, MSG_ROW, 20)))

# --- drinking one
hp0, qty0 = g.rd16(PL + POFF["hp"]), g.rd8(INV + 1)
g.press("a", wait=24)
hp1, qty1 = g.rd16(PL + POFF["hp"]), g.rd8(INV + 1)
print("HP %d -> %d, potions %d -> %d" % (hp0, hp1, qty0, qty1))
chk("T17 drinking a potion restores HP", hp1 > hp0, f"{hp0} -> {hp1}")
chk("T17 drinking a potion consumes one", qty1 == qty0 - 1, f"{qty0} -> {qty1}")
chk("T17 the picker stays on the potion while it is still useful",
    "Potion" in g.window_text(0, MSG_ROW, 20), repr(g.window_text(0, MSG_ROW, 20)))
g.shot("item_used")

# --- ether restores SP
g.press("right", wait=10)
sp0 = g.rd16(PL + POFF["sp"])
g.press("a", wait=24)
sp1 = g.rd16(PL + POFF["sp"])
chk("T17 drinking an ether restores SP", sp1 > sp0, f"{sp0} -> {sp1}")

# --- B backs out to the options without closing the menu
g.press("b", wait=12)
chk("T17 B leaves the picker but keeps the menu open", g.rd8(MM) == STATE_OPEN,
    str(g.rd8(MM)))
chk("T17 the message row is cleared on the way out",
    g.window_text(0, MSG_ROW, 20).strip("~? ") == "",
    repr(g.window_text(0, MSG_ROW, 20)))

# --- nothing usable: full health, no consumables worth drinking
g.wr16(PL + POFF["hp"], g.rd16(PL + POFF["max_hp"]))
g.wr16(PL + POFF["sp"], g.rd16(PL + POFF["max_sp"]))
# backing out of the picker leaves the cursor on ITEMS, so just press A again
chk("T17 backing out keeps the cursor on ITEMS", g.rd8(MM + 1) == CURSOR_ITEMS,
    str(g.rd8(MM + 1)))
g.press("a", wait=16)
msg = g.window_text(0, MSG_ROW, 20)
# Holding a full stack of ethers on a full SP bar reads as a bug if the menu
# just says there is nothing to use, so the two cases say different things.
chk("T17 with items but full bars the refusal says none would help",
    g.rd8(MM) == STATE_OPEN and "NONE WOULD HELP" in msg,
    f"state={g.rd8(MM)} {msg!r}")

# --- carrying nothing at all is a different message
for slot in (0, 1, 5):
    g.wr8(INV + 4 * slot + 1, 0)
g.press("a", wait=16)
msg = g.window_text(0, MSG_ROW, 20)
chk("T17 with an empty bag the refusal says there are no items",
    g.rd8(MM) == STATE_OPEN and "NO ITEMS TO USE" in msg,
    f"state={g.rd8(MM)} {msg!r}")

# --- one usable item: nowhere to cycle, so the arrows go away
g.wr8(INV + 4 * 0 + 1, 2)                 # potions only
g.wr16(PL + POFF["hp"], 5)               # hurt, so the potion is usable
g.wr16(PL + POFF["sp"], g.rd16(PL + POFF["max_sp"]))
g.press("a", wait=16)
msg = g.window_text(0, MSG_ROW, 20)
chk("T17 a single usable item opens the picker on it",
    g.rd8(MM) == STATE_ITEMS and "Potion" in msg, f"state={g.rd8(MM)} {msg!r}")
arrows = msg_row_tiles()
chk("T17 and drops both cycle arrows",
    ARROW_L_TILE not in arrows and ARROW_R_TILE not in arrows,
    str([hex(t) for t in arrows]))
g.shot("item_picker_single")
g.press("b", wait=12)

# --- and the menu still closes normally
g.press("b", wait=14)
chk("T17 B closes the pause menu", g.gs() == GS["WORLD_MAP"] and g.ms() != MS["MENU"],
    f"gs={g.gs()} ms={g.ms()}")

g.close()
chk.summary()
