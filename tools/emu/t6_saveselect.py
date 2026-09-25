"""T6 - the save select screen: slots, the clock, erasing a file, and the
version guard.

Covers a new game in each slot, the clock's HH:MM formatting, the erase
confirmation prompt, and a save written with an old `SAVE_VERSION` reading
back as empty.
"""
import json
from lotd import *
chk = Checker("t6_saveselect")

def new_game_in_slot(g, slot, hero):
    assert g.gs() == GS["SAVE_SELECT"], g.gs()
    g.save_select_pick(slot)
    chk(f"T6 slot {slot} NEW -> hero select", g.gs() == GS["HERO_SELECT"], g.gs())
    chk(f"T6 hero select -> map (hero {hero})", g.hero_select_pick(hero))
    g.tick(20)
    chk(f"T6 active_save_slot == {slot}", g.get("active_save_slot") == slot, g.get("active_save_slot"))

def rows(g):
    out = []
    for i in range(3):
        # A used slot keeps its name at col 6 and its clock at col 13, with its
        # level and floor row under them; an empty one spreads a centered
        # placeholder across the whole interior.
        name = g.bg_text(6, 4 + 4 * i, 12)
        out.append(("NEW" if g.slot_is_empty(i) else name[:6].strip(),
                    name[7:12], g.bg_text(6, 5 + 4 * i, 12)))
    return out

# --- new game in slot 0, immediately reset without an in-game save ------------
g = Game(tag="t6")
chk("T6 boot", g.boot_to_save_select())
new_game_in_slot(g, 0, 0)     # Lyra
g = g.power_cycle("t6b"); chk("T6 boot after immediate reset", g.boot_to_save_select()); g.tick(10)
r = rows(g); print("rows:", r)
chk("T6 slot 1 populated by start_game's initial save (name Lyra), others NEW", r[0][0] == "Lyra" and r[1][0] == "NEW" and r[2][0] == "NEW", str(r))
g.save_select_pick(0)
chk("T6 load initial save -> idle at floor1 default (12,16)", g.wait_map_idle(900) and g.pos() == (12, 16), f"pos={g.pos()} ms={g.ms()}")
g.step("UP"); g.wait_map_idle(200)
chk("T6 can move after loading initial save", g.pos() == (12, 15), g.pos())

# --- fill slots 2 and 3 with other classes ----------------------------------
g = g.power_cycle("t6c"); g.boot_to_save_select(); g.tick(10)
new_game_in_slot(g, 1, 1)     # Deneth (fighter)
menu_save(g, chk, "T6 in-game save in slot 2")
chk("T6 in-game save wrote slot 2 not slot 1", parse_save(g.slot(1))["name"] == "Deneth" and parse_save(g.slot(0))["name"] == "Lyra", f"{parse_save(g.slot(1))['name']} / {parse_save(g.slot(0))['name']}")
g = g.power_cycle("t6d"); g.boot_to_save_select(); g.tick(10)
new_game_in_slot(g, 2, 3)     # Tyrion (sorcerer)
g = g.power_cycle("t6e"); g.boot_to_save_select(); g.tick(10)
r = rows(g); print("rows:", r)
chk("T6 three populated slots show Lyra/Deneth/Tyrion", [x[0] for x in r] == ["Lyra", "Deneth", "Tyrion"], str([x[0] for x in r]))
chk("T6 each slot shows the new hero's level 4 on floor 1", all(x[2] == "L4        B1" for x in r), str([x[2] for x in r]))
g.shot("save_select_three_slots")
# cursor movement: down x3 -> ERASE, up wraps
g.press("down"); g.press("down"); g.press("down")
chk("T6 cursor reaches ERASE (3)", g.get("cursor") == 3, g.get("cursor"))
g.shot("save_select_cursor_erase")
g.press("down"); chk("T6 DOWN from ERASE wraps to slot 1", g.get("cursor") == 0, g.get("cursor"))
g.press("up");   chk("T6 UP from slot 1 wraps to ERASE", g.get("cursor") == 3, g.get("cursor"))
lbl = g.action_label()
chk("T6 action label reads ERASE", lbl.strip() == "ERASE", repr(lbl))
# enter erase mode
g.press("a", wait=10)
lbl = g.action_label()
chk("T6 A on ERASE -> label BACK, cursor jumps to slot 1", lbl.strip() == "BACK" and g.get("cursor") == 0, f"{lbl!r} cursor={g.get('cursor')}")
g.shot("save_select_erase_mode")
# B cancels erase mode
g.press("b", wait=10)
lbl = g.action_label()
chk("T6 B in erase mode -> back to ERASE label, still on save select", lbl.strip() == "ERASE" and g.gs() == GS["SAVE_SELECT"], f"{lbl!r} gs={g.gs()}")
# --- erasing asks first, with NO lit. A twice on ERASE used to erase file 1:
# the first press arms erase mode with the cursor on file 1, and the second
# erased it at once.
def header():
    return g.bg_text(2, 1, 16)
