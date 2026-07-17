# Clawd meets Charles — the office playbook

*Written 2026-07-15 at 7am for a same-day meetup. Honest labels: ✅ works,
🧪 experimental (built, never run on that OS), ❌ not yet.*

## The one-paragraph truth

A Lightpad always needs a **host computer on a USB cable** — it powers
itself off without one (❌ wireless isn't live yet; BLE is designed, not
built — see ROADMAP). Any **Linux** machine running this repo is ✅. A
**MacBook** is 🧪: our whole stack is pure Python and the MIDI layer
(python-rtmidi) speaks CoreMIDI natively, so it *should* work — nobody has
tried yet. Charles gets to be the first. Phones as hosts are ❌ (that's
the future mobile-host app). Windows/WSL is ❌ for now (WSL2 kernels
can't see USB MIDI without surgery).

## Charles's MacBook, step by step (🧪 ~10 minutes)

```bash
# 1. clone both repos
git clone <rod's clawdpad repo> clawdpad
git clone https://github.com/hyperb1iss/blocksd
cd blocksd && git am ../clawdpad/patches/*.patch && cd ../clawdpad

# 2. python env — blocksd needs Python >= 3.13, and macOS ships 3.9.6, so
#    a plain `python3 -m venv` builds a venv pip refuses to install into
#    ("Package 'blocksd' requires a different Python"). Name the interpreter:
brew install python@3.13
/opt/homebrew/bin/python3.13 -m venv .venv
.venv/bin/python3 -V                  # expect 3.13.x, NOT 3.9.6
.venv/bin/pip install ../blocksd segno

# 3. plug the Lightpad in (USB-C), press its side button, then two terminals:
.venv/bin/blocksd run                 # terminal 1 — keeps the block alive
.venv/bin/python clawdpadd.py        # terminal 2 — Clawd appears
```

No systemd on a Mac — two terminals is the whole ceremony. **Control
panel**: open `control.html` (repo root) in any browser → point it at
`http://127.0.0.1:8137` with the token from `~/.config/clawdpad/config.json`
(create the config per README) → buttons for jump/jingle/summon/mini/QR/say.
Zero installs — that's the Mac "app" for day one. Sounds work
automatically (`afplay` fallback is in). `./blockctl status` works in a
third terminal.

**The whole Mac path is rehearsed as of 2026-07-16** — Rod ran it end to
end on his own MacBook, one block and two. CoreMIDI port naming *was* the
untested part, and it *was* broken: macOS names every block
`Lightpad BLOCK  Lightpad BLOCK` with no index suffix, and blocksd dropped
the second one. Fixed in `patches/0003-*` — which is why step 1's
`git am ../clawdpad/patches/*.patch` is not optional on a Mac. If it still
fails, it fails in `blocksd run` — screenshot the error for Rod.
Everything above blocksd is OS-agnostic.

## Connecting the two pads 🎉 (✅ built 2026-07-15, ✅ verified on macOS 2026-07-16)

On whichever machine hosts (Charles's Mac if the 🧪 works, otherwise any
Linux box, otherwise back at Rod's place):

- **Option A — snap them**: ROLI DNA magnetic edges, click together.
  One USB cable powers the pair; the master relays its neighbor.
- **Option B — two USB cables** into the same computer. Works identically
  — ✅ verified on macOS 2026-07-16, but **only with `patches/0003-*`
  applied**; without it the Mac silently ignores the second block.

Either way, within ~15 seconds clawdpadd notices the topology change.

**Update 2026-07-16 — verified live with Charles's borrowed block, the
twins are individuals now (✅ all of it):**

- **Name tags**: when a block joins, each glass scrolls its own name
  (`block_names` in config; `blockctl names` replays it).
- **One Clawd, two rooms**: he lives on the home glass; the other keeps a
  dim ember night-light. Every few minutes he wanders over — walks off
  one glass, crosses the bezel, walks onto the other. Tap the empty
  glass to summon him. `blockctl visit` forces a hop.
- **The traveling scarf**: on any glass that isn't home he wears his
  scarf. One glance says whose block he's on.
- **The reunion** 💕: DNA-snap the blocks and the moment the magnets
  click he jumps for joy while the other glass beams a pulsing heart,
  jingle and all (`blockctl anim reunion` to preview).
- **The merged house**: while snapped, the wall is gone — he roams the
  full 30-wide room and sits straddling the seam, one eye per glass.
  Unsnap and the separate rooms (ember, scarf, visits) come back.
- **Pong** 🏓: `blockctl game pong` — one field across both glasses, a
  finger on each glass is a paddle, chime + giant score digit per point.
  One block alone plays wall-ball. `blockctl game off` ends it.
- Notify/celebrate/QR mirror on all glasses; a marquee flows across the
  row as one wide ribbon (`blockctl marquee "HI CHARLES"`).

`./blockctl status` shows `+1 more (home ROD)` when the second block is
live; `blockctl names` prints the roster.

## If the Mac path fails

- **Guaranteed**: any Linux laptop → follow README install (15 min), or
  bring both blocks to Rod's rig after work.
- **Legion Go**: WSL is a dead end for MIDI; *native Windows* Python +
  rtmidi (WinMM) is plausible but untested — same 🧪 tier as macOS,
  prep it before relying on it.
- Rod's Pixel 10/7 as host: ✅ over USB-C — clawdpad-app v0.3 verified
  (Clawd animating, hosted by the Pixel, no computer). BLE from Android
  is 🧪: the old "firmware gates API mode over BLE" theory was RETRACTED
  (it was the packet-index off-by-one, fixed in v0.3) — retest pending.

## Wireless status (updated 2026-07-17)

# ✅ **IT WORKS. Clawd runs on a battery block over Bluetooth.**

Rod did it on his MacBook the night before demo day (`docs/MACBOOK.md`
Phase 3). Paired through Audio MIDI Setup → Bluetooth, USB unplugged, hosted
from the Chrome tab: Clawd on the glass, no cable, no daemon, no install.
The "firmware gates API mode over BLE" theory is **dead** — it was always the
packet-index bug. Nobody had retried since it was fixed; it had been one test
away the whole time.

**This is the demo finale.** A block on a table, nothing plugged into it, a
browser tab driving it.

Verified: one block, over BLE, from the web page. Not yet: two blocks
wirelessly, and long-run smoothness (BLE MIDI is ~4–10 KB/s — if he stutters
we add a low-fps profile; the diff streaming was built for exactly this).

Remaining paths:

- **Charles's iPhone**: iOS speaks BLE MIDI natively (pair through
  GarageBand or any Bluetooth-MIDI-capable app), so the block works as
  a wireless *instrument* from the phone today. Hosting Clawd from an
  iPhone needs a native iOS app (no WebMIDI in iOS browsers, and
  clawdpad-app is Android) — a Swift sibling is a roadmap item.
- **Linux (home rig)**: BlueZ + PipeWire expose BLE MIDI as a MIDI node;
  if the port name matches, blocksd may need only a lower-fps profile.

## PRISM × Lightpad (2026-07-16)

Branch `lightpad-out` in the prism repo: `js/lightpad.js` streams PRISM's
output canvas to every connected Lightpad over Web MIDI (no bridge, no
build step — house rules), 15×15 @ ~12 fps as heap diffs. Params:
`lightpad.enabled` / `lightpad.gain` / `lightpad.tile` (N blocks tile
into an LED wall). Blocks left in factory MPE mode remain MIDI LEARN
controllers — mix display + control roles across his four blocks.
`tools/lightpad-selftest.mjs` pins the encoder to golden vectors from
real-hardware captures. Works on the MacBook in Chrome/Edge (Safari has
no WebMIDI), USB now, BLE per above once verified.
