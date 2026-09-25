"""T1 - a new game walks, opens a chest, and survives a pause-menu save, a
power cycle, and a reload with position and object state intact.

T2 - a chest opened before that save stays open after the reload.
"""
import json
from lotd import *

check = Checker("t1_t2")

def pixel_diff(a, b):
    from PIL import Image, ImageChops
    ia, ib = Image.open(a).convert("RGB"), Image.open(b).convert("RGB")
    d = ImageChops.difference(ia, ib).convert("L")
    n = sum(1 for p in d.getdata() if p)
    return n / (160 * 144)

# ---------------- T1: new game -> move -> pause -> SAVE -> reset -> load ----
g = Game(tag="t1")
check("T1 boot reaches save select", g.boot_to_save_select(), f"gs={g.gs()}")
g.shot("save_select_all_new")
check("T1 all slots empty (SRAM magic absent)", all(parse_save(g.slot(i))["magic"] != SAVE_MAGIC for i in range(3)))
g.save_select_pick(0)
check("T1 NEW slot -> hero select", g.gs() == GS["HERO_SELECT"], f"gs={g.gs()}")
g.shot("hero_select")
check("T1 hero select -> world map idle", g.hero_select_pick(0), f"gs={g.gs()} ms={g.ms()}")
g.tick(30)
g.shot("map_new_game")
st0 = g.state(); print("new-game state:", st0)
check("T1 new game at floor1 default (12,16)", (st0["x"], st0["y"]) == (12, 16), f"{st0['x']},{st0['y']}")
s0 = parse_save(g.slot(0)); print("initial slot0 save:", json.dumps(s0, default=str))
check("T1 start_game wrote initial save: magic/version/checksum", s0["magic"] == SAVE_MAGIC and s0["version"] == SAVE_VERSION and s0["checksum_ok"])
check("T1 initial save name Lyra, floor_index 0, pos (12,16)", s0["name"] == "Lyra" and s0["floor_index"] == 0 and (s0["map_x"] + 4, s0["map_y"] + 4) == (12, 16), f"{s0['name']} fi={s0['floor_index']} pos={s0['map_x']+4},{s0['map_y']+4}")
check("T1 live player bytes == saved player bytes", g.player_bytes() == g.slot(0)[OFF['player']:OFF['player']+PLAYER_SIZE])

# walk UP, UP, LEFT (start tile (12,16) has floor above it)
moves = []
for d in ("UP", "UP", "LEFT"):
    ok = g.step(d); g.wait_map_idle(200)
    moves.append((d, ok, g.pos(), g.facing(), g.ms()))
print("moves:", moves)
check("T1 hero walked to (11,14) facing LEFT", g.pos() == (11, 14) and g.facing() == "LEFT", f"pos={g.pos()} facing={g.facing()} ms={g.ms()}")
before = g.state(); print("before save:", before)
shot_before = g.shot("map_before_save")

g.press("start", wait=14)
check("T1 START opens pause menu", g.ms() == MS["MENU"], f"ms={g.ms()}")
g.shot("menu_open_cursor_return")
lbl = find_text(g.pb.tilemap_window, "SAVE")
check("T1 SAVE label drawn in window", lbl is not None, str(lbl))
g.press("down", wait=8)
g.shot("menu_cursor_on_save")
g.press("a", wait=16)
g.shot("menu_after_save_press")
msg = find_text(g.pb.tilemap_window, "GAME SAVED!")
check("T1 'GAME SAVED!' message shown", msg is not None, str(msg))
# Moving off SAVE retires its message. Left up, it sat under the hand once the
# hand moved over to QUIT: the sprite is 16px tall, so on the bottom row it
# reaches down into the message line.
g.press("right", wait=8)
gone = find_text(g.pb.tilemap_window, "GAME SAVED!")
check("T1 moving the cursor clears 'GAME SAVED!'", gone is None, str(gone))
s1 = parse_save(g.slot(0)); print("slot0 after in-game save:", json.dumps(s1, default=str))
check("T1 saved pos/facing match live", (s1["map_x"] + 4, s1["map_y"] + 4) == (before["x"], before["y"]) and s1["hero_direction"] == DIR["LEFT"], f"save pos={s1['map_x']+4},{s1['map_y']+4} dir={s1['hero_direction']}")
check("T1 saved checksum valid", s1["checksum_ok"])
g.press("b", wait=14)
check("T1 B closes menu back to map", g.wait_map_idle(120), f"ms={g.ms()}")
check("T1 bank after menu close is 2", g.get("_current_bank") == 2, f"bank={g.get('_current_bank')}")
# can still move after saving? ((11,15) is a wall on floor 1; (11,13) is floor)
g.step("UP"); g.wait_map_idle(200)
check("T1 hero still moves after save (UP -> (11,13))", g.pos() == (11, 13), f"pos={g.pos()}")
g.step("DOWN"); g.wait_map_idle(200)
g.step("UP"); g.wait_map_idle(200)
check("T1 back to (11,13) facing UP", g.pos() == (11, 13) and g.facing() == "UP", f"{g.pos()} {g.facing()}")
# Save again so saved facing == UP for the reload comparison
g.press("start", wait=14); g.press("down", wait=8); g.press("a", wait=16); g.press("b", wait=14); g.wait_map_idle(120)
before = g.state(); print("before power cycle:", before)
shot_before = g.shot("map_before_reset")

