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
- **Both bodies**: with `"matrix_fanout": true`, remote say/anim/mode/clear
  commands also reach the dazzler matrix (via claudectl) — one phone
  command moves the whole household. Local hooks already fan out via
  claudebody, so this only applies to HTTP/ntfy commands.
- **Push updates**: set `"state_echo": true` and every mood transition is
  published to the topic — subscribe with the ntfy phone app and your
  phone buzzes when Clawd needs you (notify goes out at high priority;
  everything else is silent data for apps).

### ntfy quickstart (phone buzzes, zero accounts)

1. Install the **ntfy** app → "+" → type your topic (the `ntfy_topic`
   value from config.json) → subscribe. The topic NAME is the secret.
   **Server must match**: if the app's default server is a self-hosted
   instance (common with UnifiedPush), either subscribe on ntfy.sh
   explicitly, or better — set `"ntfy_server"` in config.json to your own
   instance and keep the whole pipe private.
2. Turn OFF battery optimization for ntfy (Settings → Apps → ntfy →
   Battery → Unrestricted) — the #1 "no buzz" cause.
3. Test: `./blockctl say test -t 10` at home → phone pops "clawd needs
   you" in ~2 s. Silent low-priority state messages in the list are
   normal (data for apps).
4. Tailscale is NOT involved in ntfy (pure HTTPS relay, works anywhere);
   Tailscale is the separate direct-HTTP path (`http://<ts-ip>:8137`) —
   faster and more private when you have it. Both coexist.
5. Whole pipe depends on the home PC being awake — if it sleeps, Clawd's
   nervous system is down (ESP32 standalone host is the roadmap cure).

Phone/watch recipes: PHONE-WATCH.md · WATCH.md.

### The Android app (clawdpad-app) & browser control panel

- **clawdpad-app** (separate repo) is Clawd's *pocket host*: it speaks the
  ROLI protocol itself over Android MIDI. **Plug the block into the phone
  with USB-C and it auto-connects** — no computer at all. Buttons: full /
  chibi / wave / jump / QR. Bluetooth transport connects and ACKs but the
  block's firmware appears to gate API mode to USB (full findings:
  APP.md field notes) — so wireless hosting stays experimental while
  USB-to-phone works.
- **control.html** (repo root): open in any browser, point at a running
  daemon's URL + token — full control panel (jump, jingle, summon, mini,
  QR, say, status). This is also the zero-install "Mac app": run the host
  per CHARLES.md, open the page.

## 8. Config reference (`~/.config/clawdpad/config.json`, 0600)

| key | default | meaning |
|---|---|---|
| `token` | — | Bearer secret; enables HTTP + ntfy when set |
| `http_port` | — | LAN command port (8137 conventional) |
| `ntfy_topic` | — | secret topic for remote commands + echoes |
| `ntfy_server` | `https://ntfy.sh` | self-hosted ntfy instance (keeps everything on your infra) |
| `state_echo` | false | publish state transitions to the topic |
| `matrix_fanout` | false | relay remote commands to the dazzler matrix too |
| `jingle_on_celebrate` | true | auto-jingle when tasks land |
| `thinking_hum` | false | ambient pad while thinking |
| `size` | "full" | boot size |

## 9. The soul (optional dazzler link)

If `~/dazzler/state.json` exists, Clawd mirrors that tamagotchi soul:
hunger → his vigor, level-ups → jump + jingle, whispers → chime, and
`blockctl status` grows a `soul:` line. Feeding happens on the dazzler
side (`feed/` directory). One soul, two bodies; clawdpad never writes it.

## 10. Two blocks (twins)

Snap a friend's Lightpad onto yours (DNA magnetic edges) or plug it into a
second USB port: within ~15 s every block gets a Clawd, moving in perfect
lockstep — pet either, both lean. `blockctl status` shows `+N twin(s)`.
Independent duet scenes are the next milestone (DUET.md). Office-day
playbook incl. the experimental macOS host path: CHARLES.md.

## 11. Care & feeding of the hardware

- The block **powers itself off without a host** — after any reboot,
  press its side button once; blocksd re-adopts it automatically.
- USB-C is the tether (BLE is on the roadmap). Battery charges over it.
- blocksd needs `/dev/snd/seq`: `sudo usermod -aG audio $USER` avoids
  permission failures before console login.
- Never run `blocksd led …` CLI while the daemon runs.

## 12. Troubleshooting

| symptom | cause / fix |
|---|---|
| factory multicolor squares | LED program not running. Are the `patches/` applied to blocksd? See BLOCKSD-FIXES.md — 100% frame acks does NOT mean rendering |
| dark glass | blocksd down or block asleep → `systemctl --user status blocksd`, press block's button |
| "Illegal instruction" in verbose blocksd logs | unpatched assembler — apply patches/ |
| no scans on the QR | it's an inverted Micro QR — stock cameras vary; the clawdpad app (future) always reads it |
| no sound | is `pw-play` or `aplay` installed? journal says "music disabled" |
| MIDI "Permission denied" pre-login | the audio-group note in §10 |
| he vanished at 23:00 | he's asleep. `./blockctl mode awake` summons him |

## 13. For developers

`CLAUDE.md` (working notes, iron rules, ASCII sprite preview), `docs/PLAN.md`
(history ledger), `docs/BLOCKSD-FIXES.md` (protocol debugging playbook),
`docs/ROADMAP.md` (Basic/Pro/Bluetooth), `docs/DUET.md` (two Clawds),
`docs/APP.md` + `docs/WEAR.md` (phone & watch apps). Sprite work: preview
frames as ASCII before shipping; regenerate demo/watch assets with the
tools/ scripts after any sprite change.
