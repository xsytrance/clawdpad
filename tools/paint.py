#!/usr/bin/env python3
"""paint — touch-reactive demo: light blooms under your finger and cools off.

Two blocksd sockets: one subscribed to touch events, one streaming frames.
Pressure drives brightness; heat decays each frame. Logs a summary on exit.
"""

import json
import math
import os
import socket
import struct
import sys
import threading
import time

W = H = 15
CORAL = (217, 119, 87)
HOT = (255, 200, 160)  # high-pressure tint
DECAY = 0.94           # per-frame heat retention
FPS = 20


def socket_path():
    for base in (os.environ.get("XDG_RUNTIME_DIR"), "/tmp"):
        if base:
            p = os.path.join(base, "blocksd", "blocksd.sock")
            if os.path.exists(p):
                return p
    sys.exit("blocksd socket not found")


class Heat:
    def __init__(self):
        self.grid = [[0.0] * W for _ in range(H)]
        self.lock = threading.Lock()
        self.touches = 0
        self.max_pressure = 0.0

    def splat(self, fx, fy, z):
        cx, cy = fx * (W - 1), fy * (H - 1)
        with self.lock:
            self.touches += 1
            self.max_pressure = max(self.max_pressure, z)
            for y in range(max(0, int(cy) - 2), min(H, int(cy) + 3)):
                for x in range(max(0, int(cx) - 2), min(W, int(cx) + 3)):
                    d = math.hypot(x - cx, y - cy)
                    add = max(0.0, (0.3 + 0.7 * z) * (1.0 - d / 2.5))
                    self.grid[y][x] = min(1.0, self.grid[y][x] + add)

    def frame(self):
        px = bytearray()
        with self.lock:
            for row in self.grid:
                for i, h in enumerate(row):
                    r = int(CORAL[0] * h + (HOT[0] - CORAL[0]) * max(0, h - 0.7) * 3)
                    g = int(CORAL[1] * h)
                    b = int(CORAL[2] * h)
                    px += bytes((min(255, r), min(255, g), min(255, b)))
                    row[i] = h * DECAY
        return bytes(px)


def listen(heat, deadline):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
        sock.connect(socket_path())
        sock.sendall(b'{"type": "subscribe", "events": ["touch"]}\n')
        sock.settimeout(1.0)
        buf = b""
        while time.monotonic() < deadline:
            try:
                chunk = sock.recv(4096)
            except TimeoutError:
                continue
            if not chunk:
                break
            buf += chunk
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                ev = json.loads(line)
                if ev.get("type") == "touch" and ev["action"] in ("start", "move"):
                    heat.splat(ev["x"], ev["y"], ev["z"])


def main():
    seconds = float(sys.argv[1]) if len(sys.argv) > 1 else 1800.0
    deadline = time.monotonic() + seconds
    heat = Heat()
    threading.Thread(target=listen, args=(heat, deadline), daemon=True).start()

    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
        sock.connect(socket_path())
        sock.sendall(b'{"type": "discover", "id": "p-1"}\n')
        buf = b""
        while b"\n" not in buf:
            buf += sock.recv(4096)
        devs = json.loads(buf.split(b"\n")[0]).get("devices", [])
        dev = next(d for d in devs if d.get("grid_width"))
        header = struct.pack("<BBQ", 0xBD, 0x01, dev["uid"])
        print(f"painting on {dev['serial']} for {seconds:.0f}s")
        while time.monotonic() < deadline:
            sock.sendall(header + heat.frame())
            sock.recv(1)
            time.sleep(1 / FPS)

    print(f"touch events: {heat.touches}, peak pressure: {heat.max_pressure:.2f}")


if __name__ == "__main__":
    main()
