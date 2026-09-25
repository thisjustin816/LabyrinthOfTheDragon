"""T23 - PRESS START stays dark until START is actually read.

The main title plays the dragon's fire for about two seconds before it reads
the joypad, so a lit PRESS START during the fire invites a press that does
nothing. init_main_title loads the prompt's palette black and
update_fire_animation lights it on the frame the title starts reading START. Both ways onto the main title are checked: a cold boot through
the studio card and the dragon's eyes, and a quit from the map, which goes
straight into the fire.

The prompt is the eight cells (6..13, 7) on BG palette 5 (title_screen.c,
"Palette 6 - PRESS START"). Nothing else on the screen uses that palette, and
the fire and smoke sprites sit well below row 7, so a bright yellow pixel in
that box is the prompt and nothing else.
"""
from lotd import *

MTS = SYM["main_title_state"]
BOX = (6 * 8, 7 * 8, 14 * 8, 8 * 8)   # x0, y0, x1, y1 in pixels


def prompt_lit(g):
    img = g.pb.screen.image.convert("RGB").crop(BOX)
    # Palette 6 color 0 is RGB8(251, 242, 54): bright red and green, low blue.
    return sum(1 for (r, gr, b) in img.getdata() if r > 180 and gr > 180 and b < 120)


def watch(g, chk, label):
    """Tick frame by frame through the main title's fire and into the wait,
    rendering every frame, and report the prompt's lit-pixel count per state."""
    fire_frames = fire_lit = 0
    wait_frames = 0
    wait_lit_first = None
    shot_fire = False
    for _ in range(2400):
        g.tick(1, True)
        if g.get("title_state") != 2:
            continue
        mts = g.rd8(MTS)
        lit = prompt_lit(g)
        if mts == 0:
            fire_frames += 1
            fire_lit = max(fire_lit, lit)
            if fire_frames == 60 and not shot_fire:
                g.shot(f"{label.replace(' ', '_')}_mid_fire", render=False)
                shot_fire = True
        else:
            wait_frames += 1
            if wait_lit_first is None:
                wait_lit_first = lit
            if wait_frames == 30:
                g.shot(f"{label.replace(' ', '_')}_waiting", render=False)
                break
    print(f"{label}: {fire_frames} fire frames, max lit pixels during fire={fire_lit}; "
          f"first waiting frame lit pixels={wait_lit_first}")
    chk(f"T23 {label}: the fire actually played", fire_frames > 60, str(fire_frames))
    chk(f"T23 {label}: PRESS START dark on every fire frame", fire_lit == 0, str(fire_lit))
    chk(f"T23 {label}: PRESS START lit on the first frame START is read",
        (wait_lit_first or 0) > 50, str(wait_lit_first))
    # And the lit prompt is live.
    g.press("start", hold=2, wait=20)
    chk(f"T23 {label}: START from the lit prompt reaches save select",
        g.wait_for(lambda: g.gs() == GS["SAVE_SELECT"], 120), f"gs={g.gs()}")


chk = Checker("t23_title_prompt")
g = Game(tag="t23")
watch(g, chk, "cold boot")

g.tick(8); g.save_select_pick(0); g.hero_select_pick(0); g.tick(20)
chk("T23 reached the map", g.gs() == GS["WORLD_MAP"], f"gs={g.gs()}")
g.press("start", wait=14); g.press("down", wait=8); g.press("right", wait=8)
g.press("a", wait=12); g.press("left", wait=8); g.press("a", wait=4)
chk("T23 quit reaches the title", g.wait_for(lambda: g.gs() == GS["TITLE"], 120), f"gs={g.gs()}")
watch(g, chk, "after quit")
g.close()
chk.summary()
