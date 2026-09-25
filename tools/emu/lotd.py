"""Headless PyBoy harness for the Labyrinth of the Dragon emulator suites: boot,
input, game-state waits, tilemap text, screenshots, save files, and checks."""
import os
from pyboy import PyBoy

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))          # tools/emu -> repo root
ROM = os.environ.get("LOTD_ROM", os.path.join(REPO, "LabyrinthOfTheDragon.gbc"))
SHOTS = os.environ.get("LOTD_SHOTS", os.path.join(HERE, "shots"))
os.makedirs(SHOTS, exist_ok=True)

# The .noi is a side file of the symbol build, so it sits next to the ROM and is
# gitignored. LOTD_NOI points at one somewhere else.
NOI = os.environ.get("LOTD_NOI") or os.path.splitext(ROM)[0] + ".noi"


def load_noi(path):
    syms = {}
    for line in open(path):
        parts = line.split()
        if len(parts) == 3 and parts[0] == "DEF" and parts[1].startswith("_"):
            name = parts[1][1:]
            addr = int(parts[2], 16)
            syms[name] = addr & 0xFFFF if addr < 0x10000 else addr & 0x3FFF | 0x4000
    return syms


def load_statics(path):
    """File-scope statics, keyed "module.name". SDCC writes one as
    "F<module>$<name>$0_0$<type>", so a static that shares a name with a
    global or with another file's static stays apart from both."""
    statics = {}
    for line in open(path):
        parts = line.split()
        if len(parts) == 3 and parts[0] == "DEF" and parts[1].startswith("F"):
            fields = parts[1][1:].split("$")
            if len(fields) >= 3 and fields[2] == "0_0":
                addr = int(parts[2], 16)
                statics[f"{fields[0]}.{fields[1]}"] = addr & 0xFFFF if addr < 0x10000 else addr & 0x3FFF | 0x4000
    return statics


if not os.path.exists(NOI):
    raise RuntimeError(
        f"symbol file missing: {NOI}\n"
        "Build the ROM with symbols first: GBDK_DEBUG=ON make assets && GBDK_DEBUG=ON make")
# A plain `make` refreshes the ROM but not the .noi, and nothing downstream
# notices: make_floor_template patches a floor pointer read from these symbols
# straight into the ROM, so a moved address sends the game into garbage and it
# spins at full tilt instead of failing. The link step writes both files and
# the ROM lands a fraction of a second later, so the gap has to be wider than
# that; a stale .noi is a whole build behind, far past any slack this leaves.
NOI_STALE_GRACE = 10  # seconds
if os.path.getmtime(NOI) < os.path.getmtime(ROM) - NOI_STALE_GRACE:
    raise RuntimeError(
        f"symbol file is older than the ROM:\n  {NOI}\n  {ROM}\n"
        "Symbols moved when the ROM was rebuilt. Rebuild them too: "
        "GBDK_DEBUG=ON make assets && GBDK_DEBUG=ON make")
# Every "_"-prefixed symbol in the .noi, prefix dropped. Banked addresses are
# bank-relative, e.g. floor8 in bank 8 -> 0x4000-0x7FFF.
SYM = load_noi(NOI)
STATIC = load_statics(NOI)

# ItemId order from src/item.h. The inventory is Item[8] in this order, and the
# save holds one quantity byte per slot in the same order.
ITEM_NAMES = ["POTION", "ETHER", "REMEDY", "ATK_UP", "DEF_UP", "ELIXIR", "REGEN", "HASTE"]

GS = dict(TITLE=0, SAVE_SELECT=1, HERO_SELECT=2, WORLD_MAP=3, BATTLE=4,
          DEATH=5, CREDITS=6, NAME_ENTRY=7, TEST=0xFF)
MS = dict(INACTIVE=0, WAITING=1, MOVING=2, FADE_OUT=3, FADE_IN=4, LOAD_EXIT=5,
          EXIT_LOADED=6, LOAD=7, TEXTBOX_OPEN=8, TEXTBOX=9, INITIATE_BATTLE=10,
          START_BATTLE=11, FROM_BATTLE=12, MENU=13, TELEPORT=14, QUIT=15, CREDITS=16)
