#!/usr/bin/env python3
"""A software Lightpad: applies the app's packet stream exactly like the
device would, so app bugs reproduce on the PC instead of on Rod's desk.

Device model (from roli_LittleFootRunner.h + observed behavior):
  - accepts a SharedDataChange packet only if its 16-bit index == last+1
    (10-bit wrap); otherwise silently drops it (still ACKs the old counter)
  - applies data-change commands to a 7200-byte heap
  - renders IFF the program area checksum validates; else: BLANK glass

Replays the app's real behavior: renumbering packets with a global rolling
counter, playing loop intros/bodies in any order you script.

Usage: .venv/bin/python tools/emulate_block.py
"""

import base64
import json
import sys

sys.path.insert(0, "vendor/blocksd/src")
from blocksd.littlefoot.programs import bitmap_led_program  # noqa: E402
from blocksd.protocol.packing import Packed7BitReader  # noqa: E402

STREAM = "/home/xsyprime/clawdpad-app/app/src/main/assets/stream.json"
PROGRAM = bitmap_led_program()


class SoftBlock:
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

    def glass(self):
        if not self.program_ok():
            return "BLANK (program checksum invalid)"
        off = len(PROGRAM)
        lit = sum(1 for i in range(off, off + 450)
                  if self.heap[i])
        return f"renders: {lit}/450 frame bytes lit"


class App:
    """Mimics Streamer.kt: renumber every data packet, play loops."""

    def __init__(self, block):
        self.doc = json.load(open(STREAM))
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


block = SoftBlock()
app = App(block)

print("== connect, play full loop (2 cycles) ==")
app.play("full", frames=104)
print(f"   {block.glass()}  acc={block.accepted} drop={block.dropped}")

print("== press CHIBI ==")
app.play("mini", frames=30)
print(f"   {block.glass()}  acc={block.accepted} drop={block.dropped}")

print("== press QR ==")
app.play("qr")
print(f"   {block.glass()}  acc={block.accepted} drop={block.dropped}")

print("== press FULL again ==")
app.play("full", frames=10)
print(f"   {block.glass()}  acc={block.accepted} drop={block.dropped}")
