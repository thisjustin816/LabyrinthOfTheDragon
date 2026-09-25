#pragma bank 4

#include <gb/gb.h>
#include <gb/cgb.h>
#include <rand.h>
#include <stdbool.h>
#include <stdio.h>

#include "battle.h"
#include "battle.effects.h"
#include "encounter.h"
#include "player.h"
#include "monster.h"
#include "tables.h"
#include "sound.h"
#include "strings.h"

Player player = { "", CLASS_TEST };
const Ability *class_abilities[6];
const Ability *player_abilities[6];
uint8_t player_num_abilities = 0;

const Ability null_ability = { 0 };

/**
 * Used as a placeholder for abiltiies prior to implementation.
 */
static void ability_placeholder(void) {
  sprintf(battle_pre_message, "You try a thing.");
  sprintf(battle_post_message, "It doesn't work.");
}

/**
 * Updates player stats based on the given power tiers.
 * @param hp Power tier for hp.
 * @param sp Power tier for sp.
 * @param atk Power tier for atk.
 * @param def Power tier for def.
 * @param matk Power tier for matk.
 * @param mdef Power tier for mdef.
 * @param agl Power tier for agl.
 */
static void update_stats(
  PowerTier hp,
  PowerTier sp,
  PowerTier atk,
  PowerTier def,
  PowerTier matk,
  PowerTier mdef,
  PowerTier agl
) {
  player.max_hp = get_player_hp(player.level, hp);
  player.max_sp = get_player_sp(player.level, sp);
  player.atk_base = get_player_atk(player.level, atk);
  player.def_base = get_player_def(player.level, def);
  player.matk_base = get_player_atk(player.level, matk);
  player.mdef_base = get_player_def(player.level, mdef);
  player.agl_base = get_agl(player.level, agl);
}

/**
 * Set while a class's basic attack resolves, so `damage_monster` can withhold
 * the aspect-vulnerability bonus.
 *
 * Issue #41: a vulnerable monster took double damage from *every* hit, and a
 * basic attack happens every turn for free. Against the zombie and the
 * gelatinous cube that doubled the druid's and sorcerer's whole damage output
 * for the fight, which is the advantage the issue describes. The 2x is now what
 * you get for spending an ability; a basic attack deals normal damage to a
 * vulnerable target and prints the normal hit line.
 *
 * Resistance still applies to basic attacks: an enemy shrugging off the wrong
 * damage type should always be felt.
 */
static bool basic_attack;

/**
 * Set by `fell_monster` when a death knight rises, and read by
 * `announce_death_knight_rise` once the player's action has finished.
 */
static bool death_knight_rose;

/**
 * Takes a monster to 0 HP. A death knight gets one chance per fight, 3 in 16,
 * to rise at a quarter of its HP instead. Every druid, fighter, monk, and
 * sorcerer attack that can kill goes through here, so none of them skips that
 * roll.
 * @param monster Monster being struck down.
 */
static void fell_monster(Monster *monster) {
  monster->target_hp = 0;
  if (
    monster->type != MONSTER_DEATHKNIGHT ||
    (monster->parameter & DEATH_KNIGHT_REVIVE_USED)
  )
    return;
  monster->parameter |= DEATH_KNIGHT_REVIVE_USED;
  if (d16() < 3) {
    monster->target_hp = monster->max_hp / 4;
    death_knight_rose = true;
  }
}

/**
 * Replaces the action's result line with the death knight's rise, if the action
 * caused one. It runs after the whole action because area attacks skip their
 * own line and Wild Magic writes its outcome after the damage, and either would
 * hide the rise.
 */
static void announce_death_knight_rise(void) {
  if (!death_knight_rose)
    return;
  death_knight_rose = false;
  sprintf(battle_post_message, str_player_deathknight_revive);
  skip_post_message = false;
}

/**
 * Applies damage to the target monster. Takes immunities, etc. into account and
 * handles battle result messages.
 * @param base_damage Base damage for the attack.
 * @param type Aspect for the damage.
 * @return Whether the blow landed: false when there is no target, or the target
 *   is immune or phases out of it. A phase plays the miss sound, so a caller
 *   plays its hit sound only for a blow that landed.
 */
static bool damage_monster(uint16_t base_damage, DamageAspect type) {
  Monster *monster = encounter.target;

  if (!monster)
    return false;

  if (monster->aspect_immune & type) {
    sprintf(battle_post_message, str_player_hit_immune);
    return false;
  }

  switch (monster->type) {
  case MONSTER_DISPLACER_BEAST:
    monster->parameter--;
    if (monster->parameter != 0)
      break;
    monster->parameter = monster->exp_tier > B_TIER ? 2 : 4;
    sprintf(battle_post_message, str_player_displacer_beast_phase);
    SFX_MISS;
    return false;
  }

  uint8_t roll = d16();
  uint16_t damage = calc_damage(roll, base_damage);
  bool critical = is_critical(roll);
  bool hasted = has_special(SPECIAL_HASTE);

  if (hasted)
    damage += calc_damage(d16(), base_damage);

  const bool weak = (monster->aspect_vuln & type) && !basic_attack;

  // A crit ignores resistance but still doubles on a weakness. Without the
  // doubling, a crit on a weak monster would deal less than a plain hit.
  if (critical) {
    if (weak)
      damage <<= 1;
    sprintf(battle_post_message, str_player_hit_crit, damage);
  } else if (monster->aspect_resist & type) {
    damage >>= 1;
    sprintf(battle_post_message, str_player_hit_resist, damage);
  } else if (weak) {
    damage <<= 1;
    sprintf(battle_post_message, str_player_hit_vuln, damage);
  } else {
    sprintf(battle_post_message, str_player_hit, damage);
  }

  if (monster->target_hp <= damage)
    fell_monster(monster);
  else
    monster->target_hp -= damage;

  return true;
}

