# clawdpad — working notes for Claude

Clawd (the Claude Code mascot) living on a ROLI Lightpad Block M. Public
project (MIT); Rod's install lives in `~/claudeblock` (dir predates the
clawdpad rename — units/hooks point here, rename is cosmetic-only pending).
Sister project `~/dazzler` (same soul on a MatrixPortal S3). Read `README.md`
for the public story, `docs/PLAN.md` for history, `docs/BLOCKSD-FIXES.md`
for the protocol war stories.

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
                     blocksd (service: blocksd; VENDORED — vendor/blocksd,
                       │       pip install -e; patches/ = shareable fixes)
                       ▼  SysEx over USB MIDI
                     Lightpad Block M (serial LPM9E1KL3HO9XC5G)
```

## Iron rules

- **blocksd must always run** — the block powers off without its keepalive.
  After a host reboot someone must press the block's power button.
- **blocksd is installed editable from `vendor/blocksd`** (branch
  `fix/littlefoot-jump-base`, two commits, exported to `patches/`). Never
  `pip install -U blocksd`. Edit vendor → `systemctl --user restart blocksd`.
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
  pet/hum loops, optional HTTP + ntfy. `State` under one lock. `_clawd()`
  renders the icon (CLAWD_BODY/ARMS/LEGS/EYES consts, scaled from the
  official SVG rects via dazzler's make_clawd.py); frame_* compose poses.
  Energy (tau 25 s) drives a phase accumulator → pacing speed (never
  multiply t by a time-varying speed — it jumps).
- `blockctl` — stdlib CLI, claudectl-compatible, silent exit 0 when the
  daemon is absent. Test/fail regexes for post-tool energy live here.
- `patches/` — the two blocksd fixes as git am-able patches (for sharing
  and the upstream PR).
- `systemd/` — portable unit templates (%h paths).
- `tools/` — firstlight.py, paint.py, touchtest.py (protocol references).

## Testing without hardware eyes

Claude cannot see the glass. For sprite/animation work, preview frames as
ASCII before shipping:

```python
import clawdpadd
buf = clawdpadd.frame_awake(1.0)   # or any frame_*
# (y*15+x)*3 indexes RGB; map luminance to . + #
```

`blockctl status`, the clawdpadd journal, and blocksd `--verbose` device
logs are the observables; for anything visual, ask Rod to look. Sessions
named `hermes360`/`dazzler` in `blockctl sessions` are Rod's other live
Claude sessions — real traffic, not test data.
