# Emulator test harness

Headless [PyBoy](https://github.com/Baekalfen/PyBoy) suites that boot the real
ROM, play it with the D-pad, and assert on game memory and on what reaches the
screen. They exist because most of what this fork changes (save and load, menu
layout, status effects, puzzle state across a reload) cannot be checked by
reading the code, only by playing it.

## Setup

From the repo root:

```
python3 -m venv tools/emu/.venv && tools/emu/.venv/bin/pip install pyboy pysdl2-dll Pillow
```

Pillow isn't a hard pyboy dependency, but every suite that calls `.shot()`
needs it and fails hard without it. [Node](https://nodejs.org/) is needed too,
for the strings audits and for the text oracle, which loads
`assets/strings.js`; t27, t35, t36, and t40 reach the oracle through
`playtest/dragon.py`.

## Running

The suites read symbol addresses out of the `.noi` the symbol build produces,
so build with symbols first. It lands next to the ROM and the harness finds it
there; the plain `make` ROM is byte-identical, the debug flags only add side
files.

```
GBDK_DEBUG=ON make assets && GBDK_DEBUG=ON make
tools/emu/.venv/bin/python tools/emu/run_all.py
```

One suite at a time works the same way, as
`tools/emu/.venv/bin/python tools/emu/t15_flee.py`. `LOTD_ROM` and `LOTD_NOI`
point the harness at a ROM and symbol file built somewhere else, and
`LOTD_SHOTS` moves the screenshots. Each suite prints a PASS or FAIL line per
check, writes its results to `<suite>_results.json` beside the harness, and
exits 1 if any check failed; `run_all.py` totals them.

## What is here

`lotd.py` is the harness: booting, input, waiting on game state, reading the
tilemaps as text, screenshots, a save-file builder, and the `Checker` every
suite reports through. Everything else beside it is one suite per area,
numbered in the order they were written:

| | |
|---|---|
| t1_t2 | walking, a chest, and a pause-menu save and reload |
| t3, t4, t5 | the floor 4, 7, and 5 puzzles, and their state across a reload |
| t6 | save select: slots, clock, erase, version guard |
| t8, t9 | battle flow, banked calls, buffs landing |
| t10 | pause menu, QUIT, ERASE focus |
| t11 | the floor 8 ending, the cleared-game marker, the dragon's XP in the save, and a new file after a cleared game starting clean |
| t12 | tile-override hash collisions across a reload |
| t13 | the hero select panel and name entry |
| t14 | aspect vulnerability on a basic attack |
| t15 | fleeing: the odds by AGL gap, and a blinded or frightened pack unable to give chase |
| t16 | the torch burning per step |
| t17 | using items from the pause menu |
| t18 | the battle item menu's entry count and scroll |
| t19 | a debuff beating a buff on the same stat |
| t20 | the HUD key counter, read from OAM, and the menu cursor and textbox palettes, read from rendered pixels |
| t21 | floor 6's boss-room lever hint |
| t22 | debuff immunity: monster masks, dark immunity as an aspect, Still Mind, the bugbear's scare, and what a fight leaves on the player once it ends |
| t23 | PRESS START staying dark until the title reads START |
| t24 | a blow the monk's Evasion dodges reading as a dodge, not a hit for 0 |
| t25 | a Wild Magic roll every target is immune to reading as immune, and one that landed a debuff writing no line of its own |
| t26 | floor 1's stairs warning before the one-way step down to floor 2 |
| t27 | a dodge keeping the evade sound instead of the attack's own sound |
| t28 | a cured confusion staying cured against Extract Brain right away |
| t29 | an ability's buff lasting the fight and giving way to a stronger potion, and the player's status icons on the stat box's own background |
| t30 | a battle item leaving the bag on its own turn, not at the menu, a kept item playing the fail sound, and a Remedy that cures playing the healing sound |
| t31 | the monk's Flurry landing four blows past level 56, with damage that fits in 16 bits, and Open Palm's damage tier stepping up at level 30 |
| t32 | a critical hit still doubling on a weakness, ignoring resistance, and never doubling a basic attack |
| t33 | a death knight rising from any killing blow: outright kills, area attacks, and single hits |
| t34 | a stat lowered for a monster's roll staying itself past 99 and 127 |
| t35 | the dragon taking Quivering Palm's and Disintegrate's damage but never their outright kill |
| t36 | the dragon's fire breath playing the title screen's fire sound while the kobold's spit, the sorcerer's Fireball, and the death knight's hellfire orb keep the magic hit |
| t37 | a direction held from one battle menu into the next, into a fight, or through a round leaving the new menu's cursor alone until it is pressed again, while a thumb rolled onto another direction moves it at once |
| t38 | Open Palm opening with its own line, and a trip reading after the damage, on a page of its own when the damage line leaves no room, and never after a phased, killing, or death knight-raising blow |
| t39 | the title and file screens' frames counting toward the seed a floor's first step draws, the first fight after the same save changing with the title wait alone, and nothing rolling or counting on its own once play begins |
| t40 | Trip Attack and Open Palm never knocking down the dragon or the gelatinous cube, Trip Attack saying so, and both still knocking down floor 1's goblin |
| t41 | floor 7's eye lock following its two lever rules to the boss door and lighting the orb above it, starting over when the floor loads afresh, and the sconce pocket's cracked floor dropping the hero in front of the item room's door |
| t42 | a floor 8 healing mirror used before the floor loads afresh staying used and drawn dull, while an unused one still heals, and a save loaded after QUIT drawing its mirrors as that save left them |
| t43 | floor 7's elite giving a haste potion, an ATK up, and a DEF up, and its textbox naming all three |
| t44 | floors 2 to 6's elites, beaten again by a hero who already knows their ability, saying "You've learned all it can teach." instead of teaching it over |
| t45 | floor 8's gauntlet: bright bones on each waiting fight, each fight's home-floor roar and line before it starts, dim bones and no second fight after a win, a save keeping the dim bones, and every fight back with bright bones when the floor loads afresh |
| t46 | every class's basic attack and six abilities playing a sound when they work: the class's hit sound for damage, Action Surge's own sound, the powerup sound for buffs, the special critical sound for an outright kill, the miss sound for a miss or a blow the displacer beast phases out of, and the fail sound for Trip Attack against an immune monster, Sleetstorm against the immune cube, and a Wild Magic surge that fizzles |
| t47 | lost turns playing the fail sound, for the goblin or the hero knocked down, getting up, paralyzed, or frozen by fear, the goblin slipping on Sleetstorm's ice or staring in a confused stupor, and the hero mumbling while confused or blocked from fleeing, plus a confused blow on oneself playing the melee hit |
| t48 | a frightened boss, the gauntlet goblin and the dragon, trying to run and never getting away, with the fight going on, while a wandering monster on floor 1 still can |
| t49 | battle rules from the review backlog: the hero's poison death line, a confused self-hit shaking the screen, Wild Magic never reviving a monster its own fireball felled, a queued Still Mind going through fear, blindness zeroing ATK past an ATK Down for the hero and a monster, a Remedy or Still Mind putting a lowered stat back within its own round, and nothing one fight left on the hero's stats or effect flags reaching the next |
| t50 | a death on floor 2 putting the torch out and starting floor 1's random fight buildup over, and a fresh arrival on floor 2 starting its buildup over |
| t51 | a pounce or eyestalk ray the monk's Evasion dodges keeping the owlbear's or the beholder's charge, as a miss does, while one that lands spends it |
| t52 | a critical hit under a monster's own line, from the death knight and the dragon, playing the critical sound, and a blow that isn't one playing the attack's own sound |
| t53 | a step onto a stairway from the side bumping like a wall, at floor 2's one stairway with floor beside it, while the corridor there still walks and a step up from below still takes the stairs |
| t54 | a new game opening on floor 1's line of story, on one page, before the first step, and a death or a load waking on floor 1 without it |
| t55 | FIGHT and a single-target ability starting on the monster last targeted while it stands, on the first monster standing once it falls, and on the first monster again in the next fight |
| t56 | the hero hidden behind the bricks on all four brick-faced passage entrances, floor 2's and the three on floors 4 and 5 |
| t57 | floor 3's four goblin guards waiting on bright bones, a fought guard's bones dimming and its tile starting nothing, a save keeping both, and a fresh load bringing the guards back |
| t58 | Fireball, Insect Plague, and Cleave saying what they dealt, one number for monsters that took the same and each monster's damage otherwise, every number matching the HP lost, and Cleave halved by a physical resistance but not a magic one |
| t59 | the file screen showing the build's version, the Makefile's major and minor version and the commits since it changed, at the bottom left in the hint gray, beside a saved file, after the erase prompt's YES box has covered it, and after B on hero select |
| t60 | SELECT on the name entry labeling B2 to B8 and wrapping back to blank, and each start's first save holding that floor, a first run's level, the abilities, the torch, a key for each of its key-locked chests, and a first run's items, the keys and items worked out from the floors' sources |

### Pitfalls

A few behaviors of the game catch a suite out. A lost fight returns the game
to floor 1 without any error, so a suite that fights checks which floor it is
on afterward. Poking `player.level` changes only the level byte: ATK and DEF
are recomputed by a real level-up and nothing else, so a suite that needs a
level's stats builds the character with `playtest/heroes.py`. Right after an
action a monster's `hp` still lags its `target_hp`, which is the one to read.
The encounter RNG seed is a running frame count since power-on, drawn on the
first step after a floor load, so reloading a savestate replays the same
encounters unless the suite reseeds (`starts.reseed()`). A floor's fade-in
ends a frame before its `on_init` sets up the encounter ramp and puzzles, so
`start_on()` returns only after that has run; a suite that loads a floor some
other way waits for `execute_on_init` to clear before poking either. PyBoy
takes one hook per address, so a suite that listens for a sound goes through
`sounds_heard()` rather than hooking the sound itself. Returning to the map
does not say how a battle ended, since a flee returns there too, so a boss
kill is confirmed by its door opening, its NPC hiding, and the credits.
`make clean` removes the `.noi` along with the ROM, and the harness refuses to
run against a ROM whose `.noi` is missing or older than it. If you add a PyBoy
hook, put it only at an address that starts an instruction in its bank (the
`.noi`'s `A$` and `C$` labels mark them), or the patched byte corrupts the
code under it.

## playtest/

The suites' shared library for playing the game rather than poking it:

- `drive.py`: walking a planned path, crossing an exit, fighting a battle out
  with a per-class plan (`resolve_battle`), and using items and abilities.
- `helpers.py`: which floor the game is on, loading a floor afresh as its
  stairs or the trip back down after a death would, the tiles a floor's scripts have
  repainted and the palettes the screen draws a tile in, the player's state as
  a log line, reading a textbox page by page, a battle round's lines with the
  sound each plays, every sound the game plays through one shared set of
  hooks, which of a round's blows were critical hits, a symbol's bank and
  address for a PyBoy hook, casting an ability, and savestate checkpoints
  under `playtest/ckpt/`, which is ignored because a savestate is a frozen
  WRAM copy and is stale against any later ROM.
- `starts.py`: a character dropped onto any floor at that floor's own boss
  gate, with the abilities the floors below would have granted.
- `heroes.py`: a built character of any class, with every derived stat written
  from `assets/tables.csv`.
- `dragon.py`: the dragon fight's setup for t27, t35, t36, and t40, a built
  character on floor 8 walked up to the dragon and into the battle.
- `knight.py`: the death knight fight's setup for t33, t36, and t38, a hero on
  floor 8 stepping onto the knight's tile.
- `nav.py` with `exits_db.py`: pathfinding over the game's own map files and a
  hand copy of each floor's exit and door tables.
- `text_oracle.py`: a textbox seen in play compared against what
  `assets/strings.js` says it should show.

## audit/

Static checks over `src/`, each run as `python3 tools/emu/audit/<name>.py`
from anywhere. All but `cross_bank.py` run a fixture self-test first and print
its result; a FAIL on that line means the audit is broken, not the game.
`shared.py` holds the comment stripper and the `strings.js` loader they share.

- `banks.py`: a header prototype's BANKED/NONBANKED/plain annotation against
  its own definition's. SDCC rejects a BANKED disagreement when the defining
  file includes the header but carries a NONBANKED one into the definition
  silently, and checks nothing when the file does not include it, so a stale
  header can be the only line that says where a function really lives.
  Annotate the plain side to match the annotated one, and prove any fix with
  an md5 diff of the ROM, not just a passing audit. Exits 1 on a mismatch.
- `chests.py`: a chest whose reward text promises an item it does not carry
  and no callback grants. Exits 1 when it flags one.
- `cross_bank.py`: a palette or string handed across a bank boundary. Needs the
  root `.noi` from the symbol build and the generated `src/strings.h`. It has
  no fixture; it asserts the banks of a few known symbols instead, so a
  misread `.noi` fails rather than passing clean.
- `exits.py`: `playtest/exits_db.py` against each floor's own `exits[]`. Run it
  after changing any floor's exits, because a missing exit is a route the
  pathfinder silently never takes. Exits 1 on a mismatch.
- `fields.py`: struct fields that are read but never written. Its known false
  positives are listed with their reasons, and it exits 1 on any other.
- `strings_fit.py`: strings that run past a page, split a word, or come near
  the 90-character limit. Needs node.
- `strings_lint.py`: grammar and consistency findings for a human pass. Needs
  node.
- `strings_unused.py`: declared strings nothing in `src/` references. Needs
  the generated `src/strings.h`, and exits 1 when the count moves off the
  expected one.

## balance/

Not tests: scripts that say what a change to the stat tables or to a boss does
to a hit chance, the length of a fight, or its cost. `spread.py`
answers whether a monster's tier means the same thing at every depth, and
`margins.py` whether a change moves who wins; both compare the working tree
against `origin/main` by default, and `LOTD_BASE` names another revision.
`agility.py` reads the tree alone and says what AGL is worth: initiative, the
flee odds from the game's own `roll_flee()`, and the monk's attack level.
`bosses.py` plays the ROM instead of reading the tables: it fights every floor's
boss from its gate with each class and the battle bot, over battle seeds, and
tabulates the HP each fight cost and the wins. Its docstring gives the usage.
