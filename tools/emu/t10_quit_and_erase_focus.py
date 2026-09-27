"""T10 - the pause menu's layout, the QUIT confirmation, and the save select
screen's ERASE focus colors.

Covers the menu's four-option grid and icons, the QUIT prompt's yes/no
answers and what backing out of it restores, and ERASE's gold and red focus
states.
"""
from lotd import *
chk = Checker("t10_quit_and_erase_focus")
g = Game(tag="t10")
g.boot_to_save_select(); g.save_select_pick(0); g.hero_select_pick(0); g.tick(20)
start = g.pos()
MENU_ROW_1, MENU_ROW_2, MSG_ROW = 28, 29, 30      # BG-map rows of the pause menu (drawn at row 14)
MM = SYM["map_menu"]                              # MapMenu { state, cursor }
def menu_cursor(): return g.rd8(MM + 1)
def menu_state(): return g.rd8(MM)
# --- one step so an unsaved position differs from the initial save
g.step("UP"); g.wait_map_idle(200); moved = g.pos()
chk("T10 walked one step off the initial save position", moved != start, f"{start} -> {moved}")
# --- pause menu layout
g.press("start", wait=14)
chk("T10 START opens the pause menu", g.ms() == MS["MENU"], str(g.ms()))
g.shot("pause_menu")
row1 = g.window_text(0, MENU_ROW_1, 20); row2 = g.window_text(0, MENU_ROW_2, 20); row3 = g.window_text(0, MSG_ROW, 20)
print("menu rows:", repr(row1), repr(row2), repr(row3))


# Frozen here, before anything reuses the name: row1 is reassigned further down
# to hold the quit prompt's row, so comparing against row1 by name would test
# the restored menu against "QUIT THE GAME?" and could never pass.
FRESH_ROW1 = row1


def blanks(s):
    """The menu art's blank tile (0xFE, read as '~') and draw_text's space
    (0xA0, read as ' ') both render empty, and a redraw swaps one for the
    other, so a row is compared with the two treated as the same."""
    return s.replace("~", " ")


def row1_restored():
    """Backing out of the quit prompt has to put the top row back exactly.
    A substring test is not enough: the prompt's "QUIT THE GAME?" left its E
    between the two labels, and "RETURN" is a substring of "RETURNE"."""
    return blanks(g.window_text(0, MENU_ROW_1, 20)) == blanks(FRESH_ROW1)
# Each option has its own icon (VRAM tile = font char + 0x80). QUIT is the
# door glyph (0x1D) the battle menu's FLEE also shows and RETURN (0x1F) is that
# door mirrored, so the two read as a pair. SAVE is a disk (0x1C) and ITEMS a
# flask (0x7C), drawn to match their weight.
ICON_RETURN, ICON_SAVE, ICON_QUIT, ICON_ITEMS = 0x9F, 0x9C, 0x9D, 0xFC
tm = g.pb.tilemap_window
chk("T10 row 1 shows RETURN and ITEMS with their icons", "RETURN" in row1 and "ITEMS" in row1 and tm[3, MENU_ROW_1] == ICON_RETURN and tm[12, MENU_ROW_1] == ICON_ITEMS, f"{row1!r} tiles[3]={tm[3, MENU_ROW_1]:02X} tiles[12]={tm[12, MENU_ROW_1]:02X}")
# "RETURN" must not survive on row 2: the art bakes it there and SAVE's padding
# is what clears it.
chk("T10 row 2 shows SAVE and QUIT with their icons", "SAVE" in row2 and "QUIT" in row2 and "RETURN" not in row2 and tm[3, MENU_ROW_2] == ICON_SAVE and tm[12, MENU_ROW_2] == ICON_QUIT, f"{row2!r} tiles[3]={tm[3, MENU_ROW_2]:02X} tiles[12]={tm[12, MENU_ROW_2]:02X}")
icons = [tm[3, MENU_ROW_1], tm[12, MENU_ROW_1], tm[3, MENU_ROW_2], tm[12, MENU_ROW_2]]
chk("T10 the four icons on screen are all different", len(set(icons)) == 4, str([f"{t:02X}" for t in icons]))
chk("T10 message row blank", row3.strip("~? ") == "", repr(row3))
chk("T10 cursor starts on RETURN", menu_cursor() == 0, str(menu_cursor()))
# --- navigation. The options are a 2x2 grid, ordered so the most-reached
#   option is nearest the starting cursor and QUIT is furthest:
#       RETURN(0)  ITEMS(3)
#       SAVE(1)    QUIT(2)
#   UP / DOWN swap rows and LEFT / RIGHT swap columns, each keeping the other
#   axis. Enum values are not grid order, hence the scattered numbers.
seq = [("right", 3), ("down", 2), ("up", 3), ("left", 0),
       ("down", 1), ("left", 2), ("down", 3), ("right", 0)]
