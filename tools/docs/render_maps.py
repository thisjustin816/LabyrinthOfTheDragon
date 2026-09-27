"""Draw every floor's map as an SVG for the walkthrough in docs/.

Everything is read from the source the ROM is built from, so a map cannot
drift from the game: each floor's tables in src/floorN.c, the teleport() calls
its scripts make, and the tilemaps its maps[] table names, found through the
INCBIN lines in data/bank*.c. Run it again after changing any of those:

    python3 tools/docs/render_maps.py           # rewrite docs/maps/*.svg
    python3 tools/docs/render_maps.py --check   # exit 1 if a committed map is stale
    python3 tools/docs/render_maps.py --list    # print every pin, for the key tables

Tiles are decoded the way map.c's get_map_tile() decodes them. A walkable tile
with the background-priority bit set is drawn over the hero, who vanishes while
crossing it: the labyrinth's hidden passages are built from these tiles, painted
as black void or as the edge of a wall. The maps hatch them orange.

Pin labels come from the source ids (CHEST_3 is C3, LEVER_2 is L2, SCONCE_4 is
S4, DOOR_5 is D5), so a key table can be checked against the code. Exits get a
letter shared by both ends of a two-way pair; a one-way exit (a hole, a portal,
a scripted drop) puts its letter on a dashed ring where it lands. Special tiles
that no other pin covers are numbered ?1, ?2, ... in reading order per floor.
"""
import os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, os.pardir, os.pardir))
OUT = os.path.join(REPO, "docs", "maps")

WALL, GROUND, EXIT, SPECIAL = range(4)
FLOORS = range(1, 9)
CELL, MARGIN, TOP = 24, 26, 46

FIELDS = {
    "Map":    ("maps",    ["map", "bank", "data", "width", "height"]),
    "Chest":  ("chests",  ["id", "map", "x", "y", "locked", "magic_key", "message", "items", "on_open"]),
    "Exit":   ("exits",   ["map", "x", "y", "to_map", "to_x", "to_y", "heading", "type", "to_floor"]),
    "Sign":   ("signs",   ["map", "x", "y", "facing", "message"]),
    "Lever":  ("levers",  ["id", "map", "x", "y", "one_shot", "stuck", "on_pull"]),
    "Door":   ("doors",   ["id", "map", "x", "y", "type", "magic_key", "is_open"]),
    "Sconce": ("sconces", ["id", "map", "x", "y", "is_lit", "color", "on_lit"]),
    "NPC":    ("npcs",    ["id", "map", "x", "y", "monster", "tier", "on_action"]),
}
INTS = {"x", "y", "to_x", "to_y", "width", "height"}
BOOLS = {"locked", "magic_key", "is_lit", "is_open", "one_shot", "stuck"}

# player_at(x, y) guarding a block that calls teleport(): the portals and the
# scripted drops that live in a floor's on_special()/on_move() rather than in
# its exits[] table.
TELEPORT = re.compile(
    r"player_at\(\s*(\d+)\s*,\s*(\d+)\s*\)[^{};]*\)\s*\{[^{}]*?"
    r"teleport\(\s*MAP_([A-Z])\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\w+)\s*,\s*(\w+)\s*\)", re.S)

INK = "#26211d"
PAPER = "#f3ead7"
FLOOR = "#fbf6ea"
GRID = "#e3d8c1"
HIDDEN = "#e0722b"
# The source names flames red, green, and blue; on screen they burn orange,
# green, and purple, and the pins and notes say what the screen shows.
FLAME_LOOK = {"RED": "orange", "GREEN": "green", "BLUE": "purple"}
MUTED = "#7a6c5a"
FONT = "DejaVu Sans Mono, Menlo, Consolas, monospace"

