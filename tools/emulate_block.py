#!/usr/bin/env python3
"""A software Lightpad — develop and debug with no hardware at all.

ROLI Blocks are discontinued. Almost nobody can buy one, and Rod's are on his
desk, not yours. This models the device faithfully enough that render bugs
reproduce on your laptop instead of on his glass.

Device model (from roli_LittleFootRunner.h + observed behaviour):
  - accepts a SharedDataChange packet only if its 16-bit index == last+1
    (10-bit wrap); otherwise silently drops it (still ACKs the old counter)
  - applies data-change commands to a 7200-byte heap
  - renders IFF the program area checksum validates; else: BLANK glass

That last rule is the one that bites: a wrong program means a blank glass and
no error anywhere. It's how the 2026-07-16 QR-blank saga was diagnosed (the
firmware wipes the heap data area on program re-validation, so every loop
intro erased the frame that followed it).

Modes:
  web     (default) drive the device from web/clawd-core.js — the canonical,
          hardware-facing path — and check the glass matches the pose. Proves
          renderer → RGB565 → heap diff → packets → device → pixels, in full,
          without a block. Needs node.
  stream  replay a clawdpad-app stream.json (the Kotlin player's baked loops).

    .venv/bin/python3 tools/emulate_block.py
    .venv/bin/python3 tools/emulate_block.py --pose celebrate --frames 40
    .venv/bin/python3 tools/emulate_block.py stream --file ../clawdpad-app/app/src/main/assets/stream.json

Until 2026-07-17 this file hardcoded a path to Rod's Linux checkout of another
repo and ran as top-level code, so it worked on exactly one machine.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "blocksd" / "src"))   # was vendor/blocksd/src

from blocksd.littlefoot.programs import bitmap_led_program  # noqa: E402
from blocksd.protocol.packing import Packed7BitReader  # noqa: E402

PROGRAM = bitmap_led_program()


class SoftBlock:
    """The device, in software. Believes nothing it isn't told correctly."""

    def __init__(self):
        self.heap = bytearray(7200)
        self.expect = 1          # device ACKed 0 post-topology
        self.accepted = self.dropped = 0

    def receive(self, pkt):
        payload = pkt[6:-2]
        r = Packed7BitReader(payload)
        if r.read_bits(7) != 0x02:
            return
        idx = r.read_bits(16)
        if idx != self.expect:
            self.dropped += 1
            return
        self.expect = (self.expect + 1) & 0x3FF
        self.accepted += 1
        pos = last = 0
        while True:
            cmd = r.read_bits(3)
            if cmd in (0, 1):
                break
            elif cmd == 2:
                pos += r.read_bits(4)
            elif cmd == 3:
                pos += r.read_bits(8)
            elif cmd == 4:
                while True:
                    v = r.read_bits(8)
                    self.heap[pos] = v
                    last = v
                    pos += 1
                    if not r.read_bits(1):
                        break
            elif cmd == 5:
                n, v = r.read_bits(4), r.read_bits(8)
                for _ in range(n):
                    self.heap[pos] = v
                    pos += 1
                last = v
            elif cmd == 6:
                n = r.read_bits(4)
                for _ in range(n):
                    self.heap[pos] = last
                    pos += 1
            elif cmd == 7:
                n, v = r.read_bits(8), r.read_bits(8)
                for _ in range(n):
                    self.heap[pos] = v
                    pos += 1
                last = v

    def program_ok(self):
        stored = self.heap[0] | (self.heap[1] << 8)
        size = self.heap[2] | (self.heap[3] << 8)
        if size < 10 or size > 7200:
            return False
        n = size & 0xFFFF
        for i in range(2, size):
            n = (n + n * 2 + self.heap[i]) & 0xFFFF
        return n == stored

    def glass(self, expected=None):
        if not self.program_ok():
            return "BLANK (program checksum invalid)"
        off = len(PROGRAM)
        lit = sum(1 for i in range(off, off + 450) if self.heap[i])
        out = f"renders: {lit}/450 frame bytes lit"
        if expected is not None:
            bad = sum(1 for i in range(450)
                      if self.heap[off + i] != expected[i])
            out += (" | matches the pose exactly" if bad == 0
                    else f" | ❌ {bad} stale/wrong bytes vs the pose")
        return out

    def show(self):
        """The glass, as ASCII. RGB565 in the heap -> luminance."""
        if not self.program_ok():
            return ["BLANK (program checksum invalid)"]
        off = len(PROGRAM)
        rows = []
        for y in range(15):
            row = ""
            for x in range(15):
                i = off + (y * 15 + x) * 2
                v = self.heap[i] | (self.heap[i + 1] << 8)
                r = ((v >> 11) & 0x1F) << 3
                g = ((v >> 5) & 0x3F) << 2
                b = (v & 0x1F) << 3
                lum = (r + g + b) / 3
                row += "#" if lum > 90 else "+" if lum > 30 else "." if lum > 6 else " "
            rows.append(row)
        return rows


# ── web mode: drive the device from clawd-core.js ──────────────────────────

