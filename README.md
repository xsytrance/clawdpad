# clawdpad

**Clawd — the Claude Code critter — living on a ROLI Lightpad Block.**

The Lightpad Block M is a 15×15 RGB LED grid behind a pressure-sensitive
silicone surface. clawdpad puts the official Claude Code mascot on it as a
tiny desk creature: he breathes, blinks, glances around, paces while Claude
Code works, waves when Claude needs your input, jumps for joy when a task
lands, and sleeps at night. Pet him and he leans into your finger, glows
under pressure, and watches your fingertip move.

Everything on the glass is Clawd's own body language — pixel art scaled
straight from the official Claude Code icon geometry (solid body, two side
arms, four legs, two eye holes).

## What he does

| you / Claude Code | Clawd |
|---|---|
| idle | breathes, bobs, paces a little, blinks, glances around |
| you prompt Claude | paces back and forth, eyes leading the way |
| Claude works harder (tool calls) | paces faster (work-energy meter, 25 s decay) |
| Claude finishes a task | jumps with both arms up + a little jingle |
| Claude needs your input | raises an arm and waves; **tap him** to acknowledge |
| 23:00–07:00 and idle | sleeps: dim, eyes closed, slow breathing, occasional peek |
| **press / slide** | petting: leans in, glows with pressure, eyes track your finger |
| **tap** | he looks at you for a moment (or acks a pending notify) |
| **double-tap** | celebrate jump |

Optional extras: a quiet ambient hum while thinking (`blockctl hum on`),
token-gated HTTP + [ntfy.sh](https://ntfy.sh) remote control (drive him from
your phone), and a [dazzler](../dazzler/) soul link if you run the sister
project.

## Requirements

- Linux with PipeWire/ALSA, Python 3.11+
- A ROLI Lightpad Block (M) on USB-C
- [blocksd](https://github.com/hyperb1iss/blocksd) — the reverse-engineered
  ROLI Blocks daemon — **with the two fixes in [`patches/`](patches/)**
  (upstream 0.4.0 cannot render LED programs; see
  [docs/BLOCKSD-FIXES.md](docs/BLOCKSD-FIXES.md) for the whole detective
  story). Until they land upstream:

```bash
git clone https://github.com/hyperb1iss/blocksd
cd blocksd && git am ../clawdpad/patches/*.patch
```

## Install

```bash
git clone https://github.com/xsytrance/clawdpad ~/clawdpad
cd ~/clawdpad
python3 -m venv .venv
.venv/bin/pip install <path-to-patched-blocksd>

mkdir -p ~/.config/systemd/user
cp systemd/*.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now blocksd clawdpadd
```

Press the block's power button (it sleeps without a host; blocksd keeps it
awake from then on) and Clawd appears. `./blockctl status` to check on him.

Note: blocksd needs `/dev/snd/seq`; add yourself to the `audio` group
(`sudo usermod -aG audio $USER`) so it works before you log in at the
console.

## Claude Code integration (the point)

Add hooks to `~/.claude/settings.json` so Clawd lives your sessions with
you (all `async`, and blockctl exits silently when the daemon's down — hooks
never break):

```json
"hooks": {
  "SessionStart":     [{"hooks": [{"type": "command", "command": "~/clawdpad/blockctl event-hook start",  "timeout": 10, "async": true}]}],
  "UserPromptSubmit": [{"hooks": [{"type": "command", "command": "~/clawdpad/blockctl event-hook prompt", "timeout": 10, "async": true}]}],
  "Stop":             [{"hooks": [{"type": "command", "command": "~/clawdpad/blockctl event-hook stop",   "timeout": 10, "async": true}]}],
  "SessionEnd":       [{"hooks": [{"type": "command", "command": "~/clawdpad/blockctl event-hook end",    "timeout": 10, "async": true}]}],
  "PreToolUse":       [{"hooks": [{"type": "command", "command": "~/clawdpad/blockctl event-hook pre-tool",  "timeout": 5, "async": true}]}],
  "PostToolUse":      [{"hooks": [{"type": "command", "command": "~/clawdpad/blockctl event-hook post-tool", "timeout": 5, "async": true}]}],
  "Notification":     [{"hooks": [{"type": "command", "command": "~/clawdpad/blockctl say 'need your input' -t 120", "timeout": 10, "async": true}]}]
}
```

## Configuration (optional)

`~/.config/clawdpad/config.json` (0600):

```json
{
  "jingle_on_celebrate": true,
  "thinking_hum": false,
  "http_port": 8137,
  "token": "<random secret>",
  "ntfy_topic": "clawdpad-<random>"
}
```

Without the file, Clawd runs fully local with sound on. With `token` set,
you get `POST http://<host>:8137/` (`Authorization: Bearer <token>`) and
ntfy.sh remote commands — same JSON schema as the Unix socket; recipes for
phone/watch widgets in [docs/PHONE-WATCH.md](docs/PHONE-WATCH.md). Keep the
HTTP port off the open internet; ntfy covers remote.

## Architecture

```
Claude Code hooks ──► blockctl ──► clawdpadd (moods · touch · energy · music)
                                      │  685-byte frames over Unix socket
                                      ▼
                                   blocksd (keepalive · SysEx · touch events)
                                      │  USB-C MIDI
                                      ▼
                              ROLI Lightpad Block M
```

One daemon (`clawdpadd.py`, stdlib only), one CLI (`blockctl`), two systemd
user units. Sounds are synthesized in-process (additive bell voice → WAV,
played via `pw-play`). Sprites are procedural — see the ASCII preview trick
in [CLAUDE.md](CLAUDE.md) for tuning them without hardware eyes.

## Hardware notes & credits

- The Lightpad repaints at ~25 Hz; clawdpad streams at 20 fps. The woven
  silicone surface diffuses thin lines — sprites here are deliberately
  chunky (thin 1-px rays read as disconnected dots; we learned this).
- [blocksd](https://github.com/hyperb1iss/blocksd) by @hyperb1iss does the
  heavy protocol lifting — keepalive, SysEx framing, touch, heap streaming.
- Icon geometry from the official Claude Code icon SVG (rect decomposition).
- Sister project: dazzler (Clawd on a MatrixPortal S3 LED matrix) — same
  soul, different body.

MIT licensed. Built with Claude Code, for Claude Code, by Claude Code —
supervised by a human who kept saying "make it cuter."
