# MacBook dress rehearsal — burn the 🧪 down before Charles's demo

*Written 2026-07-16, the night before. Rod runs this on his own MacBook so
Charles never has to debug anything. Each phase ends with what to report
back. Blocks: unplug both from the PC and bring them over (the PC daemon
just waits; when you return, replug and press each block's power button).*

## Phase 1 — the Python stack on macOS (USB, the CoreMIDI unknown)

```bash
git clone https://github.com/xsytrance/clawdpad && cd clawdpad
git clone https://github.com/hyperb1iss/blocksd
(cd blocksd && git am ../patches/*.patch)

# blocksd needs Python >= 3.13. macOS ships /usr/bin/python3 = 3.9.6, so a
# plain `python3 -m venv` builds a venv pip refuses to install into
# ("Package 'blocksd' requires a different Python"). Name the interpreter:
brew install python@3.13
/opt/homebrew/bin/python3.13 -m venv .venv
.venv/bin/python3 -V                 # expect 3.13.x, NOT 3.9.6
.venv/bin/pip install -e ./blocksd segno

# plug ONE block in via USB-C, press its power button, then two terminals:
.venv/bin/blocksd run --verbose      # terminal 1 — keepalive + device log
.venv/bin/python3 clawdpadd.py       # terminal 2 — Clawd appears
./blockctl status                    # terminal 3
```

Then plug the SECOND block in (or snap it on) and run the tour:
`./blockctl names`, `visit`, `marquee "HI"`, `game pong`, `game off`,
snap → reunion, stay snapped → merged-house roaming.

**Watch for (this is the real test):** CoreMIDI may name both USB blocks
identically — blocksd keys device groups by *port name*, so two blocks
with the same name could collide (Linux appends port numbers; macOS may
not). If the second block never appears in `blockctl status`, that's the
finding.

**Report:** does blocksd enumerate? one block OK? two blocks OK? exact
port names from `blocksd run --verbose`'s first lines.

### ✅ RESULT 2026-07-16 — the collision was real, and it's fixed

The run-sheet called the shot. macOS does **not** append port numbers:

```
ioreg    → 2 × "Lightpad BLOCK" (ROLI Ltd.)     both blocks on the USB bus
CoreMIDI → ['Lightpad BLOCK  Lightpad BLOCK',
            'Lightpad BLOCK  Lightpad BLOCK']   two ports, IDENTICAL names
blocksd  → 1 device                             the second block vanished
```

`scan_for_blocks()` was never at fault — its occurrence counting returns
one pair per block with distinct port indices (`in=0/out=0`, `in=1/out=1`).
`TopologyManager` keyed `_groups`/`_tasks` by `pair.name`, so the second
pair collided with the first, the add-guard skipped it, and the block never
got a `DeviceGroup`. ALSA appends port numbers, which is why Linux never
saw this.

Fixed in `patches/0003-fix-topology-key-device-groups-by-port-indices-*.patch`
— key on `(name, input_port, output_port)`, plus `_label()` so identical
names stay readable in logs. Test: `tests/topology/test_manager.py`.
340 tests pass; all three patches `git am` clean onto a fresh clone.
**Upstream PR for hyperb1iss still to send.**

After the patch: both blocks enumerate, `blockctl names` shows XC5G +
SH8T, name tags scroll on both glasses, `visit` migrates home XC5G →
SH8T, and **pong spans both blocks**. Stream held for minutes with zero
reconnects.

Two traps that cost time, worth knowing before demo day:

- **Ctrl-Z is not Ctrl-C.** A suspended (`state T`) blocksd keeps its MIDI
  ports and ignores SIGTERM until resumed. Two live blocksd instances make
  every reading untrustworthy — `ps aux | grep blocksd` before believing
  anything. Use `kill -9`.
- **`blockctl status`/`names` read clawdpadd's cache**, not the hardware. A
  phantom second block showed for an hour from a stale `dev_serials`. Probe
  blocksd's `discover` over its socket for ground truth.

Non-findings, ruled out: the GenesysLogic hub in the chain was innocent
(the block enumerated fine behind it); a charge-only cable was never the
issue.

## Phase 2 — the zero-install web host (what office visitors would use)

Stop both terminals (Ctrl-C; the block falls back to factory mode after
~5 s — harmless). Then:

```bash
cd web && python3 -m http.server 8433
```

Chrome → `http://localhost:8433` → **host my block** → allow MIDI with
SysEx. Clawd should appear on the glass, hosted by the tab. Try moods,
costumes, marquee. (Safari will refuse — no WebMIDI; that's expected and
worth confirming once so we can say it plainly.)

**Report:** works / errors, and how it feels (fps-wise) vs the daemon.

### ✅ RESULT 2026-07-17 — works, after two bugs that needed a second block

The page hosted nothing at first: **both glasses stayed factory.** Two bugs,
each harmless alone, fatal together — and both invisible with one block:

1. **The device index was hardcoded to 9** (`index.html`, every `beginApi`/
   `ping`/`HeapStreamer` call). It was never a constant: blocks report their
   own topology index, and ours differ — **XC5G is 9, SH8T is 32.** The page
   was written when XC5G was the only block, so 9 looked like a fact.
2. **Port selection kept the *last* matching MIDI port** (`for … out = o` with
   no break), so with two blocks it opened SH8T's port — then addressed
   device 9, which SH8T doesn't have. Every packet vanished. Silently: a wrong
   index isn't an error, it's just nobody answering.

The page also **never listened**: `inp` was assigned and never used, which is
*why* 9 was hardcoded — with no input handler there's no way to learn the
index. Fixed by adding `TopologyDecoder` to `clawd-core.js` (ports blocksd's
`_handle_topology`), attaching `onmidimessage`, and asking the block who it
is. Verified against real captured 48-byte topology packets: the JS decoder
independently extracts 9 and 32, agreeing with blocksd's Python decoder.

**Then the buttons.** Only wave/jump/costumes/marquee worked. The rest were
**daemon-only**: `big clawd`, `chibi`, and `QR` called `remoteCmd`, which
opens `if (!remoteOn) return;` — a silent no-op while the tab is the host.
Costumes worked because they're local render state. All now act locally first
*then* call the daemon, so both paths work:

- `wave` / `jump` — ported from `frame_notify` / `frame_celebrate`.
- `chibi` / `big clawd` — `mini()` + `miniAwake/Wave/Celebrate/Sleep/Dance`
  ported from `_mini` / `_mini_frame`. (`miniDance` has no daemon counterpart;
  dance is a web/Android ear thing.)
- `QR` — matrices **baked** by `tools/make_web_qr.py` into `web/qr-data.js`.
  The tab has no encoder and a wrong QR is unscannable, so segno stays the
  reference implementation. Verified bit-identical to segno's matrix.
  Arbitrary text still needs the daemon (`blockctl qr "…"`).

Three UI traps, all found by Rod in 30 seconds of real use:

- **The clawdrobe couldn't be scrolled.** It was `overflow-x:auto` with
  `scrollbar-width:none` — fine with a touchscreen, impossible with a desktop
  trackpad. Now `flex-wrap:wrap`; every outfit visible at any width.
- **The marquee was a one-way door.** Clearing the input and re-sending was
  the only way back and nothing said so. Added an explicit ✕ (and Enter now
  submits).
- **Dance left the mic running.** Releasing it was wired only to the dance
  button, so leaving dance via any other mood kept the tab listening. Any
  mood now releases it.

**Tools built for this** (Claude can't see a glass or a browser console):
`tools/wireprobe.py` — speak the handshake, print what the block says back
(serial, topology, real device index, device logs). `tools/webpreview.mjs` —
render any web pose to ASCII, exits non-zero on a blank frame.
`tools/make_web_qr.py` — bake QR matrices.

## Phase 3 — THE BLE RETEST (this is the historic one)

The only known blocker ("firmware gates API mode over BLE") was retracted
— it was the packet-index bug, and the web page's encoder never had it.
Nobody has retried wireless since. You're about to.

1. Unplug USB. Make sure the block is ON (power button; it's on battery
   now — check the % in `blockctl status` earlier, and see the ⚠️ below
   before you trust that number).
2. Audio MIDI Setup (Cmd+Space, type it) → Window → **Show MIDI Studio**
   → **Bluetooth** button → wait for "Lightpad BLOCK" to appear →
   **Connect**.
3. Back to the Phase 2 tab → reload → **host my block**.

Outcomes, all valuable:
- **Clawd appears wirelessly** → history. Note smoothness; if he
  stutters, BLE bandwidth is the limit and we'll add a low-fps profile.
- Handshake but blank glass → API mode really is USB-gated after all;
  the 2026-07-15 finding un-retracts. Screenshot the console.
- No "Lightpad" in the MIDI device list → pairing issue; note what Audio
  MIDI Setup showed.

**Report:** which outcome + Chrome console output (View → Developer).

### ✅ RESULT 2026-07-17 — **Clawd runs wirelessly. It's the first outcome.**

The 2026-07-15 "firmware gates API mode over BLE" finding **stays retracted**.
Paired via Audio MIDI Setup → Bluetooth, USB unplugged, running on battery,
hosted from the Chrome tab: **Clawd appeared on the glass.** Nobody had
retried wireless since the packet-index bug was blamed and then cleared — so
this had been sitting one test away the whole time. One block so far.

The Phase 2 device-index fix is what made it reachable: over BLE there was
never any reason to assume the index would still be 9, and the page now asks
instead of assuming.

Still open: smoothness over BLE (bandwidth → a low-fps profile if he
stutters), and whether a second block can join wirelessly.

⚠️ **The battery reading was a lie, and it nearly cost us this phase.**
`blockctl status` said `battery 31%` all night, through hours of charging, so
this run-sheet's "mind the %" had us waiting to charge a **full** block. The
protocol's battery field is **5 bits — raw max 31**. blocksd exposes that raw
0-31 as `battery_level`; we printed it with a `%`. The blocks were at
**100%**, pinned at the ceiling. Fixed in `clawdpadd.py` (`battery_percent()`,
raw/31×100). If you ever see exactly "31%" again, suspect the units first.

## Phase 4 — PRISM's Lightpad Out (the Charles moment, rehearsed)

```bash
git clone https://github.com/xsytrance/prism && cd prism
git checkout lightpad-out
python3 tools/dev-server.py 8766
```

Chrome → `http://localhost:8766` → load any track (drag an mp3 in) →
right panel → **LIGHTPAD** group → **Lightpad Out** ON. The show should
glow on the glass over USB. Try `LED Gain`; with both blocks USB'd, try
`Tile Across Blocks`. If Phase 3 succeeded, repeat over Bluetooth —
**Prism visuals, wireless, on a battery block** is the demo finale.

Also run the self-test once on the Mac for the record:
`node tools/lightpad-selftest.mjs` (needs node; `brew install node` if
absent).

**Report:** USB result, tile result, BLE result, gain that looked best.

## Phase 5 — pack up

Blocks back to the PC, replug, press each power button. `blockctl status`
on the PC should show both again. Tell Claude everything — the findings
go into CHARLES.md so demo day has zero unknowns.
