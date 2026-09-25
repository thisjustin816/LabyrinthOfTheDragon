"""T44 - an elite beaten again doesn't teach its ability twice.

Floors 2 to 6's elites each teach an ability. A death sends the hero back to
floor 1, and every floor on the way down loads afresh with its elite back in
place, so beating one again used to replay the power-up and "You learn to use
Action Surge!" for an ability the hero already had. teach_elite_ability()
(src/floor_common.c) says "You've learned all it can teach." instead.

Floor 2's bugbear is beaten twice, the floor loading afresh in between: the
first win teaches Action Surge, the second says so and changes nothing. Then
each of floors 3 to 6's elites is beaten by a hero who already knows all six.
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "playtest"))
from lotd import *
from helpers import *
from starts import start_on

chk = Checker("t44_repeat_elites")
FLAGS = PL + POFF["ability_flags"]
MON0 = SYM["encounter"] + 1
M_HP, M_TARGET_HP = 14, 16
REPEAT = "learned all it can teach"
# floor: (map, elite's tile, the ability bit it teaches), from each floor's npcs[]
ELITES = {2: (0, (3, 5), 1 << 1), 3: (0, (3, 2), 1 << 2), 4: (0, (1, 3), 1 << 3),
          5: (1, (11, 3), 1 << 4), 6: (0, (23, 4), 1 << 5)}


def beat_elite(g, floor):
    """Face the elite, win at once, and return the textbox that follows."""
    map_id, (x, y), _ = ELITES[floor]
    if not reenter_floor(g, floor, x, y + 1, map_id):
        return None
    g.teleport(x, y + 1, "UP")
    g.interact()
    if not g.wait_for(lambda: at_menu(g), 1200):
        return None
    for _ in range(6):
        g.wait_for(lambda: at_menu(g) or g.gs() != GS["BATTLE"], 2000)
        if g.gs() != GS["BATTLE"]:
            break
        g.wr16(MON0 + M_HP, 1)
        g.wr16(MON0 + M_TARGET_HP, 1)
        g.battle_menu_goto(0)
        g.press("a", wait=12)
        g.press("a", wait=12)
        for _ in range(300):
            if g.gs() != GS["BATTLE"] or at_menu(g):
                break
            g.press("a", hold=2, wait=8)
    if not g.wait_for(lambda: g.gs() == GS["WORLD_MAP"], 1200):
        return None
    # The map settles for a frame between the fight and the box, which
    # read_textbox() would take for a box that never came.
    g.wait_for(lambda: g.ms() in (MS["TEXTBOX"], MS["TEXTBOX_OPEN"]), 300)
    return " ".join(read_textbox(g, shot=f"t44_floor{floor}"))


g, _ = start_on(2, class_id=1, level=60, abilities=0x01, tag="t44")
text = beat_elite(g, 2)
chk("T44 the first win over floor 2's bugbear teaches Action Surge",
    text is not None and "Action Surge" in text and g.rd8(FLAGS) == 0x03,
    f"text={text!r} flags={g.rd8(FLAGS):#04x}")
text = beat_elite(g, 2)
chk("T44 the second, after the floor loads afresh, says there's nothing left to learn",
    text is not None and REPEAT in text and "Action Surge" not in text and g.rd8(FLAGS) == 0x03,
    f"text={text!r} flags={g.rd8(FLAGS):#04x}")
g.close()

for floor in (3, 4, 5, 6):
    g, _ = start_on(floor, class_id=1, level=60, abilities=0x3F, tag=f"t44f{floor}")
    text = beat_elite(g, floor)
    chk(f"T44 floor {floor}'s elite, beaten by a hero who knows everything, says so",
        text is not None and REPEAT in text and g.rd8(FLAGS) == 0x3F,
        f"text={text!r} flags={g.rd8(FLAGS):#04x}")
    g.close()
chk.summary()