DIR = dict(HERE=0, DOWN=1, UP=2, LEFT=3, RIGHT=4)
DIRNAME = {v: k for k, v in DIR.items()}
DIRBTN = {DIR["UP"]: "up", DIR["DOWN"]: "down", DIR["LEFT"]: "left",
          DIR["RIGHT"]: "right"}

# SaveGame layout (SDCC: packed, 1-byte enums). Verified against a live dump.
SCRIPT_STATE_LEN = 12
SAVE_SIZE = 442 + (SCRIPT_STATE_LEN - 8)
SLOT_STRIDE = 512
SAVE_MAGIC = 0x4C44
SAVE_VERSION = 4
OFF = dict(magic=0, version=2, checksum=3, player=4, inventory=51,
           flag_pages=59, play_seconds=91, floor_index=93, map_id=94,
           map_x=95, map_y=96, hero_direction=97, flags_chest_open=98,
           flags_chest_locked=99, flags_lever_on=100, flags_lever_stuck=101,
           flags_door_locked=102, flags_sconce_lit=104, npc_visible=105,
           sconce_colors=106, script_state=114, overrides=114 + SCRIPT_STATE_LEN)
POFF = dict(name=0, player_class=8, ability_flags=9, level=10, exp=11,
            next_level_exp=13, message_speed=15, hp=16, max_hp=18, sp=20,
            max_sp=22, atk_base=24, atk=25, def_base=26, def_=27, matk_base=28,
            matk=29, mdef_base=30, mdef=31, agl_base=32, agl=33,
            aspect_immune=34, aspect_resist=35, aspect_vuln=36,
            debuff_immune=37, debuffs=38, buffs=39, has_torch=40,
            torch_gauge=41, torch_color=42, magic_keys=43, got_magic_key=44,
            special_flags=45, trip_turns=46)
PLAYER_SIZE = 47


def checksum(blob):
    s = sum(blob[:SAVE_SIZE]) - blob[OFF["checksum"]]
    return s & 0xFF


def fix_checksum(blob):
    b = bytearray(blob)
    b[OFF["checksum"]] = 0
    b[OFF["checksum"]] = sum(b[:SAVE_SIZE]) & 0xFF
    return bytes(b)


def parse_save(blob):
    b = bytes(blob)
    d = {}
    d["magic"] = b[0] | (b[1] << 8)
    d["version"] = b[2]
    d["checksum"] = b[3]
    d["checksum_ok"] = checksum(b) == b[3]
    p = b[OFF["player"]:OFF["player"] + PLAYER_SIZE]
    d["name"] = p[0:8].split(b"\0")[0].decode("ascii", "replace")
    d["class"] = p[POFF["player_class"]]
    d["level"] = p[POFF["level"]]
    d["exp"] = p[POFF["exp"]] | (p[POFF["exp"] + 1] << 8)
    d["hp"] = p[POFF["hp"]] | (p[POFF["hp"] + 1] << 8)
    d["max_hp"] = p[POFF["max_hp"]] | (p[POFF["max_hp"] + 1] << 8)
    d["atk_base"] = p[POFF["atk_base"]]
    d["def_base"] = p[POFF["def_base"]]
    d["has_torch"] = p[POFF["has_torch"]]
    d["torch_gauge"] = p[POFF["torch_gauge"]]
    d["torch_color"] = p[POFF["torch_color"]]
    d["magic_keys"] = p[POFF["magic_keys"]]
    d["inventory"] = list(b[OFF["inventory"]:OFF["inventory"] + 8])
    d["play_seconds"] = b[OFF["play_seconds"]] | (b[OFF["play_seconds"] + 1] << 8)
    for k in ("floor_index", "map_id", "map_x", "map_y", "hero_direction",
              "flags_chest_open", "flags_chest_locked", "flags_lever_on",
              "flags_lever_stuck", "flags_sconce_lit", "npc_visible"):
        d[k] = b[OFF[k]]
    d["flags_door_locked"] = b[OFF["flags_door_locked"]] | (b[OFF["flags_door_locked"] + 1] << 8)
    d["sconce_colors"] = list(b[OFF["sconce_colors"]:OFF["sconce_colors"] + 8])
    d["script_state"] = list(b[OFF["script_state"]:OFF["script_state"] + SCRIPT_STATE_LEN])
    ov = b[OFF["overrides"]:OFF["overrides"] + 320]
    d["overrides"] = [tuple(ov[i:i + 5]) for i in range(0, 320, 5) if ov[i] != 0xFF]
    return d


