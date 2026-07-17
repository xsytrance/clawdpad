# clawdpad — working notes for Claude

Clawd (the Claude Code mascot) living on a ROLI Lightpad Block M. Public
project (MIT); Rod's install lives in `~/claudeblock` (dir predates the
clawdpad rename — units/hooks point here, rename is cosmetic-only pending).
Sister project `~/dazzler` (same soul on a MatrixPortal S3). Read `README.md`
for the public story, `docs/PLAN.md` for history, `docs/BLOCKSD-FIXES.md`
for the protocol war stories, `docs/LEVELS.md` for where this is all going
(L0 tab → L1 daemon → L2 app → L3 integrations → L4 colony).

**Hosts own a block; controllers poke a host.** Exactly one host per block,
always. Hosts: the tab (web/), the daemon (clawdpadd.py), and the future app.
Controllers: `docs/APP.md` (phone), `docs/WEAR.md` (watch) — they talk to the
daemon's HTTP API and never touch the glass. Say which one any new thing is.

**Platforms port the transport, never the art.** A new body needs exactly one
new thing: a `send(bytes)` that reaches a block. clawd-core.js already draws
Clawd *and* speaks bit-identical ROLI (golden vectors prove it), so a native
shell writes a MIDI transport and hands bytes to the JS — it never reimplements
poses. That keeps parity.py a 2-body problem no matter how many platforms ship.
Note WebMIDI is Chromium-only: Electron has it, WKWebView (Tauri/macOS,
Capacitor/iOS) does not. See docs/LEVELS.md "the webview trap".

## Architecture (systemd --user services)

```
Claude Code hooks (~/.claude/settings.json)
  ├─ SessionStart/UserPromptSubmit/Stop/SessionEnd/Notification
  │     → ~/bin/claudebody "$@"        (fans out to BOTH bodies, never fails)
  │         ├─ ~/dazzler/claudectl     (matrix body)
  │         └─ ~/claudeblock/blockctl  (this body)
  └─ PreToolUse/PostToolUse → blockctl event-hook pre-tool|post-tool
        (energy only — Clawd paces faster; no per-tool visuals)

blockctl ──NDJSON──► clawdpadd.py (service: clawdpadd)
                       │  all-Clawd moods · touch · energy · music
                       │  socket: $XDG_RUNTIME_DIR/clawdpad/clawdpad.sock
                       │  optional HTTP :8137 + ntfy (config.json)
                       ▼  685-byte frames (0xBD 0x01 u64-uid + 675B RGB888)
                     blocksd (service: blocksd; VENDORED — blocksd/ (gitignored),
                       │       pip install -e; patches/ = shareable fixes)
                       ▼  SysEx over USB MIDI
                     Lightpad Block M (serial LPM9E1KL3HO9XC5G)
```

## Iron rules

- **blocksd must always run** — the block powers off without its keepalive.
  After a host reboot someone must press the block's power button.
- **blocksd is installed editable from `blocksd/`** (a gitignored clone of
  hyperb1iss/blocksd at the repo root — *not* `vendor/`, which is stale in old
  notes; three commits on `main`, exported to `patches/`). Never
  `pip install -U blocksd`. Edit blocksd/ → `systemctl --user restart blocksd`.
- **Never run `blocksd led ...` CLI while the daemon runs.**
- Frame "acks" ≠ pixels rendered. Device-side LittleFoot faults only show
  with `blocksd run --verbose` ("Device N log: Illegal instruction").
- **Sprites must be solid chunky shapes** — the woven surface diffuses thin
  1-px rays into disconnected dots ("creepy spider" incident, 2026-07-15).
