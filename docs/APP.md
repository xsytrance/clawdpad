# clawdpad companion app — design

*2026-07-15. The phone app for keeping up with your Clawd: stats, feeding,
items, his home, play, friends — and talking to him. Android first (Pixel),
iOS close behind. Nothing goes live until Rod says so.*

## Separate repo: yes

**`clawdpad-app`** should be its own repository. Different toolchain,
language, release cadence, and store-review lifecycle; the daemon repo
stays a clean, reviewable Python project a stranger can audit in one
sitting. The contract between them is the daemon's HTTP API — version that,
not a monorepo.

**Recommended stack: Expo (React Native).** One codebase for Android + iOS,
fastest path to a working APK for a Pixel, OTA updates while iterating,
and a dev-client escape hatch for native modules (BLE, if the app ever
becomes a block host itself — see ROADMAP BLE-3).

## How it connects

The app talks to **clawdpadd**, never the block:

- Same Wi-Fi / Tailscale: `http://<host>:8137` with the Bearer token.
  Pairing: **the glass itself becomes the QR code** — shipped 2026-07-15:
  `blockctl qr <data>` renders a Micro QR (format M3 is *exactly* 15x15
  modules; the dark bezel is the quiet zone; lit-pixels-as-dark-modules =
  an inverted QR). M3 alphanumeric tops out at 14 chars / 23 digits, so
  the pairing flow is: block shows a short numeric pair-code → app scans
  (zxing-cpp reads Micro QR + inverted) → app finds the daemon on the LAN
  (mDNS) → `POST /pair {code}` → daemon returns the real token. Stock
  camera apps may or may not read Micro QR — our app always will.
- Away from home: the ntfy topic (already wired) for commands, plus a
  lightweight `GET /status` poll or ntfy state echoes for the dashboard.

## Screens (v1)

1. **Home / him** — live mood, energy, size toggle (**full ↔ mini**, the
   API shipped today: `{"cmd":"size","arg":"mini"}`; on-glass gesture:
   triple-tap), battery, a
   render-mirror of the glass (the daemon can serve the current frame as
   JSON/PNG at `GET /frame` — small addition, makes the app feel alive).
2. **Stats** — level, XP, hunger curve over time, meals, sessions he's
   lived through, uptime streaks. (Daemon addition: a tiny ring-buffer
   history endpoint, `GET /history`.)
3. **Feed** — camera/gallery/notes → feed items. He eats, gains XP, the
   glass shows him munching (new `eat` pose: mini walks to a food pixel,
   chomps). See "the soul" below.
4. **Home & items** — his room in mini mode: place a bed, food bowl,
   plant, rug (room JSON the daemon renders behind roaming mini-Clawd).
   Items = the Pro props system's first customers; the app is the
   inventory UI.
5. **Play** — ball toss (a bouncing pixel he chases — physics on the
   daemon, flick gesture on the phone), laser-dot chase (drag your finger
   on the phone, he chases the dot on the glass — remote petting, works
   from anywhere), tug-of-war against your real finger on the block.
6. **Friends** — the Duet surface: befriend Charles, pick a scene
   (dance/fight/pair-code), send your Clawd traveling (Pro).
7. **Talk** ⭐ — chat with *your* Clawd. On the glass: leaning poses +
   melodic babble. In the app: his actual words.

## "Connect to my Claude account" — the Talk feature

The right integration is **Sign in with Claude / the Claude Agent SDK**:
the user OAuths with their own Claude account, and the app makes Claude
calls on their subscription — no server of ours, no API keys to manage.
Clawd's persona prompt (a small creature who lives on a Lightpad, knows
his stats, remembers his diary/meals via the daemon's status+history
endpoints as tool calls) turns the chat into *him*. Claude Code users get
extra magic: he can genuinely answer "what did we work on today?" from the
session registry. Needs verification of the current OAuth/SDK terms when
we build it — the design assumes only: user-owned auth, app-side calls.

## The soul, standalone (prereq for feeding)