# ---- power cycle ----
g = g.power_cycle(tag="t1b")
check("T1 SRAM survived power cycle", parse_save(g.slot(0))["checksum_ok"])
check("T1 boot after reset reaches save select", g.boot_to_save_select())
g.tick(20)
g.shot("save_select_slot1_used")
row_name = g.bg_text(6, 4, 6); row_clock = g.bg_text(13, 4, 5); row_stats = g.bg_text(6, 5, 12)
print("slot1 row name:", repr(row_name), "clock:", repr(row_clock), "stats:", repr(row_stats))
check("T1 save select shows name Lyra", row_name.strip() == "Lyra", repr(row_name))
saved_secs = parse_save(g.slot(0))["play_seconds"]
check("T1 save select shows an HH:MM clock == saved play time", len(row_clock) == 5 and row_clock[2] == ":" and row_clock[:2].isdigit() and row_clock[3:].isdigit() and int(row_clock[:2]) * 60 + int(row_clock[3:]) == saved_secs // 60, f"{row_clock!r} vs saved {saved_secs}s")
check("T1 slots 2/3 show '- NEW GAME -', centered in the box interior", g.slot_is_empty(1) and g.slot_is_empty(2) and g.slot_text(1) == "  - NEW GAME -  ", repr([g.slot_text(1), g.slot_text(2)]))
g.save_select_pick(0)
check("T1 used slot -> world map idle (load)", g.wait_map_idle(600), f"gs={g.gs()} ms={g.ms()}")
g.tick(30)
after = g.state(); print("after load:", after)
shot_after = g.shot("map_after_load")
for k in ("x", "y", "facing", "map", "chest_open", "door_locked", "sconce_lit", "lever_on", "lever_stuck", "sconce_colors"):
    check(f"T1 after load {k} == before", after[k] == before[k], f"{before[k]} -> {after[k]}")
check("T1 play_seconds restored (>= saved, small drift)", 0 <= after["play_seconds"] - before["play_seconds"] <= 3, f"{before['play_seconds']} -> {after['play_seconds']}")
pd = pixel_diff(shot_before, shot_after)
check("T1 screen after load ~= screen before reset", pd < 0.03, f"pixel diff ratio={pd:.4f}")
check("T1 bank is 2 on world map after load", g.get("_current_bank") == 2, f"bank={g.get('_current_bank')}")
g.step("DOWN"); g.wait_map_idle(200)
check("T1 hero not frozen after load (DOWN -> (11,14))", g.pos() == (11, 14), f"pos={g.pos()}")

# ---------------- T2: chest open -> save -> reload -> still open ----------
# Teleport next to CHEST_2 (21,13): stand at (21,14) facing UP.
g.teleport(21, 14, "UP")
g.tick(3)
check("T2 teleported to (21,14) facing UP", g.pos() == (21, 14) and g.facing() == "UP", f"{g.pos()} {g.facing()}")
before_chest = g.get("flags_chest_open")
g.interact()
check("T2 chest opened: flags_chest_open gained CHEST_2 (0x02)", (g.get("flags_chest_open") & 0x02) and not (before_chest & 0x02), f"{before_chest:#x} -> {g.get('flags_chest_open'):#x}")
check("T2 magic key granted by chest", g.rd8(SYM["player"] + POFF["magic_keys"]) == 1, f"keys={g.rd8(SYM['player'] + POFF['magic_keys'])}")
g.wait_map_idle(300)
check("T2 back to idle after chest textbox", g.ms() == MS["WAITING"], f"ms={g.ms()}")
g.press("start", wait=14); g.press("down", wait=8); g.press("a", wait=16)
msg = find_text(g.pb.tilemap_window, "GAME SAVED!")
check("T2 saved after chest", msg is not None)
g.press("b", wait=14); g.wait_map_idle(120)
s2 = parse_save(g.slot(0))
check("T2 save has chest flag and key", (s2["flags_chest_open"] & 0x02) and s2["magic_keys"] == 1, f"chest={s2['flags_chest_open']:#x} keys={s2['magic_keys']}")
g = g.power_cycle(tag="t2")
g.boot_to_save_select(); g.tick(10)
g.save_select_pick(0)
check("T2 reload -> map idle", g.wait_map_idle(600))
g.tick(20)
st = g.state(); print("T2 after load:", st)
check("T2 pos (21,14) facing UP after load", (st["x"], st["y"], st["facing"]) == (21, 14, "UP"))
check("T2 chest still open after load", st["chest_open"] & 0x02, f"{st['chest_open']:#x}")
g.shot("map_after_load_chest_open")
# press A on the chest again: should NOT re-open (already open)
g.interact()
check("T2 A on open chest does nothing (no re-open)", g.rd8(SYM["player"] + POFF["magic_keys"]) == 1, f"keys={g.rd8(SYM['player'] + POFF['magic_keys'])}")
g.close()

check.summary()