ok = True; trace = []
for btn, want in seq:
    g.press(btn, wait=8); got = menu_cursor(); trace.append((btn, got)); ok = ok and got == want
chk("T10 D-pad walks the RETURN/ITEMS/SAVE/QUIT grid as designed", ok, str(trace))
# hand sprite (sprites 16-19) follows the cursor: SAVE sits one row below
# RETURN in the same column. The walk above ends on RETURN.
ret_y = g.rd8(0xC000 + 4 * 16); ret_x = g.rd8(0xC001 + 4 * 16)
g.press("down", wait=8); save_y = g.rd8(0xC000 + 4 * 16); save_x = g.rd8(0xC001 + 4 * 16)
chk("T10 hand sprite: SAVE is 8px below RETURN, same x", save_y == ret_y + 8 and save_x == ret_x, f"RETURN ({ret_x},{ret_y}) SAVE ({save_x},{save_y})")
# --- QUIT asks first, as a YES / NO pick on the option rows
g.press("right", wait=8)
chk("T10 QUIT is the far corner from the starting cursor", menu_cursor() == 2, str(menu_cursor()))
g.press("a", wait=12)
row1 = g.window_text(0, MENU_ROW_1, 20); row2 = g.window_text(0, MENU_ROW_2, 20)
row3 = g.window_text(0, MSG_ROW, 20)
print("after A on QUIT:", repr(row1), repr(row2), repr(row3), "state", menu_state())
# The question replaces the top option row and the answers the bottom one. The
# hand cannot reach the message row (16px tall, last row on screen), so the
# answers have to sit where the hand already goes.
chk("T10 A on QUIT asks the question on the top option row",
    "QUIT THE GAME?" in row1 and menu_state() == 2, repr(row1))
chk("T10 YES and NO replace SAVE and QUIT, in the same two columns",
    "YES" in row2 and "NO" in row2 and "SAVE" not in row2 and "QUIT" not in row2, repr(row2))
chk("T10 the prompt leaves the message row alone", row3.strip("~? ") == "", repr(row3))
# NO is the answer the cursor is already on, so a stray A costs nothing.
chk("T10 the hand starts on NO", menu_cursor() == 2, str(menu_cursor()))
g.shot("quit_prompt")
no_y = g.rd8(0xC000 + 4 * 16); no_x = g.rd8(0xC001 + 4 * 16)
g.press("left", wait=8)
yes_y = g.rd8(0xC000 + 4 * 16); yes_x = g.rd8(0xC001 + 4 * 16)
chk("T10 LEFT moves the hand to YES: same row, left column",
    menu_cursor() == 1 and yes_y == no_y and yes_x < no_x,
    f"NO ({no_x},{no_y}) YES ({yes_x},{yes_y}) cursor={menu_cursor()}")