/**
 * What the area attack being resolved did, for its result line: the damage
 * each monster took by slot, 0 for one it missed or couldn't hurt, and a bit
 * per slot that was standing when it struck.
 */
static uint16_t area_damage[3];
static uint8_t area_targets;

/**
 * Writes an area attack's result line: a single hit's line when one monster
 * stood, one number when every monster took the same, and each monster's
 * damage left to right otherwise.
 * @param type Aspect type for the damage.
 * @return Whether the attack hurt any monster, so the caller can pick a sound.
 */
static bool report_area_damage(DamageAspect type) {
  uint16_t dealt[3];
  uint8_t n = 0;
  uint8_t only = 0;
  bool same = true;
  bool all_immune = true;
  for (uint8_t k = 0; k < 3; k++) {
    if (!(area_targets & (1 << k)))
      continue;
    if (n && area_damage[k] != dealt[0])
      same = false;
    if (!(encounter.monsters[k].aspect_immune & type))
      all_immune = false;
    only = k;
    dealt[n++] = area_damage[k];
  }

  if (same && !dealt[0]) {
    if (all_immune)
      sprintf(battle_post_message, str_player_hit_immune);
    else
      sprintf(battle_post_message, n == 1 ? str_player_miss : str_player_miss_all);
    return false;
  }

  if (n == 1) {
    const Monster *monster = encounter.monsters + only;
    if (monster->aspect_resist & type)
      sprintf(battle_post_message, str_player_hit_resist, dealt[0]);
    else if (monster->aspect_vuln & type)
      sprintf(battle_post_message, str_player_hit_vuln, dealt[0]);
    else
      sprintf(battle_post_message, str_player_hit, dealt[0]);
  } else if (same) {
    sprintf(battle_post_message, str_player_hit_each, dealt[0]);
  } else if (n == 2) {
    sprintf(battle_post_message, str_player_hit_two, dealt[0], dealt[1]);
  } else {
    sprintf(battle_post_message, str_player_hit_three, dealt[0], dealt[1], dealt[2]);
  }
  return true;
}

/**
 * Applies damage to all active monsters in the encounter. Takes immmunities,
 * etc. into account. Does **NOT** handle battle result messages.
 * @param base_damage Base damage for the attack.
 * @param atk ATK of the attacker.
 * @param use_mdef Whether or not to use DEF or MDEF when checking attack roll.
 * @param type Aspect type for the damage.
 * @return Number of monsters hit by the attack.
 */
static uint8_t damage_all(
  uint16_t base_damage,
  uint8_t atk,
  bool use_mdef,
  DamageAspect type
) {
  uint8_t dam_roll = d16();
  uint16_t damage = calc_damage(dam_roll, base_damage);

  if (has_special(SPECIAL_HASTE))
    damage += calc_damage(d16(), base_damage);

  Monster *monster = encounter.monsters;
  uint8_t atk_roll = d256();
  uint8_t hits = 0;
  area_targets = 0;

  for (uint8_t k = 0; k < 3; k++, monster++) {
    if (!monster->active)
      continue;
    area_targets |= 1 << k;
    area_damage[k] = 0;
    if (monster->aspect_immune & type)
      continue;

    bool evaded = false;

    switch (monster->type) {
    case MONSTER_DISPLACER_BEAST:
      monster->parameter--;
      if (monster->parameter != 0)
        break;
      monster->parameter = monster->exp_tier > B_TIER ? 2 : 4;
      evaded = true;
      break;
    }

    if (evaded)
      continue;

    const uint8_t def = use_mdef ? monster->mdef : monster->def;
    if (!check_attack(atk_roll, attack_roll_player, atk, def))
      continue;

    hits++;

    uint16_t d = damage;
    if (monster->aspect_resist & type) {
      d = damage >> 1;
    } else if (monster->aspect_vuln & type) {
      d = damage << 1;
    }
    area_damage[k] = d;

    if (monster->target_hp <= d)
      fell_monster(monster);
    else
      monster->target_hp -= d;
  }

  return hits;
}

/**
 * Applies damage to all active monsters in the encounter. Cannot miss, but
 * takes immunities and resistances into account.
 * @param base_damage Base damage for the attack.
 * @param type Aspect type for the damage.
 */
static void damage_all_no_miss(uint16_t base_damage, DamageAspect type) {
  uint8_t dam_roll = d16();
  uint16_t damage = calc_damage(dam_roll, base_damage);

  if (has_special(SPECIAL_HASTE))
    damage += calc_damage(d16(), base_damage);

  Monster *monster = encounter.monsters;
  area_targets = 0;
  for (uint8_t k = 0; k < 3; k++, monster++) {
    if (!monster->active)
      continue;
    area_targets |= 1 << k;
    area_damage[k] = 0;

    if (monster->aspect_immune & type)
      continue;

    bool evaded = false;
    switch (monster->type) {
    case MONSTER_DISPLACER_BEAST:
      monster->parameter--;
      if (monster->parameter != 0)
        break;
      monster->parameter = monster->exp_tier > B_TIER ? 2 : 4;
      evaded = true;
      break;
    }

    if (evaded)
      continue;

    uint16_t d = damage;
    if (monster->aspect_resist & type)
      d = damage >> 1;
    else if (monster->aspect_vuln & type)
      d = damage << 1;
    area_damage[k] = d;

    if (monster->target_hp <= d)
      fell_monster(monster);
    else
      monster->target_hp -= d;
  }
}

