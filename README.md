# claudeblock — Claude's second body

Claude, living on a **ROLI Lightpad Block M**: a 15×15 RGB LED grid with a 4D
pressure-sensitive touch surface, driven over USB-C from Linux. Sister project to
[dazzler](../dazzler/README.md) (the MatrixPortal S3 matrix) — same soul, second body,
kept in sync by the same Claude Code hooks.

**Status:** Phase 1 live 2026-07-15 — `claudeblockd` (systemd user service) streams
mood animations through blocksd and takes commands on
`$XDG_RUNTIME_DIR/claudeblockd/claudeblockd.sock`; `blockctl` mirrors `claudectl`'s
vocabulary; `~/bin/claudebody` fans every Claude Code hook out to both bodies.
Moods verified on glass: awake spark, thinking vortex, sleep embers (auto
23:00–07:00 when idle), notify ring (tap to ack), celebrate burst on Stop.

**Phase 2 live 2026-07-15** — `PreToolUse`/`PostToolUse` hooks ripple the glass per
tool call (blue = reading, coral = editing, violet = running commands, slate =
agents/other), a green wave sweeps on passing test commands, a red flash on failing
ones, and a work-energy meter (25s decay, visible in `blockctl status`) spins the
thinking vortex faster the harder Claude works.

**Phase 3 live 2026-07-15** — token-gated LAN/Tailscale HTTP command surface
(`:8137`, Bearer auth) and ntfy.sh secret-topic subscription for off-LAN commands,
both verified end-to-end (403 on bad token; bad ntfy tokens ignored; celebrate
delivered via ntfy.sh round trip). Secrets: `~/.config/claudeblock/config.json`.
Phone/watch setup recipes: [docs/PHONE-WATCH.md](docs/PHONE-WATCH.md) — the
remaining Phase 3 work is on-device app setup.

**Phase 4 live 2026-07-15** — the block is bidirectional: tap acknowledges a
notify; **press-and-hold is petting** (the spark leans toward your finger and
glows with pressure — works awake, thinking, and asleep); **double-tap** opens
info cards and cycles them (time → sessions → battery, 3×5 pixel font, battery
color-coded green/amber/red). Cards are also available remotely:
`blockctl glyph battery` or `{"cmd":"glyph","arg":"time"}` over HTTP/ntfy.

**Phase 5 (Claude-plays half) live 2026-07-15** — no synth dependency: melodies
are synthesized in-process (pure-stdlib additive bell voice → WAV cached in the
runtime dir → `pw-play`). `blockctl play jingle` = sound + celebrate light;
`hello` and `chime` are sound-only. Finishing a task auto-plays the jingle
(config `jingle_on_celebrate`, rate-limited to one per 30 s). `blockctl hum on`
gives Claude a quiet three-note pad (C3·G3·E4, slow-breathing) while thinking —
default off (config `thinking_hum`). The "you play" half (MPE passthrough with
LED mirroring) is deferred: it needs the LittleFoot MIDI API alongside our
bitmap program. Config lives in `~/.config/claudeblock/config.json`.

