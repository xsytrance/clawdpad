#!/usr/bin/env python3
"""clawdpadd — Clawd, the Claude Code critter, living on a ROLI Lightpad Block.

Renders the official Claude Code icon as 15x15 pixel art and gives it a
life: it breathes, blinks, paces while Claude works, waves when Claude needs
you, jumps when a task lands, and sleeps at night. Everything on the glass
is Clawd's own body language — no abstract effects.

Streams frames through a running blocksd (Unix socket, 685-byte binary
frames) and exposes a Unix-socket command interface for blockctl and
Claude Code hooks.

Moods (all rendered by _clawd()):
  awake     breathing, bobbing, pacing a little, blinking, glancing around
  thinking  pacing back and forth, eyes leading — faster the harder Claude
            works (tool-call hooks feed a work-energy meter)
  sleep     dim, eyes closed, slow breathing, occasional peek (23:00-07:00
            when idle); petting half-wakes him
  notify    right arm raised and waving, gentle pulse — tap to acknowledge
  celebrate one-shot: both arms up, jumping (~2.4s)

Touch:
  press/slide   petting — he leans toward your finger, glows with pressure,
                and his eyes follow it
  tap           acknowledges a notify; otherwise he looks at you and blinks
  double-tap    celebrate jump (with the jingle, rate-limited)

Command protocol: one JSON object per line, one JSON reply per line.
  {"cmd": "event-hook", "kind": "start|prompt|stop|end", "sid": "...", "project": "..."}
  {"cmd": "event", "kind": "ripple|wave|flash", "sid": "..."}   # energy only
  {"cmd": "mode", "arg": "awake|thinking|sleep|notify"}
  {"cmd": "say", "arg": "text", "seconds": 120}      # notify + chime
  {"cmd": "anim", "arg": "celebrate"}
  {"cmd": "play", "arg": "jingle|hello|chime"}       # jingle also jumps
  {"cmd": "hum", "arg": "on|off"}                     # ambient pad while thinking
  {"cmd": "visit"}                                    # hop to the other block
  {"cmd": "game", "arg": "pong|off"}                  # pong across the glasses
  {"cmd": "names"}                                    # glasses wear name tags
  {"cmd": "clear"}                                    # drop notify + manual mode
  {"cmd": "status"}

Remote surfaces (optional; enabled by ~/.config/clawdpad/config.json):
  HTTP  POST / with `Authorization: Bearer <token>`, GET /status
  ntfy  publish JSON commands (with a "token" field) to the secret topic

Music is synthesized in-process (pure-stdlib additive bell voice -> WAV
cached in the runtime dir, played via pw-play/aplay). Config keys:
"http_port", "token", "ntfy_topic", "jingle_on_celebrate" (default true,
one per 30s), "thinking_hum" (default false).

Soul link (optional): if ~/dazzler/state.json exists (the dazzler sister
project's tamagotchi), Clawd mirrors it read-only — hunger lowers his flame,
level-ups celebrate, whispers chime. One soul, two bodies. Absent the file,
he simply lives at full vigor.
"""

import hmac
import http.server
import json
import math
import os
import random
import shutil
import socket
import struct
import subprocess
import threading
import time
import urllib.request
import wave

try:
    import costumes
except ImportError:
    costumes = None

W = H = 15
CORAL = (217, 119, 87)     # Claude coral #D97757

FPS = {"sleep": 8}         # per-mood frame rate; default 20
FPS_DEFAULT = 20
CELEBRATE_SECONDS = 2.4
THINK_TTL = 90 * 60        # a "thinking" session older than this reads as resting
SESSION_TTL = 12 * 3600    # forget sessions entirely after this
SLEEP_START, SLEEP_END = 23, 7
EVENT_ENERGY = {"ripple": 0.10, "wave": 0.20, "flash": 0.25}
ENERGY_TAU = 25.0          # seconds for work-energy to decay to 1/e
TAP_MAX_SECONDS = 0.35     # touch shorter than this is a tap, longer is petting
DOUBLE_TAP_WINDOW = 0.6    # two taps inside this = double-tap
NOTICE_SECONDS = 1.2       # how long a single tap holds Clawd's gaze
VISIT_SECONDS = 3.2        # a hop between blocks: walk off one, onto the next
WANDER_EVERY = (150, 420)  # awake Clawd drifts to another block (min, max s)
HOME_SERIAL = "LPM9E1KL3HO9XC5G"  # Clawd's home glass (config "home_serial")
PONG_SPEED = 11.0          # ball px/s at serve; hits speed it up a touch
PONG_PADDLE = 4            # paddle height in px (2px wide — chunky rules)
ROLL_CALL_SECONDS = 4.0    # each glass scrolls its own name (config
                           # "block_names": {serial: name}; default = last 4)
REUNION_SECONDS = 4.2      # DNA snap: Clawd jumps, the other glass beams
                           # a heart — they missed each other

# Clawd's geometry, scaled from the official Claude Code icon SVG
# (viewBox 24x24; same rect decomposition dazzler's make_clawd.py uses):
# solid body, two side arm nubs, FOUR legs, two eye holes. Rects are
# (x0, y0, x1, y1), end-exclusive, on the 15x15 grid.
CLAWD_BODY = (2, 3, 13, 11)
CLAWD_ARMS = ((0, 7, 2, 9), (13, 7, 15, 9))     # left, right
CLAWD_LEGS = ((3, 11, 4, 13), (5, 11, 6, 13),
              (9, 11, 10, 13), (11, 11, 12, 13))
CLAWD_EYES = ((4, 5), (10, 5))                   # top px of each 1x2 eye hole

# Mini Clawd (chibi): 5x4 body + 1px arms + 2 legs + 1px eye holes.
# Small enough to roam the glass like a room — and for duet scenes where
# two of them need space to interact.
MINI_W, MINI_H = 5, 5   # body + legs footprint (arms poke 1px each side)

# One soul, two bodies: Clawd's pet state is OWNED by dazzler (petd.py writes
# it; a systemd timer ticks it). This body only mirrors it — never writes.
PET_STATE = os.path.expanduser("~/dazzler/state.json")
# Remote fan-out to the matrix body (config "matrix_fanout"): commands that
# arrive over HTTP/ntfy also reach dazzler via claudectl, so a phone command
# moves BOTH bodies. Local commands don't fan out — hooks already use
# claudebody for that, and doubling up would write the overlay twice.
MATRIX_CTL = os.path.expanduser("~/dazzler/claudectl")
MATRIX_CMDS = {"say", "anim", "clear", "mode"}
PET_VIGOR = {"full": 1.0, "content": 1.0, "peckish": 0.85,
             "hungry": 0.70, "starving": 0.55}  # brightness factor by mood


def blocksd_socket():
    for base in (os.environ.get("XDG_RUNTIME_DIR"), "/tmp"):
        if base:
            p = os.path.join(base, "blocksd", "blocksd.sock")
            if os.path.exists(p):
                return p
    return None


def command_socket():
    base = os.environ.get("XDG_RUNTIME_DIR") or "/tmp"
    d = os.path.join(base, "clawdpad")
    os.makedirs(d, mode=0o700, exist_ok=True)
    return os.path.join(d, "clawdpad.sock")


