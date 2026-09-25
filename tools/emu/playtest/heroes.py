"""Build a character of any class, at any level, parked on any floor.

build_character() is the general form; build_hero() is the floor 8 case, with
the gauntlet cleared, that dragon.py builds on. starts.py wraps
build_character() into the one call a suite makes.

make_floor_template()'s own `level` argument only writes the level byte, which
leaves a level-4 character wearing a level-60 label: a poked level does not
recompute any derived stat. save_load() copies the player struct
verbatim and never recomputes, so every derived stat has to be written here.
It does call player_refresh_abilities(), so ability_flags alone is enough to
give the character its spell list.

Stat tiers per class come from the update_stats() calls in src/player.c, in its
parameter order (hp, sp, atk, def, matk, mdef, agl). matk reads the atk table
and mdef the def table, matching update_stats().

csv.DictReader leaves the type row at index 0, so a level's stats live at row[level].
"""
import csv, os, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir))
from lotd import OFF, POFF, SLOT_STRIDE, ITEM_NAMES, set_field, fix_checksum, make_floor_template

CSV = os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, os.pardir, os.pardir, "assets", "tables.csv")
_ROWS = list(csv.DictReader(open(CSV)))

CLASS_NAMES = {0: "Druid", 1: "Fighter", 2: "Monk", 3: "Sorcerer"}

# (hp, sp, atk, def, matk, mdef, agl) tiers, from each *_update_stats().
CLASS_TIERS = {
    0: ("b", "b", "c", "b", "b", "a", "b"),
    1: ("a", "c", "b", "a", "c", "b", "b"),
    2: ("b", "b", "b", "b", "c", "b", "a"),
    3: ("c", "a", "c", "c", "a", "b", "a"),
}


def stats_for(class_id, level):
    hp_t, sp_t, atk_t, def_t, matk_t, mdef_t, agl_t = CLASS_TIERS[class_id]
    row = _ROWS[level]
    return {
        "max_hp": int(row[f"player_hp_{hp_t}"]),
        "max_sp": int(row[f"player_sp_{sp_t}"]),
        "atk_base": int(row[f"player_atk_{atk_t}"]),
        "def_base": int(row[f"player_def_{def_t}"]),
        "matk_base": int(row[f"player_atk_{matk_t}"]),
        "mdef_base": int(row[f"player_def_{mdef_t}"]),
        "agl_base": int(row[f"agl_{agl_t}"]),
    }


def exp_for(level):
    """get_exp() in src/stats.c: the XP a character holds on reaching `level`."""
    return int(_ROWS[min(max(level, 1), 99)]["exp_by_level"])


def build_character(class_id, level, floor=8, items=None, abilities=0x3F,
                    keys=0, tag="chr"):
    """Save blob for a level-`level` character of `class_id` standing at
    `floor`'s entrance, with `abilities` as its ability_flags bitmask.

    Only the level byte comes from make_floor_template; every derived stat is
    written here, because save_load() copies the player struct verbatim and
    never recomputes. It does call player_refresh_abilities(), so the mask is
    enough to give the character its spell list."""
    items = items or {}
    blob, pos, _ = make_floor_template(floor, hero=class_id, has_torch=True,
                                       tag=f"{tag}{class_id}")
    blob = bytearray(blob)
    p = OFF["player"]

    blob = bytearray(set_field(blob, p + POFF["level"], level))
    blob = bytearray(set_field(blob, p + POFF["ability_flags"], abilities))

    st = stats_for(class_id, level)
    for name, value in st.items():
        blob = bytearray(set_field(blob, p + POFF[name], value, width=2
                                   if name in ("max_hp", "max_sp") else 1))
    # Derived combat stats start equal to their bases; buffs move them in battle.
    for base, live in (("atk_base", "atk"), ("def_base", "def_"),
                       ("matk_base", "matk"), ("mdef_base", "mdef"),
                       ("agl_base", "agl")):
        blob = bytearray(set_field(blob, p + POFF[live], st[base]))
    blob = bytearray(set_field(blob, p + POFF["hp"], st["max_hp"], width=2))
    blob = bytearray(set_field(blob, p + POFF["sp"], st["max_sp"], width=2))
    # The template's XP is a new hero's. Left in place, the first win levels
    # the character up at once, and the level after that sits a whole run of
    # XP away.
    blob = bytearray(set_field(blob, p + POFF["exp"], exp_for(level), width=2))
    blob = bytearray(set_field(blob, p + POFF["next_level_exp"],
                               exp_for(level + 1) if level < 99 else 0xFFFF, width=2))

    for i, name in enumerate(ITEM_NAMES):
        blob = bytearray(set_field(blob, OFF["inventory"] + i, items.get(name, 0)))

    blob = bytearray(set_field(blob, p + POFF["magic_keys"], keys))

    return bytes(fix_checksum(blob)), st


def build_hero(class_id, level=60, items=None, tag="hero"):
    """Save blob for a level-`level` character of `class_id` on floor 8, with
    every ability unlocked and DOOR_1 (the dragon's door) open."""
    blob, st = build_character(class_id, level, floor=8, items=items,
                               abilities=0x3F, tag=tag)
    blob = bytearray(blob)

    # DOOR_1 is FLAG16(0) and a set bit means locked. map_restore_state() lays
    # the saved flags over the floor's ROM defaults, so clearing it here is what
    # a cleared gauntlet would have left behind.
    locked = blob[OFF["flags_door_locked"]] | (blob[OFF["flags_door_locked"] + 1] << 8)
    blob = bytearray(set_field(blob, OFF["flags_door_locked"], locked & ~1, width=2))

    # NPC_2, floor 8's beholder elite, stands at (8,11) on the only corridor to
    # the dragon's door and blocks it while alive. Beating it is what clears the
    # way in a real run, and on_elite_victory hides it the same way; hiding it
    # here keeps the fight under test to the dragon alone. NPC_1 is the dragon,
    # so its bit stays set.
    blob = bytearray(set_field(blob, OFF["npc_visible"], blob[OFF["npc_visible"]] & ~0x02))

    return bytes(fix_checksum(blob)), st


def sram_for(blob):
    sram = bytearray(3 * SLOT_STRIDE)
    sram[0:len(blob)] = blob
    return bytes(sram)
