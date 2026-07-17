#!/usr/bin/env python3
"""costumes — the Clawdrobe on the desk daemon.

MIRROR, NOT SOURCE. web/clawd-core.js is canonical for Clawd's art and
poses: author there first, then mirror the change here. Never the reverse.
(Until 2026-07-17 this file called clawd-core.js the source of truth while
clawd-core.js called clawdpadd.py the source of truth — each named the
other, so there was no reference to diff against.)

Props layer over the Clawd body; skins replace it. All return 675-byte
RGB888 frames. Verify headlessly before shipping — see
docs/MAKING-COSTUMES.md and `node tools/webpreview.mjs`."""

import math

CORAL = (217, 119, 87)

COSTUMES = [  # (id, emoji, label, is_skin)
    ("none", "paw", "just clawd", False),
    ("tophat", "hat", "dapper", False), ("shades", "cool", "too cool", False),
    ("party", "party", "party", False), ("crown", "crown", "royalty", False),
    ("phones", "phones", "vibin", False), ("scarf", "scarf", "cozy", False),
    ("bow", "bow", "cutie", False), ("halo", "halo", "angel", False),
    ("horns", "devil", "lil devil", False), ("wizard", "wiz", "wizard", False),
    ("cowboy", "hat", "howdy", False), ("flower", "flower", "bloom", False),
    ("ghost", "ghost", "spooky pal", True), ("puff", "puff", "pink puff", True),
    ("chomper", "chomp", "chomper", True), ("robot", "bot", "beep boop", True),
    ("cat", "cat", "kitty", True), ("frog", "frog", "froggy", True),
    ("alien", "alien", "alien", True), ("pumpkin", "pump", "spooky", True),
    ("star", "star", "superstar", True), ("bee", "bee", "buzzy", True),
]
SKINS = {c[0] for c in COSTUMES if c[3]}


def _p(buf, x, y, r, g, b):
    if 0 <= x < 15 and 0 <= y < 15:
        i = (y * 15 + x) * 3
        buf[i] = max(0, min(255, int(r)))
        buf[i + 1] = max(0, min(255, int(g)))
        buf[i + 2] = max(0, min(255, int(b)))


def _body(br, dx, dy, eyes, look, tint=CORAL, arm_l_dy=0, arm_r_dy=0):
    """The Clawd body, tintable. arm_*_dy raise (negative) or droop an arm.

    Mirrors clawd-core.js `body()`. The arm offsets landed 2026-07-17: without
    them `dressed()` could not express a raised arm, so clawdpadd.py had to
    exclude notify/celebrate from the costume path — meaning a costumed Clawd
    could wave and jump in the browser but not on the desk.
    """
    buf = bytearray(675)
    r, g, b = tint[0] * br, tint[1] * br, tint[2] * br
    def rect(x0, y0, x1, y1, oy=0):
        for y in range(y0 + dy + oy, y1 + dy + oy):
            for x in range(x0 + dx, x1 + dx):
                _p(buf, x, y, r, g, b)
    rect(2, 3, 13, 11)
    rect(0, 7, 2, 9, arm_l_dy); rect(13, 7, 15, 9, arm_r_dy)
    for lx in (3, 5, 9, 11):
        rect(lx, 11, lx + 1, 13)
    for ex in (4, 10):
        x = ex + dx + look
        _p(buf, x, 6 + dy, 0, 0, 0)
        if eyes:
            _p(buf, x, 5 + dy, 0, 0, 0)
    return buf