class State:
    """Everything the renderer needs, guarded by one lock."""

    def __init__(self):
        self.lock = threading.Lock()
        self.sessions = {}          # sid -> [project, "thinking"|"resting", epoch]
        self.manual = None          # explicit `mode` override
        self.notify_until = 0.0
        self.notify_text = ""
        self.oneshot_until = 0.0    # celebrate window
        self.energy = 0.0           # 0..1 work density; scales pacing speed
        self.touch = None           # live touch: [x, y, z, started] (0..1 floats)
        self.taps = []              # recent tap timestamps (double-tap detect)
        self.notice = None          # (look_dx, until): single-tap gaze
        self.block = {"connected": False, "serial": "", "battery": None}
        self.devices = []           # uids in blocksd order (render_loop's)
        self.dev_serials = {}       # uid -> serial
        self.home = None            # the glass Clawd inhabits (multi-block)
        self.visit = None           # (from_uid, to_uid, mono_t0): hop in flight
        self.next_wander = 0.0      # monotonic deadline for a self-directed hop
        self.home_serial = HOME_SERIAL
        self.game = None            # pong state dict (cmd game), or None
        self.block_names = {}       # serial -> display name (config)
        self.roll_call_until = 0.0  # monotonic: glasses wear name tags
        self.reunion_until = 0.0    # monotonic: the DNA-snap celebration
        self.linked = False         # DNA-snapped: the rooms merge into one
        self.away_flair = False     # render thread only: he's not home,
                                    # so he wears his traveling scarf
        self.started = time.time()
        self.player = None          # set in main()
        self.hum_enabled = False
        self.jingle_on_celebrate = True
        self.pet = None             # mirrored from dazzler's state.json
        self.last_say_chime = 0.0
        self.size = "full"          # "full" | "mini" (config "size", cmd size)
        self.matrix_fanout = False  # config "matrix_fanout"
        self.qr_until = 0.0         # Micro QR takeover window
        self.qr_matrix = None       # 15x15 bool rows
        self.costume = "none"       # Clawdrobe id (cmd costume)
        self.marquee = ""           # scrolling message (cmd marquee)

    def prune(self, now):
        for sid in list(self.sessions):
            project, mode, t = self.sessions[sid]
            if now - t > SESSION_TTL:
                del self.sessions[sid]
            elif mode == "thinking" and now - t > THINK_TTL:
                self.sessions[sid] = [project, "resting", t]

    def mood(self, now):
        with self.lock:
            self.prune(now)
            if now < self.qr_until and self.qr_matrix:
                return "qr"
            if now < self.oneshot_until:
                return "celebrate"
            if now < self.notify_until:
                return "notify"
            if self.manual:
                return self.manual
            if any(s[1] == "thinking" for s in self.sessions.values()):
                return "thinking"
            hour = time.localtime(now).tm_hour
            if hour >= SLEEP_START or hour < SLEEP_END:
                return "sleep"
            return "awake"

    def celebrate(self, now):
        self.oneshot_until = now + CELEBRATE_SECONDS

    def matrix_relay(self, msg):
        """Mirror a remote command onto the dazzler matrix via claudectl."""
        cmd = msg.get("cmd")
        argv = None
        if cmd == "say":
            argv = ["say", str(msg.get("arg", "")),
                    "-t", str(float(msg.get("seconds", 30)))]
        elif cmd == "anim":
            argv = ["anim", str(msg.get("arg", "celebrate"))]
        elif cmd == "clear":
            argv = ["clear"]
        elif cmd == "mode":
            arg = str(msg.get("arg", "awake")).lower()
            if arg in ("awake", "thinking", "sleep"):
                argv = ["mode", arg]
        if argv and os.path.exists(MATRIX_CTL):
            subprocess.Popen([MATRIX_CTL] + argv,
                             stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)

    def apply(self, msg, now, remote=False):
        cmd = msg.get("cmd")
        if remote and self.matrix_fanout and cmd in MATRIX_CMDS:
            self.matrix_relay(msg)
        with self.lock:
            if cmd == "event-hook":
                kind = msg.get("kind", "prompt")
                sid = str(msg.get("sid", "manual"))[:8]
                project = str(msg.get("project", "somewhere"))
                if kind in ("start", "prompt"):
                    # new activity reclaims the mood; a mere turn-ending
                    # does not, so a manually summoned Clawd survives stops
                    self.manual = None
                if kind == "start":
                    self.sessions[sid] = [project, "resting", now]
                elif kind == "prompt":
                    self.sessions[sid] = [project, "thinking", now]
                    self.energy = min(1.0, self.energy + 0.3)
                elif kind == "stop":
                    old = self.sessions.get(sid)
                    self.sessions[sid] = [old[0] if old else project,
                                          "resting", now]
                    self.celebrate(now)
                    if self.jingle_on_celebrate and self.player:
                        self.player.auto_jingle(now)
                elif kind == "end":
                    self.sessions.pop(sid, None)
                else:
                    return {"ok": False, "error": f"unknown kind: {kind}"}
            elif cmd == "event":
                # tool activity: no visual of its own — it feeds the work
                # energy that sets Clawd's pacing speed while thinking
                kind = str(msg.get("kind", "")).lower()
                self.energy = min(1.0, self.energy
                                  + EVENT_ENERGY.get(kind, 0.1))
                sid = str(msg.get("sid", ""))[:8]
                if sid in self.sessions:
                    self.sessions[sid][2] = now
            elif cmd == "mode":
                arg = str(msg.get("arg", "awake")).lower()
                if arg == "notify":
                    self.notify_until = now + float(msg.get("seconds", 30))
                elif arg in ("awake", "thinking", "sleep"):
                    self.manual = arg
                    self.notify_until = 0.0
                else:
                    return {"ok": False, "error": f"unknown mode: {arg}"}
            elif cmd == "say":
                self.notify_text = str(msg.get("arg", ""))
                self.notify_until = now + float(msg.get("seconds", 30))
                if self.player and now - self.last_say_chime > 10:
                    self.last_say_chime = now
                    self.player.play("chime")
            elif cmd == "anim":
                arg = str(msg.get("arg", "")).lower()
                if arg == "reunion":
                    self.reunion_until = (time.monotonic()
                                          + REUNION_SECONDS)
                    if self.player:
                        self.player.play("jingle")
                elif arg == "celebrate":
                    self.celebrate(now)
                    if self.jingle_on_celebrate and self.player:
                        self.player.auto_jingle(now)
                else:
                    return {"ok": False,
                            "error": "anims: celebrate, reunion"}
            elif cmd == "play":
                name = str(msg.get("arg", "jingle")).lower()
                if self.player is None or name not in MELODIES:
                    return {"ok": False, "error": f"cannot play: {name}"}
                if not self.player.play(name):
                    return {"ok": False, "error": "no audio player available"}
                if name == "jingle":  # sound + jump
                    self.celebrate(now)
            elif cmd == "hum":
                self.hum_enabled = str(msg.get("arg", "on")).lower() == "on"
            elif cmd == "costume":
                cid = str(msg.get("arg", "none")).lower()
                if costumes is None:
                    return {"ok": False, "error": "costumes module missing"}
                if cid not in {x[0] for x in costumes.COSTUMES}:
                    return {"ok": False, "error": f"unknown costume: {cid}"}
                self.costume = cid
            elif cmd == "marquee":
                self.marquee = str(msg.get("arg", ""))
            elif cmd == "size":
                arg = str(msg.get("arg", "full")).lower()
                if arg not in ("full", "mini"):
                    return {"ok": False, "error": f"unknown size: {arg}"}
                self.size = arg
            elif cmd == "qr":
                # The glass IS a Micro QR: format M3 is exactly 15x15
                # modules, and the dark bezel doubles as the quiet zone.
                # Lit = dark modules (inverted QR; scanners handle it).
                try:
                    import segno
                except ImportError:
                    return {"ok": False,
                            "error": "pip install segno for QR support"}
                data = str(msg.get("arg", "CLAWDPAD"))
                try:
                    q = segno.make(data, micro=True)
                except Exception as e:
                    return {"ok": False, "error": f"cannot encode: {e}"}
                m = [list(row) for row in q.matrix]
                if len(m) > H or len(m[0]) > W:
                    return {"ok": False,
                            "error": f"payload too big for M3 ({data!r})"}
                pad = (H - len(m)) // 2  # M1/M2 come out smaller; center them
                grid = [[False] * W for _ in range(H)]
                for y, row in enumerate(m):
                    for x, v in enumerate(row):
                        grid[y + pad][x + pad] = bool(v)
                self.qr_matrix = grid
                self.qr_until = now + float(msg.get("seconds", 30))
            elif cmd == "names":
                if not self.devices:
                    return {"ok": False, "error": "no block connected"}
                self.roll_call_until = time.monotonic() + ROLL_CALL_SECONDS
            elif cmd == "game":
                arg = str(msg.get("arg", "pong")).lower()
                if arg in ("off", "stop"):
                    self.game = None
                elif arg == "pong":
                    n = max(1, len(self.devices))
                    mono = time.monotonic()
                    self.game = {"kind": "pong", "n": n, "fw": W * n,
                                 "bx": W * n / 2, "by": H / 2,
                                 "vx": PONG_SPEED,
                                 "vy": random.choice((-4.5, 4.5)),
                                 "paddles": {"L": H / 2, "R": H / 2},
                                 "score": [0, 0], "last": mono,
                                 "serve_until": mono + 1.2}
                else:
                    return {"ok": False, "error": f"unknown game: {arg}"}
            elif cmd == "visit":
                others = [u for u in self.devices if u != self.home]
                if not others:
                    return {"ok": False, "error": "no second block connected"}
                if not self.visit:
                    self.visit = (self.home, others[0], time.monotonic())
            elif cmd == "clear":
                self.notify_until = 0.0
                self.notify_text = ""
                self.manual = None
                self.qr_until = 0.0
            elif cmd in ("status", "ping"):
                pass
            else:
                return {"ok": False, "error": f"unknown cmd: {cmd}"}
        home_serial = self.dev_serials.get(self.home, "")
        return {"ok": True, "mood": self.mood(now), "block": dict(self.block),
                "home": self.block_names.get(home_serial)
                or home_serial[-4:],
                "names": {s: self.block_names.get(s) or s[-4:]
                          for s in self.dev_serials.values()},
                "size": self.size,
                "costume": self.costume,
                "energy": round(self.energy, 3),
                "pet": dict(self.pet) if self.pet else None,
                "notify_text": self.notify_text if now < self.notify_until else "",
                "sessions": {sid: {"project": p, "mode": m, "age": int(now - t)}
                             for sid, (p, m, t) in self.sessions.items()},
                "uptime": int(now - self.started)}

    def tick(self, dt):
        """Decay work energy once per rendered frame; returns current level."""
        with self.lock:
            self.energy *= math.exp(-dt / ENERGY_TAU)
            return self.energy

    # ── Touch ────────────────────────────────────────────────────────────

    def touch_snapshot(self):
        with self.lock:
            return tuple(self.touch[:3]) if self.touch else None

    def notice_look(self, now):
        with self.lock:
            if self.notice and now < self.notice[1]:
                return self.notice[0]
            self.notice = None
        return None

    def touch_start(self, now, x, y, z):
        """Returns "ack" if this tap acknowledged a notify, else None."""
        with self.lock:
            if now < self.notify_until:
                self.notify_until = 0.0
                self.notify_text = ""
                return "ack"
            self.touch = [x, y, z, now]
        return None

    def touch_move(self, x, y, z):
        with self.lock:
            if self.touch:
                self.touch[0:3] = [x, y, z]

    def touch_end(self, now):
        """Tap bookkeeping.

        1 tap → he looks at you · 2 taps → celebrate jump ·
        3 taps → toggle full/mini (the jump morphs into the resize).
        """
        with self.lock:
            held, self.touch = self.touch, None
            if held is None or now - held[3] > TAP_MAX_SECONDS:
                return None  # that was petting, not a tap
            self.taps = [t for t in self.taps
                         if now - t < DOUBLE_TAP_WINDOW] + [now]
            if len(self.taps) >= 3:
                self.taps.clear()
                self.notice = None
                self.oneshot_until = 0.0  # cancel the double-tap jump
                self.size = "mini" if self.size == "full" else "full"
                return f"resize:{self.size}"
            if len(self.taps) == 2:
                self.notice = None
                self.celebrate(now)
                return "jump"
            # single tap: he looks at where you tapped for a moment
            look = max(-1, min(1, round((held[0] * (W - 1) - 7) * 0.2)))
            self.notice = (look, now + NOTICE_SECONDS)
        return None

    # ── Two blocks, one Clawd ────────────────────────────────────────────

    def start_visit(self, to_uid, mono):
        """Send Clawd walking to another glass (no-op mid-hop or at home)."""
        with self.lock:
            if self.visit or to_uid == self.home \
                    or to_uid not in self.devices:
                return False
            self.visit = (self.home, to_uid, mono)
            return True

    def visit_pose(self, mono):
        """Progress of the hop in flight; retires it when the walk is done."""
        with self.lock:
            if not self.visit:
                return None
            frm, to, t0 = self.visit
            p = (mono - t0) / VISIT_SECONDS
            if p >= 1.0 or to not in self.devices \
                    or frm not in self.devices:
                self.visit = None
                if to in self.devices:
                    self.home = to
                return None
            return frm, to, p

    def start_reunion(self, mono):
        """The blocks just snapped together; celebrate once, not per-event."""
        with self.lock:
            if mono < self.reunion_until:
                return False
            self.reunion_until = mono + REUNION_SECONDS
            return True

    def name_of(self, uid):
        """A block's display name: configured, or the serial's last 4."""
        with self.lock:
            serial = self.dev_serials.get(uid, "")
            return self.block_names.get(serial) or serial[-4:] or "?"

    def maybe_wander(self, mono):
        """Awake Clawd drifts to another glass now and then, like a cat."""
        with self.lock:
            if self.visit or self.linked or len(self.devices) < 2:
                return
            if self.next_wander == 0.0 or mono < self.next_wander:
                if self.next_wander == 0.0:
                    self.next_wander = mono + random.uniform(*WANDER_EVERY)
                return
            self.next_wander = mono + random.uniform(*WANDER_EVERY)
            others = [u for u in self.devices if u != self.home]
            self.visit = (self.home, random.choice(others), mono)

    # ── Pong across the glasses ──────────────────────────────────────────

    def game_step(self, mono):
        """Advance pong physics; returns True while a game is on.

        The field is W*n_blocks wide. Two blocks: a paddle on each outer
        edge, one player per glass. One block: the left edge is a wall
        and the score counts the rally.
        """
        with self.lock:
            g = self.game
            if not g:
                return False
            dt = min(0.1, mono - g["last"])
            g["last"] = mono
            if mono < g["serve_until"]:
                return True
            single = g["n"] <= 1
            g["bx"] += g["vx"] * dt
            g["by"] += g["vy"] * dt
            if g["by"] < 1:
                g["by"], g["vy"] = 1, abs(g["vy"])
            elif g["by"] > H - 2:
                g["by"], g["vy"] = H - 2, -abs(g["vy"])
            point = None
            if g["bx"] < 2:
                if single:
                    g["bx"], g["vx"] = 2, abs(g["vx"])
                elif abs(g["by"] - g["paddles"]["L"]) <= PONG_PADDLE / 2 + 1:
                    g["bx"] = 2
                    g["vx"] = min(22.0, abs(g["vx"]) * 1.05)
                    g["vy"] += (g["by"] - g["paddles"]["L"]) * 1.8
                else:
                    point = 1                     # right player scores
            elif g["bx"] > g["fw"] - 3:
                if abs(g["by"] - g["paddles"]["R"]) <= PONG_PADDLE / 2 + 1:
                    g["bx"] = g["fw"] - 3
                    g["vx"] = -min(22.0, abs(g["vx"]) * 1.05)
                    g["vy"] += (g["by"] - g["paddles"]["R"]) * 1.8
                    if single:                    # a rally point per return
                        g["score"][1] += 1
                else:
                    point = 0                     # left player scores
            if point is not None:
                if single:
                    g["score"][1] = 0             # rally over
                else:
                    g["score"][point] += 1
                g["bx"], g["by"] = g["fw"] / 2, H / 2
                g["vx"] = PONG_SPEED if point == 0 else -PONG_SPEED
                g["vy"] = random.choice((-4.5, 4.5))
                g["serve_until"] = mono + 1.2
                player = self.player
            else:
                player = None
            g["vy"] = max(-9.0, min(9.0, g["vy"]))
        if player:
            player.play("chime")
        return True

    def game_touch(self, uid, y):
        """A finger anywhere on a glass drives that glass's paddle."""
        with self.lock:
            g = self.game
            if not g or not self.devices:
                return
            side = "R" if len(self.devices) <= 1 \
                or uid == self.devices[-1] else "L"
            g["paddles"][side] = max(PONG_PADDLE / 2,
                                     min(H - 1 - PONG_PADDLE / 2,
                                         y * (H - 1)))

    def game_snapshot(self):
        with self.lock:
            return dict(self.game, paddles=dict(self.game["paddles"])) \
                if self.game else None

    # ── Soul link ────────────────────────────────────────────────────────

    def pet_vigor(self):
        with self.lock:
            mood = self.pet["mood"] if self.pet else "content"
        return PET_VIGOR.get(mood, 1.0)


