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

# 2. python env (any Python 3.11+; macOS ships one, brew's is fine too)
python3 -m venv .venv
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

If it fails, it fails in `blocksd run` (CoreMIDI port naming is the
untested part) — screenshot the error for Rod. Everything above blocksd
is OS-agnostic.

## Connecting the two pads 🎉 (✅ built 2026-07-15, needs 2nd block to verify)

On whichever machine hosts (Charles's Mac if the 🧪 works, otherwise any
Linux box, otherwise back at Rod's place):

- **Option A — snap them**: ROLI DNA magnetic edges, click together.
  One USB cable powers the pair; the master relays its neighbor.
- **Option B — two USB cables** into the same computer. Works identically.

Either way, within ~15 seconds clawdpadd notices the topology change and
**every block gets a Clawd — twins in perfect lockstep**: both breathe,
blink, pace, and jump together; pet either block and *both* lean toward
the finger (they feel each other — enjoy the reaction when people notice).
Independent personalities, cross-block chase/dance/fight scenes are the
next milestone (DUET.md tier 1); today is the twins demo.

`./blockctl status` shows `+1 twin(s)` when the second block is live.

## If the Mac path fails

- **Guaranteed**: any Linux laptop → follow README install (15 min), or
  bring both blocks to Rod's rig after work.
- **Legion Go**: WSL is a dead end for MIDI; *native Windows* Python +
  rtmidi (WinMM) is plausible but untested — same 🧪 tier as macOS,
  prep it before relying on it.
- Rod's Pixel 10/7 as host: ❌ until the mobile-host app exists (the
  block's protocol needs a program that owns USB MIDI; Android requires
  a native app for that — it's on the Pro roadmap).

## Wireless status (asked 2026-07-15)

❌ Not yet. The path (ROADMAP → Bluetooth): Linux BLE-MIDI pairing first
(BlueZ + PipeWire, this machine has the stack), adaptive diff-streaming at
8–12 fps, USB↔BLE failover. First attempt is scheduled for the home rig —
it does not block the office demo, which is USB either way.
