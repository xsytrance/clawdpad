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
python3 -m venv .venv
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

## Phase 3 — THE BLE RETEST (this is the historic one)

The only known blocker ("firmware gates API mode over BLE") was retracted
— it was the packet-index bug, and the web page's encoder never had it.
Nobody has retried wireless since. You're about to.

1. Unplug USB. Make sure the block is ON (power button; it's on battery
   now — mind the % in `blockctl status` earlier).
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