/**
 * Heals the player without going over max HP.
 *
 * The amount is rolled the same way damage is (0.75x to 1.25x, mean neutral);
 * `is_critical` and `is_fumble` are documented as covering "damage / healing"
 * rolls, and the crit, fumble and full-heal messages already existed for it.
 *
 * @param hp Amount of HP to heal the player.
 * @return The HP actually restored.
 */
uint16_t heal_player(uint16_t hp) {
  if (has_special(SPECIAL_HASTE))
    hp = (hp * 3) / 2;

  const uint8_t roll = d16();
  hp = calc_damage(roll, hp);

  if (player.hp + hp > player.max_hp)
    hp = player.max_hp - player.hp;
  player.hp += hp;

  if (player.hp == player.max_hp) {
    sprintf(battle_post_message, str_player_heal_complete);
    SFX_HEAL;
  } else if (is_critical(roll)) {
    sprintf(battle_post_message, str_player_heal_crit, hp);
    SFX_HEAL;
  } else if (is_fumble(roll)) {
    sprintf(battle_post_message, str_player_heal_fumble, hp);
    SFX_HEAL;
  } else {
    PLAYER_HEAL(hp);
  }

  return hp;
}

//------------------------------------------------------------------------------
// Class: Druid
//------------------------------------------------------------------------------

static void druid_update_stats(void) {
  update_stats(
    B_TIER,
    B_TIER,
    C_TIER,
    B_TIER,
    B_TIER,
    A_TIER,
    B_TIER
  );
}

/**
 * `damage_monster` for a class's basic attack. Wrapping the call keeps the flag
 * from leaking past the early returns in the attack functions.
 * @return Whether the blow landed.
 */
static bool damage_monster_basic(uint16_t base_damage, DamageAspect type) {
  basic_attack = true;
  const bool landed = damage_monster(base_damage, type);
  basic_attack = false;
  return landed;
}

void druid_base_attack(void) {
  sprintf(battle_pre_message, str_player_poison_spray);

  Monster *target = encounter.target;
  if (!roll_attack_player(player.matk, target->mdef)) {
    PLAYER_MISS;
    return;
  }

  PowerTier damage_tier = C_TIER;

  const uint16_t base_dmg = get_player_damage(player.level, damage_tier);
  if (damage_monster_basic(base_dmg, DAMAGE_MAGICAL))
    SFX_POISON_SPRAY;
}

void druid_cure_wounds(void) {
  sprintf(battle_pre_message, str_player_cure_wounds);
  heal_player(player.max_hp / 2);
}

void druid_bark_skin(void) {
  sprintf(battle_pre_message, str_player_bark_skin);
  SKIP_POST_MSG;
  apply_def_up(
    encounter.player_status_effects, B_TIER, EFFECT_DURATION_PERPETUAL);
  apply_special(SPECIAL_BARKSKIN);
  SFX_MID_POWERUP;
}

void druid_lightning(void) {
  sprintf(battle_pre_message, str_player_lightning);

  Monster *target = encounter.target;
  if (!roll_attack_player(player.matk, target->mdef)) {
    PLAYER_MISS;
    return;
  }

  PowerTier damage_tier = A_TIER;

  const uint16_t base_dmg = get_player_damage(
    level_offset(player.level, 10), damage_tier);

  if (damage_monster(base_dmg, DAMAGE_AIR))
    SFX_MAGIC;
}

void druid_heal(void) {
  sprintf(battle_pre_message, str_player_heal);
  // The druid's heal is a full heal. heal_player rolls 0.75x to 1.25x, so ask
  // for one and a half bars: even a fumbled roll covers the whole deficit and
  // the player reads "You're fully healed!".
  heal_player(player.max_hp + (player.max_hp >> 1));
}

void druid_insect_plague(void) {
  sprintf(battle_pre_message, str_player_insect_plague);

  PowerTier tier = B_TIER;
  if (player.level > 55)
    tier = S_TIER;
  else if (player.level > 35)
    tier = A_TIER;

  const uint8_t level = level_offset(player.level, 5);
  const uint16_t base_damage = get_player_damage(level, tier);
  uint8_t hits = damage_all(base_damage, player.matk, true, DAMAGE_MAGICAL);

  if (hits == 0) {
    PLAYER_MISS_ALL;
  } else {
    report_area_damage(DAMAGE_MAGICAL);
    SFX_MAGIC;
  }
}

void druid_regen(void) {
  sprintf(battle_pre_message, str_player_regen);
  SKIP_POST_MSG;
  PowerTier tier = player.level > 55 ? S_TIER : A_TIER;
  apply_regen(
    encounter.player_status_effects, tier, EFFECT_DURATION_PERPETUAL);
  SFX_MID_POWERUP;
}

//------------------------------------------------------------------------------
// Class: Fighter
//------------------------------------------------------------------------------

void fighter_update_stats(void) {
  update_stats(
    A_TIER,
    C_TIER,
    B_TIER,
    A_TIER,
    C_TIER,
    B_TIER,
    B_TIER
  );
}

void fighter_base_attack(void) {
  sprintf(battle_pre_message, str_player_fighter_attack);

  Monster *target = encounter.target;
  if (!roll_attack_player(player.atk, target->def)) {
    PLAYER_MISS;
    return;
  }

  const uint16_t base_dmg = get_player_damage(player.level, C_TIER);
  if (damage_monster_basic(base_dmg, DAMAGE_PHYSICAL))
    SFX_MELEE_ATTACK;
}

void fighter_second_wind(void) {
  sprintf(battle_pre_message, str_player_second_wind);
  heal_player(player.max_hp / 4);
}

