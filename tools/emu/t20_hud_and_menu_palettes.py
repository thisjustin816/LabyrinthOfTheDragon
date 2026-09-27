"""T20 - the pause menu borrows palettes and has to give them back.

Textboxes after the menu: hide_map_menu() restores BG palette 7 from
`textbox_palette`, which is bank 2 data. core.load_bg_palette() lives in ROM0
and dereferences the pointer with the caller's bank still mapped, so a call
from map.menu.c's bank 30 reads that bank's 0xFF padding instead: an
all-white palette 7 that draws every world-map textbox white on white until
a reload. A textbox after a menu round trip has to render in the colors it
had before.

The hand cursor: its sprites use palette 4, TORCH_GAUGE_PALETTE, so the menu
has to load the cursor's own colors there while it is open, or the hand wears
whatever flame the torch carries, and put the gauge's colors back when it
closes.

Also covers the magic key HUD: the placement its init draws on a floor load
matches the placement its per-frame update draws, and the count shows a "*"
in place of any number past 9.
"""
from lotd import *

chk = Checker("t20_hud_and_menu_palettes")
PL, MM = SYM["player"], SYM["map_menu"]
MENU_ROW_1, MENU_ROW_2, MSG_ROW = 28, 29, 30
CURSOR_SPRITE = 16
OAM = 0xFE00
SHADOW_OAM = SYM["shadow_OAM"]

tmpl, pos, d = make_floor_template(1, hero=0, has_torch=True, tag="t20tmpl")
g = Game(tag="t20", sram=tmpl + bytes(SLOT_STRIDE - SAVE_SIZE))
assert g.boot_to_save_select(), "no save select"
g.tick(10)
g.save_select_pick(0)
chk("T20 load floor 1 save -> map idle", g.wait_map_idle(900), f"gs={g.gs()} ms={g.ms()}")
g.tick(20)


def sprite(n):
    """(y, x, tile, attr) straight out of OAM."""
    b = OAM + 4 * n
    return tuple(g.rd8(b + k) for k in range(4))


def shadow_sprite(n):
    """(y, x, tile, attr) from the shadow OAM the game writes and the next
    VBlank copies out, so it holds what the last game frame drew."""
    b = SHADOW_OAM + 4 * n
    return tuple(g.rd8(b + k) for k in range(4))


def sprite_tile_bytes(bank, tile):
    """A sprite tile's 16 bytes from VRAM `bank`."""
    vbk = g.pb.memory[0xFF4F]
    g.pb.memory[0xFF4F] = bank
    try:
        return [g.pb.memory[0x8000 + 16 * tile + k] for k in range(16)]
    finally:
        g.pb.memory[0xFF4F] = vbk & 1


def textbox_at(x, y):
    """Face the tile at (x, y) and press A, leaving the box open."""
    for nx, ny, dd in ((x, y + 1, "UP"), (x, y - 1, "DOWN"),
                       (x - 1, y, "RIGHT"), (x + 1, y, "LEFT")):
        g.teleport(nx, ny, dd); g.tick(8)
        if g.pos() != (nx, ny):
            continue
        g.press("a", wait=12)
        if g.wait_for(lambda: g.ms() in (MS["TEXTBOX"], MS["TEXTBOX_OPEN"]), 200):
            g.tick(120)
            return True
    return False


def textbox_colors():
    """Distinct colors inside the open textbox's text area.

    The box occupies window rows 12-17 at window y 96, so its four text rows
    start 8px in. Reading pixels rather than tile ids is the point: a broken
    palette leaves the right tiles on screen in the wrong colors, which a
    tilemap check cannot see.

    Game.tick() renders only when asked, so the frame has to be drawn before
    the buffer means anything -- an unrendered buffer reads as flat white and
    would fail this check for the wrong reason.
    """
    g.tick(1, True)
    px = g.pb.screen.ndarray
    region = px[104:136, 8:152, :3]
    return {tuple(int(v) for v in region[r, c])
            for r in range(0, region.shape[0], 2)
            for c in range(0, region.shape[1], 2)}


def close_textbox():
    for _ in range(10):
        g.press("a", wait=30)
        if g.ms() == MS["WAITING"]:
            return True
    return False


# --- the magic key HUD: top-right corner, sharing the gauge's top edge
g.wr8(PL + POFF["got_magic_key"], 1)
g.wr8(PL + POFF["magic_keys"], 3)
g.wr8(PL + POFF["torch_gauge"], 32)
g.tick(30)
key_top, key_bot, qty = sprite(29), sprite(30), sprite(31)
gauge = sprite(24)
print("gauge", gauge, "key", key_top, key_bot, "qty", qty)
chk("T20 key HUD shares the torch gauge's top edge", key_top[0] == gauge[0],
    f"key y={key_top[0]} gauge y={gauge[0]}")