def set_field(blob, off, value, width=1):
    b = bytearray(blob)
    for i in range(width):
        b[off + i] = (value >> (8 * i)) & 0xFF
    return bytes(b)


class Game:
    def __init__(self, rom=ROM, tag="run", sram=None, rom_overrides=None):
        self.rom = rom
        self.tag = tag
        self.pb = PyBoy(rom, window="null", cgb=True, sound_emulated=False)
        self.pb.set_emulation_speed(0)
        if rom_overrides:
            for (bank, addr), val in rom_overrides.items():
                self.pb.memory[bank, addr] = val
        if sram is not None:
            self.set_sram(sram)
        self.nshot = 0
        self.log = []

    # -- memory -------------------------------------------------------------
    def rd8(self, a):
        return self.pb.memory[a]

    def rd16(self, a):
        return self.pb.memory[a] | (self.pb.memory[a + 1] << 8)

    def wr8(self, a, v):
        self.pb.memory[a] = v & 0xFF

    def wr16(self, a, v):
        self.wr8(a, v)
        self.wr8(a + 1, v >> 8)

    def get(self, name):
        return self.rd8(SYM[name])

    def get16(self, name):
        return self.rd16(SYM[name])

    def set(self, name, v):
        self.wr8(SYM[name], v)

    def sram(self, n=3 * SLOT_STRIDE):
        return bytes(self.pb.memory[0, 0xA000:0xA000 + n])

    def set_sram(self, data):
        self.pb.memory[0, 0xA000:0xA000 + len(data)] = list(data)

    def slot(self, i):
        return self.sram()[i * SLOT_STRIDE:i * SLOT_STRIDE + SAVE_SIZE]

    def set_slot(self, i, blob):
        blob = bytes(blob)
        assert len(blob) == SAVE_SIZE
        self.pb.memory[0, 0xA000 + i * SLOT_STRIDE:0xA000 + i * SLOT_STRIDE + SAVE_SIZE] = list(blob)

    def player_bytes(self):
        return bytes(self.pb.memory[SYM["player"]:SYM["player"] + PLAYER_SIZE])

    # -- time / input -------------------------------------------------------
    def tick(self, n=1, render=False):
        self.pb.tick(n, render)

    def press(self, btn, hold=2, wait=6):
        self.pb.button_press(btn)
        self.tick(hold)
        self.pb.button_release(btn)
        self.tick(wait)

    def hold(self, btn, frames):
        self.pb.button_press(btn)
        self.tick(frames)
        self.pb.button_release(btn)

    def wait_for(self, pred, max_frames=900, step=1):
        for _ in range(0, max_frames, step):
            if pred():
                return True
            self.tick(step)
        return pred()

    # -- state --------------------------------------------------------------
    def gs(self):
        return self.get("game_state")

    def ms(self):
        return self.get("map_state")

    def pos(self):
        x = (self.get("map_x") + 4) & 0xFF
        y = (self.get("map_y") + 4) & 0xFF
        return x, y

    def facing(self):
        return DIRNAME.get(self.get("hero_direction"), "?")

    def state(self):
        x, y = self.pos()
        return dict(gs=self.gs(), ms=self.ms(), x=x, y=y, facing=self.facing(),
                    map=self.rd8(self.get16("active_map")),
                    chest_open=self.get("flags_chest_open"),
                    door_locked=self.get16("flags_door_locked"),
                    sconce_lit=self.get("flags_sconce_lit"),
                    lever_on=self.get("flags_lever_on"),
                    lever_stuck=self.get("flags_lever_stuck"),
                    sconce_colors=list(self.pb.memory[SYM["sconce_colors"]:SYM["sconce_colors"] + 8]),
                    play_seconds=self.get16("play_seconds"),
                    slot=self.get("active_save_slot"),
                    bank=self.get("_current_bank"))

    def shot(self, name, render=True):
        if render:
            self.tick(1, True)
        img = self.pb.screen.image.convert("RGB")
        self.nshot += 1
        path = os.path.join(SHOTS, f"{self.tag}_{self.nshot:02d}_{name}.png")
        img.save(path)
        return path

    def _tilemap(self, tm, x0, x1, y0, y1):
        """Read a tilemap slice with VRAM bank 0 selected. PyBoy's tilemap
        readers follow the game's VBK register, so a screen that last touched
        bank 1 (e.g. after load_font) would hand back attribute bytes."""
        vbk = self.pb.memory[0xFF4F]
        self.pb.memory[0xFF4F] = 0
        try:
            return tm[x0:x1, y0:y1] if y1 is not None else tm[x0:x1, y0]
        finally:
            self.pb.memory[0xFF4F] = vbk & 1

    def bg_tiles(self):
        """Background tilemap (VRAM 0x9800) as 32x32 list of tile ids."""
        return self._tilemap(self.pb.tilemap_background, 0, 32, 0, 32)

    def close(self):
        self.pb.stop(save=False)

    def power_cycle(self, tag=None):
        """Simulate power off/on with battery-backed SRAM preserved."""
        data = self.sram()
        self.close()
        self.__init__(self.rom, tag or self.tag, sram=data)
        return self

    # -- flows --------------------------------------------------------------
    def boot_to_save_select(self):
        """Mash START through the intro until the save select screen appears."""
        for _ in range(60):
            if self.gs() == GS["SAVE_SELECT"]:
                self.tick(8)
                return True
            self.press("start", hold=2, wait=20)
        return self.gs() == GS["SAVE_SELECT"]

    def action_label(self):
        """The save select ERASE / BACK button text, stripped of its padding.

        The label is 7 tiles from column 11 on row 16 (src/main_menu.c
        ACTION_LABEL_COL / _ROW / _LEN).
        """
        return self.bg_text(11, 16, 7).strip()

    def slot_text(self, slot):
        """A save slot's name-row text, read across the whole box interior.

        The interior runs cols 2-17 (src/main_menu.c SLOT_INNER_COL / _LEN).
        An empty slot's placeholder is padded to that full width so it centers,
        so reading a narrower window clips it.
        """
        return self.bg_text(2, 4 + 4 * slot, 16)

    def slot_is_empty(self, slot):
        return self.slot_text(slot).strip() == "- NEW GAME -"

    def save_select_pick(self, slot):
        """Move the cursor to `slot` (0-2, 3=ERASE) and press A."""
        assert self.gs() == GS["SAVE_SELECT"]
        cur = self.get("cursor")
        while cur != slot:
            self.press("down", wait=6)
            cur = self.get("cursor")
        self.press("a", wait=12)

    def hero_select_pick(self, hero=0, name_keys=()):
        """Pick a class, then accept the name entry screen (START keeps the class
        default; `name_keys` are pressed first, e.g. to type a name). A new game
        opens on floor 1's intro box, which this closes before returning."""
        assert self.gs() == GS["HERO_SELECT"], self.gs()
        for _ in range(hero):
            self.press("right", wait=6)
        self.press("a", wait=12)
        assert self.wait_for(lambda: self.gs() == GS["NAME_ENTRY"], 120), self.gs()
        self.tick(4)
        for k in name_keys:
            self.press(k, wait=6)
        self.press("start", wait=12)
        # init_world_map() flags on_init, which opens the box on the map's
        # first frame.
        if not self.wait_for(lambda: self.gs() == GS["WORLD_MAP"] and not self.rd8(SYM["execute_on_init"]), 600):
            return False
        return self.close_textboxes() == MS["WAITING"]

    def wait_map_idle(self, max_frames=600):
        return self.wait_for(lambda: self.gs() == GS["WORLD_MAP"] and self.ms() == MS["WAITING"], max_frames)

    def walk_until_battle(self, dirs=("UP", "UP", "DOWN", "DOWN"), max_steps=200):
        """Pace back and forth until a random encounter starts. Returns the
        number of steps taken, or 0 if none triggered.

        An encounter leaves the map through FADE_OUT -> INITIATE_BATTLE ->
        START_BATTLE before game_state becomes BATTLE, so wait for either the
        battle or a settled map after every step instead of matching states:
        pressing a direction while the battle menu is opening moves its
        cursor."""
        steps = 0
        while steps < max_steps:
            for d in dirs:
                self.step(d)
                steps += 1
                self.wait_for(lambda: self.gs() == GS["BATTLE"] or
                              (self.gs() == GS["WORLD_MAP"] and self.ms() == MS["WAITING"]), 400)
                if self.gs() == GS["BATTLE"]:
                    return steps
        return 0

    def battle_menu_goto(self, target, max_presses=8):
        """Move the battle main-menu cursor to `target` (0 FIGHT, 1 ABILITY,
        2 ITEM, 3 FLEE) by reading battle_menu.screen_cursor back. It first
        empties the battle's two text buffers, which keep the last round's
        lines until the new round writes over them, so reading the round this
        menu starts never turns up one of the last round's lines."""
        self.wr8(SYM["battle_pre_message"], 0)
        self.wr8(SYM["battle_post_message"], 0)
        cur = SYM["battle_menu"] + 1
        for _ in range(max_presses):
            c = self.rd8(cur)
            if c == target:
                return True
            self.press("down" if (target - c) & 3 <= 2 else "up", wait=10)
        return self.rd8(cur) == target

    def step(self, d):
        """Take exactly one step in direction d (a DIR value or name)."""
        if isinstance(d, str):
            d = DIR[d]
        btn = DIRBTN[d]
        self.pb.button_press(btn)
        moved = self.wait_for(lambda: self.ms() == MS["MOVING"], 12)
        self.pb.button_release(btn)
        if not moved:
            self.tick(2)
            return False
        self.wait_for(lambda: self.ms() != MS["MOVING"], 60)
        self.tick(2)
        return True

    def face(self, d):
        if isinstance(d, str):
            d = DIR[d]
        self.set("hero_direction", d)
        self.set("refresh_local_tiles", 1)
        self.tick(3)

    def teleport(self, x, y, d=None):
        """Poke the hero to map tile (x, y). Screen is stale until a reload."""
        self.set("map_x", (x - 4) & 0xFF)
        self.set("map_y", (y - 4) & 0xFF)
        if d is not None:
            if isinstance(d, str):
                d = DIR[d]
            self.set("hero_direction", d)
        self.set("refresh_local_tiles", 1)
        self.tick(3)

    def interact(self):
        """Press A once, then dismiss any textbox that opens without ever
        pressing A while the map is idle (that would interact again)."""
        self.press("a", wait=10)
        return self.close_textboxes()

    def close_textboxes(self):
        """Page through and close whatever map textbox is open, without ever
        pressing A while the map is idle. Returns the map state it ends in."""
        for _ in range(12):
            ms = self.ms()
            if ms in (MS["TEXTBOX"], MS["TEXTBOX_OPEN"]):
                self.tick(40)
                self.pb.button_press("a"); self.tick(2); self.pb.button_release("a")
                # wait for the box to either advance a page or finish closing
                self.wait_for(lambda: self.ms() != MS["TEXTBOX"], 90)
                self.tick(4)
            elif ms == MS["WAITING"]:
                break
            else:
                self.tick(10)
        return self.ms()

    def window_text(self, col, row, length):
        """Decode font tiles from the window tilemap (0x9C00)."""
        tiles = self._tilemap(self.pb.tilemap_window, col, col + length, row, None)
        out = ""
        for t in tiles:
            c = (t - 0x80) & 0xFF
            out += chr(c) if 32 <= c < 127 else "?"
        return out

    def find_window_text(self, needle):
        """Row-wise search of the window map (0x9C00) with VRAM bank 0 selected."""
        return _find_in_rows(self._tilemap(self.pb.tilemap_window, 0, 32, 0, 32), needle)

    def bg_text(self, col, row, length):
        tiles = self._tilemap(self.pb.tilemap_background, col, col + length, row, None)
        out = ""
        for t in tiles:
            c = (t - 0x80) & 0xFF
            out += chr(c) if 32 <= c < 127 else "?"
        return out