void fighter_action_surge(void) {
  sprintf(battle_pre_message, str_player_action_surge);

  PowerTier tier = B_TIER;
  if (player.level > 20)
    tier = A_TIER;
  if (player.level > 40)
    tier = S_TIER;

  Monster *target = encounter.target;
  const uint8_t attack_level = level_offset(player.level, 3);
  uint16_t base_dmg = get_player_damage(attack_level, tier);
  if (damage_monster(base_dmg * 2, DAMAGE_PHYSICAL))
    SFX_ACTION_SURGE;
}

void fighter_cleave(void) {
  sprintf(battle_pre_message, str_player_cleave);

  PowerTier tier = C_TIER;
  if (player.level > 20)
    tier = B_TIER;
  if (player.level > 50)
    tier = A_TIER;
  if (player.level > 55)
    tier = S_TIER;

  const uint8_t level = level_offset(player.level, -2);
  const uint16_t base_damage = get_player_damage(level, tier);
  uint8_t hits = damage_all(base_damage, player.atk, false, DAMAGE_PHYSICAL);

  if (hits == 0) {
    PLAYER_MISS_ALL;
  } else {
    report_area_damage(DAMAGE_PHYSICAL);
    SFX_MELEE_ATTACK;
  }
}

void fighter_trip_attack(void) {
  sprintf(battle_pre_message, str_player_trip_attack);

  Monster *target = encounter.target;
  if (target->special_immune & SPECIAL_TRIP) {
    sprintf(battle_post_message, str_player_hit_immune);
    SFX_FAIL;
    return;
  }

  uint8_t def = get_monster_def(level_offset(target->level, -5), C_TIER);
  if (!roll_attack_player(player.atk, def)) {
    PLAYER_MISS;
    return;
  }

  uint8_t turns = 2;
  if (player.level > 50)
    turns = 4;
  else if (player.level > 30)
    turns = 3;

  target->trip_turns = turns;
  sprintf(battle_post_message, str_player_trip_attack_hit);
  SFX_MELEE_ATTACK;
}

void fighter_menace(void) {
  sprintf(battle_pre_message, str_player_menace);
  SKIP_POST_MSG;

  PowerTier tier = A_TIER;
  uint8_t turns = 2;
  if (player.level > 30)
    turns = 3;
  if (player.level > 50) {
    turns = 4;
    tier = S_TIER;
  }

  // A roar that lands on nothing but immune targets should say so, the same
  // way a physically-immune hit does, instead of always reading as a scare
  // that worked.
  bool landed = false, immune = false;
  Monster *monster = encounter.monsters;
  for (uint8_t k = 0; k < 3; k++, monster++) {
    if (!monster->active)
      continue;
    StatusEffectResult result = apply_scared(
      monster->status_effects, tier, turns, monster->debuff_immune);
    landed |= (result == STATUS_RESULT_SUCCESS);
    immune |= (result == STATUS_RESULT_IMMUNE);
  }

  if (!landed && immune) {
    sprintf(battle_post_message, str_player_hit_immune);
    skip_post_message = false;
    SFX_FAIL;
  } else {
    SFX_MAGIC;
  }
}

void fighter_indomitable(void) {
  sprintf(battle_pre_message, str_player_indomitable);
  SKIP_POST_MSG;
  player.aspect_resist = 0xFF;
  SFX_MID_POWERUP;
}

//------------------------------------------------------------------------------
// Class: Monk
//------------------------------------------------------------------------------

void monk_update_stats(void) {
  update_stats(
    B_TIER,
    B_TIER,
    B_TIER,
    B_TIER,
    C_TIER,
    B_TIER,
    A_TIER
  );
}

void monk_base_attack(void) {
  sprintf(battle_pre_message, str_player_monk_attack);

  Monster *target = encounter.target;
  if (!roll_attack_player(player.atk + player.agl, target->def)) {
    PLAYER_MISS;
    return;
  }

  const uint16_t base_dmg = get_player_damage(player.level, B_TIER);
  if (damage_monster_basic(base_dmg, DAMAGE_PHYSICAL))
    SFX_MONK_STRIKE;
}

void monk_evasion(void) {
  sprintf(battle_pre_message, str_player_monk_evasion);
  SKIP_POST_MSG;

  player.special_flags |= SPECIAL_EVASION;

  PowerTier agl_up_tier = C_TIER;
  uint8_t agl_up_duration = 2;

  if (player.level > 35) {
    agl_up_tier = B_TIER;
    agl_up_duration = 3;
  }

  if (player.level > 54) {
    agl_up_tier = A_TIER;
  }

  apply_agl_up(encounter.player_status_effects, agl_up_tier, agl_up_duration);
  SFX_MID_POWERUP;
}

void monk_open_palm(void) {
  sprintf(battle_pre_message, str_player_monk_open_palm);

  Monster *target = encounter.target;
  uint8_t atk = player.atk + player.agl;

  if (!roll_attack_player(atk, target->def)) {
    PLAYER_MISS;
    return;
  }

  PowerTier damage_tier = B_TIER;
  if (player.level >= 53)
    damage_tier = S_TIER;
  else if (player.level >= 30)
    damage_tier = A_TIER;

  uint8_t trip_chance = 2;
  if (player.level >= 53)
    trip_chance = 4;
  else if (player.level > 30)
    trip_chance = 3;

  const bool trips =
    d8() < trip_chance && !(target->special_immune & SPECIAL_TRIP);

  uint8_t attack_level = level_offset(player.level, player.agl);
  const uint16_t base_dmg = get_player_damage(attack_level, damage_tier);
  const bool landed = damage_monster(base_dmg, DAMAGE_PHYSICAL);
  if (landed)
    SFX_MONK_STRIKE;

  // Only a palm that lands and leaves its target standing trips it. A death
  // knight rising from the blow stays on its feet as well: the rise line
  // replaces the whole result, so the trip would go unsaid.
  if (!trips || !landed || !target->target_hp || death_knight_rose)
    return;

  target->trip_turns = player.level > 30 ? 3 : 2;

  // The trip line goes under the damage line. That takes two of the text box's
  // four rows, or three when the target resists, and a trip line that would not
  // fit below it gets a page of its own.
  char *end = battle_post_message;
  uint8_t rows = 1;
  for (; *end; end++) {
    if (*end == '\n')
      rows++;
  }
  *end++ = rows > 2 ? '\f' : '\n';
  sprintf(end, str_player_monk_open_palm_trip, target->name, target->id);
}

