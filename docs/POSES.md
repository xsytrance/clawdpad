# The pose surface — what Clawd can be, and on which body

*Written 2026-07-17, after an audit found that "the same creature, two bodies"
was not true. It is now, and `tools/parity.py` keeps it that way.*

Clawd exists in two implementations, deliberately:

| | |
|---|---|
| **`web/clawd-core.js`** | **canonical.** Every interactive body: browser (USB *and* Bluetooth), and any future native shell. Author poses and costumes HERE. |
| **`clawdpadd.py`** + `costumes.py` | the headless desk daemon. Long-running, stdlib-only, owns hooks/soul/multi-block. Mirrors the JS. |

They are kept honest by **`tools/parity.py`**, which renders the shared surface
on both and compares bytes. Not "looks right" — identical bytes.

> **⚠ There is a third body, and this harness cannot see it.** Noted
> 2026-07-17. `clawdpad-app` (the Android host) carries `ClawdRenderer.kt` +
> `Costumes.kt` — a hand port of Clawd's art into Kotlin, made from
> `clawdpadd.py` (the mirror) rather than `clawd-core.js` (the source), and
> written before the one-arrow rule existed to forbid it. `parity.py` diffs the
> desk against the browser; **nothing at all watches the phone.** Its protocol
> layer *is* golden-tested (`GoldenTest.kt`, `DecoderTest.kt`) — it's the art
> that's unguarded. Rod's call, same day: document now, fix after demo day.
> Options and reasoning in [LEVELS.md](LEVELS.md) → "The third body already
> exists". Everything below describes the two bodies this harness covers.

```bash
.venv/bin/python3 tools/parity.py       # 41/41 identical
tools/check.sh                          # parity + golden vectors + the rest
```

## The shared surface — must be identical on both

Every pose here is a pure function `(args) → 675-byte RGB888`. No I/O, no state.

| Pose | JS | Python | What he's doing |
|---|---|---|---|
| awake | `Clawd.awake(t)` | `frame_awake(t)` | breathes, bobs, paces a little, blinks, glances |
| sleep | `Clawd.sleep(t)` | `frame_sleep(t)` | dim, slow breathing, eyes closed, occasional peek |
| thinking | `Clawd.thinking(phase, t)` | `frame_thinking(phase, t)` | pacing, eyes leading the way |
| notify | `Clawd.wave(t)` | `frame_notify(t)` | right arm up, waving, gentle pulse |
| celebrate | `Clawd.celebrate(rel)` | `frame_celebrate(rel)` | both arms up, jumping |
| sad | `Clawd.sad(t)` | `frame_sad(t)` | slumped, arms drooped, heavy blinks, looks away |
| marquee | `Clawd.marquee(text, t, c)` | `_marquee_frame(text, t)` | words scroll across him |
| qr | `Clawd.qr(payload)` | `build_frame` mood `"qr"` | the glass becomes a Micro QR |
| chibi | `Clawd.mini*` | `_mini`/`_mini_frame` | quarter the pixels, roaming a big room |
| costumes | `Clawd.dressed(...)` | `costumes.dressed(...)` | props layer on; skins replace the body |

**`phase` is an accumulator, not a timestamp.** The host integrates it at
`2.5 + 4.5*energy` rad/s so Clawd paces faster the harder the work is. Never
write `phase = t * speed` — when the speed changes, the pacing jumps.

## One-sided on purpose — not drift

Listed in `tools/parity.py`'s `ONE_SIDED` and skipped by the harness. Add here
only with a reason.

