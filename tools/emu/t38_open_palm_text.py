"""T38 - Open Palm opens with its own line, and a trip reads after the damage.

Open Palm opens with "You strike with an open palm!" whether or not the blow
trips its target. The trip line, "You trip <name> <id>!", follows the damage
line in the result, and shows exactly when the trip happened: a palm the target
phases out of trips nothing, and neither does one that fells it, even a death
knight that rises from the blow.

A damage line takes two of the text box's four rows, and the trip line fits on
the two below it. A resisted hit's line takes three, so there the trip line
gets a page of its own instead of splitting across the page break.

A level 53 monk palms floor 2's bugbear from one savestate over battle seeds,
at HP no palm can take. The trip roll comes before the damage roll, so a seed
rolls the same trip and the same damage at any HP: the killing, resisted, and
phased cases replay the seeds that tripped, and a killing palm has to read
exactly the damage line its seed read standing. The death knight case plays
floor 8's knight at 1 HP until it rises from a palm whose seed trips.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "playtest"))
from lotd import *
from helpers import *
from starts import start_on
from knight import start_fight

chk = Checker("t38_open_palm_text")
MONK, OPEN_PALM = 2, 1
PRE, POST = SYM["battle_pre_message"], SYM["battle_post_message"]
SEED = SYM["__rand_seed"]
MON0 = SYM["encounter"] + 1
M_TYPE, M_MAX_HP, M_HP, M_TARGET_HP = 0, 12, 14, 16
M_DEF_BASE, M_DEF, M_AGL_BASE, M_AGL = 22, 23, 28, 29
M_RESIST, M_PARAMETER, M_TRIP = 31, 58, 59
DISPLACER_BEAST = 6                  # MonsterType, src/monster.h
PHYSICAL = 1                         # DAMAGE_PHYSICAL, src/stats.h
PAGE_DELAY, END_DELAY = 6, 7         # TextWriterState, src/text_writer.h
UNKILLABLE = 60000
SEEDS = [0x2468 + 0x3C1B * k & 0xFFFF for k in range(40)]
KNIGHT_SEEDS = [0x1357 + 0x2B7D * k & 0xFFFF for k in range(120)]
PALM = "You strike with an\nopen palm!"
TRIP = "You trip \nBugbear A!"


def raw(g, addr, n=128):
    """A C string from memory with its line and page breaks kept."""
    out = []
    for i in range(n):
        c = g.rd8(addr + i)
        if c == 0:
            break
        out.append(chr(c))
    return "".join(out)


def box(g):
    """The battle text box's four rows, as the window tilemap holds them."""
    return [g.window_text(1, row, 18).rstrip() for row in range(1, 5)]


def pages_of(g, frames=600):
    """Every page the text box finishes until the next command menu, read the
    frame the writer stops to hold it."""
    pages, last = [], None
    for _ in range(frames):
        if g.gs() != GS["BATTLE"] or at_menu(g):
            break
        state = g.rd8(TEXT_WRITER_STATE)
        if state in (PAGE_DELAY, END_DELAY) and last not in (PAGE_DELAY, END_DELAY):
            pages.append(box(g))
        last = state
        g.tick(1)
    return pages


def palm(g, state, seed, hp, resist=False, phase=False, watch=False):
    """Palm the foe from `state` with battle seed `seed` and the foe at `hp`.
    Returns (pre, post, trip_turns, target_hp, pages): the lines as written,
    with their breaks, and the text box's pages when `watch` is set. Returns
    None when the seed lets the foe move first, since its turn could spend
    rolls differently at another HP."""
    load_checkpoint(g, state)
    g.wr16(SEED, seed)
    keep_alive(g)
    # No DEF, so every palm connects, and no AGL, so the foe seldom moves first.
    for off in (M_DEF_BASE, M_DEF, M_AGL_BASE, M_AGL):
        g.wr8(MON0 + off, 0)
    g.wr16(MON0 + M_MAX_HP, max(hp, g.rd16(MON0 + M_MAX_HP)))
    g.wr16(MON0 + M_HP, hp)
    g.wr16(MON0 + M_TARGET_HP, hp)
    g.wr8(MON0 + M_TRIP, 0)
    g.wr8(MON0 + M_RESIST, PHYSICAL if resist else 0)
    if phase:
        g.wr8(MON0 + M_TYPE, DISPLACER_BEAST)
    # The bugbear's roar charge, or the displacer beast's count to its next
    # phase: 1 phases on this blow, 0 keeps the bugbear from roaring.
    g.wr8(MON0 + M_PARAMETER, 1 if phase else 0)
    g.wr8(PRE, 0)
    g.wr8(POST, 0)
    if not cast(g, OPEN_PALM, wait=1):
        return None
    if not g.wait_for(lambda: g.rd8(PRE) != 0, 600):
        return None
    g.tick(2)
    if not raw(g, PRE).startswith("You"):
        return None
    out = (raw(g, PRE), raw(g, POST), g.rd8(MON0 + M_TRIP), g.rd16(MON0 + M_TARGET_HP))
    return out + ((pages_of(g) if watch else None),)


def split(post):
    """(damage line, separator, trip line) of a result, or (post, None, None)."""
    at = post.find("You trip")
    if at < 1:
        return post, None, None
    return post[:at - 1], post[at - 1], post[at:]


