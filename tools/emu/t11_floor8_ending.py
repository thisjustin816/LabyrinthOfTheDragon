"""T11 - the floor 8 ending: the dragon fight, the cleared-game marker, the
dragon's XP landing in the save, and a new file after a cleared game
starting clean.
"""
import json, os, re, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "playtest"))
from lotd import *
from helpers import read_textbox
chk = Checker("t11_floor8_ending")
BATTLE_STATE = SYM["battle_state"]; MENU = 2
ENC = SYM["encounter"]; MON0 = ENC + 1; MON_SZ = 64          # Encounter.monsters[3], 64 B each (from the .cdb)
M_ACTIVE, M_LEVEL, M_HP, M_TARGET_HP, M_SPECIAL_IMMUNE = 5, 9, 14, 16, 60
SPECIAL_SLEET_STORM = 1 << 3            # FLAG(3) in src/player.h
slot_immunities = []
PL = SYM["player"]
MBD = SYM["mini_bosses_defeated"]; HMU = SYM["healing_mirrors_used"]
CREDITS_STATE = SYM.get("credits_state"); CREDITS_FIN = 6
GOBLIN, OWLBEAR, GCUBE, DBEAST, DKNIGHT, MFLAYER, BEHOLDER, DRAGON = 1, 4, 5, 6, 8, 9, 10, 11
# The fork card's line names the major and minor version, so it comes from
# strings.js rather than being pinned here.
FORK = re.search(r"'fork': '([^']*)'", open(os.path.join(REPO, "assets", "strings.js")).read()).group(1)

# --- floor 8 template: same trick as floors 4/5/7 (every floor lives in bank 8, only the pointer differs)
tmpl, pos, d = make_floor_template(8, hero=0, has_torch=True, tag="t11tmpl")
print("floor8 template:", json.dumps({k: d[k] for k in ("name", "floor_index", "map_x", "map_y", "flags_chest_locked", "flags_door_locked", "flags_sconce_lit", "npc_visible", "script_state", "checksum_ok")}))
chk("T11 template: floor 8 defaults (doors 1-2 locked=0x03, dragon+beholder NPCs visible=0x03, no chests)",
    d["flags_door_locked"] == 0x03 and d["npc_visible"] == 0x03 and d["flags_chest_locked"] == 0, str((hex(d["flags_door_locked"]), d["npc_visible"], d["flags_chest_locked"])))
chk("T11 template position is floor 8 default (8,29)", (d["map_x"] + 4, d["map_y"] + 4) == (8, 29), f"{d['map_x']+4},{d['map_y']+4}")

g = Game(tag="t11", sram=tmpl + bytes(SLOT_STRIDE - SAVE_SIZE))
chk("T11 boot (unmodified ROM) to save select", g.boot_to_save_select()); g.tick(10)
g.save_select_pick(0)
chk("T11 load floor 8 save -> map idle", g.wait_map_idle(900), f"gs={g.gs()} ms={g.ms()}"); g.tick(20)
st = g.state(); print("after load:", st)
chk("T11 on floor 8 at (8,29), bank 2", (st["x"], st["y"]) == (8, 29) and st["bank"] == 2, str(st))
chk("T11 mini_bosses_defeated starts 0", g.rd8(MBD) == 0, str(g.rd8(MBD)))
g.shot("floor8_start")

def dismiss_textboxes(max_loops=10):
    for _ in range(max_loops):
        ms = g.ms()
        if ms in (MS["TEXTBOX"], MS["TEXTBOX_OPEN"]):
            g.tick(40); g.pb.button_press("a"); g.tick(2); g.pb.button_release("a")
            g.wait_for(lambda: g.ms() != MS["TEXTBOX"], 90); g.tick(4)
        elif ms == MS["WAITING"]:
            return True
        else:
            g.tick(10)
    return g.ms() == MS["WAITING"]

def buff_player():
    for off, v in ((POFF["hp"], 9999), (POFF["max_hp"], 9999)):
        g.wr8(PL + off, v & 0xFF); g.wr8(PL + off + 1, v >> 8)
    g.wr8(PL + POFF["def_base"], 200); g.wr8(PL + POFF["mdef_base"], 200)

