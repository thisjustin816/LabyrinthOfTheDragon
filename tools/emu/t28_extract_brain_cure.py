"""T28 - a cure clears player.debuffs the moment it runs, not next turn.

player.debuffs mirrors encounter.player_status_effects and is otherwise only
rebuilt at the start of the player's own turn. Floor 8's mind flayer reads
the mirror for Extract Brain, not the live list, so a cure that left the
mirror alone would leave the flayer treating the player as confused until
their next turn began, and Extract Brain would fire if it moved first.
use_remedy() and monk_still_mind() rebuild player.debuffs, and the stats with
it, right where they clear the live list.

The monk fights the flayer for real (Mind Blast is the only source of player
confusion in the game) and drinks a remedy the moment it lands. A confused
player's own turn can be overridden into a random self-hit instead of the
chosen action -- a separate, unrelated mechanic -- so only trials where the
remedy actually runs (its own line appears) count as evidence: on those, the
mirror must already read clear on that same line, and the flayer's next move
must not be Extract Brain.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "playtest"))
from helpers import *
from starts import start_on, reseed
import drive

chk = Checker("t28_extract_brain_cure")
PRE, POST = SYM["battle_pre_message"], SYM["battle_post_message"]
BS = SYM["battle_state"]
CONFUSED_ID = 4


def live_confused():
    for k in range(drive.EFFECT_COUNT):
        base = drive.PLAYER_EFFECTS + k * drive.EFFECT_SIZE
        if g.rd8(base) and g.rd8(base + 1) == CONFUSED_ID:
            return True
    return False


def mirror_confused():
    return bool(g.rd8(PL + POFF["debuffs"]) & 0x10)


g, _ = start_on(8, level=47, items={"POTION": 20, "REMEDY": 20, "ELIXIR": 5}, tag="t28eb")
f = Floor(8, open_doors=set(), extra_walls={("A", 2, 27), ("A", 14, 27), ("A", 3, 22),
                                            ("A", 13, 22), ("A", 4, 17), ("A", 8, 11), ("A", 8, 3)})
save_checkpoint(g, "t28eb_start.state")

cured_lines, brain_after_cure = [], []
for trial in range(1, 9):
    if trial > 1:
        load_checkpoint(g, "t28eb_start.state")
        reseed(g, 53 * trial + 7)
    res = f.path("A", g.pos(), "A", (12, 17), face_adjacent=True)
    path, facing = res
    assert drive.run_path(g, f, "A", path, "beside the mind flayer") is True
    g.wait_map_idle(300)
    g.step(facing)
    read_textbox(g)                  # the flayer's line; its fight starts as the line closes
    assert g.wait_for(lambda: g.gs() == GS["BATTLE"], 300)
    seen, turn, cured_turn, drank = None, 0, None, False
    for _ in range(4000):
        if g.gs() != GS["BATTLE"]:
            break
        msg = (cstr(g, PRE), cstr(g, POST))
        if msg != seen:
            seen = msg
            if "remedy" in msg[0].lower():
                # The chosen action landed (a confused player's turn can be
                # overridden into a random self-hit instead -- a separate,
                # unrelated mechanic -- so only from here does a later
                # Extract Brain count as a failure).
                cured_lines.append((trial, msg, live_confused(), mirror_confused()))
                drank = True
            elif drank and "brain" in msg[0].lower():
                brain_after_cure.append((trial, msg))
                drank = False
        if g.rd8(BS) != 2:
            g.press("a", hold=2, wait=8)
            continue
        turn += 1
        if live_confused() and cured_turn is None:
            cured_turn = turn
            drive.use_battle_item(g, drive.ITEM["REMEDY"])
        else:
            g.battle_menu_goto(0); g.press("a", wait=12); g.press("a", wait=12)
        g.wait_for(lambda: g.rd8(BS) != 2, 60)
    if len(cured_lines) >= 3:
        break
g.close()

print("cured lines (trial, msg, live_confused, mirror_confused):", cured_lines)
print("Extract Brain after a landed cure:", brain_after_cure)
chk("T28 the remedy landed as the chosen action in at least one trial", bool(cured_lines), f"{len(cured_lines)}")
chk("T28 every landed remedy clears the live confusion on its own line",
    cured_lines and all(not live for _, _, live, _ in cured_lines), str(cured_lines))
chk("T28 every landed remedy clears the mirror on its own line, not next turn",
    cured_lines and all(not mirror for _, _, _, mirror in cured_lines), str(cured_lines))
chk("T28 no landed cure is followed by Extract Brain", not brain_after_cure, str(brain_after_cure))
chk.summary()