# --------------------------------------------------------------------- music

SAMPLE_RATE = 22050
JINGLE_COOLDOWN = 30.0  # auto-jingles (celebrate) at most this often

# melodies: (pitch-or-chord midi, start seconds, duration seconds)
MELODIES = {
    "jingle": [(72, 0.00, 0.14), (76, 0.14, 0.14), (79, 0.28, 0.14),
               (84, 0.42, 0.20), ([72, 76, 79, 84], 0.66, 0.55)],
    "hello": [(55, 0.00, 0.18), (60, 0.18, 0.18), (64, 0.36, 0.40)],
    "chime": [(88, 0.00, 0.16), (84, 0.20, 0.30)],
}
HUM_CHORD = (48, 55, 64)   # C3 G3 E4 — the pad Clawd hums while thinking
HUM_SECONDS = 8.0


def _note_freq(midi):
    return 440.0 * 2 ** ((midi - 69) / 12)


def _render_melody(notes, gain=0.30):
    """Additive bell voice (fundamental + 2 partials, exp decay) -> floats."""
    total = max(s + d for _, s, d in notes) + 0.9  # room for release tails
    buf = [0.0] * int(total * SAMPLE_RATE)
    for pitch, start, dur in notes:
        chord = pitch if isinstance(pitch, (list, tuple)) else [pitch]
        for midi in chord:
            f = _note_freq(midi)
            i0 = int(start * SAMPLE_RATE)
            for i in range(int((dur + 0.8) * SAMPLE_RATE)):
                if i0 + i >= len(buf):
                    break
                t = i / SAMPLE_RATE
                env = math.exp(-3.2 * t) * min(1.0, t * 200)  # no click
                s = (math.sin(2 * math.pi * f * t)
                     + 0.35 * math.sin(2 * math.pi * 2 * f * t)
                     + 0.12 * math.sin(2 * math.pi * 3.01 * f * t))
                buf[i0 + i] += s * env / len(chord)
    return buf, gain


