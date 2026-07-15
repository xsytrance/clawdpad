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

Both live in `vendor/blocksd`, which is now pip-installed **editable** into
`.venv` — replacing the PyPI copy, so `pip install -U blocksd` can no longer
silently revert them. To iterate: edit `vendor/blocksd`, then
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
