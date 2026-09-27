"""T41 - floor 7's eye lock follows two rules and starts over on each visit,
and the sconce pocket's crack drops you in front of the item room's door.

The left lever opens or shuts the left eye. The right lever moves every eye
one place right, the rightmost coming around to the left. A door is open
while the eye above it is shut: the elite's under the left eye, the item
room's under the right, and the boss door under the middle one, which opens
only when all three are shut and then locks both levers. The orb above the
boss door lights green then, as each switch's orb does when it's pressed.

Every visit to the floor starts with the eyes open, so the lock has to start
there too. The trip back down after a death reloads the floor, which redraws the
eyes and relocks the levers, and on_init puts puzzle_state back to match.

The pocket under the item room is left by a cracked floor at (21,30), below
the room's doorway, which drops you at (9,27), in front of the item room's
door in the lever hall.
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "playtest"))
from lotd import *
from helpers import *
from starts import start_on

chk = Checker("t41_floor7_eye_lock")
STATE = SYM["puzzle_state"]
STUCK = SYM["flags_lever_stuck"]
DOORS = SYM["flags_door_locked"]
LEVER_1, LEVER_2 = 1 << 0, 1 << 1                 # src/map.h
BOSS_DOOR, ELITE_DOOR, ITEM_DOOR = 1 << 1, 1 << 2, 1 << 3
EYES = [(7, 25), (8, 24), (9, 25)]                # left, middle, right
SHUT_EYE = 0x35                                   # floor7.c set_eyes()
LEVERS = {"left": (7, 28), "right": (9, 28)}
SWITCHES = [(7, 5), (13, 5)]                      # free LEVER_1 and LEVER_2
BOSS_ORB, BOSS_DOORWAY = (8, 25), (8, 26)
LIT_ORB = 4                                       # the palette floor7.c lights orbs with


def eyes(g):
    """Which eyes are shut, left to right, as 1 and 0."""
    ov = tile_overrides(g)
    return tuple(int(ov.get((0, x, y), (None,))[0] == SHUT_EYE) for x, y in EYES)


def door_open(g, door):
    return not g.rd16(DOORS) & door


def free_levers(g):
    """Step onto both key rooms' switches, as a player does."""
    for x, y in SWITCHES:
        g.teleport(x, y + 1, "UP")
        g.tick(4)
        g.step("UP")
        g.wait_map_idle(300)
    return not g.rd8(STUCK) & (LEVER_1 | LEVER_2)


def pull(g, side):
    x, y = LEVERS[side]
    g.teleport(x, y + 1, "UP")
    g.tick(4)
    g.press("a", wait=30)
    for _ in range(10):
        if g.ms() == MS["WAITING"]:
            break
        g.press("a", wait=30)
    g.wait_map_idle(300)
    return g.rd8(STATE)


g, _ = start_on(7, class_id=1, level=40, tag="t41")
chk("T41 the lock starts with every eye open", g.rd8(STATE) == 0 and eyes(g) == (0, 0, 0),
    f"state={g.rd8(STATE)} eyes={eyes(g)}")
chk("T41 the key rooms' switches free both levers", free_levers(g), f"stuck={g.rd8(STUCK):#04x}")

# (lever, shut eyes after the pull, elite door open, item door open)
STEPS = [("left", (1, 0, 0), True, False),
         ("right", (0, 1, 0), False, False),
         ("left", (1, 1, 0), True, False),
         ("right", (0, 1, 1), False, True),
         ("left", (1, 1, 1), True, True)]
for n, (side, shut, elite, item) in enumerate(STEPS, 1):
    pull(g, side)
    got = (eyes(g), door_open(g, ELITE_DOOR), door_open(g, ITEM_DOOR))
    chk(f"T41 pull {n}, the {side} lever: eyes {shut}, elite door "
        f"{'open' if elite else 'shut'}, item room door {'open' if item else 'shut'}",
        got == (shut, elite, item), f"got eyes={got[0]} elite={got[1]} item={got[2]} state={g.rd8(STATE)}")
chk("T41 with all three shut the boss door opens and both levers lock",
    door_open(g, BOSS_DOOR) and g.rd8(STUCK) & (LEVER_1 | LEVER_2) == LEVER_1 | LEVER_2,
    f"doors={g.rd16(DOORS):#06x} stuck={g.rd8(STUCK):#04x}")
ov = tile_overrides(g)
orb, doorway = (ov.get((0,) + p, (None, None))[1] for p in (BOSS_ORB, BOSS_DOORWAY))
chk("T41 and the orb above the boss door lights, leaving the doorway's colors alone",
    orb == LIT_ORB and doorway != LIT_ORB, f"orb palette={orb} doorway palette={doorway}")

# A new visit, as after a death: the eyes are open again, and so is the lock.
chk("T41 floor 7 loads afresh", reenter_floor(g, 7, 8, 29), f"pos={g.pos()} floor={current_floor(g)}")
chk("T41 a new visit starts the lock over with the eyes it draws",
    g.rd8(STATE) == 0 and eyes(g) == (0, 0, 0) and not door_open(g, BOSS_DOOR),
    f"state={g.rd8(STATE)} eyes={eyes(g)} doors={g.rd16(DOORS):#06x}")
chk("T41 and its levers are stuck again until the switches free them",
    g.rd8(STUCK) & (LEVER_1 | LEVER_2) == LEVER_1 | LEVER_2 and free_levers(g),
    f"stuck={g.rd8(STUCK):#04x}")
for side in ("left", "right", "right"):
    pull(g, side)
chk("T41 then left, right, right shuts only the right eye and opens the item room",
    eyes(g) == (0, 0, 1) and door_open(g, ITEM_DOOR) and not door_open(g, ELITE_DOOR),
    f"eyes={eyes(g)} doors={g.rd16(DOORS):#06x}")

# The pocket's way out.
chk("T41 standing in the pocket above its crack", reenter_floor(g, 7, 21, 29),
    f"pos={g.pos()}")
g.step("DOWN")
g.wait_for(lambda: g.pos() != (21, 30) and g.ms() == MS["WAITING"], 600)
g.tick(20)
chk("T41 the pocket's crack drops you in front of the item room's door",
    current_floor(g) == 7 and g.pos() == (9, 27), f"floor={current_floor(g)} pos={g.pos()}")
g.close()
chk.summary()