_JS = r"""
const path = process.argv[1], pose = process.argv[2], n = +process.argv[3];
const { Clawd, HeapStreamer, Protocol } = require(path + "/web/clawd-core.js");
globalThis.QR_BAKED = require(path + "/web/qr-data.js").QR_BAKED;
const fs = require("fs");
const program = new Uint8Array(fs.readFileSync(path + "/web/program.bin"));

const POSES = {
  awake: t => Clawd.awake(t), sleep: t => Clawd.sleep(t),
  thinking: t => Clawd.thinking(2.0, t), wave: t => Clawd.wave(t),
  celebrate: t => Clawd.celebrate(t % Clawd.CELEBRATE_SECONDS),
  dance: t => Clawd.dance(t, 0.8, 0.9), qr: () => Clawd.qr("CLAWDPAD"),
  mini: t => Clawd.miniAwake(t),
};
if (!POSES[pose]) { console.error("unknown pose: " + pose); process.exit(2); }

const hs = new HeapStreamer(9, 1);
hs.setBytes(0, program);
const b64 = a => Buffer.from(a).toString("base64");
const out = { boot: hs.drain().map(b64), steps: [] };
for (let i = 0; i < n; i++) {
  const frame = Clawd.rgb565(POSES[pose](i * 0.085));
  hs.setBytes(Protocol.PROGRAM_SIZE, frame);
  out.steps.push({ packets: hs.drain().map(b64), expected: b64(frame) });
}
console.log(JSON.stringify(out));
"""


def run_web(args) -> int:
    prog_bin = ROOT / "web" / "program.bin"
    if not prog_bin.exists():
        print(f"missing {prog_bin} — the web host needs it too")
        return 2
    res = subprocess.run(["node", "-e", _JS, str(ROOT), args.pose,
                          str(args.frames)],
                         capture_output=True, text=True, check=False)
    if res.returncode != 0:
        print(f"node failed:\n{res.stderr}")
        return 2
    doc = json.loads(res.stdout)

    block = SoftBlock()
    for p in doc["boot"]:
        block.receive(base64.b64decode(p))
    print(f"boot: {len(doc['boot'])} packet(s) — program "
          f"{'validates ✅' if block.program_ok() else 'INVALID ❌ (blank glass)'}")

    last = None
    for step in doc["steps"]:
        for p in step["packets"]:
            block.receive(base64.b64decode(p))
        last = base64.b64decode(step["expected"])

    print(f"{args.pose}: {args.frames} frames, "
          f"{block.accepted} packets accepted, {block.dropped} dropped")
    print("  " + block.glass(last))
    if args.show:
        print()
        for row in block.show():
            print("  |" + row + "|")
    ok = block.program_ok() and block.dropped == 0 and last is not None and \
        all(block.heap[len(PROGRAM) + i] == last[i] for i in range(450))
    print("\n" + ("✅ the browser's byte path renders correctly on a real device model"
                  if ok else "❌ the glass does not match the pose"))
    return 0 if ok else 1


# ── stream mode: replay a clawdpad-app stream.json ─────────────────────────

class App:
    """Mimics Streamer.kt: renumber every data packet, play loops."""

    def __init__(self, block, stream_path):
        with open(stream_path) as fh:
            self.doc = json.load(fh)
        self.block = block
        self.next = 1

    def renumber(self, pkt):
        p = bytearray(pkt)
        v = self.next
        for k in range(16):
            bit = 7 + k
            bi, off = 6 + bit // 7, bit % 7
            p[bi] = (p[bi] & ~(1 << off)) | (((v >> k) & 1) << off)
        payload = p[6:-2]
        cs = len(payload) & 0xFF
        for b in payload:
            cs = (cs + cs * 2 + b) & 0xFF
        p[-2] = cs & 0x7F
        self.next = (self.next + 1) & 0x3FF
        return bytes(p)

    def send_all(self, arr):
        for p64 in arr:
            pkt = base64.b64decode(p64)
            if len(pkt) > 8 and (pkt[6] & 0x7F) == 0x02:
                pkt = self.renumber(pkt)
            self.block.receive(pkt)

    def play(self, name, frames=None):
        loop = self.doc["loops"][name]
        self.send_all(loop["intro"])
        body = loop["body"]
        for i in range(frames if frames is not None else len(body)):
            self.send_all(body[i % len(body)])


def run_stream(args) -> int:
    path = os.path.expanduser(args.file)
    if not os.path.exists(path):
        print(f"no stream.json at {path}\n"
              "  generate one with clawdpad-app's tools/make_app_stream.py, "
              "or use the default `web` mode which needs no app repo.")
        return 2
    block = SoftBlock()
    app = App(block, path)
    app.send_all(app.doc["boot"])   # program: once, like the real Streamer
    print(f"boot — program "
          f"{'validates ✅' if block.program_ok() else 'INVALID ❌ (blank glass)'}")
    app.play(args.loop, frames=args.frames)
    print(f"{args.loop}: {block.accepted} accepted, {block.dropped} dropped")
    print("  " + block.glass())
    if args.show:
        for row in block.show():
            print("  |" + row + "|")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--show", action="store_true", help="draw the glass as ASCII")
    sub = ap.add_subparsers(dest="mode")

    web = sub.add_parser("web", help="drive from web/clawd-core.js (default)")
    web.add_argument("--pose", default="awake",
                     help="awake|sleep|thinking|wave|celebrate|dance|qr|mini")
    web.add_argument("--frames", type=int, default=24)
    web.add_argument("--show", action="store_true")

    st = sub.add_parser("stream", help="replay a clawdpad-app stream.json")
    st.add_argument("--file", required=True)
    st.add_argument("--loop", default="full")
    st.add_argument("--frames", type=int, default=104)
    st.add_argument("--show", action="store_true")

    args = ap.parse_args()
    if args.mode == "stream":
        return run_stream(args)
    if args.mode is None:   # bare invocation -> web defaults
        args = ap.parse_args(["web"])
    return run_web(args)


if __name__ == "__main__":
    sys.exit(main())
