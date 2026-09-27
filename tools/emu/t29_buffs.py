"""T29 - an ability's buff lasts the fight, and the player's status icons sit
on the stat box's own background.

Four abilities give their buff for the whole fight: the druid's Bark Skin (DEF
UP) and Regen, the monk's Diamond Body (DEF UP), and the sorcerer's Haste.
update_effect_duration() ends a 0-duration effect at the owner's next turn,
before the stat pass or player_turn() has read it, so these have to be
perpetual rather than 0, or Haste and Regen do nothing and Bark Skin and
Diamond Body keep only their other half (damage halving, aspect resist). Each
case casts the ability on floor 2's bugbear, plays one more round, and reads
what the buff is supposed to change: the effect slot itself, then
SPECIAL_HASTE, the buffs mirror, or DEF.

A perpetual buff still gives way to a stronger one of the same kind: the
A-tier DEF UP potion drunk over Bark Skin's B-tier DEF UP takes over its
slot, and a second potion, no stronger than the first, is refused.

The icon tiles are drawn for the white battlefield: the glyph is the colored
pixel and the rest is white. The monster rows put them in the Buff and Debuff
palettes over that white, but in the player's row, inside the blue stat box,
those palettes would paint a white square around every icon. So the row keeps
the box's own palette, where the glyph shows white on the box's blue. The icon
half uses an ATK UP potion rather than Haste, since the potion's duration does
not depend on the perpetual-buff handling above. It reads each icon cell in
VRAM and in rendered pixels, where the cell's most common color has to be the
box's own background, then with the debuff expired, where the cleared cell has
to render like a box cell the icon code never writes.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "playtest"))
from lotd import *
from helpers import *
from starts import start_on
import drive

chk = Checker("t29_buffs")
DRUID, MONK, SORCERER = 0, 2, 3
MON0 = SYM["encounter"] + 1
M_MAX_HP, M_HP, M_TARGET_HP, M_PARAMETER = 12, 14, 16, 58
EFFECTS, EFFECT_SIZE, EFFECT_COUNT = drive.PLAYER_EFFECTS, drive.EFFECT_SIZE, drive.EFFECT_COUNT
PERPETUAL = 0xFF

# StatusEffect ids and flags, src/stats.h; SpecialFlags, src/player.h.
BLIND, HASTE, REGEN, ATK_UP, DEF_UP = 0, 11, 12, 14, 15
FLAG_BUFF_REGEN = 1 << 4
SPECIAL_HASTE = 1 << 1
# PowerTier, src/stats.h; the DEF UP multiplier per tier, in 16ths, src/stats.c.
B_TIER, A_TIER = 1, 2
ATK_DEF_MOD = (1, 2, 4, 6)

# The player's icon row starts at tile (12,15), one cell per effect slot; the
# stat box's attribute is BATTLE_CLEAR_ATTR, src/battle.h.
ICON_X, ICON_Y = 12, 15
BATTLE_CLEAR_ATTR = 0x08
FONT_SPACE = 0xA0

def keep_up(g):
    """Full bars for the player and a bugbear no round can kill. Its roar
    charge goes too: a scare takes an effect slot, which moves every icon
    after it, and a scared caster shivers instead of casting."""
    for off in ("hp", "max_hp", "sp", "max_sp"):
        g.wr16(PL + POFF[off], 200)
    for off in (M_MAX_HP, M_HP, M_TARGET_HP):
        g.wr16(MON0 + off, 999)
    g.wr8(MON0 + M_PARAMETER, 0)


def press_through(g):
    g.wait_for(lambda: g.gs() != GS["BATTLE"] or not at_menu(g), 120)
    for _ in range(400):
        if g.gs() != GS["BATTLE"] or at_menu(g):
            break
        g.press("a", hold=2, wait=8)


def fight_round(g):
    keep_up(g)
    g.battle_menu_goto(0); g.press("a", wait=12); g.press("a", wait=12)
    press_through(g)


def active_slots(g, effect_id):
    """(tier, duration) of every active slot holding effect_id."""
    slots = []
    for k in range(EFFECT_COUNT):
        base = EFFECTS + k * EFFECT_SIZE
        if g.rd8(base) and g.rd8(base + 1) == effect_id:
            slots.append((g.rd8(base + 4), g.rd8(base + 3)))
    return slots


def duration_of(g, effect_id):
    """Duration of the active slot holding effect_id, or None if none does."""
    slots = active_slots(g, effect_id)
    return slots[0][1] if slots else None


def engage(cls, tag, items=None):
    g, _ = start_on(2, class_id=cls, level=30, items=items, abilities=0x3F, tag=tag)
    # NPC_1, the bugbear elite, stands at (3,5) (src/floor2.c).
    g.teleport(3, 6, "UP"); g.tick(4)
    g.interact()
    ok = g.wait_for(lambda: at_menu(g), 1800)
    keep_up(g)
    return g, ok


def cast_and_hold(g, row):
    """Cast `row`, then play one more round: the round a 0-duration buff
    expired in."""
    keep_up(g)
    cast_ok = cast(g, row)
    press_through(g)
    fight_round(g)
    return cast_ok


def vram(g, bank, x, y):
    vbk = g.pb.memory[0xFF4F]
    g.pb.memory[0xFF4F] = bank
    try:
        return g.pb.memory[0x9800 + x + 0x20 * y]
    finally:
        g.pb.memory[0xFF4F] = vbk & 1


def cell_pixels(g, x, y):
    g.tick(1, True)
    cell = g.pb.screen.ndarray[8 * y:8 * y + 8, 8 * x:8 * x + 8, :3]
    return [tuple(int(v) for v in cell[r, c]) for r in range(8) for c in range(8)]


def cell_colors(g, x, y):
    return set(cell_pixels(g, x, y))


def background(g, x, y):
    """The cell's most common rendered color: the ground an icon sits on."""
    pixels = cell_pixels(g, x, y)
    return max(set(pixels), key=pixels.count)


