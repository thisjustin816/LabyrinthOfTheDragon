# Labyrinth of the Dragon (GBC)
An 8-bit Adventure RPG with D&D Monsters!

Play as an adventurer locked in a dungeon, and work your way down eight floors
by solving puzzles, fighting monsters, leveling up, and collecting treasure.

## About this fork

Labyrinth of the Dragon is NesHacker's game, and it was already one of my
favorite modern Game Boy games. When I started, the original repository hadn't
been updated in over a year, and its last release, 1.0.5 Alpha, had no way to
save. I began by finishing the save system so I could play it on real
hardware. That turned into trying to finish the game, as faithfully to the
original intent as I could work out from the code, the issues, and the game
itself.

This fork was written with help from [Claude Code](https://claude.com/claude-code).
The original was made without generative AI, and this fork isn't affiliated
with or endorsed by its developer. The original is on
[itch.io](https://neshacker.itch.io/labyrinth-of-the-dragon) and
[GitHub](https://github.com/NesHacker/LabyrinthOfTheDragon). See the
[changelog](CHANGELOG.md) for everything that changed, the
[player's manual](docs/README.md) for how to play, and the
[walkthrough](docs/walkthrough/README.md) if you get stuck.

## Version

The major and minor version, such as `1.1`, is `VERSION` in the `Makefile`.
Every build adds the patch, the number of commits since that line last changed,
and shows the full version on the file screen. A release shows it as is, such
as `v1.1.4`. Any other build adds a `+`, as in `v1.1.4+`, so a test build can't
pass for a release. Two builds of the same commit get the same number, whether
they run locally or in the workflow. Counting needs the history back to that
change, so a build without it, from a shallow clone or a downloaded archive,
shows no patch, as in `v1.1+`.

The major version also goes in the cartridge header's version byte at 0x14C.
The changelog's latest heading and the credits card's `fork` line in
`assets/strings.js` name the major and minor version, as `## 1.1` and
`1.1 FORK`, so change them along with the `Makefile`.

The build workflow, `.github/workflows/build.yml`, builds the ROM with
GBDK-2020 4.5.0 for every pull request and every push to main. A pull request
builds its own head commit rather than GitHub's merge preview, so its number
matches a local build. The workflow stops if the `Makefile`, the changelog, and
the credits card disagree. Each run attaches a zip named after the ROM, such as
`LabyrinthOfTheDragon-v1.1.4+.zip`, that holds the ROM, the release notes in
`release-notes.md`, and a PDF of the player's manual, which
`tools/docs/render_manual.py` prints with headless Chrome.

Every push to main is a release: it builds with `make RELEASE=1` and publishes
the ROM as a GitHub release tagged with its version. Its notes are the lines
that push added to `CHANGELOG.md`, under their section headings, which
`tools/changelog2notes` prints for any earlier commit. When it added none,
GitHub's list of merged pull requests stands in. So a pull request adds its own
bullets under the current heading. Its zip's `release-notes.md` previews the
notes its merge would publish, and is empty when the merge would fall back to
GitHub's list. Merge pull requests with a merge commit, not a squash. A squash
replaces a branch's commits with one, so the release after it could number
below the branch's own test builds.

## Starting on a Later Floor

To test a floor without playing the ones before it, press SELECT on the name
entry screen. Each press moves the label under the letters on from START B2 to
START B8, and then back to blank for a normal start. START begins on that
floor at about the level a first run reaches it, with the abilities, magic
keys, and items that run would have. The table is `floor_starts` in
`src/name_entry.c`, and t60 checks its keys and items against the floors' own
chests.

## How to Build the ROM

### Dependencies
* [GBDK-2020](https://github.com/gbdk-2020/gbdk-2020) - The Game Boy Development
  kit. Includes the libraries and binaries for C development on the Game Boy.
* [GNU Make](https://gnuwin32.sourceforge.net/packages/make.htm) - Build system
  tool (installation should only be required on Windows).
* [NodeJS](https://nodejs.org) - Used to run the custom tools NesHacker made in
  the course of developing the game.

### Use Make to Build the ROM
Update the `Makefile` or define a shell variable named `GBDK_HOME` pointing to
the directory where you installed GBDK.

To build the ROM run the following commands:

* `npm install`
* `make assets`
* `make`