void monk_still_mind(void) {
  StatusEffectInstance *effect = encounter.player_status_effects;
  for (uint8_t k = 0; k < MAX_ACTIVE_EFFECTS; k++, effect++) {
    if (!effect->active)
      continue;
    if (is_debuff(effect->effect))
      effect->active = false;
  }
  // The stats and flags are otherwise only rebuilt at the start of the
  // player's own turn; left stale, a monster acting before then still meets
  // the lowered stats and reads a debuff this just cleared (floor 8's mind
  // flayer: Extract Brain off a confusion Still Mind already cured).
  refresh_player_stats();

  // The immunity holds for the rest of the battle: the dragon carries three
  // fright actions and a scared player rolls to flee every turn, so a cleanse
  // alone would be undone before the monk could answer. reset_encounter()
  // clears it.
  player.debuff_immune |= FLAG_DEBUFF_SCARED;

  sprintf(battle_pre_message, str_player_monk_still_mind);
  sprintf(battle_post_message, str_player_monk_still_mind_post);
  SFX_MID_POWERUP;
}

void monk_flurry(void) {
  sprintf(battle_pre_message, str_player_monk_flurry_of_blows);

  Monster *target = encounter.target;
  if (!roll_attack_player(player.atk + player.agl, target->def)) {
    PLAYER_MISS;
    return;
  }

  uint8_t attacks = 2;
  if (player.level > 50)
    attacks = 3;
  if (player.level > 56)
    attacks = 4;

  PowerTier damage_tier = B_TIER;
  if (player.level >= 53)
    damage_tier = S_TIER;
  else if (player.level >= 30)
    damage_tier = A_TIER;

  uint8_t attack_level = level_offset(player.level, player.agl);
  uint16_t base_dmg = get_player_damage(attack_level, damage_tier);
  base_dmg *= attacks;

  if (damage_monster(base_dmg, DAMAGE_PHYSICAL))
    SFX_MONK_STRIKE;
}

void monk_diamond_body(void) {
  sprintf(battle_pre_message, str_player_monk_diamond_body);
  SKIP_POST_MSG;

  PowerTier def_up_tier = B_TIER;
  if (player.level > 50)
    def_up_tier = A_TIER;

  player.aspect_resist = DAMAGE_PHYSICAL | DAMAGE_MAGICAL;
  apply_def_up(
    encounter.player_status_effects, def_up_tier, EFFECT_DURATION_PERPETUAL);
  SFX_MID_POWERUP;
}

void monk_quivering_palm(void) {
  sprintf(battle_pre_message, str_player_monk_quivering_palm);

  Monster *target = encounter.target;
  if (!roll_attack_player(player.atk + player.agl, target->def)) {
    PLAYER_MISS;
    return;
  }

  if (!(target->special_immune & SPECIAL_INSTANT_KILL)) {
    uint8_t kill_chance = 1;
    if (player.level > 50)
      kill_chance = 2;
    if (player.level > 56)
      kill_chance = 3;

    if (d8() < kill_chance) {
      sprintf(battle_post_message, str_player_monk_quivering_kill);
      fell_monster(encounter.target);
      SFX_SPECIAL_CRIT;
      return;
    }
  }

  uint8_t attack_level = level_offset(player.level, player.agl);
  uint16_t base_dmg = get_player_damage(attack_level, S_TIER);
  base_dmg *= 2;

  if (damage_monster(base_dmg, DAMAGE_PHYSICAL))
    SFX_MONK_STRIKE;
}

//------------------------------------------------------------------------------
// Class: Sorcerer
//------------------------------------------------------------------------------

void sorcerer_update_stats(void) {
  update_stats(
    C_TIER,
    A_TIER,
    C_TIER,
    C_TIER,
    A_TIER,
    B_TIER,
    A_TIER
  );
}

void sorcerer_base_attack(void) {
  sprintf(battle_pre_message, str_player_sorc_magic_missile_one);
  const PowerTier tier = B_TIER;
  const uint8_t level = level_offset(player.level, 1);
  if (damage_monster_basic(get_player_damage(level, tier), DAMAGE_MAGICAL))
    SFX_MAGIC_MISSILE;
}

void sorcerer_darkness(void) {
  sprintf(battle_pre_message, str_player_sorc_darkness);
  SKIP_POST_MSG;

  uint8_t turns = 3;
  if (player.level >= 30)
    turns = 4;
  if (player.level >= 50)
    turns = 5;

  PowerTier tier = B_TIER;
  if (player.level >= 45)
    tier = A_TIER;

  // As with fighter_menace: say so when every target shrugged it off immune,
  // rather than always reading as a blind that landed.
  bool landed = false, immune = false;
  Monster *monster = encounter.monsters;
  for (uint8_t k = 0; k < 3; k++, monster++) {
    if (!monster->active)
      continue;
    StatusEffectResult result = apply_blind(
      monster->status_effects, tier, turns, monster->debuff_immune);
    landed |= (result == STATUS_RESULT_SUCCESS);
    immune |= (result == STATUS_RESULT_IMMUNE);
  }

  if (!landed && immune) {
    sprintf(battle_post_message, str_player_hit_immune);
    skip_post_message = false;
    SFX_FAIL;
  } else {
    SFX_MAGIC;
  }
}