# ---------------------------------------------------------------------------
# Floor templates: make the game itself produce a genuine "new game on floor N"
# save by pointing bank_floor1's Floor pointer at floor N (2 ROM bytes), then
# inject that save into the *unmodified* ROM with floor_index corrected.
# ---------------------------------------------------------------------------
# make_floor_template() starts a real new game and then rewrites bank_floor1's
# floor pointer, so the game itself builds a save that begins on floor N.
FLOOR_PTR = {n: SYM[f"floor{n}"] for n in range(1, 9)}
FLOOR_INDEX = {n: n - 1 for n in range(1, 9)}      # index into map.c's floor_table


def make_floor_template(n, hero=0, has_torch=True, level=None, tag="tmpl"):
    ptr = FLOOR_PTR[n]
    ov = {(0, SYM["bank_floor1"] + 1): ptr & 0xFF, (0, SYM["bank_floor1"] + 2): ptr >> 8}
    g = Game(tag=f"{tag}{n}", rom_overrides=ov)
    assert g.boot_to_save_select()
    g.save_select_pick(0)
    assert g.hero_select_pick(hero)
    g.tick(20)
    pos = g.pos()
    blob = bytearray(g.slot(0))
    g.close()
    blob = set_field(blob, OFF["floor_index"], FLOOR_INDEX[n])
    if has_torch:
        blob = set_field(blob, OFF["player"] + POFF["has_torch"], 1)
    if level is not None:
        blob = set_field(blob, OFF["player"] + POFF["level"], level)
    blob = fix_checksum(blob)
    d = parse_save(blob)
    assert d["checksum_ok"]
    return bytes(blob), pos, d