g.shot("quit_prompt_yes")
g.press("right", wait=8)
chk("T10 RIGHT moves it back to NO", menu_cursor() == 2, str(menu_cursor()))
g.press("a", wait=12)
chk("T10 A on NO withdraws the prompt and puts the options back",
    menu_state() == 1 and "SAVE" in g.window_text(0, MENU_ROW_2, 20)
    and "QUIT" in g.window_text(0, MENU_ROW_2, 20)
    and row1_restored() and menu_cursor() == 2,
    f"state={menu_state()} cursor={menu_cursor()} "
    f"{g.window_text(0, MENU_ROW_1, 20)!r} {g.window_text(0, MENU_ROW_2, 20)!r}")
g.press("a", wait=12); chk("T10 prompt shown again", menu_state() == 2)
g.press("up", wait=8)
chk("T10 UP also backs out of the prompt, top row intact",
    menu_state() == 1 and "QUIT" in g.window_text(0, MENU_ROW_2, 20) and row1_restored(),
    f"state={menu_state()} {g.window_text(0, MENU_ROW_1, 20)!r}")
g.press("a", wait=12); chk("T10 prompt shown a third time", menu_state() == 2)
g.press("b", wait=14)
chk("T10 B backs out to the options rather than closing the menu, top row intact",
    menu_state() == 1 and g.ms() == MS["MENU"] and row1_restored(),
    f"state={menu_state()} ms={g.ms()} {g.window_text(0, MENU_ROW_1, 20)!r}")
g.press("b", wait=14); g.wait_map_idle(200)
chk("T10 a second B closes the menu, back on the map", g.gs() == GS["WORLD_MAP"] and g.ms() == MS["WAITING"] and g.pos() == moved, f"gs={g.gs()} ms={g.ms()} pos={g.pos()}")
g.step("UP"); g.wait_map_idle(200)
chk("T10 hero still moves after canceling", g.pos() != moved, str(g.pos()))
# --- confirm QUIT: pick YES, fade out, then the title screen
g.press("start", wait=14); g.press("down", wait=8); g.press("right", wait=8)
g.press("a", wait=12); g.press("left", wait=8); g.press("a", wait=4)
chk("T10 second A leaves the menu state", menu_state() == 3 or g.ms() in (MS["FADE_OUT"], MS["QUIT"]), f"menu_state={menu_state()} ms={g.ms()}")
ok = g.wait_for(lambda: g.gs() == GS["TITLE"], 120)
chk("T10 quitting lands on the title screen within 2s of confirming", ok, f"gs={g.gs()} ms={g.ms()}")
g.tick(60, True); g.shot("title_after_quit")
# A state flag can read TITLE over a black screen, so look at the frame: the
# title art paints several colors, a failed redraw leaves one or two.
title_colors = len(set(g.pb.screen.image.convert("RGB").getdata()))
chk("T10 the title screen is actually drawn, not a blank frame", title_colors >= 4,
    f"{title_colors} distinct colors")
# From the title the save select is one START away, the same route as at boot.
chk("T10 START on the title reaches the save select", g.boot_to_save_select(),
    f"gs={g.gs()}")
g.tick(10); g.shot("save_select_after_quit")
chk("T10 save select header drawn (BG map 0x9800, scroll reset)", "CHOOSE YOUR FILE" in g.bg_text(0, 1, 20), repr(g.bg_text(0, 1, 20)))
chk("T10 slot 1 shows the character name", g.bg_text(6, 4, 6).strip() != "" and not g.slot_is_empty(0), repr(g.slot_text(0)))
chk("T10 slots 2/3 empty", g.slot_is_empty(1) and g.slot_is_empty(2), repr([g.slot_text(1), g.slot_text(2)]))
chk("T10 sprites enabled again after the fade", g.rd8(0xFF40) & 0x02 == 0x02 and g.rd8(0xFF40) & 0x08 == 0, f"LCDC={g.rd8(0xFF40):02X}")
chk("T10 BG scroll reset", g.rd8(0xFF42) == 0 and g.rd8(0xFF43) == 0, f"SCY={g.rd8(0xFF42)} SCX={g.rd8(0xFF43)}")
# --- ERASE focus: label goes gold, cursor sprite beside it, hint changes
def label_colors():
    # The ERASE / BACK label sits on row 16 across cols 11-17: x 88-143,
    # y 128-135.
    img = g.pb.screen.image.convert("RGB")
    return {img.getpixel((x, y)) for x in range(88, 144) for y in range(128, 136)}
