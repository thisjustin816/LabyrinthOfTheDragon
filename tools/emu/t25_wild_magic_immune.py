"""T25 - a Wild Magic roll that every target is immune to says so.

Darkness and Menace report "They're completely immune!" when nothing they
tried could land (t22). Wild Magic rolls one of six outcomes per target, two
of them debuffs, so a confuse-and-blind roll against floor 2's bugbear,
immune to both, has to read immune rather than "But it fizzles." A cast whose
only effect was a debuff every target blocked reads immune, and a cast that
landed a debuff writes no line of its own, since the effect shows on the
monster.

A sorcerer with every ability fights the bugbear and casts Wild Magic until a
fully blocked roll and a stat-down roll have both come up. The rolls are read
off the bugbear's own effect list and HP, not the text. HP, SP and the
player's fear (the bugbear scares) are reset each round so the fight lasts.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "playtest"))
from lotd import *
from helpers import *

chk = Checker("t25_wild_magic_immune")
ENC = SYM["encounter"]
MON0 = ENC + 1                                   # Encounter.monsters[0]
M_MAX_HP, M_HP, M_TARGET_HP, M_EFFECTS = 12, 14, 16, 34
P_EFFECTS = ENC + 209                            # encounter.player_status_effects
WILD_MAGIC = 5                                   # sorcerer5, src/player.data.c
STAT_DOWNS = {5, 6, 7}                           # DEBUFF_AGL/ATK/DEF_DOWN


def reset_round():
    for off, v in (("hp", 999), ("max_hp", 999), ("sp", 200), ("max_sp", 200)):
        g.wr16(PL + POFF[off], v)
    for k in range(4):
        g.wr8(P_EFFECTS + 5 * k, 0)              # the bugbear's scare
        g.wr8(MON0 + M_EFFECTS + 5 * k, 0)       # last cast's debuffs
    g.wr8(PL + POFF["debuffs"], 0)
    full = g.rd16(MON0 + M_MAX_HP)
    g.wr16(MON0 + M_HP, full); g.wr16(MON0 + M_TARGET_HP, full)


def monster_effects():
    return {g.rd8(MON0 + M_EFFECTS + 5 * k + 1) for k in range(4) if g.rd8(MON0 + M_EFFECTS + 5 * k)}

def cast_round(row):
    """Cast `row` from the menu and return the round's distinct (pre, post)."""
    g.battle_menu_goto(1); g.press("a", wait=14)
    for _ in range(8):
        cur = g.rd8(SYM["battle_menu"] + 4)
        if cur == row:
            break
        g.press("down" if cur < row else "up", wait=10)
    g.press("a", wait=20)
    g.wait_for(lambda: not at_menu(g), 120)
    return [(pre, post) for pre, post, _ in round_messages(g)]


tmpl, _, _ = make_floor_template(2, hero=3, has_torch=False, tag="t25tmpl")   # 3 = sorcerer
tmpl = bytearray(set_field(bytearray(tmpl), OFF["player"] + POFF["ability_flags"], 0x3F))
g = Game(tag="t25", sram=bytes(fix_checksum(tmpl)) + bytes(SLOT_STRIDE - SAVE_SIZE))
assert g.boot_to_save_select(), "no save select"
g.tick(10)
g.save_select_pick(0)
chk("T25 load floor 2 save -> map idle", g.wait_map_idle(900), f"gs={g.gs()} ms={g.ms()}")
g.tick(20)
g.wr8(PL + POFF["level"], 30)
reset_round()

# NPC_1, the bugbear elite, stands at (3,5) (src/floor2.c); talk to it from below.
g.teleport(3, 6, "UP"); g.tick(4)
g.interact()
chk("T25 the bugbear fight starts", g.wait_for(lambda: at_menu(g), 1800), f"gs={g.gs()}")

blocked, landed = [], []
for n in range(30):
    if not at_menu(g) or (blocked and landed):
        break
    reset_round()
    pairs = cast_round(WILD_MAGIC)
    if not any("storm of magic" in pre for pre, _ in pairs):
        continue                                 # shivered or fled instead
    fx = monster_effects()
    hp = g.rd16(MON0 + M_TARGET_HP)
    posts = [post for pre, post in pairs if "storm of magic" in pre]
    if any("fireball" in p or "sleetstorm" in p for p in posts):
        continue
    if fx & STAT_DOWNS:
        landed.append(posts)
    elif not fx and hp == g.rd16(MON0 + M_MAX_HP):
        blocked.append(posts)

print("fully blocked rolls:", blocked)
print("stat-down rolls:", landed)
chk("T25 a fully blocked roll came up", bool(blocked), f"{len(blocked)}")
chk("T25 a fully blocked roll reads immune",
    blocked and all("They're completely immune!" in p for p in blocked[0]), str(blocked[:1]))
chk("T25 a stat-down roll came up (control)", bool(landed), f"{len(landed)}")
chk("T25 a roll that landed writes no line of its own",
    landed and not any(line in p for p in landed[0] for line in
                       ("But it fizzles.", "They're completely immune!")), str(landed[:1]))
g.close(); chk.summary()
