"""Every header prototype's BANKED/NONBANKED/plain against its own
definition's.

The compiler checks only half of this. When the defining file includes the
header, SDCC rejects a BANKED prototype over a plain definition, and the
reverse, as conflicting declarations, but it carries a NONBANKED prototype
into a plain definition without a word: the function lands in HOME as if
its own line said so, its body is unchanged, and the header is the only
line that says why. When the defining file does not include the header,
nothing is checked at all, and a plain call from another bank into a
function that turned out to live in its file's own bank is the crash this
audit exists to catch before the emulator does.

Which side to change follows from that. Annotating the plain side to match
the annotated one rebuilds byte-identical, because the compiler was already
treating the function that way. Stripping the annotation instead changes
what the compiler believes: a NONBANKED function moves out of HOME into its
file's own bank, which for a bank-0 file only shifts the layout between
HOME and CODE_0 and for any other file breaks every plain call from outside
that bank. Either way, prove a fix with a rebuild and an md5 diff against
the ROM rather than assuming it from where the linker happened to place the
function.

Definitions and prototypes are matched by name. A name with more than one
non-static definition, or none, is skipped rather than guessed at, and a
BANKED/NONBANKED definition with no prototype anywhere is reported
separately: on its own that is often fine (called only from its own file, or
only through an already-switched pointer), so it does not fail the audit.

This does not check for the class of bug `src/map.c`'s chest `on_open`
trampoline is: a call site with no bank switch at all, rather than a
prototype that disagrees with its own function. That one carries its own
comment instead.
"""
import re, sys, os, glob
from shared import strip_comments_and_strings

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(os.path.abspath(os.path.join(HERE, os.pardir, os.pardir, os.pardir)), "src")

KEYWORDS = {"if", "for", "while", "switch", "return", "sizeof", "CRITICAL", "else", "do"}

# A definition ends in `{`, a prototype in `;`; both share everything before
# that. The anchor `(?:^|[;}])` starts each attempt after the previous
# statement, so a multi-line return type or argument list is fine as long as
# neither contains a stray `;` or brace of its own -- true of every signature
# in this codebase.
_SHAPE = (
    r"(?:^|[;}])\s*(?!return\b)"
    r"((?:static\s+|extern\s+|const\s+|inline\s+)*[A-Za-z_]\w*(?:\s*\*+|\s+)[\w\s\*]*?)"
    r"\b([A-Za-z_]\w*)\s*\(([^;{}]*)\)\s*(BANKED|NONBANKED)?\s*"
)
DEF_RE = re.compile(_SHAPE + r"\{", re.M)
PROTO_RE = re.compile(_SHAPE + r";", re.M)


def _line(text, pos):
    return text.count("\n", 0, pos) + 1


def _rows(pattern, text):
    """(name, line, annot, is_static) for every top-level match, skipping
    control-flow keywords and function-pointer fields (`type (*name)(...)`,
    which never reach here: the `(` right after the return type breaks the
    character class before a name can be captured, but the check is kept as
    a second line of defense)."""
    out = []
    for m in pattern.finditer(text):
        prefix, name, args, annot = m.groups()
        if name in KEYWORDS or "(*" in m.group(0):
            continue
        out.append((name, _line(text, m.start(2)), annot or "plain", "static" in prefix))
    return out


def scan(blob):
    """blob: {path: raw text}, headers named *.h and everything else read as
    a definitions file. Returns (mismatches, undeclared):

    mismatches: [(name, def_path, def_line, def_annot, proto_path,
      proto_line, proto_annot)] for a name with exactly one non-static
      definition and a prototype whose annotation disagrees with it.
    undeclared: [(name, def_path, def_line, def_annot)] for a non-static
      BANKED/NONBANKED definition with no prototype at all.
    """
    defs, protos = {}, {}
    for path, raw in blob.items():
        text = strip_comments_and_strings(raw)
        target = protos if path.endswith(".h") else defs
        pattern = PROTO_RE if path.endswith(".h") else DEF_RE
        for name, line, annot, static in _rows(pattern, text):
            target.setdefault(name, []).append((path, line, annot, static))

    mismatches, undeclared = [], []
    for name, rows in defs.items():
        externals = [(p, ln, a) for p, ln, a, st in rows if not st]
        if len(externals) != 1:
            continue                              # static-only, or defined twice
        def_path, def_line, def_annot = externals[0]
        ps = protos.get(name)
        if not ps:
            if def_annot != "plain":
                undeclared.append((name, def_path, def_line, def_annot))
            continue
        for proto_path, proto_line, proto_annot, _ in ps:
            if proto_annot != def_annot:
                mismatches.append(
                    (name, def_path, def_line, def_annot, proto_path, proto_line, proto_annot))
    return mismatches, undeclared


# One function of each shape the detector has to get right: a stale header
# (must be caught), a matching pair, a static definition (must be ignored
# even though its own file has no prototype for it), and a NONBANKED
# definition with no header entry anywhere (must be listed, not failed on).
FIXTURE_C = """
void stale_fn(void) {
}

void matching_fn(void) BANKED {
}

static void hidden_fn(void) NONBANKED {
}

void undeclared_fn(void) NONBANKED {
}
"""
FIXTURE_H = """
void stale_fn(void) BANKED;
void matching_fn(void) BANKED;
"""


def self_test():
    bad, gone = scan({"fixture.c": FIXTURE_C, "fixture.h": FIXTURE_H})
    bad_names = sorted(n for n, *_ in bad)
    gone_names = sorted(n for n, *_ in gone)
    if bad_names != ["stale_fn"]:
        sys.exit("self-test failed: mismatches %r, expected ['stale_fn']" % bad_names)
    if gone_names != ["undeclared_fn"]:
        sys.exit("self-test failed: undeclared %r, expected ['undeclared_fn']" % gone_names)


def main():
    self_test()
    print("detector self-test: PASS (fixture flags only stale_fn, lists only undeclared_fn)")

    blob = {p: open(p).read() for p in sorted(glob.glob(os.path.join(ROOT, "*.c")) +
                                              glob.glob(os.path.join(ROOT, "*.h")))}
    mismatches, undeclared = scan(blob)

    base = lambda p: os.path.basename(p)
    print()
    if not mismatches:
        print("no prototype disagrees with its definition")
    for name, dp, dl, da, pp, pl, pa in sorted(mismatches):
        print("  !! %-24s %s:%d is %-9s but %s:%d says %s"
              % (name, base(dp), dl, da, base(pp), pl, pa))

    print()
    print("BANKED/NONBANKED definitions with no header prototype (not a failure by itself):")
    if not undeclared:
        print("  (none)")
    for name, dp, dl, da in sorted(undeclared):
        print("  .. %-24s %s:%d (%s)" % (name, base(dp), dl, da))

    if mismatches:
        sys.exit(1)


if __name__ == "__main__":
    main()
