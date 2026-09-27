"""Emulator-driving helpers built on nav.Floor: walking a planned path,
crossing an exit, fighting a battle out, and using items and abilities. Every
step's position is checked, so a mismatch between the map model and the game
surfaces at once instead of wandering off course."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir))   # tools/emu, for lotd
from lotd import *
from nav import Floor, DIRS as DIRS_XY

LOG = []
def log(s):
    LOG.append(s)
    print(s)


# Inventory is Item[8] of {id u8, quantity u8, name ptr u16}, in ITEM_NAMES order.
ITEM = {name: i for i, name in enumerate(ITEM_NAMES)}


def item_qty(g, item_id):
    return g.rd8(SYM["inventory"] + 4 * item_id + 1)


# The player's live status effects, encounter.player_status_effects: four
# 5-byte StatusEffectInstance entries {active, effect, flag, duration, tier} at
# encounter+209, the offset t22_debuff_immunity.py reads. An effect id at or
# below DEBUFF_DEF_DOWN is a debuff (stats.h is_debuff()).
PLAYER_EFFECTS, EFFECT_SIZE, EFFECT_COUNT, LAST_DEBUFF_ID = SYM["encounter"] + 209, 5, 4, 7


def has_live_debuff(g):
    """Whether the player carries a debuff right now. player.debuffs is only a
    mirror of this list, which check_status_effects() refreshes at the start
    of the player's own turn, so a debuff landing after the player has acted
    still reads clear at the next menu, where the bot decides. A player sees
    it the moment it lands. Against floor 8's mind flayer the lag is fatal:
    Mind Blast after the player's turn, a clear mirror at the next menu, no
    cure, and Extract Brain that round, an outright kill from full HP."""
    for k in range(EFFECT_COUNT):
        base = PLAYER_EFFECTS + k * EFFECT_SIZE
        if g.rd8(base) and g.rd8(base + 1) <= LAST_DEBUFF_ID:
            return True
    return False


# The monsters of a fight, read off Encounter.monsters[3] (64 bytes each:
# type at +0, active +5, level +9, exp_tier +11), for telling a fight's tier.
MONSTER_NAMES = ["kobold", "goblin", "zombie", "bugbear", "owlbear", "cube",
                 "displacer beast", "wisp", "deathknight", "mind flayer",
                 "beholder", "dragon"]
TIER_NAMES = "CBAS"


def foes(g):
    out = []
    for slot in range(3):
        base = SYM["encounter"] + 1 + 64 * slot
        if g.rd8(base + 5):
            kind, level, tier = g.rd8(base), g.rd8(base + 9), g.rd8(base + 11)
            name = MONSTER_NAMES[kind] if kind < len(MONSTER_NAMES) else f"type {kind}"
            out.append(f"{name} L{level} {TIER_NAMES[tier] if tier < 4 else tier}")
    return out


def foe_levels(g):
    """Levels of the foes still standing."""
    return [g.rd8(SYM["encounter"] + 1 + 64 * slot + 9)
            for slot in range(3) if g.rd8(SYM["encounter"] + 1 + 64 * slot + 5)]


# The last battle resolve_battle() finished, for a caller that wants its
# numbers: outcome, foes, actions (the player's turns), taken (HP lost, heals
# not netted off), max_hp, worst_hit, ratio and spent ({item: count}).
#
# ratio is max_hp / taken, which is balance/margins.py's measure played out
# rather than computed: margins.py divides the rounds a monster needs to kill
# the player by the rounds the player needs to kill it. A fight the player won
# in R rounds while taking T damage had the monster dealing T/R a round, so it
# would have needed max_hp*R/T rounds, and the ratio is max_hp/T. Above 1 the
# player outlasts the monster, as in margins.py. It counts the player's turns
# spent on items and buffs, so it reads a little lower than margins.py's
# attack-only figure.
LAST_BATTLE = {}


def use_battle_item(g, item_id):
    """Use an inventory item from the battle menu. Returns True if the game
    took it.

    The ITEM submenu lists only the slots with a non-zero quantity, in
    ItemId order, so the row for an item is just how many non-empty slots
    sit ahead of it. An item can_use_item() rejects is listed all the same
    and refused at the confirm, with the error sound and the submenu left
    open. A taken one closes the menu and starts the round; it leaves the
    inventory on the player's turn, or stays there with "You don't need
    it, so you keep it." if it does not apply by then. BattleMenu fields
    (src/battle.h): active_menu +0, screen_cursor +1, entries +3, cursor +4;
    active_menu 4 is BATTLE_MENU_ITEM, which is what confirms the submenu
    actually opened rather than the press falling through on an empty
    inventory."""
    if item_qty(g, item_id) == 0:
        return False
    if not g.battle_menu_goto(2):
        return False
    bm = SYM["battle_menu"]
    g.press("a", wait=14)
    if g.rd8(bm) != 4:                       # BATTLE_MENU_ITEM did not open
        return False
    # Read the row->ItemId map the menu actually built rather than
    # inferring it from inventory order.
    # BattleMenu: item_at[] sits after active_menu/screen_cursor/
    # last_ability_cursor/entries/cursor/scroll/max_scroll (7) +
    # active_ability (2) + ability_text[6][19] + item_text[8][19].
    ITEM_AT = 7 + 2 + (6 * 19) + (8 * 19)
    entries = g.rd8(bm + 3)
    row = None
    for i in range(min(entries, 8)):
        if g.rd8(bm + ITEM_AT + i) == item_id:
            row = i
            break
    if row is None:
        for _ in range(3):
            g.press("b", wait=12)
        return False
    for _ in range(8):
        cur = g.rd8(bm + 4)
        if cur == row:
            break
        g.press("down" if cur < row else "up", wait=10)
    if g.rd8(bm + 4) != row:
        return False
    g.press("a", wait=24)
    # battle_state 2 is the menu; still there with the item submenu open
    # means the confirm was refused.
    if g.gs() == GS["BATTLE"] and g.rd8(SYM["battle_state"]) == 2 and g.rd8(bm) == 4:
        for _ in range(3):
            g.press("b", wait=12)
        return False
    g.press("a", wait=24)
    return True


def field_heal(g, target_frac=63):
    """Top HP up from the map menu between fights, the way a player does.

    This game has no inn, no save-point heal and no passive regeneration:
    outside battle the only restoratives are the map menu's item picker
    (map.menu.c's use_field_item) and the full heal that comes with every
    level gained. A bot that only drinks mid-fight therefore walks into
    each encounter on whatever HP the last one left it with, and floor 6's
    paired B-tier owlbears are winnable from a full bar but not from a
    partial one.

    A potion restores 6/16 of max HP (item.h's POTION_HEAL_FACTOR), so one
    drunk above 62% is mostly wasted. The default drinks only while a whole
    potion still fits; a caller topping up for a boss passes a higher
    `target_frac`.

    MapMenu (src/map.h): state +0, cursor +1, with the cursor laid out
    RETURN 0 / SAVE 1 / QUIT 2 / ITEMS 3 in a 2x2 grid, so ITEMS is one
    press right of the default. Only spends potions. The picker opens on the
    first usable item in POTION, ETHER, ELIXIR order, which is the potion
    for a hurt hero holding one, and moves on to the next usable item when
    the potions run out, so the loop stops before pressing A on anything
    else."""
    pl, mm = SYM["player"], SYM["map_menu"]
    mx = g.rd16(pl + POFF["max_hp"])
    if mx == 0 or g.rd16(pl + POFF["hp"]) * 100 >= mx * target_frac:
        return False
    if not item_qty(g, ITEM["POTION"]):
        return False
    if g.gs() != GS["WORLD_MAP"] or g.ms() != MS["WAITING"]:
        return False

    g.press("start", wait=24)
    for _ in range(4):
        if g.rd8(mm + 1) == 3:          # MAP_MENU_CURSOR_ITEMS
            break
        g.press("right", wait=12)
    if g.rd8(mm + 1) != 3:
        g.press("b", wait=12)
        return False
    g.press("a", wait=24)

    drank = 0
    for _ in range(8):
        if g.rd16(pl + POFF["hp"]) * 100 >= mx * target_frac or not item_qty(g, ITEM["POTION"]):
            break
        before = g.rd16(pl + POFF["hp"])
        g.press("a", wait=24)
        if g.rd16(pl + POFF["hp"]) == before:
            break
        drank += 1
    for _ in range(3):
        g.press("b", wait=14)
    g.wait_for(lambda: g.gs() == GS["WORLD_MAP"] and g.ms() == MS["WAITING"], 200)
    if drank:
        log(f"  topped up between fights: drank {drank}, "
            f"hp={g.rd16(pl+POFF['hp'])}/{mx}")
    return drank > 0


# What each class can do in a fight, keyed by the ability's index in that
# class's table in src/player.data.c (CLASS_* order from src/player.h). "sp"
# lists every ability's cost in the same index order.
#
# The enemy-debuff abilities are left out: against one monster they cost a
# turn and return less than an attack does.
#
#   guard    one or more buff openers, cast in order once each per fight:
#            mitigation (Bark Skin, Diamond Body, Indomitable), sustain
#            (Regenerate) or tempo (Haste, which raises damage dealt rather
#            than cutting damage taken)
#   nuke     strongest single-target attack
#   sweep    area attack, for a random fight against two or more foes
#   bigheal  restores the whole bar
#   heal     restores part of it
#   cleanse  clears every debuff at once
#
# Monk and Sorcerer genuinely have no heal; both lean on items instead, which
# is the kit the game gives them. The monk has no area attack.
CLASS_PLANS = {
    0: {"sp": (3, 6, 9, 12, 15, 19),                        # Druid
        "guard": (5, 1), "nuke": 2, "sweep": 4, "bigheal": 3, "heal": 0},
    1: {"sp": (7, 14, 19, 23, 28, 35),                      # Fighter
        "guard": 5, "nuke": 1, "sweep": 2, "heal": 0},
    2: {"sp": (5, 10, 14, 18, 23, 29),                      # Monk
        "guard": 4, "nuke": 5, "cleanse": 2},
    3: {"sp": (4, 8, 12, 15, 20, 25),                       # Sorcerer
        "guard": (2,), "nuke": 4, "sweep": 1},
}


def class_plan(g):
    return CLASS_PLANS.get(g.rd8(SYM["player"] + POFF["player_class"]))


def ability_row(g, index):
    """Battle-menu row for an ability index, or None when it isn't unlocked.

    The submenu lists every unlocked ability regardless of SP
    (render_ability_text in src/battle.c walks player_num_abilities with no
    affordability filter), so rows don't shift underfoot the way the item
    menu's do. set_player_abilities packs the unlocked ones in class order,
    which makes the row just the count of unlocked abilities below this one."""
    flags = g.rd8(SYM["player"] + POFF["ability_flags"])
    if not flags & (1 << index):
        return None
    return bin(flags & ((1 << index) - 1)).count("1")


def ability_for_index(g, plan, index):
    """Menu row for a specific ability index when it is affordable, or None."""
    if g.rd16(SYM["player"] + POFF["sp"]) < plan["sp"][index]:
        return None
    return ability_row(g, index)


def ability_for(g, plan, role):
    """Menu row for a role's ability when it is unlocked and affordable."""
    index = plan.get(role) if plan else None
    if index is None:
        return None
    return ability_for_index(g, plan, index)


def cast_ability(g, row, confirm_post=True, wait=20):
    """Cast the ability sitting on `row` of the ability submenu.

    Selecting one the player can't afford only plays an error sound and leaves
    the menu open, so callers check SP first through ability_for(). A
    single-target ability opens a monster-select step that needs its own
    confirm; reading active_menu catches that without tracking which abilities
    target what. `confirm_post=False` drops the trailing press for an ability
    that calls SKIP_POST_MSG: with no post-message box to dismiss, that
    press instead lands on whatever comes up next -- the next turn's own menu,
    on a fast enough round -- and acts for the bot there."""
    bm = SYM["battle_menu"]
    if not g.battle_menu_goto(1):
        return False
    g.press("a", wait=14)
    if g.rd8(bm) != 2:                       # BATTLE_MENU_ABILITY
        return False
    for _ in range(8):
        cur = g.rd8(bm + 4)
        if cur == row:
            break
        g.press("down" if cur < row else "up", wait=10)
    if g.rd8(bm + 4) != row:
        for _ in range(3):
            g.press("b", wait=12)
        return False
    g.press("a", wait=wait)
    if g.rd8(bm) == 3:                       # BATTLE_ABILITY_MONSTER_SELECT
        g.press("a", wait=wait)
    if confirm_post:
        g.press("a", wait=20)
    return True


def resolve_battle(g, max_iters=3000, may_flee=False, use_buffs=False):
    """Fight a battle to a finish. Whenever the main menu (battle_state==2)
    isn't up, this presses A and moves on, which covers attack animations,
    status-effect messages, and the BATTLE_SUCCESS and BATTLE_LEVEL_UP
    reward screens that need the same dismissal as any textbox.

    At the menu it follows the class's plan in CLASS_PLANS, in order: a
    remedy for a live debuff, the class's own cleanse, its guard openers
    when `use_buffs` is set, a full heal off SP when HP is in danger, the
    buff items when `use_buffs` is set, an elixir or a potion when HP is in
    danger, an ether when SP falls short of the plan, another ether in a
    group fight when the sweep is known but unaffordable and ethers are
    plentiful, a flee below 35% HP when `may_flee` is set, and otherwise a
    heal ability, the nuke when `use_buffs` is set, the sweep when it isn't
    and two or more foes are up, or FIGHT.

    A lost fight sets game_state to DEATH for a window too short to poll
    reliably before the floor's respawn logic runs. A battle never moves the
    map position on a real victory, so the position from before the fight is
    checked again once the map is back; a mismatch means the fight was lost.
    Returns "victory", "fled", "death", or "stuck" (gave up after
    max_iters)."""
    pl = SYM["player"]
    BS = SYM["battle_state"]
    pre_battle_pos = g.pos()
    fled = False
    # Heal against how hard this particular fight actually hits rather
    # than a fixed percentage. The dragon rolls three attacks a turn off
    # level-80 stats and can take over 70% of a level-60 hero's bar in one
    # round; against that, a "heal under 30%" rule never fires in a
    # survivable window, because the turn that drops you under 30% is the
    # same turn that kills you. Trivial fights never reach the threshold,
    # so this costs nothing where it isn't needed.
    worst_hit = 0
    prev_hp = None
    buffs_used = set()
    refused = set()
    stock = {name: item_qty(g, i) for name, i in ITEM.items()}
    actions = taken = 0
    hp_seen = g.rd16(pl + POFF["hp"])
    against = foes(g)

    def done(outcome):
        max_hp = g.rd16(pl + POFF["max_hp"])
        spent = {name: stock[name] - item_qty(g, i) for name, i in ITEM.items()
                 if item_qty(g, i) < stock[name]}
        LAST_BATTLE.clear()
        LAST_BATTLE.update(outcome=outcome, foes=against, actions=actions, taken=taken,
                           max_hp=max_hp, worst_hit=worst_hit, spent=spent,
                           ratio=max_hp / taken if taken else float("inf"))
        log(f"    battle {outcome} vs {' + '.join(against) or '?'}: {actions} actions, "
            f"took {taken} of {max_hp} HP (ratio {LAST_BATTLE['ratio']:.1f}), "
            f"worst hit {worst_hit}, spent {spent or 'nothing'}")
        return outcome

    for _ in range(max_iters):
        # Every drop counts, whenever it lands; sampling only at the menu
        # would net a potion's heal against the hit that followed it.
        hp_now = g.rd16(pl + POFF["hp"])
        if hp_now < hp_seen:
            taken += hp_seen - hp_now
        hp_seen = hp_now
        gs = g.gs()
        if gs == GS["WORLD_MAP"]:
            if g.pos() != pre_battle_pos:
                return done("death")
            return done("fled" if fled else "victory")
        if gs == GS["DEATH"]:
            return done("death")
        if gs == GS["BATTLE"] and g.rd8(BS) == 10:   # BATTLE_PLAYER_FLED
            fled = True
        if gs != GS["BATTLE"]:
            g.press("a", hold=2, wait=8)
            continue
        if g.rd8(BS) != 2:
            g.press("a", hold=2, wait=8)
            continue
        hp = g.rd16(pl + POFF["hp"])
        max_hp = g.rd16(pl + POFF["max_hp"])
        sp = g.rd16(pl + POFF["sp"])
        plan = class_plan(g)
        frac = hp * 100 // max(max_hp, 1)
        # Back out of a submenu left open by a refused action. The game can
        # decline a selection it still listed -- a remedy whose effects another
        # remedy already cleared, for instance -- which plays an error and
        # leaves the submenu up. Every menu helper here starts from the main
        # menu, so without this the next decision opens nothing, changes
        # nothing, and the identical choice repeats: the round never completes,
        # so the debuff that prompted it never expires either. A player just
        # presses B.
        for _ in range(3):
            if g.rd8(SYM["battle_menu"]) == 0:
                break
            g.press("b", wait=12)
        if prev_hp is not None and prev_hp > hp:
            worst_hit = max(worst_hit, prev_hp - hp)
        prev_hp = hp
        # Top up while a further round of the worst damage seen so far
        # would still leave us standing, with a 60% margin on top, capped at
        # 70% of max_hp. Uncapped, a single hit at or above 62.5% of max_hp
        # (a dragon round can pass 70%) puts worst_hit*8//5 above max_hp for
        # good, so every later turn reads as in danger even at full HP and
        # the bot spends the rest of the fight on heals without attacking.
        # Ordinary fights never hit hard enough for the cap to matter.
        danger = min(max(worst_hit * 8 // 5, max_hp // 5), max_hp * 7 // 10)
        acted = False
        # A random fight against two or more foes, one of them within 12
        # levels of the hero, is worth a spell. Random fights save the nuke
        # for bosses, so without the sweep a caster meets every group with its
        # weak basic attack: a level 44 sorcerer spent 5 turns and 120 HP on a
        # pair of level 36 zombies. A group further below dies to that attack
        # in a turn, and a spell on it only drains the SP the next floor needs.
        levels = foe_levels(g)
        group_fight = (not use_buffs and len(levels) >= 2
                       and max(levels) + 12 >= g.rd8(pl + POFF["level"]))
        # Clear any active debuff before anything else. Some monsters gate a
        # scripted follow-up purely on a debuff bit rather than on damage --
        # the mind flayer's Extract Brain (src/monsters.bank7.c) sets
        # player.hp = 0 outright once DEBUFF_CONFUSED is set, independent of
        # current HP -- so a lingering debuff is a bigger threat than low HP
        # and is worth a turn to cure even at full health.
        if (has_live_debuff(g) and item_qty(g, ITEM["REMEDY"])
                and "REMEDY" not in refused):
            acted = use_battle_item(g, ITEM["REMEDY"])
            # A remedy whose effects an earlier remedy already cleared is
            # still listed but refused, and the debuff this pass saw can
            # still be there on the next one, which would pick it again.
            if not acted:
                refused.add("REMEDY")
        # A class that can clear its own debuffs should, before spending a
        # remedy it may need later.
        if not acted and has_live_debuff(g):
            row = ability_for(g, plan, "cleanse")
            if row is not None:
                acted = cast_ability(g, row)
        # Mitigation is worth the opening turn of a real fight: it applies to
        # every hit that follows, which no consumable in this game does.
        # Random encounters skip it -- they end before it pays for the turn.
        if not acted and use_buffs and hp > danger:
            guard_plan = plan.get("guard") if plan else None
            if guard_plan is not None:
                guard_indices = guard_plan if isinstance(guard_plan, tuple) else (guard_plan,)
                for index in guard_indices:
                    if ("guard", index) in buffs_used:
                        continue
                    row = ability_for_index(g, plan, index)
                    if row is None:
                        continue
                    if cast_ability(g, row, confirm_post=False):
                        buffs_used.add(("guard", index))
                        acted = True
                    break
        # A full heal off SP saves an elixir for a fight that has no SP left.
        if not acted and hp <= danger:
            row = ability_for(g, plan, "bigheal")
            if row is not None:
                acted = cast_ability(g, row)
        # Open a boss fight by spending the buff consumables, one per
        # turn, while there is still HP to spare. Regen is the important
        # one: it heals every turn for free, which is the only thing that
        # breaks the "every heal costs a turn, and the turn costs more
        # than the heal" spiral that makes the dragon look unwinnable.
        # Def-up cuts what comes in, atk-up and haste shorten the fight.
        #
        # Gated on worst_hit > 0, never the first turn, because the first
        # turn has no information yet: danger is still the max_hp//5 floor,
        # so "hp > danger" at full HP says nothing about whether this fight's
        # opening can one-shot the character. Against the dragon, spending
        # the first two turns on REGEN and HASTE, neither of which cuts
        # incoming damage, loses the fight before an attack lands. Once any
        # hit has landed, danger reflects it and REGEN's free recurring heal
        # is worth the turn for the rest of the fight.
        if not acted and use_buffs and worst_hit > 0 and hp > danger:
            for name in ("REGEN", "DEF_UP", "ATK_UP", "HASTE"):
                if name in buffs_used or not item_qty(g, ITEM[name]):
                    continue
                if use_battle_item(g, ITEM[name]):
                    buffs_used.add(name)
                    acted = True
                break
        # Consumables first when things are actually dangerous: an elixir
        # for a real emergency, a potion for ordinary chip damage, and an
        # ether once there's no SP left to cast with. Without this the bot
        # only knows "attack" and one spell, which is a far harsher bar
        # than a real player faces and is not a fair test of the balance.
        if not acted and hp <= danger and item_qty(g, ITEM["ELIXIR"]):
            acted = use_battle_item(g, ITEM["ELIXIR"])
        if not acted and hp <= danger and item_qty(g, ITEM["POTION"]):
            acted = use_battle_item(g, ITEM["POTION"])
        # Top SP up against what this fight's plan actually needs rather than
        # waiting for it to hit zero: a nuke is worth several basic attacks,
        # and the ether costs the same turn whenever it is drunk. Only
        # abilities the hero has unlocked count; an ether drunk for a spell
        # it can't cast yet spends a turn on nothing.
        #
        # Capped at max_sp: an early-game character's cap can sit below a
        # high-tier ability's cost (a level-12 monk has 20 max SP; Quivering
        # Palm costs 29), and an uncapped `want` makes `sp < want` true
        # forever -- no number of ethers can ever raise sp past max_sp.
        if not acted and hp > danger and plan and item_qty(g, ITEM["ETHER"]):
            max_sp = g.rd16(pl + POFF["max_sp"])
            want = 0
            if use_buffs and "nuke" in plan and ability_row(g, plan["nuke"]) is not None:
                want = plan["sp"][plan["nuke"]]
            heal_index = plan.get("bigheal", plan.get("heal"))
            if heal_index is not None and ability_row(g, heal_index) is not None:
                want = max(want, plan["sp"][heal_index])
            want = min(want, max_sp)
            if want and sp < want:
                acted = use_battle_item(g, ITEM["ETHER"])
        # Fight going badly: run. Healing 3 SP at a time does not keep
        # up with floor 6's paired B-tier owlbears, so waiting until SP is
        # actually exhausted is already too late -- a player watching their
        # HP go red just leaves. roll_flee() can refuse, so this keeps
        # trying rather than assuming it worked. A bot that never flees is
        # strictly worse than a player in a way that reads as the game
        # being too hard.
        # In such a fight, an ether when the sweep is known but unaffordable
        # and ethers are plentiful: the next turn then clears the group.
        if (not acted and group_fight and hp > danger and plan and "sweep" in plan
                and ability_row(g, plan["sweep"]) is not None
                and sp < plan["sp"][plan["sweep"]]
                and item_qty(g, ITEM["ETHER"]) >= 3):
            acted = use_battle_item(g, ITEM["ETHER"])
        if not acted and may_flee and frac < 35:
            g.battle_menu_goto(3); g.press("a", wait=16); g.press("a", wait=16)
            acted = True
        if not acted:
            # Heal below 70%, not 50%: past floor 1 a death costs the whole
            # run, not just this fight. Items are held back for a real
            # emergency (hp <= danger, handled above), so this tier spends SP.
            soft_heal = ability_for(g, plan, "heal")
            if soft_heal is None:
                soft_heal = ability_for(g, plan, "bigheal")
            nuke = ability_for(g, plan, "nuke") if use_buffs else None
            sweep = ability_for(g, plan, "sweep") if group_fight else None
            choice = None
            if (hp <= danger or hp * 10 < max_hp * 7) and soft_heal is not None:
                choice = soft_heal
            elif nuke is not None:
                choice = nuke
            elif sweep is not None:
                choice = sweep
            # Always leave this branch having committed to something. A cast
            # that fails puts the turn back where it started, and with the
            # fight's state unchanged the next pass makes the identical choice
            # and fails again, both HP bars frozen, until max_iters gives up.
            if choice is None or not cast_ability(g, choice):
                g.battle_menu_goto(0); g.press("a", wait=12); g.press("a", wait=12)
        actions += 1
        g.wait_for(lambda: g.rd8(BS) != 2, 60)
    return done("stuck")


def fight_arrival_encounter(g, note, frames=900):
    """Wait out a warp's arrival and fight any encounter it rolled.

    MAP_STATE_EXIT_LOADED walks the hero one tile out of an exit or portal
    in its heading (map.c's update_map()), and that move ends in on_move()
    like any other, so it can start a battle. A battle never moves the hero,
    so an arrival checked by position alone reads as clean while the fight
    waits to swallow the next input. Returns the fight's outcome, or None
    when the arrival settled without one."""
    g.wait_for(lambda: g.gs() == GS["BATTLE"] or
               (g.gs() == GS["WORLD_MAP"] and g.ms() == MS["WAITING"]), frames)
    if g.gs() != GS["BATTLE"]:
        return None
    outcome = resolve_battle(g, may_flee=True)
    g.wait_map_idle(900)
    log(f"  random encounter on arrival ({note}): {outcome}")
    if outcome in ("victory", "fled"):
        field_heal(g)
    return outcome


def run_path(g, f, cur_map, path, note=""):
    """Replay a computed direction list. `f`/`cur_map` are the Floor and map
    letter the path was planned on, so this can tell in advance, from the
    direction alone, when a step is walking onto a registered exit tile:
    those trigger a fade-out/reposition/fade-in sequence, not an ordinary
    move, and the game ignores input during it. Every step also has to
    allow for a random encounter, which on_move() rolls at the end of every
    completed move, an exit's automatic step out included. A battle never
    moves the hero, so after one the live position says whether this step
    moved or the fight was already under way from an earlier arrival; the
    step is taken again in that case. step()'s own "did movement start"
    check only has a 12-frame window and can miss a move that actually
    happened right as an earlier transition finished settling, so an
    ordinary move is reconciled against the live position rather than
    trusted blindly too. Returns True on a clean finish, False on an
    unexpected wall or position mismatch, "death" if a random encounter was
    lost, or "next_floor" if the path crossed a floor-boundary exit
    (f.path() never plans one of these, so seeing it here means the map
    model and the live game have diverged)."""
    pos = list(g.pos())
    for d in path:
        dx, dy = DIRS_XY[d]
        entering = (pos[0] + dx, pos[1] + dy)
        exit_ = f.exit_by_src.get((cur_map, entering[0], entering[1]))
        crossing = exit_ is not None and not f.is_door_closed(cur_map, entering[0], entering[1])

        for _ in range(3):
            ok = g.step(d)
            g.wait_for(lambda: g.gs() == GS["BATTLE"] or
                       (g.gs() == GS["WORLD_MAP"] and g.ms() == MS["WAITING"]), 400)

            if g.gs() == GS["WORLD_MAP"] and g.ms() in (MS["TEXTBOX"], MS["TEXTBOX_OPEN"]):
                # A plain on-move textbox -- not a sign, not a battle -- can
                # show the moment a step lands on the tile that triggers it
                # (floor1.c's on_move() does this for the stairs warning at
                # (12,4): the move completes, then the box opens on top of
                # it) or block the very next step if it is still open when
                # that one is attempted. Dismiss it blind --
                # helpers.read_textbox() would OCR the page properly, but
                # this module can't import helpers, which imports this one; a
                # script wanting the actual text reads it as a deliberate
                # step of its own -- and only retry the step if it never
                # actually landed: retrying one that already did overshoots
                # by a tile.
                for _ in range(90):
                    if g.ms() not in (MS["TEXTBOX"], MS["TEXTBOX_OPEN"]):
                        break
                    g.press("a", wait=10)
                g.wait_map_idle(300)
                log(f"  textbox at {g.pos()} ({note}); dismissed")
                if g.pos() != entering:
                    ok = g.step(d)
                    g.wait_for(lambda: g.gs() == GS["BATTLE"] or
                               (g.gs() == GS["WORLD_MAP"] and g.ms() == MS["WAITING"]), 400)

            if g.gs() != GS["BATTLE"]:
                break
            outcome = resolve_battle(g, may_flee=True)
            g.wait_map_idle(900)
            log(f"  random encounter en route to {entering} ({note}): {outcome}")
            if outcome not in ("victory", "fled"):
                return outcome
            field_heal(g)
            if g.pos() != tuple(pos):
                break
            # The fight began before this step moved at all -- rolled at the
            # end of an earlier arrival that was only checked by position --
            # and the step's input went to the battle menu. That covers every
            # encounter that seems to land on a live exit: map.c dispatches
            # the exit before on_move() rolls one, so a step onto it warps
            # rather than fights. Take the step again.
            log(f"  that fight began before step {d} moved; stepping again")

        live = g.pos()

        if crossing and not ok and live == tuple(pos):
            # Predicted a crossing from the map model, but the live game
            # blocked the step outright (a door the model still thinks is
            # open, most often -- state it tracked from an earlier open
            # that something since undid, like a death resetting the
            # floor). Report the real wall, don't wait out a warp that
            # never started.
            log(f"  ! step {d} did not move at {live} ({note}) - wall where none expected "
                f"(map model expected a crossing at {entering}; door state is stale)")
            return False

        if crossing:
            tm, tx, ty, heading = exit_
            outcome = fight_arrival_encounter(g, f"{note}, through {cur_map}{entering}")
            if outcome not in (None, "victory", "fled"):
                return outcome
            g.tick(10)
            live = g.pos()
            if tm is None:
                log(f"  ! step {d} at {entering} crossed an unplanned floor exit ({note})")
                return "next_floor"
            dest = (tx, ty)
            if live != dest:
                log(f"  ! after crossing {cur_map}{entering} -> {tm}{dest} ({note}), actually at {live}")
                return False
            log(f"  crossed internal exit at {cur_map}{entering} -> {tm}{dest} en route ({note})")
            cur_map = tm
            pos = [tx, ty]
            continue

        if live == entering:
            pos = list(entering)
            continue
        if not ok and live == tuple(pos):
            log(f"  ! step {d} did not move at {live} ({note}) - wall where none expected")
            return False
        log(f"  ! step {d} from {tuple(pos)} landed at {live}, not {entering} ({note})")
        return False
    return True


def cross_exit(g, f, cur_map, exit_key, dest_map, dest_pos, note="", cross_floor=False):
    """Walk to and step onto a registered exit tile, then wait for the map to
    settle on the far side, fighting any encounter the arrival rolled, and
    verify position."""
    path = f.path_to_exit(cur_map, g.pos(), exit_key)
    if path is None:
        log(f"  ! no path to exit {exit_key} ({note})")
        return False
    ok = run_path(g, f, cur_map, path[:-1], note)
    if ok is not True:
        log(f"  ! cross_exit {exit_key} ({note}) approach did not complete cleanly: {ok!r}")
        return False
    g.wait_map_idle(300)
    last = path[-1]
    g.pb.button_press(DIRBTN[DIR[last]] if isinstance(last, str) else last)
    g.tick(6)
    g.pb.button_release(DIRBTN[DIR[last]] if isinstance(last, str) else last)
    # An elite's ability grant arrives as a textbox on the next move, and a
    # crossing right after the fight is that move. Dismiss it as run_path()
    # does, or the position check below waits on the near side forever.
    if g.ms() in (MS["TEXTBOX"], MS["TEXTBOX_OPEN"]):
        for _ in range(90):
            if g.ms() not in (MS["TEXTBOX"], MS["TEXTBOX_OPEN"]):
                break
            g.press("a", wait=10)
        g.wait_map_idle(300)
        log(f"  textbox at {g.pos()} ({note}, crossing {exit_key}); dismissed")
    outcome = fight_arrival_encounter(g, f"{note}, through {exit_key}",
                                      frames=900 if cross_floor else 400)
    if outcome not in (None, "victory", "fled"):
        log(f"  ! cross_exit {exit_key} ({note}): lost the fight on arrival: {outcome}")
        return False
    g.tick(10)
    pos = g.pos()
    if pos != tuple(dest_pos):
        log(f"  ! after crossing {exit_key} ({note}), at {pos}, expected {dest_pos}")
        return False
    log(f"  crossed {exit_key} -> {dest_map}{dest_pos} OK ({note})")
    return True


def dismiss_after_win(g):
    """Dismiss any textbox a won fight leaves over the map. resolve_battle()
    only waits for the map itself, and a "defeated!" line or a door opening
    in a victory callback sits on top of it."""
    for _ in range(40):
        if g.gs() == GS["WORLD_MAP"] and g.ms() == MS["WAITING"]:
            break
        if g.ms() in (MS["TEXTBOX"], MS["TEXTBOX_OPEN"]):
            g.tick(30); g.press("a", wait=10)
        else:
            g.tick(10)