def _prop(cid, buf, dx, dy, look, t):
    P = lambda x, y, r, g, b: _p(buf, x, y, r, g, b)
    if cid == "tophat":
        for x in range(3, 12): P(x+dx, 2+dy, 40, 36, 44)
        for y in range(0, 2):
            for x in range(5, 10): P(x+dx, y+dy, 52, 46, 58)
        for x in range(5, 10): P(x+dx, 1+dy, 180, 60, 70)
    elif cid == "shades":
        for yy in (5+dy, 6+dy):
            for x in range(3, 6): P(x+dx+look, yy, 18, 16, 20)
            for x in range(9, 12): P(x+dx+look, yy, 18, 16, 20)
        for x in range(6, 9): P(x+dx+look, 5+dy, 30, 26, 32)
        P(4+dx+look, 5+dy, 90, 90, 110); P(10+dx+look, 5+dy, 90, 90, 110)
    elif cid == "party":
        P(7+dx, 0+dy, 255, 210, 60)
        for x in range(6, 9): P(x+dx, 1+dy, 235, 90, 160)
        for x in range(5, 10):
            e = (x+dx) % 2 == 0
            P(x+dx, 2+dy, 90 if e else 235, 170 if e else 90, 235 if e else 160)
    elif cid == "crown":
        for x in (4, 7, 10): P(x+dx, 1+dy, 255, 205, 40)
        for x in range(4, 11): P(x+dx, 2+dy, 255, 205, 40)
        P(7+dx, 2+dy, 220, 60, 90)
    elif cid == "phones":
        for x in range(4, 11): P(x+dx, 1+dy, 46, 42, 50)
        for s in (-1, 1):
            cx = 7 + s*6
            for y in range(5, 8):
                P(cx+dx, y+dy, 46, 42, 50); P(cx-s+dx, y+dy, 217, 119, 87)
            P(cx+dx, 4+dy, 46, 42, 50); P(cx+dx, 3+dy, 46, 42, 50)
    elif cid == "scarf":
        for x in range(3, 12): P(x+dx, 10+dy, 200, 60, 60)
        for x in range(4, 11): P(x+dx, 11+dy, 170, 45, 45)
        P(10+dx, 12+dy, 200, 60, 60)
        if math.sin(t*2.3) > 0.3: P(11+dx, 12+dy, 200, 60, 60)
    elif cid == "bow":
        P(6+dx, 10+dy, 235, 90, 140); P(8+dx, 10+dy, 235, 90, 140)
        P(7+dx, 10+dy, 255, 150, 190)
        P(6+dx, 9+dy, 235, 90, 140); P(8+dx, 9+dy, 235, 90, 140)
    elif cid == "halo":
        for x in range(5, 10): P(x+dx, 0+dy, 255, 225, 90)
        P(5+dx, 1+dy, 255, 225, 90); P(9+dx, 1+dy, 255, 225, 90)
    elif cid == "horns":
        P(3+dx, 2+dy, 200, 40, 40); P(3+dx, 1+dy, 220, 60, 60)
        P(11+dx, 2+dy, 200, 40, 40); P(11+dx, 1+dy, 220, 60, 60)
    elif cid == "wizard":
        P(7+dx, 0+dy, 120, 80, 200)
        for x in range(6, 9): P(x+dx, 1+dy, 120, 80, 200)
        for x in range(4, 11): P(x+dx, 2+dy, 100, 66, 175)
        P(7+dx, 1+dy, 255, 235, 120)
    elif cid == "cowboy":
        for x in range(2, 13): P(x+dx, 2+dy, 150, 100, 55)
        for x in range(5, 10): P(x+dx, 1+dy, 120, 80, 45)
        for x in range(5, 10): P(x+dx, 0+dy, 120, 80, 45)
    elif cid == "flower":
        P(7+dx, 0+dy, 255, 210, 70)
        P(6+dx, 0+dy, 235, 100, 170); P(8+dx, 0+dy, 235, 100, 170)
        P(7+dx, 1+dy, 90, 190, 90)


def _robot(br, dx, dy, eyes):
    buf = bytearray(675); s = 200*br; d = 120*br
    for y in range(3, 12):
        for x in range(3, 12): _p(buf, x+dx, y+dy, s, s, 210*br)
    for x in range(2, 13):
        _p(buf, x+dx, 3+dy, d, d, d); _p(buf, x+dx, 11+dy, d, d, d)
    _p(buf, 7+dx, 1+dy, d, d, d); _p(buf, 7+dx, 0+dy, 255, 80, 80)
    for ex in (5, 9):
        on = (90, 220, 255) if eyes else (40, 60, 70)
        _p(buf, ex+dx, 6+dy, on[0]*br, on[1]*br, on[2]*br)
    for x in range(5, 10): _p(buf, x+dx, 8+dy, d, d, d)
    for lx in (4, 10):
        _p(buf, lx+dx, 12+dy, d, d, d); _p(buf, lx+dx, 13+dy, d, d, d)
    return buf