def level_exp():
    return g.rd8(PL + POFF["level"]), g.rd16(PL + POFF["exp"]), g.rd16(PL + POFF["next_level_exp"])

def cheat_win(label, expect_type, expect_level, shot=None):
    """Wait for the battle menu, drop the boss to 1 HP, keep the player unkillable, FIGHT until it ends."""
    if not g.wait_for(lambda: g.gs() == GS["BATTLE"] and g.rd8(BATTLE_STATE) == MENU, 1800):
        chk(f"{label}: battle menu reached", False, f"gs={g.gs()} ms={g.ms()} bs={g.rd8(BATTLE_STATE)}"); return False
    info = [(g.rd8(MON0 + s * MON_SZ), g.rd8(MON0 + s * MON_SZ + M_LEVEL), g.rd16(MON0 + s * MON_SZ + M_HP))
            for s in range(3) if g.rd8(MON0 + s * MON_SZ + M_ACTIVE)]
    chk(f"{label}: expected boss (type {expect_type}, level {expect_level}, alone)", len(info) == 1 and info[0][:2] == (expect_type, expect_level), str(info))
    if shot: g.tick(10); g.shot(shot)
    rounds = 0
    for _ in range(15):
        if g.gs() != GS["BATTLE"]: break
        g.wait_for(lambda: g.rd8(BATTLE_STATE) == MENU or g.gs() != GS["BATTLE"], 2000)
        if g.gs() != GS["BATTLE"]: break
        buff_player()
        for s in range(3):
            mm = MON0 + s * MON_SZ
            if g.rd8(mm + M_ACTIVE):
                g.wr8(mm + M_HP, 1); g.wr8(mm + M_HP + 1, 0); g.wr8(mm + M_TARGET_HP, 1); g.wr8(mm + M_TARGET_HP + 1, 0)
        g.battle_menu_goto(0); g.press("a", wait=12); g.press("a", wait=12); rounds += 1
        g.wait_for(lambda: g.rd8(BATTLE_STATE) != MENU, 60)
        for _ in range(300):
            if g.gs() != GS["BATTLE"] or g.rd8(BATTLE_STATE) == MENU: break
            g.press("a", hold=2, wait=8)
    won = g.gs() != GS["BATTLE"]
    print(f"  {label}: rounds={rounds} gs={g.gs()} level/exp/next={level_exp()}")
    return won

def trigger_tile(x, y):
    """Step onto (x, y) from a walkable neighbor: on_special runs when the step
    completes, and a gauntlet fight starts once its monster's line closes."""
    for nx, ny, dd in ((x, y + 1, "UP"), (x, y - 1, "DOWN"), (x - 1, y, "RIGHT"), (x + 1, y, "LEFT")):
        g.teleport(nx, ny, dd); g.tick(4)
        moved = g.step(dd)
        if g.ms() in (MS["TEXTBOX"], MS["TEXTBOX_OPEN"]):
            read_textbox(g)
        g.wait_for(lambda: g.gs() == GS["BATTLE"] or g.ms() == MS["WAITING"], 400)
        if g.gs() == GS["BATTLE"] or g.ms() != MS["WAITING"]:
            return True
        if moved and g.pos() == (x, y):
            return True
    return False

# --- six mini-boss tiles
# generators are handed level 45; owlbear_generator / displacer_beast_generator show it as level + 2
bosses = [("goblin", 2, 27, GOBLIN, 45, 0x01), ("owlbear", 14, 27, OWLBEAR, 47, 0x02), ("gelatinous cube", 3, 22, GCUBE, 45, 0x04),
          ("displacer beast", 13, 22, DBEAST, 47, 0x08), ("deathknight", 4, 17, DKNIGHT, 45, 0x10), ("mindflayer", 12, 17, MFLAYER, 45, 0x20)]