def find_text(tm, needle):
    """Row-wise search of a whole 32x32 tilemap, in whichever VRAM bank the
    game last selected; Game.find_window_text() forces bank 0."""
    return _find_in_rows(tm[0:32, 0:32], needle)


def _find_in_rows(grid, needle):
    for row in range(32):
        s = "".join(chr((t - 0x80) & 0xFF) if 32 <= ((t - 0x80) & 0xFF) < 127 else "?" for t in grid[row])
        i = s.find(needle)
        if i >= 0:
            return (i, row, s.strip())
    return None


class Checker:
    def __init__(self, name):
        self.name = name
        self.results = []

    def __call__(self, label, cond, detail=""):
        self.results.append((label, bool(cond), str(detail)))
        print(("PASS " if cond else "FAIL ") + label + (f"  [{detail}]" if detail else ""), flush=True)
        return bool(cond)

    def summary(self):
        """Print the tally, write {name}_results.json beside the harness, and
        exit 1 if any check failed."""
        import json, sys
        fails = [r for r in self.results if not r[1]]
        print(f"\n==== {self.name}: {len(self.results) - len(fails)}/{len(self.results)} passed ====")
        for r in fails:
            print("FAILED:", r)
        with open(os.path.join(HERE, f"{self.name}_results.json"), "w") as fh:
            json.dump(self.results, fh, indent=1)
        if fails:
            sys.exit(1)


