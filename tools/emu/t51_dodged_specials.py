"""T51 - a special the monk's Evasion dodges keeps its charge, as a miss does.

Monster.parameter counts what is left of a monster's limited special: the
owlbear's pounces that knock the hero down, and the beholder's eyestalk rays.
A special that misses spends nothing, and a dodge now counts as a miss: the
charge stays and the special can come again, the way the mind flayer's Mind
Blast already worked. A special that lands still spends one.

Each case gives a monk Evasion in the monster's fight on floor 8, the gauntlet
owlbear and the elite beholder, and replays the round across battle seeds with
the charge topped up and the monster out of reach of any blow. Every round
whose monster line was the special then compares the charge left with the one
before it.

Offsets from LabyrinthOfTheDragon.cdb: Encounter.monsters at +1, hp +14,
target_hp +16, parameter +58. SPECIAL_EVASION is FLAG(2) of
player.special_flags (src/player.h).
"""
import io, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "playtest"))
from lotd import *
from helpers import *
from starts import start_on

chk = Checker("t51_dodged_specials")
MONK, LEVEL = 2, 60
SEED = SYM["__rand_seed"]
SEEDS = [0x2C41 + 0x3B7F * k & 0xFFFF for k in range(96)]
MON0 = SYM["encounter"] + 1
M_HP, M_TARGET_HP, M_PARAMETER = 14, 16, 58
SPECIAL_EVASION = 1 << 2
CHARGE = 3
DODGED = "But you evade!"
OWLBEAR = (14, 27)                             # gauntlet fight tile, src/floor8.c
BEHOLDER = (8, 11)                             # NPC_2, the elite, src/floor8.c


def fight(g):
    g.battle_menu_goto(0); g.press("a", wait=12); g.press("a", wait=1)


def specials(g, state, words):
    """Replay the round from `state` across seeds with Evasion up and the
    charge at CHARGE, and collect (post line, charge left) for every round
    whose monster line carried `words`."""
    seen = []
    for seed in SEEDS:
        state.seek(0); g.pb.load_state(state)
        g.wr16(SEED, seed)
        keep_alive(g)
        g.wr16(MON0 + M_HP, 60000); g.wr16(MON0 + M_TARGET_HP, 60000)
        g.wr8(MON0 + M_PARAMETER, CHARGE)
        g.wr8(PL + POFF["special_flags"], g.rd8(PL + POFF["special_flags"]) | SPECIAL_EVASION)
        fight(g)
        post = next((p for pre, p, _ in round_messages(g) if words in pre), None)
        if post is not None:
            seen.append((post, g.rd8(MON0 + M_PARAMETER)))
    return seen


def charge_checks(monster, special, seen, landed):
    dodged = [left for post, left in seen if post == DODGED]
    hit = [left for post, left in seen if landed(post)]
    chk(f"T51 Evasion dodged the {monster}'s {special} in some rounds", dodged,
        f"{len(seen)} {special}s: {sorted(set(post for post, _ in seen))}")
    chk(f"T51 a dodged {special} keeps its charge", dodged and all(left == CHARGE for left in dodged),
        f"charge left after each dodge: {dodged}")
    chk(f"T51 a {special} that lands still spends one", hit and all(left == CHARGE - 1 for left in hit),
        f"charge left after each landed {special}: {hit}")


# --- the gauntlet owlbear's pounce --------------------------------------------
g, _ = start_on(8, class_id=MONK, level=LEVEL, abilities=0x3F, tag="t51_owlbear")
started = reenter_floor(g, 8, OWLBEAR[0] + 1, OWLBEAR[1])
if started:
    g.step("LEFT"); read_textbox(g)
    started = g.wait_for(lambda: at_menu(g), 1800)
chk("T51 the gauntlet owlbear's fight starts", started, f"gs={g.gs()} pos={g.pos()}")
state = io.BytesIO(); g.pb.save_state(state)
charge_checks("owlbear", "pounce", specials(g, state, "pounces") if started else [],
              lambda post: "fall prone" in post)
g.close()

# --- the elite beholder's eyestalk ray ----------------------------------------
g, _ = start_on(8, class_id=MONK, level=LEVEL, abilities=0x3F, tag="t51_beholder")
g.teleport(BEHOLDER[0], BEHOLDER[1] + 1, "UP"); g.tick(4)
g.press("a", wait=10); read_textbox(g)
started = g.wait_for(lambda: at_menu(g), 1800)
chk("T51 the elite beholder's fight starts", started, f"gs={g.gs()} pos={g.pos()}")
state = io.BytesIO(); g.pb.save_state(state)
charge_checks("beholder", "ray", specials(g, state, "shoots a ray") if started else [],
              lambda post: post not in (DODGED, "But you dodge the ray!"))
g.close()

chk.summary()
