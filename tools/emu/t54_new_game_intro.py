"""T54 - a new game opens on one line of story, and nothing else does.

start_game() sets new_game_intro, and floor 1's on_init shows
str_floor1_intro before the hero can take a step, then clears the flag. A
death or a load wakes on floor 1 without it.

The death is t50's: poison and 1 HP in a random fight. Offsets from
LabyrinthOfTheDragon.cdb: Encounter.player_status_effects at +209, a status
effect 5 bytes: active, effect, flag, duration, tier.
"""
import os, re, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "playtest"))
from lotd import *
from helpers import *
from starts import start_on

chk = Checker("t54_new_game_intro")
INTRO = re.search(r"'intro': '([^']*)'", open(os.path.join(REPO, "assets", "strings.js")).read()).group(1)
BOXES = (MS["TEXTBOX"], MS["TEXTBOX_OPEN"])
P_EFFECTS = SYM["encounter"] + 209
POISONED, S_TIER, PERPETUAL = (3, 0x08), 3, 0xFF


def on_init_done(g):
    return g.gs() == GS["WORLD_MAP"] and not g.rd8(SYM["execute_on_init"])


def intro_shown(g):
    """The pages of any textbox that opens in the next two seconds, pressing
    nothing first."""
    return read_textbox(g) if g.wait_for(lambda: g.ms() in BOXES, 120) else []


g = Game(tag="t54")
g.boot_to_save_select(); g.save_select_pick(0)
g.wait_for(lambda: g.gs() == GS["HERO_SELECT"], 300)
g.tick(10); g.press("a", wait=12)
g.wait_for(lambda: g.gs() == GS["NAME_ENTRY"], 120)
g.tick(6); g.press("start", wait=12)
chk("T54 a new game reaches floor 1", g.wait_for(lambda: on_init_done(g), 600) and current_floor(g) == 1,
    f"gs={g.gs()} floor={current_floor(g)}")
pages = intro_shown(g)
chk("T54 a new game opens on the intro line, on one page, at the arrival tile",
    pages == [INTRO] and g.pos() == (12, 16), f"pages={pages} pos={g.pos()}")
chk("T54 the hero walks once the box closes",
    g.ms() == MS["WAITING"] and g.step("UP") and g.pos() == (12, 15), f"ms={g.ms()} pos={g.pos()}")

fought = g.walk_until_battle(("DOWN", "UP"), max_steps=400) and g.wait_for(lambda: at_menu(g), 1800)
chk("T54 a random fight starts on floor 1", fought, f"gs={g.gs()} pos={g.pos()}")
if fought:
    for off, value in enumerate((1, POISONED[0], POISONED[1], PERPETUAL, S_TIER)):
        g.wr8(P_EFFECTS + off, value)
    g.wr16(PL + POFF["hp"], 1)
    g.battle_menu_goto(0); g.press("a", wait=12); g.press("a", wait=1)
    # Press through the fight and the death, but never on the map.
    for frame in range(6000):
        if g.gs() == GS["WORLD_MAP"]:
            break
        if frame % 10 == 0:
            g.pb.button_press("a")
        elif frame % 10 == 2:
            g.pb.button_release("a")
        g.tick(1)
    g.pb.button_release("a")
    awake = g.wait_for(lambda: on_init_done(g), 600) and current_floor(g) == 1
    chk("T54 the hero dies and wakes on floor 1", awake, f"gs={g.gs()} floor={current_floor(g)}")
    pages = intro_shown(g)
    chk("T54 waking after a death shows no intro", INTRO not in pages, pages)
g.close()

g, _ = start_on(1, tag="t54b")
pages = intro_shown(g)
chk("T54 loading a save on floor 1 shows no intro", INTRO not in pages and g.ms() == MS["WAITING"],
    f"pages={pages} ms={g.ms()}")
g.close()
chk.summary()