for i, (name, x, y, mtype, mlevel, bit) in enumerate(bosses):
    chk(f"T11 stepping on ({x},{y}) starts the {name} fight", trigger_tile(x, y), f"gs={g.gs()} ms={g.ms()} pos={g.pos()}")
    won = cheat_win(f"T11 {name}", mtype, mlevel, shot="mini_boss_goblin" if i == 0 else None)
    chk(f"T11 {name} beaten -> back on the map", won and g.gs() == GS["WORLD_MAP"], f"gs={g.gs()}")
    dismiss_textboxes(); g.wait_map_idle(600); g.tick(6)
    chk(f"T11 {name}: mini_bosses_defeated gains bit {bit:#04x}", g.rd8(MBD) & bit, f"{g.rd8(MBD):#04x}")
    # The gelatinous cube is the only generator that sets special_immune, so
    # monster_init_instance has to zero it along with every sibling immunity
    # field, or the next monster into the same slot inherits the cube's
    # sleet-storm immunity for the rest of the run.
    slot_immunities.append((name, g.rd8(MON0 + M_SPECIAL_IMMUNE)))
    if i == 2:
        # --- mid-way save / reload: floor 8's counters ride script_state (floor 8's own script state)
        menu_save(g, chk, "T11 save after 3 mini-bosses")
        s = parse_save(g.slot(0)); print("saved script_state:", s["script_state"], "door_locked", hex(s["flags_door_locked"]))
        chk("T11 save: script_state[3] == mini_bosses_defeated (0x07)", s["script_state"][3] == 0x07 == g.rd8(MBD), str(s["script_state"]))
        g = reload_slot(g, 0, "t11b"); g.tick(10)
        chk("T11 reload -> floor 8 idle, mini_bosses_defeated restored (deferred)", g.ms() == MS["WAITING"] and g.rd8(MBD) == 0x07, f"ms={g.ms()} mbd={g.rd8(MBD):#04x}")
        chk("T11 reload: door 1 still locked", g.state()["door_locked"] == 0x03, hex(g.state()["door_locked"]))
        g.shot("floor8_after_reload")
print("monsters[0].special_immune after each mini-boss:", slot_immunities)
# Each mini-boss is a single-monster layout, so they all land in slot 0. The
# cube is third of the six and is the one that sets the bit; the three after
# it are the ones that would inherit it.
chk("T11 the cube declares its own sleet-storm immunity",
    slot_immunities[2][1] & SPECIAL_SLEET_STORM, str(slot_immunities[2]))
chk("T11 and it does not outlive the cube's encounter",
    all(not (imm & SPECIAL_SLEET_STORM) for _, imm in slot_immunities[3:]),
    str(slot_immunities[3:]))
lvl, exp, nxt = level_exp(); print("after six mini-bosses: level/exp/next", lvl, exp, nxt)
chk("T11 level-ups from six level-45 bosses stayed sane (4 < level <= 99, exp < next)", 4 < lvl <= 99 and exp < nxt, str((lvl, exp, nxt)))
chk("T11 six bits set, door 1 still locked", g.rd8(MBD) == 0x3F and g.state()["door_locked"] == 0x03, f"{g.rd8(MBD):#04x} {hex(g.state()['door_locked'])}")

# --- a healing mirror: heals once, then has lost its luster
g.wr8(PL + POFF["hp"], 5); g.wr8(PL + POFF["hp"] + 1, 0)
g.teleport(5, 27, "UP"); g.tick(4); g.press("a", wait=10); g.tick(30); g.shot("healing_mirror"); dismiss_textboxes(); g.tick(4)
chk("T11 mirror 1: full heal and used-flag set", g.rd16(PL + POFF["hp"]) == g.rd16(PL + POFF["max_hp"]) and g.rd8(HMU) & 0x01, f"hp={g.rd16(PL + POFF['hp'])}/{g.rd16(PL + POFF['max_hp'])} used={g.rd8(HMU):#04x}")
g.wr8(PL + POFF["hp"], 5); g.wr8(PL + POFF["hp"] + 1, 0)
g.interact(); g.tick(4)
chk("T11 mirror 1 again: no heal (lost its luster)", g.rd16(PL + POFF["hp"]) == 5, f"hp={g.rd16(PL + POFF['hp'])}")