def yes_label():
    return g.bg_text(2, 16, 7).strip()      # the YES box's face, cols 2-8
def label_colors(col):
    """The colors on row 16 across the seven label cells from `col`."""
    g.tick(1, True)
    img = g.pb.screen.image.convert("RGB")
    return {img.getpixel((x, y)) for x in range(col * 8, col * 8 + 56) for y in range(128, 136)}
def lit():
    """The answer shown lit, "YES" or "NO", from the two buttons' colors: the
    lit one gold, the other gray."""
    gold = lambda cs: any(r > 200 and b < 180 and r - b > 40 for (r, gc, b) in cs)
    gray = lambda cs: all(r == gc == b for (r, gc, b) in cs)
    yes, no = label_colors(2), label_colors(11)
    if gold(yes) and gray(no):
        return "YES"
    if gold(no) and gray(yes):
        return "NO"
    return f"neither: yes {sorted(yes)[:3]}, no {sorted(no)[:3]}"
def yes_box_gone():
    """The YES box's cells, cols 1-9 on rows 15-17, back to the backdrop, apart
    from the version drawn back over row 16's cols 1-9, which t59 checks."""
    g.tick(1, True)
    img = g.pb.screen.image.convert("RGB")
    backdrop = img.getpixel((0, 0))
    return all(img.getpixel((x, y)) == backdrop for x in range(8, 80) for y in range(120, 144)
               if not (128 <= y < 136))
lyra = g.slot(0)
g.press("down"); g.press("down"); g.press("down"); g.press("a", wait=10)   # ERASE -> erase mode, cursor -> 0
g.press("a", wait=10)                                                        # A on file 1
chk("T6 A twice on ERASE asks ERASE THIS FILE? instead of erasing file 1", header() == "ERASE THIS FILE?" and g.slot(0) == lyra, f"header={header()!r}, file 1 {'kept' if g.slot(0) == lyra else 'changed'}")
chk("T6 the prompt offers YES and NO with NO lit", yes_label() == "YES" and g.action_label() == "NO" and lit() == "NO", f"{yes_label()!r} {g.action_label()!r} lit={lit()}")
g.shot("save_select_erase_prompt")
g.press("left", wait=8)
chk("T6 LEFT lights YES", lit() == "YES", lit())
g.shot("save_select_erase_prompt_yes")
g.press("right", wait=8)
chk("T6 RIGHT lights NO again", lit() == "NO", lit())
g.press("a", wait=10)                                                        # NO
chk("T6 A on NO keeps the file and goes back to erase mode on it", g.slot(0) == lyra and header() == "CHOOSE YOUR FILE" and g.action_label() == "BACK" and g.get("cursor") == 0 and yes_box_gone(), f"header={header()!r} label={g.action_label()!r} cursor={g.get('cursor')}")
g.press("start", wait=10); g.press("start", wait=10)                         # asks, NO
chk("T6 START answers like A: NO keeps the file", g.slot(0) == lyra and header() == "CHOOSE YOUR FILE" and g.action_label() == "BACK", f"header={header()!r} label={g.action_label()!r}")
g.press("a", wait=10); g.press("left", wait=8); g.press("b", wait=10)       # asks, YES lit, B
chk("T6 B backs out of the prompt with YES lit and keeps the file", g.slot(0) == lyra and header() == "CHOOSE YOUR FILE" and g.action_label() == "BACK" and yes_box_gone(), f"header={header()!r} label={g.action_label()!r}")
g.press("a", wait=10); g.press("down", wait=8)                               # asks, DOWN
chk("T6 DOWN backs out of the prompt without moving the cursor", g.slot(0) == lyra and header() == "CHOOSE YOUR FILE" and g.get("cursor") == 0, f"header={header()!r} cursor={g.get('cursor')}")
# erase slot 2 (Deneth): YES
g.press("down", wait=8)                                                      # cursor -> slot 2
g.press("a", wait=10); g.press("left", wait=8)                               # asks, YES lit
g.press("a", wait=30)                                                        # erase slot 2 (full repaint)
r = rows(g); print("rows after erase:", r)
chk("T6 slot 2 erased -> NEW, slots 1/3 intact", r[1][0] == "NEW" and r[0][0] == "Lyra" and r[2][0] == "Tyrion", str([x[0] for x in r]))
chk("T6 SRAM slot 2 zeroed", all(b == 0 for b in g.slot(1)), "")
chk("T6 erase mode and the prompt end after erasing", g.action_label() == "ERASE" and header() == "CHOOSE YOUR FILE" and yes_box_gone(), f"label={g.action_label()!r} header={header()!r}")
g.shot("save_select_after_erase")
# erase mode on an EMPTY slot does nothing
g.press("down"); g.press("down"); g.press("down"); g.press("a", wait=10)   # erase mode
g.press("down", wait=8); g.press("a", wait=20)                                 # slot 2 (empty)
chk("T6 erasing an empty slot is rejected, with no prompt (still in erase mode, others intact)", g.action_label() == "BACK" and header() == "CHOOSE YOUR FILE" and parse_save(g.slot(0))["name"] == "Lyra" and parse_save(g.slot(2))["name"] == "Tyrion", f"label={g.action_label()!r} header={header()!r}")
g.press("b", wait=10)
# B (not in erase mode) -> title; START -> back to save select with same data
g.press("b", wait=20)
chk("T6 B from save select -> title screen", g.gs() == GS["TITLE"], g.gs())
g.tick(60); g.shot("title_after_B")
chk("T6 title reached TITLE_MAIN (not intro)", g.get("title_state") == 2, g.get("title_state"))
fire_done = g.wait_for(lambda: g.get("main_title_state") == 1, 600)
chk("T6 title fire animation finishes (MAIN_WAIT_FOR_INPUT)", fire_done, g.get("main_title_state"))
g.press("start", wait=20)
ok = g.wait_for(lambda: g.gs() == GS["SAVE_SELECT"], 300)
chk("T6 START from title returns to save select", ok, g.gs())
g.tick(10)
r = rows(g); chk("T6 slots intact after title round-trip", [x[0] for x in r] == ["Lyra", "NEW", "Tyrion"], str([x[0] for x in r]))
g.shot("save_select_after_title_roundtrip")
# load slot 3 (Tyrion), save in-game -> writes slot 3
g.save_select_pick(2)
chk("T6 load slot 3 -> idle", g.wait_map_idle(900))
chk("T6 active slot is 2 after load", g.get("active_save_slot") == 2, g.get("active_save_slot"))
g.step("UP"); g.wait_map_idle(200)
menu_save(g, chk, "T6 save into slot 3")
s = parse_save(g.slot(2))
chk("T6 slot 3 save has Tyrion at (12,15)", s["name"] == "Tyrion" and (s["map_x"] + 4, s["map_y"] + 4) == (12, 15), f"{s['name']} {s['map_x']+4},{s['map_y']+4}")
chk("T6 slot 1 untouched", parse_save(g.slot(0))["name"] == "Lyra" and (parse_save(g.slot(0))["map_x"] + 4) == 12)
# --- clock formatting: HH:MM under an hour and at the top of the clock; and a v3
# save must be rejected ---
def set_clock(secs):
    g.pb.memory[SYM["play_seconds"]:SYM["play_seconds"] + 2] = [secs & 0xFF, secs >> 8]
