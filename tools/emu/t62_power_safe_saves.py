"""T62 - saves surviving a power cut and bad SRAM: a boot from random SRAM, a
forged save with a bad checksum, an old version's save, the newer of a slot's
two copies winning across the generation counter's wrap, and a power cut after
every write of a save and of an erase.

A cut is simulated by hooking `sram_put` in src/save.c, which every write to
a save goes through, and copying SRAM as it stood before each write. Each copy
is then booted from a savestate taken on the title screen.
"""
import io, random, re
from lotd import *
chk = Checker("t62_power_safe_saves")

full = int(re.search(r"DEF Fsave\$sram_put\$0\$0 0x([0-9A-Fa-f]+)", open(NOI).read()).group(1), 16)
SRAM_PUT = (full >> 16, full & 0xFFFF)


def new_game_in_slot(g, slot, hero=0):
    g.save_select_pick(slot)
    assert g.hero_select_pick(hero)
    g.tick(20)


def reboot_to_save_select(g, tag):
    g = g.power_cycle(tag)
    assert g.boot_to_save_select()
    g.tick(10)
    return g


def load(g, slot):
    """Load a slot and wait out the floor's on_init, which runs a frame after
    the fade-in ends and takes no input until it has."""
    g.save_select_pick(slot)
    return g.wait_map_idle(900) and g.wait_for(lambda: not g.rd8(SYM["execute_on_init"]), 60)


def with_copies(blob_a, blob_b, tag):
    """A game whose slot 0 has the two copies given, at the save select."""
    g = Game(tag=tag)
    g.set_copy(0, 0, blob_a)
    g.set_copy(0, 1, blob_b)
    assert g.boot_to_save_select()
    g.tick(10)
    return g


def regen(blob, generation, **fields):
    for name, value in fields.items():
        blob = set_field(blob, OFF[name], value)
    return fix_checksum(set_field(blob, OFF["generation"], generation))


# --- random SRAM ---------------------------------------------------------------
noise = bytes(random.Random(62).randrange(256) for _ in range(SRAM_BANK_SIZE))
g = Game(tag="t62a", sram=noise)
chk("T62 random SRAM: boots to the save select", g.boot_to_save_select())
g.tick(10)
chk("T62 random SRAM: every slot reads as NEW GAME", all(g.slot_is_empty(i) for i in range(3)),
    [g.slot_text(i).strip() for i in range(3)])
new_game_in_slot(g, 1)
chk("T62 random SRAM: a new game starts in slot 2", g.gs() == GS["WORLD_MAP"] and g.get("active_save_slot") == 1)
g = reboot_to_save_select(g, "t62a2")
chk("T62 random SRAM: slot 2's first save loads after a power cycle", load(g, 1) and g.pos() == (12, 16), g.pos())
template = g.slot(1)
g.close()

# --- a forged save and an old version's ---------------------------------------
forged = bytearray(template)
forged[OFF["checksum"]] ^= 0x01
g = with_copies(bytes(forged), bytes(SAVE_SIZE), "t62b")
chk("T62 a save with a valid magic and a bad checksum reads as NEW GAME", g.slot_is_empty(0), g.slot_text(0).strip())
g.save_select_pick(0)
chk("T62 choosing it starts a new game", g.gs() == GS["HERO_SELECT"], g.gs())
g.close()

older = regen(template, 0, map_y=(15 - 4) & 0xFF)
newer = bytearray(regen(template, 1))
newer[OFF["checksum"]] ^= 0x01
g = with_copies(older, bytes(newer), "t62c")
chk("T62 a newer copy with a bad checksum is passed over for the older valid one",
    load(g, 0) and g.pos() == (12, 15), g.pos())
g.close()

g = Game(tag="t62d")
g.set_slot(0, fix_checksum(set_field(template, OFF["version"], 4)))
g.set_slot(1, template)
assert g.boot_to_save_select()
g.tick(10)
chk("T62 a version 4 save reads as NEW GAME", g.slot_is_empty(0), g.slot_text(0).strip())
beside = g.slot_text(1).strip()
chk("T62 and the slot beside it survives", not g.slot_is_empty(1) and load(g, 1) and g.pos() == (12, 16), beside)
g.close()

# --- the newer copy, across the generation counter's wrap --------------------
for gen_a, gen_b, want in ((255, 0, (12, 15)), (0, 255, (12, 16))):
    g = with_copies(regen(template, gen_a), regen(template, gen_b, map_y=(15 - 4) & 0xFF), f"t62e{gen_a}")
    chk(f"T62 copies at generations {gen_a} and {gen_b}: the game loads {'second' if want == (12, 15) else 'first'}",
        load(g, 0) and g.pos() == want, g.pos())
    if gen_a == 255:
        kept = g.copy(0, 1)
        menu_save(g, chk, "T62 save over the wrapped pair")
        first = parse_save(g.copy(0, 0))
        chk("T62 the save goes to the older copy, at generation 1, and leaves the newer one",
            first["checksum_ok"] and g.copy(0, 0)[OFF["generation"]] == 1 and g.copy(0, 1) == kept,
            f"generation={g.copy(0, 0)[OFF['generation']]}")
    g.close()