g.tick(1, True); gray = label_colors()
while g.get("cursor") != 3:
    g.press("down", wait=6)
g.tick(2, True); g.shot("save_select_erase_focused")
gold = label_colors()
print("label colors on slot:", sorted(gray)[:6], "| on ERASE:", sorted(gold)[:6])
chk("T10 ERASE label recolored when the cursor lands on it", gold != gray, "")
chk("T10 ERASE label shows a warm gold tone", any(r > 200 and b < 180 and r - b > 40 for (r, gcol, b) in gold), str(sorted(gold)[:8]))
chk("T10 no stray cursor sprite", g.rd8(0xC000) == 0 and g.rd8(0xC001) == 0, f"sprite0 y={g.rd8(0xC000)} x={g.rd8(0xC001)}")
# arm erase mode: cursor jumps to slot 1, label BACK (red), hint A:ERASE B:CANCEL
g.press("a", wait=10); g.tick(1, True)
chk("T10 erase armed: cursor on slot 1, label BACK", g.get("cursor") == 0 and g.action_label() == "BACK", f"cursor={g.get('cursor')} label={g.action_label()!r}")
red = label_colors(); chk("T10 armed BACK label is red-toned, not gold", any(r > 120 and gcol < 80 and b < 80 for (r, gcol, b) in red) and red != gold, str(sorted(red)[:8]))
g.shot("save_select_erase_armed")
# move onto BACK: gold focus + A:CANCEL; A cancels erase mode and leaves the cursor on ERASE
g.press("up", wait=8); g.tick(1, True)
chk("T10 focused BACK is gold again", label_colors() == gold or any(r > 200 and b < 180 for (r, gcol, b) in label_colors()), "")
g.press("a", wait=10)
chk("T10 A on BACK cancels erase mode (label back to ERASE)", g.action_label() == "ERASE", repr(g.action_label()))
# --- load slot 1 again: position must be the initial save's (quit did not save)
g.save_select_pick(0); g.wait_map_idle(900); g.tick(20)
chk("T10 reload after quit -> map idle at the *saved* position (quit did not save)", g.gs() == GS["WORLD_MAP"] and g.ms() == MS["WAITING"] and g.pos() == start, f"pos={g.pos()} saved={start}")
chk("T10 bank 2 on the map after quit/reload", g.get("_current_bank") == 2, str(g.get("_current_bank")))
g.step("UP"); g.wait_map_idle(200)   # DOWN from the start tile is a wall; T1 walks UP
chk("T10 hero moves after quit/reload", g.pos() != start, str(g.pos()))
# save, quit, reload: saved position sticks
menu_save(g, chk, "T10 save after reload"); p2 = g.pos()
g.press("start", wait=14); g.press("down", wait=8); g.press("right", wait=8)
g.press("a", wait=12); g.press("left", wait=8); g.press("a", wait=4)
chk("T10 second quit lands on the title", g.wait_for(lambda: g.gs() == GS["TITLE"], 120),
    f"gs={g.gs()}")
chk("T10 and START from the title reaches save select", g.boot_to_save_select(), f"gs={g.gs()}")
g.tick(10); g.save_select_pick(0); g.wait_map_idle(900); g.tick(20)
chk("T10 reload after save+quit -> saved position", g.pos() == p2 and g.ms() == MS["WAITING"], f"{g.pos()} vs {p2}")
g.close(); chk.summary()
