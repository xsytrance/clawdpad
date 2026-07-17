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
    # The micro-behaviours: rare by design, so no ordinary t reaches them and
    # every case above stays green whatever they do. These land inside the
    # windows on purpose — an untested rare behaviour is an unshipped one.
    ("awake stretch t=600.8", "m.frame_awake(600.8)",       "Clawd.awake(600.8)"),
    ("awake stretch t=601.4", "m.frame_awake(601.4)",       "Clawd.awake(601.4)"),
    ("awake look-L t=300.5",  "m.frame_awake(300.5)",       "Clawd.awake(300.5)"),
    ("awake look-R t=302.0",  "m.frame_awake(302.0)",       "Clawd.awake(302.0)"),
    ("sleep t=1.0",        "m.frame_sleep(1.0)",            "Clawd.sleep(1.0)"),
    ("sleep t=9.8 (peek)", "m.frame_sleep(9.8)",            "Clawd.sleep(9.8)"),
    ("thinking ph=2 t=.3", "m.frame_thinking(2.0, 0.3)",    "Clawd.thinking(2.0, 0.3)"),
    ("thinking ph=0 t=1",  "m.frame_thinking(0.0, 1.0)",    "Clawd.thinking(0.0, 1.0)"),
    ("thinking ph=5.5",    "m.frame_thinking(5.5, 2.7)",    "Clawd.thinking(5.5, 2.7)"),
    ("notify/wave t=0",    "m.frame_notify(0.0)",           "Clawd.wave(0.0)"),
    ("notify/wave t=0.3",  "m.frame_notify(0.3)",           "Clawd.wave(0.3)"),
    ("celebrate rel=0",    "m.frame_celebrate(0.0)",        "Clawd.celebrate(0.0)"),
    ("celebrate rel=0.3",  "m.frame_celebrate(0.3)",        "Clawd.celebrate(0.3)"),
    # sad: t=0.3 catches a heavy blink, t=2.0 has the eyes open, t=9.0 is the
    # look-away. Three points because all three are the pose.
    ("sad t=0.3 (blink)",  "m.frame_sad(0.3)",              "Clawd.sad(0.3)"),
    ("sad t=2.0",          "m.frame_sad(2.0)",              "Clawd.sad(2.0)"),
    ("sad t=9.0 (away)",   "m.frame_sad(9.0)",              "Clawd.sad(9.0)"),
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
    ("mini sad t=2",       "m._mini_frame('sad', 2.0, 0, None, 1.0)",
                           "Clawd.miniSad(2.0)"),
    ("marquee 'HI'",       "m._marquee_frame('HI', 1.0)",
                           "Clawd.marquee('HI', 1.0, Clawd.CORAL)"),
]

# (name, costume, python expr, js expr) — a costume *inside a pose*, which is
# the gap the next bug lived in. CASES checks poses undressed; COSTUME_CASES
# checks costumes at fixed arguments; neither could see that build_frame
# re-derived *awake* breath/bob/blink for every costumed calm mood, so a
# dressed Clawd on the desk never slept and never paced while thinking. The
# browser was right the whole time, and 32/32 stayed green through all of it.
# A pose is (body language x outfit) — test the product, not the factors.
DRESSED_CASES = [
    ("tophat sleep t=1.0",  "tophat", "m.frame_sleep(1.0, costume='tophat')",
                                      "Clawd.sleep(1.0)"),
    ("tophat sleep t=9.8",  "tophat", "m.frame_sleep(9.8, costume='tophat')",
                                      "Clawd.sleep(9.8)"),
    ("tophat awake t=2.7",  "tophat", "m.frame_awake(2.7, costume='tophat')",
                                      "Clawd.awake(2.7)"),
    ("scarf thinking ph=2", "scarf",  "m.frame_thinking(2.0, 0.3, costume='scarf')",
                                      "Clawd.thinking(2.0, 0.3)"),
    ("scarf thinking ph=5.5", "scarf", "m.frame_thinking(5.5, 2.7, costume='scarf')",
                                       "Clawd.thinking(5.5, 2.7)"),
    ("tophat wave t=0.3",   "tophat", "m.frame_notify(0.3, costume='tophat')",
                                      "Clawd.wave(0.3)"),
    ("tophat celebrate .3", "tophat", "m.frame_celebrate(0.3, costume='tophat')",
                                      "Clawd.celebrate(0.3)"),
    ("robot sad t=2.0",     "robot",  "m.frame_sad(2.0, costume='robot')",
                                      "Clawd.sad(2.0)"),
    ("ghost sleep t=1.0",   "ghost",  "m.frame_sleep(1.0, costume='ghost')",
                                      "Clawd.sleep(1.0)"),
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
    # ROOT goes on the path BEFORE the daemon loads, or clawdpadd.py's
    # `try: import costumes / except ImportError: costumes = None` quietly
    # succeeds at failing — and every costume path in the daemon renders a bare
    # Clawd. This harness ran that way from the day it was written: it proved
    # costumes.py matched the browser, while the *daemon's* use of it was
    # untested and, as it turned out, broken. A test that silently degrades is
    # worse than no test, because it reports green.
    sys.path.insert(0, str(ROOT))
    m = load_daemon()  # noqa: F841 — used by eval
    if m.costumes is None:
        raise SystemExit("parity: clawdpadd loaded without costumes — "
                         "the costume cases below would all be fake green")
    import costumes

    out = {}
    for name, py, _ in CASES:
        out[name] = list(bytes(eval(py)))  # noqa: S307 — table above is the input
    for name, _cid, py, _ in DRESSED_CASES:
        out[name] = list(bytes(eval(py)))  # noqa: S307
    for cid, dx, dy, al, ar in COSTUME_CASES:
        key = f"dressed {cid} dx={dx} dy={dy} arms={al},{ar}"
        out[key] = list(bytes(costumes.dressed(
            cid, 1.0, dx, dy, True, 0, 1.0, arm_l_dy=al, arm_r_dy=ar)))
    return out


def render_js():
    lines = ['const { Clawd } = require(process.argv[1]);', 'const out = {};']
    for name, _, js in CASES:
        lines.append(f'out[{json.dumps(name)}] = Array.from({js});')
    # the browser dresses from inside the pose: set the outfit, then ask.
    for name, cid, _, js in DRESSED_CASES:
        lines.append(f'Clawd.costume = {json.dumps(cid)};')
        lines.append(f'out[{json.dumps(name)}] = Array.from({js});')
    lines.append('Clawd.costume = "none";')
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
