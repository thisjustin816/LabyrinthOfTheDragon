"""T50 - what a death and a new floor put back: the torch goes out, and the
random encounter ramp starts over.

The hero dies on floor 2 to poison in a random fight, with a lit torch and the
encounter ramp written far along. Waking on floor 1, the torch is out, so the
first steps can meet monsters again, and the ramp is floor 1's own from its
first step: no steps counted and the floor's starting chance. Arriving on floor
2 afresh from floor 1 starts that floor's ramp over the same way.

The ramp is src/map.encounters.c's steps and current_chance. Offsets from
LabyrinthOfTheDragon.cdb: Encounter.player_status_effects at +209, a status
effect 5 bytes: active, effect, flag, duration, tier.
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "playtest"))
from lotd import *
from helpers import *
from starts import start_on

chk = Checker("t50_death_resets")
FIGHTER = 1
STEPS, CHANCE = STATIC["map_encounters.steps"], STATIC["map_encounters.current_chance"]
TORCH = SYM["player"] + POFF["torch_gauge"]
P_EFFECTS = SYM["encounter"] + 209
POISONED, S_TIER, PERPETUAL = (3, 0x08), 3, 0xFF
FLOOR_START_CHANCE = 1                         # config_random_encounter's ic, floors 1 and 2

g, _ = start_on(2, class_id=FIGHTER, level=15, tag="t50")
floor2_start = g.pos()
fought = g.walk_until_battle(("UP", "DOWN", "LEFT", "RIGHT"), max_steps=400) and \
    g.wait_for(lambda: at_menu(g), 1800)
chk("T50 a random fight starts on floor 2", fought, f"gs={g.gs()} pos={g.pos()}")

if fought:
    for off, value in enumerate((1, POISONED[0], POISONED[1], PERPETUAL, S_TIER)):
        g.wr8(P_EFFECTS + off, value)
    g.wr16(SYM["player"] + POFF["hp"], 1)
    g.wr8(TORCH, 20)
    g.wr8(STEPS, 5); g.wr8(CHANCE, 200)
    g.battle_menu_goto(0); g.press("a", wait=12); g.press("a", wait=1)
    for frame in range(6000):
        if g.gs() == GS["WORLD_MAP"] and current_floor(g) == 1 and g.ms() == MS["WAITING"]:
            break
        if frame % 10 == 0:
            g.pb.button_press("a")
        elif frame % 10 == 2:
            g.pb.button_release("a")
        g.tick(1)
    g.pb.button_release("a")
    g.wait_map_idle(600)
    g.tick(4)
awake = g.gs() == GS["WORLD_MAP"] and current_floor(g) == 1
chk("T50 the hero dies and wakes on floor 1", awake, f"gs={g.gs()} floor={current_floor(g)}")
if awake:
    chk("T50 the torch is out after a death", g.rd8(TORCH) == 0, f"torch_gauge={g.rd8(TORCH)}")
    chk("T50 the encounter ramp starts over after a death",
        (g.rd8(STEPS), g.rd8(CHANCE)) == (0, FLOOR_START_CHANCE),
        f"steps={g.rd8(STEPS)} chance={g.rd8(CHANCE)}")

    g.wr8(STEPS, 5); g.wr8(CHANCE, 200)
    arrived = reenter_floor(g, 2, *floor2_start)
    chk("T50 floor 2 loads afresh from floor 1", arrived, f"pos={g.pos()} floor={current_floor(g)}")
    chk("T50 the encounter ramp starts over on arrival",
        arrived and (g.rd8(STEPS), g.rd8(CHANCE)) == (0, FLOOR_START_CHANCE),
        f"steps={g.rd8(STEPS)} chance={g.rd8(CHANCE)}")
g.close()
chk.summary()