# shape, fill, stroke, stroke width, text color
STYLE = {
    "start":  ("circle", "#ffffff", "#2e7d4f", 2.6, "#1d4d31"),
    "chest":  ("rect", "#e2a82b", "#6e4b0e", 1.2, "#2b1d05"),
    "locked": ("rect", "#e2a82b", "#b0211a", 2.6, "#2b1d05"),
    "lever":  ("rect", "#3d6ea5", "#1d3a5c", 1.2, "#ffffff"),
    "sconce": ("rect", "#5e554b", "#2e2924", 1.2, "#ffd98a"),
    "F_RED":  ("circle", "#e0862b", "#7a4310", 1.2, "#ffffff"),
    "F_GREEN": ("circle", "#2f9a4b", "#15492a", 1.2, "#ffffff"),
    "F_BLUE": ("circle", "#8e4fc7", "#4a2270", 1.2, "#ffffff"),
    "sign":   ("rect", "#8b5a2b", "#4a2e13", 1.2, "#ffffff"),
    "boss":   ("rect", "#8e1b1b", "#3f0b0b", 1.2, "#ffffff"),
    "elite":  ("rect", "#6a3d9a", "#33184f", 1.2, "#ffffff"),
    "door":   ("rect", "#6b4423", "#35210f", 1.2, "#ffffff"),
    "stairs": ("circle", "#ffffff", INK, 1.4, INK),
    "gated":  ("circle", "#ffffff", "#8a5a2b", 3.0, INK),
    "hole":   ("circle", "#4d4640", "#1c1814", 1.4, "#ffffff"),
    "portal": ("circle", "#b43fc1", "#5c1a63", 1.4, "#ffffff"),
    "next":   ("rect", "#2e7d4f", "#15492a", 1.2, "#ffffff"),
    "special": ("rect", "#f2c14e", "#8a6410", 1.2, "#2b1d05"),
    "passage": ("rect", HIDDEN, "#8a3d10", 1.2, "#ffffff"),
}


def strip_comments(text):
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    return re.sub(r"//[^\n]*", " ", text)


def brace_entries(body):
    """The top-level {...} entries of a C initializer body, quote-aware."""
    out, depth, cur, quoted = [], 0, [], False
    for ch in body:
        if ch == '"':
            quoted = not quoted
        if not quoted and ch == "{":
            depth += 1
            if depth == 1:
                cur = []
                continue
        elif not quoted and ch == "}":
            depth -= 1
            if depth == 0:
                out.append("".join(cur))
                continue
        if depth >= 1:
            cur.append(ch)
    return out


def split_fields(entry):
    fields, cur, quoted = [], [], False
    for ch in entry:
        if ch == '"':
            quoted = not quoted
        if ch == "," and not quoted:
            fields.append("".join(cur).strip())
            cur = []
        else:
            cur.append(ch)
    if "".join(cur).strip():
        fields.append("".join(cur).strip())
    return fields


def parse_tables(src, name="source"):
    """Every table FIELDS names, as lists of dicts, from comment-stripped C."""
    out = {}
    for ctype, (table, names) in FIELDS.items():
        m = re.search(rf"static const {ctype} {table}\[\]\s*=\s*\{{(.*?)\n\}};", src, re.S)
        if not m:
            sys.exit(f"{name}: no {table}[] table")
        rows = []
        for entry in brace_entries(m.group(1)):
            fields = split_fields(entry)
            if fields[0] == "END":
                break
            row = dict(zip(names, fields))
            for key in ("map", "to_map"):
                if key in row and row[key].startswith("MAP_"):
                    row[key] = row[key][4:]
            for key in INTS & row.keys():
                row[key] = int(row[key])
            for key in BOOLS & row.keys():
                row[key] = row[key] == "true"
            rows.append(row)
        out[table] = rows
    return out


def incbins():
    """{symbol: file} for every INCBIN in data/bank*.c."""
    out = {}
    data = os.path.join(REPO, "data")
    for fn in sorted(os.listdir(data)):
        if re.fullmatch(r"bank\d+\.c", fn):
            text = open(os.path.join(data, fn)).read()
            for sym, path in re.findall(r'INCBIN\(\s*(\w+)\s*,\s*"([^"]+)"\s*\)', text):
                out[sym] = os.path.join(REPO, path)
    return out