- **Everything on the glass is Clawd's body language.** No abstract effects
  (vortex/ripples/rings/glyph cards were built and deliberately removed at
  Rod's request). New feelings = new poses/gaits for `_clawd()`.
- **One soul, two bodies**: `~/dazzler/state.json` is owned by dazzler's
  petd.py. pet_loop mirrors it READ-ONLY; never write it, never fork a pet.
- Touch events on the wire use field `index` (docs say `touch_index`).
- xsyprime isn't in the `audio` group: blocksd MIDI scans fail between boot
  and console login (self-heals; fix: `sudo usermod -aG audio xsyprime`).

## Daily commands

```bash
printf '{"cmd":"subscribe"}\n' | nc -U /tmp/clawdpad/clawdpad.sock   # watch him
./blockctl status                # mood · block · energy · soul · sessions
./blockctl mode awake            # summon Clawd (sticky until next prompt)
./blockctl say "hi" -t 60        # notify: wave + chime; tap to ack
./blockctl anim celebrate        # jump, arms up (+ jingle, rate-limited)
./blockctl play jingle           # sound + jump  (also: hello, chime)
./blockctl hum on                # quiet pad while thinking
journalctl --user -u clawdpadd -f
systemctl --user restart clawdpadd    # after editing clawdpadd.py
```

Secrets/config: `~/.config/clawdpad/config.json` (0600). Restarting
clawdpadd re-binds :8137 — the permission classifier may require Rod to run
that restart himself.

## Code map

- `clawdpadd.py` — the daemon, one stdlib-only file. Threads: render loop
  (owns the frame stream, reconnects forever), touch loop, command server,
  pet/hum loops, optional HTTP + ntfy. `State` under one lock.
  **`State.emit()` has its own `subs_lock`** — `self.lock` is non-reentrant and
  emit is called from inside locked sections (`touch_end`); sharing it would
  deadlock the touch loop. Subscribers drop events when slow; nothing an
  integration does may stall the render loop. `{"cmd":"subscribe"}` /
  SSE `GET /events` are the outbound stream — `notify`→`ack` is the loop
  integrations live on (see docs/MANUAL.md §7b). `_clawd()`
  renders the icon (CLAWD_BODY/ARMS/LEGS/EYES consts, scaled from the
  official SVG rects via dazzler's make_clawd.py); frame_* compose poses.
  Energy (tau 25 s) drives a phase accumulator → pacing speed (never
  multiply t by a time-varying speed — it jumps).
- `blockctl` — stdlib CLI, claudectl-compatible, silent exit 0 when the
  daemon is absent. Test/fail regexes for post-tool energy live here.
- `patches/` — the three blocksd fixes as git am-able patches (for sharing
  and the upstream PR). 0003 is macOS-only: CoreMIDI names every block
  identically, so keying device groups by port name drops the second one
  (`docs/BLOCKSD-FIXES.md`). Two blocks on a Mac need it.
- `systemd/` — portable unit templates (%h paths).
- `web/` — the zero-install host: `index.html` + `clawd-core.js` (Clawd's
  poses in JS, `TopologyDecoder`, `HeapStreamer`) drive a block straight from
  a Chrome tab over WebMIDI — USB *or* Bluetooth, no daemon. `qr-data.js` is
  GENERATED (tools/make_web_qr.py). Buttons must act **locally first, then**
  call `remoteCmd` — a remote-only button is a silent no-op while the tab is
  the host, which is how chibi/QR/size shipped broken.
- **`web/clawd-core.js` is CANONICAL for Clawd's art and poses.** Author a pose
  or costume there first, then mirror into `clawdpadd.py`/`costumes.py`. Never
  the reverse. Until 2026-07-17 the two files each named the *other* as source
  of truth, which meant drift had no reference to resolve against — and drift
  had already shipped (a costumed Clawd could wave in the browser but not on
  the desk). One arrow, one direction, forever.
- **`blocksd` is CANONICAL for the protocol** — the opposite direction. The
  daemon emits frames to blocksd; clawd-core.js reimplements the ROLI stack for
  WebMIDI because a browser can't dial a Unix socket. That replica is kept
  honest by golden vectors, not by sharing code. Run `tools/check.sh`.
- **Never hardcode a block's device index.** Blocks report their own topology
  index and they differ (XC5G=9, SH8T=32). Ask via topology; see
  docs/MACBOOK.md Phase 2 for the evening this cost.
- `tools/` — firstlight.py, paint.py, touchtest.py (protocol references);
  `wireprobe.py` (what a block says back: serial, topology, real device index,
  device logs — stop blocksd first); `webpreview.mjs` (render web poses as
  ASCII, no browser); `make_web_qr.py` (bake QR matrices with segno).

## Testing without hardware eyes

Claude cannot see the glass. For sprite/animation work, preview frames as
ASCII before shipping:

```python
import clawdpadd
buf = clawdpadd.frame_awake(1.0)   # or any frame_*
# (y*15+x)*3 indexes RGB; map luminance to . + #
```

For the web page the equivalent is `node tools/webpreview.mjs` (any pose,
full or mini, no browser needed).

**`tools/check.sh` is the whole no-hardware safety net** — golden vectors
(clawd-core.js speaks bit-identical ROLI to blocksd), cross-body parity
(`tools/parity.py`: 28 poses, byte-identical on desk and browser), every pose
renders, imports clean. Run it before claiming anything works. It found five
shipped drift bugs the day it was written; see `docs/POSES.md`.

`blockctl status`, the clawdpadd journal, and blocksd `--verbose` device
logs are the observables; for anything visual, ask Rod to look. **Beware
`blockctl status`/`names`: they read clawdpadd's cache, not the hardware** —
a phantom block once persisted there for an hour after it was gone. Ground
truth is blocksd's `discover` over its socket, or `tools/wireprobe.py`. Sessions
named `hermes360`/`dazzler` in `blockctl sessions` are Rod's other live
Claude sessions — real traffic, not test data.