# --- the elite beholder NPC at (8,11): dialog, fight, seventh bit, door 1 opens, NPC hidden
g.teleport(8, 12, "UP"); g.tick(4); g.press("a", wait=10); g.tick(30); g.shot("elite_dialog")
dismiss_textboxes(max_loops=4)
won = cheat_win("T11 elite beholder", BEHOLDER, 55, shot="elite_battle")
chk("T11 elite beaten -> back on the map", won and g.gs() == GS["WORLD_MAP"], f"gs={g.gs()}")
dismiss_textboxes(); g.wait_map_idle(600); g.tick(6)
st = g.state()
chk("T11 all seven beaten (0x7F), door 1 unlocked (0x02 left), beholder NPC hidden (npc_visible 0x01)",
    g.rd8(MBD) == 0x7F and st["door_locked"] == 0x02 and g.get("npc_visible") == 0x01, f"mbd={g.rd8(MBD):#04x} doors={hex(st['door_locked'])} npcs={g.get('npc_visible'):#04x}")
g.shot("door_open")

# --- through the door: the stairs exit at (8,9) lands at (8,6) in the dragon's chamber
g.teleport(8, 10, "UP"); g.tick(4); g.step("UP"); g.wait_map_idle(600); g.tick(10)
chk("T11 door 1 stairs exit -> lands at (8,6) and steps off to (8,5) facing UP", g.pos() == (8, 5) and g.facing() == "UP", f"pos={g.pos()} facing={g.facing()} ms={g.ms()}")
g.shot("dragon_chamber")

# --- the dragon at (8,3)
g.teleport(8, 4, "UP"); g.tick(4); g.press("a", wait=10); g.tick(40); g.shot("dragon_dialog")
dismiss_textboxes(max_loops=4)
chk("T11 dragon fight starts", g.wait_for(lambda: g.gs() == GS["BATTLE"], 600), f"gs={g.gs()}")
pre_dragon = level_exp()
won = cheat_win("T11 dragon", DRAGON, 60, shot="dragon_battle")
chk("T11 dragon beaten -> back on the map (no credits yet)", won and g.gs() == GS["WORLD_MAP"], f"gs={g.gs()}")
post_dragon = level_exp()
chk("T11 the dragon's XP is counted", post_dragon[1] > pre_dragon[1], f"level/exp before {pre_dragon[:2]}, after {post_dragon[:2]}")
g.wait_for(lambda: g.ms() in (MS["TEXTBOX"], MS["TEXTBOX_OPEN"]), 300)
# the text writer types the message out; wait for the words rather than a fixed frame count
g.wait_for(lambda: g.find_window_text("stairway") is not None, 600); g.shot("stairs_open_text")
msg = g.find_window_text("stairway") or g.find_window_text("slain")
chk("T11 'stairway opens' message shown", msg is not None, str(msg))
dismiss_textboxes(); g.wait_map_idle(600); g.tick(6)
st = g.state()
chk("T11 dragon NPC gone, door 2 open (door_locked 0x00)", g.get("npc_visible") == 0 and st["door_locked"] == 0, f"npcs={g.get('npc_visible'):#04x} doors={hex(st['door_locked'])}")
FLAGS = SYM["flags"]
chk("T11 game-complete flag not set before the stairs", g.rd8(FLAGS) & 1 == 0, f"flags[0]={g.rd8(FLAGS):#04x}")
g.shot("door2_open")
# walk up through where the dragon stood onto the staircase door at (8,1)
for _ in range(3):
    g.step("UP"); g.wait_for(lambda: g.gs() != GS["WORLD_MAP"] or g.ms() in (MS["WAITING"], MS["FADE_OUT"], MS["CREDITS"]), 300)
    if g.ms() in (MS["FADE_OUT"], MS["CREDITS"]) or g.gs() != GS["WORLD_MAP"]: break
