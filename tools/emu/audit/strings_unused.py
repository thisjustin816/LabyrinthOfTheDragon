"""Find declared strings.js symbols that nothing under src/ references.

src/strings.h declares one `extern const char str_<namespace>_<key>[]` per
assets/strings.js entry; data/*.c defines them (generated, not a use). A
symbol is unused when no other file under src/ names it. EXPECTED_UNUSED
pins the known count, and the audit exits 1 when the count differs, so a
string newly wired up or newly orphaned shows up rather than hiding in the
list. Also lists every floor_test/tbd string's reference sites, since one of
the nine floor_test strings is used live and the rest are dead alongside it.
"""
import glob
import os
import re

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, os.pardir, os.pardir)) + os.sep
STRINGS_H = ROOT + "src/strings.h"

DECL_RE = re.compile(r'extern const char (str_\w+)\[\];')
EXPECTED_UNUSED = 27


def declared_symbols():
    text = open(STRINGS_H).read()
    return DECL_RE.findall(text)


def strip_comments_and_strings(text):
    """Blank out //, /* */ and string/char literal contents, keeping every
    newline in place so line numbers still line up. A symbol named only
    inside a comment (floor5.c's three commented-out signs pointing at
    str_floor_common_tbd) must not count as a use."""
    out = []
    i, n = 0, len(text)
    while i < n:
        two = text[i:i + 2]
        if two == '//':
            j = text.find('\n', i)
            j = n if j == -1 else j
            out.append(' ' * (j - i))
            i = j
        elif two == '/*':
            j = text.find('*/', i + 2)
            j = n if j == -1 else j + 2
            out.append(''.join(c if c == '\n' else ' ' for c in text[i:j]))
            i = j
        elif text[i] in ('"', "'"):
            quote = text[i]
            j = i + 1
            while j < n and text[j] != quote:
                j += 2 if text[j] == '\\' else 1
            j = min(j + 1, n)
            out.append(''.join(c if c == '\n' else ' ' for c in text[i:j]))
            i = j
        else:
            out.append(text[i])
            i += 1
    return ''.join(out)


def source_files():
    """src/*.c and src/*.h, excluding strings.h itself (the declaration
    site, not a use) -- some symbols are only named inside a macro body in
    a .h, e.g. battle.effects.h's MISS()/HEAL_HP()/FLEE_*() wrappers."""
    return sorted(
        p for p in glob.glob(ROOT + "src/*.c") + glob.glob(ROOT + "src/*.h")
        if os.path.basename(p) != "strings.h"
    )


def usage_sites(symbol):
    """(file, line) pairs under src/ that name this symbol in live code,
    excluding data/*.c (generated definitions), strings.h (the declaration
    itself), and any comment or string-literal text."""
    sites = []
    pattern = re.compile(r'\b' + re.escape(symbol) + r'\b')
    for path in source_files():
        code = strip_comments_and_strings(open(path).read())
        for n, line in enumerate(code.splitlines(), 1):
            if pattern.search(line):
                sites.append((os.path.basename(path), n))
    return sites


def self_test():
    # Fixture mirrors the real shape: a header with three symbols -- one
    # used by live code, one named only inside a // comment (floor5.c's
    # shape exactly), and one truly dead.
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        srcdir = os.path.join(d, "src")
        os.makedirs(srcdir)
        with open(os.path.join(srcdir, "strings.h"), "w") as f:
            f.write(
                "extern const char str_t_used[];\n"
                "extern const char str_t_macro[];\n"
                "extern const char str_t_commented[];\n"
                "extern const char str_t_orphan[];\n"
            )
        with open(os.path.join(srcdir, "user.c"), "w") as f:
            f.write(
                "void f(void) { puts(str_t_used); }\n"
                "// { MAP_A, 2, 18, UP, str_t_commented }, // Boss\n"
                "/* also str_t_commented in a block comment */\n"
            )
        # battle.effects.h's shape: a symbol named only inside a header macro.
        with open(os.path.join(srcdir, "user.effects.h"), "w") as f:
            f.write("#define MISS() sprintf(buf, str_t_macro)\n")

        global ROOT, STRINGS_H
        real_root, real_header = ROOT, STRINGS_H
        ROOT, STRINGS_H = d + os.sep, os.path.join(srcdir, "strings.h")
        try:
            syms = declared_symbols()
            used = {s for s in syms if usage_sites(s)}
            ok = (
                syms == ['str_t_used', 'str_t_macro', 'str_t_commented', 'str_t_orphan']
                and used == {'str_t_used', 'str_t_macro'}
            )
        finally:
            ROOT, STRINGS_H = real_root, real_header

    if not ok:
        print(f"self-test: FAIL (syms={syms}, used={used})")
        return False
    print("self-test: PASS (fixture flags str_t_commented and str_t_orphan, not str_t_used/str_t_macro)")
    return True


def main():
    if not self_test():
        raise SystemExit(1)

    symbols = declared_symbols()
    unused = [s for s in symbols if not usage_sites(s)]

    print(f"symbols declared: {len(symbols)}")
    print(f"unused (declared, never referenced in src/*.c or src/*.h): {len(unused)}")
    print(f"expected: {EXPECTED_UNUSED}" + ("  (MATCH)" if len(unused) == EXPECTED_UNUSED else "  (CHANGED -- report this)"))
    print()
    for s in unused:
        print(f"  !! {s}")

    print("\n=== floor_test / tbd strings: reference sites (live code, not data/*.c) ===")
    ft_tbd = [s for s in symbols if 'floor_test' in s or s.endswith('_tbd') or '_tbd_' in s]
    for s in ft_tbd:
        sites = usage_sites(s)
        where = ", ".join(f"{f}:{n}" for f, n in sites) if sites else "(none -- dead)"
        print(f"  {s}: {where}")

    if len(unused) != EXPECTED_UNUSED:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
