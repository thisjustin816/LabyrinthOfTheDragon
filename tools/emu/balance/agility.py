"""What AGL buys: initiative, whether you can flee, and every monk attack's
to-hit and damage level.
"""
from tables import NEW, CLASSES, ATK_P, col, hit


def p_first(agl_p, agl_m, monsters=1):
    """d32()+agl+1 each, sorted descending; the player holds index 0 so wins ties."""
    wins = sum(1 for a in range(32) for b in range(32) if a + agl_p >= b + agl_m)
    return (wins / 1024) ** monsters


def p_flee(agl, block):
    """roll_flee() in src/stats.c: a d256 roll under 128 + 16 per point of AGL
    over the fastest monster able to chase, held to 32..224."""
    chance = max(32, min(224, 128 + 16 * (agl - block)))
    return chance / 256


print("Initiative: P(player acts before a same-level monster), with no AGL vs the class's own.\n")
print(f"{'lvl':>4} {'class':<9} {'tier':>5} | {'one monster':^17} | {'first of three':^17}")
for lvl in (10, 30, 60):
    i = lvl - 1
    for c, s in CLASSES.items():
        ap = col(NEW, "agl", s["agl"])[i]
        for mt in ("C", "S"):
            am = col(NEW, "agl", mt)[i]
            print(f"{lvl:>4} {c:<9} {mt:>5} | {p_first(0, am):>7.1%} {p_first(ap, am):>8.1%} |"
                  f" {p_first(0, am, 3):>7.1%} {p_first(ap, am, 3):>8.1%}")
    print()

print("Flee: 128 + 16 per point of AGL over the fastest monster able to chase,")
print("in 256, held to 1 in 8 and 7 in 8. A blinded or frightened monster cannot")
print("chase (issue #80), and with none left to chase the hero always gets away.\n")
print(f"{'lvl':>4} {'class':<9} | {'vs C':>12} {'vs S':>12}")
for lvl in (10, 30, 60, 90):
    i = lvl - 1
    for c, s in CLASSES.items():
        ap = col(NEW, "agl", s["agl"])[i]
        ac, as_ = col(NEW, "agl", "C")[i], col(NEW, "agl", "S")[i]
        print(f"{lvl:>4} {c:<9} | {'C=' + str(ac):>6} {p_flee(ap, ac):>5.0%} {'S=' + str(as_):>6} {p_flee(ap, as_):>5.0%}")
    print()

print("Monk ability damage: level_offset(level, agl) picks the damage row.\n")
for lvl in (10, 30, 60, 90):
    i = lvl - 1
    s = CLASSES["monk"]
    a = col(NEW, "agl", s["agl"])[i]
    d0 = col(NEW, "player_dmg", s["dmg"])[i]
    d1 = col(NEW, "player_dmg", s["dmg"])[min(lvl + a, 99) - 1]
    atk, mdef = col(NEW, "player_atk", s["atk"])[i], col(NEW, "monster_def", "A")[i]
    print(f"  lvl {lvl:>2}  agl {a:>2}   damage {d0:>4} -> {d1:<4} ({d1 / d0 - 1:+.0%})"
          f"   to-hit vs A-tier {hit(ATK_P, atk, mdef):.1%} -> {hit(ATK_P, atk + a, mdef):.1%}")
