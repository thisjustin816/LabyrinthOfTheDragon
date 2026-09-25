"""T12 - floor 8's tile-override hash table holds a collision across a
reload.

Two of the floor's healing mirrors hash to the same table slot; each must
still repaint its own tile, and that state must hold after a save and
reload.
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "playtest"))
from lotd import *
from helpers import vram_byte, screen_cells, drawn_palettes
chk = Checker("t12_override_collision")
# Two of floor 8's healing mirrors collide in the tile-override hash (map 0: (11,21) and (19,9) both hash to
# slot 2, so the second probes to slot 3). Each colliding override has to repaint its own tile and survive a reload.
OV_SLOT = 5                                  # bytes per override: map_id, x, y, tile, palette
tmpl, pos, d = make_floor_template(8, hero=0, has_torch=True, tag="t12tmpl")
g = Game(tag="t12", sram=tmpl + bytes(SLOT_STRIDE - SAVE_SIZE))
g.boot_to_save_select(); g.tick(10); g.save_select_pick(0); chk("T12 on floor 8", g.wait_map_idle(900) and g.pos() == (8, 29), str(g.pos())); g.tick(20)
HMU = SYM["healing_mirrors_used"]; PL = SYM["player"]
def snapshot():
    return [(vram_byte(g, 0x9800 + i, 0), vram_byte(g, 0x9800 + i, 1)) for i in range(1024)]
def use_mirror(x, y, label):
    g.teleport(x, y + 1, "UP"); g.tick(4)
    # a teleport leaves the screen stale: save + reload draws it fresh at this spot (and exercises the deferred override repaint)
    menu_save(g, chk, f"{label}: save near the mirror")
    return reload_slot(g, 0, f"t12_{label[:6]}")
# --- mirror 4 at (11,21)
g = use_mirror(11, 21, "T12 m4"); g.tick(10)
before = snapshot(); p_before = drawn_palettes(g, 11, 21)
g.wr8(PL + POFF["hp"], 5); g.wr8(PL + POFF["hp"] + 1, 0)
g.interact(); g.tick(6)
after = snapshot(); p_after = drawn_palettes(g, 11, 21)
changed = [i for i in range(1024) if before[i] != after[i]]
mine = {a - 0x9800 for a in screen_cells(g, 11, 21)}
print("mirror 4: palette", p_before, "->", p_after, "| changed cells:", changed, "| expected:", sorted(mine))
chk("T12 mirror 4 healed and flagged", g.rd16(PL + POFF["hp"]) == g.rd16(PL + POFF["max_hp"]) and g.rd8(HMU) & 0x08, f"hp={g.rd16(PL + POFF['hp'])} used={g.rd8(HMU):#04x}")
chk("T12 mirror 4 tile repainted to palette 4", p_after == [4], str(p_after))
chk("T12 mirror 4: only its own 2x2 cells changed on screen", set(changed) <= mine and changed, f"changed={changed} mine={sorted(mine)}")
g.shot("mirror4_used")
# --- mirror 5 at (19,9): same hash slot as mirror 4, inserted second (probes to the next slot)
g = use_mirror(19, 9, "T12 m5"); g.tick(10)
before = snapshot(); p_before = drawn_palettes(g, 19, 9)
g.wr8(PL + POFF["hp"], 5); g.wr8(PL + POFF["hp"] + 1, 0)
g.interact(); g.tick(6)
after = snapshot(); p_after = drawn_palettes(g, 19, 9)
changed = [i for i in range(1024) if before[i] != after[i]]
mine = {a - 0x9800 for a in screen_cells(g, 19, 9)}
print("mirror 5: palette", p_before, "->", p_after, "| changed cells:", changed, "| expected:", sorted(mine))
chk("T12 mirror 5 healed and flagged (used=0x18)", g.rd16(PL + POFF["hp"]) == g.rd16(PL + POFF["max_hp"]) and g.rd8(HMU) == 0x18, f"hp={g.rd16(PL + POFF['hp'])} used={g.rd8(HMU):#04x}")
chk("T12 mirror 5 tile repainted to palette 4 despite the colliding slot", p_after == [4], str(p_after))
chk("T12 mirror 5: only its own 2x2 cells changed on screen", set(changed) <= mine and changed, f"changed={changed} mine={sorted(mine)}")
g.shot("mirror5_used")
# --- both overrides survive a save/reload and land on the right tiles
menu_save(g, chk, "T12 save with both colliding overrides")
sv = parse_save(g.slot(0)); ov = sv["overrides"]
print("saved overrides:", ov)
raw = g.slot(0)[OFF["overrides"]:OFF["overrides"] + OV_SLOT * 4]
slot2, slot3 = tuple(raw[OV_SLOT * 2:OV_SLOT * 2 + 3]), tuple(raw[OV_SLOT * 3:OV_SLOT * 3 + 3])
chk("T12 mirror 4 holds hash slot 2 and mirror 5 probes on to slot 3", slot2 == (0, 11, 21) and slot3 == (0, 19, 9),
    f"slot 2={slot2} slot 3={slot3}")
chk("T12 save holds exactly the two mirror overrides (tile 0xFF, palette 4)", sorted((x, y) for (m, x, y, t, p) in ov) == [(11, 21), (19, 9)] and all(t == 0xFF and p == 4 for (m, x, y, t, p) in ov), str(ov))
g = reload_slot(g, 0, "t12_r1"); g.tick(10)
chk("T12 after reload at (19,10): mirror 5 tile still palette 4", drawn_palettes(g, 19, 9) == [4], str(drawn_palettes(g, 19, 9)))
g.teleport(11, 22, "UP"); g.tick(4); menu_save(g, chk, "T12 save at mirror 4"); g = reload_slot(g, 0, "t12_r2"); g.tick(10)
chk("T12 after reload at (11,22): mirror 4 tile still palette 4", drawn_palettes(g, 11, 21) == [4], str(drawn_palettes(g, 11, 21)))
chk("T12 both mirrors still flagged used after reloads", g.rd8(HMU) == 0x18, f"{g.rd8(HMU):#04x}")
g.wr8(PL + POFF["hp"], 5); g.wr8(PL + POFF["hp"] + 1, 0); g.interact(); g.tick(4)
chk("T12 mirror 4 refuses a second use after the collision", g.rd16(PL + POFF["hp"]) == 5, str(g.rd16(PL + POFF["hp"])))
g.close(); chk.summary()
