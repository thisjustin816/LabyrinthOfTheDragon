"""Shared loader for the stat tables, so a balance script can compare what is
in the tree against any revision of assets/tables.csv.

The tables are the game's whole difficulty curve: 99 rows per stat, four power
tiers each. A change to one is hard to judge by reading the diff, and easy to
judge by asking what it does to a hit chance or to the length of a fight.
"""
import csv, io, os, subprocess

# tools/emu/balance/tables.py -> repo root
REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
CSV = os.path.join(REPO, "assets", "tables.csv")
UPSTREAM = os.environ.get("LOTD_BASE", "origin/main")


def load(rev=None):
    """Column name -> 99 values. `rev` reads that revision instead of the tree."""
    if rev:
        txt = subprocess.run(["git", "-C", REPO, "show", f"{rev}:assets/tables.csv"],
                             capture_output=True, text=True, check=True).stdout
    else:
        txt = open(CSV).read()
    rows = [r for r in csv.reader(io.StringIO(txt)) if r and r[0].strip()]
    hdr = [h.strip() for h in rows[0]]
    data = {h: [] for h in hdr}
    for r in rows[2:]:                      # row 1 names the C types
        for h, v in zip(hdr, r):
            data[h].append(int(v.strip()))
    return data


NEW = load()
_old = None


def __getattr__(name):
    """OLD, the tables at UPSTREAM, loads on first use, so a script that only
    reads the tree runs without that revision."""
    global _old
    if name == "OLD":
        if _old is None:
            _old = load(UPSTREAM)
        return _old
    raise AttributeError(name)


def col(d, name, tier):
    return d[f"{name}_{tier.lower()}"]


# data/bank05.c. Index is the atk-def delta clamped to +/-32, then +32; the
# value is the threshold a d256 roll has to come in under.
ATK_P = [154,156,158,161,163,165,168,170,173,175,177,180,182,184,187,189,192,194,
         196,199,201,203,206,208,211,213,215,218,220,222,225,227,230,230,231,231,
         232,233,233,234,235,235,236,236,237,238,238,239,240,240,241,241,242,243,
         243,244,245,245,246,246,247,248,248,249,250]
ATK_M = [50,54,58,63,67,72,76,81,85,89,94,98,103,107,112,116,121,125,129,134,138,
         143,147,152,156,160,165,169,174,178,183,187,192,193,195,196,198,199,201,
         203,204,206,207,209,211,212,214,215,217,219,220,222,223,225,227,228,230,
         231,233,235,236,238,239,241,243]


def hit(table, atk, dfn):
    """Probability that an attack of `atk` lands against `dfn`."""
    d = max(-32, min(32, atk - dfn))
    return table[d + 32] / 256.0


# player.c update_stats(): hp, sp, atk, def, matk, mdef, agl, plus the damage
# tier each class's attacks roll on.
CLASSES = {
    "fighter":  dict(hp="a", sp="c", atk="b", dfn="a", agl="b", dmg="b"),
    "monk":     dict(hp="b", sp="b", atk="b", dfn="b", agl="a", dmg="b"),
    "druid":    dict(hp="b", sp="b", atk="c", dfn="b", agl="b", dmg="c"),
    "sorcerer": dict(hp="c", sp="a", atk="c", dfn="c", agl="a", dmg="c"),
}
