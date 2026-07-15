#!/usr/bin/env python3
"""Render Galaxy-Watch-ready Clawd assets from the real frame functions.

Outputs (450x450, round-face safe — content fits the inscribed circle):
  docs/watch/clawd_face.png   hero still (awake, eyes open) — photo watch face
  docs/watch/clawd_face.gif   breathing/blink loop — WatchMaker/Facer GIF layer
  docs/watch/clawd_sleep.png  dim sleeping variant — night photo face

Usage: .venv/bin/python tools/make_watch_assets.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from PIL import Image, ImageDraw  # noqa: E402

import clawdpadd as c  # noqa: E402

SIZE = 450
BG = (12, 10, 10)
# 15 LEDs must fit the inscribed circle: use ~0.62 of the diameter so the
# sprite clears round bezels and watch complications comfortably.
CELL = 20
DOT = 16
GRID = 15 * CELL
OFF = (SIZE - GRID) // 2


def render(buf):
    img = Image.new("RGB", (SIZE, SIZE), BG)
    d = ImageDraw.Draw(img)
    # faint LED grid so it reads as "his block", not clip art
    for y in range(15):
        for x in range(15):
            cx = OFF + x * CELL + CELL // 2
            cy = OFF + y * CELL + CELL // 2
            i = (y * 15 + x) * 3
            r, g, b = buf[i], buf[i + 1], buf[i + 2]
            if max(r, g, b) < 8:
                d.ellipse((cx - 2, cy - 2, cx + 2, cy + 2), fill=(22, 18, 17))
            else:
                d.ellipse((cx - DOT // 2, cy - DOT // 2,
                           cx + DOT // 2, cy + DOT // 2), fill=(r, g, b))
    return img


def main():
    out = "docs/watch"
    os.makedirs(out, exist_ok=True)
    render(c.frame_awake(1.0)).save(f"{out}/clawd_face.png")
    render(c.frame_sleep(2.0)).save(f"{out}/clawd_sleep.png")
    frames, t = [], 0.0
    while t < 6.5:  # one full breath, includes a blink at ~4.3s
        frames.append(render(c.frame_awake(t)))
        t += 0.15
    frames[0].save(f"{out}/clawd_face.gif", save_all=True,
                   append_images=frames[1:], duration=150, loop=0,
                   optimize=True)
    for f in os.listdir(out):
        print(f"{out}/{f}: {os.path.getsize(os.path.join(out, f))} bytes")


if __name__ == "__main__":
    main()