**Python only** — all daemon-context, none of it meaningful in a tab:
`pong`, `visit` (block-to-block hop), `heart`/`reunion`, `empty` (the
night-light on an unoccupied glass), `_glyph_big`, touch/petting poses (needs
the pressure sensor), and vigor/hunger dimming (owned by dazzler's soul).

**Battery body language** is Python-only and is *not a pose* — it's three
multipliers the host applies (`State.battery_pace/battery_vigor/battery_tired`),
exactly like `pet_vigor()`. Below 20% he paces slower, dims, and his blinks go
long and yawning; while charging he gets a slow ±6% warm breath. They compose:
a hungry Clawd on a dying block is dimmer than either alone. A full battery
renders byte-identical to no feature at all, which is why parity stays green.

**JS only:** `dance` + `miniDance` (mic-driven — a web/Android ears thing; the
daemon has no dance mood), and `rgb565` (a WebMIDI-side wire concern; the
daemon ships RGB888 to blocksd and lets it pack).

## The rule the poses don't get to make

The **marquee and costumes take over the calm moods only** — `awake`, `sleep`,
`thinking`. Never `notify`, `celebrate`, or `qr`: if Clawd needs you, you see
him *wave*, not a message.

This is gated **once** per host — `build_frame` in Python, `currentFrame()` in
`index.html` — and never inside a pose. Poses are pure. When this rule lived
inside each pose, `wave` hid behind a marquee while `sleep` ignored it, and
both sides were "right".

## What went wrong before parity existed

All of this shipped, and none of it was visible without a block and two
machines. It's the argument for the harness:

- **A costumed Clawd could wave and jump in the browser but not on the desk.**
  `costumes.dressed()` had no arm offsets, so `build_frame` had to strip his
  outfit for notify/celebrate. Pure signature mismatch, invisible in review.
- **`frame_thinking` had no JS counterpart at all** — the tab could not show
  the single behaviour the whole project is named for.
- **The tab's sleeping Clawd neither breathed nor peeked** — `index.html`
  inlined a flat `dressed(0.22, …, false, …)`. `miniSleep` did it correctly,
  so only full-size drifted.
- **Chibi was one brightness unit brighter in the browser.** `mini()` rounded
  where `body()` and Python truncate. Invisible to the eye; caught by bytes.
- **The two files each named the other as source of truth**, so there was no
  reference to diff against and none of the above was resolvable by reading.

## What went wrong *after* parity existed (2026-07-17, same day)

The harness caught five bugs on day one and then reported 32/32 green over two
more, both of which it was structurally blind to. Worth reading before trusting
any green tick, including this one's:

- **A costumed Clawd never slept on the desk, and never paced while thinking.**
  `build_frame` had three near-duplicate costume branches that re-derived
  *awake* breath/bob/blink for every calm mood and returned early — so at 3am a
  dressed Clawd breathed at 0.72 with his eyes open. The browser was right the
  whole time, because its poses dress themselves from the inside
  (`Clawd.dressed()`), so the outfit can't overwrite the body language.
  **The bug lived in the gate above the poses, and parity renders poses.**
  Fixed by giving the daemon the same seam: `_skin()`, one render path, poses
  own body language and only `build_frame` decides what he's wearing.
- **parity.py had never loaded the daemon's costumes.** It put ROOT on
  `sys.path` *after* importing clawdpadd, so `try: import costumes / except
  ImportError: costumes = None` quietly succeeded at failing. It proved
  costumes.py matched the browser while the daemon's *use* of it went untested —
  and broken. **A test that silently degrades is worse than no test: it reports
  green.** It now hard-fails if the daemon loads without costumes.

The lesson for the next table: a pose is (body language × outfit), and the old
tables checked the factors, never the product. `DRESSED_CASES` checks the
product, and caught both of the above the minute it existed.

## Adding a pose

1. Write it in `web/clawd-core.js`. Keep it pure — no marquee checks, no
   costume decisions, no state.
2. Preview it: `node tools/webpreview.mjs <pose>`. Solid chunky shapes only —
   the silicone diffuses 1px lines into disconnected dots.
3. Mirror it into `clawdpadd.py` (and `costumes.py` if it wears anything).
4. Add a row to `CASES` in `tools/parity.py`. If it's deliberately one-sided,
   add it to `ONE_SIDED` **with a reason** instead.
5. `tools/check.sh` — green, or it isn't done.
