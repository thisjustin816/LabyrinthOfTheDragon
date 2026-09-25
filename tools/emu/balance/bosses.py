"""Fight every floor's boss from its gate, per class, over battle seeds, and
tabulate what the fights cost.

    tools/emu/.venv/bin/python tools/emu/balance/bosses.py fight OUT.json \\
        [--classes 0,1,2,3] [--floors 1,2,3,4,5,6,7,8] [--seeds 20] [--offsets 0,-3,-6]
    tools/emu/.venv/bin/python tools/emu/balance/bosses.py table OUT.json [MORE.json ...]

`--offsets` fights each gated boss at those levels relative to its gate as
well, for judging where a gate belongs; every row records the hero's level and
the worst single hit it took.

Not a test: a measurement for judging a change to a boss or to the stat tables.
`fight` saves one state per floor and class at the battle menu and replays the
fight from it with a fresh battle seed each time, so two builds fight the same
seeds and any difference between them is the change. LOTD_ROM and LOTD_NOI pick
the build, as they do for the suites. One process per class uses more cores;
`table` reads all the files together.

The hero is the floor's gate level, with the abilities the walkthrough route has
by the boss and 5 potions, 3 ethers, and 2 remedies. The dragon, which has no
gate, is fought at level 47, the level a real run reached it at, with floor 8's
chest haul. Each fight plays drive.resolve_battle with use_buffs: guard buffs
first, then the strongest unlocked single-target attack, with heals and items
when in danger. Two classes play differently from drive's plans: the monk opens
with Evasion and attacks with Quivering Palm, Flurry, or Open Palm, the first
that is unlocked, and the sorcerer opens with Darkness.

`table` prints, per boss and class, the median HP lost per fight in full bars,
the wins out of the fights run, and how many wins took two turns or fewer.
"""
import argparse, io, json, os, statistics, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(HERE, "..", "playtest"))

CLASSES = {0: "druid", 1: "fighter", 2: "monk", 3: "sorcerer"}

# floor: (ability flags by the boss, map, tile below the boss). The gate level
# itself comes from starts.FLOOR_BOSS_GATE, the one copy the test suite reads.
BOSSES = {
    1: (0x01, 0, (12, 6)),
    2: (0x01, 0, (10, 4)),
    3: (0x07, 0, (4, 15)),
    4: (0x0F, 0, (28, 22)),
    5: (0x1F, 1, (3, 4)),
    6: (0x3F, 1, (3, 5)),
    7: (0x3F, 0, (27, 8)),
}
DRAGON_LEVEL = 47
KIT = {"POTION": 5, "ETHER": 3, "REMEDY": 2}
DRAGON_KIT = {"POTION": 7, "ETHER": 6, "REMEDY": 2, "ELIXIR": 6, "REGEN": 3,
              "HASTE": 3, "ATK_UP": 1, "DEF_UP": 1}


def install_plans(drive):
    """The monk's and sorcerer's plans for these fights. The monk's "nuke" stays
    Flurry's index because drive sizes its ether top-up from it."""
    drive.CLASS_PLANS[2] = dict(drive.CLASS_PLANS[2], guard=(0, 4), nuke=3,
                                nuke_priority=(5, 3, 1))
    drive.CLASS_PLANS[3] = dict(drive.CLASS_PLANS[3], guard=(0, 2))
    ability_for = drive.ability_for

    def strongest(g, plan, role):
        if role == "nuke" and plan and "nuke_priority" in plan:
            for index in plan["nuke_priority"]:
                row = drive.ability_for_index(g, plan, index)
                if row is not None:
                    return row
            return None
        return ability_for(g, plan, role)

    drive.ability_for = strongest


