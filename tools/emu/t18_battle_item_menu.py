"""T18 - the battle ITEM submenu keeps its entry count and scroll in step.

Using the last of an item stack takes its row out of the list. The item leaves
the inventory on the player's turn, render_item_text() rebuilds the rows then,
and the submenu takes the new count the next time it opens. If the count were
not rebuilt with the rows, the menu would draw `entries` rows over the shorter
list, painting the blanked padding row, and the scroll position could sit past
the new ceiling.

Five items make the list one row longer than the four that fit, so a single use
takes it from "scrolls by one" to "fits exactly": reopened, it has to report no
scroll ceiling and open unscrolled.

Reads BattleMenu directly: active_menu +0, screen_cursor +1,
last_ability_cursor +2, entries +3, cursor +4, scroll +5, max_scroll +6.
Item is { id, quantity, const char *name } = 4 bytes, so inventory[k].quantity
is at inventory + 4k + 1.
"""
from lotd import *

chk = Checker("t18_battle_item_menu")
BM = SYM["battle_menu"]
BATTLE_STATE = SYM["battle_state"]
INV = SYM["inventory"]
SUBMENU_ROWS = 4
BATTLE_MENU_ITEM = 4        # BattleMenuType
MAIN_CURSOR_ITEM = 2        # BattleScreenCursor

# POTION, ETHER, REMEDY, DEF UP, HASTE. The last list entry is a buff, so
# can_use_item() says yes whatever the player's HP and status are.
STOCKED = (0, 1, 2, 4, 7)
LAST = len(STOCKED) - 1

def entries():   return g.rd8(BM + 3)
def cursor():    return g.rd8(BM + 4)
def scroll():    return g.rd8(BM + 5)
def maxscroll(): return g.rd8(BM + 6)
def active():    return g.rd8(BM + 0)
def qty(k):      return g.rd8(INV + 4 * k + 1)
def stocked():   return sum(1 for k in range(8) if qty(k) > 0)

def wait_menu(n=1500):
    return g.wait_for(lambda: g.gs() == GS["BATTLE"] and g.rd8(BATTLE_STATE) == 2, n)

g = Game(tag="t18")
g.boot_to_save_select(); g.save_select_pick(0); g.hero_select_pick(0); g.tick(20)

for k in range(8):
    g.wr8(INV + 4 * k + 1, 1 if k in STOCKED else 0)

g.walk_until_battle()
chk("T18 reached a battle menu", wait_menu()); g.tick(10)

chk("T18 cursor moved to ITEM", g.battle_menu_goto(MAIN_CURSOR_ITEM))
g.press("a", wait=20)
chk("T18 the ITEM submenu is the active menu", active() == BATTLE_MENU_ITEM, str(active()))

n0 = entries()
chk("T18 the submenu lists every stocked item", n0 == stocked() == len(STOCKED),
    f"entries={n0} stocked={stocked()}")
chk("T18 one row more than fits, so the list scrolls by one",
    maxscroll() == n0 - SUBMENU_ROWS == 1, f"max_scroll={maxscroll()} entries={n0}")
chk("T18 the submenu opens unscrolled", scroll() == 0 and cursor() == 0,
    f"scroll={scroll()} cursor={cursor()}")

# Walk to the last entry: the list scrolls by one to bring it into view.
for _ in range(LAST):
    g.press("down", wait=10)
chk("T18 cursor on the last entry", cursor() == LAST, str(cursor()))
chk("T18 reaching the last entry scrolled the list", scroll() == 1, str(scroll()))
g.shot("battle_item_menu_scrolled")

g.press("a", wait=24)
g.wait_for(lambda: g.rd8(BATTLE_STATE) != 2, 60)
chk("T18 back at the menu after the round", wait_menu(), f"gs={g.gs()}")
chk("T18 the item was used on its turn", qty(STOCKED[LAST]) == 0 and stocked() == len(STOCKED) - 1,
    f"qty={qty(STOCKED[LAST])} stocked={stocked()}")

chk("T18 cursor moved back to ITEM", g.battle_menu_goto(MAIN_CURSOR_ITEM))
g.press("a", wait=20)
n1 = entries()
chk("T18 the reopened list is one entry shorter", n1 == n0 - 1, f"entries={n1}")
chk("T18 a list that fits after the use reports no scroll ceiling", maxscroll() == 0,
    f"max_scroll={maxscroll()} entries={n1}")
chk("T18 and opens unscrolled", scroll() == 0, f"scroll={scroll()} max_scroll={maxscroll()}")
chk("T18 the cursor stays inside the list", cursor() < n1, f"cursor={cursor()} entries={n1}")

g.close(); chk.summary()