def decode(data, w, h):
    """{(x, y): (collision, graphic, priority)} for one tilemap."""
    if len(data) != 2 * w * h:
        sys.exit(f"tilemap is {len(data)} bytes, expected {2 * w * h} for {w}x{h}")
    return {(x, y): (data[2 * (x + y * w)] >> 6, data[2 * (x + y * w)] & 0x3F,
                     bool(data[2 * (x + y * w) + 1] & 0x80))
            for y in range(h) for x in range(w)}


def read_floor(n, bins):
    path = os.path.join(REPO, "src", f"floor{n}.c")
    src = strip_comments(open(path).read())
    fl = parse_tables(src, f"floor{n}.c")
    d = re.search(r"#define DEFAULT_X (\d+)\s+#define DEFAULT_Y (\d+)", src)
    fl["entry"] = (int(d.group(1)), int(d.group(2)))
    fl["n"] = n
    fl["tiles"] = {}
    for m in fl["maps"]:
        if m["data"] not in bins:
            sys.exit(f"floor{n}.c: map {m['map']} names {m['data']}, which no INCBIN defines")
        fl["tiles"][m["map"]] = decode(open(bins[m["data"]], "rb").read(), m["width"], m["height"])
    fl["teleports"] = []
    for x, y, tm, tx, ty, heading, kind in TELEPORT.findall(src):
        x, y = int(x), int(y)
        homes = [m for m, t in fl["tiles"].items() if (x, y) in t and t[(x, y)][0] != WALL]
        if len(homes) > 1:
            # on_special() only runs on special tiles, so a pad there wins.
            homes = [m for m in homes if fl["tiles"][m][(x, y)][0] == SPECIAL]
        if len(homes) != 1:
            sys.exit(f"floor{n}.c: teleport source ({x},{y}) is walkable on {len(homes)} maps")
        fl["teleports"].append({"map": homes[0], "x": x, "y": y, "to_map": tm,
                                "to_x": int(tx), "to_y": int(ty), "heading": heading, "type": kind})
    return fl


def hidden_tiles(fl, letter):
    """Walkable tiles drawn as something you would not try to walk on: the
    priority-flagged ones the hero vanishes behind, and the ones that wear a
    graphic this map otherwise uses only for walls."""
    tiles = fl["tiles"][letter]
    wall_art = {g for c, g, _ in tiles.values() if c == WALL}
    return {xy for xy, (c, g, prio) in tiles.items() if c != WALL and (prio or g in wall_art)}


def clusters(tiles):
    """4-connected groups of (x, y) tiles, in reading order of each group's first tile."""
    left, out = set(tiles), []
    while left:
        seed = min(left, key=lambda p: (p[1], p[0]))
        left.remove(seed)
        group, todo = [seed], [seed]
        while todo:
            x, y = todo.pop()
            for nb in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if nb in left:
                    left.remove(nb)
                    group.append(nb)
                    todo.append(nb)
        out.append(sorted(group, key=lambda p: (p[1], p[0])))
    return sorted(out, key=lambda g: (g[0][1], g[0][0]))


def gate(kind, has_door):
    return "gated" if has_door and kind == "stairs" else kind


