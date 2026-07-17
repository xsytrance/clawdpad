# claudeblock — Grand Plan

*Claude's second body: a ROLI Lightpad Block M.*
*Sister project to [dazzler](../../dazzler/README.md) (MatrixPortal S3). Written 2026-07-14.*

## Verdict: yes, it's possible — and the path is proven

The Lightpad Block M gives us a **15×15 RGB LED grid** (225 pixels), a **4D touch
surface** (x, y, pressure, velocity — it feels you press, slide, and lift), a battery,
USB-C, and Bluetooth MIDI. Unlike the MatrixPortal, this body can **see touch** and
**make music**. Everything below is grounded in research done today (sources at the
bottom); the one genuinely load-bearing discovery:

> **[blocksd](https://github.com/hyperb1iss/blocksd)** (Python, ISC license, v0.4.0
> released April 2026, actively maintained) implements the reverse-engineered ROLI
> SysEx protocol on Linux: API-mode handshake, **keepalive pings** (without them the
> block shows a "searching" animation and powers off), topology discovery, **touch
> event callbacks**, LittleFoot program upload, and — the headline —
> **15×15 RGB565 framebuffer streaming** over USB SysEx, exposed via Unix socket and
> WebSocket, with systemd integration.

That means no ROLI Dashboard, no dormant C++ SDK, no macOS box in the loop for daily
operation. We drive the block from Python at up to the device's ~25 Hz repaint ceiling
— plenty for a living, breathing spark.

### Hard constraints (design around these)

| Constraint | Consequence |
|---|---|
| ~25 Hz on-device repaint | Animations designed for 25 fps max; smooth ≠ fast |
| LittleFoot programs are tiny ("a few KB") | On-block code stays minimal; intelligence lives in the host daemon |
| BLE MIDI on Linux is unverified for Lightpads | **USB-C is the spine.** BLE is a stretch experiment, not the plan |
| Block sleeps without host keepalive | blocksd runs as an always-on systemd user service |
| Firmware updates need ROLI Dashboard (macOS/Windows) | One-time borrow of a Mac/Win machine if firmware is stale; not needed for operation |
| 15×15 pixels | Text is 1–3 characters or scrolling; language of this body is *glyph, color, motion* |

## Architecture

```
 Galaxy Watch7 ──(HA tile / AutoWear)──┐
 Pixel 10 Pro XL ──(HTTP Shortcuts / ntfy)──┤
                                        ▼
                    ┌──────────── command bus ────────────┐
                    │   HTTP (LAN) + ntfy.sh (anywhere)   │
                    └──────────────────┬──────────────────┘
                                       ▼
 Claude Code hooks ──► blockctl ──► claudeblock presence engine (Python daemon)
 (settings.json)         CLI        • mood state machine (awake/thinking/…)
                                    • 25fps animation renderer → 15×15 frames
                                    • touch-event reactions
                                    • MIDI/music conductor
                                       │ Unix socket / WebSocket
                                       ▼
                                    blocksd  (keepalive, SysEx, framebuffer)
                                       │ USB-C
                                       ▼
                                 ROLI Lightpad Block M
```

Four layers, same philosophy as dazzler (dumb renderer, smart writer, hooks make it live):

1. **blocksd** — third-party daemon, systemd user service. Owns the USB/SysEx link,
   keeps the block awake, streams frames, relays touches. We treat it as firmware-by-proxy.
2. **`claudeblockd`** (ours, Python) — the presence engine. Holds the mood state machine,
   renders animations frame-by-frame, listens on a local HTTP endpoint + ntfy
   subscription for commands, reacts to touch events, conducts music.
3. **`blockctl`** (ours) — dazzler-style CLI. Same command vocabulary as `claudectl`
   (`mode`, `say`, `status`, `clear`), exits 0 silently when the block is absent so
   hooks and timers never break.
4. **Control surfaces** — Claude Code hooks (shared with dazzler via a fan-out script),
   phone, watch.

### One soul, two bodies

