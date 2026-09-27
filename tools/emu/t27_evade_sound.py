"""T27 - the evade sound stays the evade sound.

damage_player() plays sfx_evade and writes "But you evade!" on a dodge, and
picks the hit or crit sound itself on a landed blow. A monster's attack in
src/monsters.bank6.c or src/monsters.bank7.c that sets its own line or sound
does it only behind `if (damage > 0)`, as the themed attacks do, so a dodge
keeps the evade line and sound. The dragon's tail whip swaps in a flourish on
a landed hit, and its fire breath the title screen's fire (t36).

Two representative sites, one from each file: the kobold's axe/loogie attack
(src/monsters.bank6.c) and the dragon's tail whip legendary action
(src/monsters.bank7.c). Both read battle_sfx directly rather than trust a
sound byte a screenshot can't show.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "playtest"))
from lotd import *
from helpers import *
from starts import start_on
import drive

chk = Checker("t27_evade_sound")
SPECIAL_EVASION = 1 << 2
SFX_EVADE = SYM["sfx_evade"]
SFX_MELEE = SYM["sfx_monster_attack1"]
SFX_MAGIC = SYM["sfx_monster_attack2"]
SFX_CRIT = SYM["sfx_monster_critical"]
SFX_SPECIAL_CRIT = SYM["sfx_big_door_open"]
def cast_evasion(g):
    """Ability row 0 is every class's innate ability; for the monk that's
    Evasion, TARGET_SELF and SKIP_POST_MSG. The cast animation runs well past
    a couple hundred frames, so this waits it out fully (and doesn't poke any
    other memory while it's mid-animation) before handing back control."""
    g.battle_menu_goto(1); g.press("a", wait=14); g.press("a", wait=20)
    g.wait_for(lambda: at_menu(g), 900)

# --- Part A: the kobold's attack (bank6.c) -----------------------------------
log("\n=== kobold: dodges must keep the evade sound ===")
g, _ = start_on(1, class_id=2, level=10, tag="t27_kobold")   # 2 = monk
chk("T27 the monk knows Evasion (ability row 0)",
    g.rd8(SYM["player_num_abilities"]) >= 1
    and g.rd16(SYM["player_abilities"]) == SYM["monk0"] & 0xFFFF,
    f"num={g.rd8(SYM['player_num_abilities'])}")
keep_alive(g)

KOBOLD_ATTACKS = ("raises a tiny axe", "spits a glob of fire")
evades, hits = [], []
for step in range(600):
    if g.gs() == GS["BATTLE"]:
        keep_alive(g)
        if at_menu(g):
            cast_evasion(g)
        for rnd in range(30):
            if not g.wait_for(lambda: at_menu(g), 1800):
                break
            keep_alive(g)
            g.battle_menu_goto(0); g.press("a", wait=12); g.press("a", wait=12)
            for pre, post, sfx in round_messages(g):
                # Only the kobold's attack lines count. A turn that shows no
                # post message, such as a kobold getting up, leaves the last
                # one in the buffer, which would read as a hit.
                if not any(a in pre for a in KOBOLD_ATTACKS):
                    continue
                if post.startswith("But you evade"):
                    evades.append((pre, post, sfx))
                elif "damage" in post:
                    hits.append((pre, post, sfx))
            if len(evades) >= 3 or g.gs() != GS["BATTLE"]:
                break
        if g.gs() == GS["BATTLE"]:
            for _ in range(200):
                if g.gs() != GS["BATTLE"]:
                    break
                g.press("a", hold=2, wait=8)
            g.wait_map_idle(400)
        if len(evades) >= 3:
            break
        continue
    g.step(["UP", "DOWN", "LEFT", "RIGHT"][step % 4])
    g.wait_map_idle(120)

print("kobold evades:", evades)
print("kobold hits:", hits[:4])
chk("T27 the kobold's attack was dodged at least once", bool(evades), f"{len(evades)} dodges")
chk("T27 every dodge keeps the evade sound",
    evades and all(sfx == SFX_EVADE for _, _, sfx in evades), str(evades))
chk("T27 a landed hit still plays its own sound",
    hits and all(sfx in (SFX_MELEE, SFX_MAGIC, SFX_CRIT) for _, _, sfx in hits), str(hits[:4]))
g.close()


# --- Part B: the dragon's tail whip (bank7.c), with its landed-hit flourish ---
log("\n=== dragon tail whip: a dodge gets no extra flourish sound ===")
import io
import dragon as D

SEED = SYM["__rand_seed"]


# Level 20 keeps Evasion's dodge chance at its base 50% (player.level <= 30,
# monster.core.c): high enough to see it fire, low enough that a landed hit
# still turns up in a handful of trials.
g = D.built(2, 20, {"POTION": 20, "ETHER": 20, "ELIXIR": 20}, "t27_dragon")
D.engage(g, "t27 dragon")
keep_alive(g)
g.wait_for(lambda: at_menu(g), 600)      # engage() only waits for gs()==BATTLE
# A dragon that moves first can frighten the monk out of its turn, and a cast
# retried on later turns lets the dragon spend its tail whips first. So cast
# on the first turn, from a pinned seed, trying the next until Evasion is up.
first_menu = io.BytesIO(); g.pb.save_state(first_menu)
for seed in [0x0B1D + 0x3F17 * k & 0xFFFF for k in range(10)]:
    first_menu.seek(0); g.pb.load_state(first_menu)
    g.wr16(SEED, seed)
    cast_evasion(g)
    if g.rd8(PL + POFF["special_flags"]) & SPECIAL_EVASION:
        break
chk("T27 the monk cast Evasion before facing the dragon",
    g.rd8(PL + POFF["special_flags"]) & SPECIAL_EVASION,
    f"special_flags={g.rd8(PL + POFF['special_flags']):#04x}")
keep_alive(g); D.keep_up(g)

# The dragon spends its legendary charges (3 for the S tier this level reaches)
# on tail whip and wing flap alike, so tail whip itself comes up only a
# handful of times a fight, too scarce at a 50% dodge chance to count on both
# a dodge and a landed hit in one fight. Retry from right after Evasion is
# cast, each time from a different battle seed, until both have been seen.
start = io.BytesIO(); g.pb.save_state(start)
SEEDS = [0x1D2B + 0x2F59 * k & 0xFFFF for k in range(40)]

tail_dodges, tail_hits = [], []
for trial, seed in enumerate(SEEDS):
    if tail_dodges and tail_hits:
        break
    start.seek(0); g.pb.load_state(start)
    g.wr16(SEED, seed)
    for rnd in range(60):
        keep_alive(g); D.keep_up(g)
        if not g.wait_for(lambda: at_menu(g), 1800):
            break
        keep_alive(g); D.keep_up(g)
        g.battle_menu_goto(0); g.press("a", wait=12); g.press("a", wait=12)   # basic attack
        for pre, post, sfx in round_messages(g):
            if "sweeps" not in pre and "tail" not in pre:
                continue
            if post.startswith("But you evade"):
                tail_dodges.append((pre, post, sfx))
            elif "damage" in post or "CRITICAL" in post:
                tail_hits.append((pre, post, sfx))
        if tail_dodges and tail_hits:
            break

print(f"tail whip over {trial + 1} seeds")
print("tail whip dodges:", tail_dodges)
print("tail whip hits:", tail_hits[:4])
chk("T27 the dragon's tail whip was dodged at least once", bool(tail_dodges), f"{len(tail_dodges)} dodges")
chk("T27 a dodged tail whip keeps the evade sound, no flourish",
    tail_dodges and all(sfx == SFX_EVADE for _, _, sfx in tail_dodges), str(tail_dodges))
chk("T27 the dragon's tail whip landed at least once", bool(tail_hits), f"{len(tail_hits)} hits")
chk("T27 a landed tail whip gets its flourish sound",
    tail_hits and all(sfx == SFX_SPECIAL_CRIT for _, _, sfx in tail_hits), str(tail_hits[:4]))
g.close()

chk.summary()
