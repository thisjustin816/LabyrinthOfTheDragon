"""Find const ROM data handed across a bank boundary.

core.load_bg_palette() and core.load_sprite_palette() sit in ROM0 and
dereference the pointer they are given with the caller's bank still mapped,
so passing them a symbol that lives in another bank reads the caller's bank
at that address instead. Tilemaps do not have the problem: a Tilemap carries
its own bank field and draw_tilemap() switches.

Banks come from the .noi symbol table, whose DEF addresses are
(bank << 16) | mapped_address, cross-checked against each file's #pragma bank.
"""
import re, glob, os
from shared import strip_comments_and_strings

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, os.pardir, os.pardir)) + os.sep
NOI = ROOT + "LabyrinthOfTheDragon.noi"
STR_H = ROOT + "src/strings.h"

CALLS = re.compile(
    r"core\.load_(?:bg|sprite)_palette\(\s*([A-Za-z_]\w*)")
DECL_RE = re.compile(r"extern const char (str_(\w+?)_\w+)\[\];")

# Files whose only legitimate use of a bank-2 string is handing the
# pointer to textbox.c's display path (signs, chests, NPC lines, doors),
# never dereferencing it themselves.
TEXTBOX_HANDOFF_FILES = {
    "floor1.c", "floor2.c", "floor3.c", "floor4.c", "floor5.c", "floor6.c",
    "floor7.c", "floor8.c", "floor_common.c", "map.c", "map.encounters.c",
    "map.menu.c",
}

_file_banks = {}


def file_bank(path):
    """The bank a source file's #pragma bank puts it in, 0 without one."""
    if path not in _file_banks:
        m = re.search(r"^#pragma bank (\d+)", open(path).read(), re.M)
        _file_banks[path] = int(m.group(1)) if m else 0
    return _file_banks[path]


def load_banks():
    """Symbol -> bank, from the .noi's (bank << 16) | mapped_address."""
    sym_bank = {}
    for line in open(NOI):
        m = re.match(r"DEF _(\w+) 0x([0-9A-Fa-f]+)$", line.strip())
        if not m:
            continue
        name, addr = m.group(1), int(m.group(2), 16)
        bank, mapped = addr >> 16, addr & 0xFFFF
        if mapped < 0x4000:                     # ROM0 or RAM: always reachable
            bank = 0
        sym_bank[name] = bank
    return sym_bank


def palettes(sym_bank):
    bad = []
    for path in sorted(glob.glob(ROOT + "src/*.c")):
        src = open(path).read()
        fb = file_bank(path)
        for n, line in enumerate(src.splitlines(), 1):
            for sym in CALLS.findall(line):
                b = sym_bank.get(sym)
                if b is None:                   # a local, a parameter, or inlined
                    continue
                if b != 0 and b != fb:
                    bad.append((os.path.basename(path), n, fb, sym, b, line.strip()))

    # The detector has to be able to fail: two symbols whose banks are known
    # pin the bank decoding, so a changed .noi format cannot pass as clean.
    print("symbols indexed: %d" % len(sym_bank))
    print("textbox_palette bank: %s   map.menu.c bank: 30" % sym_bank.get("textbox_palette"))
    assert sym_bank.get("textbox_palette") == 2, "banks are not being read correctly"
    assert sym_bank.get("main_menu_palette") == 30, "banks are not being read correctly"
    print()

    if not bad:
        print("no cross-bank palette loads")
    for f, n, fb, sym, sb, line in bad:
        print("  !! %s:%d (bank %d) loads %s from bank %d\n       %s" % (f, n, fb, sym, sb, line))


# The same question for strings. A string is safe when it is in bank 0
# (always mapped), or when the code dereferencing it runs with the string's
# bank mapped. Two established patterns do that:
#
#  - Map textboxes: textbox.c (bank 2) is the only thing that ever walks a
#    textbox string byte by byte (text_writer.c has no #pragma bank of its
#    own, but it is only ever called from inside a banked call already
#    mapped into bank 2, e.g. update_textbox()/open_textbox(), so bank 2
#    stays mapped for the read). Floor code (bank 8) and map.c/map.menu.c
#    only ever *pass* a bank-2 string pointer into that path -- sign
#    tables, chest rewards, map_textbox_with_action() -- so they may
#    reference bank-2 strings freely.
#  - Battle messages: built with sprintf() into WRAM by the ability or
#    monster code itself. sprintf is unbanked, so it reads its format
#    string with whatever bank the *caller* has mapped -- safe only when
#    the calling file's own bank equals the string's bank.
#
# Everything else is flagged for a check on screen: this is a flagger, not
# an oracle.
def strings(sym_bank):
    print()
    print("=== String reads across a bank boundary ===")

    str_bank = {}   # symbol -> bank, from sym_bank (the .noi already indexed every symbol)
    str_ns = {}
    for line in open(STR_H):
        m = DECL_RE.search(line)
        if not m:
            continue
        sym, ns = m.group(1), m.group(2)
        b = sym_bank.get(sym)
        if b is not None:
            str_bank[sym] = b
            str_ns[sym] = ns

    assert str_bank, "no str_* symbols resolved from the .noi -- header pattern or .noi format changed"
    assert str_bank.get("str_floor1_boss_defeated") == 2, "floor namespace strings are not bank 2 as expected"
    assert str_bank.get("str_monster_hit") == 6, "monster namespace strings are not bank 6 as expected"
    assert str_bank.get("str_player_miss") == 4, "player namespace strings are not bank 4 as expected"
    print("string symbols resolved: %d" % len(str_bank))

    flagged = []
    sym_re_cache = {}
    # .h files are excluded: a macro header (battle.effects.h) has no bank of
    # its own. It compiles into whatever .c file invokes the macro, and that
    # call site is what needs checking: battle.effects.h's PLAYER_MISS,
    # PLAYER_MISS_ALL, and PLAYER_HEAL (player namespace, bank 4) are invoked
    # only from player.c (bank 4), and MONSTER_FLEE and MONSTER_FLEE_FAIL
    # (monster namespace, bank 6) only from monster.core.c (bank 6). The
    # header's own text would misread as an unbanked, bank-0 reference site.
    for path in sorted(glob.glob(ROOT + "src/*.c")):
        base = os.path.basename(path)
        fb = file_bank(path)
        code = strip_comments_and_strings(open(path).read())
        for n, line in enumerate(code.splitlines(), 1):
            for sym, sb in str_bank.items():
                if sb == 0 or sb == fb:
                    continue
                pat = sym_re_cache.setdefault(sym, re.compile(r"\b" + re.escape(sym) + r"\b"))
                if not pat.search(line):
                    continue
                if sb == 2 and base in TEXTBOX_HANDOFF_FILES:
                    continue  # established hand-off pattern
                if re.match(r"\s*return\s+" + re.escape(sym) + r"\s*;\s*$", line):
                    continue  # returns the pointer value; never dereferences it
                flagged.append((base, n, fb, sym, sb, str_ns[sym]))

    if not flagged:
        print("no string reference falls outside the two established safe patterns")
    else:
        print("%d reference(s) fit neither pattern -- verify each on screen before calling it a defect:" % len(flagged))
        for base, n, fb, sym, sb, ns in flagged:
            print("  !! %s:%d (bank %d) reads %s (namespace '%s', bank %d)" % (base, n, fb, sym, ns, sb))


def main():
    sym_bank = load_banks()
    palettes(sym_bank)
    strings(sym_bank)


if __name__ == "__main__":
    main()