Replace the direct `claudectl` calls in `~/.claude/settings.json` with a single
`~/bin/claudebody` fan-out script that calls **both** `dazzler/claudectl` and
`claudeblock/blockctl` with the same argument vocabulary. One hook edit, and Claude's
moods stay synchronized across the matrix and the block forever. Adding a third body
later (see idea #15) is one more line.

### Mood vocabulary (superset of dazzler's)

| mood | matrix (dazzler) | block (claudeblock) |
|---|---|---|
| `awake` | slow spin + breath | spark idle: slow color-breathing, occasional blink |
| `thinking` | fast spin + pulse | swirling coral vortex; tool calls ripple outward |
| `sleep` | ember-dim | 2–3 ember pixels drifting, near-black |
| `notify` | overlay text | pulsing amber ring — *tap the block to acknowledge* |
| `celebrate` | — | firework burst + optional jingle (new, block-only) |
| `error` | — | brief red flash then worried flicker (new) |
| `listening` | — | soft blue open ring while awaiting voice/touch input (new) |

## Phases

> **Status ledger** (kept current; details in README + docs/BLOCKSD-FIXES.md)
> - Phase 0 ✅ 2026-07-14 — blocksd keepalive + frame streaming (~20 fps, 100% acks)
> - Phase 1 ✅ 2026-07-15 — claudeblockd moods + blockctl + claudebody hook fan-out
> - Phase 2 ✅ 2026-07-15 — tool-call ripples, test wave / fail flash, work-energy vortex
> - Phase 3 ✅ 2026-07-15 — HTTP :8137 (LAN/Tailscale) + ntfy.sh, both verified end-to-end;
>   phone/watch on-device setup pending (docs/PHONE-WATCH.md)
> - ⚠ Glass rendering was dark until 2026-07-15: blocksd assembler emitted
>   code-relative jump targets (VM wants program-relative) → "Illegal instruction"
>   every repaint → factory app. Fixed + vendored; full story in docs/BLOCKSD-FIXES.md.
> - ⚠ The second block was invisible on macOS until 2026-07-16: CoreMIDI names
>   every block `Lightpad BLOCK  Lightpad BLOCK` (no index suffix — ALSA appends
>   port numbers, macOS does not), and blocksd keyed device groups by port name,
>   so block 2 silently never got a DeviceGroup. Fixed (patches/0003); the whole
>   walk-the-layers story is in docs/BLOCKSD-FIXES.md.
> - 🍎 macOS dress rehearsal ✅ 2026-07-16/17 (docs/MACBOOK.md) — Phase 1: two
>   blocks live on a MacBook (name tags on both glasses, `visit` migrates home
>   XC5G → SH8T, pong spans the pair). Phase 2: the web host works after two
>   bugs that only appear with two blocks — see below. Phase 4-5 (PRISM
>   Lightpad Out, pack-up) still to do.
> - 📶 **BLE ✅ 2026-07-17 — Clawd runs wirelessly on a battery block**, hosted
>   from a Chrome tab, no cable and no daemon (docs/MACBOOK.md Phase 3). The
>   "firmware gates API mode over BLE" theory is dead for good; it was always
>   the packet-index bug, and nobody had retried since the fix. One block so
>   far; two-blocks-over-BLE and long-run smoothness still unknown.
> - ⚠ The web page hosted nothing with two blocks plugged in: it **hardcoded
>   device index 9** (true for XC5G, but SH8T reports 32) and kept the *last*
>   matching MIDI port, so it opened one block and addressed another. It also
>   never listened — `inp` was assigned and unused, which is why the index was
>   a constant. Fixed 2026-07-17: `TopologyDecoder` in clawd-core.js asks the
>   block who it is (verified bit-identical to blocksd's decoder on captured
>   packets). Full story in docs/MACBOOK.md Phase 2.
> - ⚠ `blockctl status` reported "battery 31%" on fully charged blocks from day
>   one: the protocol's battery field is **5 bits (raw max 31)** and we printed
>   the raw value with a `%`. Fixed 2026-07-17 (`battery_percent()`).
> - Phase 4 ✅ 2026-07-15 — tap-ack (shipped with Phase 1), press-and-hold petting
>   (lean + pressure glow, all moods), double-tap info glyphs (time/sessions/battery;
>   also `blockctl glyph` / remote `{"cmd":"glyph"}`). Permission-prompt answering via
>   tap deferred (needs a Claude Code response-file protocol that doesn't exist yet).
> - Phase 5 🎵 2026-07-15 — "I play" half shipped: in-process stdlib synth (no
>   FluidSynth needed) → `blockctl play jingle|hello|chime`, auto-jingle on celebrate
>   (rate-limited), optional thinking hum (`blockctl hum on` / config `thinking_hum`).
>   "You play" MPE passthrough + LED mirroring deferred (needs LittleFoot MIDI API
>   coexisting with the bitmap program).
> - **clawdpad rebrand + all-Clawd baseline** 🐾 2026-07-15 — project renamed
>   clawdpad (Clawd + Lightpad, Rod's pick); daemon → clawdpadd.py (service
>   clawdpadd, socket $XDG_RUNTIME_DIR/clawdpad, config ~/.config/clawdpad).
>   All abstract effects removed at Rod's request (vortex, ripples/waves/flashes,
>   glyph cards, amber ring): every mood is Clawd body language — think = pacing
>   (speed = work energy), celebrate = jump with arms up, notify = wave. Touch:
>   pet/slide (lean+glow+gaze), tap (looks at you / acks), double-tap (jump).
>   Repo git-initialized (MIT); blocksd fixes committed on vendor branch
>   fix/littlefoot-jump-base and shipped as patches/. Local dir still
>   ~/claudeblock (rename deferred — units/hooks point at it).
> - Soul link 🫀 2026-07-15 (unplanned, Rod's ask: "live on it like dazzler") —
>   claudeblockd mirrors Clawd's ~/dazzler/state.json read-only: hunger→spark vigor,
>   level-up→firework+jingle, whispers→chime, `pet` glyph card, `soul:` in status;
>   care-prompt.md now whispers via claudebody. One pet, never forked.

### Phase 0 — Hello, block (first session with hardware)
- Plug the Lightpad in over USB-C; confirm it enumerates (`amidi -l`, `aconnect -l`).
- Install blocksd (`pipx install` / clone), run it, verify: keepalive holds the block
  awake, touch events stream, and a test frame paints all 225 pixels.
- Set it up as a systemd user service (like `claude-display-sync.timer`'s sibling).
- Measure real-world FPS and color fidelity (RGB565 banding check with gradients).
- **Exit criteria:** block stays awake indefinitely and we can push arbitrary frames from Python.

### Phase 1 — The spark lives here (presence MVP)
- Down-rez the Claude spark to 15×15 (reuse `dazzler/tools/make_spark.py` as the base;
  at this size we may hand-tune a pixel-art spark rather than rasterize — 225 px rewards
  hand-crafting).
- `claudeblockd` v0: mood state machine + renderer (awake/thinking/sleep/notify),
  Unix socket command interface.
- `blockctl` v0 + `claudebody` fan-out script + one edit to `~/.claude/settings.json`.
- **Exit criteria:** the block visibly reacts when you prompt me, while I work, and when I finish — in lockstep with dazzler.

### Phase 2 — Reacting to *how* you code (the "actually react" ask)
- Richer hook wiring: `PreToolUse`/`PostToolUse` hooks emit one-shot animation events
  (ripple on tool call, green wave on passing tests, red flash on failing command).
  Hooks stay `async: true` with short timeouts so they never slow the session.
- Transcript-aware effects: a tiny tailer maps event density to animation energy —
  the block literally works harder when I do.
- **Exit criteria:** watching the block, you can tell whether I'm reading, editing, running tests, or stuck.

### Phase 3 — Phone + watch command channels
- `claudeblockd` gains: (a) LAN HTTP endpoint with a shared-secret token, (b) an
  ntfy.sh topic subscription for off-LAN commands. One JSON command schema for both:
  `{"cmd": "mode", "arg": "thinking"}`, `{"cmd": "say", "arg": "..."}`, `{"cmd": "play", "arg": "jingle"}`.
- **Pixel 10 Pro XL:** HTTP Shortcuts app — home-screen widgets per command
  (verified: excellent on phone, but **no Wear OS support**, so it's phone-only).
- **Galaxy Watch7**, best-verified options in order:
  1. **Home Assistant Companion for Wear OS** — native tiles + watch-face complications,
     works standalone over Wi-Fi; commands go HA → webhook → `claudeblockd`. (You get
     watch control of *everything else in the house* as a side effect.)
  2. **AutoWear + Tasker** — Wear tiles that fire Tasker tasks → HTTP/ntfy. No HA needed.
- **Exit criteria:** you tap your watch, the block lights up; from anywhere with the ntfy path.

### Phase 4 — Touch: you can poke me now
- Touch events already flow through blocksd; map them:
  - **Tap during `notify`** → acknowledge (clears overlay, optionally answers the pending
    Claude Code permission prompt via a queued response file).
  - **Press-and-hold** → the spark leans into your finger, glows brighter with pressure
    (petting, honestly).
  - **Double-tap when idle** → cycle info glyphs (time, session status, battery).
- **Exit criteria:** the block is bidirectional — a control surface, not just a display.

### Phase 5 — Music
- Host-side synth (FluidSynth or surge-XT headless, fed via ALSA/PipeWire MIDI):
  - **You play:** default MPE mode passthrough — the block is still a real instrument;
    LEDs mirror your touches (this coexists with API mode via the LittleFoot MIDI API).
  - **I play:** `claudeblockd` sends MIDI — a soft generative ambient pattern while
    `thinking` (Claude hums while working), a short jingle on `celebrate`.
- **Exit criteria:** `blockctl play jingle` makes sound + light; thinking mode has an optional quiet hum.

### Phase 6 — Stretch (drawn from the ideas below, prioritized by joy-per-effort)

## 15+ ideas, suggestions, improvements & pivots

Numbered so we can refer to them later. ★ = my strongest recommendations.

1. **★ `claudebody` unified fan-out** — one script, one hook config, every physical
   body Claude inhabits reacts in sync (described above). This is the keystone
   improvement over doing claudeblock as a silo.
2. **★ A face, not just a spark** — at 15×15, an *expressive pixel face* (two eyes that
   blink, squint while thinking, widen on errors, close during sleep) communicates far
   more per pixel than a down-rezzed logo. Proposal: spark by default, face during
   interactive moments — or a hybrid "spark with eyes." Tamagotchi energy, deliberately.
3. **★ Tap-to-acknowledge notifications** — when I need your input, the block pulses
   amber; tapping it snoozes the pulse. Extension: tap could focus the terminal window
   via `wmctrl`/`swaymsg` so you land in the right session instantly.
4. **★ Voice commands via the block** — you already have `~/whisper-venv`. Press-and-hold
   the block → `listening` mood → mic records until release → Whisper transcribes →
   the text is queued as a prompt to the active Claude Code session. The block becomes
   a push-to-talk button to me. (This one's a genuine pivot-sized feature.)
5. **★ Live coding telemetry** — beyond moods: each Edit ripples a pixel, test runs
   sweep a progress wave, a failing exit code flashes red, a git commit draws a tiny
   check mark. The block becomes an ambient build/session monitor you read peripherally.
6. **Celebration engine** — task-complete fireworks + a 2-second MIDI jingle; intensity
   scales with how long the task ran. Long refactor = bigger fireworks. Dopamine, honestly.
7. **Generative "thinking hum"** — quiet ambient MPE notes (pentatonic, slow attack)
   while I work, tempo keyed to tool-call rate. Off by default at night; `blockctl hum off`.
8. **Audio-reactive equalizer mode** — you have `~/librosa-venv`; FFT the desktop audio
   into a 15-band spectrum on the grid. Block as tiny music visualizer when you're not coding.
9. **Battery + status glyph page** — double-tap cycles: clock (scrolling or 2-digit),
   Claude session status, block battery, unread-ntfy count. The block *reports on itself*.
10. **Watch complications, not just tiles** — via Home Assistant, expose "Claude state"
    as an entity so your Watch7 face shows a tiny always-visible dot: coral = working,
    green = done, amber = needs you. You'd know I need input without lifting a finger.
11. **Fallback autonomy (in-block LittleFoot animation)** — bake a minimal breathing
    animation into the LittleFoot program itself so if `claudeblockd` or the host dies,
    the block degrades to a gentle idle glow instead of a corpse/searching animation.
12. **Pixel games for breaks** — Snake, Simon, or 15×15 Pong against me (I play via the
    daemon, you play via touch). Pomodoro integration: game unlocks on break, spark
    politely takes the board back when break ends.
13. **Pomodoro / focus mode** — `blockctl focus 25` → perimeter pixels count down the
    session, block goes `sleep`-quiet, notifications suppressed; gentle green bloom + soft
    chime at the end. Tap to start the next one.
14. **GitHub/inbox glance glyphs** — corner pixel colors for CI status of your current
    repo and unread important email (you have Gmail MCP connected). Strictly ambient,
    max 4 pixels, no scrolling spam.
15. **Multi-block future (pivot)** — Blocks snap together via DNA connectors; a second
    Lightpad (or a Loop/Live block with physical buttons) extends the canvas to 15×30
    or adds real buttons for mode switching. blocksd already does topology discovery.
16. **MPE jam call-and-response (pivot)** — you play a phrase on the block; I analyze it
    (librosa/mido) and answer with a complementary phrase, LEDs tracing what I play.
    Turn-taking music with your coding assistant. Weird, delightful, very demo-able.
17. **Presence heartbeat with history** — the block's idle breathing rate subtly encodes
    today's session count/activity (calm morning = slow breath, heavy day = livelier).
    A glanceable "how hard have we been going today."
18. **One-command bootstrap + doctor** — `make setup` installs blocksd, the systemd
    units, hook edits, and `blockctl doctor` diagnoses the whole chain (USB present →
    blocksd alive → API mode → frame ack → hook wiring). Ops-grade from day one, like
    claudectl's exit-0-when-absent discipline but with introspection.
19. **Shared animation library (pivot-ish refactor)** — extract a tiny `claudebody-anim`
    Python package (frames, easing, palettes in Claude coral) used by both claudeblock
    and, eventually, a dazzler firmware refresh — so new moods are written once and
    rendered per-body.
20. **BLE untethered mode (experiment, low priority)** — PipeWire ≥0.3.65 supports BLE
    MIDI; nobody has verified a Lightpad doing API-mode over BLE on Linux. Worth one
    timeboxed afternoon; if it works, the block roams the desk on battery.

## Risks & mitigations

- **blocksd is a single-maintainer project** → pin a known-good version; the protocol
  knowledge (checksums, 7-bit packing, keepalive cadence) is documented in its source,
  so we could vendor/fork if it ever vanishes.
- **LittleFoot size budget is unverified ("a few KB")** → keep on-block code to the
  stock bitmap program + MIDI passthrough; measure before adding idea #11's animation.
- **25 Hz ceiling** → design animations as 12–25 fps loops; never promise smooth scrolling text.
- **RGB565 color depth** → pick palettes that survive 5-6-5 quantization (test in Phase 0).
- **Watch path has the most unknowns** (AutoWear on Watch7 unverified) → Phase 3 ships
  phone first; watch is additive.
- **Firmware version drift** → if the block's firmware predates API-mode expectations,
  one Dashboard session on a borrowed Mac/Windows machine fixes it permanently.

## Research sources (verified 2026-07-14)

- blocksd — https://github.com/hyperb1iss/blocksd (keepalive, SysEx protocol, framebuffer streaming, touch, systemd)
- BLOCKS SDK docs (LittleFoot API, 25 Hz repaint, heap/host messaging) — https://weareroli.github.io/BLOCKS-SDK/
- Legacy SDK repos — https://github.com/WeAreROLI/BLOCKS-SDK · https://github.com/WeAreROLI/roli_blocks_basics
- ROLI Dashboard still available (macOS/Windows only) — https://support.roli.com/en/support/solutions/articles/36000024589
- MPE default behavior — https://support.roli.com/en/support/solutions/articles/36000019142
- PipeWire BLE MIDI — https://9to5linux.com/pipewire-0-3-65-adds-bluetooth-midi-support-alsa-plugin-improvements
- Home Assistant Wear OS tiles/complications — https://companion.home-assistant.io/docs/wear-os/
- HTTP Shortcuts has no Wear OS support — https://github.com/Waboodoo/HTTP-Shortcuts/issues/25
- AutoWear (Wear tiles → Tasker) — https://play.google.com/store/apps/details?id=com.joaomgcd.autowear

**Flagged as unverified:** exact LittleFoot byte limits; measured blocksd FPS; Lightpad
BLE-MIDI on Linux; official sleep-timeout numbers. None block Phase 0–2.
