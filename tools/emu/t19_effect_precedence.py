"""T19 - a debuff beats a buff on the same stat, whichever slot it landed in.

update_player_status_effects() assigns each stat from its `_base` value rather
than adjusting a running one, so whichever slot is applied last wins outright.
Buffs are applied in one pass and debuffs in a second, so the debuff wins
whatever the slot order: an ATK UP potion does not cancel a blind, and a blind
does not wipe a fresh ATK UP in the slot after it.

Encounter.player_status_effects is at +209; StatusEffectInstance is 5 bytes:
active, effect, flag, duration, tier.
"""
from lotd import *

chk = Checker("t19_effect_precedence")
EFF = SYM["encounter"] + 209
BATTLE_STATE = SYM["battle_state"]
PL = SYM["player"]
DEBUFF_BLIND, DEBUFF_ATK_DOWN, BUFF_ATK_UP = 0, 6, 14
# Monster is 64 bytes; max_hp +12, hp +14, target_hp +16 (from the .cdb).
MON0, MSIZE = SYM["encounter"] + 1, 64
M_MAXHP, M_HP, M_TARGET_HP = 12, 14, 16
FLAG_BLIND, FLAG_ATK_DOWN, FLAG_ATK_UP = 1 << 0, 1 << 6, 1 << 6
A_TIER = 2

g = Game(tag="t19")
g.boot_to_save_select(); g.save_select_pick(0); g.hero_select_pick(0); g.tick(20)

def wait_menu(n=1500):
    return g.wait_for(lambda: g.gs() == GS["BATTLE"] and g.rd8(BATTLE_STATE) == 2, n)

g.walk_until_battle()
chk("T19 reached a battle menu", wait_menu()); g.tick(10)

# Park the level-up requirement out of reach. A level-up mid-test would move
# atk_base between two measurements that are meant to differ only in slot order.
g.wr8(PL + POFF["next_level_exp"], 0xFF); g.wr8(PL + POFF["next_level_exp"] + 1, 0xFF)

def put(slot, effect, flag, tier=A_TIER, duration=90):
    b = EFF + slot * 5
    g.wr8(b + 0, 1); g.wr8(b + 1, effect); g.wr8(b + 2, flag)
    g.wr8(b + 3, duration); g.wr8(b + 4, tier)

def top_up_monsters():
    """Seven measurements take seven attacks, which would kill the encounter long
    before the last one. Put the monsters back to full so the battle lasts."""
    for i in range(3):
        b = MON0 + i * MSIZE
        if not g.rd8(b + 5):            # active
            continue
        mx = g.rd8(b + M_MAXHP) | (g.rd8(b + M_MAXHP + 1) << 8)
        for off in (M_HP, M_TARGET_HP):
            g.wr8(b + off, mx & 0xFF); g.wr8(b + off + 1, mx >> 8)


def measure(slots):
    """Write the slots, let one player turn resolve so check_status_effects()
    reruns, then read the stat it produced alongside the base it came from."""
    top_up_monsters()
    for s in range(4):
        for b in range(5):
            g.wr8(EFF + s * 5 + b, 0)
    for s in slots:
        put(*s)
    g.press("a", wait=10); g.press("a", wait=10)
    g.wait_for(lambda: g.rd8(BATTLE_STATE) != 2, 120)
    g.wait_for(lambda: g.gs() != GS["BATTLE"] or g.rd8(BATTLE_STATE) == 2, 1500)
    # Every slot written must still be live, or the reading says nothing about
    # precedence -- it just says one of the two effects had already lapsed.
    live = [s for s, *_ in slots if g.rd8(EFF + s * 5) == 1]
    assert len(live) == len(slots) and g.gs() == GS["BATTLE"], \
        f"effects lapsed or battle ended: live={live} of {[s for s,*_ in slots]} gs={g.gs()}"
    return g.rd8(PL + POFF["atk"]), g.rd8(PL + POFF["atk_base"])

BLIND  = (0, DEBUFF_BLIND, FLAG_BLIND)
UP     = (0, BUFF_ATK_UP, FLAG_ATK_UP)
DOWN   = (0, DEBUFF_ATK_DOWN, FLAG_ATK_DOWN)
def at(slot, e): return (slot,) + e[1:]

# --- each effect on its own still does what it always did
atk, base = measure([BLIND])
chk("T19 blind alone zeroes ATK", atk == 0, f"atk={atk} base={base}")
up_atk, up_base = measure([UP])
chk("T19 ATK UP alone raises ATK above base", up_atk > up_base, f"atk={up_atk} base={up_base}")
down_atk, down_base = measure([DOWN])
chk("T19 ATK DOWN alone lowers ATK below base", 0 < down_atk < down_base,
    f"atk={down_atk} base={down_base}")

# --- the pair, both ways round. The point is that the two orders agree.
a1, _ = measure([at(0, BLIND), at(1, UP)])
a2, _ = measure([at(0, UP),    at(1, BLIND)])
chk("T19 blind beats ATK UP with blind in the earlier slot", a1 == 0, str(a1))
chk("T19 blind beats ATK UP with blind in the later slot", a2 == 0, str(a2))
chk("T19 slot order does not decide blind vs ATK UP", a1 == a2, f"{a1} vs {a2}")

b1, b1_base = measure([at(0, DOWN), at(1, UP)])
b2, b2_base = measure([at(0, UP),   at(1, DOWN)])
chk("T19 ATK DOWN beats ATK UP with the debuff earlier", b1 < b1_base, f"atk={b1} base={b1_base}")
chk("T19 ATK DOWN beats ATK UP with the debuff later", b2 < b2_base, f"atk={b2} base={b2_base}")
chk("T19 slot order does not decide ATK DOWN vs ATK UP", b1 == b2, f"{b1} vs {b2}")

g.close(); chk.summary()