void sorcerer_fireball(void) {
  sprintf(battle_pre_message, str_player_sorc_fireball);

  Monster *monster = encounter.monsters;
  uint8_t mdef = monster->mdef;

  for (uint8_t k = 0; k < 3; k++, monster++) {
    if (!monster->active)
      continue;
    if (monster->mdef < mdef)
      mdef = monster->mdef;
  }

  PowerTier tier = C_TIER;
  if (player.level >= 50)
    tier = B_TIER;

  uint16_t damage = get_player_damage(player.level, tier);

  if (!roll_attack_player(player.matk, mdef))
    damage /= 2;

  damage_all_no_miss(damage, DAMAGE_FIRE);
  if (report_area_damage(DAMAGE_FIRE))
    SFX_MAGIC;
  else
    SFX_MISS;
}

void sorcerer_haste(void) {
  sprintf(battle_pre_message, str_player_sorc_haste);
  SKIP_POST_MSG;
  apply_haste(
    encounter.player_status_effects, B_TIER, EFFECT_DURATION_PERPETUAL);
  SFX_MID_POWERUP;
}

/**
 * Brings down Sleetstorm's ice for the rest of the battle. When every monster
 * there is immune to it, the storm says so instead, as Darkness and Menace do.
 * @return Whether any monster in the fight can slip on the ice.
 */
static bool sleetstorm(void) {
  sprintf(battle_pre_message, str_player_sorc_sleetstorm);

  bool takes_hold = false;
  Monster *monster = encounter.monsters;
  for (uint8_t k = 0; k < 3; k++, monster++) {
    if (monster->active && !(monster->special_immune & SPECIAL_SLEET_STORM))
      takes_hold = true;
  }

  if (!takes_hold) {
    sprintf(battle_post_message, str_player_hit_immune);
    SFX_FAIL;
    return false;
  }

  SKIP_POST_MSG;
  SFX_MAGIC;
  player.special_flags |= SPECIAL_SLEET_STORM;
  return true;
}

void sorcerer_sleetstorm(void) {
  sleetstorm();
}

void sorcerer_disintegrate(void) {
  sprintf(battle_pre_message, str_player_sorc_disintegrate);

  Monster *target = encounter.target;
  if (!roll_attack_player(player.matk + 10, target->mdef)) {
    PLAYER_MISS;
    return;
  }

  Monster *monster = encounter.target;
  if(!(monster->special_immune & SPECIAL_INSTANT_KILL)) {
    uint8_t kill_chance = 2;
    if (player.level > 40)
      kill_chance = 3;
    if (player.level > 50)
      kill_chance = 4;

    if (d8() < kill_chance) {
      sprintf(battle_post_message, str_player_sorc_disintegrate_kill);
      fell_monster(encounter.target);
      SFX_SPECIAL_CRIT;
      return;
    }
  }

  uint8_t attack_level = level_offset(player.level, 5);
  uint16_t base_dmg = get_player_damage(attack_level, S_TIER);
  base_dmg *= 2;
  if (damage_monster(base_dmg, DAMAGE_MAGICAL))
    SFX_MAGIC;
}

// What a wild magic surge turned into. Fireball and sleetstorm overwrite the
// pre-message on their way through and suppress their own post message, so the
// surge has to report them itself; HP changes and landed debuffs show up on the
// monsters and need no line.
#define WILD_MAGIC_FIREBALL 1
#define WILD_MAGIC_SLEETSTORM 2
#define WILD_MAGIC_HP 4
#define WILD_MAGIC_DEBUFF_LANDED 8
#define WILD_MAGIC_IMMUNE 16

/**
 * @return The outcome bit for one of Wild Magic's debuff attempts.
 */
static uint8_t wild_magic_debuff(StatusEffectResult result) {
  if (result == STATUS_RESULT_SUCCESS)
    return WILD_MAGIC_DEBUFF_LANDED;
  if (result == STATUS_RESULT_IMMUNE)
    return WILD_MAGIC_IMMUNE;
  return 0;
}

