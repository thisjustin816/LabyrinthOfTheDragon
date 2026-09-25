"""T4 - floor 7's lever puzzle and its state across a save and reload.

Starts from a save built straight from the ROM's own floor defaults, frees
both levers, then reloads and confirms `puzzle_state`, the lever flags, and
the eye tiles they repaint all survive.
"""
import json
from lotd import *
chk = Checker("t4_floor7")
tmpl, pos, d = make_floor_template(7, hero=1, has_torch=True)
print("floor7 template:", json.dumps({k: d[k] for k in ("name","floor_index","map_x","map_y","flags_lever_stuck","flags_door_locked","flags_sconce_lit","npc_visible","checksum_ok")}))
chk("T4 template: levers 1,2 start stuck (0x03), doors 1-8 closed (0xFF)", d["flags_lever_stuck"] == 0x03 and d["flags_door_locked"] == 0xFF, str((hex(d["flags_lever_stuck"]), hex(d["flags_door_locked"]))))
g = Game(tag="t4", sram=tmpl + bytes(SLOT_STRIDE - SAVE_SIZE))
chk("T4 boot to save select", g.boot_to_save_select()); g.tick(10)
g.save_select_pick(0)
chk("T4 load floor7 -> idle", g.wait_map_idle(900)); g.tick(20)
st = g.state(); print("after load:", st)
chk("T4 on floor 7 at (8,30)", (st["x"], st["y"]) == (8, 30))
g.shot("floor7_start")
# Hit the two lever-unlock switches by stepping onto them (MAP_SPECIAL tiles fire on_special on arrival)
g.teleport(7, 6, "UP"); g.step("UP"); g.wait_map_idle(300)
chk("T4 switch (7,5): lever 1 unstuck, switch_lever_1 set", not (g.get("flags_lever_stuck") & 1) and g.get("switch_lever_1") == 1, f"stuck={g.get('flags_lever_stuck'):#x} sw1={g.get('switch_lever_1')}")
g.teleport(13, 6, "UP"); g.step("UP"); g.wait_map_idle(300)
chk("T4 switch (13,5): lever 2 unstuck", g.get("flags_lever_stuck") == 0 and g.get("switch_lever_2") == 1, f"stuck={g.get('flags_lever_stuck'):#x}")
# Pull left, right, left: 0 -L-> 1 -R-> 2 -L-> 4  (eyes 1,1,0)
def pull(lever_x, label):
    g.teleport(lever_x, 29, "UP"); g.interact(); g.wait_map_idle(300); g.tick(4)
    print(label, "puzzle_state=", g.get("puzzle_state"), "doors=", hex(g.get16("flags_door_locked")))
pull(7, "pull L1 #1")
chk("T4 after first pull: puzzle_state 1", g.get("puzzle_state") == 1, g.get("puzzle_state"))
pull(9, "pull L2 #1")
chk("T4 after second pull: puzzle_state 2", g.get("puzzle_state") == 2, g.get("puzzle_state"))
pull(7, "pull L1 #2")
chk("T4 after third pull: puzzle_state 4 (eyes 1,1,0)", g.get("puzzle_state") == 4, g.get("puzzle_state"))
chk("T4 DOOR_3 open, DOOR_4 closed at state 4", not (g.get16("flags_door_locked") & 0x4) and (g.get16("flags_door_locked") & 0x8), hex(g.get16("flags_door_locked")))
menu_save(g, chk, "T4 mid-sequence save (state 4)")
s = parse_save(g.slot(0))
ov = {(e[1], e[2]): e for e in s["overrides"]}
print("saved overrides:", s["overrides"])
chk("T4 save has script_state[2]=puzzle_state=4", s["script_state"][2] == 4, s["script_state"])
chk("T4 save has eye tile overrides (7,25)=0x35,(8,24)=0x35,(9,25)=0x36 and switch tiles (7,5),(13,5)=0xF4",
    ov.get((7,25),(0,0,0,0))[3] == 0x35 and ov.get((8,24),(0,0,0,0))[3] == 0x35 and ov.get((9,25),(0,0,0,0))[3] == 0x36 and ov.get((7,5),(0,0,0,0))[3] == 0xF4 and ov.get((13,5),(0,0,0,0))[3] == 0xF4, str(sorted(ov.keys())))
g = reload_slot(g, 0, "t4b")
st = g.state(); print("after reload:", st)
chk("T4 reload idle at (7,29)", g.ms() == MS["WAITING"] and (st["x"], st["y"]) == (7, 29))
chk("T4 DEFERRED RESTORE: puzzle_state == 4 after reload", g.get("puzzle_state") == 4, g.get("puzzle_state"))
chk("T4 levers still unstuck after reload", g.get("flags_lever_stuck") == 0, hex(g.get("flags_lever_stuck")))
eyes_after = [bg_tile_at(g, 7, 25), bg_tile_at(g, 8, 24), bg_tile_at(g, 9, 25)]
print("eye BG tiles after reload:", eyes_after)
# 0x35 = eye on, 0x36 = eye off (map tile ids); BG ids come via map_tile_lookup, so compare on/on/off pattern
chk("T4 eye tiles repainted after reload: (7,25)==(8,24) != (9,25)", eyes_after[0] == eyes_after[1] and eyes_after[0] != eyes_after[2], str(eyes_after))
g.shot("floor7_after_reload_eyes")
chk("T4 switch_lever_1/2 restored to 1 after reload (script_state)", g.get("switch_lever_1") == 1 and g.get("switch_lever_2") == 1, f"sw1={g.get('switch_lever_1')} sw2={g.get('switch_lever_2')}")
chk("T4 save carries script_state[2]=4 and floor7 switch bits 0b0011", parse_save(g.slot(0))["script_state"][2] == 4 and parse_save(g.slot(0))["script_state"][9] == 0x03, str(parse_save(g.slot(0))["script_state"]))
# finish: from 4, right then left: 4 -R-> 6 -L-> 7
pull(9, "L2"); chk("T4 state 6", g.get("puzzle_state") == 6, g.get("puzzle_state"))
pull(7, "L1"); chk("T4 state 7 -> boss door DOOR_2 open, levers stuck", g.get("puzzle_state") == 7 and not (g.get16("flags_door_locked") & 0x2) and g.get("flags_lever_stuck") == 0x03, f"state={g.get('puzzle_state')} doors={hex(g.get16('flags_door_locked'))} stuck={hex(g.get('flags_lever_stuck'))}")
g.shot("floor7_solved")
g.close()
chk.summary()
