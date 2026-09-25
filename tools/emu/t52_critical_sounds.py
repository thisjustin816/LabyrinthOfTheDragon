"""T52 - a critical hit keeps the critical sound under a monster's own line.

damage_player() plays the critical sound on a critical. A monster attack that
writes its own line over damage_player()'s used to set its own sound with it,
hiding the critical: the death knight's longsword and hellfire orb, the
dragon's tail whip, wing flap, and claws, and the displacer beast's,
will-o-wisp's, owlbear's, and mind flayer's hits. A critical keeps the
critical sound now, and a blow that isn't one keeps the attack's own sound.
The dragon's fire breath roars with the title screen's fire either way (t36).

The death knight and the dragon stand for the rest. Each fight replays rounds
across battle seeds with the hero, a fighter, kept alive and the monster kept
up, and helpers.critical_watch() says which blows were criticals, since a
monster's own line can hide the word CRITICAL.

Offsets from LabyrinthOfTheDragon.cdb: Encounter.monsters at +1, max_hp +12,
hp +14, target_hp +16.
"""
import io, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "playtest"))
from lotd import *
from helpers import *
import dragon as D
from knight import start_fight

chk = Checker("t52_critical_sounds")
FIGHTER = 1
SEED = SYM["__rand_seed"]
SEEDS = [0x2C41 + 0x3B7F * k & 0xFFFF for k in range(24)]
ROUNDS = 6
MON0 = SYM["encounter"] + 1
M_MAX_HP, M_HP, M_TARGET_HP = 12, 14, 16
SFX_MELEE, SFX_MAGIC = SYM["sfx_monster_attack1"], SYM["sfx_monster_attack2"]
SFX_CRIT, SFX_SPECIAL_CRIT = SYM["sfx_monster_critical"], SYM["sfx_big_door_open"]
NAMES = {SYM[name]: name for name in SOUNDS}

# Each attack: words in the monster's line, words in the line of a blow that
# landed, and the sound that blow plays when it isn't a critical.
KNIGHT = {
    "longsword, two hits": ("longsword", "hit twice", SFX_SPECIAL_CRIT),
    "longsword, one hit": ("longsword", "slash you", SFX_MELEE),
    "hellfire orb": ("hellfire", "take", SFX_MAGIC),
}
DRAGON = {
    "tail whip": ("sweeps its tail", "damage", SFX_SPECIAL_CRIT),
    "wing flap": ("beats its wings", "toppled", SFX_SPECIAL_CRIT),
    "claws": ("swoops down", "damage", SFX_MELEE),
}


def fight(g):
    g.battle_menu_goto(0); g.press("a", wait=12); g.press("a", wait=1)


def keep_knight_up(g):
    for off in (M_MAX_HP, M_HP, M_TARGET_HP):
        g.wr16(MON0 + off, 60000)


def blows(g, attacks, keep_up):
    """Replay ROUNDS rounds from here on each seed, and collect (attack,
    critical, sound) for every blow of `attacks` that landed."""
    crits = critical_watch(g)
    state = io.BytesIO(); g.pb.save_state(state)
    seen = []
    for seed in SEEDS:
        state.seek(0); g.pb.load_state(state)
        g.wr16(SEED, seed)
        for _ in range(ROUNDS):
            if not g.wait_for(lambda: at_menu(g), 1800):
                break
            keep_alive(g); keep_up(g)
            crits.clear()
            fight(g)
            for pre, post, sfx in round_messages(g):
                for name, (words, landed, _) in attacks.items():
                    if words in pre and landed in post:
                        seen.append((name, pre in crits, sfx))
                        break
    return seen


def checks(monster, attacks, seen):
    crit = [(name, sfx) for name, was_crit, sfx in seen if was_crit]
    plain = [(name, sfx) for name, was_crit, sfx in seen if not was_crit]
    chk(f"T52 the {monster}'s own lines came up on landed blows, criticals among them",
        plain and crit, f"{len(plain)} plain, {len(crit)} critical, attacks "
        f"{sorted(set(name for name, _, _ in seen))}")
    chk(f"T52 a critical under the {monster}'s own line plays the critical sound",
        crit and all(sfx == SFX_CRIT for _, sfx in crit),
        str([(name, NAMES.get(sfx, sfx)) for name, sfx in crit[:6]]))
    chk(f"T52 a blow of the {monster}'s that isn't a critical plays the attack's own sound",
        plain and all(sfx == attacks[name][2] for name, sfx in plain),
        str([(name, NAMES.get(sfx, sfx)) for name, sfx in plain if sfx != attacks[name][2]][:6]))


# --- the death knight, on floor 8 ---------------------------------------------
g, ok = start_fight(FIGHTER, 60, "t52_knight")
chk("T52 the fight with floor 8's death knight starts", ok, f"gs={g.gs()} pos={g.pos()}")
checks("death knight", KNIGHT, blows(g, KNIGHT, keep_knight_up) if ok else [])
g.close()

# --- the dragon ---------------------------------------------------------------
g = D.built(FIGHTER, 47, None, "t52_dragon")
D.engage(g, "t52 dragon")
ok = g.wait_for(lambda: at_menu(g), 600)
chk("T52 the dragon's fight starts", ok, f"gs={g.gs()}")
checks("dragon", DRAGON, blows(g, DRAGON, D.keep_up) if ok else [])
g.close()

chk.summary()
