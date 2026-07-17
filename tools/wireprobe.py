#!/usr/bin/env python3
"""wireprobe.py — what the block actually says back, per MIDI port.

Built 2026-07-16 to debug the web host (docs/MACBOOK.md Phase 2). Claude
cannot see the glass or a browser console, so this is the observable: it
speaks the same handshake the web page speaks, but prints every byte the
device sends back — serial, topology, ACKs, and device log messages.

blocksd must NOT be running (it holds API mode and answers the pings).

    .venv/bin/python3 tools/wireprobe.py            # probe every port
    .venv/bin/python3 tools/wireprobe.py --port 0   # just one

The question it exists to answer: which *device index* does this block
respond on? web/index.html hardcodes 9 and never parses the topology
reply, so if the real index differs, every packet after the handshake is
addressed to a device that isn't there — acks and all, silently.
"""

from __future__ import annotations

import argparse
import sys
import time

import rtmidi

from blocksd.protocol.builder import build_ping, build_request_topology
from blocksd.protocol.decoder import PacketHandler, decode_packet
from blocksd.protocol.serial import is_serial_response, parse_serial_response
from blocksd.topology.detector import scan_for_blocks

SERIAL_DUMP_REQUEST = bytes([0xF0, 0x00, 0x21, 0x10, 0x78, 0x3F, 0xF7])


class Recorder(PacketHandler):
    """Collect everything the device volunteers, print nothing on its own."""

    def __init__(self) -> None:
        self.topology_devices: list[dict] = []
        self.acks: list[int] = []
        self.logs: list[str] = []
        self.names: list[str] = []
        self.versions: list[str] = []
        self.events: list[str] = []

    def on_topology_begin(self, num_devices: int, num_connections: int) -> None:
        self.events.append(f"topology_begin: {num_devices} device(s), "
                           f"{num_connections} connection(s)")

    def on_topology_device(self, topology_index: int, serial: str,
                           battery_level: int, battery_charging: bool) -> None:
        self.topology_devices.append({"index": topology_index, "serial": serial,
                                      "battery": battery_level})
        self.events.append(f"topology_device: index={topology_index} "
                           f"serial={serial}")

    def on_topology_connection(self, dev1_idx: int, port1: int,
                               dev2_idx: int, port2: int) -> None:
        self.events.append(f"topology_connection: dev{dev1_idx}:port{port1}"
                           f" ↔ dev{dev2_idx}:port{port2}")

    def on_topology_end(self) -> None:
        self.events.append("topology_end")

    def on_topology_extend(self, num_devices: int, num_connections: int) -> None:
        self.events.append("topology_extend")

    def on_packet_ack(self, device_index: int, counter: int) -> None:
        self.acks.append(counter)

    def on_log_message(self, index: int, message: str) -> None:
        # The only place device-side LittleFoot faults ever surface.
        self.logs.append(f"[dev {index}] {message}")

    def on_device_name(self, topology_index: int, name: str) -> None:
        self.names.append(f"[dev {topology_index}] {name!r}")

    def on_device_version(self, topology_index: int, version: str) -> None:
        self.versions.append(f"[dev {topology_index}] {version!r}")

    def on_touch(self, *a: object) -> None: ...
    def on_button(self, *a: object) -> None: ...
    def on_config_set(self, *a: object) -> None: ...
    def on_config_update(self, *a: object) -> None: ...
    def on_config_factory_sync_end(self, *a: object) -> None: ...
    def on_config_factory_sync_reset(self, *a: object) -> None: ...
    def on_firmware_update_ack(self, *a: object) -> None: ...
    def on_program_event(self, *a: object) -> None: ...


def probe(in_port: int, out_port: int, label: str) -> dict:
    """Speak the web page's handshake; report what came back."""
    print(f"\n{'=' * 66}\nPORT PAIR in={in_port} out={out_port}  {label}\n{'=' * 66}")

    midi_in, midi_out = rtmidi.MidiIn(), rtmidi.MidiOut()
    midi_in.open_port(in_port)
    midi_out.open_port(out_port)
    midi_in.ignore_types(sysex=False)  # SysEx is the entire protocol

    raw: list[bytes] = []
    midi_in.set_callback(lambda msg, _d: raw.append(bytes(msg[0])))

    rec = Recorder()
    serials: list[str] = []

    def drain() -> None:
        for packet in raw[:]:
            raw.remove(packet)
            if is_serial_response(packet):
                try:
                    serials.append(parse_serial_response(packet))
                except Exception as exc:  # noqa: BLE001
                    print(f"  serial parse failed: {exc}")
                continue
            try:
                decode_packet(packet, rec)
            except Exception as exc:  # noqa: BLE001
                print(f"  decode failed ({len(packet)}B): {exc}")

    # 1 — serial dump. Same request the web page sends first.
    print("→ serial dump request")
    midi_out.send_message(list(SERIAL_DUMP_REQUEST))
    time.sleep(0.8)
    drain()
    print(f"← serial: {serials or 'NOTHING'}")

    # 2 — topology at index 0, exactly as web/index.html:138 does.
    print("→ requestTopology(0)")
    midi_out.send_message(list(build_request_topology(0)))
    time.sleep(1.2)
    drain()

    if rec.topology_devices:
        print("← topology:")
        for dev in rec.topology_devices:
            print(f"    index={dev['index']}  serial={dev['serial']}  "
                  f"battery={dev['battery']}")
    else:
        print("← topology: NOTHING")

    # 3 — does the device answer a ping at each plausible index? This is the
    # actual question: the web page assumes 9 and never checks.
    print("→ ping sweep (which index ACKs?)")
    answered: list[int] = []
    for idx in range(0, 16):
        rec.acks.clear()
        raw.clear()
        midi_out.send_message(list(build_ping(idx)))
        time.sleep(0.12)
        drain()
        if rec.acks:
            answered.append(idx)
            print(f"    index {idx:2d} → ACK ×{len(rec.acks)}")
    if not answered:
        print("    (no index answered a ping — device is not in API mode;"
              " that is expected before beginApi)")

    for line in rec.events:
        print(f"  · {line}")
    for line in rec.logs:
        print(f"  ⚠ DEVICE LOG {line}")

    midi_in.close_port()
    midi_out.close_port()
    del midi_in, midi_out

    return {"label": label, "serials": serials,
            "topology": rec.topology_devices, "ping_indices": answered,
            "logs": rec.logs}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--port", type=int, help="probe only this port pair index")
    args = ap.parse_args()

    pairs = scan_for_blocks()
    if not pairs:
        print("No ROLI blocks on MIDI. Is the block powered on?")
        return 1

    print(f"detector found {len(pairs)} port pair(s):")
    for i, p in enumerate(pairs):
        print(f"  [{i}] in={p.input_port} out={p.output_port} name={p.name!r}")

    chosen = [pairs[args.port]] if args.port is not None else pairs
    results = [probe(p.input_port, p.output_port, f"pair {i}")
               for i, p in enumerate(chosen)]

    print(f"\n{'=' * 66}\nSUMMARY\n{'=' * 66}")
    for r in results:
        print(f"{r['label']}: serial={r['serials'] or '—'} "
              f"topology_indices={[d['index'] for d in r['topology']]} "
              f"ping_answered={r['ping_indices'] or '—'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
