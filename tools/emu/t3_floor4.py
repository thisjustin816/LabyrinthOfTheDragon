"""T3 - floor 4's flame-pair puzzle and its state across a save and reload.

Starts from a save built straight from the ROM's own floor defaults, solves
two of the puzzle's pairs, then reloads and confirms `puzzle_count` and the
door it opens both survive.
"""
import json
from lotd import *
chk = Checker("t3_floor4")
tmpl, pos, d = make_floor_template(4, hero=0, has_torch=True)
print("floor4 template:", json.dumps({k: d[k] for k in ("name","floor_index","map_x","map_y","flags_chest_locked","flags_door_locked","flags_sconce_lit","npc_visible","has_torch","checksum_ok")}))
chk("T3 template: floor4 defaults (chests 5,6 locked=0x30; doors 1-4 closed=0x0F; npcs 0x03; no lit sconces)",
    d["flags_chest_locked"] == 0x30 and d["flags_door_locked"] == 0x0F and d["npc_visible"] == 0x03 and d["flags_sconce_lit"] == 0, str((hex(d["flags_chest_locked"]), hex(d["flags_door_locked"]), d["npc_visible"], d["flags_sconce_lit"])))
chk("T3 template position is floor4 default (24,30)", (d["map_x"] + 4, d["map_y"] + 4) == (24, 30), f"{d['map_x']+4},{d['map_y']+4}")

g = Game(tag="t3", sram=tmpl + bytes(SLOT_STRIDE - SAVE_SIZE))   # slot 0 only
chk("T3 boot (unmodified ROM) to save select", g.boot_to_save_select())
g.tick(10); g.shot("save_select_floor4_slot")
g.save_select_pick(0)
chk("T3 load floor4 save -> map idle", g.wait_map_idle(900), f"gs={g.gs()} ms={g.ms()}")
g.tick(20)
st = g.state(); print("after load:", st)
chk("T3 on floor 4 at (24,30)", (st["x"], st["y"]) == (24, 30))
chk("T3 puzzle_count starts 0", g.get("puzzle_count") == 0, g.get("puzzle_count"))
g.shot("floor4_start")

def light_torch_at(sx, sy, expect_color, label):
    g.teleport(sx, sy, "UP"); g.interact(); g.tick(4)
    tc = g.rd8(SYM["player"] + POFF["torch_color"]); tg = g.rd8(SYM["player"] + POFF["torch_gauge"])
    chk(f"T3 {label}: torch lit color={expect_color}", tc == expect_color and tg > 0, f"color={tc} gauge={tg}")

def light_sconce_at(sx, sy, label):
    g.teleport(sx, sy, "UP"); g.interact(); g.tick(6)   # on_lit runs on the next update_map
    g.wait_map_idle(300)

# Pair 1: GREEN (static green sconce at (24,27); pair at (2,9),(4,9))
light_torch_at(24, 28, 2, "green")
light_sconce_at(2, 10, "sconce1"); light_sconce_at(4, 10, "sconce2")
chk("T3 pair 1 solved: puzzle_count == 1", g.get("puzzle_count") == 1, g.get("puzzle_count"))
chk("T3 sconces 1,2 lit green", (g.get("flags_sconce_lit") & 0x03) == 0x03 and g.state()["sconce_colors"][:2] == [2, 2], str(g.state()["sconce_colors"]))
# Pair 2: RED (static red at (25,27); pair at (9,9),(10,9))
light_torch_at(25, 28, 1, "red")
light_sconce_at(9, 10, "sconce3"); light_sconce_at(10, 10, "sconce4")
chk("T3 pair 2 solved: puzzle_count == 2", g.get("puzzle_count") == 2, g.get("puzzle_count"))
chk("T3 door 1 still closed", g.get16("flags_door_locked") & 0x0001)
# Save mid-puzzle
menu_save(g, chk, "T3 save at puzzle_count=2")
s = parse_save(g.slot(0))
chk("T3 save captured script_state[0]=puzzle_count=2, sconce_lit=0x0F, colors G,G,R,R", s["script_state"][0] == 2 and s["flags_sconce_lit"] == 0x0F and s["sconce_colors"][:4] == [2, 2, 1, 1], f"{s['script_state']} lit={s['flags_sconce_lit']:#x} colors={s['sconce_colors']}")
# Reload
g = reload_slot(g, 0, "t3b")
chk("T3 reload -> map idle", g.gs() == GS["WORLD_MAP"] and g.ms() == MS["WAITING"], f"gs={g.gs()} ms={g.ms()}")
st = g.state(); print("after reload:", st)
chk("T3 DEFERRED RESTORE: puzzle_count == 2 after reload", g.get("puzzle_count") == 2, g.get("puzzle_count"))
chk("T3 sconce flags/colors restored", st["sconce_lit"] == 0x0F and st["sconce_colors"][:4] == [2, 2, 1, 1], f"lit={st['sconce_lit']:#x} colors={st['sconce_colors']}")
chk("T3 no on_lit replay on load: door 1 still closed, puzzle_count not advanced", (st["door_locked"] & 1) and g.get("puzzle_count") == 2)
g.shot("floor4_after_reload")
# Pair 3: BLUE (static blue at (23,27); pair at (17,9),(18,9))
light_torch_at(23, 28, 3, "blue")
light_sconce_at(17, 10, "sconce5"); light_sconce_at(18, 10, "sconce6")
g.wait_map_idle(400)
chk("T3 pair 3 solved after reload: puzzle_count == 3", g.get("puzzle_count") == 3, g.get("puzzle_count"))
chk("T3 DOOR_1 opened (flags_door_locked bit0 clear)", not (g.get16("flags_door_locked") & 0x0001), f"door_locked={g.get16('flags_door_locked'):#06x}")
# Save and reload at the open door, with a screenshot, then walk through it
g.teleport(28, 28, "UP"); g.tick(2)
menu_save(g, chk, "T3 save at door")
g = reload_slot(g, 0, "t3c")
st = g.state()
chk("T3 at (28,28) facing UP after reload, door open persisted", (st["x"], st["y"]) == (28, 28) and not (st["door_locked"] & 1), str(st))
g.shot("floor4_boss_door_open")
# walk through the open door: step UP onto (28,27) which is an exit -> should transition (not blocked)
g.step("UP"); g.tick(60)
# The door tile is also the stairs exit -> arrives at (28,23) facing UP and auto-steps to (28,22).
g.wait_map_idle(300)
chk("T3 walking into the opened door fires its stairs exit (hero ends at (28,22) in the boss room)", g.pos() == (28, 22), f"pos={g.pos()} ms={g.ms()}")
g.shot("floor4_boss_room_after_door")
g.close()
chk.summary()
