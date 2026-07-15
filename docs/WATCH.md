# Clawd on the Galaxy Watch7

*Written 2026-07-15, under a 90-minute deadline before Rod left for work.
Three paths, fastest first. Assets in `docs/watch/` (regenerate anytime
with `.venv/bin/python tools/make_watch_assets.py` — they render from the
real frame functions, so they always match the current sprite).*

## Path 1 — Photo watch face (≈5 minutes, zero installs)

Clawd as your watch face, right now:

1. Get `docs/watch/clawd_face.png` onto the phone (Claude just sent it in
   chat; or Google Photos / USB).
2. Phone → **Galaxy Wearable** app → **Watch faces** → find the **Photos**
   face → set `clawd_face.png` as the image → apply.
3. Optional: add `clawd_sleep.png` as a second photo — the Photos face
   lets you tap-cycle between them (day Clawd / night Clawd).

Static, but it's *him*, on your wrist, before you finish your coffee.

## Path 2 — Animated Clawd (≈15 minutes, WatchMaker)

`clawd_face.gif` is a 6.5 s breathing loop with a real blink at ~4.3 s:

1. Install **WatchMaker** on the phone + its Wear OS companion on the
   watch (Play Store; the watch part installs from the phone app).
2. New watch face → add a **GIF layer** → pick `clawd_face.gif` → center,
   scale to taste (it's round-face safe at full size).
3. Add a time text layer above him (his glass stays a creature — the
   watch can carry the clock).
4. Sync to watch. Free tier is enough for one face.

Facer works too (GIF layers need Facer Creator on the web); WatchMaker is
the faster route.

## Path 3 — Control tiles (the Phase-3 dream; do this on the weekend)

Buttons on the wrist that command the real Clawd: celebrate, jingle,
status, summon. Two options, per docs/PHONE-WATCH.md research:

- **Tasker + AutoWear** (no Home Assistant): Tasker task per command —
  HTTP Request action, `POST http://100.96.211.44:8137/` (Tailscale, works
  anywhere; LAN IP at home), header `Authorization: Bearer <token>`, body
  e.g. `{"cmd":"anim","arg":"celebrate"}` — then an AutoWear tile per task.
  Off-network fallback: POST to `https://ntfy.sh/<topic>` with the token
  inside the JSON instead.
- **Home Assistant Companion** (if HA enters the house): `rest_command`
  per palette entry → scripts → native watch tiles/complications.

Print secrets when configuring:
`python3 -m json.tool ~/.config/clawdpad/config.json`

## Someday (Pro, see APP.md)

The companion app's Wear OS module: live mood mirror as a tile, "he's
hungry" complications, one-tap wave. The watch face that *is* the live
glass (frames over the phone bridge) is bandwidth-cheap at 15×15 — a
genuinely feasible Pro feature.
