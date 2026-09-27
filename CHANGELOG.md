# Changelog

This fork's changes to [Labyrinth of the Dragon](https://github.com/NesHacker/LabyrinthOfTheDragon), compared with the original's main branch. Issue links go to the original's tracker.

## 1.1

Based on the original's main branch as of August 24, 2025: 1.0.5 Alpha, plus its compiler warning fixes ([#73](https://github.com/NesHacker/LabyrinthOfTheDragon/pull/73)) and a README update. The original's two open pull requests are merged too: the spelling fixes in [#77](https://github.com/NesHacker/LabyrinthOfTheDragon/pull/77) and the floor 3 encounter fix in [#79](https://github.com/NesHacker/LabyrinthOfTheDragon/pull/79).

### Added

- Saving ([#75](https://github.com/NesHacker/LabyrinthOfTheDragon/issues/75)). Three save files on the cartridge's battery-backed RAM, a SAVE command in the menu, and a file screen that shows the game's version and each hero's level, floor, and play time, and asks before erasing a file. The floors' doors, levers, and puzzles are saved along with the hero.
- A name for your hero, up to six letters, entered after choosing a class. The name the original gave that class's hero is filled in to start.
- ITEMS in the menu, for drinking a Potion, Ether, or Elixir outside of battle ([#70](https://github.com/NesHacker/LabyrinthOfTheDragon/issues/70)).
- QUIT in the menu, which returns to the title screen after asking first.
- A crown on the file of a hero who has beaten the game.
- The floor in the menu and on the file screen, counted down from B1 to B8.
- A short description of each hero on the hero select screen.
- A warning before the one-way stairs off floor 1.
- A line of story as a new game begins.
- A hint sign for floor 4's flame-color puzzle, and a message on floor 6 when only one of the boss door's two levers is pulled.
- Sound effects for the 19 abilities that made no sound when they worked ([#40](https://github.com/NesHacker/LabyrinthOfTheDragon/issues/40)). Cleave and Trip Attack sound like the fighter's attack, and Open Palm, Flurry, and Quivering Palm like the monk's strike. Attack spells and Menace play the magic hit, buffs play the powerup sound Evasion uses, and Action Surge plays a sound the game had but never used. An outright kill with Quivering Palm or Disintegrate has a sound of its own, and Trip Attack plays the fail sound against a monster immune to it.
- Sound effects for lost turns and confused blows, which were silent. A turn lost to paralysis, fear, confusion, being knocked down, or Sleetstorm's ice plays the fail sound, and so do an escape the monsters block and a battle item you keep because it would no longer help. A confused blow plays the melee hit.

### Changed

- The dragon's defeat plays out on the map. The door behind it opens, and the stairs beyond save the game as cleared and roll the credits. The ending can be replayed from the stairs.
- The torch burns down one step at a time instead of on a clock, so standing still or reading a sign costs nothing. A full torch lasts 32 steps at any pace, and wandering monsters leave you alone for the first 31. On the clock it went out after about 20 steps of nonstop walking, and sooner if you stopped ([#80](https://github.com/NesHacker/LabyrinthOfTheDragon/issues/80)).
- Fleeing depends on speed. At even AGL you get away half the time. Each point of AGL you have over the fastest monster still able to chase you adds 1 in 16, and each point it has over you takes 1 in 16 away, from 1 in 8 up to 7 in 8. A blinded or frightened monster can't chase, and if none can, you always get away. A monster that runs from you makes the same roll against your AGL ([#80](https://github.com/NesHacker/LabyrinthOfTheDragon/issues/80)).
- A battle item is used up only when your turn comes. If you lose that turn, or the item would no longer help by then, it stays in your bag.
- Paralysis no longer always costs your turn. Each turn you have a chance to move anyway, as monsters do: 1 in 4 against the weakest paralysis, about 1 in 10 against the strongest.
- An attack dodged with Evasion reads and sounds like a dodge, and its side effects miss too.
- A death knight that rises from an Open Palm gets up untripped, since the line announcing its rise replaces the blow's result.
- The monk's Still Mind also guards against fear for the rest of the battle, and its message says so.
- The magic key counter sits at the top right of the screen.
- B on the hero select screen goes back to the file screen.
- A cure takes effect at once, so a monster can't act on an ailment that's already gone.
- Menace, Darkness, Sleetstorm, and Wild Magic say so when every target is immune, and a monster's fear that doesn't take hold says so, instead of seeming to land.
- Stepping onto a switch, portal, or other trigger tile always works before a random encounter can start.
- A direction still held when a battle menu opens, even one held while walking into the fight, no longer moves the new menu's cursor. Release it and press again. Before, a thumb that lingered on DOWN while opening TECH slid the cursor off the first ability before the player looked.
- When the dragon's fire breath lands in full, it plays the title screen's fire sound.
- FIGHT and single-target abilities aim at the monster you last attacked, as long as it still stands, instead of always starting on the first monster.
- Fireball, Cleave, and Insect Plague say how much damage they deal: a single hit's line against one monster, one number when every monster takes the same, and each monster's damage from left to right otherwise. They showed only their own line before.
- Floor 7's eye lock follows two rules: the left lever opens or shuts the left eye, and the right lever moves every eye one place to the right. Each pull used to jump to a pattern with no rule behind it.
- Bones mark the six fights waiting in floor 8's gauntlet hall. Stepping onto one brings out the monster with the roar and the line it used on its own floor, and the fight starts when the line closes. A beaten monster's bones dim. The fights used to start without warning from plain floor.
- Bones also mark floor 3's four goblin guards, one in front of each skull button, and dim once that guard has fought. The guards used to attack from plain floor.
- Floor 8's healing mirrors are light blue until used, instead of green.
- The random seed also counts your time on the screens before play: title, file, hero, and name, as the original's `RANDOM_SEED` setting describes. It already counted how long you wait on each floor before your first step.

### Balance

- Monster DEF is rescaled, so each step up in a monster's strength costs the same share of your hit chance at every level ([#35](https://github.com/NesHacker/LabyrinthOfTheDragon/issues/35)).
- New SP costs for the druid, monk, and sorcerer, so each can use a new ability a few times when it's learned ([#35](https://github.com/NesHacker/LabyrinthOfTheDragon/issues/35)). Druid: 3, 6, 9, 12, 15, and 19. Monk: 5, 10, 14, 18, 23, and 29. Sorcerer: 4, 8, 12, 15, 20, and 25.
- A weakness doubles ability damage, but a free basic attack deals normal damage ([#41](https://github.com/NesHacker/LabyrinthOfTheDragon/issues/41)).
- The bosses of floors 3 and 5, the gelatinous cube and the death knight, fight at four stars, in the colors they already wore on the map. At two stars most heroes could finish either with one ability at the gate.
- The bosses of floors 1 to 7 fight you from levels 8, 15, 18, 24, 32, 34, and 36, instead of 10, 17, 24, 29, 40, 45, and 45. The gates were written before dying and replaying became the game's loop, and they held heroes back from fights they could win. Each now sits where the weakest class wins about one fight in five, so a hero who isn't ready can try and come back stronger.
- Bark Skin, Regenerate, Diamond Body, and Haste last the whole battle. Haste and Regenerate did nothing before.
- Healing varies by up to a quarter either way, as damage does, and can be a critical or a fumble. The druid's Heal still always fills the bar.
- The dragon has 1939 HP instead of 1236, so its fight lasts long enough for its special moves to come into play. Quivering Palm and Disintegrate can't kill it outright.
- Trip Attack and Open Palm can't knock down the dragon, and Trip Attack can't knock down the gelatinous cube, which Open Palm and Sleetstorm already couldn't. A monster that's down loses its turns, so a fighter could keep either one down for a whole fight.
- The mind flayer and the beholder start their battles at full HP, with their stat bonuses in place. The mind flayer's HP is figured at its own strength, not always the highest.
- Floor 7's elite gives a haste potion, an ATK up, and a DEF up instead of only a haste potion. The elites before it each teach an ability, and a single potion paid no more than a chest on the same floor.
- Ability upgrades set for levels 61 to 81 arrive between levels 51 and 57. XP runs out around level 57, so the old levels took many extra runs to reach, and five of them couldn't be reached at all.

### Fixed

- The monk's Flurry never reached its fourth blow, and its damage wrapped around to small numbers at high levels.
- The monk's Open Palm never got the harder hit its level 30 upgrade was written to give.
- The monk's Open Palm could trip a displacer beast that phased out of the blow.
- A blow the displacer beast phased out of played the hit sound instead of the miss sound.
- A critical hit from a monster attack with a line of its own, such as the dragon's tail whip or the death knight's longsword, played that attack's usual sound instead of the critical sound.
- Using a Remedy in battle made no sound. It plays the healing sound, as potions do.
- A frightened boss, elite, or gauntlet fight could run away, and the battle counted as won. Its door opened without a fight, and a high-level fighter's Menace could run the dragon off to reach the ending. They still try, but can't get away.
- When poison killed you on your own turn, the battle showed no line for it, only the previous line again or an empty box. It says "You succumb to the poison!"
- Hitting yourself while confused didn't shake the screen the way other hits do.
- Wild Magic said "But it fizzles." after a surge that changed a monster's HP or landed a debuff. Those surges show on the monsters, and "But it fizzles." now means the surge did nothing.
- Wild Magic could bring back a monster its own fireball had just felled.
- A lit torch stayed lit through a death, so the first steps back on floor 1 were safe from monsters.
- The buildup toward the next random fight carried over from floor to floor, and into a new game or a return from death. Each arrival on a floor starts fresh with the floor's safe steps.
- A critical hit on a weakness dealt less than a plain hit on the same weakness.
- A death knight got its chance to rise only from a single-target hit, never from an area attack or an outright kill.
- Your own buffs and debuffs never changed your stats. Whatever effect sat in your first slot acted as blindness, ATK Up and DEF Up did nothing, and Haste and AGL Up never raised your AGL.
- Your AGL was 0 in every battle, so quick heroes never acted sooner and fleeing never got the benefit of speed.
- Ailments from your last battle still counted in the next one until your first turn, so after you fled the mind flayer while confused, the rematch could open with its Extract Brain.
- A monster both blinded and hit by ATK Down could keep most of its aim, depending on the order the two landed in.
- A frightened monk's queued Still Mind could be lost to the fear it would have cured. Paralysis and confusion already let it through.
- Dodging the owlbear's knockdown pounce or the beholder's eyestalk ray with Evasion used up one of its uses. A miss never did.
- Floor 8's third chest didn't give the ATK Up and DEF Up its message promised.
- A sconce alcove on floor 7 could be seen but never reached. Once the item room's chest is open, the floor beside it gives way into the alcove, and a cracked floor there drops you back to the lever hall.
- Floor 7's cracked floors played the portal sound instead of the falling one.
- The orb above floor 7's boss door stayed dark when the eye lock opened the door. It now lights up green, as the orbs above the switches do.
- Floor 2's elite bugbear was drawn on the map in two-star colors, where every other elite uses three-star colors.
- A stairway on floor 2 could be walked into from the side, through the wall it's set in.
- Three hidden passages on floors 4 and 5 that open through brick left the hero in plain view on the brick. They hide the hero, as floor 2's always did.
- The fighter's Cleave aimed with MATK and dealt magic damage, so it hit the gelatinous cube and zombies for double and the death knight and mind flayer for half. It's a physical attack, aimed with ATK against DEF.
- The gelatinous cube's immunity to Sleetstorm carried over to whichever monster took its place next.
- Monsters resisted the wrong status effects. The bugbear shrugged off fear and paralysis instead of confusion and poison, the gelatinous cube never resisted poison, and the will-o-wisp and death knight resisted DEF Down instead of dark damage.
- Pressing A on an empty item list in battle read past the end of the inventory.
- The title screen showed PRESS START before it would respond to it.
- Coming back from the credits left every sprite hidden until the power was cycled: the hero was invisible on the file screen, the hero select screen, and the map.
- The key counter went blank past 9 keys. It now shows "*".
- After a death, floor 1 kept the encounter rate of the floor where you fell. It now starts fresh, as other floors do when you reach them, and its hidden kobold is back.
- A new game started after the credits kept the last hero's torch lit for a few seconds, out of sight but still keeping random fights away.
- After a death, floor 7's eye lock went on from the last visit's pulls while its eyes showed open.
- A healing mirror used before a death looked new on the next visit to floor 8. It stays used, and now looks it.
- Stat lookups could read outside their tables: a monster left at level 0 read the entry before its row ([#78](https://github.com/NesHacker/LabyrinthOfTheDragon/issues/78)). A review of the whole codebase turned up many smaller bugs.

### Text

- Wild Magic, critical and fumbled heals, unlocking a door with a magic key, the kobold's daze, and the will-o-wisp's lightning use the lines written for them.
- A chest holding one potion or ether says "You get a potion!" or "You get an ether!" instead of "a potions" or "an ethers".
- Open Palm always opens with "You strike with an open palm!" A trip reads after the damage instead of replacing that line, on a page of its own after a resisted hit.
- The bugbear's roar says "Terror grips you!" when it lands, so it no longer reads the same as a turn lost to that fear, which says "You shiver with fear!".
- An elite you beat again after a death says "You've learned all it can teach." It used to teach you the ability you already had over again, sound and all.
- A doubled word is gone from the credits, and a card for this fork follows the original's credits.
- Monsters go by their full names in every battle line. The lines all monsters share shortened five of them to G.Cube, D.Beast, W.O.Wisp, D.Knight, and M.Flayer, while their own attack lines spelled the names out.
- Lines of text break only at spaces and use the box's full width. An ellipsis no longer sits alone on the last row, as it did in the gelatinous cube's and the will-o-wisp's lines, and several three-row lines now fit in two.
- Four typos in battle lines are fixed: the druid's bolts of "lighting", a resolve that doesn't "waiver", a confused monster attacking "any ally", and the "deathknight" that rises.

### For developers

- An emulator test suite in `tools/emu` that plays the real ROM with PyBoy, with a test for most of the fixes above, plus static audits and balance scripts.
- A player's manual (`docs/README.md`) and a walkthrough (`docs/walkthrough`) whose maps are drawn from the game's own data by `tools/docs/render_maps.py`.
- The cartridge header carries the title LABYRINTH and a version byte, both set in the Makefile.
- Every pull request builds the ROM and attaches it to the run in a zip with a preview of the release notes and a PDF of the player's manual from `tools/docs/render_manual.py`. Every merge to main also publishes the ROM as a GitHub release, with the changelog lines the merge added as its notes.
- The build numbers every ROM from the Makefile's major and minor version and a patch that counts the commits since that version changed. The file screen shows the result, such as v1.1.4, with a "+" on any build that isn't a release.
- SELECT on the name entry screen starts a new game on a lower floor, B2 to B8, with the level, abilities, magic keys, and items a first run would bring there, to test a floor without playing the ones before it.
- A plain `make` builds a complete ROM in a fresh clone or right after `make clean`, with no separate `make assets` step, and changing a header rebuilds what depends on it.
- The build has no compiler warnings. The start mode in `src/main.c`, normal play or one of the test modes, is a preprocessor switch, so the modes not picked leave no unreachable code ([#74](https://github.com/NesHacker/LabyrinthOfTheDragon/issues/74)).

### Known issues

- [#72](https://github.com/NesHacker/LabyrinthOfTheDragon/issues/72), an item that's invisible but still selectable in fights with gelatinous cubes, didn't reproduce. It's still open.
- In one fight with a single monster on floor 2, attacks went off on the first press every turn, skipping the step where you pick a target. It was seen once, on a ModRetro Chromatic, and didn't reproduce. It's still open.
