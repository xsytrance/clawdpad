#!/usr/bin/env python3
"""Precompute the entire SysEx byte stream for the clawdpad Android app.

The v0.1 app is a *player*, not a protocol stack: this script uses the
proven Python implementation (vendored blocksd + clawdpadd's renderer) to
generate every packet — handshake, keepalive, and per-mood animation loops
as SharedDataChange diff streams. Each loop is standalone: its intro
re-syncs the full heap (program + frame) from an unknown device state, so
the app can switch loops at any time without tracking anything.

Output: ~/clawdpad-app/app/src/main/assets/stream.json
Usage:  .venv/bin/python tools/make_app_stream.py
"""

import base64
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "vendor", "blocksd", "src"))

import clawdpadd as c  # noqa: E402
from blocksd.littlefoot.programs import bitmap_led_program  # noqa: E402
from blocksd.protocol.builder import (  # noqa: E402
    build_begin_api_mode, build_end_api_mode, build_ping,
    build_request_topology,
)
from blocksd.protocol.constants import SERIAL_DUMP_REQUEST  # noqa: E402
from blocksd.protocol.remote_heap import RemoteHeap  # noqa: E402

FPS = 8              # BLE-friendly
HEAP_SIZE = 7200
DEVICE_INDEX = 9     # this block ACKs as topology index 9 (v0.2: parse topology)


def rgb565(frame):
    """clawdpadd RGB888 frame bytes -> BitmapLEDProgram heap bytes."""
    out = bytearray()
    for i in range(0, len(frame), 3):
        r, g, b = frame[i], frame[i + 1], frame[i + 2]
        r5, g6, b5 = (r >> 3) & 0x1F, (g >> 2) & 0x3F, (b >> 3) & 0x1F
        out.append(r5 | ((g6 & 0x07) << 5))
        out.append((g6 >> 3) | (b5 << 3))
    return bytes(out)


def drain(heap):
    """Pull all pending packets, simulating instant ACKs (offline)."""
    pkts = []
    while (pkt := heap.send_changes(DEVICE_INDEX)) is not None:
        pkts.append(pkt)
        heap.handle_ack(heap._messages[-1].packet_index)
    return pkts


def b64(pkts):
    return [base64.b64encode(p).decode() for p in pkts]


def make_boot():
    """Program upload — sent ONCE after handshake. Never again: rewriting
    the program area makes the firmware reload it and WIPE the frame data
    (discovered via the QR heartbeat-pixel experiment: intros that carried
    the program erased their own pixels)."""
    heap = RemoteHeap(HEAP_SIZE)
    heap.handle_ack(0)
    heap.set_bytes(0, bitmap_led_program())
    return b64(drain(heap))


def make_loop(frames):
    """Loop intro syncs the FRAME AREA ONLY; body cycles f1..fn plus the
    wrap diff back to f0. The program region is never touched (see
    make_boot)."""
    program = bitmap_led_program()
    heap = RemoteHeap(HEAP_SIZE)
    heap.handle_ack(0)
    heap.set_bytes(0, program)
    drain(heap)  # deliver the program in simulation, then discard —
                 # loop intros start from a device that already has it
    # Single-pass full-coverage intro, no flash: mark the frame area as
    # UNKNOWN so the diff engine emits EVERY byte (zeros included) in one
    # pass — old pixels morph directly into new ones as the bytes stream,
    # exactly like body frames. (History: lit-pixels-only intros left
    # stale residue; a clear-pass sentinel fixed residue but blinked the
    # glass dark — and 0x01 even decoded to green. This does neither.)
    from blocksd.protocol.remote_heap import _UNKNOWN
    for i in range(len(program), HEAP_SIZE):
        heap._device_state[i] = _UNKNOWN
    heap.set_bytes(len(program), rgb565(frames[0]))
    intro = drain(heap)
    body = []
    for f in frames[1:] + [frames[0]]:
        heap.set_bytes(len(program), rgb565(f))
        body.append(b64(drain(heap)))
    return {"intro": b64(intro), "body": body, "fps": FPS}


def frames(fn, seconds, **kw):
    return [fn(i / FPS, **kw) for i in range(int(seconds * FPS))]


class _QRState:  # minimal stand-in so we can reuse the daemon's QR command
    def __init__(self):
        import threading
        self.lock = threading.Lock()
        self.qr_matrix = None
        self.qr_until = 0.0


def qr_frame(text, heartbeat=False):
    st = _QRState()
    reply = c.State.apply.__wrapped__ if hasattr(c.State.apply, "__wrapped__") \
        else None
    # build the matrix exactly like the daemon's qr command does
    import segno
    q = segno.make(text, micro=True)
    m = [list(row) for row in q.matrix]
    pad = (15 - len(m)) // 2
    buf = bytearray(15 * 15 * 3)
    for y, row in enumerate(m):
        for x, v in enumerate(row):
            if v:
                i = ((y + pad) * 15 + (x + pad)) * 3
                buf[i] = buf[i + 1] = buf[i + 2] = 140
    if heartbeat:  # bottom-right corner blink, outside the quiet zone story
        buf[(14 * 15 + 14) * 3] = 60
    return bytes(buf)


def main():
    out = os.path.expanduser(
        "~/clawdpad-app/app/src/main/assets/stream.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    doc = {
        "boot": make_boot(),
        "handshake": b64([bytes(SERIAL_DUMP_REQUEST),
                          build_request_topology(DEVICE_INDEX),
                          build_end_api_mode(DEVICE_INDEX),
                          build_begin_api_mode(DEVICE_INDEX)]),
        "ping": base64.b64encode(build_ping(DEVICE_INDEX)).decode(),
        "loops": {
            "full": make_loop(frames(c.frame_awake, 6.5)),
            "mini": make_loop(
                [c._mini_frame("awake", i / FPS, 0, None, 1.0)
                 for i in range(int(13.0 * FPS))]),
            "wave": make_loop(frames(c.frame_notify, 2.5)),
            "jump": make_loop(frames(c.frame_celebrate, 2.4)),
            "mini_wave": make_loop(
                [c._mini_frame("notify", i / FPS, 0, None, 1.0)
                 for i in range(int(2.5 * FPS))]),
            "mini_jump": make_loop(
                [c._mini_frame("celebrate", i / FPS, 0, None, 1.0)
                 for i in range(int(2.4 * FPS))]),
            # QR body must keep DATA flowing: an all-static loop sends
            # nothing after the intro, and the block blanks on an idle
            # data stream (the working daemon path always has periodic
            # protocol chatter). One blinking corner pixel = a heartbeat.
            "qr": make_loop([qr_frame("CLAWDPAD"),
                             qr_frame("CLAWDPAD", heartbeat=True)]),
        },
    }
    with open(out, "w") as fh:
        json.dump(doc, fh)
    sizes = {k: sum(len(p) for p in v["intro"])
             + sum(len(p) for f in v["body"] for p in f)
             for k, v in doc["loops"].items()}
    print(f"{out}: {os.path.getsize(out)} bytes; loop b64 sizes: {sizes}")


if __name__ == "__main__":
    main()
