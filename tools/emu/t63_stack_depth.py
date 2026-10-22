"""T63 - the stack's depth in play against the Makefile's STACK_RESERVE, the
room tools/romcheck makes static work RAM leave below $E000 for the stack.

Once a run settles on the map, the free work RAM between static data and the
stack is filled with 0xA5. The run then saves, fights, and loads floors, and
the lowest byte no longer 0xA5 marks the deepest the stack went. The deepest
of every run must stay at least MARGIN bytes inside the reserve.
"""
import os, re, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "playtest"))
from starts import start_on
from helpers import *
chk = Checker("t63_stack_depth")

STACK_TOP = 0xE000
MARGIN = 256
HEAP_END = int(re.search(r"DEF s__HEAP_END 0x([0-9A-Fa-f]+)", NOI_TEXT).group(1), 16)
RESERVE = int(re.search(r"^STACK_RESERVE *= *(\d+)", open(os.path.join(REPO, "Makefile")).read(), re.M).group(1))
FILL = 0xA5


def fill(g):
    """Fill the free work RAM up to 16 bytes short of the stack pointer."""
    sp = g.pb.register_file.SP
    g.pb.memory[HEAP_END:sp - 16] = [FILL] * (sp - 16 - HEAP_END)


def depth(g):
    """How far below STACK_TOP the stack has reached since the fill."""
    free = g.pb.memory[HEAP_END:STACK_TOP]
    lowest = next((HEAP_END + k for k, b in enumerate(free) if b != FILL), STACK_TOP)
    return STACK_TOP - lowest


depths = {}

# A new game: two saves around a fight, and a fresh load of floor 1.
g = Game(tag="t63a")
assert g.boot_to_save_select()
g.save_select_pick(0)
assert g.hero_select_pick(0)
g.tick(20)
fill(g)
menu_save(g, chk, "T63 floor 1 save")
start = g.pos()
chk("T63 floor 1 fight", g.walk_until_battle(max_steps=120) > 0 and resolve_battle(g) in ("victory", "fled", "death"))
g.wait_map_idle(2400)
menu_save(g, chk, "T63 floor 1 save after the fight")
chk("T63 floor 1 loads afresh", reenter_floor(g, 1, *start))
depths["floor 1: saves, a fight, a load"] = depth(g)
g.close()

# Floor 7 at its gate level with every ability, fighting with buffs and items.
g, _ = start_on(7, items={"POTION": 5, "ETHER": 5, "ATK_UP": 2, "DEF_UP": 2}, tag="t63b")
fill(g)
steps = g.walk_until_battle(max_steps=200)
outcome = resolve_battle(g, use_buffs=True) if steps else None
chk("T63 floor 7 fight", outcome in ("victory", "fled"), f"steps={steps} outcome={outcome}")
g.wait_map_idle(2400)
depths["floor 7: a fight with abilities and items"] = depth(g)
g.close()

# Every other floor's load and on_init.
for floor in range(2, 9):
    g, _ = start_on(floor, tag=f"t63f{floor}")
    fill(g)
    chk(f"T63 floor {floor} loads afresh", reenter_floor(g, floor, *g.pos()))
    depths[f"floor {floor}: a load"] = depth(g)
    g.close()

for run, d in depths.items():
    print(f"  {d:5d} bytes  {run}")
deepest = max(depths.values())
chk(f"T63 the deepest stack, {deepest} bytes, stays {MARGIN} bytes inside the {RESERVE}-byte reserve",
    deepest + MARGIN <= RESERVE, f"room left: {RESERVE - deepest}")
chk("T63 the fill reached work RAM the stack never used", all(d < STACK_TOP - HEAP_END for d in depths.values()),
    f"free work RAM: {STACK_TOP - HEAP_END} bytes")
chk.summary()
