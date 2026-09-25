"""Shared helpers for the suites that play the game, on top of drive.py:
which floor the game is on, loading a floor afresh, the tiles its scripts
have repainted and the palettes the screen draws a tile in, the player's
state as a log line, reading a textbox page by
page and checking it against the text oracle, casting an ability, the
sounds the game plays and which of a round's blows were critical hits, and
savestate checkpoints.
"""
import re, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from drive import *  # Game, Floor, SYM, GS, MS, DIR, DIRBTN, POFF, ITEM, log, etc.

# Savestates are per-run and stale against any later ROM, so they live in an
# ignored subdirectory rather than traveling with the tooling.
CKPT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ckpt")
PL = SYM["player"]
NOI_TEXT = open(NOI).read()
# Every sound function sound.h declares that the build links in.
SOUNDS = [name for name in re.findall(r"void (sfx_\w+)\(void\)",
                                      open(os.path.join(REPO, "src", "sound.h")).read())
          if f"DEF _{name} " in NOI_TEXT]

# `floor_bank` (src/map.c, file-scope static) holds the ROM address of the
# active floor's FloorBank struct. It is non-banked WRAM, so reading it and
# comparing against SYM["bank_floorN"] reproduces map_floor_index()'s own
# comparison (src/map.c) without executing any game code.
FLOOR_BANK_PTR = STATIC["map.floor_bank"]
FLOOR_BANKS = {n: SYM[f"bank_floor{n}"] for n in range(1, 9)}
BANK_TO_FLOOR = {v: k for k, v in FLOOR_BANKS.items()}


def current_floor(g):
    """Which floor (1-8) the live game is on, per the engine's own
    floor_bank pointer rather than the position, which a lost fight moves to
    floor 1's spawn tile without saying so."""
    return BANK_TO_FLOOR.get(g.rd16(FLOOR_BANK_PTR))


def reenter_floor(g, floor, x, y, map_id=0):
    """Load `floor` afresh with the hero standing at (x, y) on map `map_id`,
    the way its stairs or the trip back down after a death do: load_exit() runs
    set_active_floor(), which resets the floor's objects and tile overrides,
    and the floor's on_init runs on the next frame. This fills in active_exit
    (an Exit in src/map.h, 10 bytes) and enters MAP_STATE_TELEPORT, as a
    floor's teleport() call does, so the screen fades out and back in as it
    would on the stairs. The hero arrives standing still, so no step and no
    random encounter follow. Returns whether the floor loaded."""
    ex = SYM["active_exit"]
    exit_stairs = 1                                  # ExitType, src/map.h
    for off, v in ((3, map_id), (4, x), (5, y), (6, DIR["HERE"]), (7, exit_stairs)):
        g.wr8(ex + off, v)
    g.wr16(ex + 8, FLOOR_BANKS[floor])
    g.set("map_state", MS["TELEPORT"])
    loaded = g.wait_map_idle(600) and current_floor(g) == floor
    g.tick(4)                                        # on_init's frame
    return loaded and g.pos() == (x, y)


TILE_OVERRIDES = STATIC["map.tile_override_hashtable"]


def tile_overrides(g):
    """{(map_id, x, y): (tile, palette)} for every tile the floor's scripts
    have repainted since it loaded: src/map.c's tile_override_hashtable, 64
    entries of map_id, x, y, tile and palette, where map_id 0xFF is empty."""
    out = {}
    for k in range(64):
        e = TILE_OVERRIDES + 5 * k
        if g.rd8(e) != 0xFF:
            out[(g.rd8(e), g.rd8(e + 1), g.rd8(e + 2))] = (g.rd8(e + 3), g.rd8(e + 4))
    return out


def vram_byte(g, addr, bank):
    """One byte of VRAM `bank`, leaving VBK as the game had it."""
    vbk = g.pb.memory[0xFF4F]
    g.pb.memory[0xFF4F] = bank
    try:
        return g.pb.memory[addr]
    finally:
        g.pb.memory[0xFF4F] = vbk & 1