def pins(fl):
    """{map letter: [(x, y, label, style, note)]} plus the landing rings,
    {map letter: [(x, y, label, style)]}, for one floor."""
    out = {m: [] for m in fl["tiles"]}
    rings = {m: [] for m in fl["tiles"]}
    doors = {(d["map"], d["x"], d["y"]): d for d in fl["doors"]}

    out["A"].append((*fl["entry"], "@", "start", "arrival"))

    sources = fl["exits"] + fl["teleports"]
    by_tile = {(e["map"], e["x"], e["y"]): e for e in sources}
    lettered, letters = set(), iter("abcdefghijklmnopqrstuvwxyz")
    for e in sources:
        key = (e["map"], e["x"], e["y"])
        if key in lettered:
            continue
        lettered.add(key)
        if e.get("to_floor"):
            out[e["map"]].append((e["x"], e["y"], "DOWN", "next", "stairs down to the next floor"))
            continue
        try:
            letter = next(letters)
        except StopIteration:
            sys.exit(f"floor{fl['n']}: more than 26 exits")
        kind = {"EXIT_HOLE": "hole", "EXIT_PORTAL": "portal"}.get(e.get("type"), "stairs")
        dest = (e["to_map"], e["to_x"], e["to_y"])
        back = by_tile.get(dest)
        two_way = back is not None and (back["to_map"], back["to_x"], back["to_y"]) == key
        note = f"{'two-way' if two_way else 'one-way'} to {dest[0]}({dest[1]},{dest[2]})"
        out[e["map"]].append((e["x"], e["y"], letter, gate(kind, key in doors), note))
        if two_way:
            lettered.add(dest)
            out[dest[0]].append((dest[1], dest[2], letter, gate(kind, dest in doors),
                                 f"two-way to {key[0]}({key[1]},{key[2]})"))
        else:
            rings[dest[0]].append((dest[1], dest[2], letter, kind))

    for c in fl["chests"]:
        out[c["map"]].append((c["x"], c["y"], "C" + c["id"].split("_")[1],
                              "locked" if c["locked"] else "chest", "chest"))
    for lv in fl["levers"]:
        out[lv["map"]].append((lv["x"], lv["y"], "L" + lv["id"].split("_")[1], "lever", "lever"))
    for s in fl["sconces"]:
        if s["id"] == "SCONCE_STATIC":
            color = s.get("color", "FLAME_NONE")[6:]
            out[s["map"]].append((s["x"], s["y"], "F", "F_" + color, f"{FLAME_LOOK.get(color, color.lower())} flame"))
        else:
            out[s["map"]].append((s["x"], s["y"], "S" + s["id"].split("_")[1], "sconce", "sconce"))
    for s in fl["signs"]:
        out[s["map"]].append((s["x"], s["y"], "!", "sign", "sign"))
    for npc in fl["npcs"]:
        boss = npc["tier"] == "S_TIER"
        out[npc["map"]].append((npc["x"], npc["y"], "B" if boss else "E", "boss" if boss else "elite",
                                npc["monster"][8:].lower().replace("_", " ")))
    placed = {(m, x, y) for m in out for x, y, *_ in out[m]}
    for d in fl["doors"]:
        key = (d["map"], d["x"], d["y"])
        if key in placed:
            continue
        if d["type"] == "DOOR_NEXT_LEVEL":
            out[d["map"]].append((d["x"], d["y"], "UP", "next", "stairs up and out, behind a door"))
        else:
            out[d["map"]].append((d["x"], d["y"], "D" + d["id"].split("_")[1], "door", "door"))
        placed.add(key)

    covered = placed | {(m, x, y) for m in rings for x, y, *_ in rings[m]}
    count = 0
    for m in sorted(fl["tiles"]):
        t = fl["tiles"][m]
        for x, y in sorted((xy for xy, v in t.items() if v[0] == SPECIAL), key=lambda p: (p[1], p[0])):
            if (m, x, y) not in covered:
                count += 1
                out[m].append((x, y, f"?{count}", "special", "special tile"))

    count = 0
    for m in sorted(fl["tiles"]):
        pinned = {(x, y) for x, y, *_ in out[m]}
        for group in clusters(hidden_tiles(fl, m) - pinned):
            count += 1
            anchor = min(group, key=lambda p: (sum(abs(p[0] - q[0]) + abs(p[1] - q[1]) for q in group),
                                               p[1], p[0]))
            out[m].append((*anchor, f"H{count}", "passage", f"hidden passage, {len(group)} tiles"))
    return out, rings


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def pin_svg(cx, cy, label, style, ring=False):
    shape, fill, stroke, width, text = STYLE[style]
    parts = []
    if ring:
        parts.append(f'<circle cx="{cx}" cy="{cy}" r="9" fill="none" stroke="{fill if fill != "#ffffff" else stroke}" '
                     f'stroke-width="1.8" stroke-dasharray="2.6 2"/>')
        text = fill if fill != "#ffffff" else stroke
    elif shape == "circle":
        parts.append(f'<circle cx="{cx}" cy="{cy}" r="9.5" fill="{fill}" stroke="{stroke}" stroke-width="{width}"/>')
    else:
        parts.append(f'<rect x="{cx - 10}" y="{cy - 10}" width="20" height="20" rx="4" '
                     f'fill="{fill}" stroke="{stroke}" stroke-width="{width}"/>')
    size = {1: 13, 2: 11, 3: 9}.get(len(label), 8)
    parts.append(f'<text x="{cx}" y="{cy + size * 0.36:.1f}" font-size="{size}" fill="{text}" '
                 f'text-anchor="middle" font-weight="bold">{esc(label)}</text>')
    return "".join(parts)


