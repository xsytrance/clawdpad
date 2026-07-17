#!/usr/bin/env python3
"""Golden vectors — the conformance oracle for every ROLI protocol port.

blocksd is the reference implementation. Every other port — clawd-core.js
(browser/WebMIDI), Kotlin's Protocol.kt (clawdpad-app), and anything that
comes later — must produce byte-identical output. These vectors are how
that gets proved instead of assumed.

The output is DETERMINISTIC (seeded rng) and committed to the repo, so a
port can be verified with nothing but `node web/test-golden.mjs` — no
Python, no venv, no blocksd, no hardware.

Consumers:
  - web/test-golden.mjs                      (clawd-core.js)
  - clawdpad-app JVM unit tests              (--out to its resources dir)

Output: tools/golden.json   (override with --out PATH)
Usage:  .venv/bin/python3 tools/make_golden_vectors.py
"""

import argparse
import base64
import json
import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
# blocksd is normally pip-installed editable from ./blocksd; fall back to its
# source tree so this runs in a bare checkout. (Was "vendor/blocksd/src",
# a directory that does not exist — the import only worked via the venv.)
sys.path.insert(0, os.path.join(ROOT, "blocksd", "src"))

from blocksd.littlefoot.programs import bitmap_led_program  # noqa: E402
from blocksd.protocol.builder import (  # noqa: E402
    build_begin_api_mode, build_end_api_mode, build_ping,
    build_request_topology,
)
from blocksd.protocol.checksum import calculate_checksum  # noqa: E402
from blocksd.protocol.packing import Packed7BitWriter  # noqa: E402
from blocksd.protocol.remote_heap import RemoteHeap  # noqa: E402

rng = random.Random(20260716)


def b64(data):
    return base64.b64encode(bytes(data)).decode()


vectors = {}

# 1) 7-bit packing: (value, bits) sequences -> packed bytes
packing = []
for _ in range(24):
    fields = [(rng.getrandbits(bits), bits)
              for bits in (rng.choices([1, 3, 4, 5, 7, 8, 9, 12, 16, 32], k=rng.randint(1, 8)))]
    w = Packed7BitWriter(256)
    for v, bits in fields:
        w.write_bits(v, bits)
    packing.append({"fields": [[v, b] for v, b in fields],
                    "packed": b64(w.get_data())})
vectors["packing"] = packing

# 2) checksums over random payloads
checksums = []
for n in (0, 1, 7, 63, 199):
    payload = bytes(rng.randrange(128) for _ in range(n))
    checksums.append({"payload": b64(payload),
                      "checksum": calculate_checksum(payload)})
vectors["checksum"] = checksums

# 3) command builders at various indexes
vectors["commands"] = {
    "ping_idx9": b64(build_ping(9)),
    "ping_idx0": b64(build_ping(0)),
    "topology_idx0": b64(build_request_topology(0)),
    "begin_api_idx9": b64(build_begin_api_mode(9)),
    "end_api_idx9": b64(build_end_api_mode(9)),
}

# 4) THE big one: heap diff encoding. Random frame transitions -> packets.
program = bitmap_led_program()
transitions = []
heap = RemoteHeap(7200)
heap.handle_ack(0)
heap.set_bytes(0, program)


def drain(h):
    pkts = []
    while (p := h.send_changes(9)) is not None:
        pkts.append(p)
        h.handle_ack(h._messages[-1].packet_index)
    return pkts


boot = drain(heap)
vectors["boot"] = [b64(p) for p in boot]
vectors["program"] = b64(program)

state = bytes(450)
for case in range(12):
    # random-ish frame: runs of colors + sparse pixels + zeros (all encoder paths)
    frame = bytearray(state)
    for _ in range(rng.randint(1, 6)):
        start = rng.randrange(440)
        length = rng.randint(1, min(60, 450 - start))
        if rng.random() < 0.3:
            val = 0
        elif rng.random() < 0.5:
            val = rng.randrange(1, 256)
            frame[start:start + length] = bytes([val]) * length
            continue
        else:
            val = None
        for i in range(start, start + length):
            frame[i] = rng.randrange(256) if val is None else val
    heap.set_bytes(len(program), bytes(frame))
    pkts = drain(heap)
    transitions.append({"frame": b64(bytes(frame)),
                        "packets": [b64(p) for p in pkts]})
    state = bytes(frame)
vectors["transitions"] = transitions

ap = argparse.ArgumentParser(description=__doc__)
ap.add_argument("--out", default=os.path.join(ROOT, "tools", "golden.json"),
                help="where to write (default: tools/golden.json, in-repo). "
                     "Point at clawdpad-app's test resources to refresh the "
                     "Kotlin port's copy.")
args = ap.parse_args()

out = os.path.expanduser(args.out)
os.makedirs(os.path.dirname(out), exist_ok=True)
with open(out, "w") as fh:
    json.dump(vectors, fh)
print(f"{out}: {os.path.getsize(out)} bytes; "
      f"{len(packing)} packing, {len(transitions)} transitions, "
      f"{len(boot)} boot pkts")
