"""T24 - a blow the monk's Evasion dodges reads as a dodge, and is one.

damage_player() handles Evasion itself: a dodge writes "But you evade!", plays
the evade sound and returns zero. A monster that writes its own hit line over
that with the zero reads "They hit twice for 0 damage!", so the displacer
beast, the deathknight, the dragon, and the will-o'-wisp keep the dodge's
line.

A dodge also blocks an attack's effect on top of the damage: Mind Blast's
confusion, and the topple or poison of a pounce, wing flap, or eyestalk ray.
The second half checks Mind Blast, the one whose effect sets up an outright
kill (Extract Brain).

A level-4 monk on floor 8 steps onto the displacer beast's mini-boss tile,
casts Evasion, then attacks, which barely scratches a level-47 monster, so the
fight runs long enough for several of the beast's attacks to be dodged. Its HP
is raised so the beast cannot end the test first. Every round's messages are
read in order, since one sample catches whichever side happened to act last.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "playtest"))
from lotd import *
from helpers import *

chk = Checker("t24_evade_text")
BS = SYM["battle_state"]
SPECIAL_EVASION = 1 << 2          # player.h SpecialFlags


def hp():
    return g.rd16(PL + POFF["hp"])


tmpl, pos, d = make_floor_template(8, hero=2, has_torch=True, tag="t24tmpl")   # 2 = monk
g = Game(tag="t24", sram=tmpl + bytes(SLOT_STRIDE - SAVE_SIZE))
chk("T24 boot to save select", g.boot_to_save_select()); g.tick(10)
g.save_select_pick(0)
chk("T24 load floor 8 save -> map idle", g.wait_map_idle(900), f"gs={g.gs()} ms={g.ms()}"); g.tick(20)
chk("T24 the monk knows Evasion (ability row 0, player.data.c monk0)",
    g.rd8(SYM["player_num_abilities"]) >= 1
    and g.rd16(SYM["player_abilities"]) == SYM["monk0"] & 0xFFFF,
    f"num={g.rd8(SYM['player_num_abilities'])} first={g.rd16(SYM['player_abilities']):#06x}")
keep_alive(g)

# The displacer beast's tile, (13,22), stepped onto from (12,22).
g.teleport(12, 22, "RIGHT"); g.tick(4)
g.step("RIGHT")
read_textbox(g)                      # the beast's line; its fight starts as the line closes
chk("T24 stepping onto (13,22) starts the displacer beast fight",
    g.wait_for(lambda: at_menu(g), 1800), f"gs={g.gs()} bs={g.rd8(BS)}")

# Evasion is TARGET_SELF and skips its post message, so ability, row 0, A.
keep_alive(g)
g.battle_menu_goto(1); g.press("a", wait=14); g.press("a", wait=20)
first = round_messages(g)
chk("T24 Evasion cast: the special flag is set for the fight",
    g.rd8(PL + POFF["special_flags"]) & SPECIAL_EVASION,
    f"special_flags={g.rd8(PL + POFF['special_flags']):#04x} {first}")

evades, hits, zero_lines = [], [], []
for rnd in range(40):
    if not g.wait_for(lambda: at_menu(g), 1800) or len(evades) >= 3:
        break
    keep_alive(g)
    g.battle_menu_goto(0); g.press("a", wait=12); g.press("a", wait=12)   # FIGHT
    before = hp()
    msgs = round_messages(g, lambda g: hp())   # the HP as each line appeared
    for pre, post, hp_then in msgs:
        if not pre.startswith("Displacer Beast"):
            continue
        if "for 0 damage" in post:
            zero_lines.append(post)
        if post.startswith("But you evade"):
            evades.append((rnd, post, before, hp_then))
        elif "damage" in post:
            hits.append(post)

print("evades:", evades)
print("hits:", hits[:6])
chk("T24 the beast's attacks were dodged at least twice", len(evades) >= 2, f"{len(evades)} dodges, {len(hits)} hits")
chk("T24 a dodge costs no HP", all(b == then for _, _, b, then in evades), str(evades))
chk("T24 no line ever reports a hit for 0 damage", not zero_lines, str(zero_lines[:3]))
chk("T24 every landed hit reports its damage", all(" 0 damage" not in h for h in hits) and bool(hits),
    str(hits[:3]))
g.close()

# --- A dodged Mind Blast confuses nobody --------------------------------------
# The mind flayer blasts on a 3-in-8 roll until one lands, so whether a dodge
# comes before the first landing depends on the fight's rolls. Each trial
# replays the approach with a different seed (map.c reseeds on the first step
# while init_random is set) until one has shown a dodged blast.
CONFUSED_ID = 4                                  # StatusEffect DEBUFF_CONFUSED
EFFECTS, EFFECT_SIZE, EFFECT_COUNT = SYM["encounter"] + 209, 5, 4   # as t22


def live_confused():
    return any(g.rd8(EFFECTS + k * EFFECT_SIZE) and g.rd8(EFFECTS + k * EFFECT_SIZE + 1) == CONFUSED_ID
               for k in range(EFFECT_COUNT))


import io
g = Game(tag="t24b", sram=tmpl + bytes(SLOT_STRIDE - SAVE_SIZE))
g.boot_to_save_select(); g.tick(10); g.save_select_pick(0); g.wait_map_idle(900); g.tick(20)
keep_alive(g)
g.teleport(11, 17, "RIGHT"); g.tick(4)                  # beside the mind flayer's tile
start = io.BytesIO(); g.pb.save_state(start)

dodged, landed = [], []
for trial in range(1, 11):
    start.seek(0); g.pb.load_state(start)
    g.wr8(SYM["init_random"], 1); g.tick(37 * trial + 11)
    g.step("RIGHT")
    read_textbox(g)                  # the flayer's line
    if not g.wait_for(lambda: at_menu(g), 1800):
        break
    keep_alive(g)
    g.battle_menu_goto(1); g.press("a", wait=14); g.press("a", wait=20)   # Evasion
    round_messages(g)
    for rnd in range(25):
        if not g.wait_for(lambda: at_menu(g), 1800):
            break
        keep_alive(g)
        g.battle_menu_goto(0); g.press("a", wait=12); g.press("a", wait=12)
        msgs = round_messages(g)
        blasts = [(pre, post) for pre, post, _ in msgs if "psychic energy" in pre]
        if not blasts:
            continue
        post = blasts[-1][1]
        if post.startswith("But you evade"):
            dodged.append((trial, rnd, post, live_confused()))
        elif "confused" in post:
            landed.append((trial, rnd, post, live_confused()))
            break                                         # Extract Brain comes next
    if dodged:
        break

print("dodged blasts:", dodged)
print("landed blasts:", landed)
chk("T24 a Mind Blast was dodged in one of the trials", bool(dodged), f"landed={landed}")
chk("T24 a dodged Mind Blast leaves no confusion", dodged and not any(c for *_, c in dodged), str(dodged))
chk("T24 no dodged blast reads as damage", all("damage" not in p for _, _, p, _ in dodged), str(dodged))
g.close(); chk.summary()
