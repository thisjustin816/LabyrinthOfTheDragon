"""T39 - the time before play counts toward the dice.

The first move on each map seeds the dice from map.c's new_seed, a running
frame count since power-on that keeps adding the frames the player waits on
each map before moving. With RANDOM_SEED at 0, main.c also adds every frame on
the title, file, hero, and name screens, so the same save plays out
differently depending on when the player pressed START on the title.

Each case powers on, waits on the main title until it reads START, waits a
chosen number of frames more, and presses START once. The file screen has to
show new_seed ahead by exactly the extra wait, and the same wait has to give
the same seed, since the suites depend on repeatable runs. Time on the file
screen counts the same way. Then, from one save with the file and map timing
held fixed, the first random fight on floor 1 has to change with the title wait
alone and repeat for a repeated wait. Once the first step has seeded the dice,
nothing rolls or counts on its own: idling on the map or at a battle menu
leaves the dice and the count alone.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "playtest"))
from lotd import *
from helpers import *
import heroes

chk = Checker("t39_random_seed")
SEED = SYM["__rand_seed"]
NEW_SEED = SYM.get("new_seed") or STATIC.get("map.new_seed")
MTS = SYM["main_title_state"]
MON0 = SYM["encounter"] + 1
TITLE_MAIN, MAIN_WAIT_FOR_INPUT = 2, 1     # title_screen.c
TITLE_WAITS = [0, 1, 2, 5, 60, 250]
FILE_WAITS = [8, 9, 15, 98]                # the file screen ignores A for its first frames
FIGHT_WAITS = [1, 30, 200, 450, 900]
IDLE = 300

blob, _ = heroes.build_character(1, 12, floor=1, tag="t39_hero")
SRAM = heroes.sram_for(bytes(fix_checksum(bytearray(blob))))


def at_title_prompt(g):
    return g.get("title_state") == TITLE_MAIN and g.rd8(MTS) == MAIN_WAIT_FOR_INPUT


def to_file_screen(g, wait):
    """Wait `wait` frames past the title's first START-reading frame, press
    START, and return new_seed on the file screen's first frame."""
    if not g.wait_for(lambda: at_title_prompt(g), 3000):
        return None
    g.tick(wait)
    g.press("start", hold=2, wait=0)
    if not g.wait_for(lambda: g.gs() == GS["SAVE_SELECT"], 300):
        return None
    return g.rd16(NEW_SEED)


def to_map(g, title_wait, file_wait):
    """Load the save with the given waits; True once the map is idle."""
    if to_file_screen(g, title_wait) is None:
        return False
    g.tick(file_wait)
    g.save_select_pick(0)
    g.wait_map_idle(600)
    return g.gs() == GS["WORLD_MAP"]


def first_fight(g, idle_check=False):
    """Pace floor 1's entrance until a random fight starts. Returns the step
    it came on and its monsters as (type, level) pairs, or None."""
    dirs, di, steps = ["RIGHT", "LEFT"], 0, 0
    for _ in range(400):
        if g.gs() == GS["BATTLE"] or g.ms() in (MS["INITIATE_BATTLE"], MS["START_BATTLE"]):
            if not g.wait_for(lambda: at_menu(g), 600):
                return None
            return steps, tuple((g.rd8(MON0 + 64 * k), g.rd8(MON0 + 64 * k + 9))
                                for k in range(3) if g.rd8(MON0 + 64 * k + 5))
        if g.step(dirs[di]):
            steps += 1
        else:
            di ^= 1
            if g.step(dirs[di]):
                steps += 1
            else:
                dirs = ["UP", "DOWN"] if dirs[0] == "RIGHT" else ["RIGHT", "LEFT"]
        if idle_check and steps == 1:
            dice, count = g.rd16(SEED), g.rd16(NEW_SEED)
            g.tick(IDLE)
            chk("T39 once the first step has seeded the dice, idling on the map rolls and counts nothing",
                (g.rd16(SEED), g.rd16(NEW_SEED)) == (dice, count),
                f"dice {dice:#06x} -> {g.rd16(SEED):#06x}, count {count} -> {g.rd16(NEW_SEED)}")
        if steps >= 120:
            break
    return None


at_file = {}
for wait in TITLE_WAITS:
    g = Game(tag=f"t39_title_{wait}")
    at_file[wait] = to_file_screen(g, wait)
    g.close()
print("new_seed on the file screen by title wait:", at_file)
chk("T39 every run reaches the file screen", None not in at_file.values(), at_file)
if None not in at_file.values():
    base = at_file[TITLE_WAITS[0]]
    chk("T39 each extra frame on the title adds one to the seed count",
        all(at_file[w] - base == w for w in TITLE_WAITS), at_file)

g = Game(tag="t39_title_again")
again = to_file_screen(g, TITLE_WAITS[3])
g.close()
chk("T39 the same wait on the title gives the same count", again == at_file[TITLE_WAITS[3]],
    f"{again} vs {at_file[TITLE_WAITS[3]]}")

on_map = {}
for wait in FILE_WAITS:
    g = Game(tag=f"t39_file_{wait}", sram=SRAM)
    on_map[wait] = g.rd16(NEW_SEED) if to_map(g, 0, wait) else None
    g.close()
print("new_seed on the map by file-screen wait:", on_map)
chk("T39 every file-screen run reaches the map", None not in on_map.values(), on_map)
if None not in on_map.values():
    base = on_map[FILE_WAITS[0]]
    chk("T39 each extra frame on the file screen adds one to the seed count",
        all(on_map[w] - base == w - FILE_WAITS[0] for w in FILE_WAITS), on_map)

fights = {}
for wait in FIGHT_WAITS:
    g = Game(tag=f"t39_fight_{wait}", sram=SRAM)
    fights[wait] = first_fight(g, idle_check=(wait == FIGHT_WAITS[0])) if to_map(g, wait, 8) else None
    if wait == FIGHT_WAITS[0] and fights[wait]:
        dice = g.rd16(SEED)
        g.tick(IDLE)
        chk("T39 idling at a battle menu rolls nothing", g.rd16(SEED) == dice,
            f"{dice:#06x} -> {g.rd16(SEED):#06x}")
    g.close()
print("first fight (step, monsters) by title wait:", fights)
chk("T39 every run meets a random fight", None not in fights.values(), fights)
distinct = len(set(fights.values()))
chk("T39 a different wait on the title changes the first fight after the same save",
    distinct >= len(FIGHT_WAITS) - 1, f"{distinct} distinct of {len(FIGHT_WAITS)}")

g = Game(tag="t39_fight_again", sram=SRAM)
repeat = first_fight(g) if to_map(g, FIGHT_WAITS[2], 8) else None
g.close()
chk("T39 the same waits give the same first fight", repeat == fights[FIGHT_WAITS[2]],
    f"{repeat} vs {fights[FIGHT_WAITS[2]]}")
chk.summary()