chk("T11 stepping onto the stairs leaves the map for the credits", g.wait_for(lambda: g.gs() == GS["CREDITS"], 900), f"gs={g.gs()} ms={g.ms()} pos={g.pos()}")
chk("T11 game-complete flag set", g.rd8(FLAGS) & 1, f"flags[0]={g.rd8(FLAGS):#04x}")
sv = parse_save(g.slot(0))
chk("T11 slot saved on the stairs with the flag, at (8,1), dragon gone", sv["checksum_ok"] and ((sv["map_x"] ^ 0x80) - 0x80 + 4, (sv["map_y"] ^ 0x80) - 0x80 + 4) == (8, 1) and sv["npc_visible"] == 0, f"pos={(sv['map_x'] ^ 0x80) - 0x80 + 4},{(sv['map_y'] ^ 0x80) - 0x80 + 4} npcs={sv['npc_visible']}")
chk("T11 and it keeps the level and XP the dragon paid", (sv["level"], sv["exp"]) == post_dragon[:2], f"saved {(sv['level'], sv['exp'])}, after the fight {post_dragon[:2]}")
# --- credits: one sample per page, taken while the page is held static (CREDITS_HOLD) or on the last page (CREDITS_FIN)
CT_PAGE = SYM["credits_text_page"]; HOLD = 2
pages = {}
for _ in range(2000):
    g.tick(5)
    cs = g.rd8(CREDITS_STATE); pg = g.rd8(CT_PAGE)
    if cs in (HOLD, CREDITS_FIN) and pg not in pages:
        rows = [g.bg_text(0, r, 21).strip() for r in range(4, 14)]
        pages[pg] = " / ".join(t for t in rows if t)
        g.tick(1, True); g.shot(f"credits_page{pg}")
    if cs == CREDITS_FIN and len(pages) >= 9:
        break
print("credits pages:"); [print(f"  {k}: {pages[k]}") for k in sorted(pages)]
chk("T11 credits show pages 1..9, each held", sorted(pages) == list(range(1, 10)), str(sorted(pages)))
p1, p3, p8, p9 = pages.get(1, ""), pages.get(3, ""), pages.get(8, ""), pages.get(9, "")
chk("T11 page 1: the dragon was defeated", "last gasp" in p1 and "Defeated" in p1, p1)
chk("T11 page 3 reads 'was free of the / dungeon and / the dragon' (one 'the', not two)", "was free of the / dungeon and / the dragon" in p3 and "The dungeon" not in p3, p3)
chk("T11 page 8: the fork card, after the original's credits", FORK in p8 and "thisJUSTin816" in p8, p8)
chk("T11 page 9: thank you for playing", "for playing" in p9, p9)
chk("T11 credits end in CREDITS_FIN and wait for START", g.rd8(CREDITS_STATE) == CREDITS_FIN, str(g.rd8(CREDITS_STATE)))
g.press("start", wait=20)
chk("T11 START after credits -> title", g.wait_for(lambda: g.gs() == GS["TITLE"], 300), f"gs={g.gs()}")
g.tick(60, True); g.shot("title_after_credits")
# the slot holds the cleared game: crown on the save select, reload lands on the stairs
chk("T11 title -> save select", g.boot_to_save_select()); g.tick(10); g.shot("save_select_cleared")
# The credits hide the sprites; the screens after them must show them again,
# or the hero is invisible everywhere until the power is cycled.
chk("T11 sprites are enabled again after the credits (LCDC bit 1)", g.rd8(0xFF40) & 0x02, f"LCDC={g.rd8(0xFF40):#04x}")
# CLEAR_MARK is "\x1e", which draw_text maps to font tile 0x1E + 0x80 = 0x9E:
# the crown drawn into assets/tiles/font.png.
CROWN = 0x9E
chk("T11 slot 1 shows the cleared-game crown (tile 0x9E at col 5)", g.pb.tilemap_background[5, 4] == CROWN, f"tile={g.pb.tilemap_background[5, 4]:#04x}")
chk("T11 slots 2/3 show no crown", g.pb.tilemap_background[5, 8] != CROWN and g.pb.tilemap_background[5, 12] != CROWN)
# The save select shows the build's version at the bottom left, level with the
# ERASE label, and no other version string.
rows = [g.bg_text(0, r, 20) for r in range(18)]
chk("T11 the save select shows the build's version at the bottom left and no other",
    g.bg_text(1, 16, 9) == game_version().ljust(9) and sum(len(re.findall(r"v\d+\.\d+", r)) for r in rows) == 1,
    repr([rows[r] for r in (0, 15, 16, 17)]))
chk("T11 the empty-slot placeholder is centered in the box interior",
    g.slot_text(1) == "  - NEW GAME -  ", repr(g.slot_text(1)))
