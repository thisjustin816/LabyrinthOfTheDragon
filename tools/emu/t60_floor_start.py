"""T60 - SELECT on the name entry starts a new game on a lower floor.

Each press cycles a label under the grid from START B2 to START B8 and back to
blank. START then puts the hero on that floor at about the level a full first
run reaches it at, with the abilities the elites before it teach, the torch, a
magic key for each of its key-locked chests, and every item a first run
gathers on the floors before it without using any. Those floors give fewer
keys than they have key-locked chests, so a first run opens each floor's in
order until its keys run out. The expected keys and items come from the
floors' own sources, so a chest that changes without src/name_entry.c's table
fails here.
"""
import os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "playtest"))
sys.path.insert(0, os.path.join(HERE, "audit"))
from lotd import *
from helpers import current_floor
from shared import strip_comments

chk = Checker("t60_floor_start")
ITEMS = ["POTION", "ETHER", "REMEDY", "ATK_UP", "DEF_UP", "ELIXIR", "REGEN", "HASTE"]
LABEL_COL, LABEL_ROW, LABEL_LEN = 6, 15, 8
# About the level a full first run reaches each floor at.
START_LEVELS = {2: 14, 3: 20, 4: 30, 5: 35, 6: 45, 7: 48, 8: 52}


def table(src, name):
    """The rows of a floor's `static const ... name[]` table, as field lists."""
    m = re.search(r"static const \w+ %s\[\]\s*=\s*\{" % name, src)
    depth = 0
    for j in range(m.end() - 1, len(src)):
        depth += {"{": 1, "}": -1}.get(src[j], 0)
        if depth == 0:
            body = src[m.end():j]
            break
    rows = [[f.strip() for f in e.group(1).split(",") if f.strip()]
            for e in re.finditer(r"\{([^{}]*)\}", body)]
    return [r for r in rows if r and r[0] != "END"]


def floor_facts():
    """Per floor: what a first run gathers, and its key-locked chests."""
    common = strip_comments(open(os.path.join(REPO, "src", "floor_common.c")).read())
    lists = {m.group(1): re.findall(r"\{\s*ITEM_(\w+),\s*(\d+)\s*\}", m.group(2))
             for m in re.finditer(r"const Item (chest_item_\w+)\[\]\s*=\s*\{(.*?)\};", common, re.S)}
    facts = {}
    for n in range(1, 9):
        src = strip_comments(open(os.path.join(REPO, "src", f"floor{n}.c")).read())
        # Chest fields: id, map, col, row, locked, key unlock, message, items,
        # callback. Door fields: id, map, col, row, type, key unlock, open.
        chests = table(src, "chests")
        keys = sum(1 for c in chests if c[8:9] == ["chest_add_magic_key"])
        keys -= sum(1 for d in table(src, "doors") if d[5:6] == ["true"])
        haul = [0] * len(ITEMS)
        key_chests = [c for c in chests if c[4:6] == ["true", "true"]]
        opened = [c for c in chests if c[4:6] != ["true", "true"]] + key_chests[:max(keys, 0)]
        for c in opened:
            for item, q in lists.get(c[7] if len(c) > 7 else "", []):
                haul[ITEMS.index(item)] += int(q)
        for item, q in re.findall(r"add_items\(ITEM_(\w+),\s*(\d+)\)", src):
            haul[ITEMS.index(item)] += int(q)
        facts[n] = dict(haul=haul, key_chests=len(key_chests))
    return facts


def to_name_entry(g):
    g.boot_to_save_select(); g.save_select_pick(0)
    g.wait_for(lambda: g.gs() == GS["HERO_SELECT"], 300)
    g.tick(10); g.press("a", wait=12)
    g.wait_for(lambda: g.gs() == GS["NAME_ENTRY"], 120)
    g.tick(6)


def label(g):
    return g.bg_text(LABEL_COL, LABEL_ROW, LABEL_LEN)


facts = floor_facts()
for n in range(2, 9):
    haul = [sum(facts[f]["haul"][k] for f in range(1, n)) for k in range(len(ITEMS))]
    level = START_LEVELS[n]
    abilities = (1 << min(n - 1, 6)) - 1
    g = Game(tag=f"t60_b{n}")
    to_name_entry(g)
    for _ in range(n - 1):
        g.press("select", wait=8)
    chk(f"T60 {n - 1} SELECT presses label the start B{n}", label(g) == f"START B{n}", repr(label(g)))
    if n == 5:
        g.shot("name_entry_start_b5")
    g.press("start", wait=12)
    arrived = g.wait_for(lambda: g.gs() == GS["WORLD_MAP"] and not g.rd8(SYM["execute_on_init"]), 900)
    chk(f"T60 START puts the hero on B{n}", arrived and current_floor(g) == n,
        f"gs={g.gs()} floor={current_floor(g)}")
    blob = g.slot(0)
    d = parse_save(blob)
    p = OFF["player"]
    got = dict(floor=d["floor_index"] + 1, level=d["level"], abilities=blob[p + POFF["ability_flags"]],
               torch=d["has_torch"], keys=d["magic_keys"], got_key=blob[p + POFF["got_magic_key"]],
               items=d["inventory"], name=d["name"])
    want = dict(floor=n, level=level, abilities=abilities, torch=1, keys=facts[n]["key_chests"], got_key=1,
                items=haul, name="Lyra")
    chk(f"T60 B{n}'s first save: level {level}, abilities {abilities:#04x}, the torch, "
        f"{want['keys']} keys, and a first run's items",
        got == want, f"got {got}, want {want}")
    g.close()

# The eighth press wraps back to floor 1, which starts as always, on the intro.
g = Game(tag="t60_b1")
to_name_entry(g)
for _ in range(8):
    g.press("select", wait=8)
chk("T60 an eighth SELECT press blanks the label again", label(g) == " " * LABEL_LEN, repr(label(g)))
g.press("start", wait=12)
g.wait_for(lambda: g.gs() == GS["WORLD_MAP"] and not g.rd8(SYM["execute_on_init"]), 900)
d = parse_save(g.slot(0))
chk("T60 with the label blank, START begins on B1 at level 4 with nothing, on the intro line",
    current_floor(g) == 1 and d["level"] == 4 and not any(d["inventory"]) and not d["has_torch"]
    and g.wait_for(lambda: g.ms() in (MS["TEXTBOX"], MS["TEXTBOX_OPEN"]), 120),
    f"floor={current_floor(g)} level={d['level']} items={d['inventory']} torch={d['has_torch']} ms={g.ms()}")
g.close()
chk.summary()