set_clock(754)                         # 12 min 34 s
menu_save(g, chk, "T6 save with play_seconds=754")
g = g.power_cycle("t6f"); g.boot_to_save_select(); g.tick(10)
clock = g.bg_text(13, 4 + 4 * 2, 5)
chk("T6 clock shows 00:12 for 754 s (slot 3)", clock == "00:12", repr(clock))
g.save_select_pick(2); g.wait_map_idle(900)
set_clock(65534); g.tick(150)          # runs past the counter's last second
chk("T6 play clock stops at 65535 s rather than wrapping", g.get16("play_seconds") == 65535, g.get16("play_seconds"))
menu_save(g, chk, "T6 save at the top of the play clock")
g = g.power_cycle("t6g"); g.boot_to_save_select(); g.tick(10)
clock = g.bg_text(13, 4 + 4 * 2, 5)
chk("T6 clock tops out at 18:12 for 65535 s", clock == "18:12", repr(clock))
c1 = g.bg_text(13, 4, 5)
chk("T6 slot 1 clock zero-padded HH:MM", len(c1) == 5 and c1[2] == ":" and c1[:2].isdigit() and c1[3:].isdigit(), repr(c1))
g.shot("save_select_clocks")
# downgrade slot 1 to version 3 with a valid checksum -> must read as NEW
b = set_field(g.slot(0), OFF["version"], 3); b = fix_checksum(b); g.set_slot(0, b)
g.press("b", wait=20); g.wait_for(lambda: g.get("main_title_state") == 1, 600); g.press("start", wait=20)
g.wait_for(lambda: g.gs() == GS["SAVE_SELECT"], 300); g.tick(10)
chk("T6 old-version (v3) save is treated as empty (NEW)", g.slot_is_empty(0), repr(g.slot_text(0)))
g.close()
chk.summary()