g.save_select_pick(0); g.wait_map_idle(900); g.tick(20)
chk("T11 reload after the ending -> floor 8 on the stairs, all bosses beaten, dragon gone", g.gs() == GS["WORLD_MAP"] and g.pos() == (8, 1) and g.rd8(MBD) == 0x7F and g.get("npc_visible") == 0, f"gs={g.gs()} pos={g.pos()} mbd={g.rd8(MBD):#04x} npcs={g.get('npc_visible')}")
chk("T11 flag restored from the save", g.rd8(FLAGS) & 1, f"flags[0]={g.rd8(FLAGS):#04x}")
chk("T11 and the hero sprite is on screen after the reload", g.rd8(0xFF40) & 0x02 and any(0 < g.rd8(0xFE00 + 4 * k) < 160 for k in range(4)), f"LCDC={g.rd8(0xFF40):#04x}")

# --- a new file started after a cleared game begins clean. The cleared flag
# and floor 8's spent mirrors are game-wide state that no floor's on_init
# resets, so starting a game has to clear them itself; QUIT is what makes a
# second game in one power-on reachable. Floor 1's on_load re-arms the hidden
# kobold and the no-return warning, so the new game has to run it, and a new
# hero hasn't found a key or the torch, so the key counter stays hidden and no
# flame is left burning to keep random fights away.
MIRRORS = SYM["healing_mirrors_used"]
GOT_KEY = PL + POFF["got_magic_key"]
GAUGE, COLOR = PL + POFF["torch_gauge"], PL + POFF["torch_color"]
g.wr8(MIRRORS, 0x05)
g.set("special_encounter", 0)                  # the kobold already fought
g.set("warned_no_return", 1)                   # the warning already read
g.wr8(GOT_KEY, 1)
g.wr8(GAUGE, 30)                               # a lit torch, green
g.wr8(COLOR, 2)
g.press("start", wait=14)
chk("T11 pause menu opens on the cleared file", g.ms() == MS["MENU"], str(g.ms()))
g.press("down", wait=8); g.press("right", wait=8); g.press("a", wait=12)
g.press("left", wait=8); g.press("a", wait=12)
chk("T11 QUIT -> title", g.wait_for(lambda: g.gs() == GS["TITLE"], 600), f"gs={g.gs()}")
chk("T11 title -> save select again", g.boot_to_save_select()); g.tick(10)
g.save_select_pick(1)
chk("T11 empty slot 2 -> hero select", g.gs() == GS["HERO_SELECT"], f"gs={g.gs()}")
chk("T11 new hero -> world map", g.hero_select_pick(0), f"gs={g.gs()} ms={g.ms()}")
chk("T11 a new file after a cleared game carries no cleared flag", g.rd8(FLAGS) & 1 == 0, f"flags[0]={g.rd8(FLAGS):#04x}")
sv2 = parse_save(g.slot(1))
chk("T11 and its first save is written without the flag", sv2["checksum_ok"] and g.slot(1)[OFF["flag_pages"]] & 1 == 0, f"flag_pages[0]={g.slot(1)[OFF['flag_pages']]:#04x}")
chk("T11 and floor 8's mirrors are unspent for it", g.rd8(MIRRORS) == 0, f"healing_mirrors_used={g.rd8(MIRRORS):#04x}")
chk("T11 and floor 1's hidden kobold and no-return warning are armed again",
    g.get("special_encounter") == 1 and g.get("warned_no_return") == 0,
    f"special_encounter={g.get('special_encounter')} warned_no_return={g.get('warned_no_return')}")
chk("T11 and the key counter stays hidden until a key is found", g.rd8(GOT_KEY) == 0,
    f"got_magic_key={g.rd8(GOT_KEY)}")
chk("T11 and no flame burns on for the new hero, in play or in its first save",
    g.rd8(GAUGE) == 0 and g.rd8(COLOR) == 0 and sv2["torch_gauge"] == 0 and sv2["torch_color"] == 0,
    f"gauge={g.rd8(GAUGE)} color={g.rd8(COLOR)} saved gauge={sv2['torch_gauge']} color={sv2['torch_color']}")
g.close(); chk.summary()
