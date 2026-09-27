"""T21 - floor 6's boss door needs both wing levers, and says so.

on_pulled() opens DOOR_1 only once LEVER_3 and LEVER_4 have both been thrown.
Only one wing holds a reward worth detouring for, so a player can reasonably
skip the other, and the first lever pulled has to say why the boss door stays
shut. The hint lives in floor_common rather than floor6's namespace, next to
the light_fires message it matches in shape.
"""
from lotd import *

chk = Checker("t21_floor6_lever_hint")
LEVER_3, LEVER_4 = (3, 15), (12, 24)
DOOR = SYM["flags_door_locked"]

tmpl, pos, d = make_floor_template(6, hero=0, has_torch=True, tag="t21tmpl")
g = Game(tag="t21", sram=tmpl + bytes(SLOT_STRIDE - SAVE_SIZE))
assert g.boot_to_save_select(), "no save select"
g.tick(10)
g.save_select_pick(0)
chk("T21 load floor 6 save -> map idle", g.wait_map_idle(900), f"gs={g.gs()} ms={g.ms()}")
g.tick(20)


def textbox_lines():
    return [g.window_text(1, 1 + r, 18).rstrip() for r in range(4)]


def pull(x, y, label):
    """Pull the lever once from the first reachable neighbor.

    Exactly one press, and no retry from another tile when nothing opens: a
    lever that pulls silently and one that cannot be reached are different
    failures, and retrying turns the first into a second press on an
    already-thrown lever, which answers "It's stuck!" and hides what happened.
    Returns the textbox text, or None if the pull said nothing.
    """
    for nx, ny, dd in ((x, y + 1, "UP"), (x, y - 1, "DOWN"),
                       (x - 1, y, "RIGHT"), (x + 1, y, "LEFT")):
        g.teleport(nx, ny, dd); g.tick(8)
        if g.pos() != (nx, ny):
            continue
        g.press("a", wait=12)
        if not g.wait_for(lambda: g.ms() in (MS["TEXTBOX"], MS["TEXTBOX_OPEN"]), 200):
            return None
        g.tick(120)
        lines = textbox_lines()
        g.shot(f"t21_{label}")
        for _ in range(10):
            g.press("a", wait=30)
            if g.ms() == MS["WAITING"]:
                break
        return " ".join(l for l in lines if l)
    raise AssertionError(f"no reachable tile next to the lever at ({x},{y})")


boss_locked_before = bool(g.rd16(DOOR) & 0x01)
chk("T21 the boss door starts locked", boss_locked_before, hex(g.rd16(DOOR)))

first = pull(*LEVER_3, "one_lever")
print("after the first lever:", repr(first))
chk("T21 one lever alone says another still holds the door",
    first is not None and "another lever" in first.lower(), repr(first))
chk("T21 and the boss door is still locked", g.rd16(DOOR) & 0x01, hex(g.rd16(DOOR)))

second = pull(*LEVER_4, "both_levers")
print("after the second lever:", repr(second))
chk("T21 the second lever opens the boss door", not (g.rd16(DOOR) & 0x01),
    hex(g.rd16(DOOR)))
chk("T21 and says so rather than repeating the hint",
    second is not None and "another lever" not in second.lower(), repr(second))

g.close()
chk.summary()