g, _ = start_on(2, class_id=MONK, level=53, abilities=0x3F, tag="t38_bugbear")
# NPC_1, the bugbear elite, stands at (3,5) (src/floor2.c).
g.teleport(3, 6, "UP"); g.tick(4)
g.interact()
ok = g.wait_for(lambda: at_menu(g), 1800)
chk("T38 the fight with floor 2's bugbear starts", ok,
    f"gs={g.gs()} ms={g.ms()} pos={g.pos()}")
save_checkpoint(g, "t38_bugbear.state")

standing = {}
for seed in SEEDS:
    out = palm(g, "t38_bugbear.state", seed, UNKILLABLE)
    if out:
        standing[seed] = out
tripped = [s for s, out in standing.items() if out[2]]
kept = [s for s, out in standing.items() if not out[2]]
print(f"palms={len(standing)} tripped={len(tripped)} kept their feet={len(kept)}")

chk("T38 the monk moves first and palms on most seeds", len(standing) >= 30,
    f"{len(standing)}/{len(SEEDS)}")
chk("T38 some palms trip and some do not", len(tripped) >= 3 and len(kept) >= 3,
    f"tripped={len(tripped)} kept={len(kept)}")
bad = [(s, out[0]) for s, out in standing.items() if out[0] != PALM]
chk("T38 every palm opens with the palm line, trip or not", not bad, bad[:3])

bad = []
for s in tripped:
    damage, sep, trip = split(standing[s][1])
    if not ("damage" in damage and sep == "\n" and damage.count("\n") == 1 and trip == TRIP):
        bad.append((s, standing[s][1]))
chk("T38 a trip's result is the damage line with the trip line on the next row",
    tripped and not bad, bad[:3])
bad = [(s, standing[s][1]) for s in kept if "trip" in standing[s][1]]
chk("T38 a palm that does not trip never says it did", not bad, bad[:3])

if tripped:
    seed = tripped[0]
    pages = palm(g, "t38_bugbear.state", seed, UNKILLABLE, watch=True)[4]
    damage = split(standing[seed][1])[0].split("\n")
    want = [damage[0].rstrip(), damage[1].rstrip(), "You trip", "Bugbear A!"]
    chk("T38 on screen, the damage and trip lines share one page", want in pages,
        f"want={want} pages={pages}")

# A killing palm: the same seeds, with the bugbear at 1 HP.
bad = []
for s in tripped:
    out = palm(g, "t38_bugbear.state", s, 1)
    if not out or out[3] != 0 or out[2] or out[1] != split(standing[s][1])[0]:
        bad.append((s, out and out[1:4]))
chk("T38 a palm that fells its foe reads only its damage line and trips nothing",
    tripped and not bad, bad[:3])

# A resisted palm: the same seeds, with the bugbear resisting physical damage.
resisted, bad = [], []
for s in tripped:
    out = palm(g, "t38_bugbear.state", s, UNKILLABLE, resist=True)
    if not out:
        bad.append((s, None))
        continue
    if "resist" not in out[1]:
        continue                     # a critical hit ignores resistance
    resisted.append(s)
    damage, sep, trip = split(out[1])
    if not (damage.count("\n") == 2 and sep == "\f" and trip == TRIP and out[2]):
        bad.append((s, out[1:3]))
chk("T38 a resisted palm that trips gives the trip line its own page",
    resisted and not bad, f"resisted={len(resisted)} bad={bad[:3]}")
if resisted:
    seed = resisted[0]
    out = palm(g, "t38_bugbear.state", seed, UNKILLABLE, resist=True, watch=True)
    rows = [r.rstrip() for r in split(out[1])[0].split("\n")]
    pages = out[4]
    want = [rows + [""], ["You trip", "Bugbear A!", "", ""]]
    shown = any(pages[k:k + 2] == want for k in range(len(pages)))
    chk("T38 on screen, the resisted line holds its page and the trip line follows",
        shown, f"want={want} pages={pages}")

# A phased palm: the same seeds, against a displacer beast one blow from phasing.
bad = []
for s in tripped:
    out = palm(g, "t38_bugbear.state", s, UNKILLABLE, phase=True)
    if not out or "phase" not in out[1] or "trip" in out[1] or out[2]:
        bad.append((s, out and out[1:3]))
chk("T38 a palm the foe phases out of trips nothing", tripped and not bad, bad[:3])
g.close()

# A death knight rising from the palm: the rise replaces the result line, so
# the knight must not be left tripped without a word.
g, ok = start_fight(MONK, 81, "t38_knight")
chk("T38 the fight with floor 8's death knight starts", ok,
    f"gs={g.gs()} ms={g.ms()} pos={g.pos()}")
save_checkpoint(g, "t38_knight.state")
rises, found = 0, None
for seed in KNIGHT_SEEDS:
    out = palm(g, "t38_knight.state", seed, 1)
    if not out or "revives" not in out[1]:
        continue
    rises += 1
    standing_out = palm(g, "t38_knight.state", seed, UNKILLABLE)
    if standing_out and standing_out[2]:
        found = (seed, out, standing_out)
        break
g.close()
print(f"knight rises={rises} found={found and found[0]}")
chk("T38 a palm that trips the standing knight fells it, and it rises", found,
    f"rises={rises}")
if found:
    seed, out, standing_out = found
    chk("T38 the risen knight is not tripped, and the rise line shows alone",
        out[2] == 0 and "trip" not in out[1],
        f"trip_turns={out[2]} post={out[1]!r}")
chk.summary()
