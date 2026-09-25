"""T36 - the dragon's fire breath roars with the title screen's fire, and no
other fire attack does.

damage_player() picks the sound for a blow it lands: the melee hit for
physical damage and the magic hit for everything else, fire included, with a
critical keeping the critical sound. The dragon's fire breath then swaps in
the title screen's dragon fire (sfx_title_fire) on a landed breath, critical
or not, while its half-damage dodge keeps the miss sound. The kobold's spit,
the death knight's hellfire orb, and the sorcerer's Fireball keep the magic
hit.

Every check reads battle_sfx as the round's text changes, since a screenshot
can't show a sound. The kobolds come from floor 1's encounter tables, and the
dragon and the death knight from floor 8, each fight replayed from a savestate
across battle seeds until the attack in question has come up.
"""
import io
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "playtest"))
from lotd import *
from helpers import *
from starts import start_on
import dragon as D
import drive
from knight import start_fight

chk = Checker("t36_fire_sounds")
MONK, SORCERER = 2, 3
FIREBALL = 1                                  # sorcerer1, src/player.data.c
KOBOLD = 0                                    # MonsterType, src/monster.h
SEED = SYM["__rand_seed"]
SEEDS = [0x2C41 + 0x3B7F * k & 0xFFFF for k in range(40)]
MON0 = SYM["encounter"] + 1
M_TYPE, M_ACTIVE, M_MAX_HP, M_HP, M_TARGET_HP, M_SIZE = 0, 5, 12, 14, 16, 64
SFX_FIRE = SYM["sfx_title_fire"]
SFX_MAGIC = SYM["sfx_monster_attack2"]
SFX_MELEE = SYM["sfx_monster_attack1"]
SFX_CRIT = SYM["sfx_monster_critical"]
SFX_MISS = SYM["sfx_miss"]


def keep_monsters_up(g, hp=60000):
    """Every active monster at `hp`, so the hero's attacks never end the fight."""
    for slot in range(3):
        m = MON0 + M_SIZE * slot
        if g.rd8(m + M_ACTIVE):
            for off in (M_MAX_HP, M_HP, M_TARGET_HP):
                g.wr16(m + off, hp)


def kobolds_here(g):
    return [s for s in range(3) if g.rd8(MON0 + M_SIZE * s + M_ACTIVE)
            and g.rd8(MON0 + M_SIZE * s + M_TYPE) == KOBOLD]


def fight(g):
    """FIGHT the first monster, then the round's lines with their sounds."""
    g.battle_menu_goto(0); g.press("a", wait=12); g.press("a", wait=12)
    return round_messages(g)


def hit_sound(post, landed):
    """The sound a landed blow's line should carry: `landed`, or the critical's own."""
    return SFX_CRIT if "CRITICAL" in post else landed


# --- Part A: the sorcerer's Fireball and the kobold's spit, on floor 1 --------
log("\n=== floor 1: Fireball and a kobold's spit keep the magic hit ===")
g, _ = start_on(1, class_id=SORCERER, level=10, abilities=0x3F, tag="t36_kobold")
fireballs, spits, axes = [], [], []
for battle in range(8):
    if len(spits) >= 3 and fireballs:
        break
    if not g.walk_until_battle(("UP", "DOWN", "LEFT", "RIGHT"), max_steps=400):
        break
    if not g.wait_for(lambda: at_menu(g), 1800):
        break
    keep_alive(g)
    log(f"  battle {battle}: {drive.foes(g)}")
    if kobolds_here(g):
        for rnd in range(40):
            if not g.wait_for(lambda: at_menu(g), 1800):
                break
            keep_alive(g); keep_monsters_up(g)
            if fireballs:
                lines = fight(g)
            else:
                cast(g, FIREBALL, wait=1)
                lines = round_messages(g)
                fireballs += [(pre, sfx) for pre, post, sfx in lines if "EXPLOSION" in pre]
            for pre, post, sfx in lines:
                if pre.startswith("Kobold") and "damage" in post:
                    (spits if "spits" in pre else axes).append((pre, post, sfx))
            if len(spits) >= 3 and fireballs:
                break
    # Cut the pack down, a lone goblin included, and walk on.
    keep_monsters_up(g, 1)
    for _ in range(12):
        if g.gs() != GS["BATTLE"]:
            break
        fight(g) if at_menu(g) else round_messages(g)
    g.wait_map_idle(600)

