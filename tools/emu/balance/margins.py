"""How long a fight lasts, and who runs out first.

Rounds to kill vs rounds to die for one player against one same-level monster,
basic attacks only. The ratio is what difficulty actually feels like: above 1
the player outlasts the monster. Comparing the ratio against the base revision
separates "numbers moved" from "the outcome moved".
"""
from tables import NEW, OLD, CLASSES, ATK_M, ATK_P, col, hit, UPSTREAM

print(f"Rounds to kill / rounds to die, tree vs {UPSTREAM}.")
print("Basic attacks only, damage rolls average 1.0x, no abilities or items.\n")
for c, s in CLASSES.items():
    print(f"  {c}")
    for lvl in (15, 40, 70):
        i = lvl - 1
        p_hp, p_dmg = col(NEW, "player_hp", s["hp"])[i], col(NEW, "player_dmg", s["dmg"])[i]
        p_atk, p_def = col(NEW, "player_atk", s["atk"])[i], col(NEW, "player_def", s["dfn"])[i]
        out = []
        for t in ("C", "S"):
            m_hp, m_dmg = col(NEW, "monster_hp", t)[i], col(NEW, "monster_dmg", t)[i]
            pair = []
            for d in (OLD, NEW):
                ph = hit(ATK_P, p_atk, col(d, "monster_def", t)[i])
                mh = hit(ATK_M, col(d, "monster_atk", t)[i], p_def)
                pair.append((p_hp / (mh * m_dmg)) / (m_hp / (ph * p_dmg)))
            out.append((t, pair[0], pair[1]))
        print(f"    lvl {lvl:>2}   " + "   ".join(
            f"{t}: {o:5.2f} -> {n:5.2f} ({(n / o - 1) * 100:+5.1f}%)" for t, o, n in out))
    print()
