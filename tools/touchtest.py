#!/usr/bin/env python3
"""touchtest — subscribe to blocksd touch/button events and print them."""

import json
import os
import socket
import sys
import time


def socket_path():
    for base in (os.environ.get("XDG_RUNTIME_DIR"), "/tmp"):
        if base:
            p = os.path.join(base, "blocksd", "blocksd.sock")
            if os.path.exists(p):
                return p
    sys.exit("blocksd socket not found")


def main():
    seconds = float(sys.argv[1]) if len(sys.argv) > 1 else 30.0
    deadline = time.monotonic() + seconds
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
        sock.connect(socket_path())
        sock.sendall(b'{"type": "subscribe", "events": ["touch", "button"]}\n')
        sock.settimeout(1.0)
        buf = b""
        count = 0
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
                if ev.get("type") == "touch":
                    count += 1
                    # print start/end always; sample moves so output stays sane
                    if ev["action"] != "move" or count % 10 == 0:
                        print(f"{ev['action']:5s} touch#{ev['index']} "
                              f"x={ev['x']:.2f} y={ev['y']:.2f} "
                              f"pressure={ev['z']:.2f}")
                elif ev.get("type") == "button":
                    print(f"button {ev['button_id']} {ev['action']}")
        print(f"total touch events: {count}")


if __name__ == "__main__":
    main()
