"""T46 - every hero ability plays a sound when it works.

Each class's basic attack and six abilities are used against floor 8's gauntlet
goblin, replayed from a savestate across battle seeds until the outcome in
question comes up. A landed blow, critical or not, plays its class's hit sound:
the monk's strike, the fighter's melee attack, or the magic hit for the druid's
and sorcerer's spells, with Action Surge playing a sound of its own. Buffs play
the powerup Evasion plays, and an outright kill plays the special critical
sound. A miss keeps the miss sound, checked against a goblin whose DEF and MDEF
are raised to 255. Trip Attack against a monster immune to it plays the fail
sound, checked on the gauntlet's gelatinous cube. A blow the displacer beast
phases out of plays the miss sound too, checked on the gauntlet's displacer
beast one blow short of its phase. Sleetstorm against a lone gelatinous cube,
immune to it, says so with the fail sound, and a Wild Magic surge that lands
nothing, checked on a goblin with no room left for a debuff, fizzles with the
fail sound.

Every check reads battle_sfx when the hero's line appears, which is the sound
that line is about to play. The line is found by its opening words: an ability
that skips its own result line leaves the monster's last one in place.
"""
import io, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "playtest"))
from lotd import *
from helpers import *
from starts import start_on

chk = Checker("t46_ability_sounds")
DRUID, FIGHTER, MONK, SORCERER = 0, 1, 2, 3
CLASS = {DRUID: "druid", FIGHTER: "fighter", MONK: "monk", SORCERER: "sorcerer"}
LEVEL = 48
FIGHT = None                                  # the basic attack, off the main menu
ARMORED, CUBE_FIGHT, PHASING, CROWDED = "armored", "cube", "phasing", "crowded"
REGEN, FLAG_REGEN, PERPETUAL = 12, 0x10, 0xFF  # BUFF_REGEN, FLAG_BUFF_REGEN (src/stats.h)
SEED = SYM["__rand_seed"]
SEEDS = [0x2C41 + 0x3B7F * k & 0xFFFF for k in range(48)]
MON0 = SYM["encounter"] + 1
M_HP, M_TARGET_HP = 14, 16
M_DEF_BASE, M_DEF, M_MDEF_BASE, M_MDEF = 22, 23, 26, 27
M_PARAMETER = 58                              # the displacer beast's blows to its phase
M_EFFECTS = 34                                # four 5-byte status effect slots
GOBLIN, CUBE, DISPLACER = (2, 27), (3, 22), (13, 22)   # gauntlet fight tiles, src/floor8.c
SOUNDS = {
    "sfx_action_surge": "the Action Surge sound",
    "sfx_big_door_open": "the special critical sound",
    "sfx_heal": "the heal sound",
    "sfx_magic_missile": "the magic missile sound",
    "sfx_melee_attack": "the fighter's attack sound",
    "sfx_mid_powerup": "the powerup sound",
    "sfx_miss": "the miss sound",
    "sfx_monk_strike": "the monk strike sound",
    "sfx_monster_attack2": "the magic hit sound",
    "sfx_monster_fail": "the fail sound",
    "sfx_poison_spray": "the poison spray sound",
}
NAMES = {SYM[name]: name for name in SOUNDS}


def landed(post):
    return post.startswith(("You deal", "CRITICAL HIT!", "SUPER EFFECTIVE", "They resist"))


def missed(post):
    return post == "But you miss!"


def whiffed(post):
    return post == "A COMPLETE WHIFF."


def immune(post):
    return post == "They're completely immune!"


def phased(post):
    return post == "They phase out and evade the attack!"


def reads(*lines):
    return lambda post: post in lines


def anything(post):
    return True


# Every line Wild Magic writes itself; a surge that landed on a monster skips its
# own line, leaving whatever the round wrote before.
WILD_MAGIC_LINES = ("And a fireball goes flying!", "And a sleetstorm descends!",
                    "They're completely immune!", "But it fizzles.")


