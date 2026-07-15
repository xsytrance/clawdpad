# clawdpad roadmap — Basic and Pro

*Written 2026-07-15. Basic ships first and stays small and delightful; Pro is
the ecosystem play. Nothing here is promised to anyone but Clawd.*

## Basic (v1.x) — "he just lives there"

The bar for Basic: clone → run → a creature lives on your desk. Every
feature must survive the question *"is this Clawd, or is this a dashboard?"*

Shipped: the character (breathe/blink/glance/pace/wave/jump/sleep), full
touch vocabulary (pet, slide, tap, double-tap), Claude Code hooks, energy →
pacing speed, synthesized sounds, `blockctl demo`, optional HTTP/ntfy remote
and dazzler soul link.

Recommended next, in order:

1. **`blockctl doctor`** — one command that checks everything a new user
   trips on: blocksd running? block detected? patches applied (probe for the
   assembler fix)? user in `audio` group? frames actually rendering (device
   log check)? Prints fixes, not just failures. *Adoption lives or dies here.*
2. **`install.sh`** — venv + patched blocksd + systemd units + (optionally)
   the Claude Code hooks JSON merge, one command.
3. **Battery body language** — the block knows its battery; Clawd should:
   sluggish pacing and slow yawning blinks under 20%, a contented warm pulse
   while charging. (Data is already in `state.block["battery"]`.)
4. **Config for the sleep window** — `"sleep": [23, 7]` in config.json;
   night-owl owners exist (see: this project's entire commit history).
5. **Micro-behaviors** — rare idle moments so he never feels looped: a
   stretch (arms up + tall body) every ~10 min, a long look left then right,
   sitting down (body drops 2px, legs tucked) after an hour of idle. Keep
   them rare — scarcity is what makes them alive.
6. **Sad pose** — the one missing emotion: slumped body (dy +1), drooped
   arms (+2), heavy blinks. Used sparingly: repeated command failures,
   starving soul. (This was the old red-flash; now it's a feeling.)

## Bluetooth (the cable-cutting arc)

Goal: Clawd roams the desk on battery. Reality check: the Lightpad speaks
**BLE MIDI** — same SysEx protocol, radically less bandwidth (~4–10 KB/s
usable vs USB's effectively unlimited; full frames are ~790 B packed, so
naive 20 fps streaming does not fit).

The architecture already has the right shape: **hub and spoke**. One host
owns the block (keepalive + frames); everything else talks to the *host*,
not the block. Phones/tablets/other PCs already "talk to it" today via
HTTP + ntfy — that's PC, Mac, Android, and iOS covered for *control*
with zero new code. What Bluetooth actually buys is an **unplugged block**.

Milestones:

- **BLE-1 (Linux, this machine):** pair via bluetoothctl (BlueZ 5.85 +
  PipeWire ≥0.3.65 expose BLE MIDI as a normal MIDI node). If the port name
  matches, blocksd may need only a lower-fps profile. Key enabler: the
  SharedDataChange protocol is *diff-based* — Clawd's animations change few
  pixels per frame (a blink is 4 bytes, a pace step is two columns), so
  adaptive diff streaming at 8–12 fps should feel identical. Add a
  `transport: usb|ble|auto` config with automatic failover (plug in → USB
  takes over; unplug → BLE resumes).
- **BLE-2 (battery etiquette):** BLE mode implies battery: dim everything
  15%, drop idle fps, sleep sooner, battery body language (Basic #3) doing
  real work.
- **BLE-3 (hosts beyond Linux):** the protocol layer of blocksd is pure
  Python — the MIDI transport is the only platform-specific piece. A
  `bleak`-based transport (cross-platform BLE) could make the host run on
  macOS/Windows. Mobile *hosts* (the phone keeps Clawd alive with no PC)
  are a Pro-sized project.
- **BLE-4 (the dream, Pro):** a $10 ESP32 dongle as a standalone host —
  Clawd lives with **no computer at all**. The keepalive + diff-streaming
  loop fits comfortably in an ESP32; poses could be baked or pushed over
  Wi-Fi. This is the "buy a block, flash a dongle, own a creature" product.

## Duet — two Clawds (Basic *and* Pro)

Two blocks can interact **with no middleman at all**: ROLI's DNA connectors
snap blocks into a hardware topology the protocol reports natively — the
master relays its neighbor over one link, and one clawdpadd drives both as
a single canvas with a seam. Dance, chase, fight, pair-code, and
Animal-Crossing-style melodic "talk" through the host speakers. Remote
friends federate daemon-to-daemon (LAN/tailnet in Basic; internet via ntfy
plus **Traveling Clawd** — he walks off your block and onto theirs — in
Pro). Full design: [DUET.md](DUET.md).

## Pro — "the ecosystem"

Pro is APIs + an open reaction vocabulary, so anything can make Clawd feel
something. Design center: **props and poses, not pixels** — integrators say
*what happened*, Clawd decides how to be about it. Nobody gets to draw on
the glass directly; that's how you keep every integration looking like him.

- **Props system** (the foundation): small overlay sprites Clawd holds,
  wears, or stands next to, composed onto any pose. An envelope held in his
  mouth (you've got mail), a tiny clock (meeting soon), an umbrella
  (rain incoming), a red hard-hat (deploy in progress), a flag (CI result).
  Props are 5×4-ish sprites with an anchor point — one JSON file each, so
  the community can draw them.
- **Event API**: `POST /event {"type": "email", "prop": "envelope",
  "urgency": 0.4, "ttl": 300}` → Clawd holds the envelope until tapped
  (tap = acknowledged, event marked read via callback URL). A queue, not a
  firehose: he holds one thing at a time, like anyone with a mouth.
- **Feeling API**: `POST /feel {"emotion": "proud|worried|excited|tired",
  "intensity": 0.7}` — maps to pose/gait/brightness. This is what agent
  frameworks integrate with (OpenClaw agents reporting their state: a
  blocked agent = worried pacing; a finished pipeline = the jump).
- **Agent presence**: multiple registered agents each get a presence slot;
  Clawd's overall mood is the argmax of their states. Optionally: DNA-link
  more blocks (the topology already supports it) — a literal *colony*, one
  block per agent. Claude Code, OpenClaw, cron jobs, CI — each a creature.
- **Gesture commands (two-way)**: draw a ✓ on the glass to approve a
  pending permission prompt, an ✗ to deny, a circle to re-run. The touch
  stream is already rich (x/y/pressure paths); a tiny $1-recognizer gets
  this. This turns Clawd from a display into a *control surface with a
  personality* — likely the single most useful Pro feature.
- **Watch/phone packs**: first-class HTTP Shortcuts / Tasker / HA blueprint
  bundles (Basic ships raw recipes; Pro ships importables).
- **Sound packs**: melodies are already data (`MELODIES`); let people ship
  theirs. Quiet hours config.
- **clawdpad.dev registry** (someday): props, sound packs, and integration
  blueprints, community-contributed, one `blockctl install envelope` away.

## Explicitly out (any tier)

- Text scrolling, dashboards, notification counts — that's a smartwatch,
  not a creature.
- Direct pixel access for integrators (see Props).
- Anything that makes the default experience noisy. Clawd is calm company;
  the jingle cooldown and whisper budgets are load-bearing personality.
