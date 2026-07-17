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

> ## ⚠ This document was overtaken by reality — read this first
>
> *2026-07-17.* Two of this doc's load-bearing decisions were never followed,
> and `xsytrance/clawdpad-app` has been shipping the opposite for two days:
>
> | this doc says | the repo actually is |
> |---|---|
> | **Expo / React Native**, one codebase for Android + iOS | **native Kotlin** (`dev.clawdpad.host`), Android only, AGP 8.5.2 / JDK 17 |
> | a **controller** — "talks to the daemon, never the block" | a **host** — it drives the block over Android MIDI with no computer at all |
>
> Neither reversal is wrong; both are undocumented, which is how a doc starts
> lying. The host/controller flip is the bigger one: per LEVELS.md the app is
> **L2**, and a chunk of L2 therefore already exists on Android.
>
> Everything below still describes a *worthwhile* app — the stats/feed/talk/
> friends screens, the soul, the QR pairing. Read it as **the controller half,
> unbuilt**, not as a description of the repo. Someone should decide whether
> clawdpad-app grows those screens (host *and* controller in one app) or they
> land in a separate companion, and then rewrite this header away.

## How it connects

*(As designed — for the controller half. The shipped app is a host and talks
to the block directly; see the header above.)*

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

## Battle mode 🐛🚀🧪

Rod's ask, 2026-07-17. Rock-paper-scissors as **Bug · Ship · Test** — a test
catches a bug, a bug blocks the ship, and "ship it" overrules the test. Clawd's
hand comes from his real state (energy from the Claude Code hooks, hunger from
the soul, battery), so you're playing against your own workday, and his gait
tells during the countdown. Phone is your hand, the glass is the arena, the
daemon is the referee.

Full design, including the daemon additions it needs: **[BATTLE.md](BATTLE.md)**.

## Updates — "tap here to check for updates"

Rod's ask, 2026-07-17: upgrade straight from the app. One button in Settings,
and it must **say what it found** — "You're up to date" is a feature, not a
non-event. Never update silently: this app talks to a creature, and a creature
that changes behaviour without telling you is a bug report.

> **Corrected 2026-07-17:** the first draft of this section was written against
> `expo-updates` — OTA JavaScript bundles, "check → fetch → reload". **None of
> that exists.** The app is native Kotlin (see the header), so there is no JS
> to hot-swap and no OTA channel: *every* update is a whole APK. That deletes a
> tier of complexity and one real footgun (OTA onto a mismatched runtime), and
> it makes the button simpler than first designed. Good news, arrived late.

**Every update is an APK.** No OTA, no partial updates, no "restart to apply" —
download, install, done. The button's whole job:

1. `GET` the manifest (below). One request, and it must time out gracefully —
   a creature app that hangs on a settings screen because Wi-Fi is captive is
   a bad creature app.
2. Compare `versionCode` against `BuildConfig.VERSION_CODE`. Not the name —
   names are for humans, `versionCode` is what Android actually orders by.
3. Same or older → **"You're up to date"**, and say the version. That's the
   feature; a button that does nothing visible reads as broken.
4. Newer → show `notes`, download, **verify `sha256`**, then hand it to
   `PackageInstaller`.

**Sideloading is the awkward part, and it's Android's rule, not ours.** We're
not on Play (yet), so installing means `REQUEST_INSTALL_PACKAGES` + a
`PackageInstaller` session, and the OS shows its own scary "install unknown
apps" screen the first time. Nothing we can do about that except not be
sketchy: verify the hash before the install intent, and never auto-install.

**The signing trap, which is worse than it looks:** the APK CI publishes today
is *debug-signed*. Android refuses to upgrade an installed app in place if the
signing key changes, so the day this ships a release-signed build, every
sideloaded tester must uninstall first — losing local state — and the updater
button will simply fail with a signature mismatch. Either keep one key forever
or plan that break deliberately, with a release note that says "uninstall
first". Decide before there are testers, not after.

Where the manifest comes from:

1. **GitHub Releases — ✅ shipped 2026-07-17, so build against this.** A `v*`
   tag runs `.github/workflows/build.yml` in clawdpad-app, which tests, builds,
   and attaches the APK with its sha256. `GET /repos/xsytrance/clawdpad-app/
   releases/latest` is a public, unauthenticated JSON endpoint that already
   carries `tag_name`, the notes, and the asset URL — **the manifest exists
   whether we write one or not.** The button can ship against it today.
2. **Self-hosted from the daemon** — `GET /app/latest` returns the manifest
   below over the tailnet. No store, no GitHub, and it fits LEVELS.md rule 4
   (local-first): your creature's updates come from your own machine. Worth it
   the day the app is *also* a controller and the daemon is already in the
   conversation. About a day.
