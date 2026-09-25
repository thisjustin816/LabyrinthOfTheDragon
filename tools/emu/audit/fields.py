"""Find struct fields that logic reads but nothing ever writes.

A declaration the parser cannot read is an error rather than a skipped field,
and the detector proves itself on a fixture before its output is believed.
EXPECTED lists the findings known to be false positives, each with its
reason; anything else is a new finding, and the audit exits 1 on one.
"""
import re, sys, os, glob
from shared import strip_comments

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(os.path.abspath(os.path.join(HERE, os.pardir, os.pardir, os.pardir)), "src")


def struct_fields_in(src, typename):
    """Field names of `typedef struct [tag] { ... } typename;` in C text `src`.

    Returns [(name, is_aggregate)], or None when no such struct is there.
    """
    body = None
    # Walk every typedef struct in the text and keep the one that closes with
    # `} typename;` -- brace counting rather than a non-greedy `}` match, which
    # stops at the first nested closing brace.
    for m in re.finditer(r"typedef\s+struct\s*(?:\w+\s*)?\{", src):
        i = m.end() - 1
        depth = 0
        for j in range(i, len(src)):
            if src[j] == "{":
                depth += 1
            elif src[j] == "}":
                depth -= 1
                if depth == 0:
                    tail = src[j + 1:j + 80]
                    if re.match(r"\s*%s\s*;" % re.escape(typename), tail):
                        body = src[i + 1:j]
                    break
        if body:
            break
    if body is None:
        return None

    # One declaration per `;` at depth 0 of the body. Function-pointer members
    # and nested anonymous structs both nest, so track depth here too.
    decl, depth, decls = [], 0, []
    for ch in body:
        if ch in "{(":
            depth += 1
        elif ch in "})":
            depth -= 1
        if ch == ";" and depth == 0:
            decls.append("".join(decl))
            decl = []
        else:
            decl.append(ch)

    fields = []
    for d in decls:
        d = " ".join(d.split())
        if not d:
            continue
        fp = re.search(r"\(\s*\*\s*(\w+)\s*\)", d)   # void (*take_turn)(...)
        if fp:
            fields.append((fp.group(1), True))
            continue
        # Trailing identifier of the declaration, plus any array suffix.
        m = re.search(r"(\w+)\s*(\[[^;]*\])?$", d)
        if not m:
            sys.exit("unparsed declaration in %s: %r" % (typename, d))
        fields.append((m.group(1), bool(m.group(2))))
    return fields


def struct_fields(path, typename):
    fields = struct_fields_in(strip_comments(open(path).read()), typename)
    if fields is None:
        sys.exit("could not find struct %s in %s" % (typename, path))
    return fields


ASSIGN = r"(?:=[^=]|\+=|-=|\*=|/=|\|=|&=|\^=|<<=|>>=)"
ANY_ACCESSOR = r"(?:->|\.)"


def usage(field, blob, scope=ANY_ACCESSOR):
    """(write_sites, read_sites) of `field` across blob {path: text}.

    `scope` is what must precede the name. The default matches `x.field` and
    `x->field`, so a local of the same name is never counted; a struct
    instance's own name (`\\bplayer\\.`) narrows it to that one object when
    another struct shares the field name.
    """
    writes, reads = [], []
    f = re.escape(field)
    access = re.compile(r"%s%s\b" % (scope, f))
    wr = re.compile(r"%s%s\s*(?:\[[^\]]*\])?\s*(?:%s|\+\+|--)" % (scope, f, ASSIGN))
    pre = re.compile(r"(?:\+\+|--)\s*[\w.\->\[\]]*%s%s\b" % (scope, f))
    # &m->field passed out is a write the callee may perform. Only a unary
    # `&` counts: one that opens an argument, a list item or an assignment.
    # `a && m->field` and `mask & m->field` are reads, and the first version
    # of this regex counted both as writes.
    addr = re.compile(r"(?:^|[(,=])\s*&(?!&)\s*[\w.\->\[\]]*%s%s\b" % (scope, f))
    for path, text in blob.items():
        for n, line in enumerate(text.splitlines(), 1):
            if not access.search(line):
                continue
            where = "%s:%d" % (os.path.basename(path), n)
            if wr.search(line) or pre.search(line) or addr.search(line):
                writes.append(where)
            else:
                reads.append(where)
    return writes, reads