def _cat(br, dx, dy, eyes, look):
    buf = _body(br, dx, dy, eyes, look, (230, 150, 90))
    for ex in (2, 12):
        _p(buf, ex+dx, 2+dy, 230*br, 150*br, 90*br)
        _p(buf, ex+dx, 1+dy, 200*br, 120*br, 70*br)
    for s in (-1, 1):
        _p(buf, 7+s*4+dx, 7+dy, 240, 240, 230)
        _p(buf, 7+s*5+dx, 7+dy, 240, 240, 230)
    _p(buf, 7+dx, 7+dy, 255, 150, 170)
    return buf


def _frog(br, dx, dy, eyes):
    buf = bytearray(675); gd = 80*br
    for y in range(4, 12):
        for x in range(2, 13):
            if math.hypot(x-7-dx, y-7.5-dy) < 5.4:
                _p(buf, x+dx, y+dy, gd, 190*br, gd)
    for ex in (4, 10):
        _p(buf, ex+dx, 3+dy, 210*br, 240*br, 210*br)
        _p(buf, ex+dx, 2+dy, 210*br, 240*br, 210*br)
        if eyes: _p(buf, ex+dx, 3+dy, 20, 30, 20)
    for x in range(5, 10): _p(buf, x+dx, 9+dy, 40, 90, 40)
    return buf


def _alien(br, dx, dy, eyes):
    buf = bytearray(675)
    for y in range(2, 13):
        for x in range(3, 12):
            w = 1 - abs(y-5)*0.06
            if abs(x-7-dx) < 4.2*w: _p(buf, x+dx, y+dy, 120*br, 210*br, 120*br)
    for ex in (-2, 2):
        _p(buf, 7+ex+dx, 5+dy, 10, 15, 10)
        _p(buf, 7+ex+dx-(1 if ex > 0 else -1), 5+dy, 10, 15, 10)
        _p(buf, 7+ex+dx, 6+dy, 10, 15, 10)
    return buf


def _pumpkin(br, dx, dy, eyes):
    buf = bytearray(675)
    for y in range(2, 13):
        for x in range(1, 14):
            if math.hypot((x-7-dx)*0.85, y-7-dy) < 5.6:
                _p(buf, x+dx, y+dy, 255*br, 140*br, 20*br)
    _p(buf, 7+dx, 1+dy, 90*br, 150*br, 60*br)
    g = 30 if eyes else 10
    for ex in (4, 10):
        _p(buf, ex+dx, 5+dy, g, g, g); _p(buf, ex+dx, 6+dy, g, g, g)
    _p(buf, 7+dx, 6+dy, g, g, g)
    for x in range(4, 11): _p(buf, x+dx, 9+dy, g, g, g)
    for x in (5, 7, 9): _p(buf, x+dx, 8+dy, g, g, g)
    return buf


_STAR = ["0000001000000","0000011100000","0000011100000","1111111111111",
         "0111111111110","0011111111100","0001111111000","0011111111100",
         "0011110111100","0111100011110","0110000000110","0000000000000"]


def _star(br, dx, dy, eyes):
    buf = bytearray(675)
    for r, row in enumerate(_STAR):
        for c in range(13):
            if row[c] == "1": _p(buf, c+1+dx, r+1+dy, 255*br, 205*br, 60*br)
    for ex in (5, 9):
        if eyes: _p(buf, ex+dx, 6+dy, 40, 30, 10)
    return buf