def screen_cells(g, tx, ty):
    """The four BG map addresses (2x2) that draw map tile (tx, ty) on the
    first map, following src/map.c's get_vram_at() ring mapping."""
    sx, sy = g.get("map_scroll_x"), g.get("map_scroll_y")
    mx, my = g.get("map_x"), g.get("map_y")
    mx, my = (mx - 256 if mx > 127 else mx), (my - 256 if my > 127 else my)
    col = ((sx >> 3) + (tx - mx) * 2) & 31
    row = ((sy >> 3) + (ty - my) * 2) & 31
    return [0x9800 + ((row + dr) & 31) * 32 + ((col + dc) & 31) for dr in (0, 1) for dc in (0, 1)]


def drawn_palettes(g, tx, ty):
    """The palettes the screen draws map tile (tx, ty) in, from the BG
    attributes in VRAM bank 1. What the player sees can differ from
    tile_overrides() when a repaint misses the screen."""
    return sorted({vram_byte(g, a, 1) & 7 for a in screen_cells(g, tx, ty)})


def inv_str(g):
    inv = SYM["inventory"]
    held = {n: g.rd8(inv + 4 * i + 1) for i, n in enumerate(ITEM_NAMES)
            if g.rd8(inv + 4 * i + 1)}
    return f"{held or 'empty'} keys={g.rd8(PL+POFF['magic_keys'])}"


def player_str(g):
    return (f"level={g.rd8(PL+POFF['level'])} "
            f"hp={g.rd16(PL+POFF['hp'])}/{g.rd16(PL+POFF['max_hp'])} "
            f"sp={g.rd16(PL+POFF['sp'])}/{g.rd16(PL+POFF['max_sp'])} "
            f"atk={g.rd8(PL+POFF['atk'])} def={g.rd8(PL+POFF['def_'])} "
            f"torch_color={g.rd8(PL+POFF['torch_color'])} "
            f"torch_gauge={g.rd8(PL+POFF['torch_gauge'])} "
            f"inventory: {inv_str(g)}")


def textbox_colors(g):
    """Distinct colors inside the open textbox's text area, the same region
    t20_hud_and_menu_palettes.py samples. Reading pixels rather than tile ids
    is the point: a broken palette leaves the right tiles on screen in the
    wrong colors, white on white, which a tilemap read alone cannot see. This
    renders a frame first, since the framebuffer is otherwise stale."""
    g.tick(1, True)
    px = g.pb.screen.ndarray
    region = px[104:136, 8:152, :3]
    return {tuple(int(v) for v in region[r, c])
            for r in range(0, region.shape[0], 2)
            for c in range(0, region.shape[1], 2)}


# text_writer.state (text_writer.h): the struct's first seven fields are
# function pointers, so the state byte sits at offset 14. DONE is the last
# character written, PAGE_WAIT the end of a page with more to come.
TEXT_WRITER_STATE = SYM["text_writer"] + 14
WRITER_DONE, WRITER_PAGE_WAIT = 0, 1


