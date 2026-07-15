# The clawdpad Manual

*Everything about living with Clawd. Plain-text edition — the illustrated
HTML edition is [manual.html](manual.html). Current as of 2026-07-15.*

---

## 1. What is this?

Clawd is the Claude Code mascot, alive on a ROLI Lightpad Block M — a
15×15 LED grid behind a touch-sensitive silicone surface. He breathes,
blinks, paces while Claude Code works, waves when Claude needs you, jumps
when tasks land, and sleeps at night. He is a creature, not a dashboard:
everything on the glass is his body language.

## 2. Meet his moods

| mood | what you see | when |
|---|---|---|
| awake | breathing, bobbing, small paces, blinks, idle glances | nothing's happening; daytime |
| thinking | pacing back and forth, eyes leading | a Claude Code session is working — **he paces faster the harder Claude works** |
| notify | right arm up, waving, gentle pulse | Claude needs your input — **tap him to acknowledge** |
| celebrate | both arms up, jumping (+ jingle) | a task finished; double-tap; level-up |
| sleep | dim, eyes closed, slow breath, rare peek | 23:00–07:00 when idle |
| qr | the glass becomes a Micro QR code | `blockctl qr` (pairing, party trick) |

Sizes: **full** (fills the glass) and **mini** (chibi Clawd roaming his
block like a room). Toggle: triple-tap, `blockctl size mini`, config.

## 3. Touch — how to handle your Clawd

| gesture | reaction |
|---|---|
| press & hold | petting: he leans toward your finger, glows with pressure |
| slide | his eyes (and body) follow your finger |
| tap ×1 | acknowledges a notify; otherwise he turns and looks at you |
| tap ×2 | celebrate jump (with jingle, rate-limited) |
| tap ×3 | transforms: full ↔ mini (chime) |

Petting works in every mood. Petting him asleep half-wakes him, like
disturbing anyone at 3am. When he's hungry (soul link), his flame runs
low; starving, it gutters — feed him.

## 4. Sounds

Synthesized in-daemon (no synth software): **jingle** (task lands, rising
bell arpeggio), **chime** (notify / whispers / resize), **hello**
(greeting), and an optional quiet **hum** while thinking
(`blockctl hum on`). Auto-jingle is rate-limited to one per 30 s;
`"jingle_on_celebrate": false` silences it.

## 5. The command line

```
./blockctl status          mood · block · energy · soul · sessions
./blockctl demo            guided tour of every mood
./blockctl mode awake      summon him manually (sticky until next prompt)
./blockctl say "hi" -t 60  notify wave + chime; tap to ack
./blockctl anim celebrate  jump
./blockctl play jingle     sound + jump (also: hello, chime)
./blockctl hum on|off      thinking pad
./blockctl size full|mini  resize (same as triple-tap)
./blockctl qr TEXT -t 30   Micro QR on the glass (≤14 alnum / 23 digits)
./blockctl clear           drop notify + manual mode
./blockctl sessions        which Claude sessions he's tracking
```

## 6. Claude Code hooks (how he knows)

Hooks in `~/.claude/settings.json` call `blockctl event-hook …` on session
start/prompt/stop/end (mood), pre/post tool use (work energy), and
notifications (the wave). Full JSON in the README. blockctl exits silently
if the daemon's down — hooks never break your session.

## 7. Remote control (phone, laptop, anywhere)

With `~/.config/clawdpad/config.json` set (token + port + topic):

- **LAN/Tailscale**: `POST http://<host>:8137/` with header
  `Authorization: Bearer <token>` and a JSON command like
  `{"cmd":"anim","arg":"celebrate"}`. `GET /status` for state.
- **Anywhere**: publish the same JSON (plus `"token": "…"`) to your secret
  ntfy.sh topic.
- **Push updates**: set `"state_echo": true` and every mood transition is
  published to the topic — subscribe with the ntfy phone app and your
  phone buzzes when Clawd needs you (notify goes out at high priority;
  everything else is silent data for apps).

Phone/watch recipes: PHONE-WATCH.md · WATCH.md.

## 8. Config reference (`~/.config/clawdpad/config.json`, 0600)

| key | default | meaning |
|---|---|---|
| `token` | — | Bearer secret; enables HTTP + ntfy when set |
| `http_port` | — | LAN command port (8137 conventional) |
| `ntfy_topic` | — | secret topic for remote commands + echoes |
| `state_echo` | false | publish state transitions to the topic |
| `jingle_on_celebrate` | true | auto-jingle when tasks land |
| `thinking_hum` | false | ambient pad while thinking |
| `size` | "full" | boot size |

## 9. The soul (optional dazzler link)

If `~/dazzler/state.json` exists, Clawd mirrors that tamagotchi soul:
hunger → his vigor, level-ups → jump + jingle, whispers → chime, and
`blockctl status` grows a `soul:` line. Feeding happens on the dazzler
side (`feed/` directory). One soul, two bodies; clawdpad never writes it.

## 10. Care & feeding of the hardware

- The block **powers itself off without a host** — after any reboot,
  press its side button once; blocksd re-adopts it automatically.
- USB-C is the tether (BLE is on the roadmap). Battery charges over it.
- blocksd needs `/dev/snd/seq`: `sudo usermod -aG audio $USER` avoids
  permission failures before console login.
- Never run `blocksd led …` CLI while the daemon runs.

## 11. Troubleshooting

| symptom | cause / fix |
|---|---|
| factory multicolor squares | LED program not running. Are the `patches/` applied to blocksd? See BLOCKSD-FIXES.md — 100% frame acks does NOT mean rendering |
| dark glass | blocksd down or block asleep → `systemctl --user status blocksd`, press block's button |
| "Illegal instruction" in verbose blocksd logs | unpatched assembler — apply patches/ |
| no scans on the QR | it's an inverted Micro QR — stock cameras vary; the clawdpad app (future) always reads it |
| no sound | is `pw-play` or `aplay` installed? journal says "music disabled" |
| MIDI "Permission denied" pre-login | the audio-group note in §10 |
| he vanished at 23:00 | he's asleep. `./blockctl mode awake` summons him |

## 12. For developers

`CLAUDE.md` (working notes, iron rules, ASCII sprite preview), `docs/PLAN.md`
(history ledger), `docs/BLOCKSD-FIXES.md` (protocol debugging playbook),
`docs/ROADMAP.md` (Basic/Pro/Bluetooth), `docs/DUET.md` (two Clawds),
`docs/APP.md` + `docs/WEAR.md` (phone & watch apps). Sprite work: preview
frames as ASCII before shipping; regenerate demo/watch assets with the
tools/ scripts after any sprite change.