# (ability, action, its line's opening words, outcome, outcome's post line, sound, fight)
CHECKS = {
    DRUID: [
        ("Poison Spray", FIGHT, "Poison gas erupts", "a hit", landed, "sfx_poison_spray", None),
        ("Cure Wounds", 0, "You're enveloped", "the heal", anything, "sfx_heal", None),
        ("Bark Skin", 1, "Your skin grows", "the buff", anything, "sfx_mid_powerup", None),
        ("Lightning", 2, "Bolts of lightning", "a hit", landed, "sfx_monster_attack2", None),
        ("Lightning", 2, "Bolts of lightning", "a miss", missed, "sfx_miss", ARMORED),
        ("Heal", 3, "Radiant green light", "the heal", anything, "sfx_heal", None),
        ("Insect Plague", 4, "Locusts swarm", "a hit", lambda p: not whiffed(p),
         "sfx_monster_attack2", None),
        ("Insect Plague", 4, "Locusts swarm", "a whiff", whiffed, "sfx_miss", ARMORED),
        ("Regenerate", 5, "You surge with", "the buff", anything, "sfx_mid_powerup", None),
        ("Poison Spray", FIGHT, "Poison gas erupts", "a phased blow", phased, "sfx_miss", PHASING),
        ("Lightning", 2, "Bolts of lightning", "a phased blow", phased, "sfx_miss", PHASING),
    ],
    FIGHTER: [
        ("Attack", FIGHT, "You rush forward", "a hit", landed, "sfx_melee_attack", None),
        ("Second Wind", 0, "You catch your", "the heal", anything, "sfx_heal", None),
        ("Action Surge", 1, "You surge forth", "a hit", landed, "sfx_action_surge", None),
        ("Cleave", 2, "You cleave", "a hit", lambda p: not whiffed(p), "sfx_melee_attack", None),
        ("Cleave", 2, "You cleave", "a whiff", whiffed, "sfx_miss", ARMORED),
        ("Trip Attack", 3, "You sweep your", "a trip", reads("You topple your foe!"),
         "sfx_melee_attack", None),
        ("Trip Attack", 3, "You sweep your", "an immune target", immune, "sfx_monster_fail",
         CUBE_FIGHT),
        ("Menace", 4, "You growl", "a scare", lambda p: not immune(p), "sfx_monster_attack2",
         None),
        ("Indomitable", 5, "You feel invincible", "the buff", anything, "sfx_mid_powerup", None),
        ("Attack", FIGHT, "You rush forward", "a phased blow", phased, "sfx_miss", PHASING),
        ("Action Surge", 1, "You surge forth", "a phased blow", phased, "sfx_miss", PHASING),
    ],
    MONK: [
        ("Strike", FIGHT, "You strike with your", "a hit", landed, "sfx_monk_strike", None),
        ("Evasion", 0, "You feel light", "the buff", anything, "sfx_mid_powerup", None),
        ("Open Palm", 1, "You strike with an open", "a hit", landed, "sfx_monk_strike", None),
        ("Open Palm", 1, "You strike with an open", "a miss", missed, "sfx_miss", ARMORED),
        ("Still Mind", 2, "You become one", "the cleanse",
         reads("Healed of all ills, and beyond fear."), "sfx_mid_powerup", None),
        ("Flurry", 3, "You attack with a flurry", "a hit", landed, "sfx_monk_strike", None),
        ("Flurry", 3, "You attack with a flurry", "a miss", missed, "sfx_miss", ARMORED),
        ("Diamond Body", 4, "You become tough", "the buff", anything, "sfx_mid_powerup", None),
        ("Quivering Palm", 5, "You attack their", "a hit", landed, "sfx_monk_strike", None),
        ("Quivering Palm", 5, "You attack their", "an outright kill", reads("And end them."),
         "sfx_big_door_open", None),
        ("Quivering Palm", 5, "You attack their", "a miss", missed, "sfx_miss", ARMORED),
        ("Strike", FIGHT, "You strike with your", "a phased blow", phased, "sfx_miss", PHASING),
        ("Open Palm", 1, "You strike with an open", "a phased blow", phased, "sfx_miss", PHASING),
        ("Flurry", 3, "You attack with a flurry", "a phased blow", phased, "sfx_miss", PHASING),
        ("Quivering Palm", 5, "You attack their", "a phased blow", phased, "sfx_miss", PHASING),
    ],
    SORCERER: [
        ("Magic Missile", FIGHT, "You fire a magic", "a hit", landed, "sfx_magic_missile", None),
        ("Darkness", 0, "You enshroud", "the blinding", lambda p: not immune(p),
         "sfx_monster_attack2", None),
        ("Fireball", 1, "EXPLOSION", "the blast", anything, "sfx_monster_attack2", None),
        ("Haste", 2, "You speed up", "the buff", anything, "sfx_mid_powerup", None),
        ("Sleetstorm", 3, "Sleet rains down", "the storm", anything, "sfx_monster_attack2", None),
        ("Disintegrate", 4, "You send forth", "a hit", landed, "sfx_monster_attack2", None),
        ("Disintegrate", 4, "You send forth", "an outright kill", reads("And they are no more."),
         "sfx_big_door_open", None),
        ("Sleetstorm", 3, "Sleet rains down", "a storm against the immune cube", immune,
         "sfx_monster_fail", CUBE_FIGHT),
        ("Wild Magic", 5, "You let loose", "a surge that lands on the goblin",
         lambda p: p not in WILD_MAGIC_LINES, "sfx_monster_attack2", None),
        ("Wild Magic", 5, "You let loose", "a surge with no room for its debuffs",
         reads("But it fizzles."), "sfx_monster_fail", CROWDED),
        ("Wild Magic", 5, "You let loose", "a surge that casts Fireball or Sleetstorm",
         reads("And a fireball goes flying!", "And a sleetstorm descends!"),
         "sfx_monster_attack2", None),
        ("Magic Missile", FIGHT, "You fire a magic", "a phased blow", phased, "sfx_miss", PHASING),
        ("Disintegrate", 4, "You send forth", "a phased blow", phased, "sfx_miss", PHASING),
    ],
}