def orphans(fields, blob, scope=ANY_ACCESSOR):
    """Fields that are read somewhere and written nowhere."""
    out = []
    for field, is_aggregate in fields:
        writes, reads = usage(field, blob, scope)
        if reads and not writes:
            out.append((field, is_aggregate, reads))
    return out


# (struct, field) -> why the detector flags it though something does write it.
EXPECTED = {
    ("Monster", "status_effects"):
        "an array written element by element through a StatusEffectInstance pointer",
    ("Encounter", "monsters"):
        "an array written through Monster pointers the generators receive",
    ("Encounter", "player_status_effects"):
        "an array written through a StatusEffectInstance pointer",
    ("Ability", "target_type"): "set in player.data.c's const Ability initializers",
    ("Ability", "sp_cost"): "set in player.data.c's const Ability initializers",
    ("Ability", "execute"): "set in player.data.c's const Ability initializers",
}


def report(label, typename, fields, blob, scope=ANY_ACCESSOR):
    """Print the struct's findings and return the ones EXPECTED does not list."""
    print("=== %s ===" % label)
    found = orphans(fields, blob, scope)
    new = []
    for field, is_aggregate, reads in found:
        kind = "array/pointer" if is_aggregate else "scalar"
        why = EXPECTED.get((typename, field))
        if why:
            print("  .. %-22s %-13s reads=%d  expected: %s" % (field, kind, len(reads), why))
            continue
        new.append(field)
        print("  !! %-22s %-13s reads=%d" % (field, kind, len(reads)))
        for r in reads[:6]:
            print("       %s" % r)
    if not found:
        print("  (none)")
    return new


# One field of each shape the detector has to get right. Only `orphan` is a
# true positive; every other member is written in some form the regexes must
# recognize, or is never read at all.
FIXTURE_STRUCT = """
typedef struct {
  uint8_t written;
  uint8_t orphan;
  uint8_t untouched;
  uint8_t counted;
  uint8_t handed_out;
  uint8_t slots[4];
  void (*hook)(uint8_t x);
} Fixture;
"""
FIXTURE_CODE = """
void f(Fixture *m, Fixture *o) {
  uint8_t orphan = 3;
  m->written = 1;
  if (m->written && m->orphan) { }
  m->counted++;
  if (m->counted == 2) { }
  fill(&o->handed_out);
  read_into(1, &o->handed_out);
  if (o->handed_out) { }
  if (mask & m->orphan) { }
  m->slots[2] = 0;
  if (m->slots[1]) { }
  m->hook = g;
  m->hook(m->orphan);
  if (orphan) { }
}
"""


def self_test():
    fields = struct_fields_in(strip_comments(FIXTURE_STRUCT), "Fixture")
    names = [f for f, _ in fields or []]
    want = ["written", "orphan", "untouched", "counted", "handed_out", "slots", "hook"]
    if names != want:
        sys.exit("fixture struct parsed as %r, expected %r" % (names, want))
    flagged = [f for f, _, _ in orphans(fields, {"fixture.c": strip_comments(FIXTURE_CODE)})]
    if flagged != ["orphan"]:
        sys.exit("detector self-test failed: flagged %r, expected ['orphan']" % flagged)


TARGETS = [
    ("Monster", "monster.h"),
    ("Player", "player.h"),
    ("Encounter", "encounter.h"),
    ("StatusEffectInstance", "stats.h"),
    ("Ability", "player.h"),
]


def main():
    self_test()
    print("detector self-test: PASS (fixture flags only `orphan`)")
    sources = sorted(glob.glob(os.path.join(ROOT, "*.c")) + glob.glob(os.path.join(ROOT, "*.h")))
    blob = {p: strip_comments(open(p).read()) for p in sources}
    new = []
    for typename, header in TARGETS:
        new += report("%s (%s)" % (typename, header), typename,
                      struct_fields(os.path.join(ROOT, header), typename), blob)
    # Player and Monster share member names (hp, debuff_immune, ...), so a
    # Player member nothing writes hides behind the Monster writes counted
    # above. This pass counts only accesses spelled through the one `player`
    # object; a member written through a Player pointer shows up here too, so
    # read its sites before calling it a defect.
    new += report("Player, counting only `player.` accesses", "Player",
                  struct_fields(os.path.join(ROOT, "player.h"), "Player"), blob,
                  scope=r"\bplayer\.")
    if new:
        print("\nnew findings: %s" % ", ".join(new))
        sys.exit(1)


if __name__ == "__main__":
    main()
