# clawdpad-wear — the real Galaxy Watch7 app

*Design, 2026-07-15. Third member of the family: daemon (`clawdpad`),
phone (`clawdpad-app`), watch (`clawdpad-wear`). Interim wrist presence
(photo faces, WatchMaker loop) is covered in WATCH.md — this is the
native app that replaces it.*

## Repo & stack

Separate repo **`clawdpad-wear`** — Wear OS 5 (Watch7) wants native:
**Kotlin + Compose for Wear OS**, plus the Tiles and Complications APIs
that RN/Expo can't reach. The phone app stays Expo; the two apps share
nothing but the daemon's JSON contract, which is the point.

## Connectivity (standalone-first)

The watch talks to the *daemon*, like every family member:

- **Home Wi-Fi / tailnet**: direct `http://<host>:8137` (Bearer token).
- **Anywhere**: the ntfy topic over HTTPS — the watch publishes commands
  and subscribes to **state echoes** (shipped in the daemon 2026-07-15:
  `"state_echo": true` in config publishes `{"event":"state", mood, size,
  energy, battery, pet}` on every transition; notify states go out at
  ntfy priority *high*, everything else *min*/silent).
- Phone-bridge (Wearable Data Layer) only as a fallback — standalone
  keeps the watch useful when the phone's in a bag.

## Features, in build order

1. **W1 — Tile** (a weekend): one swipe from the watch face — his current
   mood glyph + three buttons: wave at him (`say`), celebrate, status.
   Tiles are declarative and cache-friendly; state comes from the last
   echo, tap actions are one HTTPS POST each.
2. **W2 — "He needs you" (the killer)**: state echo `mood=notify` →
   ongoing watch notification + haptic; the notification's action button
   sends `{"cmd":"clear"}` — **tap your wrist to acknowledge the block
   across the world**. Claude Code permission prompt → wrist buzz → one
   tap. This alone justifies the app.
3. **W3 — Live watch face**: Clawd rendered natively on the face. Not
   streamed pixels — the sprite is ~40 rectangles; port `_clawd()` /
   `_mini()` math to a Compose canvas and animate locally from the last
   echo's mood (breathe/blink/pace exactly like the glass, because it's
   the same formulas). Ambient mode = the sleeping pose, genuinely.
4. **W4 — Complications**: hunger/level as a small complication for
   people who keep their own face; battery-of-the-block chip.
5. **W5 — Soul actions**: feed shortcut (quick-replies as notes), stats
   micro-screen (level/XP/hunger ring).

## Daemon contract (all shipped)

| channel | use |
|---|---|
| `GET /status` (Bearer) | pull: full state incl. pet, size, energy |
| `POST /` commands | act: say/anim/play/size/qr/clear/mode |
| ntfy topic, `{"event":"state"…}` | push: transitions, priority-coded |
| ntfy topic, token'd JSON | act from anywhere (no LAN needed) |

## Dev-loop notes (for the build weekend)

Android Studio + Wear OS emulator gets W1–W3 built without touching the
watch; on-body install via Wireless Debugging (Watch7: Settings →
Developer options → ADB over Wi-Fi, `adb pair`). No Samsung store
account needed for sideload; Play deployment is a Pro-era question.
