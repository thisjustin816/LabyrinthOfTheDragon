"""T30 - a battle item leaves the bag on its own turn.

The menu only queues an item; use_item() takes it out of the inventory on the
player's turn, the way an ability spends its SP only when it fires. A turn the
player never gets costs nothing, and an item whose use has lapsed by its turn
says "You don't need it, so you keep it." and stays. Each case queues an item
against floor 2's bugbear and reads the count once the round is over:

- prone (trip_turns), so the turn is lost and the potion stays;
- a blind with no turns left, which ends at the start of the player's turn,
  before the Remedy runs, so the Remedy says so, with the fail sound other
  lost turns play, and stays;
- the plain case, a potion drunk on its turn, which leaves the bag;
- a Remedy against a blind that lasts, which cures it with the healing sound
  the potions play.

Sounds are heard through sounds_heard(), which hooks the sound functions.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "playtest"))
from lotd import *
from helpers import *
from starts import start_on
import drive

chk = Checker("t30_item_turn")
FIGHTER = 1
PRE = SYM["battle_pre_message"]
MON0 = SYM["encounter"] + 1
M_MAX_HP, M_HP, M_TARGET_HP, M_PARAMETER = 12, 14, 16, 58
EFFECTS, EFFECT_SIZE, EFFECT_COUNT = drive.PLAYER_EFFECTS, drive.EFFECT_SIZE, drive.EFFECT_COUNT
BLIND = 0                                   # StatusEffect, src/stats.h
POTION, REMEDY = drive.ITEM["POTION"], drive.ITEM["REMEDY"]
CURED, KEPT = "You remedy what ails you!", "You don't need it, so you keep it."


def heard(g, sound, since):
    """The battle lines `sound` started under after the first `since` sounds
    sounds_heard() caught."""
    return [line for line, s in sounds_heard(g)[since:] if s == sound]

def engage(tag, items):
    """The bugbear with a bar no round can empty and no roar charge, since a
    scare would be a debuff for the Remedy to cure, facing a fighter whose HP
    is short enough of full for a potion to be usable."""
    g, _ = start_on(2, class_id=FIGHTER, level=30, items=items, tag=tag)
    # NPC_1, the bugbear elite, stands at (3,5) (src/floor2.c).
    g.teleport(3, 6, "UP"); g.tick(4)
    g.interact()
    ok = g.wait_for(lambda: at_menu(g), 1800)
    for off in (M_MAX_HP, M_HP, M_TARGET_HP):
        g.wr16(MON0 + off, 999)
    g.wr8(MON0 + M_PARAMETER, 0)
    for field, v in (("max_hp", 400), ("hp", 200), ("max_sp", 200), ("sp", 200)):
        g.wr16(PL + POFF[field], v)
    return g, ok


def play_round(g):
    """Press through the round the menu just queued, returning every line the
    round printed."""
    seen = []
    g.wait_for(lambda: g.gs() != GS["BATTLE"] or not at_menu(g), 120)
    for _ in range(400):
        if g.gs() != GS["BATTLE"] or at_menu(g):
            break
        text = cstr(g, PRE)
        if text and text not in seen:
            seen.append(text)
        g.press("a", hold=2, wait=8)
    return seen


# --- A turn the player never gets ---------------------------------------------
g, ok = engage("t30_prone", {"POTION": 2})
chk("T30 reaches the bugbear fight", ok, f"gs={g.gs()}")
g.wr8(PL + POFF["trip_turns"], 2)
chk("T30 the menu takes a potion from a prone fighter", drive.use_battle_item(g, POTION))
seen = play_round(g)
chk("T30 the turn is lost to lying prone", "You lie prone!" in seen, str(seen))
chk("T30 and the potion is still in the bag", drive.item_qty(g, POTION) == 2,
    f"qty={drive.item_qty(g, POTION)}")
g.close()

# --- An item whose use lapsed before its turn ---------------------------------
g, ok = engage("t30_lapsed", {"REMEDY": 1})
chk("T30 reaches the second bugbear fight", ok, f"gs={g.gs()}")
# Live at the menu, so the menu takes the Remedy; its countdown ends it as
# the player's turn starts.
free = next(k for k in range(EFFECT_COUNT) if not g.rd8(EFFECTS + k * EFFECT_SIZE))
for off, v in enumerate((1, BLIND, 1 << BLIND, 0, 0)):   # active, id, flag, duration, tier
    g.wr8(EFFECTS + free * EFFECT_SIZE + off, v)
mark = len(sounds_heard(g))
chk("T30 the menu takes a Remedy against the blind", drive.use_battle_item(g, REMEDY))
seen = play_round(g)
failed = heard(g, "sfx_monster_fail", mark)
chk("T30 the blind has ended by its turn, so it reads that you keep the Remedy",
    KEPT in seen, str(seen))
chk("T30 with the fail sound", KEPT in failed, f"fail sound under {failed}")
chk("T30 and the Remedy is still in the bag", drive.item_qty(g, REMEDY) == 1,
    f"qty={drive.item_qty(g, REMEDY)}")
g.close()

# --- The plain case ------------------------------------------------------------
g, ok = engage("t30_plain", {"POTION": 2})
chk("T30 reaches the third bugbear fight", ok, f"gs={g.gs()}")
chk("T30 the menu takes the potion", drive.use_battle_item(g, POTION))
seen = play_round(g)
chk("T30 drunk on its turn, it heals", any(t.endswith("HP healed!") for t in seen), str(seen))
chk("T30 and leaves the bag", drive.item_qty(g, POTION) == 1, f"qty={drive.item_qty(g, POTION)}")
g.close()

# --- A Remedy that cures -------------------------------------------------------
g, ok = engage("t30_cure", {"REMEDY": 1})
chk("T30 reaches the fourth bugbear fight", ok, f"gs={g.gs()}")
free = next(k for k in range(EFFECT_COUNT) if not g.rd8(EFFECTS + k * EFFECT_SIZE))
for off, v in enumerate((1, BLIND, 1 << BLIND, 3, 0)):   # active, id, flag, duration, tier
    g.wr8(EFFECTS + free * EFFECT_SIZE + off, v)
mark = len(sounds_heard(g))
chk("T30 the menu takes a Remedy against a blind that lasts", drive.use_battle_item(g, REMEDY))
seen = play_round(g)
healed = heard(g, "sfx_heal", mark)
chk("T30 the Remedy cures it", CURED in seen, str(seen))
chk("T30 and plays the healing sound the potions play", CURED in healed, f"heal sound under {healed}")
g.close()

chk.summary()
