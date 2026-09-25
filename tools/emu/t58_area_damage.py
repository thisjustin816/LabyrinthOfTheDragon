"""T58 - area attacks say what they dealt, and Cleave hits as a physical blow.

Fireball, Cleave, and Insect Plague end with a damage line: a single hit's line
when one monster stands, "You deal N damage to each!" when every monster took
the same, and each monster's damage from left to right otherwise. Every number
has to match the HP the monster lost. Cleave is physical, so a monster that
resists physical blows takes half and one that resists magic takes it all.

Monster slots from LabyrinthOfTheDragon.cdb: 64 bytes each from encounter+1,
active at +5, max_hp at +12, hp at +14, target_hp at +16, aspect_resist at
+31, aspect_vuln at +32. Aspects from src/stats.h.
"""
import os, re, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "playtest"))
from lotd import *
from helpers import *
from starts import start_on, reseed

chk = Checker("t58_area_damage")
DRUID, FIGHTER, SORCERER = 0, 1, 3
PHYSICAL, MAGICAL, FIRE = 0x01, 0x02, 0x20
FIREBALL_ROW, CLEAVE_ROW, INSECT_PLAGUE_ROW = 1, 2, 4
HP = 999


def slot(k):
    return SYM["encounter"] + 1 + 64 * k


def standing(g):
    return [k for k in range(3) if g.rd8(slot(k) + 5)]


def prime(g, resist=None):
    """Full bars, monsters that outlast the round, and no resistance or
    weakness beyond `resist`, {slot: aspect}."""
    keep_alive(g)
    for k in standing(g):
        for off in (12, 14, 16):
            g.wr16(slot(k) + off, HP)
        g.wr8(slot(k) + 31, (resist or {}).get(k, 0))
        g.wr8(slot(k) + 32, 0)


def cast_and_read(g, row, pre):
    """Cast `row` and return (its damage line, each standing monster's HP
    lost, in slot order)."""
    up = standing(g)
    before = [g.rd16(slot(k) + 16) for k in up]
    cast(g, row, wait=1)
    lines = round_messages(g)
    post = next((p for q, p, _ in lines if q == pre), None)
    return post, [b - g.rd16(slot(k) + 16) for b, k in zip(before, up)]


def numbers(line):
    return [int(n) for n in re.findall(r"\d+", line or "")]


def group_fight(g, tag, want):
    """A random floor 1 fight with `want` monsters, from a fresh seed each try."""
    save_checkpoint(g, f"{tag}.state")
    for k in range(60):
        load_checkpoint(g, f"{tag}.state")
        reseed(g, 17 * k + 7)
        if g.walk_until_battle(("DOWN", "UP"), max_steps=200) and g.wait_for(lambda: at_menu(g), 1800):
            g.tick(10)
            if len(standing(g)) == want:
                return True
    return False


# Fireball against the owlbear alone: a single hit's line.
g, _ = start_on(2, class_id=SORCERER, level=20, abilities=0x3F, tag="t58a")
g.teleport(10, 4, "UP"); g.tick(4); g.press("a", wait=10)
read_textbox(g)
fought = g.wait_for(lambda: at_menu(g), 1800)
chk("T58 the owlbear fight starts", fought, f"gs={g.gs()}")
if fought:
    prime(g)
    post, lost = cast_and_read(g, FIREBALL_ROW, "EXPLOSION!")
    chk("T58 Fireball against one monster says what it dealt, as a single hit does",
        post == f"You deal {lost[0]} damage!" and lost[0] > 0, f"post={post!r} lost={lost}")
g.close()

# Fireball and Insect Plague against three monsters.
for name, cls, row, pre, aspect, tag in (("Fireball", SORCERER, FIREBALL_ROW, "EXPLOSION!", FIRE, "t58b"),
                                         ("Insect Plague", DRUID, INSECT_PLAGUE_ROW, "Locusts swarm!", MAGICAL, "t58c")):
    g, _ = start_on(1, class_id=cls, level=40, abilities=0x3F, tag=tag)
    g.wr8(PL + POFF["torch_gauge"], 0)
    fought = group_fight(g, tag, 3)
    chk(f"T58 a fight with three monsters starts for {name}", fought, f"standing={standing(g)}")
    if not fought:
        g.close()
        continue
    for _ in range(4):
        prime(g)
        post, lost = cast_and_read(g, row, pre)
        if all(lost):
            break
        g.wait_for(lambda: at_menu(g), 900)
    chk(f"T58 {name} against three alike says one number for each",
        post == f"You deal {lost[0]} damage to each!" and len(set(lost)) == 1 and lost[0] > 0,
        f"post={post!r} lost={lost}")
    g.wait_for(lambda: at_menu(g), 900)
    for _ in range(4):
        prime(g, {standing(g)[1]: aspect})
        post, lost = cast_and_read(g, row, pre)
        if all(lost):
            break
        g.wait_for(lambda: at_menu(g), 900)
    chk(f"T58 {name} with the middle monster resisting lists each, left to right",
        numbers(post) == lost and lost[1] == lost[0] // 2 and lost[0] == lost[2],
        f"post={post!r} lost={lost}")
    g.close()

# Cleave: physical, so physical resistance halves it and magic resistance doesn't.
g, _ = start_on(1, class_id=FIGHTER, level=40, abilities=0x3F, tag="t58d")
g.wr8(PL + POFF["torch_gauge"], 0)
fought = group_fight(g, "t58d", 3)
chk("T58 a fight with three monsters starts for Cleave", fought, f"standing={standing(g)}")
if fought:
    up = standing(g)
    for _ in range(6):
        prime(g, {up[0]: PHYSICAL, up[1]: MAGICAL})
        post, lost = cast_and_read(g, CLEAVE_ROW, "You cleave through your enemies!")
        if all(lost):
            break
        g.wait_for(lambda: at_menu(g), 900)
    chk("T58 Cleave's line matches what each monster lost", numbers(post) == lost and all(lost),
        f"post={post!r} lost={lost}")
    chk("T58 Cleave is halved by a physical resistance and ignores a magic one",
        lost[0] == lost[2] // 2 and lost[1] == lost[2], f"lost={lost}")
g.close()
chk.summary()
