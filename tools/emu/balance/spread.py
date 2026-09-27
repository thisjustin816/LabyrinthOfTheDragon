"""Issue #35: does a monster's tier mean the same thing at every depth?

Reports the C-to-S spread in hit chance per class, and how much that spread
itself moves between level 1 and 99. A spread that holds steady is the goal;
one that grows means tier counts for more the deeper you go.
"""
from tables import NEW, OLD, CLASSES, ATK_M, ATK_P, col, hit, UPSTREAM


def drift(data, atk_t, def_t, side):
    vals = []
    for i in range(99):
        p_atk, p_def = col(NEW, "player_atk", atk_t)[i], col(NEW, "player_def", def_t)[i]
        if side == "m":
            v = [hit(ATK_M, col(data, "monster_atk", t)[i], p_def) for t in "CBAS"]
        else:
            v = [hit(ATK_P, p_atk, col(data, "monster_def", t)[i]) for t in "CBAS"]
        vals.append(abs(v[0] - v[3]) * 100)
    return min(vals), max(vals), max(vals) - min(vals)


print("C-to-S tier spread across levels 1-99, in points of hit chance.")
print("'drift' is how much the spread moves from level 1 to 99 (want ~0).")
print(f"Comparing the tree against {UPSTREAM}.\n")
for side, label in (("m", "monster hits player (monster ATK axis)"),
                    ("p", "player hits monster (monster DEF axis)")):
    print(label)
    print(f"  {'class':<9} {'base spread':>18} {'drift':>7}    {'tree spread':>18} {'drift':>7}")
    for c, s in CLASSES.items():
        lo, hi, d0 = drift(OLD, s["atk"], s["dfn"], side)
        l2, h2, d1 = drift(NEW, s["atk"], s["dfn"], side)
        note = "  worse" if d1 > d0 + 2 else ("  better" if d1 < d0 - 2 else "")
        print(f"  {c:<9} {lo:>7.1f}-{hi:<5.1f}p {d0:>10.1f}p    {l2:>7.1f}-{h2:<5.1f}p {d1:>10.1f}p{note}")
    print()