Today the soul is mirrored from dazzler (read-only, one soul two bodies).
App users won't have dazzler, so clawdpad grows a **native soul module**:
same schema (hunger/xp/level/meals/mood), same tick rules, stored in
`~/.local/state/clawdpad/soul.json` — active only when the dazzler mirror
is absent, so Rod's rig keeps dazzler as the single owner. Feed API:
`POST /feed {"kind": "photo|note", "caption": ...}` → hunger up, XP, munch
pose, item logged for the diary/stats screen.

## API additions the app needs from the daemon (small, Basic-friendly)

| endpoint | purpose |
|---|---|
| `{"cmd":"size"}` | ✅ shipped today |
| `GET /frame` | live 15×15 mirror for the app's home screen |
| `GET /history` | stats screen (ring buffer: mood/energy/hunger samples) |
| `POST /feed` | native-soul feeding |
| `{"cmd":"room", ...}` | place/remove furniture (mini mode) |
| `{"cmd":"ball"} / {"cmd":"dot", "x":…, "y":…}` | play modes |
| `blockctl pair-qr` | QR pairing |

## My additions (opinionated)

- **Push notifications via ntfy** (no Firebase needed for v1): "Clawd is
  hungry", "battery 15%", "Charles's Clawd is at the door", "he leveled
  up while you were out". The ntfy app or our app subscribes to the same
  topic the daemon already publishes to.
- **Widget/watch tile**: his current pose + mood as a 1×1 home-screen
  widget. Glanceable creature.
- **Do-not-disturb inheritance**: app knows your phone's DND; tells the
  daemon to hold jingles/whispers (quiet hours already exist — this
  automates them).
- **Guest QR**: coworkers scan a QR and get a read-only live view + one
  free "wave at him" button. Maximum office virality, zero risk.
- **Explicitly not in the app**: streaming the glass as video, text on the
  glass, or any remote control that would make him a gadget instead of a
  creature. The app keeps up with him; it doesn't puppet him.


## Field notes — first live Android host session (2026-07-15, 7-8am)

Built v0.1 as a *player of precomputed SysEx* (tools/make_app_stream.py
generates handshake + per-mood diff-stream loops from the proven Python
stack; the Kotlin app is MIDI plumbing + playback + pings). Findings, in
order of discovery, over BLE via the MIDI BLE Connect bridge:

1. **The transport works.** Serial dump answered (MAC + serial parsed from
   the hex), GATT writes flowed at full rate, zero errors.
2. **The block speaks from topology index 9, not 0.** Every command must be
   addressed there; the serial request works index-less, which masked it.
   v0.2 must parse the topology response instead of hardcoding.
3. **Packet counters are device-wide and persist across sessions.** A
   precomputed stream numbered from 0 only aligns after a block power
   cycle. (ACK counters visibly count our packets 0,1,2… after a fresh
   boot.)
4. **beginAPIMode must be re-sent until the device engages** — blocksd
   loops it every cycle; a single send is not enough (v0.1.2 courts 8×).
5. **The wall: firmware appears to gate API mode to USB.** With perfect
   alignment and persistent courting, the block ACKs everything and still
   keeps its factory app — consistent with ROLI never supporting BLE for
   anything but note-MIDI (their docs: Bluetooth on macOS only, for
   playing). **Pivot: USB-C phone hosting** — Android MIDI treats a
   USB-attached block identically (the app auto-connects on plug-in as of
   v0.2), and USB is the transport the protocol is proven on.

**RESOLVED (v0.3, evening of the same day):** the real bug was an
off-by-one in the packet index — the device ACKs counter 0 after
topology, so the first data packet it accepts is #1; ours started at #0
and the program-header packet was silently dropped. Found by capturing a
working blocksd TX byte-log (BLOCKSD_TX_LOG env in the vendored
connection.py) and diffing: identical except byte 7. The 'firmware gates
API mode over BLE' theory is RETRACTED — finding #5 above was this same
bug wearing a costume. v0.3 seeds the generator at index 1 and renumbers
every packet live in Kotlin (golden-tested against the Python builder),
making loops infinite. VERIFIED: Clawd animating on the block, hosted by
a Pixel 10 Pro XL over USB-C, no computer. BLE retest pending.

Next for v0.4+: parse topology + ACKs live (drop hardcoded index 9),
Kotlin Clawd renderer instead of baked loops (touch reactions!),
foreground service, BLE wireless verification.