def render(fl, letter, pinset, rings):
    m = next(mp for mp in fl["maps"] if mp["map"] == letter)
    w, h, t = m["width"], m["height"], fl["tiles"][letter]
    hid = hidden_tiles(fl, letter)
    W, H = 2 * MARGIN + w * CELL, TOP + h * CELL + MARGIN
    ox, oy = MARGIN, TOP
    title = f"Floor {fl['n']}" + (f", map {letter}" if len(fl["maps"]) > 1 else "")
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
         f'font-family="{FONT}" role="img" aria-label="{title}">',
         f"<title>{title}</title>",
         "<defs>",
         f'<pattern id="grid" width="{CELL}" height="{CELL}" patternUnits="userSpaceOnUse" x="{ox}" y="{oy}">'
         f'<rect width="{CELL}" height="{CELL}" fill="{FLOOR}"/>'
         f'<path d="M{CELL} 0V{CELL}H0" fill="none" stroke="{GRID}" stroke-width="1"/></pattern>',
         f'<pattern id="hatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">'
         f'<rect width="6" height="6" fill="{INK}"/><rect width="2.6" height="6" fill="{HIDDEN}"/></pattern>',
         "</defs>",
         f'<rect width="{W}" height="{H}" fill="{PAPER}"/>',
         f'<text x="{ox}" y="18" font-size="13" font-weight="bold" fill="{INK}">{title}</text>',
         f'<rect x="{ox}" y="{oy}" width="{w * CELL}" height="{h * CELL}" fill="{INK}"/>']
    for y in range(h):
        x = 0
        while x < w:
            if t[(x, y)][0] != WALL and (x, y) not in hid:
                x0 = x
                while x < w and t[(x, y)][0] != WALL and (x, y) not in hid:
                    x += 1
                s.append(f'<rect x="{ox + x0 * CELL}" y="{oy + y * CELL}" width="{(x - x0) * CELL}" '
                         f'height="{CELL}" fill="url(#grid)"/>')
            else:
                x += 1
    edges = []
    for x, y in sorted(hid, key=lambda p: (p[1], p[0])):
        px, py = ox + x * CELL, oy + y * CELL
        s.append(f'<rect x="{px}" y="{py}" width="{CELL}" height="{CELL}" fill="url(#hatch)"/>')
        if (x, y - 1) not in hid:
            edges.append(f"M{px} {py}h{CELL}")
        if (x, y + 1) not in hid:
            edges.append(f"M{px} {py + CELL}h{CELL}")
        if (x - 1, y) not in hid:
            edges.append(f"M{px} {py}v{CELL}")
        if (x + 1, y) not in hid:
            edges.append(f"M{px + CELL} {py}v{CELL}")
    if edges:
        s.append(f'<path d="{"".join(edges)}" fill="none" stroke="{HIDDEN}" stroke-width="1.6" '
                 f'stroke-dasharray="3 2"/>')
    for i in range(w):
        for yy in (oy - 6, oy + h * CELL + 14):
            s.append(f'<text x="{ox + i * CELL + CELL / 2}" y="{yy}" font-size="9" fill="{MUTED}" '
                     f'text-anchor="middle">{i}</text>')
    for j in range(h):
        for xx, anchor in ((ox - 5, "end"), (ox + w * CELL + 5, "start")):
            s.append(f'<text x="{xx}" y="{oy + j * CELL + CELL / 2 + 3}" font-size="9" fill="{MUTED}" '
                     f'text-anchor="{anchor}">{j}</text>')
    for x, y, label, style in rings[letter]:
        s.append(pin_svg(ox + x * CELL + CELL / 2, oy + y * CELL + CELL / 2, label, style, ring=True))
    for x, y, label, style, _ in pinset[letter]:
        s.append(pin_svg(ox + x * CELL + CELL / 2, oy + y * CELL + CELL / 2, label, style))
    s.append("</svg>")
    return "\n".join(s) + "\n"


