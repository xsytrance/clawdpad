#!/usr/bin/env python3
"""firstlight — claudeblock's hello-world: a breathing Claude spark on the Lightpad.

Talks to a running blocksd via its Unix socket: NDJSON `discover`, then
binary 685-byte LED frames (0xBD, 0x01, u64 uid, 675 bytes RGB888).
"""

import json
import math
import os
import socket
import struct
import sys
import time

W = H = 15
CORAL = (217, 119, 87)  # Claude coral #D97757


def socket_path():
    for base in (os.environ.get("XDG_RUNTIME_DIR"), "/tmp"):
        if base:
            p = os.path.join(base, "blocksd", "blocksd.sock")
            if os.path.exists(p):
                return p
    sys.exit("blocksd socket not found — is the daemon running?")


def discover(sock):
    sock.sendall(b'{"type": "discover", "id": "fl-1"}\n')
    buf = b""
    while b"\n" not in buf:
        buf += sock.recv(4096)
    resp = json.loads(buf.split(b"\n")[0])
    for dev in resp.get("devices", []):
        if dev.get("grid_width") and dev.get("grid_height"):
            return dev
    sys.exit("no LED-capable device found")


def spark_frame(t):
    """Radial coral glow breathing at ~0.15 Hz, with a bright 'nucleus'."""
    breath = 0.55 + 0.45 * math.sin(t * 2 * math.pi / 6.5)  # dazzler's 6.5s breath
    px = bytearray()
    cx = cy = (W - 1) / 2
    for y in range(H):
        for x in range(W):
            d = math.hypot(x - cx, y - cy) / math.hypot(cx, cy)
            glow = max(0.0, 1.0 - d) ** 2.2
            level = glow * breath
            if d < 0.18:  # nucleus stays hot
                level = min(1.0, level + 0.35)
            px += bytes(min(255, int(c * level)) for c in CORAL)
    return bytes(px)


def main():
    seconds = float(sys.argv[1]) if len(sys.argv) > 1 else 12.0
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
        sock.connect(socket_path())
        dev = discover(sock)
        uid = dev["uid"]
        print(f"streaming to {dev['block_type']} {dev['serial']} "
              f"(battery {dev['battery_level']}%)")
        header = struct.pack("<BBQ", 0xBD, 0x01, uid)
        sent = accepted = 0
        start = time.monotonic()
        while (t := time.monotonic() - start) < seconds:
            sock.sendall(header + spark_frame(t))
            sent += 1
            if sock.recv(1) == b"\x01":
                accepted += 1
            time.sleep(1 / 20)  # ~20 fps target, device repaints at ~25 Hz
        print(f"frames sent {sent}, accepted {accepted}, "
              f"effective {sent / seconds:.1f} fps")


if __name__ == "__main__":
    main()
