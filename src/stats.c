#pragma bank 5

#include "stats.h"
#include "player.h"

/**
 * Clamps a level to the 1..MAX_PLAYER_LEVEL range the stat tables cover.
 *
 * Every accessor below indexes `[level - 1]`, so a level of 0 reads the entry
 * before its row. That is how issue #78 produced a kobold hitting for 3031: a
 * MONSTER_LAYOUT_2 encounter entry that only declared one monster left the
 * second monster zeroed, and MonsterType 0 is MONSTER_KOBOLD at level 0. PR #79
 * fixes that particular entry, but clamping here means a malformed entry can
 * never again read outside the tables.
 */
static uint8_t clamp_level(uint8_t level) {
  if (level < 1)
    return 1;
  if (level > MAX_PLAYER_LEVEL)
    return MAX_PLAYER_LEVEL;
  return level;
}

/**
 * Masks a tier down to the 4 rows the stat tables have.
 */
static uint8_t clamp_tier(PowerTier tier) {
  return ((uint8_t)tier) & 0x03;
}

uint16_t get_exp(uint8_t level) BANKED {
  return exp_by_level[clamp_level(level) - 1];
}

uint16_t get_monster_exp(uint8_t level, PowerTier tier) BANKED {
  return monster_exp[clamp_tier(tier)][clamp_level(level) - 1];
}

uint8_t get_agl(uint8_t level, PowerTier tier) BANKED {
  return agl[clamp_tier(tier)][clamp_level(level) - 1];
}

uint16_t get_player_hp(uint8_t level, PowerTier tier) BANKED {
  return player_hp[clamp_tier(tier)][clamp_level(level) - 1];
}

uint8_t get_player_sp(uint8_t level, PowerTier tier) BANKED {
  return player_sp[clamp_tier(tier)][clamp_level(level) - 1];
}

uint8_t get_player_def(uint8_t level, PowerTier tier) BANKED {
  return player_def[clamp_tier(tier)][clamp_level(level) - 1];
}

uint8_t get_player_atk(uint8_t level, PowerTier tier) BANKED {
  return player_atk[clamp_tier(tier)][clamp_level(level) - 1];
}

uint16_t get_player_damage(uint8_t level, PowerTier tier) BANKED {
  return player_dmg[clamp_tier(tier)][clamp_level(level) - 1];
}

uint16_t get_monster_hp(uint8_t level, PowerTier tier) BANKED {
  return monster_hp[clamp_tier(tier)][clamp_level(level) - 1];
}

uint8_t get_monster_def(uint8_t level, PowerTier tier) BANKED {
  return monster_def[clamp_tier(tier)][clamp_level(level) - 1];
}

uint8_t get_monster_atk(uint8_t level, PowerTier tier) BANKED {
  return monster_atk[clamp_tier(tier)][clamp_level(level) - 1];
}

uint16_t get_monster_dmg(uint8_t level, PowerTier tier) BANKED {
  return monster_dmg[clamp_tier(tier)][clamp_level(level) - 1];
}

uint16_t get_player_heal(uint8_t level, PowerTier tier) BANKED {
  return player_heal[clamp_tier(tier)][clamp_level(level) - 1];
}

bool check_attack(
  uint8_t d256_roll,
  uint8_t *table,
  uint8_t atk,
  uint8_t def
 ) BANKED {
  // Compute in 16 bits: a buffed ATK against a weak DEF can differ by more
  // than 127, which an int8_t would flip negative.
  int16_t delta = (int16_t)atk - (int16_t)def;
  if (delta <= -32)
    return d256_roll < table[0];
  if (delta >= 32)
    return d256_roll < table[64];
  return d256_roll < table[(uint8_t)(delta + 32)];
}

bool roll_attack_monster(uint8_t atk, uint8_t def) BANKED {
  return check_attack(d256(), attack_roll_monster, atk, def);
}

bool roll_attack_player(uint8_t atk, uint8_t def) BANKED {
  return check_attack(d256(), attack_roll_player, atk, def);
}

uint16_t calc_damage(uint8_t d16_roll, uint16_t base_dmg) BANKED {
  // Compute in 32 bits. A high-level monk's Flurry passes a base of up to 4600,
  // and 4600 times the top modifier of 20 is 92000, too big for a uint16_t.
  uint32_t d = base_dmg;
  d *= damage_roll_modifier[d16_roll & 0x0F];
  d /= 16;
  return d == 0 ? 1 : (uint16_t)d;
}

uint16_t calc_monster_exp(uint8_t mlevel, PowerTier tier) BANKED {

  int8_t diff = (int8_t)mlevel - (int8_t)player.level;

  if (diff <= -8)
    return 0;

  if (diff >= 7)
    return get_monster_exp(mlevel, tier) << 1;

  uint16_t k = (uint16_t)xp_mod[diff + 8];
  k *= get_monster_exp(mlevel, tier);
  k /= 16;

  return k;
}

const uint8_t agl_mod[4] = { 2, 4, 8, 12 };
const uint16_t atk_def_mod[4] = { 1, 2, 4, 6 };

bool roll_flee(uint8_t agl, uint8_t block_agl) BANKED {
  if (block_agl > agl + 10)
    return false;
  if (agl > block_agl + 10)
    return true;
  return rand() < 128;
}

uint8_t agl_down(uint8_t base_agl, PowerTier tier) BANKED {
  const uint8_t mod = agl_mod[tier];
  return base_agl < mod ? 0 : base_agl - mod;
}

uint8_t atk_down(uint8_t base, PowerTier tier) BANKED {
  uint16_t k = atk_def_mod[tier];
  k *= base;
  k >>= 4;
  k = base - k;
  return k;
}

uint8_t def_down(uint8_t base, PowerTier tier) BANKED {
  uint16_t k = atk_def_mod[tier];
  k *= base;
  k >>= 4;
  k = base - k;
  return k;
}

uint8_t agl_up(uint8_t base_agl, PowerTier tier) BANKED {
  return base_agl + agl_mod[tier];
}

uint8_t atk_up(uint8_t base, PowerTier tier) BANKED {
  uint16_t k = atk_def_mod[tier];
  k *= base;
  k >>= 4;
  k += base;
  return k;
}

uint8_t def_up(uint8_t base, PowerTier tier) BANKED {
  uint16_t k = atk_def_mod[tier];
  k *= base;
  k >>= 4;
  k += base;
  return k;
}

bool fear_flee_roll(PowerTier tier) BANKED {
  const uint8_t chance_tbl[4] = { 64, 96, 135, 185 };
  return d256() < chance_tbl[tier < 4 ? tier : 0];
}

bool fear_shiver_roll(PowerTier tier) BANKED {
  const uint8_t chance_tbl[4] = { 128, 135, 185, 240 };
  return d256() < chance_tbl[tier < 4 ? tier : 0];
}

bool paralyzed_roll(PowerTier tier) BANKED {
  const uint8_t chance_tbl[4] = { 192, 212, 230, 250 };
  return d256() < chance_tbl[tier < 4 ? tier : 0];
}

uint16_t poison_hp(PowerTier tier, uint16_t max_hp) BANKED {
  uint16_t k = max_hp * (tier < 4 ? tier + 2 : 1);
  k >>= 4;
  return k;
}

bool confused_attack(PowerTier tier) BANKED {
  const uint8_t chance_tbl[4] = { 64, 96, 128, 192 };
  return d256() < chance_tbl[tier < 4 ? tier : 0];
}

uint16_t regen_hp(PowerTier tier, uint16_t max_hp) BANKED {
  uint16_t k = max_hp * (tier < 4 ? tier + 2 : 1);
  k >>= 4;
  return k;
}
