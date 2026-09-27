"""T22 - debuff immunity, on both sides of the fight.

apply_status_effect() enforces immunity as `immune & flag`, where flag is a
DebuffFlag bit rather than a StatusEffect index, so a monster's debuff_immune
has to be built from DebuffFlag bits to block what its source line names. A
monster immune to dark damage carries that in aspect_immune, since
DAMAGE_DARK in debuff_immune is an unrelated debuff bit.

Checks the monster masks by reading the live bytes rather than by trying to
land each debuff: several of the intended immunities (poison, dark) have no
player-side source, so a behavioral test could not tell "immune" from
"nothing tried it".

A blocked debuff reads as blocked: apply_status_effect()'s
STATUS_RESULT_IMMUNE picks the post-message in fighter_menace(),
sorcerer_darkness(), and the bugbear's roar, so none of them prints its "it
landed" text against an immune target.

Mind Blast's own immunity check (src/monsters.bank7.c) tests the player's
mask against FLAG_DEBUFF_CONFUSED (16), not the StatusEffect value
DEBUFF_CONFUSED (4), which as a mask is FLAG_DEBUFF_PARALYZED. Nothing in the
game grants the player that immunity, so the suite pokes the mask.

And the end of a fight clears what it gave the player: Still Mind's
immunity, Diamond Body's resistances, the prone counter, and the special
flags, read on the map, since the save stores the player whole.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "playtest"))
from lotd import *
from helpers import cstr, read_textbox
from starts import start_on

chk = Checker("t22_debuff_immunity")
ENC, PL = SYM["encounter"], SYM["player"]
MON0, MON_SZ = ENC + 1, 64
M_ACTIVE, M_TYPE, M_DEBUFF_IMMUNE, M_ASPECT_IMMUNE = 5, 0, 33, 30
P_DEBUFF_IMMUNE = POFF["debuff_immune"]

# DebuffFlag, from src/stats.h.
BLIND, SCARED, PARALYZED, POISONED, CONFUSED = 1, 2, 4, 8, 16
DAMAGE_DARK = 1 << 7
BUGBEAR, GCUBE, WISP, DKNIGHT = 3, 5, 7, 8

tmpl, pos, d = make_floor_template(3, hero=2, has_torch=False, tag="t22tmpl")
g = Game(tag="t22", sram=tmpl + bytes(SLOT_STRIDE - SAVE_SIZE))
assert g.boot_to_save_select(), "no save select"
g.tick(10)
g.save_select_pick(0)
chk("T22 load floor 3 save -> map idle", g.wait_map_idle(900), f"gs={g.gs()} ms={g.ms()}")
g.tick(20)

# Survive long enough to sample whatever wanders in.
for off, v in ((POFF["hp"], 9999), (POFF["max_hp"], 9999)):
    g.wr8(PL + off, v & 0xFF); g.wr8(PL + off + 1, v >> 8)

seen = {}
for step in range(500):
    if g.gs() == GS["BATTLE"]:
        for s in range(3):
            base = MON0 + s * MON_SZ
            if g.rd8(base + M_ACTIVE):
                seen.setdefault(g.rd8(base + M_TYPE),
                                (g.rd8(base + M_DEBUFF_IMMUNE),
                                 g.rd8(base + M_ASPECT_IMMUNE)))
        for _ in range(400):
            if g.gs() != GS["BATTLE"]:
                break
            g.press("a", hold=2, wait=6)
        g.wait_map_idle(400)
        continue
    if BUGBEAR in seen:
        break
    g.step(["UP", "DOWN", "LEFT", "RIGHT"][step % 4])
    g.wait_map_idle(120)

print("sampled monster immunity bytes:",
      {t: (hex(d), hex(a)) for t, (d, a) in sorted(seen.items())})

chk("T22 met a bugbear to sample", BUGBEAR in seen, str(sorted(seen)))
if BUGBEAR in seen:
    mask = seen[BUGBEAR][0]
    chk("T22 bugbear is immune to exactly blind, confused and poison",
        mask == (BLIND | CONFUSED | POISONED), f"{mask:#010b}")
    chk("T22 bugbear is not immune to scared or paralyzed",
        not (mask & (SCARED | PARALYZED)), f"{mask:#010b}")

# --- monsters immune to dark damage carry it as an aspect, not a debuff
#
# Floor 6's elite is a will-o-wisp at (23,4) (src/floor6.c), met face to face;
# floor 8's death knight starts its fight from its tile, (4,17) (src/floor8.c).
def dark_immune_masks(floor, level, tile, kind, step_on, tag):
    """(debuff_immune, aspect_immune) of the first `kind` monster in the fight
    at `tile`, or None if no such fight starts."""
    gg, _ = start_on(floor, class_id=1, level=level, abilities=0x3F, tag=tag)
    x, y = tile
    gg.teleport(x, y + 1, "UP"); gg.tick(4)
    if step_on:
        gg.step("UP")
    else:
        gg.interact()
    for _ in range(60):
        if gg.gs() == GS["BATTLE"] and gg.rd8(SYM["battle_state"]) == 2:
            break
        if gg.ms() in (MS["TEXTBOX"], MS["TEXTBOX_OPEN"]):
            gg.press("a", wait=20)
        gg.tick(30)
    masks = None
    for s in range(3):
        base = MON0 + s * MON_SZ
        if gg.gs() == GS["BATTLE"] and gg.rd8(base + M_ACTIVE) and gg.rd8(base + M_TYPE) == kind:
            masks = (gg.rd8(base + M_DEBUFF_IMMUNE), gg.rd8(base + M_ASPECT_IMMUNE))
            break
    gg.close()
    return masks


for label, floor, level, tile, kind, step_on in (
        ("will-o-wisp", 6, 45, (23, 4), WISP, False),
        ("death knight", 8, 81, (4, 17), DKNIGHT, True)):
    masks = dark_immune_masks(floor, level, tile, kind, step_on, f"t22_{kind}")
    chk(f"T22 reached a {label} fight", masks is not None, str(masks))
    if masks is not None:
        chk(f"T22 the {label} is immune to dark damage and to no debuff",
            masks == (0, DAMAGE_DARK), f"debuff_immune={masks[0]:#04x} aspect_immune={masks[1]:#04x}")

# --- the player half: Still Mind grants immunity to fear, for its fight only
#
# The ability list is rebuilt by player_refresh_abilities(), which save_load()
# calls. Poking ability_flags on a running game leaves the battle menu showing
# whatever was unlocked at boot, so the flags go into the save blob instead.
g.close()
monk = bytearray(tmpl)
monk = bytearray(set_field(monk, OFF["player"] + POFF["ability_flags"], 0x3F))
monk = bytearray(fix_checksum(monk))
g2 = Game(tag="t22b", sram=bytes(monk) + bytes(SLOT_STRIDE - SAVE_SIZE))
assert g2.boot_to_save_select()
g2.tick(10)
g2.save_select_pick(0)
assert g2.wait_map_idle(900)
g2.tick(20)
chk("T22 the monk starts with no debuff immunity",
    g2.rd8(PL + P_DEBUFF_IMMUNE) == 0, hex(g2.rd8(PL + P_DEBUFF_IMMUNE)))

# All six are unlocked, so Still Mind's menu row equals its ability index, 2.
g2.wr8(PL + POFF["level"], 60)
for off, v in ((POFF["sp"], 200), (POFF["max_sp"], 200),
               (POFF["hp"], 9999), (POFF["max_hp"], 9999)):
    g2.wr8(PL + off, v & 0xFF); g2.wr8(PL + off + 1, v >> 8)

for step in range(500):
    if g2.gs() == GS["BATTLE"]:
        break
    g2.step(["UP", "DOWN", "LEFT", "RIGHT"][step % 4])
    g2.wait_map_idle(120)
chk("T22 reached a battle to cast Still Mind in", g2.gs() == GS["BATTLE"],
    f"gs={g2.gs()}")

BS, BM = SYM["battle_state"], SYM["battle_menu"]


def cast_row(gg, row, label):
    """Open the ability menu, drive the cursor to `row`, confirm the cast.

    Presses exactly what the menu asks for (no trailing guess) so a
    SKIP_POST_MSG ability doesn't leave a spare press to desync the next
    turn's menu, the trap drive.cast_ability() documents.
    """
    gg.wait_for(lambda: gg.rd8(BS) == 2, 900)
    gg.battle_menu_goto(1)
    gg.press("a", wait=14)
    for _ in range(8):
        cur = gg.rd8(BM + 4)
        if cur == row:
            break
        gg.press("down" if cur < row else "up", wait=10)
    reached = gg.rd8(BM + 4) == row
    chk(f"T22 cursor reached {label}", reached, str(gg.rd8(BM + 4)))
    gg.press("a", wait=20)
    if gg.rd8(BM) == 3:            # single-target: confirm the monster
        gg.press("a", wait=20)
    gg.wait_for(lambda: gg.gs() != GS["BATTLE"] or gg.rd8(BS) == 2, 900)
    return reached


cast_row(g2, 2, "Still Mind")

after = g2.rd8(PL + P_DEBUFF_IMMUNE)
chk("T22 Still Mind grants lasting immunity to scared", after & SCARED,
    f"{after:#010b}")
chk("T22 and grants nothing else", after == SCARED, f"{after:#010b}")

# Leaving the fight has to give back what it gave the player: the save stores
# the player whole, so it must be gone on the map, and it must not ride into
# every later battle. Still Mind set the immunity. Nothing in this fight sets Diamond Body's resistances, the prone
# counter or the special flags, so they are set by hand once the monster is
# down, on the rewards screen (BattleState 14, 16, 17), before the fight ends.
AFTER_VICTORY = (14, 16, 17)
REST = ("aspect_resist", "trip_turns", "special_flags")
set_rest = False
for _ in range(400):
    if g2.gs() != GS["BATTLE"]:
        break
    if not set_rest and g2.rd8(BS) in AFTER_VICTORY:
        for field, value in zip(REST, (0x03, 2, 0x05)):   # physical|magical, prone, barkskin|evasion
            g2.wr8(PL + POFF[field], value)
        set_rest = True
    g2.press("a", hold=2, wait=6)
g2.wait_map_idle(600)
chk("T22 the immunity is gone once the fight is over",
    g2.gs() == GS["WORLD_MAP"] and g2.rd8(PL + P_DEBUFF_IMMUNE) == 0,
    f"gs={g2.gs()} immune={g2.rd8(PL + P_DEBUFF_IMMUNE):#04x}")
chk("T22 and so is the rest of what the fight gave the player",
    set_rest and all(g2.rd8(PL + POFF[f]) == 0 for f in REST),
    f"set={set_rest} " + " ".join(f"{f}={g2.rd8(PL + POFF[f]):#04x}" for f in REST))
for step in range(500):
    if g2.gs() == GS["BATTLE"]:
        break
    g2.step(["UP", "DOWN", "LEFT", "RIGHT"][step % 4])
    g2.wait_map_idle(120)
chk("T22 reached a second battle", g2.gs() == GS["BATTLE"], f"gs={g2.gs()}")
g2.wait_for(lambda: g2.rd8(BS) == 2, 900)
chk("T22 the immunity does not ride into the next fight",
    g2.rd8(PL + P_DEBUFF_IMMUNE) == 0, hex(g2.rd8(PL + P_DEBUFF_IMMUNE)))

# --- a monster that scares the player has to honor the mask too
#
# The bugbear's "For Hruggek!" has to pass player.debuff_immune like its
# eleven siblings, or it scares straight through Still Mind. It fires on
# d8() < 2 and only while it has a charge, and its generator grants exactly
# one, which a level-60 monk out-damages long before the roll comes around.
# So this keeps the bugbear standing and its charges topped up, and waits for
# the shout rather than casting and hoping.
PRE = SYM["battle_pre_message"]
POST = SYM["battle_post_message"]
M_HP, M_TARGET_HP, M_PARAMETER = 14, 16, 58
# Encounter.player_status_effects, from the .cdb: four 5-byte instances laid
# out { active, effect, flag, duration, tier }. Read here rather than
# player.debuffs, which is only rebuilt at round completion -- sampling that
# mirror right after the shout reports the previous round and makes this check
# pass against the very defect it exists to catch.
P_EFFECTS = ENC + 209
EFFECT_SIZE, EFFECT_COUNT = 5, 4
DEBUFF_SCARED_ID, DEBUFF_CONFUSED_ID = 1, 4          # StatusEffect, src/stats.h


def player_has_effect(gg, effect_id):
    for k in range(EFFECT_COUNT):
        base = P_EFFECTS + k * EFFECT_SIZE
        if gg.rd8(base) and gg.rd8(base + 1) == effect_id:
            return True
    return False


def player_is_scared(gg):
    return player_has_effect(gg, DEBUFF_SCARED_ID)


def in_bugbear_fight(gg):
    for s in range(3):
        base = MON0 + s * MON_SZ
        if gg.rd8(base + M_ACTIVE) and gg.rd8(base + M_TYPE) == BUGBEAR:
            return base
    return None


bug = in_bugbear_fight(g2)
for step in range(500):
    if bug is not None:
        break
    if g2.gs() == GS["BATTLE"]:
        for _ in range(400):
            if g2.gs() != GS["BATTLE"]:
                break
            g2.press("a", hold=2, wait=6)
        g2.wait_map_idle(400)
    g2.step(["UP", "DOWN", "LEFT", "RIGHT"][step % 4])
    g2.wait_map_idle(120)
    if g2.gs() == GS["BATTLE"]:
        g2.wait_for(lambda: g2.rd8(BS) == 2 or g2.gs() != GS["BATTLE"], 900)
        bug = in_bugbear_fight(g2)

chk("T22 found a bugbear to be scared by", bug is not None, str(bug))

shouts = landed = wrong_text = 0
if bug is not None:
    for turn in range(60):
        if g2.gs() != GS["BATTLE"]:
            break
        g2.wait_for(lambda: g2.rd8(BS) == 2 or g2.gs() != GS["BATTLE"], 900)
        if g2.gs() != GS["BATTLE"]:
            break
        for _ in range(6):
            if g2.rd8(BM) == 0:
                break
            g2.press("b", wait=14)
        for off, v in ((POFF["hp"], 9999), (POFF["max_hp"], 9999)):
            g2.wr8(PL + off, v & 0xFF); g2.wr8(PL + off + 1, v >> 8)
        g2.wr8(PL + P_DEBUFF_IMMUNE, SCARED)
        # Keep it alive and shouting.
        g2.wr8(bug + M_HP, 0xFF); g2.wr8(bug + M_HP + 1, 0x01)
        g2.wr8(bug + M_TARGET_HP, 0xFF); g2.wr8(bug + M_TARGET_HP + 1, 0x01)
        g2.wr8(bug + M_PARAMETER, 9)
        g2.battle_menu_goto(0); g2.press("a", wait=12); g2.press("a", wait=12)
        g2.wait_for(lambda: g2.gs() != GS["BATTLE"] or g2.rd8(BS) != 2, 120)
        g2.tick(40)
        if "hruggek" in cstr(g2, PRE).lower():
            shouts += 1
            landed += player_is_scared(g2)
            # Immune every time (debuff_immune is forced above each turn), so
            # the post message must be the miss line, never the hit line.
            wrong_text += "unimpressed" not in cstr(g2, POST).lower()
        g2.wait_for(lambda: g2.gs() != GS["BATTLE"] or g2.rd8(BS) == 2, 900)
        if shouts >= 3:
            break

print(f"bugbear scare attempts: {shouts}, landed through immunity: {landed}, "
      f"wrong text: {wrong_text}")
chk("T22 the bugbear actually tried its scare", shouts > 0, str(shouts))
chk("T22 and it did not land through the player's immunity", landed == 0,
    f"{landed} of {shouts} landed")
chk('T22 and the bugbear says "You are unimpressed." rather than claiming '
    "the fear landed", wrong_text == 0,
    f"{wrong_text} of {shouts} shouts showed the wrong text")

g2.close()

# --- the player's side: a debuff blocked outright reads as immune, not as if
# it landed
#
# fighter_menace() and sorcerer_darkness() choose their post-message from what
# apply_scared() and apply_blind() return. Floor 3's boss cube is immune to
# both (POISONED | BLIND | SCARED, gelatinous_cube_generator in
# src/monsters.bank6.c), so casting either at it has to show the immunity line
# rather than the "it worked" one. NPC_1 gates the fight on player.level >=
# 24; poking the level straight to clear that gate is fine here since this
# checks only the cast's own text and the cube's mask, not any level-derived
# combat stat.
NPC1_X, NPC1_Y = 4, 14


def fight_immune_cube(hero, tag):
    tmpl3, _, _ = make_floor_template(3, hero=hero, has_torch=False, tag=f"{tag}tmpl")
    tmpl3 = bytearray(tmpl3)
    tmpl3 = bytearray(set_field(tmpl3, OFF["player"] + POFF["ability_flags"], 0x3F))
    tmpl3 = bytearray(fix_checksum(tmpl3))
    gg = Game(tag=tag, sram=bytes(tmpl3) + bytes(SLOT_STRIDE - SAVE_SIZE))
    assert gg.boot_to_save_select()
    gg.tick(10)
    gg.save_select_pick(0)
    assert gg.wait_map_idle(900)
    gg.tick(20)
    gg.wr8(PL + POFF["level"], 30)
    for off, v in ((POFF["sp"], 200), (POFF["max_sp"], 200),
                   (POFF["hp"], 9999), (POFF["max_hp"], 9999)):
        gg.wr8(PL + off, v & 0xFF); gg.wr8(PL + off + 1, v >> 8)
    gg.teleport(NPC1_X, NPC1_Y + 1, "UP")
    gg.interact()
    gg.wait_for(lambda: gg.gs() == GS["BATTLE"], 900)
    if gg.gs() == GS["BATTLE"]:
        mask = gg.rd8(MON0 + M_DEBUFF_IMMUNE)
        chk(f"T22 {tag}: the boss cube is immune to exactly poison, blind and scared",
            gg.rd8(MON0 + M_TYPE) == GCUBE and mask == (POISONED | BLIND | SCARED),
            f"type={gg.rd8(MON0 + M_TYPE)} mask={mask:#010b}")
    return gg


def cast_and_read_post(gg, row, label):
    """Like cast_row, but returns every distinct battle_post_message text
    seen while the round plays out, not just one sampled at a fixed point.

    Turn order against the boss cube differs between the classes
    fight_immune_cube() builds (it sets sp, hp, and level directly and never
    touches agl, unlike tools/emu/playtest/heroes.py's full stat write, so
    whichever of the fighter's or the sorcerer's level-1 agility loses to
    the cube's varies): sometimes the cube's own "But they miss!" shows
    first and the ability's message follows, sometimes the ability's message
    shows first and the cube's overwrites it. Reading at any single point
    catches the wrong one for one of the two orders, so this collects the
    whole sequence.
    """
    gg.wait_for(lambda: gg.rd8(BS) == 2, 900)
    gg.battle_menu_goto(1)
    gg.press("a", wait=14)
    for _ in range(8):
        cur = gg.rd8(BM + 4)
        if cur == row:
            break
        gg.press("down" if cur < row else "up", wait=10)
    reached = gg.rd8(BM + 4) == row
    chk(f"T22 cursor reached {label}", reached, str(gg.rd8(BM + 4)))
    gg.press("a", wait=20)
    if gg.rd8(BM) == 3:            # single-target: confirm the monster
        gg.press("a", wait=20)
    seen = []
    for _ in range(70):
        gg.tick(6)
        text = cstr(gg, POST)
        if not seen or text != seen[-1]:
            seen.append(text)
        if gg.gs() != GS["BATTLE"]:
            break
    return reached, seen


gf = fight_immune_cube(1, "t22f")  # Fighter
chk("T22 fighter reached the immune cube", gf.gs() == GS["BATTLE"], f"gs={gf.gs()}")
if gf.gs() == GS["BATTLE"]:
    _, seen = cast_and_read_post(gf, 4, "Menace")  # fighter4 in src/player.data.c
    print("Menace vs. an all-immune target, messages seen:", seen)
    chk("T22 Menace against an all-immune target reports immunity, not a scare",
        any("immune" in t.lower() for t in seen), seen)
gf.close()

gs_ = fight_immune_cube(3, "t22s")  # Sorcerer
chk("T22 sorcerer reached the immune cube", gs_.gs() == GS["BATTLE"], f"gs={gs_.gs()}")
if gs_.gs() == GS["BATTLE"]:
    _, seen = cast_and_read_post(gs_, 0, "Darkness")  # sorcerer0 in src/player.data.c
    print("Darkness vs. an all-immune target, messages seen:", seen)
    chk("T22 Darkness against an all-immune target reports immunity, not a blind",
        any("immune" in t.lower() for t in seen), seen)
gs_.close()

# --- Mind Blast honors the player's confuse immunity mask ---------------------
#
# Nothing in the game grants FLAG_DEBUFF_CONFUSED, so this pokes the mask
# directly: the point is the mask is checked correctly, not how a player would
# come by it.
tmpl8, _, _ = make_floor_template(8, hero=2, has_torch=True, tag="t22mbtmpl")   # 2 = monk
gm = Game(tag="t22mb", sram=tmpl8 + bytes(SLOT_STRIDE - SAVE_SIZE))
assert gm.boot_to_save_select(), "no save select"
gm.tick(10)
gm.save_select_pick(0)
chk("T22 load floor 8 save -> map idle", gm.wait_map_idle(900), f"gs={gm.gs()} ms={gm.ms()}")
gm.tick(20)
for off, v in ((POFF["hp"], 9999), (POFF["max_hp"], 9999)):
    gm.wr8(PL + off, v & 0xFF); gm.wr8(PL + off + 1, v >> 8)

# The mind flayer's tile, (12,17), stepped onto from (11,17) (t24).
gm.teleport(11, 17, "RIGHT"); gm.tick(4)
gm.step("RIGHT")
read_textbox(gm)                     # the flayer's line; its fight starts as the line closes
chk("T22 stepping onto the mind flayer's tile starts the fight",
    gm.wait_for(lambda: gm.gs() == GS["BATTLE"], 1800), f"gs={gm.gs()}")
# reset_encounter() zeroes player.debuff_immune when the battle starts, so
# the poke has to land after that, not before.
gm.wr8(PL + P_DEBUFF_IMMUNE, CONFUSED)

blasted = False
for rnd in range(30):
    if gm.gs() != GS["BATTLE"] or blasted:
        break
    if gm.rd8(BS) == 2:
        gm.battle_menu_goto(0); gm.press("a", wait=12); gm.press("a", wait=12)
    seen_pre = None
    for _ in range(400):
        if gm.gs() != GS["BATTLE"] or gm.rd8(BS) == 2:
            break
        pre = cstr(gm, PRE)
        if pre != seen_pre:
            seen_pre = pre
            if "psychic energy" in pre:
                post = cstr(gm, POST)
                print(f"  Mind Blast: {pre!r} / {post!r}")
                chk("T22 Mind Blast reads the player's confuse immunity",
                    "resist" in post.lower(), post)
                # The effect list, not player.debuffs, which only mirrors it
                # once the round completes.
                chk("T22 and the player is never marked confused",
                    not player_has_effect(gm, DEBUFF_CONFUSED_ID), post)
                blasted = True
        gm.press("a", hold=2, wait=8)
chk("T22 the flayer attempted Mind Blast within the trial budget", blasted)
gm.close()

chk.summary()