def def_line(g):
    return f"def={g.rd8(PL + POFF['def_'])} base={g.rd8(PL + POFF['def_base'])}"


def def_raised(g):
    return g.rd8(PL + POFF["def_"]) > g.rd8(PL + POFF["def_base"])


# --- Sorcerer's Haste ---------------------------------------------------------
g, ok = engage(SORCERER, "t29_haste")
chk("T29 sorcerer reaches the bugbear fight", ok, f"gs={g.gs()}")
chk("T29 Haste was cast", cast_and_hold(g, 2))            # sorcerer2
chk("T29 Haste is still active a round later, for the fight",
    duration_of(g, HASTE) == PERPETUAL, str(duration_of(g, HASTE)))
chk("T29 and player_turn() turns it into SPECIAL_HASTE",
    g.rd8(PL + POFF["special_flags"]) & SPECIAL_HASTE,
    f"special_flags={g.rd8(PL + POFF['special_flags']):#04x}")
g.close()

# --- Druid's Bark Skin and Regen ---------------------------------------------
g, ok = engage(DRUID, "t29_druid")
chk("T29 druid reaches the bugbear fight", ok, f"gs={g.gs()}")
chk("T29 Bark Skin was cast", cast_and_hold(g, 1))        # druid1
chk("T29 Bark Skin's DEF UP is still active a round later, for the fight",
    duration_of(g, DEF_UP) == PERPETUAL, str(duration_of(g, DEF_UP)))
chk("T29 and the stat pass raises DEF", def_raised(g), def_line(g))
chk("T29 Regen was cast", cast_and_hold(g, 5))            # druid5
chk("T29 Regen is still active a round later, for the fight",
    duration_of(g, REGEN) == PERPETUAL, str(duration_of(g, REGEN)))
chk("T29 and shows in the buffs mirror the stat pass builds",
    g.rd8(PL + POFF["buffs"]) & FLAG_BUFF_REGEN,
    f"buffs={g.rd8(PL + POFF['buffs']):#04x}")
g.close()

# --- Monk's Diamond Body -----------------------------------------------------
g, ok = engage(MONK, "t29_monk")
chk("T29 monk reaches the bugbear fight", ok, f"gs={g.gs()}")
chk("T29 Diamond Body was cast", cast_and_hold(g, 4))     # monk4
chk("T29 Diamond Body's DEF UP is still active a round later, for the fight",
    duration_of(g, DEF_UP) == PERPETUAL, str(duration_of(g, DEF_UP)))
chk("T29 and the stat pass raises DEF", def_raised(g), def_line(g))
g.close()

