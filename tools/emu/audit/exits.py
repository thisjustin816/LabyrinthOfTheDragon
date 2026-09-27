"""The pathfinder's copy of each floor's exits, checked against the source.

nav.py routes from playtest/exits_db.py, a hand transcription of every floor's
Exit table, and nothing else keeps the two in step. A missing exit is the quiet
failure, since a route the pathfinder cannot see is one it simply never takes,
so run this after changing any floor's exits[].

This compares the two field by field: source map and tile, destination tile,
and heading. The destination map is left out on purpose, because exits_db marks
a cross-floor exit's destination map as None rather than naming the other
floor's map, and the heading and tile already pin the landing down. The scanner
proves itself on a fixture first, so a change to the Exit struct's layout fails
loudly instead of parsing no exits and reporting every floor clean.
"""
import os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, os.pardir, os.pardir, os.pardir))
sys.path.insert(0, os.path.join(REPO, "tools", "emu", "playtest"))
from exits_db import EXITS
from shared import strip_comments

MAPS = {"MAP_A": "A", "MAP_B": "B"}


def scan(src):
    """Every exit in one floor file's exits[] table, as
    (map, x, y, to_x, to_y, heading) tuples. None if there is no table."""
    src = strip_comments(src)
    m = re.search(r"static const Exit exits\[\]\s*=\s*\{(.*?)\n\};", src, re.S)
    if not m:
        return None
    found = set()
    for sm, sx, sy, _tm, tx, ty, head in re.findall(
            r"\{\s*(MAP_[AB])\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(MAP_[AB])\s*,"
            r"\s*(\d+)\s*,\s*(\d+)\s*,\s*(\w+)", m.group(1)):
        found.add((MAPS[sm], int(sx), int(sy), int(tx), int(ty), head))
    return found


def copy_of(n, exits=EXITS):
    return {(e[0], e[1], e[2], e[4], e[5], e[6]) for e in exits.get(n, [])}


# Four shapes: stairs within a map, a hole landing HERE, an exit on MAP_B, and a
# cross-floor exit whose trailing &bank_floorN the scanner has to step past.
FIXTURE = """
static const Exit exits[] = {
  { MAP_A, 8, 26, MAP_A, 27, 9, UP, EXIT_STAIRS },
  { MAP_A, 21, 30, MAP_A, 11, 18, HERE, EXIT_HOLE },  // a trailing comment
  { MAP_B, 3, 5, MAP_A, 3, 18, DOWN, EXIT_STAIRS },
  /* { MAP_A, 1, 1, MAP_A, 2, 2, UP, EXIT_STAIRS }, commented out */
  { MAP_A, 27, 5, MAP_A, 8, 29, UP, EXIT_STAIRS, &bank_floor8 },
  { END },
};
"""
FIXTURE_WANT = {("A", 8, 26, 27, 9, "UP"), ("A", 21, 30, 11, 18, "HERE"),
                ("B", 3, 5, 3, 18, "DOWN"), ("A", 27, 5, 8, 29, "UP")}


def drift(exits=EXITS):
    """{floor: (missing_from_copy, extra_in_copy)} for every floor that differs."""
    out = {}
    for n in range(1, 9):
        src = scan(open(os.path.join(REPO, "src", f"floor{n}.c")).read())
        if src is None:
            sys.exit(f"floor{n}.c: no exits[] table found")
        copy = copy_of(n, exits)
        if src != copy:
            out[n] = (src - copy, copy - src)
    return out


def main():
    got = scan(FIXTURE)
    if got != FIXTURE_WANT:
        sys.exit(f"scanner self-test failed:\n  got  {sorted(got)}\n  want {sorted(FIXTURE_WANT)}")
    print("scanner self-test: PASS (fixture parses to its four exits)")

    bad = drift()
    for n in range(1, 9):
        print(f"floor {n}: {'DRIFT' if n in bad else 'matches'} "
              f"({len(copy_of(n))} exits in the copy)")
    for n, (missing, extra) in sorted(bad.items()):
        for e in sorted(missing):
            print(f"  !! floor {n}: in floor{n}.c but not exits_db.py: {e}")
        for e in sorted(extra):
            print(f"  !! floor {n}: in exits_db.py but not floor{n}.c: {e}")
    if bad:
        sys.exit(1)
    print("exits_db.py matches every floor's exits table")


if __name__ == "__main__":
    main()