chk("T20 key graphic's halves are 8px apart", key_bot[0] == key_top[0] + 8,
    f"{key_top[0]} / {key_bot[0]}")
chk("T20 key HUD sits in the right half of the screen, on screen",
    key_top[1] > 80 and qty[1] + 8 <= 168, f"key x={key_top[1]} qty x={qty[1]}")
chk("T20 quantity reads 3", qty[2] == 0x30 + 3, f"tile={qty[2]:#04x}")
g.shot("hud_keys_corner")

# One digit can't show 10 or more, so the count shows a "*" instead: tile 0x3A,
# MAGIC_KEY_MANY in src/map.h, drawn after the digits in objects.png.
MANY = 0x3A
# Ten keys would read 0x30 + 10, which is MANY itself, so 10 cannot tell a
# digit from the "*"; 11, 12, and 15 can.
for keys, want in ((9, 0x30 + 9), (11, MANY), (12, MANY), (15, MANY)):
    g.wr8(PL + POFF["magic_keys"], keys)
    g.tick(4)
    chk(f"T20 quantity with {keys} keys shows tile {want:#04x}", sprite(31)[2] == want,
        f"tile={sprite(31)[2]:#04x}")
chk("T20 the count's sprites draw from VRAM bank 1", sprite(31)[3] & 0x08,
    f"attr={sprite(31)[3]:#04x}")
chk("T20 the \"*\" tile holds a drawn glyph", any(sprite_tile_bytes(1, MANY)),
    str(sprite_tile_bytes(1, MANY)))
g.shot("hud_keys_many")
g.wr8(PL + POFF["magic_keys"], 3)
g.tick(4)

# Loading a save runs the HUD's init and sets the map idle in one frame; the
# per-frame update first runs on the frame after. So the shadow OAM on the
# first idle frame is the init's placement, and 40 frames on it is the
# update's. The keys have to be in the save for the init to draw them.
chk("T20 keys saved", menu_save(g, chk, "T20 key HUD save"))
g = g.power_cycle(tag="t20b")
assert g.boot_to_save_select(), "no save select after the power cycle"
g.tick(10)
chk("T20 save select opens on slot 1", g.get("cursor") == 0, str(g.get("cursor")))
g.pb.button_press("a")
for frame in range(900):
    if g.gs() == GS["WORLD_MAP"] and g.ms() == MS["WAITING"]:
        break
    g.tick(1)
    if frame == 1:
        g.pb.button_release("a")
g.pb.button_release("a")
init_place = (shadow_sprite(29), shadow_sprite(30), shadow_sprite(31))
g.tick(40)
after_place = (shadow_sprite(29), shadow_sprite(30), shadow_sprite(31))
print("key HUD init", init_place, "update", after_place)
# The init draws the count as 0 and only the update writes the real digit, so
# a 0 here proves the sample came before any update ran.
chk("T20 the first idle frame is the init's, before any update",
    init_place[2][2] == 0x30 and after_place[2][2] == 0x30 + 3,
    f"count tile {init_place[2][2]:#04x} then {after_place[2][2]:#04x}")
chk("T20 the HUD's init draws the saved keys", init_place[0][0] != 0 and init_place[2][0] != 0,
    str(init_place))
chk("T20 key HUD does not move between the HUD's init and its update",
    [sp[:2] for sp in init_place] == [sp[:2] for sp in after_place],
    f"{init_place} vs {after_place}")
g.tick(10)

# --- a textbox before the menu is ever opened
chk("T20 reached floor 1's locked chest", textbox_at(2, 2), f"pos={g.pos()}")
rows = [g.window_text(1, 1 + r, 18).rstrip() for r in range(4)]
chk("T20 the locked chest says so", "locked" in " ".join(rows).lower(), repr(rows))
fresh = textbox_colors()
chk("T20 a fresh textbox renders in more than one color", len(fresh) > 1,
    str(sorted(fresh)))
g.shot("textbox_before_menu")
chk("T20 textbox closes", close_textbox(), f"ms={g.ms()}")

# --- open and close the pause menu, then look at a textbox again
g.press("start", wait=20)
chk("T20 START opens the pause menu", g.ms() == MS["MENU"], str(g.ms()))

# The hand cursor's colors must not be the torch's. Floor 1 has lit static
# sconces in two colors -- red in the main corridor, blue in the boss room --
# so the torch can be relit for real rather than by poking torch_color, which
# would not reload the palette and would make this check pass either way.
def hand_colors():
    """Colors inside the 16x16 block the four hand sprites occupy.

    The sprite is re-read each time: the block moves with the cursor, and a
    stale position would sample menu backdrop instead of the hand.
    """
    g.tick(1, True)
    y, x, _, _ = sprite(CURSOR_SPRITE)
    px = g.pb.screen.ndarray
    region = px[y - 16:y, x - 8:x + 8, :3]
    return {tuple(int(v) for v in region[r, c])
            for r in range(region.shape[0]) for c in range(region.shape[1])}


