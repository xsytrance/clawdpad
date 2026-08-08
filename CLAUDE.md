# clawdpad — working notes for Claude

<!-- CANON:BEGIN v1 2026-08-07 — managed by the Singularity Event. Edit the source, not this block. -->
## The Dominion — standing canon (v1)

**Theme.** Everything in this fleet is named and spoken in the register of
**magic, science, and military** — *"Doctor Doom meets Master Chief."* Imperial,
arcane, martial, over real engineering. Music is the soul that runs through all
three. The Lexicon (`hermes360/docs/codex/lexicon.json`) is the source of truth
for names; a themed name with no Lexicon entry is a bug, not creativity.

> **The Iron Rule.** The theme is a **naming / lore / presentation layer over
> stable technical identifiers. It NEVER renames the substrate.** Ports stay
> numeric in code; unit names, API paths, file names, env vars, and DB tables are
> unchanged. Themed names appear in agent speech, UIs, docs, and conversation —
> never in code identifiers. Renaming the substrate would break every running
> system, backup, and timer on the fleet.

Core terms: fleet → **the Dominion** · owner → **the Sovereign** · host →
**Realm** · PRIME → **the Citadel** · exxo-1 → **the Foundry** · tailnet →
**the Ley Lines** · service → **Engine** · agent → **Champion** · port →
**Portal** · endpoint → **Gate** · code → **Spell** · function → **Incantation**
· database → **Vault** · config → **Ward** · secret → **Seal** · doc → **Tome**
· log/receipt → **Chronicle** · backup → **Wardstone** · monitor → **the Augury**
· LLM → **Familiar** · notification → **a Sending** · Singularity → **the Grand
Archive**. *(Top names blessed by the Sovereign 2026-08-07.)*

**Reporting.** Every substantive reply ends with a `## TL;DR` — last, after the
detail, 3–5 bullets. Lead with anything the Sovereign must act on. Corrections
go **in** the TL;DR, never buried in the body.

**ISI.** On a big feature, a big change, a security posture, a schema change, or
a new project: **Intent** (what is he really trying to achieve?), **Sanity** (is
this the right approach? say so plainly, once), **Improvement** (is there a
better way? what would I add?). Verify with commands — measured beats plausible.
ISI is advisory, not a veto: raise it, recommend, then build. If he reaffirms,
that's the decision. Not permission to stall, and not permission to gold-plate.

**Secrets.** `~/.config/<system>/env`, mode 600. Never in a chat box, a commit,
or a screenshot. Exposed once = rotate the same day. `docs/SECURITY.md` is law.

**The Five Foundations.** One network (the tailnet) · one wallet (OpenRouter,
named key per system) · one secrets pattern · one memory (this) · one ark
(exxo-1). Full text: `docs/MASTER_PLAN.md`.

**Birth and death.** A new system gets, on day 0: `git init`, an env file (600),
a named key if it spends, a **Lexicon entry**, a row in `docs/SYSTEMS.md`, and an
Eye config if it has a UI. *A system not in the registry does not exist.* Cold
for 60 days → `~/archive/`. Archiving is honorable; drift is not.
<!-- CANON:END -->

<!-- BULLETIN:BEGIN 2026-08-08T12:42 — managed by the Singularity Event. Facts, not rules. Edit the registry, not this block. -->
## The Dominion — the roster (41 systems)

You are in **claudeblock**. Claude living on the ROLI Lightpad Block — dress him up, shrink him, morph him into other characters.

**Tell the Archive anything that matters:** `tell-singularity "…"` (`--birth <sys>` · `--death <sys>` · `--change <sys>` · `--ask "…"`)
**Find out what you missed:** `~/singularity/scripts/brief.sh`

### Born or changed in the last 14 days
- **planet-studio** — 2026-08-08 — satellite (music) — Android studio companion for x1c7.com: the Wall, galaxy, cover studio…
- **audiex** (the Warhorn) — 2026-08-08 — satellite (music) — standalone offline-first player for the Suno catalog; the planet-studio…
- **stem-racer** — 2026-08-07 — satellite (music/game) — stem-based racing game; APK served from ~/apk-share.
- **cadence** — 2026-08-07 — the Dominion's ceremony bus (Portal 8114). Any Engine posts a rite; it decides how it is felt…
- **vgclan** — 2026-08-02 — satellite — VG Clan revival site; re-recruit the founders, deploy to vgclan.x1c7.com.
- **NEXUS** — 2026-07-31 — command vault (obsidian) — Gradle project with mobile-web application components.
- **memguard** — 2026-07-31 — utility — guards against memory exhaustion on Prime; the GPU is shared (16 GB) and a runaway…
- **singularity** (the Grand Archive) — 2026-07-31 — the Grand Archive. System of record for a life: every chat, doc, photo and receipt, dated…