def read_textbox(g, max_pages=6, shot=None):
    """Read a textbox's actual text (sign, chest message, etc.) instead of
    blind-dismissing it the way Game.interact() does. Call this right after
    pressing A on a sign or object; it waits for the box, reads every page
    from the window tilemap, advances through all of them, and leaves the map
    idle. Every page also gets a rendered-pixel check, and a page drawn in
    one color (text in the tilemap but invisible on screen, white on white)
    logs a loud failure. Returns a list of page strings.

    A box can hand over to a fight when it closes -- an NPC's pre-fight line
    is map_textbox_with_action() -- so this stops the moment the game leaves
    the map, rather than pressing A into the battle menu. `shot` names a
    screenshot of the first page, taken once it has finished typing."""
    def on_map():
        return g.gs() == GS["WORLD_MAP"]

    def snapshot():
        # Exactly the textbox's own region (textbox.c's init_textbox():
        # set_origin(VRAM_WINDOW, 1, 1), set_size(18, 4)) -- not the whole
        # 32x32 window tilemap. The window layer is only ~20x18 tiles
        # visible on screen at once; tiles outside that (e.g. the pause
        # menu's own rows, drawn elsewhere in the same buffer) still sit in
        # VRAM and a full-grid read picks them up as if they were part of
        # the textbox, corrupting every capture with unrelated HUD text.
        lines = []
        for row in range(1, 5):
            s = g.window_text(1, row, 18).strip()
            if s and any(c.isalnum() for c in s):
                lines.append(s)
        return " ".join(lines)

    pages = []
    for _ in range(max_pages):
        opened = False
        for _ in range(90):
            if not on_map():
                break
            ms = g.ms()
            if ms in (MS["TEXTBOX"], MS["TEXTBOX_OPEN"]):
                opened = True
                break
            if ms == MS["WAITING"]:
                break
            g.tick(5)
        if not opened:
            break
        # The text writer types one character at a time (text_writer.c), so a
        # fixed wait can sample mid-animation and read a truncated line as if
        # it were the whole page. Nor is two samples agreeing enough: the
        # writer pauses at every line end, long enough to pass for a finished
        # page ("You look in the"), and an NPC's box sits blank before its
        # writer starts. So the page is finished when the writer says so.
        # While the box is still opening the writer reads DONE from the last
        # text and the window still holds that text, so the box must also be
        # fully open and the page non-empty.
        page = snapshot()
        for _ in range(120):
            if g.ms() not in (MS["TEXTBOX"], MS["TEXTBOX_OPEN"]):
                break
            if (page and g.ms() == MS["TEXTBOX"]
                    and g.rd8(TEXT_WRITER_STATE) in (WRITER_DONE, WRITER_PAGE_WAIT)):
                break
            g.tick(4)
            page = snapshot()
        colors = textbox_colors(g)
        if shot and page and not pages:
            g.shot(shot, render=False)
        if page and len(colors) <= 1:
            log(f"  !! PIXEL CHECK FAILED: textbox renders in {len(colors)} color(s) "
                f"{sorted(colors)} -- text present in the tilemap but not visibly on "
                f"screen (white on white)")
        if page and (not pages or page != pages[-1]):
            pages.append(page)
        g.pb.button_press("a"); g.tick(2); g.pb.button_release("a")
        g.wait_for(lambda: g.ms() != MS["TEXTBOX"], 90)
        g.tick(4)
    for _ in range(15):
        if not on_map() or g.ms() == MS["WAITING"]:
            break
        g.press("a", wait=10)
    if on_map():
        g.wait_map_idle(300)
    return pages


def cstr(g, addr, n=128):
    """A C string from memory, non-printing bytes as spaces, runs collapsed:
    battle_pre_message and battle_post_message read as the screen shows them."""
    out = []
    for i in range(n):
        c = g.rd8(addr + i)
        if c == 0:
            break
        out.append(chr(c) if 32 <= c < 127 else " ")
    return " ".join("".join(out).split())


BATTLE_MENU = 2                       # battle_state at the player's command menu


def at_menu(g):
    return g.gs() == GS["BATTLE"] and g.rd8(SYM["battle_state"]) == BATTLE_MENU


def keep_alive(g, hp=9999, sp=99):
    """Full bars every round, for a suite that needs the hero to outlast the
    fight it is watching."""
    for off in ("hp", "max_hp"):
        g.wr16(PL + POFF[off], hp)
    for off in ("sp", "max_sp"):
        g.wr16(PL + POFF[off], sp)


def sounds_heard(g):
    """A list that gains (battle pre line, sound name) each time one of the
    game's sounds starts, from now until the game closes, through a hook on
    every function in SOUNDS. PyBoy takes one hook per address, so every
    suite listens through this one list: the first call installs the hooks,
    and later calls return the same list."""
    if getattr(g, "sound_log", None) is None:
        heard = g.sound_log = []
        pre = SYM["battle_pre_message"]
        for name in SOUNDS:
            g.pb.hook_register(*banked(name), lambda sound: heard.append((cstr(g, pre), sound)), name)
    return g.sound_log