LEGEND = [
    ("tile", "floor", "Floor you can see"),
    ("tile", "wall", "Wall or black void"),
    ("tile", "hidden", "Hidden floor: looks like void or wall, but you can walk it"),
    ("passage", "H1", "Hidden passage, numbered on each floor"),
    ("start", "@", "Where you arrive on the floor"),
    ("stairs", "a", "Stairs or doorway; both ends share a letter"),
    ("gated", "b", "Stairs behind a door that opens later"),
    ("hole", "c", "Hole: drops you one way"),
    ("portal", "d", "Portal: sends you one way"),
    ("ring", "c", "Where a hole or portal lands you"),
    ("next", "DOWN", "Stairs down to the next floor"),
    ("next", "UP", "The stairs up and out, on floor 8"),
    ("chest", "C1", "Chest"),
    ("locked", "C4", "Locked chest (magic key or puzzle)"),
    ("lever", "L1", "Lever"),
    ("sconce", "S1", "Sconce, unlit until you or a puzzle light it"),
    ("F_RED", "F", "Burning flame (orange, green, or purple): relight your torch"),
    ("sign", "!", "Sign"),
    ("elite", "E", "Elite monster: see the floor's key"),
    ("boss", "B", "Floor boss"),
    ("door", "D5", "Door"),
    ("special", "?1", "Special tile: see the floor's key"),
]


def render_legend():
    row, W = 26, 520
    H = 30 + row * len(LEGEND)
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
         f'font-family="{FONT}" role="img" aria-label="Map legend">',
         "<title>Map legend</title>",
         "<defs>",
         f'<pattern id="hatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">'
         f'<rect width="6" height="6" fill="{INK}"/><rect width="2.6" height="6" fill="{HIDDEN}"/></pattern>',
         "</defs>",
         f'<rect width="{W}" height="{H}" fill="{PAPER}"/>',
         f'<text x="16" y="20" font-size="13" font-weight="bold" fill="{INK}">Legend</text>']
    for i, (style, label, text) in enumerate(LEGEND):
        cy = 30 + i * row + row / 2
        cx = 16 + CELL / 2
        if style == "tile":
            fill = {"floor": FLOOR, "wall": INK, "hidden": "url(#hatch)"}[label]
            line = f'stroke="{HIDDEN}" stroke-dasharray="3 2"' if label == "hidden" else f'stroke="{GRID}"'
            s.append(f'<rect x="16" y="{cy - CELL / 2}" width="{CELL}" height="{CELL}" fill="{fill}" '
                     f'{line} stroke-width="1.4"/>')
        elif style == "ring":
            s.append(pin_svg(cx, cy, label, "hole", ring=True))
        else:
            s.append(pin_svg(cx, cy, label, style))
        s.append(f'<text x="{16 + CELL + 12}" y="{cy + 4}" font-size="12" fill="{INK}">{esc(text)}</text>')
    s.append("</svg>")
    return "\n".join(s) + "\n"


def outputs():
    """{file name: SVG text} for every map and the legend."""
    bins = incbins()
    out = {"legend.svg": render_legend()}
    for n in FLOORS:
        fl = read_floor(n, bins)
        pinset, rings = pins(fl)
        for m in fl["maps"]:
            name = f"floor-{n}.svg" if len(fl["maps"]) == 1 else f"floor-{n}{m['map'].lower()}.svg"
            out[name] = render(fl, m["map"], pinset, rings)
    return out