### The full roster
`sayhai` · `stem-racer` · `va-academy` · `vgclan` · `cadence` · `entangled-private` · `entangled-tools` · `xsyverse` · `fft-psx-vera` · `hermes360-c2-artifacts` · `argus-risk-adviser` · `clawdpad-app` · `aurex16pp` · `ember-lite` · `kinetica` · `planet-studio` · `audiex` · `vAIb` · `pokepad` · `ossicle-backups` · `Hermes` · `ossicle` · `singularity-integration` · `x1c7.com` · `AGENOR-Horology` · `atlas` · `entangled` · `undertale-vera` · `eye-of-thundera` · `hermes360` · `xsywatch` · `NEXUS` · `memguard` · `singularity` · `skynet` · `xsynet` · `ossicle-worktrees` · `dazzler` · `claudeblock` · `ember-pro` · `prism`

Live: `GET :8801/api/event/roster` · Canonical: `singularity/docs/SYSTEMS.md`
<!-- BULLETIN:END -->

Clawd (the Claude Code mascot) living on a ROLI Lightpad Block M. Public
project (MIT); Rod's install lives in `~/claudeblock` (dir predates the
clawdpad rename — units/hooks point here, rename is cosmetic-only pending).
Sister project `~/dazzler` (same soul on a MatrixPortal S3). Read `README.md`
for the public story, `docs/PLAN.md` for history, `docs/BLOCKSD-FIXES.md`
for the protocol war stories, `docs/LEVELS.md` for where this is all going
(L0 tab → L1 daemon → L2 app → L3 integrations → L4 colony).

**Hosts own a block; controllers poke a host.** Exactly one host per block,
always. Hosts: the tab (web/), the daemon (clawdpadd.py), and the future app.
Controllers: `docs/APP.md` (phone), `docs/WEAR.md` (watch) — they talk to the
daemon's HTTP API and never touch the glass. Say which one any new thing is.

**Platforms port the transport, never the art.** A new body needs exactly one
new thing: a `send(bytes)` that reaches a block. clawd-core.js already draws
Clawd *and* speaks bit-identical ROLI (golden vectors prove it), so a native
shell writes a MIDI transport and hands bytes to the JS — it never reimplements
poses. That keeps parity.py a 2-body problem no matter how many platforms ship.
Note WebMIDI is Chromium-only: Electron has it, WKWebView (Tauri/macOS,
Capacitor/iOS) does not. See docs/LEVELS.md "the webview trap".

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
                     blocksd (service: blocksd; VENDORED — blocksd/ (gitignored),
                       │       pip install -e; patches/ = shareable fixes)
                       ▼  SysEx over USB MIDI
                     Lightpad Block M (serial LPM9E1KL3HO9XC5G)