def to_menu(g, lotd, helpers, frames=3000):
    """Talk to the boss and press through its lines until the battle menu."""
    g.interact()
    for _ in range(frames // 10):
        if helpers.at_menu(g):
            return True
        if g.ms() in (lotd.MS["TEXTBOX"], lotd.MS["TEXTBOX_OPEN"]):
            g.press("a", wait=8)
        else:
            g.tick(10)
    return helpers.at_menu(g)


def boss_game(floor, cls, tag, offset=0):
    """A game at the boss's battle menu, the hero `offset` levels from the
    floor's gate. The dragon has no gate and takes no offset."""
    import lotd, helpers, heroes, dragon
    from starts import FLOOR_BOSS_GATE
    if floor == 8:
        g = dragon.built(cls, DRAGON_LEVEL, DRAGON_KIT, tag)
        dragon.engage(g, tag)
        return g, g.wait_for(lambda: helpers.at_menu(g), 900)
    gate = FLOOR_BOSS_GATE[floor]
    abilities, map_id, (x, y) = BOSSES[floor]
    level = max(4, gate + offset)                # a new hero is level 4
    blob, _ = heroes.build_character(cls, level, floor=floor, items=KIT,
                                     abilities=abilities, tag=tag)
    blob = bytearray(blob)
    for name, v in (("map_id", map_id), ("map_x", (x - 4) & 0xFF),
                    ("map_y", (y - 4) & 0xFF), ("hero_direction", lotd.DIR["UP"])):
        blob = bytearray(lotd.set_field(blob, lotd.OFF[name], v))
    g = lotd.Game(tag=tag, sram=heroes.sram_for(bytes(lotd.fix_checksum(blob))))
    assert g.boot_to_save_select()
    g.save_select_pick(0)
    g.wait_map_idle(600)
    assert g.pos() == (x, y), f"{tag}: at {g.pos()}, wanted {(x, y)}"
    # A boss refuses a hero under its gate. The floor's on_npc_action reads
    # player.level only for that check, so the talk happens at the gate level
    # and the fight at the hero's own, restored before its first action.
    level_at = lotd.SYM["player"] + lotd.POFF["level"]
    if level < gate:
        g.wr8(level_at, gate)
    ok = to_menu(g, lotd, helpers)
    g.wr8(level_at, level)
    return g, ok


def fight(args):
    import lotd, drive
    install_plans(drive)
    seeds = [0x3A17 + 0x2C4F * k & 0xFFFF for k in range(args.seeds)]
    mon0 = lotd.SYM["encounter"] + 1
    rows = []
    for cls in args.classes:
        for floor in args.floors:
            for offset in (args.offsets if floor != 8 else [0]):
                tag = f"bosses_{floor}_{cls}_{offset:+d}"
                g, ok = boss_game(floor, cls, tag, offset)
                if not ok:
                    print(f"floor {floor} {CLASSES[cls]} {offset:+d}: never reached the battle menu",
                          flush=True)
                    g.close()
                    continue
                boss = drive.foes(g)[0]
                boss_hp = g.rd16(mon0 + 12)                 # Monster.max_hp
                level = g.rd8(lotd.SYM["player"] + lotd.POFF["level"])
                start = io.BytesIO()
                g.pb.save_state(start)
                for seed in seeds:
                    start.seek(0)
                    g.pb.load_state(start)
                    g.wr16(lotd.SYM["__rand_seed"], seed)
                    outcome = drive.resolve_battle(g, max_iters=6000, use_buffs=True)
                    last = drive.LAST_BATTLE
                    rows.append({"floor": floor, "class": CLASSES[cls], "boss": boss,
                                 "boss_hp": boss_hp, "level": level, "offset": offset,
                                 "seed": seed, "outcome": outcome,
                                 "actions": last["actions"], "taken": last["taken"],
                                 "worst_hit": last["worst_hit"], "max_hp": last["max_hp"],
                                 "spent": last["spent"]})
                g.close()
    with open(args.out, "w") as fh:
        json.dump(rows, fh, indent=1)
    print(f"wrote {len(rows)} fights to {args.out}")


def table(args):
    rows = []
    for path in args.files:
        with open(path) as fh:
            rows += json.load(fh)
    print("Median HP lost per fight in full bars, wins, wins in two turns or fewer, "
          "and fights where one hit took the whole bar.\n")
    for floor in sorted({r["floor"] for r in rows}):
        here = [r for r in rows if r["floor"] == floor]
        print(f"floor {floor}: {here[0]['boss']}, {here[0]['boss_hp']} HP")
        # A file with no "level" key was fought at its floor's gate level.
        levels = sorted({r.get("level", 0) for r in here})
        for level in levels:
            at = [r for r in here if r.get("level", 0) == level]
            if len(levels) > 1:
                print(f"  hero level {level}")
            for cls in CLASSES.values():
                fights = [r for r in at if r["class"] == cls]
                if not fights:
                    continue
                wins = [r for r in fights if r["outcome"] == "victory"]
                cost = statistics.median(r["taken"] / r["max_hp"] for r in fights)
                short = sum(1 for r in wins if r["actions"] <= 2)
                one = sum(1 for r in fights if r.get("worst_hit", 0) >= r["max_hp"])
                print(f"    {cls:8} {cost:5.2f} bars   {len(wins):2}/{len(fights)} won   "
                      f"{short:2} in two turns   {one:2} one-shot")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    f = sub.add_parser("fight", help="fight the bosses and write the fights to OUT")
    f.add_argument("out")
    f.add_argument("--classes", type=lambda s: [int(c) for c in s.split(",")],
                   default=list(CLASSES))
    f.add_argument("--floors", type=lambda s: [int(c) for c in s.split(",")],
                   default=list(range(1, 9)))
    f.add_argument("--seeds", type=int, default=20)
    f.add_argument("--offsets", type=lambda s: [int(c) for c in s.split(",")], default=[0],
                   help="hero levels relative to the gate, e.g. 0,-3,-6")
    t = sub.add_parser("table", help="summarize one or more files `fight` wrote")
    t.add_argument("files", nargs="+")
    args = parser.parse_args()
    (fight if args.command == "fight" else table)(args)


if __name__ == "__main__":
    main()
