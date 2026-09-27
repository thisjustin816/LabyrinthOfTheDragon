"""Chests whose reward text promises an item the chest does not carry.

A chest entry that leaves `items` to C's silent NULL fill shows its reward
text and grants nothing. This flags any chest whose open_msg is a
str_chest_item_* string but whose items pointer is not a chest_item_* list,
unless it has an on_open callback to grant something itself. Exits 1 when
it flags a chest. The scanner proves itself on a fixture table first, so a
change to the Chest struct's layout fails loudly instead of scanning every
chest and finding nothing.
"""
import re, glob, os, sys
from shared import strip_comments

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(os.path.abspath(os.path.join(HERE, os.pardir, os.pardir, os.pardir)), "src")


def scan(src, label):
    """(chests_seen, offenders) for one floor file's text.

    Offenders are (label, chest_id, msg, items, callback).
    """
    src = strip_comments(src)
    m = re.search(r"static const Chest chests\[\]\s*=\s*\{", src)
    if not m:
        return 0, []
    # Walk to the matching close brace, then split the body on the
    # brace-delimited entries.
    i, depth, body = m.end() - 1, 0, None
    for j in range(i, len(src)):
        if src[j] == "{":
            depth += 1
        elif src[j] == "}":
            depth -= 1
            if depth == 0:
                body = src[i + 1:j]
                break
    if body is None:
        sys.exit("%s: chests[] never closes" % label)
    total, bad = 0, []
    for entry in re.finditer(r"\{([^{}]*)\}", body):
        fields = [f.strip() for f in entry.group(1).split(",")]
        fields = [f for f in fields if f]
        if not fields or fields[0] == "END":
            continue
        total += 1
        text = [f for f in fields if f.startswith("str_chest_item_")]
        # Positional layout: id, map, x, y, locked, key_unlock, msg, items, cb
        if not text:
            continue
        idx = fields.index(text[0])
        items = fields[idx + 1] if idx + 1 < len(fields) else "NULL"
        cb = fields[idx + 2] if idx + 2 < len(fields) else None
        if cb not in (None, "NULL"):
            continue
        if items == "NULL" or not items.startswith("chest_item"):
            bad.append((label, fields[0], text[0], items, cb))
    return total, bad


# Four shapes: a complete chest, reward text with no item list (C fills the
# rest with NULL), a chest whose message is not a reward at all and so owes
# nothing, and reward text whose callback grants the reward.
FIXTURE = """
static const Chest chests[] = {
  { CHEST_1, MAP_A, 1, 2, false, false, str_chest_item_1pot, chest_item_1pot, NULL },
  { CHEST_2, MAP_A, 3, 4, true, true, str_chest_item_1eth },
  { CHEST_3, MAP_B, 5, 6, false, false, str_floor1_sign_empty, NULL, on_open_special },
  { CHEST_4, MAP_B, 7, 8, false, false, str_chest_item_1eth, NULL, grant_ether },
  { END },
};
"""


def main():
    total, bad = scan(FIXTURE, "fixture")
    ids = [b[1] for b in bad]
    if total != 4 or ids != ["CHEST_2"]:
        sys.exit("scanner self-test failed: saw %d chests, flagged %r" % (total, ids))
    print("scanner self-test: PASS (fixture flags only CHEST_2)")

    total, bad = 0, []
    for path in sorted(glob.glob(os.path.join(SRC, "floor*.c"))):
        t, b = scan(open(path).read(), os.path.basename(path))
        total += t
        bad += b
    print(f"chests scanned: {total}")
    if not bad:
        print("every chest with reward text carries an item list")
    for f, cid, msg, items, cb in bad:
        print(f"  !! {f} {cid}: msg={msg} items={items} callback={cb}")
    if bad:
        sys.exit(1)


if __name__ == "__main__":
    main()