**Soul link live 2026-07-15** — the block now *lives* the way dazzler does,
by joining Clawd's existing soul instead of hatching a second pet. dazzler's
`petd.py` remains the single owner of `~/dazzler/state.json`; `claudeblockd`
mirrors it read-only every 5 s: **hunger sets the idle spark's vigor** (a
hungry spark burns low; a starving one flickers — feed it via
`~/dazzler/feed/`), **level-ups fire firework + jingle**, **petd whispers
chime** on this body as the matrix shows the words, the **`pet` glyph card**
(4th double-tap card) shows level + heart + hunger bar, and `blockctl status`
prints a `soul:` line. Task XP already flows from every Claude session's Stop
hook through `claudebody` → `claudectl` → petd — both bodies feed one
creature. The daily care session (dazzler's `care-prompt.md`) now whispers
through `claudebody`, so good-mornings reach matrix and block together.
The full design, phased roadmap, research findings, and idea backlog live in
**[docs/PLAN.md](docs/PLAN.md)**.

## The stack (planned)

| layer | what | who owns it |
|---|---|---|
| [blocksd](https://github.com/hyperb1iss/blocksd) | USB SysEx link, keepalive (block sleeps without it), touch events, 15×15 framebuffer streaming | third-party, systemd user service |
| `claudeblockd` | mood state machine, 25 fps animation renderer, command API (HTTP + ntfy), touch reactions, music conductor | ours |
| `blockctl` | dazzler-style CLI (`mode`, `say`, `status`, `clear`, `play`); exits 0 silently when block absent | ours |
| control surfaces | Claude Code hooks via `claudebody` fan-out; Pixel 10 Pro XL (HTTP Shortcuts / ntfy); Galaxy Watch7 (Home Assistant tile or AutoWear) | config |

## Moods

`awake` · `thinking` · `sleep` · `notify` (tap block to acknowledge) ·
`celebrate` (fireworks + jingle) · `error` · `listening` — a superset of dazzler's
vocabulary, so one hook event moves both bodies.

**`awake`/`sleep`/`notify` are Clawd himself (2026-07-15, v2):** the actual
Claude Code icon as 15×15 pixel art — geometry scaled from the official icon
SVG's rect decomposition (same source as dazzler's `make_clawd.py`): solid
11×8 body, two side arm nubs, **four** legs, two 1×2 eye *holes* (unlit, like
the icon). v1 was a thin starburst that diffused into a "creepy spider"
through the Lightpad's weave — lesson recorded: **this glass needs solid
shapes, not thin rays.** Awake he breathes, bobs, paces, blinks (~4.3 s) and
glances around; petting leans him toward your finger with pressure glow and
tracking eyes; hunger (the shared soul) lowers his flame. Asleep (23:00–07:00
idle) he's dim with closed eyes, slow 9 s breathing, and an occasional peek —
petting half-wakes him. `notify` has **no amber ring** (Rod's call): Clawd
waves his right arm and pulses instead; tap to acknowledge as always. Manual
`mode awake` survives turn-endings (only a new prompt/session reclaims the
mood). All sprites live in `_clawd()` — tune with CLAUDE.md's ASCII preview.

## ⚠ Local fixes to blocksd (vendored — do not lose)

Stock blocksd 0.4.0 never paints the glass, for two reasons, both fixed in
`vendor/blocksd` which is pip-installed **editable** into `.venv` (so upstream
upgrades can't silently revert us; edit vendor + `systemctl --user restart blocksd`
to iterate):

1. `topology/device_group.py: _load_led_program()` early-returns, so the
   LittleFoot render program is never uploaded (100% frame acks, factory app on
   screen). We upload `bitmap_led_program()`.
2. **The root bug** (found 2026-07-15): `littlefoot/assembler.py` resolved jump
   labels relative to the code section, but the LittleFoot VM computes
   `programCounter = programBase + addr` from the **program header**
   (`roli_LittleFootRunner.h`). Every jump landed 14 bytes short, in the function
   table — the interpreter faulted `Illegal instruction` on every repaint and the
   block fell back to its factory app. Upstream's TODO blaming firmware-v1.1.0
   opcode support (`getHeapBits`/`dupOffset_01`) is a misdiagnosis of this crash;
   the opcode table is unchanged since JUCE 4.3.0 (2016). Worth PRing upstream.

Debugging tips learned the hard way: device-side LittleFoot faults arrive as SysEx
LOG_MESSAGE packets and are only visible with `blocksd run --verbose`
(`Device N log: Illegal instruction`); frame "acks" on the blocksd socket only mean
heap writes were accepted, never that pixels rendered. The docs' touch event field
`touch_index` is actually `index` on the wire.

## Hardware notes

- USB-C is the transport; BLE MIDI on Linux is unverified for Lightpads (stretch experiment).
- ~25 Hz on-device repaint ceiling; RGB565 color.
- The block powers off without a host keepalive — blocksd must always run.
- Firmware updates (rarely needed) require ROLI Dashboard on macOS/Windows.