3. **Play Store internal testing track** — free, real update UX, no scary
   unknown-sources screen, and Charles can be a tester with an email address.
   The answer if this app ever has a life beyond Rod's Pixel; overkill before.

**Check compatibility, not just version.** The contract between app and daemon
is the HTTP API (see "Separate repo" above), so the updater must answer *"will
this app still talk to my daemon?"* — hence `min_daemon_api` in the manifest.
Note this only bites once the app talks to a daemon at all: today it's a pure
host and has no daemon to mismatch, which is a reprieve, not an exemption.
An app that updates itself into being unable to reach Clawd is worse than an
app that never updates. If they'd mismatch, say so **before** downloading, and
say which side needs the upgrade.

**The Clawd-shaped version:** the check isn't a spinner — he *fetches*. Tap,
and he trots off the left edge of the glass, comes back with the answer in his
mouth (envelope prop = update waiting, nothing = you're current), and the
restart is him waking up new. Body language, not a progress bar. The daemon
gets the same news over the event stream, so the block tells you even when
your phone's in your pocket.

## Distribution — where the APK lives (and where it doesn't)

*Written 2026-07-17, when Rod asked to put the APK in the repo. There was no
APK — `xsytrance/clawdpad-app` had two days of Kotlin and zero releases — so
this recorded the decision in advance. **Shipped the same day**: CI now builds
it and a `v*` tag publishes it.*

**The APK never goes in git.** Not this repo, not `clawdpad-app`. Git keeps
every binary forever: a 50 MB APK committed once is 50 MB in every clone of a
Python repo whose whole pitch is that a stranger can audit it in one sitting,
and every rebuild adds another copy. There is no undo short of rewriting
history. This is not a style preference — it's the one packaging mistake that
can't be walked back.

**It goes in a GitHub Release**, attached as an asset on a tag. Free, built for
exactly this, doesn't touch the tree, and gives the updater a stable URL to
fetch. `.gitignore` should carry `*.apk` / `*.aab` from the app repo's first
commit, before anyone can do it by accident.

**How it works now** (`clawdpad-app/.github/workflows/build.yml`, 2026-07-17):
every push builds and runs the Kotlin golden tests, leaving the APK on the run
page; a `v*` tag additionally publishes it to a Release with its sha256 in the
notes. Tests gate the build — an APK that speaks the protocol wrong is worse
than no APK. Two known rough edges, both deliberate: the build is
**debug-signed** (see the signing trap above), and the repo has **no Gradle
wrapper**, so CI pins Gradle 8.7 by hand — AGP 8.5.2 needs ≥ 8.7. Adding a real
wrapper is the better fix and wants a machine with Gradle on it.

The updater's manifest — GitHub's own `releases/latest` JSON already covers
most of this; write one only if the daemon starts serving `GET /app/latest`:

```json
{
  "version": "1.2.0",
  "runtime_version": "1",
  "url": "https://github.com/xsytrance/clawdpad-app/releases/download/v1.2.0/clawdpad-1.2.0.apk",
  "sha256": "…",
  "min_daemon_api": 3,
  "notes": "Battle mode: Bug · Ship · Test"
}
```

`sha256` is not optional: sideloading already asks the user to click through
Android's "install unknown apps" warning, and an unverified download over a
URL is the one place this project could actually hurt someone. Check the hash
before the install intent, and fail loudly.

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

### The QR-blank saga (2026-07-16) — firmware wipes frame data on program reload

The app's QR blanked while every animated mood worked. Emulator said the
bytes were perfect; the wire said every packet was ACKed. The clue: giving
the QR a blinking corner "heartbeat" pixel — the DOT rendered on an
otherwise blank glass. Body diffs painted; the intro's pixels vanished.

**Root cause:** every loop intro re-uploaded the LittleFoot program, and
the firmware, on (re)validating a program, WIPES its heap data area — the
wipe lands after the intro's pixel bytes, erasing them. Animated moods
repaint 8×/s so nobody ever saw it; the static QR kept only its heartbeat.
This also explains why blocksd never hits it: it uploads the program once
per connection, never on mode changes.

**Rule (now in the generator + Streamer):** the program is uploaded ONCE
after handshake ("boot" packets); loop intros sync the frame area only.
Debugging pattern worth keeping: a deliberately-blinking pixel is a
render-path witness — if the heartbeat shows and your content doesn't,
your content was erased after delivery, not dropped in transit.

Scanning reality: through the silicone weave, inverted, Micro-format, the
on-glass QR defeats stock camera apps; the companion app's zxing-cpp
scanner is the intended reader (pairing flow). Human-visible = success.
