"""T59 - the file screen shows the game's version.

tools/version2h writes the version into src/version.h at build time: the
Makefile's major and minor version, then the number of commits since that line
last changed, then a "+" on any build that isn't a release. The file screen
draws it at the bottom left, level with the ERASE button's label
(src/main_menu.c VERSION_COL and ACTION_LABEL_ROW), in background palette 7's
hint gray. The erase prompt's YES box covers it while the prompt is up, and it
comes back when the prompt closes.
"""
import os, re, subprocess, sys
from lotd import *

chk = Checker("t59_version")
VERSION = game_version()
COL, ROW, LEN = 1, 16, 9
NAVY, HINT = (20, 22, 44), (150, 160, 190)


def git(*args):
    return subprocess.run(["git", "-C", REPO, *args], capture_output=True, text=True).stdout.strip()


def commits_since_version():
    """The commits since the Makefile's VERSION line last changed, found with
    git log rather than the blame version2h uses, or None in a shallow clone.
    A change to the line not yet committed counts as 0."""
    if git("rev-parse", "--is-shallow-repository") != "false":
        return None
    if git("diff", "HEAD", "--name-only", "-G^VERSION *=", "--", "Makefile"):
        return 0
    last = git("log", "-1", "--format=%H", "-G^VERSION *=", "--", "Makefile")
    return int(git("rev-list", "--count", f"{last}..HEAD")) if last else None


def rgb555(rgb):
    r, g_, b = rgb
    return (r >> 3) | ((g_ >> 3) << 5) | ((b >> 3) << 10)


def bg_palette(g, pal):
    """A background palette's four colors, read back through BCPS and BCPD."""
    colors = []
    for k in range(4):
        g.pb.memory[0xFF68] = pal * 8 + k * 2
        lo = g.pb.memory[0xFF69]
        g.pb.memory[0xFF68] = pal * 8 + k * 2 + 1
        colors.append(lo | (g.pb.memory[0xFF69] << 8))
    return colors


def field_attrs(g):
    """The attribute bytes under the version field, from VRAM bank 1."""
    vbk = g.pb.memory[0xFF4F]
    g.pb.memory[0xFF4F] = 1
    try:
        return [g.pb.memory[0x9800 + ROW * 32 + COL + k] for k in range(LEN)]
    finally:
        g.pb.memory[0xFF4F] = vbk


def shows_version(g, label):
    text = g.bg_text(COL, ROW, LEN)
    attrs = field_attrs(g)
    chk(label, text == VERSION.ljust(LEN) and all(a & 0x0F == 0x0F for a in attrs),
        f"text={text!r} attrs={[hex(a) for a in attrs]}")


base = re.search(r"^VERSION *= *(\S+)", open(os.path.join(REPO, "Makefile")).read(), re.M).group(1)
n = commits_since_version()
expected = f"v{base}" + ("" if n is None else f".{n}")
chk(f"T59 src/version.h holds the Makefile's {base} and the {n} commits since it changed",
    VERSION in (expected, expected + "+"),
    f"version.h has {VERSION!r}, git gives {expected!r} with or without the +; rebuild if HEAD moved since the build")

g = Game(tag="t59")
g.boot_to_save_select()
shows_version(g, f"T59 the file screen shows {VERSION} at the bottom left, in palette 7 with the font bank")
chk("T59 palette 7 is the hint gray on the navy backdrop",
    bg_palette(g, 7) == [rgb555(NAVY)] * 3 + [rgb555(HINT)], [hex(c) for c in bg_palette(g, 7)])

# A file to erase, then back to the file screen.
g.save_select_pick(0)
g.hero_select_pick(0)
g.wait_map_idle(600)
menu_save(g, chk, "T59 setup")
g.power_cycle("t59b")
g.boot_to_save_select()
shows_version(g, "T59 the version shows beside a saved file")

g.save_select_pick(3)
while g.get("cursor") != 0:
    g.press("up", wait=6)
g.press("a", wait=12)
chk("T59 the erase prompt's YES box takes the corner",
    g.bg_text(2, 1, 16) == "ERASE THIS FILE?" and g.bg_text(2, ROW, 7) == "  YES  "
    and VERSION not in g.bg_text(0, ROW, 10),
    f"header={g.bg_text(2, 1, 16)!r} row={g.bg_text(0, ROW, 10)!r}")
g.press("b", wait=12)
shows_version(g, "T59 the version comes back when the prompt closes")
g.press("b", wait=12)
shows_version(g, "T59 the version stays when erase mode ends")

# B on hero select comes back to a freshly drawn file screen.
g.save_select_pick(1)
g.wait_for(lambda: g.gs() == GS["HERO_SELECT"], 300)
g.tick(10)
g.press("b", wait=20)
g.wait_for(lambda: g.gs() == GS["SAVE_SELECT"], 300)
g.tick(8)
shows_version(g, "T59 the version shows after B on hero select")
g.close()
chk.summary()
