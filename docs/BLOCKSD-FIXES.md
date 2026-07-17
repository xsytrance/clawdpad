# blocksd fixes — the "Illegal instruction" investigation (2026-07-15)

Full record of why the Lightpad never rendered our frames, how it was diagnosed,
and what was fixed. Written for future-us and for an upstream PR to
[blocksd](https://github.com/hyperb1iss/blocksd).

## Symptom

- blocksd reports `Loaded BitmapLEDProgram (100 bytes)`, `Device API connected`,
  battery, topology — everything healthy.
- Clients streaming 675-byte RGB888 frames to the blocksd socket get **100%
  frame acceptance** at 20 fps.
- The glass shows the **factory app** (multicolored note-grid squares) forever.
- Once, at program-upload time, a brief coral/blue flash was seen — and wrongly
  recorded as "rendering verified".

## Red herrings, in the order we fell for them

1. **"Frame acks mean it's painting"** — no. The `\x01` ack on the blocksd Unix
   socket means the daemon accepted the frame into its heap mirror. It says
   nothing about the device.
2. **"The program upload works because the log says Loaded"** — no. That log
   line means bytes were written into blocksd's `RemoteHeap` *target* state.
   Delivery and execution are separate.
3. **Upstream's TODO** (`getHeapBits 0x40 and dupOffset_01 0x11 are not
   supported on firmware v1.1.0`) — a misdiagnosis (see below). The opcode
   table is bit-identical in every public JUCE/ROLI release from JUCE 4.3.0
   (Nov 2016) through roli_blocks_basics (2020): we diffed
   `juce_LittleFootRunner.h` across 4.3.0, 4.3.1, 5.0.0, 5.1.2, and
   roli_blocks_basics `main`.

## The decisive clue

Device-side LittleFoot faults are reported over SysEx as `LOG_MESSAGE` (0x30)
packets. blocksd logs them **only at DEBUG**
(`device_group.py: on_log_message → log.debug`). Running
`blocksd run --daemon --verbose` immediately showed:

```
DEBUG [blocksd.topology.device_group] Device 731921524192880557 log: Illegal instruction
```

…repeating ~25×/second — once per repaint cycle. So the program **was
delivered, checksummed, and executed** — and crashed on every repaint. (The
"Illegal instruction" string is `ErrorCode::unknownInstruction` in
`roli_LittleFootRunner.h`.)

## Root cause

`littlefoot/assembler.py` resolved jump labels **relative to the code
section**. The LittleFoot VM resolves them **relative to the program header**:

```cpp
// roli_LittleFootRunner.h
void jump (int16 addr) noexcept {
    if (((uint16) addr) >= programSize) return setError (ErrorCode::illegalAddress);
    programCounter = programBase + (uint16) addr;   // programBase = header start
}
```

Program layout (same header everywhere since 2016):

```
0   checksum        (2 bytes)
2   program size    (2)
4   num functions   (2)
6   num globals     (2)
8   heap size       (2)
10  function table  (4 bytes per function: id + code offset)
10+4n  bytecode
```

With one function, code starts at byte 14. Every loop-jump in the
BitmapLEDProgram therefore landed **14 bytes short** — inside the function
table — where the interpreter decoded garbage and faulted. The brief
coral/blue flash on upload was the program's first instructions running before
the first jump killed it; the firmware then reverted to the factory app.

Note the function *table* entries were already correct (`build()` adds
`code_base + f.code_offset`) — only label fixups missed the offset. That
asymmetry is why the program could *start* (function entry addresses valid)
but never *loop*.

## The fixes (vendored)

All three live in `blocksd/` — a gitignored clone at the repo root, pip-installed
**editable** into `.venv`, replacing the PyPI copy so `pip install -U blocksd`
can no longer silently revert them. To iterate: edit `blocksd/`, then
`systemctl --user restart blocksd`.

1. `src/blocksd/littlefoot/assembler.py — _resolve_labels()`: add
   `code_base = _HEADER_SIZE + len(self._functions) * _FUNC_ENTRY_SIZE` to
   every label target.
2. `src/blocksd/topology/device_group.py — _load_led_program()`: remove the
   early-return; upload `bitmap_led_program()` (upstream's original intent).

Verified on hardware 2026-07-15: Lightpad Block M, serial `LPM9E1KL3HO9XC5G`,
firmware-era v1.1.x — zero device faults after the fixed program loaded
(the error flood stopped at the exact second the upload landed), and the
15×15 stream renders live (confirmed visually: mood animations + overlays).

## Upstream PR notes

- The one-line assembler fix likely obsoletes upstream's firmware-opcode
  theory; their disabled `_load_led_program` can be re-enabled as-is.
- `getHeapBits` (0x40) and `dupOffset` (operand form 0x18) both execute fine
  on our firmware once jumps resolve correctly — the shipping
  `bitmap_led_program()` uses both.
- Suggest upstream also raise `on_log_message` to INFO or WARNING for strings
  matching known `ErrorCode` texts — a device screaming "Illegal instruction"
  25×/s should not require `--verbose` to notice.

## Debugging playbook (next time the glass looks wrong)

1. `systemctl --user status blocksd` — device connected at all?
2. Temporarily run verbose: edit the unit's `ExecStart` to add `--verbose`,
   `systemctl --user daemon-reload && systemctl --user restart blocksd`, then
   `journalctl --user -u blocksd -f | grep "log:"` — the device tells you
   about program faults directly. Revert afterwards (touch events are noisy
   at DEBUG).
3. Remember the layering: frame ack ≠ heap delivered ≠ program running.
   Device `LOG_MESSAGE`s are the only ground truth short of eyes on glass.
4. A SIGKILLed blocksd (e.g. stop timeout while log-flooded) leaves the block
   confused for a few seconds; the next connect cycle recovers it.

---

# blocksd fix 3 — the macOS two-block collision (2026-07-16)

Found on Rod's MacBook during the `docs/MACBOOK.md` dress rehearsal, on the
first night two blocks were ever plugged into a Mac. The run-sheet predicted
this failure in writing before it happened — see its Phase 1 section.

## Symptom

- One block: flawless. Enumerates, streams, renders.
- Second block plugged in (its own USB-C port, direct to the Mac): **silently
  absent.** No error, no warning, no log line. blocksd's `discover` returns
  one device forever.

## Red herrings, in the order we fell for them

1. **"Both blocks are alive"** — `blockctl status` said `+1 more` and
   `blockctl names` listed XC5G *and* SH8T. Both read clawdpadd's cached
   `dev_serials` (populated once at render-loop connect), not the hardware.
   The phantom outlived the block it described by an hour. *Frame acks ≠
   pixels rendered has a sibling: **daemon state ≠ device presence**.*
2. **The USB hub** — `ioreg` showed a GenesysLogic USB2.1/3.1 hub in the
   chain, and a power-budget theory fit every symptom. Innocent: the block
   enumerated fine behind it. Killed by plugging direct.
3. **Charge-only USB-C cable** — the classic, and wrong here.
4. **DNA snap relaying the neighbor** — plausible (one cable, two blocks),
   but the snapped block was simply never seen either.

## The decisive clue

Walking the stack layer by layer, top-down, instead of theorizing:

```
ioreg -p IOUSB → 2 × "Lightpad BLOCK" (ROLI Ltd.)   ✅ kernel sees both
rtmidi ports   → ['Lightpad BLOCK  Lightpad BLOCK',
                  'Lightpad BLOCK  Lightpad BLOCK']  ✅ two ports…
                                                     ❗ …IDENTICAL names
blocksd        → 1 device                            ❌ breaks here
```

macOS/CoreMIDI does **not** append port numbers. Two ports, byte-identical
names, no index suffix, nothing to tell them apart but their position.

Then, directly against the hardware:

```python
scan_for_blocks() → 2 pairs:
  MidiPortPair(input_port=0, output_port=0, name='Lightpad BLOCK  Lightpad BLOCK')
  MidiPortPair(input_port=1, output_port=1, name='Lightpad BLOCK  Lightpad BLOCK')
unique names: 1        # ← the whole bug, in one number
```

## Root cause

`topology/detector.py` was **never at fault**. Its occurrence counting
(`detector.py:74-85`) exists precisely to handle duplicate names, and it
works: two pairs, correct distinct port indices.

`topology/manager.py` threw that work away:

```python
self._groups: dict[str, _GroupEntry] = {}   # port name → entry
...
for pair in detected:
    if pair.name not in self._groups:       # both pairs → same key
        self._add_group(pair)               # second block never added
```

Two pairs, one key. The second block matched the first's key, the add-guard
skipped it, and it never got a `DeviceGroup` — so it never handshaked, never
appeared in topology, never existed. The port indices that distinguish them
were sitting in the pair, unused as a key.

ALSA appends port numbers (`Lightpad BLOCK:Lightpad BLOCK 20:0`), making
names unique on Linux. **That is the only reason this survived to 2026** —
upstream is Linux-first, and the bug is invisible there.

## The fix (vendored)

`patches/0003-fix-topology-key-device-groups-by-port-indices-not-p.patch`:

3. `src/blocksd/topology/manager.py`: key `_groups`/`_tasks` on
   `(name, input_port, output_port)` instead of `name`; add `_label()` so
   identically-named groups stay distinguishable in logs. Regression test in
   `tests/topology/test_manager.py`.

Verified on hardware 2026-07-16: MacBook (Apple silicon, macOS 15), two
Lightpad Block M — `LPM9E1KL3HO9XC5G` (XC5G) + `LPME4HE5UZQ9SH8T` (SH8T),
both firmware 1.1.0. Before: `discover` → 1 device. After: both enumerate,
both stream, name tags scroll on both glasses (confirmed visually), `visit`
migrates home XC5G → SH8T, and **pong spans both blocks**. Stream held for
minutes with zero reconnects. 340 tests pass; all three patches `git am`
clean onto a fresh clone.

## Upstream PR notes

- Affects **every macOS user with two identical blocks** — likely most of
  them, since blocks are sold to be snapped together.
- The detector already does the hard part; this is a ~12-line manager change.
- **Known remaining sharp edge:** rtmidi port indices are positional, so
  unplugging one block renumbers the other, causing a brief remove/re-add of
  the surviving group. It self-heals next scan. Keying on device *serial*
  would fix it properly, but the serial is only known **after** the group
  handshakes — chicken-and-egg. Worth raising in the PR; not solved here.
- Consider a `log.warning` when two detected pairs share a cleaned name — it
  would have made this a five-minute bug instead of an evening.

## Debugging playbook (macOS, two blocks)

1. `ps aux | grep blocksd` **first**. Two live instances make every reading
   meaningless — they both hold CoreMIDI ports (it's multi-client) and both
   ping the hardware.
2. **Ctrl-Z is not Ctrl-C.** A suspended blocksd (`ps` state `T`) keeps its
   ports and **ignores SIGTERM until resumed** — `kill <pid>` appears to do
   nothing. Use `kill -9`. This cost us a full misdiagnosis cycle.
3. Ground truth is blocksd's `discover` over its socket, *not* `blockctl
   status`/`names` (clawdpadd cache — see red herring 1).
4. Walk the layers top-down and let each one clear itself: `ioreg -p IOUSB`
   (kernel) → `rtmidi.MidiIn().get_ports()` (CoreMIDI) → `scan_for_blocks()`
   (detector) → `discover` (manager). The bug is at the first layer that
   disagrees with the one above it.
5. `system_profiler SPUSBDataType` returns empty under some sandboxes —
   `ioreg -p IOUSB -l` is the reliable probe.
