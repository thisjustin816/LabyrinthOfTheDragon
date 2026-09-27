"""T9 - the battle menu's FIGHT/ITEM/ABILITY submenus, a buff item landing,
and the banked calls underneath.

Opens each submenu, drinks an ATK UP potion, and confirms the buff applies to
the player's stats on the next turn.
"""
from lotd import *
chk = Checker("t9_battle_probe")
BATTLE_STATE = SYM["battle_state"]; BATTLE_STATE_MENU = 2
g = Game(tag="t9")
g.boot_to_save_select(); g.save_select_pick(0); g.hero_select_pick(0); g.tick(20)
inv = SYM["inventory"]
for k, q in ((0, 3), (1, 12), (3, 1)):
    g.wr8(inv + 4 * k + 1, q)
steps = g.walk_until_battle()
chk("T9 battle started", steps > 0, f"steps={steps}")
def wait_menu(n=1200):
    return g.wait_for(lambda: g.gs() == GS["BATTLE"] and g.rd8(BATTLE_STATE) == BATTLE_STATE_MENU, n)
chk("T9 reached battle menu", wait_menu()); g.tick(10)
chk("T9 menu opens with the cursor on FIGHT", g.rd8(SYM["battle_menu"] + 1) == 0, str(g.rd8(SYM["battle_menu"] + 1)))
g.shot("battle_menu")
chk("T9 cursor moved to ITEM", g.battle_menu_goto(2)); g.press("a", wait=24)
g.shot("battle_item_menu")
rows = [g.bg_text(1, 0x15 + r, 18) for r in range(4)]
print("ITEM submenu rows:", rows)
chk("T9 item rows show counts x3 / x12 / x1", any("x3 " in r for r in rows) and any("x12" in r for r in rows) and any("x1 " in r for r in rows), str(rows))
g.press("b", wait=12)
chk("T9 cursor moved to ABILITY", g.battle_menu_goto(1)); g.press("a", wait=24)
g.shot("battle_ability_menu")
rows2 = [g.bg_text(1, 0x15 + r, 18) for r in range(4)]
print("ABILITY submenu rows:", rows2)
chk("T9 ability row shows an SP cost digit", any(any(c.isdigit() for c in r) for r in rows2), str(rows2))
g.press("b", wait=12)
# --- stat sanity: AGL must equal its base in battle (reset_player_stats never copied it before)
pl = SYM["player"]
agl = g.rd8(pl + POFF["agl"]); agl_base = g.rd8(pl + POFF["agl_base"])
chk("T9 player.agl == agl_base and nonzero at battle start", agl == agl_base and agl > 0, f"agl={agl} base={agl_base}")
# --- use ATK UP from the ITEM submenu. encounter.c applies buffs in
# update_player_status_effects at the start of the player's *next* turn, so the
# stat is read at the menu after the following FIGHT round, not right away.
atk_base = g.rd8(pl + POFF["atk_base"]); atk0 = g.rd8(pl + POFF["atk"])
chk("T9 cursor back to ITEM", g.battle_menu_goto(2)); g.press("a", wait=24)
for _ in range(2): g.press("down", wait=10)          # third row is ATK UP
cur = g.rd8(SYM["battle_menu"] + 4)                  # battle_menu.cursor
chk("T9 item submenu cursor on row 2 (ATK UP)", cur == 2, str(cur))
g.press("a", wait=12)
g.wait_for(lambda: g.rd8(BATTLE_STATE) != BATTLE_STATE_MENU, 60)
g.wait_for(lambda: g.gs() != GS["BATTLE"] or g.rd8(BATTLE_STATE) == BATTLE_STATE_MENU, 2000)
qty = g.rd8(inv + 4 * 3 + 1)
chk("T9 ATK UP consumed (qty 1 -> 0)", qty == 0, str(qty))
# fight rounds: FIGHT -> A (target) -> A (confirm); wait for the menu to come back each round
rounds = 0; atk_after = None; buffs_after = None
for i in range(8):
    if not wait_menu(1500): break
    if rounds == 1 and atk_after is None:
        atk_after = g.rd8(pl + POFF["atk"]); buffs_after = g.rd8(pl + POFF["buffs"])
    g.battle_menu_goto(0)
    g.press("a", wait=12); g.press("a", wait=12)
    rounds += 1
    g.wait_for(lambda: g.rd8(BATTLE_STATE) != BATTLE_STATE_MENU, 60)
    g.wait_for(lambda: g.gs() != GS["BATTLE"] or g.rd8(BATTLE_STATE) == BATTLE_STATE_MENU, 1500)
    if g.gs() != GS["BATTLE"]: break
print("ATK UP:", "atk", atk0, "->", atk_after, "base", atk_base, "buffs", buffs_after, "| rounds fought:", rounds, "gs:", g.gs())
chk("T9 ATK UP buff applied on the next turn: player.atk > atk_base and buffs flag set",
    atk_after is not None and atk_after > atk_base and buffs_after, f"atk {atk0}->{atk_after} base={atk_base} buffs={buffs_after}")
chk("T9 fought at least one round", rounds >= 1, str(rounds))
chk("T9 the battle left the game in a valid state",
    g.gs() in (GS["BATTLE"], GS["WORLD_MAP"]), f"gs={g.gs()}")
g.close(); chk.summary()