# --- a power cut after every write --------------------------------------------
# The title screen, waiting for START, with SRAM still unread. START skips the
# intro and does nothing while the title's fire burns.
t = Game(tag="t62t")
for _ in range(120):
    if t.get("title_state") == 2 and t.get("main_title_state") == 1:
        break
    t.press("start", wait=20)
title = io.BytesIO()
t.pb.save_state(title)


def boot_from(snapshot):
    """Load the title savestate over `snapshot` and reach the save select."""
    title.seek(0)
    t.pb.load_state(title)
    t.set_sram(snapshot)
    t.press("start", wait=20)
    t.wait_for(lambda: t.gs() == GS["SAVE_SELECT"], 300)
    t.tick(10)


def record_writes(g):
    snapshots = []
    g.pb.hook_register(*SRAM_PUT, lambda _: snapshots.append(g.sram()), None)
    return snapshots


g = Game(tag="t62f")
assert g.boot_to_save_select()
new_game_in_slot(g, 0)
g.step("UP")
g.wait_map_idle(200)
menu_save(g, chk, "T62 a save to fall back on")
g.face("LEFT")
snapshots = record_writes(g)
menu_save(g, chk, "T62 the save that is cut")
g.pb.hook_deregister(*SRAM_PUT)
snapshots.append(g.sram())
writes = len(snapshots) - 1
chk("T62 the save went through sram_put once per byte, plus the magic cleared first",
    writes == SAVE_SIZE + 1, writes)

before, after = DIR["UP"], DIR["LEFT"]
wrong = []
for n, snapshot in enumerate(snapshots):
    boot_from(snapshot)
    loaded = load(t, 0)
    facing = t.get("hero_direction")
    want = after if n == writes else before
    if not (loaded and facing == want and t.pos() == (12, 15)):
        wrong.append((n, loaded, DIRNAME.get(facing), t.pos()))
chk(f"T62 a cut after any of the {writes} writes loads the save from before it, and none at all the save after",
    not wrong, wrong[:5])

for n in sorted({0, 1, writes // 2, writes - 1, writes}):
    boot_from(snapshots[n])
    load(t, 0)
    t.face("DOWN")
    saved = menu_save(t, lambda *_: None, "")
    newest = parse_save(t.slot(0))
    chk(f"T62 after a cut at write {n}, the next save works", saved and newest["checksum_ok"]
        and newest["hero_direction"] == DIR["DOWN"], newest["hero_direction"])

# --- a power cut after every write of an erase --------------------------------
# The slot's older copy gets a name of its own, to tell it from the newer.
sram = bytearray(g.sram())
first_at, second_at = 0, SLOT_COUNT * SLOT_STRIDE
older_at = first_at if newest_copy(g.copy(0, 0), g.copy(0, 1)) == 1 else second_at
older = bytearray(sram[older_at:older_at + SAVE_SIZE])
older[OFF["player"]:OFF["player"] + 6] = b"OLDER\0"
sram[older_at:older_at + SAVE_SIZE] = fix_checksum(older)
g.close()

boot_from(bytes(sram))
name = t.slot_text(0).split()[0]
chk("T62 before the erase, slot 1 shows its newer copy", name != "OLDER" and not t.slot_is_empty(0), t.slot_text(0))
snapshots = record_writes(t)
t.press("down"); t.press("down"); t.press("down"); t.press("a", wait=10)   # ERASE, cursor on file 1
t.press("a", wait=10); t.press("left", wait=8); t.press("a", wait=30)       # YES
t.pb.hook_deregister(*SRAM_PUT)
snapshots.append(t.sram())
chk("T62 the erase cleared both copies' magic and wiped both copies",
    len(snapshots) - 1 == 2 + COPY_COUNT * SLOT_STRIDE and t.slot_is_empty(0), len(snapshots) - 1)

wrong = []
for n, snapshot in enumerate(snapshots):
    boot_from(snapshot)
    shown = t.slot_text(0).strip()
    if not (shown == "- NEW GAME -" or shown.split()[0] == name):
        wrong.append((n, shown))
chk("T62 a cut after any write of an erase leaves the slot's save or nothing, never the older copy",
    not wrong, wrong[:5])
t.close()
chk.summary()