def round_messages(g, read=None):
    """Every (pre, post, value) the battle shows between now and the next
    command menu, pressing A through the message boxes. `value` is read(g) at
    the moment the text changed, by default battle_sfx, the sound that text is
    about to play. Polled every frame, because an ability that skips its post
    message plays its sound six frames into its text and battle.c then clears
    the pointer. A line counts once it has read the same on two frames
    running, since a frame boundary can fall inside the sprintf writing it.
    An A press on a fresh line can finish it in the frame it appears, and its
    sound then plays and clears before that read, so a battle_sfx of 0 falls
    back to the sound sounds_heard() caught under the same line. A pair with
    no pre line is not a line, such as the buffers battle_menu_goto() empties."""
    heard = sounds_heard(g) if read is None else None
    mark = len(heard) if heard is not None else 0
    read = read or (lambda g: g.rd16(SYM["battle_sfx"]))
    pre, post = SYM["battle_pre_message"], SYM["battle_post_message"]
    seen, last, out = None, None, []
    for frame in range(4000):
        if g.gs() != GS["BATTLE"] or at_menu(g):
            break
        pair = (cstr(g, pre), cstr(g, post))
        if pair != seen and pair == last and pair[0]:
            seen = pair
            value = read(g)
            if heard is not None and not value:
                value = next((SYM[sound] for line, sound in heard[mark:] if line == pair[0]), 0)
            out.append((pair[0], pair[1], value))
        last = pair
        if frame % 10 == 0:
            g.pb.button_press("a")
        elif frame % 10 == 2:
            g.pb.button_release("a")
        g.tick(1)
    g.pb.button_release("a")
    return out


def cast(g, row, wait=20):
    """Select ability `row` in battle, pressing exactly the confirms the menu
    asks for: drive.cast_ability() without its trailing press, which after an
    ability that skips its post message lands on the next turn's menu. `wait`
    is the frames idled after each confirm; a caller about to read an
    all-target ability's round frame by frame passes 1."""
    return cast_ability(g, row, confirm_post=False, wait=wait)


def banked(name):
    """(bank, address) of a symbol, which SYM keeps only as the address."""
    full = int(re.search(r"DEF _" + name + r" 0x([0-9A-Fa-f]+)", NOI_TEXT).group(1), 16)
    return full >> 16, full & 0xFFFF


def critical_watch(g):
    """A list that gains the battle's pre line each time damage_player()
    rolls a critical hit on the hero, from now until the game closes. It hooks
    damage_player()'s one `SFX_CRIT;` line through that line's label in the
    .noi, since a monster's own line can write over "CRITICAL HIT!" and leave
    nothing on screen to say a blow was one."""
    src = open(os.path.join(REPO, "src", "monster.core.c")).read().split("\n")
    line = next(k + 1 for k, text in enumerate(src) if text.strip() == "SFX_CRIT;")
    label = re.search(rf"DEF C\$monster\.core\.c\${line}\$\S* 0x([0-9A-Fa-f]+)", NOI_TEXT)
    full = int(label.group(1), 16)
    seen = []
    try:
        g.pb.hook_deregister(full >> 16, full & 0xFFFF)
    except Exception:
        pass
    g.pb.hook_register(full >> 16, full & 0xFFFF,
                       lambda _: seen.append(cstr(g, SYM["battle_pre_message"])), None)
    return seen


def check_oracle(pages, oracle, note):
    """The text oracle's check of `pages` against oracle=(namespace, key[, params])."""
    ns, key, params = (oracle + (None,))[:3] if len(oracle) < 3 else oracle
    from text_oracle import check_textbox
    return check_textbox(ns, key, pages, params, note=note)


def save_checkpoint(g, name):
    os.makedirs(CKPT_DIR, exist_ok=True)
    path = os.path.join(CKPT_DIR, name)
    with open(path, "wb") as fh:
        g.pb.save_state(fh)
    log(f"  checkpoint saved: {path}")
    return path


def load_checkpoint(g, name):
    path = os.path.join(CKPT_DIR, name)
    with open(path, "rb") as fh:
        g.pb.load_state(fh)
    g.tick(4)