def _bee(br, dx, dy, eyes, t):
    buf = bytearray(675)
    for y in range(5, 12):
        for x in range(4, 11):
            if math.hypot(x-7-dx, y-8-dy) < 3.6:
                st = (y+dy) % 2 == 0
                _p(buf, x+dx, y+dy, 30 if st else 255*br,
                   25 if st else 210*br, 20 if st else 30)
    for wx in (3, 11):
        up = 0 if math.sin(t*12) > 0 else 1
        _p(buf, wx+dx, 5+up+dy, 220, 230, 255)
        _p(buf, wx+(1 if wx < 7 else -1)+dx, 5+up+dy, 220, 230, 255)
    for ex in (6, 8):
        if eyes: _p(buf, ex+dx, 6+dy, 15, 12, 8)
    return buf


def _ghost(br, dx, dy, eyes, look, t):
    buf = bytearray(675); r, g, b = 150*br, 190*br, 255*br
    for y in range(2, 13):
        for x in range(2, 13):
            cx = x - 7 - dx
            dome = math.hypot(cx, (y-6-dy)*1.1) < 5.4 and y <= 6+dy
            body = 6+dy <= y <= 11+dy and abs(cx) < 5.2
            skirt = y == 12+dy and abs(cx) < 5.2 and (x+int(t*3)) % 2 == 0
            if dome or body or skirt: _p(buf, x, y, r, g, b)
    for s in (-1, 1):
        ex, ey = 7+s*2+dx, 5+dy
        _p(buf, ex, ey, 245, 245, 250); _p(buf, ex, ey+1, 245, 245, 250)
        if eyes: _p(buf, ex+max(-1, min(1, look)), ey+1, 30, 30, 60)
    return buf


def _puff(br, dx, dy, eyes, look):
    buf = bytearray(675)
    for y in range(15):
        for x in range(15):
            if math.hypot(x-7-dx, y-7-dy) < 5.2: _p(buf, x, y, 255*br, 150*br, 185*br)
    for s in (-1, 1):
        for fx in range(2): _p(buf, 7+s*3-fx*s+dx, 12+dy, 200*br, 40*br, 70*br)
        _p(buf, 7+s*3+dx, 8+dy, 255*br, 110*br, 150*br)
        ex = 7+s*2+dx+max(-1, min(1, look))
        _p(buf, ex, 6+dy, 25, 20, 35)
        if eyes:
            _p(buf, ex, 5+dy, 25, 20, 35); _p(buf, ex, 4+dy, 90, 85, 120)
    return buf


def _chomper(br, dx, dy, t, facing_right):
    buf = bytearray(675)
    mouth = 0.18 + 0.42*abs(math.sin(t*5))
    for y in range(15):
        for x in range(15):
            cx, cy = x-7-dx, y-7-dy
            if math.hypot(cx, cy) < 5.4:
                ang = math.atan2(cy, cx if facing_right else -cx)
                if abs(ang) > mouth: _p(buf, x, y, 255*br, 215*br, 0)
    _p(buf, 7+dx+(1 if facing_right else -1), 4+dy, 25, 22, 18)
    return buf


def dressed(cid, br, dx, dy, eyes, look, t, arm_l_dy=0, arm_r_dy=0):
    """Dress Clawd. Skins ignore the arm offsets — they're whole other bodies
    with their own anatomy; props ride on top of the arm-raised body. Same
    rule as clawd-core.js `dressed()`."""
    if cid == "ghost": buf = _ghost(br, dx, dy, eyes, look, t)
    elif cid == "puff": buf = _puff(br, dx, dy, eyes, look)
    elif cid == "chomper": buf = _chomper(br, dx, dy, t, math.sin(t*0.13) >= 0)
    elif cid == "robot": buf = _robot(br, dx, dy, eyes)
    elif cid == "cat": buf = _cat(br, dx, dy, eyes, look)
    elif cid == "frog": buf = _frog(br, dx, dy, eyes)
    elif cid == "alien": buf = _alien(br, dx, dy, eyes)
    elif cid == "pumpkin": buf = _pumpkin(br, dx, dy, eyes)
    elif cid == "star": buf = _star(br, dx, dy, eyes)
    elif cid == "bee": buf = _bee(br, dx, dy, eyes, t)
    else: buf = _body(br, dx, dy, eyes, look, CORAL, arm_l_dy, arm_r_dy)
    if cid != "none" and cid not in SKINS:
        _prop(cid, buf, dx, dy, look, t)
    return buf
