# claudeblock — working notes for Claude

Claude's second body: a ROLI Lightpad Block M (15×15 RGB, 4D touch, USB-C).
Sister project to `~/dazzler`; both bodies are driven by the same Claude Code
hooks via `~/bin/claudebody`. Read `README.md` for status, `docs/PLAN.md` for
the roadmap, `docs/BLOCKSD-FIXES.md` for the hard-won protocol debugging story.

## Architecture (all running as systemd --user services)

```
Claude Code hooks (~/.claude/settings.json)
  ├─ SessionStart/UserPromptSubmit/Stop/SessionEnd/Notification
  │     → ~/bin/claudebody "$@"        (fans out to BOTH bodies, never fails)
  │         ├─ ~/dazzler/claudectl     (matrix body)
  │         └─ ~/claudeblock/blockctl  (this body)
  └─ PreToolUse/PostToolUse → blockctl event-hook pre-tool|post-tool  (block-only)

blockctl ──NDJSON──► claudeblockd.py (service: claudeblockd)
                       │  moods · overlays · energy · touch · glyphs
                       │  + HTTP :8137 (Bearer token) + ntfy.sh subscription
                       ▼  685-byte binary frames (0xBD 0x01 u64-uid + 675B RGB888)
                     blocksd (service: blocksd; VENDORED — vendor/blocksd,
                       │       pip install -e; NOT the PyPI copy)
                       ▼  SysEx over USB MIDI
                     Lightpad Block M (serial LPM9E1KL3HO9XC5G)
```

## Iron rules

- **blocksd must always run** — the block powers itself off without its
  keepalive. After a host reboot someone must press the block's power button.
- **blocksd is installed editable from `vendor/blocksd`** which carries two
  local fixes (assembler jump-base bug + LED program upload — see
  docs/BLOCKSD-FIXES.md). Never `pip install -U blocksd`; edit vendor and
  `systemctl --user restart blocksd`.
- **Never run `blocksd led ...` CLI while the daemon runs** (spawns a second
  competing API-mode host).
- Frame "acks" from the blocksd socket ≠ pixels rendered. Device-side
  LittleFoot faults only show with `blocksd run --verbose`
  (`Device N log: Illegal instruction`).
- blocksd needs `/dev/snd/seq`; xsyprime isn't in the `audio` group, so scans
  fail with "Permission denied" between boot and console login (harmless,
  self-heals; permanent fix: `sudo usermod -aG audio xsyprime`).
- Touch events on the wire use field `index` (docs say `touch_index`).
- **One soul, two bodies**: Clawd's pet state (`~/dazzler/state.json`) is
  owned by dazzler's petd.py. claudeblockd mirrors it READ-ONLY (pet_loop) —
  never write it, never fork a second pet. Feeding happens in
  `~/dazzler/feed/`; care sessions live in dazzler (care-prompt.md, which
  whispers through claudebody so both bodies speak).

## Daily commands

```bash
./blockctl status                # mood · block · energy · sessions
./blockctl mode thinking         # manual mood (hooks reclaim control)
./blockctl say "hi" -t 60        # notify ring; tap block to ack
./blockctl anim celebrate        # fireworks
./blockctl glyph battery         # info card (double-tap does this too)
./blockctl play jingle           # sound + celebrate light (also: hello, chime)
./blockctl hum on                # quiet pad while thinking (off by default)
./blockctl clear
journalctl --user -u claudeblockd -f
systemctl --user restart claudeblockd   # after editing claudeblockd.py
```

Remote: HTTP `POST http://<lan-or-tailscale>:8137/` with
`Authorization: Bearer <token>`, or publish JSON (with `"token"` field) to the
secret ntfy.sh topic — secrets in `~/.config/claudeblock/config.json` (0600).
Recipes: docs/PHONE-WATCH.md. Restarting claudeblockd re-binds :8137; the
permission classifier may require Rod to run that restart himself.

## Code map

- `claudeblockd.py` — the presence engine. One file on purpose. Threads:
  render loop (owns blocksd frame stream, reconnects forever), touch loop,
  Unix-socket command server, HTTP server, ntfy long-poll. `State` holds
  everything under one lock. Moods render procedurally at 20 fps (sleep 8);
  one-shot overlays (ripple/wave/flash) composite additively over any mood;
  `energy` (tau 25 s) scales vortex speed via a phase accumulator (never
  multiply t by a time-varying speed — it jumps).
- `blockctl` — stdlib-only client, claudectl-compatible vocabulary, exits 0
  silently when the daemon is absent (hooks must never fail). Tool-class
  ripple palette + test/fail regexes live here.
- `tools/` — firstlight.py (hello-world streamer), paint.py (touch demo),
  touchtest.py. Good protocol references.
- `vendor/blocksd` — vendored dependency with local fixes; has its own
  CLAUDE.md with the full SysEx protocol reference.

## Testing without hardware eyes

Claude cannot see the glass. `blockctl status`, claudeblockd journal, and
blocksd `--verbose` device logs are the observables; for anything visual, ask
Rod to look. For sprite/animation work, preview frames as ASCII before
shipping — import claudeblockd, call a frame function, and print a 15×15
brightness grid (see the Clawd redesign session for the pattern):

```python
buf = claudeblockd.frame_awake(1.0)
# (y*15+x)*3 indexes RGB; map luminance to . - + # and EYE color to @
``` The `hermes360`/`dazzler` sessions appearing in `blockctl
sessions` are Rod's other live Claude sessions — real traffic, not test data.
