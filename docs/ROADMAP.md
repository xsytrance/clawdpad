# clawdpad roadmap — Basic and Pro

*Written 2026-07-15. Basic ships first and stays small and delightful; Pro is
the ecosystem play. Nothing here is promised to anyone but Clawd.*

> **See [LEVELS.md](LEVELS.md) (2026-07-17) — the capability ladder (L0 tab →
> L1 daemon → L2 app → L3 integrations → L4 colony), which is the newer spine.**
> Basic ≈ L0–L2, Pro ≈ L3–L4; the Pro section below is L3's feature list
> written early. The two taxonomies should merge into one before they start
> lying to each other — LEVELS.md "How this maps onto Basic/Pro" has the
> proposal, and it's Rod's call.

## Basic (v1.x) — "he just lives there"

The bar for Basic: clone → run → a creature lives on your desk. Every
feature must survive the question *"is this Clawd, or is this a dashboard?"*

Shipped: the character (breathe/blink/glance/pace/wave/jump/sleep), full
touch vocabulary (pet, slide, tap, double-tap), Claude Code hooks, energy →
pacing speed, synthesized sounds, `blockctl demo`, optional HTTP/ntfy remote
and dazzler soul link.

Recommended next, in order:

1. ~~**`blockctl doctor`**~~ — ✅ **shipped 2026-07-17.** Nine checks: Python
   ≥3.13, blocksd editable (not a PyPI copy that silently reverts the fixes),
   all three patches present, blocksd answering, a block on the wire (asked of
   blocksd, never blockctl's cache), `audio` group, clawdpadd alive, Claude Code
   hooks wired, and device-log faults. Prints the fix under each failure.
   Built as a **library with two faces** (LEVELS idea #2): `doctor.py` returns
   data and never prints, `blockctl doctor` renders it, `--json` for anything
   else, and the L2 app's first-run screen is the third face for free.
   Its patch probes are also a regression test on the vendored fork — they run
   in `tools/check.sh`, so a dropped fix goes red there instead of on a dark
   glass at 2am. **Still to verify: the negative paths.** Every check has only
   ever been seen passing (or skipping) on a healthy tree; the FAIL branches are
   argued, not observed. Break things on purpose one evening.
2. **`install.sh`** — venv + patched blocksd + systemd units + (optionally)
   the Claude Code hooks JSON merge, one command.
3. ~~**Battery body language**~~ — ✅ **shipped 2026-07-17.** Sluggish pacing
   and slow yawning blinks under 20%, a contented warm pulse while charging.
   `State.battery_pace/battery_vigor/battery_tired`, shaped like `pet_vigor()`
   so they compose. It was blocked by a bug nobody had noticed: the protocol's
   battery field is 5 bits, so `state.block["battery"]` was a raw 0-31 printed
   with a `%` — a full block read "31%" and there was no threshold to write
   against. Fixed (`battery_percent()`); see docs/MACBOOK.md Phase 3.
4. ~~**Config for the sleep window**~~ — ✅ **shipped 2026-07-17.**
   `"sleep": [23, 7]` in config.json. Wraps midnight or doesn't (`[1, 7]` is a
   dawn nap); `[0, 0]` never sleeps, which is the demo-table setting. Bad config
   keeps the default instead of killing the daemon — fat-finger a number and you
   get your old bedtime back, not a dead creature and a traceback in a journal
   you've never read.
5. **Micro-behaviors** — 🟡 **half shipped 2026-07-17.** The stretch (arms
   over his head, up on his toes, ~1.6s every ~10 min) and the long look (left,
   hold, right, ~2.6s every ~6 min) are in, on both bodies, parity-checked at
   times inside their windows — an untested rare behaviour is an unshipped one.
   Both are pure functions of the clock (`idle_window`/`Clawd.idleWindow`), no
   state and no randomness, which is what lets the desk and the browser agree
   on when he stretches. Periods are coprime-ish (607, 371) so they never lock
   into a rhythm, since a rhythm is the loop this exists to break.
   **Still to do: sitting down after an hour idle.** It's the only one of the
   three that needs *state* — "how long since anything happened" — and that
   doesn't belong in a pure pose. It wants an idle clock on `State` passed in
   like `tired`, which is a design decision, not a leftover.
6. **Pinch to resize** — triple-tap toggles full/mini today; the block is
   multitouch, so a two-finger pinch (shrink) / spread (grow) gesture is
   the natural upgrade. Needs per-index touch tracking.
7. ~~**Sad pose**~~ — ✅ **shipped 2026-07-17.** Slumped body (dy +1), drooped
   arms (+2), heavy blinks, and he looks away and holds it. `blockctl mode sad`;
   `Clawd.sad`/`miniSad` in clawd-core.js, `frame_sad` on the desk, byte-identical
   (parity 32/32). Petting comforts him but doesn't straighten him up — you
   can't pet the sad out of him in one go. **Nothing triggers it automatically
   yet**: the failure-streak and starving-soul hooks are still to write, and
   until they exist he only mopes when asked. Scarcity is the whole design, so
   that wiring deserves its own thought rather than a threshold picked today.

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

> **✅ The missing primitive landed 2026-07-17: the outbound event stream.**
> Everything below needed a way for Clawd to say what *he* did, and the daemon
> had none — `apply()` was strictly request/response and the only push in the
> whole system was ntfy's 1 Hz coalesced state echo on three fields. A tap, the
> most important thing he can tell you, never left the process.
> Now: `{"cmd":"subscribe"}` on the socket, `GET /events` (SSE) over HTTP.
> Kinds: `notify · ack · tap · double-tap · triple-tap · touch · session`.
> **`notify` → `ack` is the loop** — raise a thing, he holds it, and `ack`
> fires when a human taps the glass. That's tap-to-acknowledge, working today,
> without the callback URL. Gesture commands now have a touch stream to read.
> See docs/MANUAL.md §7b.

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