def gauge_colors():
    """Colors inside the four torch gauge body sprites' 8x8 boxes."""
    g.tick(1, True)
    px = g.pb.screen.ndarray
    out = set()
    for n in range(25, 29):
        y, x, _, _ = sprite(n)
        region = px[y - 16:y - 8, x - 8:x, :3]
        out |= {tuple(int(v) for v in region[r, c])
                for r in range(region.shape[0]) for c in range(region.shape[1])}
    return out


def light_torch_at(x, y, label):
    """Walk up to a lit sconce and take a flame off it."""
    g.press("b", wait=20)                   # out of the menu if it is open
    g.wait_map_idle(300); g.tick(10)
    for nx, ny, dd in ((x, y + 1, "UP"), (x, y - 1, "DOWN"),
                       (x - 1, y, "RIGHT"), (x + 1, y, "LEFT")):
        g.teleport(nx, ny, dd); g.tick(8)
        if g.pos() != (nx, ny):
            continue
        g.press("a", wait=20); g.tick(20)
        if g.rd8(PL + POFF["torch_gauge"]):
            print(f"{label}: torch color {g.rd8(PL + POFF['torch_color'])} "
                  f"gauge {g.rd8(PL + POFF['torch_gauge'])}")
            return True
    return False


g.press("b", wait=20); g.wait_map_idle(300); g.tick(10)
chk("T20 lit the torch at the red sconce", light_torch_at(6, 13, "red sconce"),
    f"color={g.rd8(PL + POFF['torch_color'])}")
red_flame = g.rd8(PL + POFF["torch_color"])
g.press("start", wait=20); g.tick(10)
hand_red = hand_colors()
g.shot("menu_cursor_red_torch")

chk("T20 lit the torch at the blue sconce", light_torch_at(11, 3, "blue sconce"),
    f"color={g.rd8(PL + POFF['torch_color'])}")
blue_flame = g.rd8(PL + POFF["torch_color"])
chk("T20 the two sconces really are different colors", red_flame != blue_flame,
    f"red={red_flame} blue={blue_flame}")
gauge_blue = gauge_colors()
g.press("start", wait=20); g.tick(10)
hand_blue = hand_colors()
g.shot("menu_cursor_blue_torch")

chk("T20 the hand looks the same whatever color the torch is",
    hand_red == hand_blue,
    f"red={sorted(hand_red)} blue={sorted(hand_blue)}")
# The cursor palette is white/black/dark gray, so pure white and pure black
# both appear; no torch flame palette contains either.
chk("T20 and wears the cursor's own white-on-black colors",
    (248, 248, 248) in hand_blue and (0, 0, 0) in hand_blue,
    str(sorted(hand_blue)))

# --- the quit confirmation is a YES / NO pick, not a key/value line
g.press("right", wait=10); g.press("down", wait=10)
g.press("a", wait=16)
row1 = g.window_text(0, MENU_ROW_1, 20)
row2 = g.window_text(0, MENU_ROW_2, 20)
chk("T20 the quit prompt asks on the top option row", "QUIT THE GAME?" in row1,
    repr(row1))
chk("T20 and answers on the bottom one", "YES" in row2 and "NO" in row2,
    repr(row2))
chk("T20 the hand stays visible for the pick", sprite(CURSOR_SPRITE)[0] != 0,
    str(sprite(CURSOR_SPRITE)))
g.press("a", wait=16)                       # A on NO backs out
chk("T20 A on NO puts the options back", "QUIT" in g.window_text(0, MENU_ROW_2, 20),
    repr(g.window_text(0, MENU_ROW_2, 20)))

g.press("b", wait=20); g.wait_map_idle(300); g.tick(20)
chk("T20 back on the map after the menu", g.ms() == MS["WAITING"], str(g.ms()))

# The torch gauge's palette must be back too, or the gauge wears the cursor's
# white and black.
gauge_after = gauge_colors()
chk("T20 the torch gauge wears its own colors again once the menu closes",
    gauge_after == gauge_blue, f"before={sorted(gauge_blue)} after={sorted(gauge_after)}")
chk("T20 reached the boss NPC for a second textbox", textbox_at(12, 5),
    f"pos={g.pos()}")
rows = [g.window_text(1, 1 + r, 18).rstrip() for r in range(4)]
chk("T20 the boss brushes the player off", any(r for r in rows), repr(rows))
after = textbox_colors()
chk("T20 a textbox after a menu round trip still renders in more than one color",
    len(after) > 1, str(sorted(after)))
chk("T20 and in the same colors as before the menu", after == fresh,
    f"before={sorted(fresh)} after={sorted(after)}")
g.shot("textbox_after_menu")
close_textbox()

g.close()
chk.summary()