void sorcerer_wild_magic(void) {
  Monster *monster = encounter.monsters;
  uint8_t outcome = 0;

  for (uint8_t k = 0; k < 3; k++, monster++) {
    // A monster an earlier roll's fireball just felled stays down: its HP
    // rolls would otherwise bring it back.
    if (!monster->active || !monster->target_hp)
      continue;

    uint8_t roll = d8();

    if (roll == 0) {
      monster->target_hp = 1;
      outcome |= WILD_MAGIC_HP;
    } else if (roll == 1) {
      monster->target_hp = monster->max_hp - 1;
      outcome |= WILD_MAGIC_HP;
    } else if (roll < 4) {
      outcome |= wild_magic_debuff(apply_agl_down(
        monster->status_effects, A_TIER, 10, monster->debuff_immune));
      outcome |= wild_magic_debuff(apply_def_down(
        monster->status_effects, A_TIER, 10, monster->debuff_immune));
      outcome |= wild_magic_debuff(apply_atk_down(
        monster->status_effects, A_TIER, 10, monster->debuff_immune));
    } else if (roll < 6) {
      outcome |= wild_magic_debuff(apply_confused(
        monster->status_effects, A_TIER, 10, monster->debuff_immune));
      outcome |= wild_magic_debuff(apply_blind(
        monster->status_effects, A_TIER, 10, monster->debuff_immune));
    } else if (roll == 6) {
      sorcerer_fireball();
      outcome |= WILD_MAGIC_FIREBALL;
    } else {
      outcome |= sleetstorm() ? WILD_MAGIC_SLEETSTORM : WILD_MAGIC_IMMUNE;
    }
  }

  sprintf(battle_pre_message, str_player_sorc_wild_magic);

  // Fireball and sleetstorm set the skip flag and a sound on their way through,
  // so every outcome sets both again.
  skip_post_message = false;
  if (outcome & WILD_MAGIC_FIREBALL) {
    sprintf(battle_post_message, str_player_sorc_wild_magic_fireball);
    SFX_MAGIC;
  } else if (outcome & WILD_MAGIC_SLEETSTORM) {
    sprintf(battle_post_message, str_player_sorc_wild_magic_sleetstorm);
    SFX_MAGIC;
  } else if (outcome & (WILD_MAGIC_HP | WILD_MAGIC_DEBUFF_LANDED)) {
    SKIP_POST_MSG;
    SFX_MAGIC;
  } else if (outcome & WILD_MAGIC_IMMUNE) {
    // The storm did nothing but meet immunities: say so, as Darkness and
    // Menace do, rather than fizzling.
    sprintf(battle_post_message, str_player_hit_immune);
    SFX_FAIL;
  } else {
    sprintf(battle_post_message, str_player_sorc_wild_magic_fizzle);
    SFX_FAIL;
  }
}

//------------------------------------------------------------------------------
// Class: Test Class
//------------------------------------------------------------------------------

void test_class_update_stats(void) {
  update_stats(
    S_TIER,
    S_TIER,
    S_TIER,
    S_TIER,
    S_TIER,
    S_TIER,
    S_TIER
  );
}

void test_class_base_attack(void) {
  ability_placeholder();
}

void test_class_ability0(void) {
  sprintf(battle_pre_message, "Attacking all\x60");
  const uint8_t base_damage = get_player_damage(player.level, B_TIER);
  const uint8_t hits = damage_all(base_damage, player.atk, false, DAMAGE_PHYSICAL);

  if (!hits) {
    PLAYER_MISS_ALL;
  } else {
    sprintf(battle_post_message, "Damage Applied.");
  }
}

void test_class_ability1(void) {
  sprintf(battle_pre_message, "(De)buffing\x60");
  SKIP_POST_MSG;

  // player.hp = 1;
  // player.sp = 1;

  apply_poison(encounter.player_status_effects, C_TIER, 10, 0);
  apply_def_down(encounter.player_status_effects, C_TIER, 10, 0);
  apply_atk_down(encounter.player_status_effects, C_TIER, 10, 0);
  apply_agl_down(encounter.player_status_effects, C_TIER, 10, 0);

  // player.hp = 1;

  // Monster *monster = encounter.monsters;
  // for (uint8_t k = 0; k < 3; k++, monster++) {
  //   if (!monster->active)
  //     continue;
  //   StatusEffectInstance *effects = monster->status_effects;
  //   apply_regen(effects, C_TIER, 6, monster->debuff_immune);
  // }
}

void test_class_ability2(void) {
  sprintf(battle_pre_message, "SUPERKILL!!!");
  SKIP_POST_MSG;
  Monster *monster = encounter.monsters;
  for (uint8_t k = 0; k < 3; k++, monster++) {
    if (!monster->active)
      continue;
    monster->target_hp = 0;
  }
}

void test_class_ability3(void) {
  ability_placeholder();
}

void test_class_ability4(void) {
  ability_placeholder();
}

void test_class_ability5(void) {
  ability_placeholder();
}

//------------------------------------------------------------------------------
// Common functions
//------------------------------------------------------------------------------

/**
 * Updates a player's stats based on their current class and level.
 */
void update_player_stats(void) {
  switch (player.player_class) {
  case CLASS_DRUID:
    druid_update_stats();
    break;
  case CLASS_FIGHTER:
    fighter_update_stats();
    break;
  case CLASS_MONK:
    monk_update_stats();
    break;
  case CLASS_SORCERER:
    sorcerer_update_stats();
    break;
  case CLASS_TEST:
    test_class_update_stats();
    break;
  }
}

/**
 * Sets class abilities based on the current player class.
 */
void set_class_abilities(void) {
  switch (player.player_class) {
  case CLASS_DRUID:
    class_abilities[0] = &druid0;
    class_abilities[1] = &druid1;
    class_abilities[2] = &druid2;
    class_abilities[3] = &druid3;
    class_abilities[4] = &druid4;
    class_abilities[5] = &druid5;
    break;
  case CLASS_FIGHTER:
    class_abilities[0] = &fighter0;
    class_abilities[1] = &fighter1;
    class_abilities[2] = &fighter2;
    class_abilities[3] = &fighter3;
    class_abilities[4] = &fighter4;
    class_abilities[5] = &fighter5;
    break;
  case CLASS_MONK:
    class_abilities[0] = &monk0;
    class_abilities[1] = &monk1;
    class_abilities[2] = &monk2;
    class_abilities[3] = &monk3;
    class_abilities[4] = &monk4;
    class_abilities[5] = &monk5;
    break;
  case CLASS_SORCERER:
    class_abilities[0] = &sorcerer0;
    class_abilities[1] = &sorcerer1;
    class_abilities[2] = &sorcerer2;
    class_abilities[3] = &sorcerer3;
    class_abilities[4] = &sorcerer4;
    class_abilities[5] = &sorcerer5;
    break;
  case CLASS_TEST:
    class_abilities[0] = &test_class0;
    class_abilities[1] = &test_class1;
    class_abilities[2] = &test_class2;
    class_abilities[3] = &test_class3;
    class_abilities[4] = &test_class4;
    class_abilities[5] = &test_class5;
    break;
  }
}