print("fireballs:", fireballs)
print("spits:", spits[:4])
print("axes:", axes[:4])
chk("T36 Fireball keeps the magic hit sound",
    fireballs and all(sfx == SFX_MAGIC for _, sfx in fireballs), str(fireballs))
chk("T36 a kobold's spit landed at least three times", len(spits) >= 3, f"{len(spits)} spits")
chk("T36 a spit keeps the magic hit sound, a critical its own",
    spits and all(sfx == hit_sound(post, SFX_MAGIC) for _, post, sfx in spits), str(spits[:4]))
chk("T36 a kobold's axe keeps the melee sound",
    axes and all(sfx == hit_sound(post, SFX_MELEE) for _, post, sfx in axes), str(axes[:4]))
g.close()


# --- Part B: the dragon's fire breath, on floor 8 ------------------------------
log("\n=== dragon: a landed breath roars, a dodge keeps the miss sound ===")
g = D.built(MONK, 47, None, "t36_dragon")
D.engage(g, "t36 dragon")
g.wait_for(lambda: at_menu(g), 600)          # engage() only waits for gs()==BATTLE
keep_alive(g); D.keep_up(g)
start = io.BytesIO(); g.pb.save_state(start)
breaths, dodges = [], []
for trial, seed in enumerate(SEEDS):
    if len(breaths) >= 2:
        break
    start.seek(0); g.pb.load_state(start)
    g.wr16(SEED, seed)
    for rnd in range(30):
        keep_alive(g); D.keep_up(g)
        if not g.wait_for(lambda: at_menu(g), 1800):
            break
        keep_alive(g); D.keep_up(g)
        for pre, post, sfx in fight(g):
            if "exhales" in pre:
                (dodges if post.startswith("You dodge") else breaths).append((pre, post, sfx))
        if len(breaths) >= 2:
            break

print(f"fire breath over {trial + 1} seeds")
print("breaths:", breaths[:4])
print("dodges:", dodges[:4])
chk("T36 the dragon's fire breath landed at least twice", len(breaths) >= 2,
    f"{len(breaths)} breaths, {len(dodges)} dodges")
chk("T36 a landed breath plays the title screen's fire, critical or not",
    breaths and all(sfx == SFX_FIRE for _, _, sfx in breaths), str(breaths[:4]))
chk("T36 every dodged breath seen keeps the miss sound",
    all(sfx == SFX_MISS for _, _, sfx in dodges), f"{len(dodges)} dodges {dodges[:4]}")
g.close()


# --- Part C: the death knight's hellfire orb, on floor 8 -----------------------
log("\n=== death knight: the hellfire orb keeps the magic hit ===")
g, ok = start_fight(MONK, 60, "t36_knight")
chk("T36 the fight with floor 8's death knight starts", ok, f"gs={g.gs()} ms={g.ms()} pos={g.pos()}")
keep_alive(g); keep_monsters_up(g)
crits = critical_watch(g)
start = io.BytesIO(); g.pb.save_state(start)
orbs = []
for trial, seed in enumerate(SEEDS):
    if len(orbs) >= 2:
        break
    start.seek(0); g.pb.load_state(start)
    g.wr16(SEED, seed)
    seen = len(orbs)
    for rnd in range(10):                     # the orb comes once a fight, 1 in 8 a turn
        if not g.wait_for(lambda: at_menu(g), 1800):
            break
        keep_alive(g); keep_monsters_up(g)
        crits.clear()
        orbs += [(pre, post, sfx, pre in crits) for pre, post, sfx in fight(g) if "hellfire" in pre]
        if len(orbs) > seen:
            break

print(f"hellfire orb over {trial + 1} seeds")
print("orbs:", orbs[:4])
chk("T36 the death knight's hellfire orb came up at least twice", len(orbs) >= 2, f"{len(orbs)} orbs")
chk("T36 the hellfire orb keeps the magic hit, hit or dodged, or on a critical the critical's own",
    orbs and all(sfx == (SFX_CRIT if crit else SFX_MAGIC) for _, _, sfx, crit in orbs), str(orbs[:4]))
g.close()

chk.summary()
