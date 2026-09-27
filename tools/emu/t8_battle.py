"""T8 - a random encounter after a reload plays out to a decision, and the
game is left in a valid state afterward either way.

Loads a saved game, walks until floor 1's random encounter fires, then mashes
through the battle to a victory or a death, and checks the save, position,
and bank that follow.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "playtest"))
from lotd import *
from nav import Floor, DIRS as DIRS_XY
chk = Checker("t8_battle")
F1 = Floor(1)
g = Game(tag="t8")
g.boot_to_save_select(); g.save_select_pick(0); g.hero_select_pick(0); g.tick(20)
menu_save(g, chk, "T8 initial in-game save")
g = reload_slot(g, 0, "t8b")
chk("T8 loaded", g.ms() == MS["WAITING"])
# walk up/down until a random encounter triggers (floor 1: 7 safe steps then chance-based)
steps = g.walk_until_battle(max_steps=120)
chk("T8 random encounter triggered after load", steps > 0, f"steps={steps} gs={g.gs()} ms={g.ms()}")
g.wait_for(lambda: g.gs() == GS["BATTLE"], 600); g.tick(120)
chk("T8 game_state BATTLE", g.gs() == GS["BATTLE"], g.gs())
g.shot("battle_after_load")
# mash A through the battle, bounded; track outcome
outcome = None
for i in range(900):
    g.press("a", hold=2, wait=8)
    gs = g.gs()
    if gs == GS["WORLD_MAP"]:
        outcome = "victory/return"; break
    if gs == GS["DEATH"]:
        outcome = "death"; break
print("battle outcome:", outcome, "after", i, "presses; gs", g.gs())
chk("T8 battle resolved (victory or death, no hang)", outcome is not None, f"gs={g.gs()}")
if outcome == "death":
    g.wait_for(lambda: g.gs() == GS["WORLD_MAP"], 2400)
    for _ in range(40):
        g.press("a", hold=2, wait=8)
        if g.gs() == GS["WORLD_MAP"]: break
ok = g.wait_map_idle(1200)
chk("T8 back on world map and idle after battle", ok and g.gs() == GS["WORLD_MAP"], f"gs={g.gs()} ms={g.ms()} pos={g.pos()}")
g.tick(20); g.shot("map_after_battle")
st = g.state(); print("after battle:", st)
chk("T8 bank 2 on map after battle", g.get("_current_bank") == 2, g.get("_current_bank"))
# Step toward an open neighbor, per floor 1's own walkable map, and land on it.
here = (st["x"], st["y"])
d, (dx, dy) = next((d, v) for d, v in DIRS_XY.items() if F1.neighbor("A", *here, d) == ("A", here[0] + v[0], here[1] + v[1]))
g.step(d); g.wait_map_idle(300)
chk("T8 hero moves after battle", g.pos() == (here[0] + dx, here[1] + dy), f"stepped {d} from {here} to {g.pos()}")
menu_save(g, chk, "T8 save after battle")
s = parse_save(g.slot(0))
chk("T8 post-battle save valid with current position", s["checksum_ok"] and (s["map_x"] + 4, s["map_y"] + 4) == g.pos(), f"{s['map_x']+4},{s['map_y']+4} vs {g.pos()} hp={s['hp']}/{s['max_hp']} lvl={s['level']}")
g = reload_slot(g, 0, "t8c")
chk("T8 reload after battle -> idle at saved position", g.ms() == MS["WAITING"] and g.pos() == (s["map_x"] + 4, s["map_y"] + 4), f"{g.pos()}")
chk("T8 hp restored from save", g.rd16(SYM["player"] + POFF["hp"]) == s["hp"], f"{g.rd16(SYM['player'] + POFF['hp'])} vs {s['hp']}")
g.close(); chk.summary()