/**
 * Sets abilities based on the player's current class.
 */
void set_player_abilities(void) {
  uint8_t flags = player.ability_flags;
  player_num_abilities = 0;

  for (uint8_t k = 0; k < MAX_ABILITIES; k++, flags >>= 1) {
    player_abilities[player_num_abilities] = &null_ability;
    if (flags & 1)
      player_abilities[player_num_abilities++] = class_abilities[k];
  }
}

// -----------------------------------------------------------------------------

void grant_ability(AbilityFlag flag) BANKED {
  player.ability_flags |= flag;
  set_player_abilities();
}

char *get_druid_grant_message(AbilityFlag flag) {
  switch (flag) {
  case ABILITY_1:
    return str_gain_ability_druid1;
  case ABILITY_2:
    return str_gain_ability_druid2;
  case ABILITY_3:
    return str_gain_ability_druid3;
  case ABILITY_4:
    return str_gain_ability_druid4;
  default:
    return str_gain_ability_druid5;
  }
}

char *get_fighter_grant_message(AbilityFlag flag) {
  switch (flag) {
  case ABILITY_1:
    return str_gain_ability_fighter1;
  case ABILITY_2:
    return str_gain_ability_fighter2;
  case ABILITY_3:
    return str_gain_ability_fighter3;
  case ABILITY_4:
    return str_gain_ability_fighter4;
  default:
    return str_gain_ability_fighter5;
  }
}

char *get_monk_grant_message(AbilityFlag flag) {
  switch (flag) {
  case ABILITY_1:
    return str_gain_ability_monk1;
  case ABILITY_2:
    return str_gain_ability_monk2;
  case ABILITY_3:
    return str_gain_ability_monk3;
  case ABILITY_4:
    return str_gain_ability_monk4;
  default:
    return str_gain_ability_monk5;
  }
}

char *get_sorcerer_grant_message(AbilityFlag flag) {
  switch (flag) {
  case ABILITY_1:
    return str_gain_ability_sorcerer1;
  case ABILITY_2:
    return str_gain_ability_sorcerer2;
  case ABILITY_3:
    return str_gain_ability_sorcerer3;
  case ABILITY_4:
    return str_gain_ability_sorcerer4;
  default:
    return str_gain_ability_sorcerer5;
  }
}

const char *get_grant_message(AbilityFlag flag) BANKED {
  switch (player.player_class) {
  case CLASS_DRUID:
    return get_druid_grant_message(flag);
  case CLASS_FIGHTER:
    return get_fighter_grant_message(flag);
  case CLASS_MONK:
    return get_monk_grant_message(flag);
  default:
    return get_sorcerer_grant_message(flag);
  }
}

/**
 * @return EXP needed for the level after `level`, or 0xFFFF at the cap.
 */
static uint16_t exp_for_next_level(uint8_t level) {
  return level < MAX_PLAYER_LEVEL ? get_exp(level + 1) : 0xFFFF;
}

void set_player_level(uint8_t level) BANKED {
  if (level > MAX_PLAYER_LEVEL)
    level = MAX_PLAYER_LEVEL;
  player.level = level;
  player.exp = get_exp(player.level);
  player.next_level_exp = exp_for_next_level(player.level);
  update_player_stats();
  full_heal_player();
}

void init_player(PlayerClass player_class) BANKED {
  player.player_class = player_class;

  switch (player.player_class) {
  case CLASS_DRUID:
    sprintf(player.name, "Lyra");
    break;
  case CLASS_FIGHTER:
    sprintf(player.name, "Deneth");
    break;
  case CLASS_MONK:
    sprintf(player.name, "Ken");
    break;
  case CLASS_SORCERER:
    sprintf(player.name, "Tyrion");
    break;
  }

  player.has_torch = false;
  player.torch_gauge = 0;
  player.torch_color = FLAME_NONE;
  player.magic_keys = 0;
  player.got_magic_key = false;
  clear_inventory();

  set_class_abilities();
  player.ability_flags = 0;

  grant_ability(ABILITY_0);
  set_player_level(4);
  reset_player_stats();

  player.message_speed = AUTO_PAGE_MED;
  player.aspect_immune = 0;
  player.aspect_resist = 0;
  player.aspect_vuln = 0;
}

bool level_up(uint16_t xp) BANKED {
  bool level_up = false;

  // Saturate rather than wrap: level 99 needs 65118 EXP.
  player.exp = (player.exp > 0xFFFF - xp) ? 0xFFFF : player.exp + xp;

  // Stop at the cap. get_exp() clamps its argument, so the requirement stops
  // rising at level 99, and without this check the loop would never end.
  while (player.level < MAX_PLAYER_LEVEL && player.exp >= player.next_level_exp) {
    level_up = true;
    player.level++;
    player.next_level_exp = exp_for_next_level(player.level);
  }

  if (level_up) {
    update_player_stats();
    full_heal_player();
  }

  return level_up;
}

void player_base_attack(void) BANKED {
  switch (player.player_class) {
  case CLASS_DRUID:
    druid_base_attack();
    break;
  case CLASS_FIGHTER:
    fighter_base_attack();
    break;
  case CLASS_MONK:
    monk_base_attack();
    break;
  case CLASS_SORCERER:
    sorcerer_base_attack();
    break;
  case CLASS_TEST:
    test_class_base_attack();
    break;
  }
  announce_death_knight_rise();
}

void player_use_ability(const Ability *ability) BANKED {
  ability->execute();
  announce_death_knight_rise();
}
