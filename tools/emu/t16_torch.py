"""T16 - issue #80 follow-up: the torch burns per step, not on a wall clock.

One unit per completed step, so a full torch is 32 steps of light and time
spent standing still or reading a textbox costs nothing. A lit torch
suppresses random encounters entirely, so a torch that drained on a clock
would cover far fewer steps than the ~25 between encounters once it goes
out.
"""
from lotd import *

chk = Checker("t16_torch")
PL = SYM["player"]


def light(g):
    g.wr8(PL + POFF["has_torch"], 1)
    g.wr8(PL + POFF["torch_gauge"], 32)
    g.wr8(PL + POFF["torch_color"], 1)


def gauge(g):
    return g.rd8(PL + POFF["torch_gauge"])


# --- standing still must cost nothing
g = Game(tag="t16a")
g.boot_to_save_select(); g.save_select_pick(0); g.hero_select_pick(0); g.tick(20)
light(g)
g.tick(600)          # ten seconds of no input at all
idle_gauge = gauge(g)
print("gauge after 600 idle frames:", idle_gauge, "of 32")
chk("T16 standing still does not burn the torch", idle_gauge == 32, str(idle_gauge))
g.close()

# --- each step costs exactly one unit
g = Game(tag="t16b")
g.boot_to_save_select(); g.save_select_pick(0); g.hero_select_pick(0); g.tick(20)
light(g)
steps = 0
per_step = []
for _ in range(6):
    before_pos, before_gauge = g.pos(), gauge(g)
    moved = False
    for d in ("UP", "DOWN", "LEFT", "RIGHT"):
        g.step(d); g.wait_map_idle(200)
        if g.pos() != before_pos:
            moved = True
            break
    if not moved or g.gs() != GS["WORLD_MAP"]:
        break
    steps += 1
    per_step.append(before_gauge - gauge(g))
print("gauge drop per step:", per_step, "after", steps, "steps gauge is", gauge(g))
chk("T16 took some steps", steps >= 3, str(steps))
chk("T16 every step costs exactly one unit", per_step and all(d == 1 for d in per_step),
    str(per_step))
chk("T16 the gauge falls from a full 32 by one for each step taken", gauge(g) == 32 - steps,
    f"{gauge(g)} after {steps} steps")
g.close()
chk.summary()
