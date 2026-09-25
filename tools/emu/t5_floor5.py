"""T5 - floor 5's lever flame-color puzzle and its state across a reload.

Starts from a save built straight from the ROM's own floor defaults, pulls
the levers to set each flame's color, then reloads and confirms the colors
and the boss door they unlock both survive.
"""
import json
from lotd import *
chk = Checker("t5_floor5")
tmpl, pos, d = make_floor_template(5, hero=2, has_torch=True)
print("floor5 template:", json.dumps({k: d[k] for k in ("name","floor_index","map_x","map_y","flags_door_locked","flags_sconce_lit","checksum_ok")}))
g = Game(tag="t5", sram=tmpl + bytes(SLOT_STRIDE - SAVE_SIZE))
chk("T5 boot", g.boot_to_save_select()); g.tick(10)
g.save_select_pick(0)
chk("T5 load floor5 -> idle", g.wait_map_idle(900)); g.tick(20)
st = g.state(); print("after load:", st)
chk("T5 on floor 5 at (12,30)", (st["x"], st["y"]) == (12, 30))
def pull(sx, sy, d, label):
    g.teleport(sx, sy, d); g.interact(); g.wait_map_idle(300); g.tick(4)
    print(label, "flames:", g.get("lever1_flame"), g.get("lever2_flame"), g.get("lever3_flame"), "lit:", hex(g.get("flags_sconce_lit")), "colors:", g.state()["sconce_colors"][:3], "doors:", hex(g.get16("flags_door_locked")))
pull(9, 12, "RIGHT", "L1 x1")      # lever1 -> RED
chk("T5 lever1 once -> lever1_flame RED, SCONCE_1 lit red", g.get("lever1_flame") == 1 and (g.get("flags_sconce_lit") & 1) and g.state()["sconce_colors"][0] == 1)
pull(1, 3, "RIGHT", "L2 x1"); pull(1, 3, "RIGHT", "L2 x2")   # lever2 -> GREEN
chk("T5 lever2 twice -> GREEN", g.get("lever2_flame") == 2 and g.state()["sconce_colors"][1] == 2)
menu_save(g, chk, "T5 save with R,G set")
g = reload_slot(g, 0, "t5b")
st = g.state(); print("after reload:", st)
chk("T5 sconce colors restored R,G (display state)", st["sconce_colors"][:2] == [1, 2] and (st["sconce_lit"] & 3) == 3, str(st["sconce_colors"]))
chk("T5 FIX: lever flame counters restored after reload (RED, GREEN)", g.get("lever1_flame") == 1 and g.get("lever2_flame") == 2, f"{g.get('lever1_flame')},{g.get('lever2_flame')}")
# Player pulls lever3 three times -> BLUE completes R,G,B
pull(26, 20, "RIGHT", "L3 x1"); pull(26, 20, "RIGHT", "L3 x2"); pull(26, 20, "RIGHT", "L3 x3")
chk("T5 FIX: lever3 BLUE opens boss door DOOR_3 after a reload", g.get("lever3_flame") == 3 and not (g.get16("flags_door_locked") & 0x4), f"l3={g.get('lever3_flame')} doors={hex(g.get16('flags_door_locked'))}")
g.shot("floor5_boss_door_open")
g.close()
chk.summary()