# --- A stronger potion over an ability's buff --------------------------------
g, ok = engage(DRUID, "t29_stack", items={"DEF_UP": 2})
chk("T29 stacking run reaches the bugbear fight", ok, f"gs={g.gs()}")
chk("T29 Bark Skin was cast", cast_and_hold(g, 1))        # druid1
chk("T29 its DEF UP is B tier and perpetual",
    active_slots(g, DEF_UP) == [(B_TIER, PERPETUAL)], str(active_slots(g, DEF_UP)))
chk("T29 the A-tier DEF UP potion is accepted over it",
    drive.use_battle_item(g, drive.ITEM["DEF_UP"]))
press_through(g)
fight_round(g)
chk("T29 and takes over Bark Skin's slot rather than filling a second",
    active_slots(g, DEF_UP) == [(A_TIER, PERPETUAL)], str(active_slots(g, DEF_UP)))
def_base = g.rd8(PL + POFF["def_base"])
chk("T29 so the stat pass raises DEF by the A tier",
    g.rd8(PL + POFF["def_"]) == def_base + (def_base * ATK_DEF_MOD[A_TIER] >> 4), def_line(g))
chk("T29 a second potion, no stronger than the first, is refused",
    not drive.use_battle_item(g, drive.ITEM["DEF_UP"])
    and drive.item_qty(g, drive.ITEM["DEF_UP"]) == 1,
    f"qty={drive.item_qty(g, drive.ITEM['DEF_UP'])}")
g.close()

# --- The player's status icons -----------------------------------------------
g, ok = engage(MONK, "t29_icons", items={"ATK_UP": 1})
chk("T29 icon run reaches the bugbear fight", ok, f"gs={g.gs()}")
chk("T29 the ATK UP potion was drunk", drive.use_battle_item(g, drive.ITEM["ATK_UP"]))
press_through(g)
fight_round(g)
reference = cell_colors(g, ICON_X + EFFECT_COUNT, ICON_Y)   # box, never an icon
box = background(g, ICON_X + EFFECT_COUNT, ICON_Y)

tile, attr = vram(g, 0, ICON_X, ICON_Y), vram(g, 1, ICON_X, ICON_Y)
chk("T29 the ATK UP icon is drawn in the player's row", tile == 0x60 + ATK_UP, f"tile={tile:#04x}")
chk("T29 in the stat box's palette", attr == BATTLE_CLEAR_ATTR, f"attr={attr:#04x}")
chk("T29 and sits on the box's own background, not a white square",
    background(g, ICON_X, ICON_Y) == box, f"{background(g, ICON_X, ICON_Y)} vs box {box}")

# A debuff beside it, poked into the next free slot and drawn by the next
# round's redraw.
free = next(k for k in range(EFFECT_COUNT) if not g.rd8(EFFECTS + k * EFFECT_SIZE))
base = EFFECTS + free * EFFECT_SIZE
for off, v in enumerate((1, BLIND, 1 << BLIND, 3, 0)):   # active, id, flag, duration, tier
    g.wr8(base + off, v)
fight_round(g)
x = ICON_X + 1
tile, attr = vram(g, 0, x, ICON_Y), vram(g, 1, x, ICON_Y)
chk("T29 a debuff icon follows the buff", tile == 0x60 + BLIND, f"tile={tile:#04x}")
chk("T29 in the stat box's palette too", attr == BATTLE_CLEAR_ATTR, f"attr={attr:#04x}")
chk("T29 and sits on the box's own background as well",
    background(g, x, ICON_Y) == box, f"{background(g, x, ICON_Y)} vs box {box}")

# Expire it. The cleared cell has to render like the rest of the box.
g.wr8(base + 3, 0)
fight_round(g)
tile, attr = vram(g, 0, x, ICON_Y), vram(g, 1, x, ICON_Y)
chk("T29 the expired debuff's cell is blank again",
    tile == FONT_SPACE and duration_of(g, BLIND) is None, f"tile={tile:#04x}")
chk("T29 with the box's own attribute", attr == BATTLE_CLEAR_ATTR, f"attr={attr:#04x}")
chk("T29 and renders like the rest of the box",
    cell_colors(g, x, ICON_Y) == reference, f"{sorted(cell_colors(g, x, ICON_Y))} vs {sorted(reference)}")
g.close()

chk.summary()
