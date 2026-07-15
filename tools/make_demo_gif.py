#!/usr/bin/env python3
"""Render docs/demo.gif from clawdpadd's real frame functions.

Each LED becomes a soft round dot on dark glass, so the GIF looks like the
actual Lightpad. Usage: .venv/bin/python tools/make_demo_gif.py [out.gif]
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from PIL import Image, ImageDraw  # noqa: E402

import clawdpadd as c  # noqa: E402

CELL = 22          # px per LED
DOT = 17           # dot diameter
BG = (14, 11, 10)  # dark glass


def render(buf):
    img = Image.new("RGB", (15 * CELL, 15 * CELL), BG)
    d = ImageDraw.Draw(img)
    for y in range(15):
        for x in range(15):
            i = (y * 15 + x) * 3
            r, g, b = buf[i], buf[i + 1], buf[i + 2]
            if max(r, g, b) < 8:
                continue
            cx, cy = x * CELL + CELL // 2, y * CELL + CELL // 2
            d.ellipse((cx - DOT // 2, cy - DOT // 2,
                       cx + DOT // 2, cy + DOT // 2), fill=(r, g, b))
    return img


def frange(stop, step):
    t = 0.0
    while t < stop:
        yield t
        t += step


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "docs/demo.gif"
    frames = []
    # awake: breathe, glance, catch a blink (t=4.3 blink window)
    frames += [render(c.frame_awake(t)) for t in frange(6.5, 0.12)]
    # petting sweep: finger slides across, he leans and follows
    for i, t in enumerate(frange(2.4, 0.12)):
        frames.append(render(c.frame_awake(6.5 + t, (i / 20.0, 0.35, 0.7))))
    # thinking: pacing (phase sweep)
    frames += [render(c.frame_thinking(p, p)) for p in frange(9.0, 0.22)]
    # notify: waving
    frames += [render(c.frame_notify(t)) for t in frange(2.5, 0.1)]
    # celebrate: both arms up, jumping
    frames += [render(c.frame_celebrate(t)) for t in frange(2.4, 0.1)]
    # sleep: dim, eyes closed
    frames += [render(c.frame_sleep(t)) for t in frange(3.5, 0.18)]
    frames[0].save(out, save_all=True, append_images=frames[1:],
                   duration=110, loop=0, optimize=True)
    print(f"{out}: {len(frames)} frames, {os.path.getsize(out)} bytes")


if __name__ == "__main__":
    main()