def game_version():
    """The version the build wrote into src/version.h for the file screen."""
    import re
    with open(os.path.join(REPO, "src", "version.h")) as fh:
        return re.search(r'#define GAME_VERSION "([^"]*)"', fh.read()).group(1)


def bg_tile_at(g, tx, ty):
    """BG tile id (top-left 8x8 of the 16x16 map tile) for map tile (tx, ty) given current map_x/y."""
    mx = g.get("map_x"); my = g.get("map_y")
    if mx > 127: mx -= 256
    if my > 127: my -= 256
    col = (tx - mx + 1) * 2
    row = (ty - my + 1) * 2
    if not (0 <= col < 32 and 0 <= row < 32):
        return None
    return g.bg_tiles()[row][col]


def menu_save(g, chk, label):
    assert g.ms() == MS["WAITING"], g.ms()
    g.press("start", wait=14)
    g.press("down", wait=8)          # SAVE is below RETURN in the left column
    g.press("a", wait=16)
    ok = find_text(g.pb.tilemap_window, "GAME SAVED!") is not None
    chk(label + ": GAME SAVED! shown", ok)
    g.press("b", wait=14)
    g.wait_map_idle(200)
    return ok


def reload_slot(g, slot, tag):
    g = g.power_cycle(tag=tag)
    assert g.boot_to_save_select()
    g.tick(10)
    g.save_select_pick(slot)
    g.wait_map_idle(900)
    g.tick(20)
    return g