def _render_hum():
    """Quiet slow-breathing pad; fades at both ends so looping is seamless."""
    n = int(HUM_SECONDS * SAMPLE_RATE)
    buf = [0.0] * n
    for k, midi in enumerate(HUM_CHORD):
        f = _note_freq(midi)
        for i in range(n):
            t = i / SAMPLE_RATE
            lfo = 0.6 + 0.4 * math.sin(2 * math.pi * t / (3.1 + k))
            buf[i] += lfo * (math.sin(2 * math.pi * f * t)
                             + 0.2 * math.sin(2 * math.pi * 2 * f * t))
    fade = int(0.5 * SAMPLE_RATE)
    for i in range(fade):
        g = i / fade
        buf[i] *= g
        buf[n - 1 - i] *= g
    return buf, 0.10


def _write_wav(path, samples, gain):
    peak = max(1e-9, max(abs(v) for v in samples))
    scale = gain * 32767 / peak
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(b"".join(
            struct.pack("<h", int(v * scale)) for v in samples))


class Player:
    """Renders melodies to cached WAVs and plays them via pw-play/aplay.

    All methods are safe from any thread; playback is fire-and-forget
    subprocesses so the render loop never blocks on audio.
    """

    def __init__(self):
        self.dir = os.path.dirname(command_socket())
        self.bin = (shutil.which("pw-play") or shutil.which("aplay")
                    or shutil.which("afplay"))  # afplay: macOS hosts
        self.proc = None
        self.hum_proc = None
        self.last_auto_jingle = 0.0
        if self.bin is None:
            log("no pw-play/aplay found — music disabled")

    def _wav(self, name):
        path = os.path.join(self.dir, f"{name}.wav")
        if not os.path.exists(path):
            samples, gain = (_render_hum() if name == "hum"
                             else _render_melody(MELODIES[name]))
            _write_wav(path, samples, gain)
            log(f"rendered {name}.wav ({os.path.getsize(path)} bytes)")
        return path

    def play(self, name):
        """Play a named melody now. Returns False if audio is unavailable."""
        if self.bin is None or name not in MELODIES:
            return False
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
        self.proc = subprocess.Popen(
            [self.bin, self._wav(name)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True

    def auto_jingle(self, now):
        """Celebrate-triggered jingle, rate-limited so storms stay calm."""
        if now - self.last_auto_jingle < JINGLE_COOLDOWN:
            return
        self.last_auto_jingle = now
        self.play("jingle")

    def hum_running(self):
        return self.hum_proc is not None and self.hum_proc.poll() is None

    def hum_start(self):
        if self.bin is None or self.hum_running():
            return
        self.hum_proc = subprocess.Popen(
            [self.bin, self._wav("hum")],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def hum_stop(self):
        if self.hum_running():
            self.hum_proc.terminate()


def pet_loop(state):
    """One soul, two bodies: mirror Clawd's life from dazzler's state.json.

    Optional — if the file never appears, Clawd lives at full vigor.
    Level-ups jump + jingle; petd whispers chime; hunger reaches the
    renderer via State.pet_vigor().
    """
    last = None
    while True:
        try:
            with open(PET_STATE) as fh:
                pet = json.load(fh)
        except (OSError, ValueError):
            time.sleep(15)
            continue
        now = time.time()
        with state.lock:
            state.pet = {"level": pet.get("level", 1),
                         "hunger": float(pet.get("hunger", 50.0)),
                         "mood": pet.get("mood", "content"),
                         "xp": pet.get("xp", 0)}
        if last is not None:
            if pet.get("level", 1) > last.get("level", 1):
                log(f"Clawd leveled up → {pet.get('level')}!")
                with state.lock:
                    state.celebrate(now)
                if state.player:
                    state.player.play("jingle")
            w_new = pet.get("whispers") or []
            w_old = last.get("whispers") or []
            if w_new and (not w_old or w_new[-1] > w_old[-1]):
                if state.player:
                    state.player.play("chime")
        last = pet
        time.sleep(5)


def hum_loop(state, player):
    """Clawd hums (quietly) while thinking, when enabled."""
    while True:
        humming = state.hum_enabled and state.mood(time.time()) == "thinking"
        if humming and not player.hum_running():
            player.hum_start()   # 8s pad; re-started each time it runs out
        elif not humming and player.hum_running():
            player.hum_stop()
        time.sleep(0.5)


# ---------------------------------------------------------------- animations

def _blit(buf, x, y, color):
    if 0 <= x < W and 0 <= y < H:
        i = (y * W + x) * 3
        buf[i], buf[i + 1], buf[i + 2] = color


def _clawd(brightness, dx=0, dy=0, eyes="open", look=0,
           arm_l_dy=0, arm_r_dy=0):
    """Render Clawd — the actual Claude Code icon as 15x15 pixel art.

    dx/dy shift the whole creature (pace/bob/jump); `eyes` is
    "open"|"closed"; `look` shifts the eye holes sideways; arm_*_dy raise
    (negative) or droop an arm. Eyes are holes (unlit), like the icon.
    """
    buf = bytearray(W * H * 3)
    col = tuple(min(255, int(c * brightness)) for c in CORAL)

    def rect(x0, y0, x1, y1, oy=0):
        for y in range(y0 + dy + oy, y1 + dy + oy):
            for x in range(x0 + dx, x1 + dx):
                _blit(buf, x, y, col)

    rect(*CLAWD_BODY)
    rect(*CLAWD_ARMS[0], oy=arm_l_dy)
    rect(*CLAWD_ARMS[1], oy=arm_r_dy)
    for leg in CLAWD_LEGS:
        rect(*leg)
    for ex, ey in CLAWD_EYES:
        x = ex + dx + look
        _blit(buf, x, ey + 1 + dy, (0, 0, 0))
        if eyes == "open":
            _blit(buf, x, ey + dy, (0, 0, 0))
    return buf


def _mini(brightness, px, py, eyes="open", look=0, arms="down"):
    """Render chibi-Clawd with his body's top-left at (px, py).

    Same soul, quarter the pixels: 5x4 body, 1px arm nubs (raised when
    arms="up"), two legs, 1px eye holes (a blink just closes them).
    """
    buf = bytearray(W * H * 3)
    col = tuple(min(255, int(c * brightness)) for c in CORAL)
    for y in range(4):
        for x in range(5):
            _blit(buf, px + x, py + y, col)
    ay = py + (0 if arms == "up" else 2)
    _blit(buf, px - 1, ay, col)
    _blit(buf, px + 5, ay, col)
    _blit(buf, px + 1, py + 4, col)   # legs
    _blit(buf, px + 3, py + 4, col)
    if eyes == "open":
        _blit(buf, px + 1 + look, py + 1, (0, 0, 0))
        _blit(buf, px + 3 + look, py + 1, (0, 0, 0))
    return buf


def _mini_frame(mood, t, phase, touch, vigor):
    """Mini-mode composition: a small Clawd roaming a big room."""
    blink = (t % 4.3) < 0.13
    if mood == "celebrate":
        bounce = abs(math.sin(t * math.pi / 0.6))
        return _mini(1.0, 5, 6 - round(3 * bounce), "open", 0, arms="up")
    if mood == "notify":
        pulse = (0.78 + 0.22 * math.sin(t * 2 * math.pi * 1.4)) \
            * max(0.7, vigor)
        arms = "up" if (t * 2.4) % 1.0 < 0.5 else "down"
        return _mini(pulse, 5, 5, "closed" if blink else "open", 0, arms)
    if mood == "sleep":
        breath = 0.26 + 0.08 * math.sin(t * 2 * math.pi / 9.0)
        peek = (t % 9.7) < 0.4
        if touch is not None:
            breath = min(0.7, breath + 0.45 * touch[2])
            peek = True
        return _mini(breath, 8, 8, "open" if peek else "closed", 0)
    if touch is not None:  # he walks toward your finger, glowing
        tx, ty, tz = touch
        px = max(1, min(9, round(tx * (W - 1)) - 2))
        py = max(0, min(9, round(ty * (H - 1)) - 2))
        return _mini(min(1.0, 0.85 + 0.35 * tz) * vigor, px, py,
                     "closed" if blink else "open", 0)
    if mood == "thinking":  # pacing a shorter beat, same energy clock
        px = 5 + round(3.5 * math.sin(phase * 0.5))
        look = 1 if math.cos(phase * 0.5) > 0.25 else \
            (-1 if math.cos(phase * 0.5) < -0.25 else 0)
        return _mini(0.9, px, 6, "closed" if (t % 2.1) < 0.09 else "open",
                     look)
    # awake: roaming the room on slow, wandering paths
    px = max(1, min(9, round(5 + 4.2 * math.sin(t * 0.09))))
    py = max(0, min(9, round(4 + 3.2 * math.sin(t * 0.067 + 1.3))))
    brightness = (0.72 + 0.28 * math.sin(t * 2 * math.pi / 6.5)) * vigor
    if vigor <= PET_VIGOR["starving"]:
        brightness *= 0.88 + 0.12 * math.sin(t * 13.7)
    look = round(0.9 * math.sin(t * 0.31))
    return _mini(brightness, px, py, "closed" if blink else "open", look)


def _touch_pose(touch):
    """Shared petting math: lean offsets, gaze, pressure glow."""
    tx, ty, tz = touch
    fx, fy = tx * (W - 1) - 7, ty * (H - 1) - 7
    dx = max(-2, min(2, round(fx * 0.3)))
    dy = max(-1, min(1, round(fy * 0.2)))
    look = max(-1, min(1, round(fx * 0.2)))
    return dx, dy, look, tz


def frame_awake(t, touch=None, vigor=1.0, notice=None, xoff=0):
    """Clawd awake: breathes, bobs, paces a little, blinks, glances around.

    Petting leans him toward your finger with pressure glow and tracking
    eyes; a single tap (`notice`) holds his gaze for a moment. Vigor
    mirrors hunger — a hungry Clawd burns low, a starving one gutters
    (feed him: ~/dazzler/feed/). `xoff` shifts his whole world sideways —
    linked blocks render one wide room as per-glass windows.
    """
    breath = 0.72 + 0.28 * math.sin(t * 2 * math.pi / 6.5)
    if touch is not None:
        dx, dy, look, tz = _touch_pose(touch)
        brightness = min(1.0, breath + 0.35 * tz)
    else:
        dx = round(1.5 * math.sin(t * 0.13))
        dy = round(0.5 * math.sin(t * 2 * math.pi / 6.5))
        look = notice if notice is not None else round(0.9 * math.sin(t * 0.31))
        brightness = breath
    brightness *= vigor
    if vigor <= PET_VIGOR["starving"]:
        brightness *= 0.88 + 0.12 * math.sin(t * 13.7)
    blink = (t % 4.3) < 0.13
    return _clawd(brightness, dx + xoff, dy,
                  "closed" if blink else "open", look)


def frame_thinking(phase, t, touch=None, notice=None, xoff=0):
    """Clawd hard at work: pacing back and forth, eyes leading the way.

    `phase` accumulates at 2.5+4.5*energy rad/s in the render loop, so he
    paces visibly faster the harder Claude is working — and winds down
    when the work does. Quick busy blinks.
    """
    if touch is not None:
        dx, dy, look, tz = _touch_pose(touch)
        brightness = min(1.0, 0.9 + 0.35 * tz)
    else:
        dx = round(2.2 * math.sin(phase * 0.5))
        dy = 0
        vel = math.cos(phase * 0.5)
        look = notice if notice is not None else \
            (1 if vel > 0.25 else (-1 if vel < -0.25 else 0))
        brightness = 0.9
    blink = (t % 2.1) < 0.09
    return _clawd(brightness, dx + xoff, dy,
                  "closed" if blink else "open", look)


def frame_sleep(t, touch=None):
    """Clawd asleep: dim, slow breathing, eyes closed, occasional peek.

    Petting warms him and half-wakes the eyes, like disturbing anyone
    at 3am.
    """
    breath = 0.26 + 0.08 * math.sin(t * 2 * math.pi / 9.0)
    peek = (t % 9.7) < 0.4
    if touch is not None:
        breath = min(0.7, breath + 0.45 * touch[2])
        peek = True
    return _clawd(breath, 0, round(0.5 * math.sin(t * 2 * math.pi / 9.0)),
                  "open" if peek else "closed", 0)


def frame_notify(t, vigor=1.0):
    """Clawd needs you: right arm raised, waving, gentle pulse. Tap to ack."""
    pulse = (0.78 + 0.22 * math.sin(t * 2 * math.pi * 1.4)) * max(0.7, vigor)
    wave_up = (t * 2.4) % 1.0 < 0.5
    blink = (t % 4.3) < 0.13
    return _clawd(pulse, 0, 0, "closed" if blink else "open", 0,
                  arm_r_dy=-2 if wave_up else -1)


def frame_celebrate(rel):
    """Task landed: both arms up, jumping. (dazzler's celebrate, in 15x15.)"""
    bounce = abs(math.sin(rel * math.pi / 0.6))  # two full hops per burst
    return _clawd(1.0, 0, -round(2 * bounce), "open", 0,
                  arm_l_dy=-2, arm_r_dy=-2)


def frame_empty(t):
    """A glass with nobody home: a faint ember night-light, breathing."""
    buf = bytearray(W * H * 3)
    glow = 0.10 + 0.05 * math.sin(t * 2 * math.pi / 9.0)
    col = tuple(int(c * glow) for c in CORAL)
    for y in (7, 8):
        for x in (7, 8):
            _blit(buf, x, y, col)
    return buf


def _glyph_big(buf, key, col):
    """A font glyph at double size, centered — score digits, the heart."""
    rows = _MARQUEE_FONT[key]
    for r in range(5):
        for c in range(3):
            if rows[r][c] == "1":
                for oy in (0, 1):
                    for ox in (0, 1):
                        _blit(buf, 4 + c * 2 + ox, 2 + r * 2 + oy, col)


def frame_heart(t):
    """A big pulsing heart — the other half of a reunion."""
    buf = bytearray(W * H * 3)
    pulse = 0.55 + 0.35 * math.sin(t * 2 * math.pi * 1.1)
    _glyph_big(buf, "<3", tuple(int(c * pulse) for c in CORAL))
    return buf


def frame_pong(g, block_i, mono):
    """One glass of the pong field: outer-edge paddles, a 2x2 ball.

    Serve pauses show the score as a big double-size digit (the rally
    count in single-block wall-ball). Everything chunky, per the rules
    of the woven glass.
    """
    buf = bytearray(W * H * 3)
    n = g["n"]
    if mono < g["serve_until"]:
        s = g["score"][0] if (n > 1 and block_i == 0) else g["score"][1]
        _glyph_big(buf, str(s % 10), tuple(int(c * 0.55) for c in CORAL))
        return buf
    pad = tuple(int(c * 0.9) for c in CORAL)
    half = PONG_PADDLE // 2
    if n == 1:
        wall = tuple(int(c * 0.18) for c in CORAL)
        for y in range(H):
            _blit(buf, 0, y, wall)
    elif block_i == 0:
        ly = round(g["paddles"]["L"])
        for y in range(ly - half, ly - half + PONG_PADDLE):
            _blit(buf, 0, y, pad)
            _blit(buf, 1, y, pad)
    if block_i == n - 1:
        ry = round(g["paddles"]["R"])
        for y in range(ry - half, ry - half + PONG_PADDLE):
            _blit(buf, 13, y, pad)
            _blit(buf, 14, y, pad)
    bx, by = round(g["bx"]) - block_i * W, round(g["by"])
    for oy in (0, 1):
        for ox in (0, 1):
            _blit(buf, bx + ox, by - 1 + oy, (235, 235, 235))
    return buf


def frame_visit(t, p, leaving, direction):
    """One glass of a hop: Clawd walks off the old block, onto the new.

    `p` runs 0..1 over the whole hop — the first half leaves, the second
    half arrives. 18px of dx clears the glass completely; the hurried
    walk-bob and the eyes leading toward `direction` sell the trip.
    """
    if leaving:
        prog = min(1.0, p * 2.0)
        dx = direction * round(prog * 18)
    else:
        prog = max(0.0, p * 2.0 - 1.0)
        dx = -direction * round((1.0 - prog) * 18)
    dy = -1 if int(t * 7) % 2 else 0
    return _clawd(0.92, dx, dy, "open", direction)



_MARQUEE_FONT = {
    "A": ("010","101","111","101","101"), "B": ("110","101","110","101","110"),
    "C": ("011","100","100","100","011"), "D": ("110","101","101","101","110"),
    "E": ("111","100","110","100","111"), "F": ("111","100","110","100","100"),
    "G": ("011","100","101","101","011"), "H": ("101","101","111","101","101"),
    "I": ("111","010","010","010","111"), "J": ("001","001","001","101","010"),
    "K": ("101","110","100","110","101"), "L": ("100","100","100","100","111"),
    "M": ("101","111","111","101","101"), "N": ("101","111","111","111","101"),
    "O": ("010","101","101","101","010"), "P": ("110","101","110","100","100"),
    "Q": ("010","101","101","011","001"), "R": ("110","101","110","110","101"),
    "S": ("011","100","010","001","110"), "T": ("111","010","010","010","010"),
    "U": ("101","101","101","101","111"), "V": ("101","101","101","101","010"),
    "W": ("101","101","111","111","101"), "X": ("101","101","010","101","101"),
    "Y": ("101","101","010","010","010"), "Z": ("111","001","010","100","111"),
    "0": ("111","101","101","101","111"), "1": ("010","110","010","010","111"),
    "2": ("111","001","111","100","111"), "3": ("111","001","011","001","111"),
    "4": ("101","101","111","001","001"), "5": ("111","100","111","001","111"),
    "6": ("111","100","111","101","111"), "7": ("111","001","001","010","010"),
    "8": ("111","101","111","101","111"), "9": ("111","101","111","001","111"),
    "!": ("010","010","010","000","010"), "?": ("111","001","011","000","010"),
    "-": ("000","000","111","000","000"), ".": ("000","000","000","000","010"),
    " ": ("000","000","000","000","000"), ":": ("000","010","000","010","000"),
    "<3": ("000","101","111","111","010"),
}


def _marquee_frame(text, t, block=0, span=1):
    """Scroll `text` right-to-left across the glass in Claude coral.

    With several blocks in a row, `block`/`span` render one 15px window
    of a single wide ribbon that flows across all of them.
    """
    buf = bytearray(W * H * 3)
    glyphs = [_MARQUEE_FONT.get(ch, _MARQUEE_FONT["?"]) for ch in text.upper()]
    width = len(glyphs) * 4
    gx = span * W - (int(t * 11) % (width + span * W)) - block * W
    for rows in glyphs:
        for r in range(5):
            for col in range(3):
                if rows[r][col] == "1":
                    _blit(buf, gx + col, 5 + r, CORAL)
        gx += 4
    return buf


def build_frame(mood, t, phase, state, touch):
    now = time.time()
    with state.lock:
        marquee, costume = state.marquee, state.costume
    if costume == "none" and state.away_flair and costumes is not None:
        costume = "scarf"   # he's out visiting; he dresses for the trip
    # marquee + costumes take over the calm moods (not qr/notify/celebrate)
    if marquee and mood in ("awake", "sleep", "thinking"):
        return _marquee_frame(marquee, t)
    if costume != "none" and costumes is not None and \
            mood in ("awake", "sleep", "thinking"):
        breath = 0.72 + 0.28 * math.sin(t * 2 * math.pi / 6.5)
        dx = round(1.5 * math.sin(t * 0.13))
        dy = round(0.5 * math.sin(t * 2 * math.pi / 6.5))
        look = round(0.9 * math.sin(t * 0.31))
        blink = (t % 4.3) < 0.13
        return bytearray(costumes.dressed(costume,
            breath * state.pet_vigor(), dx, dy, not blink, look, t))
    if mood == "qr":
        buf = bytearray(W * H * 3)
        with state.lock:
            grid = state.qr_matrix
        for y in range(H):
            for x in range(W):
                if grid[y][x]:
                    _blit(buf, x, y, (235, 235, 235))
        return buf
    with state.lock:
        size = state.size
    if size == "mini":
        return _mini_frame(mood, t, phase, touch, state.pet_vigor())
    notice = state.notice_look(now)
    if mood == "thinking":
        return frame_thinking(phase, t, touch, notice)
    if mood == "sleep":
        return frame_sleep(t, touch)
    if mood == "notify":
        return frame_notify(t, state.pet_vigor())
    if mood == "celebrate":
        with state.lock:
            rel = CELEBRATE_SECONDS - (state.oneshot_until - now)
        return frame_celebrate(max(0.0, rel))
    return frame_awake(t, touch, state.pet_vigor(), notice)


def build_frames(mood, t, phase, state, touch, mono):
    """One frame per connected block.

    A lone block is exactly the classic behavior. With more, Clawd
    inhabits one glass (state.home) and the others hold a night-light;
    takeover moods (qr/notify/celebrate) mirror everywhere, a marquee
    spans the row of glasses as one wide ribbon, and a visit in flight
    walks him from one glass to the next.
    """
    with state.lock:
        devices = list(state.devices)
        marquee = state.marquee
        roll_call = state.roll_call_until
        reunion = state.reunion_until
        home_now = state.home
        serials = dict(state.dev_serials)
        home_serial_cfg = state.home_serial
    game = state.game_snapshot()
    if game and devices:
        return {u: frame_pong(game, i, mono)
                for i, u in enumerate(devices)}
    if devices and mono < reunion:
        # the snap: Clawd jumps for joy, every other glass beams a heart
        rel = mono - (reunion - REUNION_SECONDS)
        return {u: frame_celebrate(rel % CELEBRATE_SECONDS)
                if u == home_now else frame_heart(t) for u in devices}
    if devices and mono < roll_call:
        # name tags: each glass scrolls its own name
        return {u: _marquee_frame(state.name_of(u), t) for u in devices}
    if len(devices) <= 1:
        state.away_flair = bool(
            devices and serials.get(devices[0], "") != home_serial_cfg)
        return {u: build_frame(mood, t, phase, state, touch)
                for u in devices}
    if marquee and mood in ("awake", "sleep", "thinking"):
        return {u: _marquee_frame(marquee, t, i, len(devices))
                for i, u in enumerate(devices)}
    if mood in ("qr", "notify", "celebrate"):
        frame = build_frame(mood, t, phase, state, touch)
        return {u: frame for u in devices}
    pose = state.visit_pose(mono)
    if pose:
        frm, to, p = pose
        direction = 1 if devices.index(to) > devices.index(frm) else -1
        frames = {u: frame_empty(t) for u in devices}
        frames[frm] = frame_visit(t, p, True, direction)
        frames[to] = frame_visit(t, p, False, direction)
        return frames
    with state.lock:
        linked = state.linked
    if linked and mood in ("awake", "thinking"):
        # snapped: the wall is gone — one wide room, roamed end to end
        # (he'll happily sit straddling the seam)
        state.away_flair = False
        span = W * (len(devices) - 1)
        wx = round(span / 2 * (1 + math.sin(t * 0.09)))
        vigor = state.pet_vigor()
        notice = state.notice_look(time.time())
        frames = {}
        for i, u in enumerate(devices):
            xoff = wx - W * i
            if mood == "thinking":
                frames[u] = frame_thinking(phase, t, touch, notice,
                                           xoff=xoff)
            else:
                frames[u] = frame_awake(t, touch, vigor, notice,
                                        xoff=xoff)
        return frames
    with state.lock:
        home = state.home
    frames = {u: frame_empty(t) for u in devices}
    if home in frames:
        state.away_flair = serials.get(home, "") != home_serial_cfg
        frames[home] = build_frame(mood, t, phase, state, touch)
    return frames


# ------------------------------------------------------------------ plumbing

def log(msg):
    print(time.strftime("%H:%M:%S"), msg, flush=True)


def load_config():
    path = os.path.expanduser("~/.config/clawdpad/config.json")
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def discover_blocks(sock):
    """All LED-grid devices blocksd can see — DNA-snapped neighbors and
    extra USB blocks alike. Every one of them gets a Clawd."""
    sock.sendall(b'{"type": "discover", "id": "cpd-1"}\n')
    buf = b""
    while b"\n" not in buf:
        chunk = sock.recv(4096)
        if not chunk:
            raise ConnectionError("blocksd closed during discover")
        buf += chunk
    devs, seen = [], set()
    for dev in json.loads(buf.split(b"\n")[0]).get("devices", []):
        # DNA-snapped while both stay on USB: the same block can appear
        # through both port groups — one Clawd per glass, not per cable
        if dev.get("grid_width") and dev.get("grid_height") \
                and dev.get("uid") not in seen:
            seen.add(dev.get("uid"))
            devs.append(dev)
    return devs


def peek_device_count():
    """Cheap out-of-band device count (own short-lived connection), so the
    render loop can notice a friend's block snapping on mid-stream."""
    path = blocksd_socket()
    if path is None:
        return -1
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.settimeout(2.0)
            sock.connect(path)
            return len(discover_blocks(sock))
    except (OSError, ValueError):
        return -1


def render_loop(state):
    """Own the blocksd frame stream; reconnect forever, quietly."""
    start = time.monotonic()
    announced_wait = False
    while True:
        path = blocksd_socket()
        if path is None:
            if not announced_wait:
                log("waiting for blocksd socket…")
                announced_wait = True
            time.sleep(3)
            continue
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
                sock.connect(path)
                devs = discover_blocks(sock)
                if not devs:
                    with state.lock:
                        state.block = {"connected": False, "serial": "",
                                       "battery": None}
                        state.devices = []
                    if not announced_wait:
                        log("blocksd up, block absent — will keep checking")
                        announced_wait = True
                    time.sleep(3)
                    continue
                announced_wait = False
                master = devs[0]
                with state.lock:
                    state.block = {"connected": True,
                                   "serial": master["serial"],
                                   "battery": master.get("battery_level"),
                                   "blocks": len(devs)}
                    state.devices = [d["uid"] for d in devs]
                    state.dev_serials = {d["uid"]: d["serial"]
                                         for d in devs}
                    state.home = next(
                        (d["uid"] for d in devs
                         if d["serial"] == state.home_serial),
                        devs[0]["uid"])
                    state.visit = None
                    state.next_wander = 0.0
                    if len(devs) > 1:   # friends announce themselves
                        state.roll_call_until = (time.monotonic()
                                                 + ROLL_CALL_SECONDS)
                log("streaming to "
                    + ", ".join(f"{state.name_of(d['uid'])}"
                                f" ({d['serial']})" for d in devs)
                    + f" (battery {master.get('battery_level')}%)")
                headers = {d["uid"]: struct.pack("<BBQ", 0xBD, 0x01,
                                                 d["uid"])
                           for d in devs}
                rejects = 0
                frames_sent = 0
                phase = 0.0
                last = time.monotonic()
                while True:
                    now = time.time()
                    mood = state.mood(now)
                    mono = time.monotonic()
                    dt, last = mono - last, mono
                    energy = state.tick(dt)
                    phase += dt * (2.5 + 4.5 * energy)
                    touch = state.touch_snapshot()
                    game_on = state.game_step(mono)
                    if not game_on and len(devs) > 1 and mood == "awake" \
                            and touch is None:
                        state.maybe_wander(mono)
                    frames = build_frames(mood, mono - start, phase, state,
                                          touch, mono)
                    accepted = 0
                    for uid, header in headers.items():
                        sock.sendall(header + frames[uid])
                        ack = sock.recv(1)
                        if not ack:
                            raise ConnectionError("blocksd closed")
                        accepted += ack == b"\x01"
                    rejects = 0 if accepted else rejects + 1
                    if rejects > 60:  # all blocks gone; re-discover
                        raise ConnectionError("frames not accepted")
                    frames_sent += 1
                    if frames_sent % 300 == 0:  # ~15s: did a friend snap on?
                        n = peek_device_count()
                        if n >= 0 and n != len(devs):
                            log(f"topology changed ({len(devs)} → {n} blocks)")
                            raise ConnectionError("topology changed")
                    # petting and pong deserve full frame rate even asleep
                    fps = FPS_DEFAULT if touch or game_on \
                        else FPS.get(mood, FPS_DEFAULT)
                    time.sleep(1 / fps)
        except (OSError, ConnectionError, json.JSONDecodeError) as e:
            with state.lock:
                state.block = {"connected": False, "serial": "", "battery": None}
                state.devices = []
            log(f"stream dropped ({e}); retrying in 3s")
            time.sleep(3)


def touch_loop(state):
    """Feed blocksd touch events into the state machine.

    tap on notify → acknowledge · single tap → he looks at you ·
    hold/slide → petting · double-tap → celebrate jump.
    """
    while True:
        path = blocksd_socket()
        if path is None:
            time.sleep(5)
            continue
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
                sock.connect(path)
                sock.sendall(b'{"type": "subscribe",'
                             b' "events": ["touch", "topology"]}\n')
                prev_links = -1     # -1: unknown until the first report
                buf = b""
                while True:
                    chunk = sock.recv(4096)
                    if not chunk:
                        raise ConnectionError("blocksd closed")
                    buf += chunk
                    while b"\n" in buf:
                        line, buf = buf.split(b"\n", 1)
                        try:
                            ev = json.loads(line)
                        except ValueError:
                            continue
                        if ev.get("type") == "topology_changed":
                            links = len(ev.get("connections", []))
                            if links and prev_links <= 0 and \
                                    state.start_reunion(time.monotonic()):
                                log("DNA snap — reunion!")
                                if state.player:
                                    state.player.play("jingle")
                            elif prev_links > 0 and links == 0:
                                log("blocks parted — rooms separate again")
                            with state.lock:
                                state.linked = links > 0
                            prev_links = links
                            continue
                        if ev.get("type") != "touch":
                            continue
                        action = ev.get("action")
                        uid = ev.get("uid")
                        with state.lock:
                            game_on = state.game is not None
                            away = not state.linked \
                                and len(state.devices) > 1 \
                                and uid is not None and uid != state.home
                        if game_on:
                            # every finger is a paddle; nothing else
                            if action in ("start", "move"):
                                state.game_touch(uid,
                                                 float(ev.get("y", 0.5)))
                            continue
                        if away:
                            # a tap on an empty glass calls Clawd over
                            if action == "start" and \
                                    state.start_visit(uid, time.monotonic()):
                                log("summoned to the other block by touch")
                            continue
                        x = float(ev.get("x", 0.5))
                        y = float(ev.get("y", 0.5))
                        z = float(ev.get("z", 0.5))
                        now = time.time()
                        if action == "start":
                            if state.touch_start(now, x, y, z) == "ack":
                                log("notify acknowledged by touch")
                        elif action == "move":
                            state.touch_move(x, y, z)
                        elif action == "end":
                            result = state.touch_end(now)
                            if result == "jump":
                                log("double-tap → celebrate")
                                if state.player and state.jingle_on_celebrate:
                                    state.player.auto_jingle(now)
                            elif result and result.startswith("resize:"):
                                log(f"triple-tap → {result.split(':')[1]}")
                                if state.player:
                                    state.player.play("chime")
        except (OSError, ConnectionError):
            time.sleep(5)


def serve_commands(state):
    path = command_socket()
    try:
        os.unlink(path)
    except FileNotFoundError:
        pass
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(path)
    os.chmod(path, 0o600)
    server.listen(8)
    log(f"command socket at {path}")
    while True:
        conn, _ = server.accept()
        threading.Thread(target=handle_client, args=(state, conn),
                         daemon=True).start()


def handle_client(state, conn):
    with conn:
        conn.settimeout(5.0)
        buf = b""
        try:
            while True:
                chunk = conn.recv(4096)
                if not chunk:
                    return
                buf += chunk
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    try:
                        msg = json.loads(line)
                        if not isinstance(msg, dict):
                            raise ValueError
                    except ValueError:
                        reply = {"ok": False, "error": "bad json"}
                    else:
                        reply = state.apply(msg, time.time())
                    conn.sendall(json.dumps(reply).encode() + b"\n")
        except (OSError, TimeoutError):
            return


class RemoteHandler(http.server.BaseHTTPRequestHandler):
    """LAN command surface. Same schema as the Unix socket, token-gated."""

    state = None   # set before serving
    token = None

    def _authed(self):
        got = self.headers.get("Authorization", "")
        got = got[7:] if got.startswith("Bearer ") else \
            self.headers.get("X-Token", "")
        return bool(got) and hmac.compare_digest(got, self.token)

    def _reply(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers",
                         "Authorization, Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        # CORS preflight, so the control panel page works from file://
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers",
                         "Authorization, Content-Type")
        self.end_headers()

    def do_POST(self):
        if self.path != "/":
            return self._reply(404, {"ok": False, "error": "not found"})
        if not self._authed():
            return self._reply(403, {"ok": False, "error": "bad token"})
        try:
            length = min(int(self.headers.get("Content-Length") or 0), 4096)
            msg = json.loads(self.rfile.read(length))
            if not isinstance(msg, dict):
                raise ValueError
        except (ValueError, OSError):
            return self._reply(400, {"ok": False, "error": "bad json"})
        reply = self.state.apply(msg, time.time(), remote=True)
        self._reply(200 if reply.get("ok") else 400, reply)
        log(f"http command: {msg.get('cmd')}")

    def do_GET(self):
        if self.path != "/status":
            return self._reply(404, {"ok": False, "error": "not found"})
        if not self._authed():
            return self._reply(403, {"ok": False, "error": "bad token"})
        self._reply(200, self.state.apply({"cmd": "status"}, time.time()))

    def log_message(self, *args):
        pass  # journal noise; commands are logged explicitly above


def serve_http(state, port, token):
    handler = type("Handler", (RemoteHandler,),
                   {"state": state, "token": token})
    server = http.server.ThreadingHTTPServer(("0.0.0.0", port), handler)
    log(f"http command surface on :{port}")
    server.serve_forever()


def state_echo_loop(state, topic, server):
    """Publish state transitions to the ntfy topic (config "state_echo").

    This is the push channel for the app family (phone/watch): mood
    changes at priority min (silent data), notify at high — so a
    subscribed phone (ntfy app) or the future Wear app buzzes when Clawd
    needs you. Echoes carry no "token" field, so ntfy_loop ignores them
    as commands; subscribers tell them apart by "event": "state".
    """
    last = None
    while True:
        now = time.time()
        with state.lock:
            snap = {"event": "state", "mood": None, "size": state.size,
                    "energy": round(state.energy, 2),
                    "battery": state.block.get("battery"),
                    "pet": dict(state.pet) if state.pet else None}
        snap["mood"] = state.mood(now)
        key = (snap["mood"], snap["size"], snap["battery"])
        if key != last:
            urgent = snap["mood"] == "notify"
            try:
                urllib.request.urlopen(urllib.request.Request(
                    f"{server}/{topic}",
                    data=json.dumps(snap).encode(),
                    headers={"Title": "clawd needs you" if urgent
                             else "clawdpad-state",
                             "Priority": "high" if urgent else "min",
                             "Tags": "state"}), timeout=10)
                last = key
            except OSError:
                pass  # retried implicitly on the next change
        time.sleep(1)


def ntfy_loop(state, topic, token, server):
    """Long-poll the ntfy server for off-LAN commands.

    Server is config "ntfy_server" (default https://ntfy.sh — a self-hosted
    instance keeps everything on your own infrastructure). Topic + token
    are both secret either way.
    """
    url = f"{server}/{topic}/json"
    while True:
        try:
            # ntfy keepalives arrive ~45s apart; 90s of silence = dead link
            with urllib.request.urlopen(url, timeout=90) as resp:
                log("ntfy subscribed")
                for line in resp:
                    try:
                        ev = json.loads(line)
                    except ValueError:
                        continue
                    if ev.get("event") != "message":
                        continue
                    try:
                        msg = json.loads(ev.get("message", ""))
                    except ValueError:
                        continue
                    if not isinstance(msg, dict):
                        continue
                    if msg.get("event") == "state":
                        continue  # our own state_echo_loop publications
                    supplied = str(msg.pop("token", ""))
                    if not hmac.compare_digest(supplied, token):
                        log("ntfy message with bad token ignored")
                        continue
                    state.apply(msg, time.time(), remote=True)
                    log(f"ntfy command: {msg.get('cmd')}")
        except OSError as e:
            log(f"ntfy link dropped ({e}); retrying in 15s")
            time.sleep(15)


def main():
    state = State()
    cfg = load_config()
    state.player = Player()
    state.hum_enabled = bool(cfg.get("thinking_hum", False))
    state.jingle_on_celebrate = bool(cfg.get("jingle_on_celebrate", True))
    if cfg.get("size") in ("full", "mini"):
        state.size = cfg["size"]
    state.matrix_fanout = bool(cfg.get("matrix_fanout", False))
    state.home_serial = str(cfg.get("home_serial", HOME_SERIAL))
    names = cfg.get("block_names", {})
    if isinstance(names, dict):
        state.block_names = {str(k): str(v).upper() for k, v in
                             names.items()}  # marquee font is uppercase
    # pre-render all sounds off the hot path so play() never blocks the lock
    threading.Thread(
        target=lambda: [state.player._wav(n)
                        for n in (*MELODIES, "hum") if state.player.bin],
        daemon=True).start()
    threading.Thread(target=hum_loop, args=(state, state.player),
                     daemon=True).start()
    threading.Thread(target=pet_loop, args=(state,), daemon=True).start()
    threading.Thread(target=touch_loop, args=(state,), daemon=True).start()
    threading.Thread(target=serve_commands, args=(state,), daemon=True).start()
    token = cfg.get("token")
    if token and cfg.get("http_port"):
        threading.Thread(target=serve_http,
                         args=(state, int(cfg["http_port"]), token),
                         daemon=True).start()
    if token and cfg.get("ntfy_topic"):
        server = str(cfg.get("ntfy_server", "https://ntfy.sh")).rstrip("/")
        threading.Thread(target=ntfy_loop,
                         args=(state, cfg["ntfy_topic"], token, server),
                         daemon=True).start()
        if cfg.get("state_echo"):
            threading.Thread(target=state_echo_loop,
                             args=(state, cfg["ntfy_topic"], server),
                             daemon=True).start()
    render_loop(state)  # never returns


if __name__ == "__main__":
    main()
