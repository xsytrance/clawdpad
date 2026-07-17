#!/usr/bin/env python3
"""parity.py — prove Clawd looks the same on the desk and in the browser.

Golden vectors prove clawd-core.js speaks the same *protocol* as blocksd.
Nothing proved it draws the same *creature* as clawdpadd.py — and by
2026-07-17 it didn't:

  - a costumed Clawd could wave and jump in the browser but not on the desk
    (costumes.dressed() had no arm offsets)
  - `frame_thinking` had no JS counterpart at all — the tab could not show
    him pacing while Claude works
  - the tab's sleeping Clawd neither breathed nor peeked (a flat 0.22 body)
  - a marquee hid an urgent wave in the browser, but not on the desk

Every one of those shipped, and every one is invisible without a block and
two machines. This renders both implementations of the shared pose surface
and compares the bytes.

    .venv/bin/python3 tools/parity.py          # all cases
    .venv/bin/python3 tools/parity.py -v       # show ASCII on failure

Poses that intentionally exist on only one side are listed in ONE_SIDED and
skipped — see docs/POSES.md. Add to that list only with a reason.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Poses that legitimately live on one side only. Not drift — architecture.
ONE_SIDED = {
    "python": ["pong", "visit", "heart", "empty", "glyph_big", "touch poses",
               "vigor/hunger dimming",     # daemon-context: multi-block, sensor, soul
               "battery body language"],   # host-applied multipliers, not poses:
                                           # the tab has no battery to be tired about
    "js":     ["dance", "miniDance", "rgb565"],  # web/Android ears; RGB565 is a
                                                 # WebMIDI-side wire concern
}

# (name, python expr, js expr) — evaluated with `m` (clawdpadd) / `costumes`
# and `Clawd` respectively. Keep the arguments identical on both sides.
CASES = [
    ("awake t=0.3",        "m.frame_awake(0.3)",            "Clawd.awake(0.3)"),
    ("awake t=2.7",        "m.frame_awake(2.7)",            "Clawd.awake(2.7)"),
    ("awake t=11.0",       "m.frame_awake(11.0)",           "Clawd.awake(11.0)"),
    ("sleep t=1.0",        "m.frame_sleep(1.0)",            "Clawd.sleep(1.0)"),
    ("sleep t=9.8 (peek)", "m.frame_sleep(9.8)",            "Clawd.sleep(9.8)"),
    ("thinking ph=2 t=.3", "m.frame_thinking(2.0, 0.3)",    "Clawd.thinking(2.0, 0.3)"),
    ("thinking ph=0 t=1",  "m.frame_thinking(0.0, 1.0)",    "Clawd.thinking(0.0, 1.0)"),
    ("thinking ph=5.5",    "m.frame_thinking(5.5, 2.7)",    "Clawd.thinking(5.5, 2.7)"),
    ("notify/wave t=0",    "m.frame_notify(0.0)",           "Clawd.wave(0.0)"),
    ("notify/wave t=0.3",  "m.frame_notify(0.3)",           "Clawd.wave(0.3)"),
    ("celebrate rel=0",    "m.frame_celebrate(0.0)",        "Clawd.celebrate(0.0)"),
    ("celebrate rel=0.3",  "m.frame_celebrate(0.3)",        "Clawd.celebrate(0.3)"),
    ("mini awake t=3",     "m._mini_frame('awake', 3.0, 0, None, 1.0)",
                           "Clawd.miniAwake(3.0)"),
    ("mini notify t=0.3",  "m._mini_frame('notify', 0.3, 0, None, 1.0)",
                           "Clawd.miniWave(0.3)"),
    ("mini sleep t=1",     "m._mini_frame('sleep', 1.0, 0, None, 1.0)",
                           "Clawd.miniSleep(1.0)"),
    ("mini thinking ph=2", "m._mini_frame('thinking', 0.3, 2.0, None, 1.0)",
                           "Clawd.miniThinking(2.0, 0.3)"),
    ("mini celebrate r=.3", "m._mini_frame('celebrate', 0.3, 0, None, 1.0)",
                            "Clawd.miniCelebrate(0.3)"),
    ("marquee 'HI'",       "m._marquee_frame('HI', 1.0)",
                           "Clawd.marquee('HI', 1.0, Clawd.CORAL)"),
]

# (costume, dx, dy, arm_l, arm_r) — the arm-offset path that was broken.
COSTUME_CASES = [
    ("none", 0, 0, 0, 0), ("none", 0, 0, 0, -2),
    ("tophat", 0, 0, 0, 0), ("tophat", 0, 0, 0, -2),
    ("tophat", 0, -2, -2, -2), ("bowtie", 0, 0, 0, -1),
    ("scarf", 1, 0, -2, -2), ("robot", 0, 0, 0, -2),
    ("cat", 0, 0, -2, -2), ("ghost", 0, 0, 0, -2),
]


def load_daemon():
    spec = importlib.util.spec_from_file_location("cp", ROOT / "clawdpadd.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def render_python():
    m = load_daemon()  # noqa: F841 — used by eval
    sys.path.insert(0, str(ROOT))
    import costumes

    out = {}
    for name, py, _ in CASES:
        out[name] = list(bytes(eval(py)))  # noqa: S307 — table above is the input
    for cid, dx, dy, al, ar in COSTUME_CASES:
        key = f"dressed {cid} dx={dx} dy={dy} arms={al},{ar}"
        out[key] = list(bytes(costumes.dressed(
            cid, 1.0, dx, dy, True, 0, 1.0, arm_l_dy=al, arm_r_dy=ar)))
    return out


def render_js():
    lines = ['const { Clawd } = require(process.argv[1]);', 'const out = {};']
    for name, _, js in CASES:
        lines.append(f'out[{json.dumps(name)}] = Array.from({js});')
    for cid, dx, dy, al, ar in COSTUME_CASES:
        key = f"dressed {cid} dx={dx} dy={dy} arms={al},{ar}"
        lines.append(f'Clawd.costume = {json.dumps(cid)};')
        lines.append(f'out[{json.dumps(key)}] = '
                     f'Array.from(Clawd.dressed(1.0,{dx},{dy},true,0,1.0,{al},{ar}));')
    lines.append('Clawd.costume = "none";')
    lines.append('console.log(JSON.stringify(out));')
    res = subprocess.run(
        ["node", "-e", "\n".join(lines), str(ROOT / "web" / "clawd-core.js")],
        capture_output=True, text=True, check=False)
    if res.returncode != 0:
        raise SystemExit(f"node failed:\n{res.stderr}")
    return json.loads(res.stdout)


def ascii_art(buf):
    rows = []
    for y in range(15):
        row = ""
        for x in range(15):
            i = (y * 15 + x) * 3
            lum = (buf[i] + buf[i + 1] + buf[i + 2]) / 3
            row += "#" if lum > 90 else "+" if lum > 30 else "." if lum > 6 else " "
        rows.append(row)
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("-v", "--verbose", action="store_true",
                    help="print both renderings side by side on failure")
    args = ap.parse_args()

    py, js = render_python(), render_js()
    names = list(py)
    bad = []
    for name in names:
        if name not in js:
            bad.append((name, "missing in JS"))
        elif py[name] != js[name]:
            diff = sum(1 for a, b in zip(py[name], js[name]) if a != b)
            bad.append((name, f"{diff}/675 subpixels differ"))

    for name in names:
        mark = "❌" if any(n == name for n, _ in bad) else "✅"
        detail = next((d for n, d in bad if n == name), "")
        print(f"  {mark} {name}{'  — ' + detail if detail else ''}")
        if args.verbose and detail and name in js:
            for a, b in zip(ascii_art(py[name]), ascii_art(js[name])):
                flag = "  " if a == b else " <"
                print(f"      |{a}|  |{b}|{flag}")

    print(f"\n{len(names) - len(bad)}/{len(names)} poses identical on both bodies")
    if bad:
        print("❌ the desk and the browser disagree — see docs/POSES.md")
        return 1
    print("✅ Clawd is the same creature on the desk and in the browser")
    return 0


if __name__ == "__main__":
    sys.exit(main())