FIXTURE_C = """
static const Map maps[] = {
  { MAP_A, BANK_17, fixture_map, 3, 1 },
  { END },
};
static const Chest chests[] = {
  /* { CHEST_9, MAP_A, 9, 9, false, false, NULL, NULL }, commented out */
  { CHEST_1, MAP_A, 2, 0, true, true, str_one, items_one },
  { END },
};
static const Exit exits[] = {
  { MAP_A, 1, 0, MAP_A, 0, 0, UP, EXIT_STAIRS, &bank_floor2 },  // cross-floor
  { END },
};
static const Sign signs[] = {
  { MAP_A, 0, 0, UP, "Hi, there" },
  { END },
};
static const Lever levers[] = {
  { END },
};
static const Door doors[] = {
  { END }
};
static const Sconce sconces[] = {
  { SCONCE_STATIC, MAP_A, 2, 0, true, FLAME_RED },
  { END }
};
static const NPC npcs[] = {
  { END }
};
"""
FIXTURE_TILES = bytes([0x40, 0x80, 0x85, 0x03, 0x00, 0x00])


def self_test():
    """The parser and decoder prove themselves on fixtures first, so a change
    to a struct's layout or the tile format fails loudly instead of drawing
    empty maps."""
    t = parse_tables(strip_comments(FIXTURE_C), "fixture")
    want = {"maps": [("A", "fixture_map", 3, 1)], "chests": [("CHEST_1", 2, True, True)],
            "exits": [("A", 1, 0, "&bank_floor2")], "signs": [('"Hi, there"',)],
            "sconces": [("SCONCE_STATIC", "FLAME_RED")]}
    got = {"maps": [(r["map"], r["data"], r["width"], r["height"]) for r in t["maps"]],
           "chests": [(r["id"], r["x"], r["locked"], r["magic_key"]) for r in t["chests"]],
           "exits": [(r["map"], r["x"], r["y"], r["to_floor"]) for r in t["exits"]],
           "signs": [(r["message"],) for r in t["signs"]],
           "sconces": [(r["id"], r["color"]) for r in t["sconces"]]}
    if got != want or t["levers"] or t["npcs"]:
        sys.exit(f"table parser self-test failed:\n  got  {got}\n  want {want}")
    tiles = decode(FIXTURE_TILES, 3, 1)
    if tiles != {(0, 0): (GROUND, 0, True), (1, 0): (EXIT, 5, False), (2, 0): (WALL, 0, False)}:
        sys.exit(f"tile decoder self-test failed: {tiles}")


def main():
    unknown = [a for a in sys.argv[1:] if a not in ("--check", "--list")]
    if unknown:
        sys.exit(f"unknown option {' '.join(unknown)}: use --check, --list, or no option")
    self_test()
    if "--list" in sys.argv:
        bins = incbins()
        for n in FLOORS:
            fl = read_floor(n, bins)
            pinset, rings = pins(fl)
            for m in sorted(pinset):
                print(f"floor {n} map {m}: {len(hidden_tiles(fl, m))} hidden tiles")
                for x, y, label, style, note in sorted(pinset[m], key=lambda p: (p[3], p[2])):
                    print(f"  {label:4} ({x},{y}) {style}: {note}")
                for x, y, label, style in rings[m]:
                    print(f"  ring {label} ({x},{y}) {style} landing")
        return
    files = outputs()
    if "--check" in sys.argv:
        stale = [f for f, text in sorted(files.items())
                 if not os.path.exists(os.path.join(OUT, f)) or open(os.path.join(OUT, f)).read() != text]
        for f in stale:
            print(f"stale: docs/maps/{f}")
        sys.exit(1 if stale else 0)
    os.makedirs(OUT, exist_ok=True)
    for f, text in sorted(files.items()):
        with open(os.path.join(OUT, f), "w") as fh:
            fh.write(text)
    print(f"wrote {len(files)} files to docs/maps/")


if __name__ == "__main__":
    main()