def battle_state(g, floor, tile):
    """A savestate at the first command menu of the gauntlet fight on `tile`,
    stepped onto from the tile to its right, or None if the fight never started."""
    floor.seek(0); g.pb.load_state(floor)
    if not reenter_floor(g, 8, tile[0] + 1, tile[1]):
        return None
    g.step("LEFT")
    read_textbox(g)
    if not g.wait_for(lambda: at_menu(g), 1800):
        return None
    state = io.BytesIO(); g.pb.save_state(state)
    return state


def hero_line(g, state, action, opening, seed, fight):
    """The hero's (post line, sound) after using `action` from `state` under
    `seed`, or None when the hero's line never came up that round."""
    state.seek(0); g.pb.load_state(state)
    g.wr16(SEED, seed)
    keep_alive(g, sp=999)
    g.wr16(MON0 + M_HP, 60000); g.wr16(MON0 + M_TARGET_HP, 60000)
    if fight == ARMORED:
        for off in (M_DEF_BASE, M_DEF, M_MDEF_BASE, M_MDEF):
            g.wr8(MON0 + off, 255)
    if fight == PHASING:
        g.wr8(MON0 + M_PARAMETER, 1)
    if fight == CROWDED:
        for slot in range(4):
            for off, value in enumerate((1, REGEN, FLAG_REGEN, PERPETUAL, 3)):
                g.wr8(MON0 + M_EFFECTS + 5 * slot + off, value)
    if action is FIGHT:
        g.battle_menu_goto(0); g.press("a", wait=12); g.press("a", wait=1)
    elif not cast(g, action, wait=1):
        return None
    for pre, post, sound in round_messages(g):
        if pre.startswith(opening):
            return post, sound
    return None


for cls, checks in CHECKS.items():
    log(f"\n=== {CLASS[cls]} ===")
    g, _ = start_on(8, class_id=cls, level=LEVEL, abilities=0x3F, tag=f"t46_{CLASS[cls]}")
    floor = io.BytesIO(); g.pb.save_state(floor)
    fights = {None: battle_state(g, floor, GOBLIN)}
    fights[ARMORED] = fights[CROWDED] = fights[None]
    if any(check[-1] == CUBE_FIGHT for check in checks):
        fights[CUBE_FIGHT] = battle_state(g, floor, CUBE)
    fights[PHASING] = battle_state(g, floor, DISPLACER)
    chk(f"T46 {CLASS[cls]}: the gauntlet fights start",
        all(fights.values()), f"started={[k for k, v in fights.items() if v]}")
    for ability, action, opening, outcome, want, sound, fight in checks:
        seen, trial = None, None
        if fights[fight]:
            for trial, seed in enumerate(SEEDS):
                line = hero_line(g, fights[fight], action, opening, seed, fight)
                if line and want(line[0]):
                    seen = line
                    break
        if seen:
            detail = f"seed {trial}: {seen[0]!r} played {NAMES.get(seen[1], hex(seen[1]))}"
        else:
            detail = f"never came up in {len(SEEDS)} seeds"
        chk(f"T46 {CLASS[cls]} {ability}: {outcome} plays {SOUNDS[sound]}",
            seen and seen[1] == SYM[sound], detail)
    g.close()

chk.summary()
