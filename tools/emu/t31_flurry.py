"""T31 - Flurry of Blows lands four blows past level 56, and its damage fits.
Open Palm steps up a damage tier at level 30.

monk_flurry() multiplies one blow's base damage by the blow count: two, three
past level 50, four past level 56. Each trial fights floor 2's bugbear from one
savestate and one battle seed, so both casts roll the same d16, once at level 57
and once at level 56. AGL is raised until both clamp to attack level 99, which
gives both the same blow, player_dmg[S_TIER][98] = 1150 (src/tables.c), so the
two damage lines come out 4:3.

Four blows at that base is 4600, and calc_damage() multiplies it by a roll
modifier of up to 20 (damage_roll_modifier, data/bank05.c) before dividing by
16. The product needs 17 bits, so each line is checked against the exact values
the modifiers allow, not a range a wrapped result could still land in.

Open Palm has the same B, A, S ladder as Flurry, stepping at 30 and 53. The
same trick checks the first step: AGL 70 clamps levels 29 and 30 both to
attack level 99, so the only difference between the two casts is the tier,
player_dmg[B_TIER][98] = 732 against player_dmg[A_TIER][98] = 941.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "playtest"))
from lotd import *
from helpers import *
from starts import start_on

chk = Checker("t31_flurry")
MONK, OPEN_PALM, FLURRY = 2, 1, 3    # monk1 and monk3, src/player.data.c
PRE, POST = SYM["battle_pre_message"], SYM["battle_post_message"]
SEED = SYM["__rand_seed"]
MON0 = SYM["encounter"] + 1
M_MAX_HP, M_HP, M_TARGET_HP, M_PARAMETER = 12, 14, 16, 58
M_IMMUNE, M_RESIST, M_VULN = 30, 31, 32
BLOW = 1150                          # player_dmg[S_TIER][98], src/tables.c
MODIFIERS = (12, 13, 13, 14, 14, 15, 15, 16, 16, 17, 17, 18, 18, 19, 19, 20)
HIGH_AGL = 50                        # 56 + 50 and 57 + 50 both clamp to 99
PALM_AGL = 70                        # 29 + 70 and 30 + 70 both clamp to 99
PALM_B, PALM_A = 732, 941            # player_dmg[B_TIER][98], player_dmg[A_TIER][98]
SEEDS = [0x1D3B + 0x2F11 * k & 0xFFFF for k in range(8)]


def lines(blows):
    """Every damage line `blows` blows can print, mapped to its modifier."""
    return {BLOW * blows * m // 16: m for m in MODIFIERS}

def set_up(g, level, agl=HIGH_AGL):
    """The level under test at attack level 99, full bars, and a bugbear that
    can't die, resist, or roar the monk into shivering instead of attacking."""
    g.wr8(PL + POFF["level"], level)
    g.wr8(PL + POFF["agl_base"], agl)
    g.wr8(PL + POFF["agl"], agl)
    for off in ("hp", "max_hp", "sp", "max_sp"):
        g.wr16(PL + POFF[off], 200)
    for off in (M_MAX_HP, M_HP, M_TARGET_HP):
        g.wr16(MON0 + off, 60000)
    for off in (M_IMMUNE, M_RESIST, M_VULN, M_PARAMETER):
        g.wr8(MON0 + off, 0)


def ability_damage(g, row, words):
    """Cast the ability at `row` and read its damage, or None when it misses.
    `words` are tokens of the ability's own lines, so a monster's line can't
    be read in its place."""
    g.wr8(PRE, 0)
    g.wr8(POST, 0)
    if not cast(g, row):
        return None
    done = lambda: any(w in cstr(g, PRE) for w in words) and any(
        w in cstr(g, POST) for w in ("damage", "miss"))
    if not g.wait_for(done, 600):
        return None
    for tok in cstr(g, POST).replace("!", " ").split():
        if tok.isdigit():
            return int(tok)
    return None


g, _ = start_on(2, class_id=MONK, level=57, abilities=0x3F, tag="t31_flurry")
# NPC_1, the bugbear elite, stands at (3,5) (src/floor2.c).
g.teleport(3, 6, "UP"); g.tick(4)
g.interact()
chk("T31 the monk reaches the bugbear fight", g.wait_for(lambda: at_menu(g), 1800),
    f"gs={g.gs()}")
save_checkpoint(g, "t31_menu.state")

three, four = lines(3), lines(4)
trials = []
for seed in SEEDS:
    load_checkpoint(g, "t31_menu.state")
    g.wr16(SEED, seed)
    set_up(g, 57)
    save_checkpoint(g, "t31_trial.state")
    at_57 = ability_damage(g, FLURRY, ("flurry",))
    load_checkpoint(g, "t31_trial.state")
    set_up(g, 56)
    at_56 = ability_damage(g, FLURRY, ("flurry",))
    trials.append((seed, at_57, at_56))

palm_b = {PALM_B * m // 16: m for m in MODIFIERS}
palm_a = {PALM_A * m // 16: m for m in MODIFIERS}
palms = []
for seed in SEEDS:
    load_checkpoint(g, "t31_menu.state")
    g.wr16(SEED, seed)
    set_up(g, 30, PALM_AGL)
    save_checkpoint(g, "t31_palm.state")
    at_30 = ability_damage(g, OPEN_PALM, ("palm", "trip"))
    load_checkpoint(g, "t31_palm.state")
    set_up(g, 29, PALM_AGL)
    at_29 = ability_damage(g, OPEN_PALM, ("palm", "trip"))
    palms.append((seed, at_30, at_29))
g.close()

print("(seed, level 57 damage, level 56 damage):", trials)
landed = [(s, a, b) for s, a, b in trials if a is not None and b is not None]
chk("T31 most trials land both casts", len(landed) >= 6, f"{len(landed)}/{len(trials)}")
chk("T31 at level 56 every line is three blows: 3 x 1150 x modifier / 16",
    landed and all(b in three for _, _, b in landed), str(landed))
chk("T31 at level 57 every line is four blows: 4 x 1150 x modifier / 16",
    landed and all(a in four for _, a, _ in landed), str(landed))
chk("T31 each pair rolled the same modifier, so the lines are 4:3",
    landed and all(a in four and four[a] == three.get(b) for _, a, b in landed), str(landed))
chk("T31 the seeds include rolls whose four-blow product overflows 16 bits",
    any(BLOW * 4 * three.get(b, 0) > 0xFFFF for _, _, b in landed), str(landed))

print("(seed, Open Palm at 30, Open Palm at 29):", palms)
palm_landed = [(s, a, b) for s, a, b in palms if a is not None and b is not None]
chk("T31 most Open Palm trials land both casts", len(palm_landed) >= 6, f"{len(palm_landed)}/{len(palms)}")
chk("T31 Open Palm at level 29 is a B tier blow: 732 x modifier / 16",
    palm_landed and all(b in palm_b for _, _, b in palm_landed), str(palm_landed))
chk("T31 Open Palm at level 30 is an A tier blow: 941 x modifier / 16, same modifier",
    palm_landed and all(a in palm_a and palm_a[a] == palm_b.get(b) for _, a, b in palm_landed), str(palm_landed))
chk.summary()