```

## Iron rules

- **blocksd must always run** — the block powers off without its keepalive.
  After a host reboot someone must press the block's power button.
- **blocksd is installed editable from `blocksd/`** (a gitignored clone of
  hyperb1iss/blocksd at the repo root — *not* `vendor/`, which is stale in old
  notes; three commits on `main`, exported to `patches/`). Never
  `pip install -U blocksd`. Edit blocksd/ → `systemctl --user restart blocksd`.
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
printf '{"cmd":"subscribe"}\n' | nc -U /tmp/clawdpad/clawdpad.sock   # watch him
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
  pet/hum loops, optional HTTP + ntfy. `State` under one lock.
  **`State.emit()` has its own `subs_lock`** — `self.lock` is non-reentrant and
  emit is called from inside locked sections (`touch_end`); sharing it would
  deadlock the touch loop. Subscribers drop events when slow; nothing an
  integration does may stall the render loop. `{"cmd":"subscribe"}` /
  SSE `GET /events` are the outbound stream — `notify`→`ack` is the loop
  integrations live on (see docs/MANUAL.md §7b). `_clawd()`
  renders the icon (CLAWD_BODY/ARMS/LEGS/EYES consts, scaled from the
  official SVG rects via dazzler's make_clawd.py); frame_* compose poses.
  Energy (tau 25 s) drives a phase accumulator → pacing speed (never
  multiply t by a time-varying speed — it jumps).
- `blockctl` — stdlib CLI, claudectl-compatible, silent exit 0 when the
  daemon is absent. Test/fail regexes for post-tool energy live here.
  `blockctl doctor` is the exception to the silence: it's loud when things are
  broken, because that's the job.
- `doctor.py` — the nine checks a new owner trips on, as a **library**: `run()`
  returns `Check` objects and **never prints**. blockctl renders them; `--json`
  is the machine face; the L2 app's first-run screen is meant to be the third
  (docs/LEVELS.md idea #2). A check that prints can't be a wizard. Every check
  catches its own exception — it only ever runs on broken machines. Its patch
  probes must key off symbols the patches *introduce* (`code_base`,
  `bitmap_led_program`, `_GroupKey`), never words from their commit messages:
  the first draft probed for "port_indices" and called a healthy tree broken.
- `patches/` — the three blocksd fixes as git am-able patches (for sharing
  and the upstream PR). 0003 is macOS-only: CoreMIDI names every block
  identically, so keying device groups by port name drops the second one
  (`docs/BLOCKSD-FIXES.md`). Two blocks on a Mac need it.
- `systemd/` — portable unit templates (%h paths).
- `web/` — the zero-install host: `index.html` + `clawd-core.js` (Clawd's
  poses in JS, `TopologyDecoder`, `HeapStreamer`) drive a block straight from
  a Chrome tab over WebMIDI — USB *or* Bluetooth, no daemon. `qr-data.js` is
  GENERATED (tools/make_web_qr.py). Buttons must act **locally first, then**
  call `remoteCmd` — a remote-only button is a silent no-op while the tab is
  the host, which is how chibi/QR/size shipped broken.
- **`web/clawd-core.js` is CANONICAL for Clawd's art and poses.** Author a pose
  or costume there first, then mirror into `clawdpadd.py`/`costumes.py`. Never
  the reverse. Until 2026-07-17 the two files each named the *other* as source
  of truth, which meant drift had no reference to resolve against — and drift
  had already shipped (a costumed Clawd could wave in the browser but not on
  the desk). One arrow, one direction, forever.
- **`blocksd` is CANONICAL for the protocol** — the opposite direction. The
  daemon emits frames to blocksd; clawd-core.js reimplements the ROLI stack for
  WebMIDI because a browser can't dial a Unix socket. That replica is kept
  honest by golden vectors, not by sharing code. Run `tools/check.sh`.
- **Never hardcode a block's device index.** Blocks report their own topology
  index and they differ (XC5G=9, SH8T=32). Ask via topology; see
  docs/MACBOOK.md Phase 2 for the evening this cost.
- `tools/` — firstlight.py, paint.py, touchtest.py (protocol references);
  `wireprobe.py` (what a block says back: serial, topology, real device index,
  device logs — stop blocksd first); `webpreview.mjs` (render web poses as
  ASCII, no browser); `make_web_qr.py` (bake QR matrices with segno).

## Testing without hardware eyes

Claude cannot see the glass. For sprite/animation work, preview frames as
ASCII before shipping:

```python
import clawdpadd
buf = clawdpadd.frame_awake(1.0)   # or any frame_*
# (y*15+x)*3 indexes RGB; map luminance to . + #
```

For the web page the equivalent is `node tools/webpreview.mjs` (any pose,
full or mini, no browser needed).

**`tools/check.sh` is the whole no-hardware safety net** — golden vectors
(clawd-core.js speaks bit-identical ROLI to blocksd), cross-body parity
(`tools/parity.py`: 45 cases, byte-identical on desk and browser), every pose
renders, imports clean. Run it before claiming anything works. It found five
shipped drift bugs the day it was written — and two more the same day that it
had been *structurally blind to* while reporting green (a costumed Clawd never
slept on the desk; parity itself never loaded the daemon's costumes). Read
`docs/POSES.md` before trusting a green tick: **a pose is body language ×
outfit, and a table that checks the factors can miss the product.**

`blockctl status`, the clawdpadd journal, and blocksd `--verbose` device
logs are the observables; for anything visual, ask Rod to look. **Beware
`blockctl status`/`names`: they read clawdpadd's cache, not the hardware** —
a phantom block once persisted there for an hour after it was gone. Ground
truth is blocksd's `discover` over its socket, or `tools/wireprobe.py`. Sessions
named `hermes360`/`dazzler` in `blockctl sessions` are Rod's other live
Claude sessions — real traffic, not test data.
