#!/usr/bin/env python3
"""claudeblockd — Claude's presence engine for the ROLI Lightpad Block M.

Streams mood animations to the block through a running blocksd (Unix socket,
685-byte binary frames) and exposes its own Unix socket command interface for
blockctl / hooks / future phone+watch bridges.

Moods: awake (breathing spark) · thinking (coral vortex) · sleep (drifting
embers, auto 23:00–07:00 when idle) · notify (pulsing amber ring — tap the
block to acknowledge) · celebrate (one-shot firework, ~2.4s) · glyph
(double-tap info cards: time → sessions → battery).

Touch (Phase 4): a tap acknowledges notify; press-and-hold is petting — the
spark leans toward your finger and glows with pressure; double-tap shows the
glyph card and cycles it on further double-taps.

Remote surfaces (Phase 3), sharing the same command schema:
  · HTTP on the LAN: POST / with `Authorization: Bearer <token>` and a JSON
    command body; GET /status for state. Token + port live in
    ~/.config/claudeblock/config.json (plain HTTP — home-LAN threat model).
  · ntfy.sh: publish a JSON command (with a "token" field) to the secret
    topic in config.json; works from anywhere.

Command protocol: one JSON object per line, one JSON reply per line.
  {"cmd": "event-hook", "kind": "start|prompt|stop|end", "sid": "...", "project": "..."}
  {"cmd": "mode", "arg": "awake|thinking|sleep|notify"}
  {"cmd": "say", "arg": "text", "seconds": 120}      # renders as notify
  {"cmd": "anim", "arg": "celebrate"}
  {"cmd": "event", "kind": "ripple|wave|flash", "color": [r, g, b], "sid": "..."}
  {"cmd": "glyph", "arg": "time|sessions|battery|pet", "seconds": 4}
  {"cmd": "play", "arg": "jingle|hello|chime"}     # sound + celebrate light
  {"cmd": "hum", "arg": "on|off"}                   # ambient pad while thinking

Music (Phase 5) is synthesized in-process — pure-stdlib additive bell voice
rendered to WAV (cached in the runtime dir) and played via pw-play/aplay.
Config (~/.config/claudeblock/config.json): "jingle_on_celebrate" (default
true, rate-limited to one per 30 s) and "thinking_hum" (default false).

Soul link: Clawd's tamagotchi state (~/dazzler/state.json, owned by dazzler's
petd.py) is mirrored read-only. Hunger sets the idle spark's vigor, level-ups
fire firework+jingle, petd whispers chime here, and the "pet" glyph card
shows level + hunger bar. One soul, two bodies — never write dazzler's state.
  {"cmd": "clear"}                                    # drop notify + manual mode
  {"cmd": "status"}                                   # -> mood, block, sessions
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

W = H = 15
CORAL = (217, 119, 87)     # Claude coral #D97757
AMBER = (255, 176, 32)
EMBER = (140, 52, 22)
CX = CY = (W - 1) / 2
RMAX = math.hypot(CX, CY)

FPS = {"sleep": 8}         # per-mood frame rate; default 20
FPS_DEFAULT = 20
CELEBRATE_SECONDS = 2.4
EVENT_TTL = {"ripple": 0.9, "wave": 1.2, "flash": 0.5}
EVENT_ENERGY = {"ripple": 0.10, "wave": 0.20, "flash": 0.25}
ENERGY_TAU = 25.0          # seconds for work-energy to decay to 1/e
TAP_MAX_SECONDS = 0.35     # touch shorter than this is a tap, longer is petting
DOUBLE_TAP_WINDOW = 0.6    # two taps inside this = double-tap
GLYPH_SECONDS = 4.0
GLYPHS = ("time", "sessions", "battery", "pet")

# One soul, two bodies: Clawd's pet state is OWNED by dazzler (petd.py writes
# it; a systemd timer ticks it). The block only mirrors it — never writes.
PET_STATE = os.path.expanduser("~/dazzler/state.json")
PET_VIGOR = {"full": 1.0, "content": 1.0, "peckish": 0.85,
             "hungry": 0.70, "starving": 0.55}  # idle-spark brightness factor

# 3x5 pixel font for the glyph cards (rows of '1' bits, top to bottom)
FONT = {
    "0": ("111", "101", "101", "101", "111"),
    "1": ("010", "110", "010", "010", "111"),
    "2": ("111", "001", "111", "100", "111"),
    "3": ("111", "001", "011", "001", "111"),
    "4": ("101", "101", "111", "001", "001"),
    "5": ("111", "100", "111", "001", "111"),
    "6": ("111", "100", "111", "101", "111"),
    "7": ("111", "001", "001", "010", "010"),
    "8": ("111", "101", "111", "101", "111"),
    "9": ("111", "101", "111", "001", "111"),
    "?": ("111", "001", "011", "000", "010"),
}
THINK_TTL = 90 * 60        # a "thinking" session older than this reads as resting
SESSION_TTL = 12 * 3600    # forget sessions entirely after this
SLEEP_START, SLEEP_END = 23, 7


def blocksd_socket():
    for base in (os.environ.get("XDG_RUNTIME_DIR"), "/tmp"):
        if base:
            p = os.path.join(base, "blocksd", "blocksd.sock")
            if os.path.exists(p):
                return p
    return None


def command_socket():
    base = os.environ.get("XDG_RUNTIME_DIR") or "/tmp"
    d = os.path.join(base, "claudeblockd")
    os.makedirs(d, mode=0o700, exist_ok=True)
    return os.path.join(d, "claudeblockd.sock")


class State:
    """Everything the renderer needs, guarded by one lock."""

    def __init__(self):
        self.lock = threading.Lock()
        self.sessions = {}          # sid -> [project, "thinking"|"resting", epoch]
        self.manual = None          # explicit `mode` override; hooks clear it
        self.notify_until = 0.0
        self.notify_text = ""
        self.oneshot_until = 0.0    # celebrate window
        self.oneshot_rng = random.Random(0)
        self.events = []            # one-shots: (kind, (r, g, b), started)
        self.energy = 0.0           # 0..1 work density; scales vortex speed
        self.touch = None           # live touch: [x, y, z, started] (0..1 floats)
        self.taps = []              # recent tap timestamps (double-tap detect)
        self.glyph_until = 0.0
        self.glyph_index = 0
        self.block = {"connected": False, "serial": "", "battery": None}
        self.started = time.time()
        self.player = None                # set in main()
        self.hum_enabled = False          # config "thinking_hum" / {"cmd":"hum"}
        self.jingle_on_celebrate = True   # config "jingle_on_celebrate"
        self.pet = None                   # mirrored from dazzler's state.json
        self.last_say_chime = 0.0

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
            if now < self.oneshot_until:
                return "celebrate"
            if now < self.notify_until:
                return "notify"
            if now < self.glyph_until:
                return "glyph"
            if self.manual:
                return self.manual
            if any(s[1] == "thinking" for s in self.sessions.values()):
                return "thinking"
            hour = time.localtime(now).tm_hour
            if hour >= SLEEP_START or hour < SLEEP_END:
                return "sleep"
            return "awake"

    def apply(self, msg, now):
        cmd = msg.get("cmd")
        with self.lock:
            if cmd == "event-hook":
                kind = msg.get("kind", "prompt")
                sid = str(msg.get("sid", "manual"))[:8]
                project = str(msg.get("project", "somewhere"))
                if kind in ("start", "prompt"):
                    # new activity reclaims the mood; a mere turn-ending does
                    # not, so a manually summoned Clawd survives stop events
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
                    self.oneshot_until = now + CELEBRATE_SECONDS
                    self.oneshot_rng = random.Random(int(now))
                    if self.jingle_on_celebrate and self.player:
                        self.player.auto_jingle(now)
                elif kind == "end":
                    self.sessions.pop(sid, None)
                else:
                    return {"ok": False, "error": f"unknown kind: {kind}"}
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
            elif cmd == "event":
                kind = str(msg.get("kind", "")).lower()
                if kind not in EVENT_TTL:
                    return {"ok": False, "error": f"unknown event: {kind}"}
                color = tuple(int(c) for c in (msg.get("color")
                                               or CORAL))[:3]
                self.events = [e for e in self.events
                               if now - e[2] < EVENT_TTL[e[0]]][-7:]
                self.events.append((kind, color, now))
                self.energy = min(1.0, self.energy + EVENT_ENERGY[kind])
                sid = str(msg.get("sid", ""))[:8]
                if sid in self.sessions:  # keep a busy session's clock fresh
                    self.sessions[sid][2] = now
            elif cmd == "anim":
                if str(msg.get("arg", "")).lower() != "celebrate":
                    return {"ok": False, "error": "only 'celebrate' in v0"}
                self.oneshot_until = now + CELEBRATE_SECONDS
                self.oneshot_rng = random.Random(int(now))
                if self.jingle_on_celebrate and self.player:
                    self.player.auto_jingle(now)
            elif cmd == "play":
                name = str(msg.get("arg", "jingle")).lower()
                if self.player is None or name not in MELODIES:
                    return {"ok": False, "error": f"cannot play: {name}"}
                if not self.player.play(name):
                    return {"ok": False, "error": "no audio player available"}
                if name == "jingle":  # sound + light, per the plan
                    self.oneshot_until = now + CELEBRATE_SECONDS
                    self.oneshot_rng = random.Random(int(now))
            elif cmd == "hum":
                self.hum_enabled = str(msg.get("arg", "on")).lower() == "on"
            elif cmd == "glyph":
                name = str(msg.get("arg", "time")).lower()
                if name not in GLYPHS:
                    return {"ok": False, "error": f"unknown glyph: {name}"}
                self.glyph_index = GLYPHS.index(name)
                self.glyph_until = now + float(msg.get("seconds", GLYPH_SECONDS))
            elif cmd == "clear":
                self.notify_until = 0.0
                self.notify_text = ""
                self.manual = None
            elif cmd in ("status", "ping"):
                pass
            else:
                return {"ok": False, "error": f"unknown cmd: {cmd}"}
        return {"ok": True, "mood": self.mood(now), "block": dict(self.block),
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

    def active_events(self, now):
        with self.lock:
            self.events = [e for e in self.events
                           if now - e[2] < EVENT_TTL[e[0]]]
            return list(self.events)

    def touch_snapshot(self):
        with self.lock:
            return tuple(self.touch[:3]) if self.touch else None

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
        """Tap bookkeeping. Returns the glyph name if a double-tap fired."""
        with self.lock:
            held, self.touch = self.touch, None
            if held is None or now - held[3] > TAP_MAX_SECONDS:
                return None  # that was petting, not a tap
            self.taps = [t for t in self.taps
                         if now - t < DOUBLE_TAP_WINDOW] + [now]
            if len(self.taps) < 2:
                return None
            self.taps.clear()
            if now < self.glyph_until:  # already showing: cycle to the next card
                self.glyph_index = (self.glyph_index + 1) % len(GLYPHS)
            else:
                self.glyph_index = 0
            self.glyph_until = now + GLYPH_SECONDS
            return GLYPHS[self.glyph_index]

    def glyph_snapshot(self, now):
        with self.lock:
            self.prune(now)
            thinking = sum(1 for s in self.sessions.values()
                           if s[1] == "thinking")
            return (GLYPHS[self.glyph_index], len(self.sessions), thinking,
                    self.block.get("battery"), self.pet)

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
HUM_CHORD = (48, 55, 64)   # C3 G3 E4 — the pad Claude hums while thinking
HUM_SECONDS = 8.0


def _note_freq(midi):
    return 440.0 * 2 ** ((midi - 69) / 12)


def _render_melody(notes, gain=0.30):
    """Additive bell voice (fundamental + 2 partials, exp decay) -> float samples."""
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
                env = math.exp(-3.2 * t) * min(1.0, t * 200)  # click-free attack
                s = (math.sin(2 * math.pi * f * t)
                     + 0.35 * math.sin(2 * math.pi * 2 * f * t)
                     + 0.12 * math.sin(2 * math.pi * 3.01 * f * t))
                buf[i0 + i] += s * env / len(chord)
    return buf, gain


def _render_hum():
    """Quiet slow-breathing pad; fades at both ends so looping doesn't click."""
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
        self.bin = shutil.which("pw-play") or shutil.which("aplay")
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
        """Celebrate-triggered jingle, rate-limited so session storms stay calm."""
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

    petd.py (dazzler) owns the state; we watch it read-only every 5 s.
    Level-ups → firework + jingle on the glass. New whispers (petd speaking
    on the matrix) → a chime here, so both bodies feel inhabited. Hunger
    reaches the idle spark via State.pet_vigor().
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
                    state.oneshot_until = now + CELEBRATE_SECONDS
                    state.oneshot_rng = random.Random(int(now))
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
    """Claude hums (quietly) while thinking, when enabled. Checks twice a second."""
    while True:
        humming = state.hum_enabled and state.mood(time.time()) == "thinking"
        if humming and not player.hum_running():
            player.hum_start()   # 8s pad; re-started each time it runs out
        elif not humming and player.hum_running():
            player.hum_stop()
        time.sleep(0.5)


# ---------------------------------------------------------------- animations

def _emit(levels, color):
    """levels: 225 floats 0..1 -> RGB888 frame bytes in `color`."""
    px = bytearray()
    for lv in levels:
        lv = 0.0 if lv < 0.0 else (1.0 if lv > 1.0 else lv)
        px += bytes(min(255, int(c * lv)) for c in color)
    return px


def _lean(touch, pull=0.45):
    """Where the spark's center sits: drawn toward a touch, else home."""
    if touch is None:
        return CX, CY, 0.0
    tx, ty, tz = touch
    cx = CX + (tx * (W - 1) - CX) * pull
    cy = CY + (ty * (H - 1) - CY) * pull
    return cx, cy, tz


# Clawd's geometry, scaled from the official Claude Code icon SVG
# (viewBox 24x24; same rect decomposition dazzler's make_clawd.py uses):
# solid body, two side arm nubs, FOUR legs, two eye holes. Rects are
# (x0, y0, x1, y1), end-exclusive, on the 15x15 grid.
CLAWD_BODY = (2, 3, 13, 11)
CLAWD_ARMS = ((0, 7, 2, 9), (13, 7, 15, 9))     # left, right
CLAWD_LEGS = ((3, 11, 4, 13), (5, 11, 6, 13),
              (9, 11, 10, 13), (11, 11, 12, 13))
CLAWD_EYES = ((4, 5), (10, 5))                   # top px of each 1x2 eye hole


def _clawd(brightness, dx=0, dy=0, eyes="open", look=0,
           arm_l_dy=0, arm_r_dy=0):
    """Render Clawd — the actual Claude Code icon as 15x15 pixel art.

    dx/dy shift the whole creature (pace/bob, dazzler-style); `eyes` is
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


def frame_awake(t, touch=None, vigor=1.0):
    """Clawd awake: breathes, bobs, paces a little, blinks, glances around.

    Touch makes him lean toward your finger, glow with pressure, and watch
    it. Vigor mirrors hunger (see pet_loop) — a hungry Clawd burns low, a
    starving one gutters (feed him: ~/dazzler/feed/).
    """
    breath = 0.72 + 0.28 * math.sin(t * 2 * math.pi / 6.5)
    if touch is not None:
        tx, ty, tz = touch
        fx, fy = tx * (W - 1) - 7, ty * (H - 1) - 7
        dx = max(-2, min(2, round(fx * 0.3)))
        dy = max(-1, min(1, round(fy * 0.2)))
        look = max(-1, min(1, round(fx * 0.2)))
        brightness = min(1.0, breath + 0.35 * tz)
    else:
        dx = round(1.5 * math.sin(t * 0.13))
        dy = round(0.5 * math.sin(t * 2 * math.pi / 6.5))
        look = round(0.9 * math.sin(t * 0.31))
        brightness = breath
    brightness *= vigor
    if vigor <= PET_VIGOR["starving"]:
        brightness *= 0.88 + 0.12 * math.sin(t * 13.7)
    blink = (t % 4.3) < 0.13
    return _clawd(brightness, dx, dy, "closed" if blink else "open", look)


def frame_thinking(phase, energy, touch=None):
    """Three-armed coral vortex; spins and brightens with work energy.

    Petting leans the vortex eye toward the finger, gently (it's busy).
    """
    cx, cy, tz = _lean(touch, pull=0.30)
    floor = min(0.6, 0.22 + 0.18 * energy + 0.2 * tz)
    levels = []
    for y in range(H):
        for x in range(W):
            dx, dy = x - cx, y - cy
            r = math.hypot(dx, dy) / RMAX
            arm = math.sin(math.atan2(dy, dx) * 3 + r * 5.0 - phase)
            level = (floor + (1.0 - floor) * max(0.0, arm)) \
                * max(0.0, 1.0 - r) ** 1.4
            if r < 0.14:
                level = 1.0
            levels.append(level)
    return _emit(levels, CORAL)


def frame_sleep(t, touch=None):
    """Clawd asleep, dazzler-style: dim, slow ember breathing, eyes closed —
    with an occasional one-frame peek. Petting warms him and half-wakes the
    eyes, like disturbing anyone at 3am.
    """
    breath = 0.26 + 0.08 * math.sin(t * 2 * math.pi / 9.0)
    peek = (t % 9.7) < 0.4
    if touch is not None:
        breath = min(0.7, breath + 0.45 * touch[2])
        peek = True
    return _clawd(breath, 0, round(0.5 * math.sin(t * 2 * math.pi / 9.0)),
                  "open" if peek else "closed", 0)


def _blit(buf, x, y, color):
    if 0 <= x < W and 0 <= y < H:
        i = (y * W + x) * 3
        buf[i], buf[i + 1], buf[i + 2] = color


def _blit_text(buf, text, x0, y0, color):
    """Render 3x5 FONT glyphs left to right with 1px spacing."""
    x = x0
    for ch in text:
        for dy, row in enumerate(FONT.get(ch, FONT["?"])):
            for dx, bit in enumerate(row):
                if bit == "1":
                    _blit(buf, x + dx, y0 + dy, color)
        x += 4


def frame_glyph(t, state):
    """Double-tap info cards over a dimmed spark: time / sessions / battery."""
    buf = bytearray(frame_awake(t))
    for i, b in enumerate(buf):
        buf[i] = int(b * 0.22)  # dim the spark so the card reads clearly
    name, total, thinking, battery, pet = state.glyph_snapshot(time.time())
    if name == "pet":
        level = pet["level"] if pet else 1
        hunger = pet["hunger"] if pet else 50.0
        _blit_text(buf, str(min(int(level), 99)), 2, 2, CORAL)
        _blit(buf, 11, 3, (255, 90, 110))   # a small heart, honestly
        _blit(buf, 13, 3, (255, 90, 110))
        for dx in range(11, 14):
            _blit(buf, dx, 4, (255, 90, 110))
        _blit(buf, 12, 5, (255, 90, 110))
        color = ((80, 220, 100) if hunger >= 40 else
                 (255, 176, 32) if hunger >= 20 else (255, 60, 50))
        for x in range(1, 14):              # hunger bar frame
            _blit(buf, x, 10, (60, 45, 40))
            _blit(buf, x, 12, (60, 45, 40))
        for x in range(1, 1 + round(min(100, max(0, hunger)) / 100 * 13)):
            _blit(buf, x, 11, color)
    elif name == "time":
        tm = time.localtime()
        white = (210, 210, 225)
        _blit_text(buf, f"{tm.tm_hour:02d}", 4, 2, white)
        _blit_text(buf, f"{tm.tm_min:02d}", 4, 9, white)
    elif name == "sessions":
        _blit_text(buf, str(min(total, 9)), 6, 4, CORAL)
        for i in range(min(total, 13)):  # dot row: bright = thinking
            _blit(buf, 1 + i, 12,
                  (255, 170, 120) if i < thinking else (70, 40, 28))
    else:  # battery
        if battery is None:
            level, color = 0, (110, 110, 130)
        else:
            level = max(0, min(100, int(battery)))
            color = ((80, 220, 100) if level >= 50 else
                     (255, 176, 32) if level >= 20 else (255, 60, 50))
        for x in range(2, 13):          # case outline
            _blit(buf, x, 5, color)
            _blit(buf, x, 9, color)
        for y in range(5, 10):
            _blit(buf, 2, y, color)
            _blit(buf, 12, y, color)
        for y in range(6, 9):           # positive terminal
            _blit(buf, 13, y, color)
        fill = round(level / 100 * 9)
        for x in range(3, 3 + fill):    # charge bar
            for y in range(6, 9):
                _blit(buf, x, y, color)
    return buf


def frame_notify(t, state=None, touch=None):
    """Clawd needs you: he waves an arm and pulses brighter. Tap to ack.

    (No amber ring — Rod's call. The wave is dazzler's 'wave' sequence.)
    """
    vigor = state.pet_vigor() if state else 1.0
    pulse = (0.78 + 0.22 * math.sin(t * 2 * math.pi * 1.4)) * max(0.7, vigor)
    wave = -2 if (t * 2.4) % 1.0 < 0.5 else -1  # right arm raised, beckoning
    blink = (t % 4.3) < 0.13
    return _clawd(pulse, 0, 0, "closed" if blink else "open", 0,
                  arm_r_dy=wave)


def frame_celebrate(t, rng):
    """Expanding ring + sparkles bursting from the center."""
    prog = t / CELEBRATE_SECONDS
    ring_r = prog * RMAX * 1.3
    fade = max(0.0, 1.0 - prog)
    px = bytearray()
    sparkles = {(rng.randrange(W), rng.randrange(H)): rng.random()
                for _ in range(26)}
    rng.seed(rng.random())  # advance so sparkles shimmer frame to frame
    for y in range(H):
        for x in range(W):
            d = math.hypot(x - CX, y - CY)
            ring = max(0.0, 1.0 - abs(d - ring_r) / 1.5) * fade
            sp = sparkles.get((x, y), 0.0) * fade
            r = min(255, int(AMBER[0] * ring + 255 * sp))
            g = min(255, int(AMBER[1] * ring + 235 * sp))
            b = min(255, int(AMBER[2] * ring + 170 * sp))
            px += bytes((r, g, b))
    return px


def build_frame(mood, t, phase, energy, state, touch):
    if mood == "thinking":
        return frame_thinking(phase, energy, touch)
    if mood == "sleep":
        return frame_sleep(t, touch)
    if mood == "notify":
        return frame_notify(t, state, touch)
    if mood == "glyph":
        return frame_glyph(t, state)
    if mood == "celebrate":
        with state.lock:
            rel = CELEBRATE_SECONDS - (state.oneshot_until - time.time())
            rng = state.oneshot_rng
        return frame_celebrate(max(0.0, rel), rng)
    return frame_awake(t, touch, state.pet_vigor())


def overlay_level(kind, age, x, y):
    """0..1 contribution of a one-shot event at pixel (x, y)."""
    if kind == "ripple":  # thin ring expanding from center
        prog = age / EVENT_TTL["ripple"]
        d = math.hypot(x - CX, y - CY)
        return max(0.0, 1.0 - abs(d - prog * (RMAX + 2)) / 1.2) * (1.0 - prog)
    if kind == "wave":    # horizontal band sweeping bottom -> top
        prog = age / EVENT_TTL["wave"]
        yc = (H + 3) - prog * (H + 6)
        return max(0.0, 1.0 - abs(y - yc) / 2.0) * (1.0 - prog)
    if kind == "flash":   # whole-glass flash, fast decay
        return (1.0 - age / EVENT_TTL["flash"]) ** 2 * 0.9
    return 0.0


def apply_overlays(buf, events, now):
    for kind, color, started in events:
        age = now - started
        for y in range(H):
            for x in range(W):
                lv = overlay_level(kind, age, x, y)
                if lv <= 0.0:
                    continue
                i = (y * W + x) * 3
                for c in range(3):
                    buf[i + c] = min(255, buf[i + c] + int(color[c] * lv))


# ------------------------------------------------------------------ plumbing

def log(msg):
    print(time.strftime("%H:%M:%S"), msg, flush=True)


def discover_block(sock):
    sock.sendall(b'{"type": "discover", "id": "cbd-1"}\n')
    buf = b""
    while b"\n" not in buf:
        chunk = sock.recv(4096)
        if not chunk:
            raise ConnectionError("blocksd closed during discover")
        buf += chunk
    for dev in json.loads(buf.split(b"\n")[0]).get("devices", []):
        if dev.get("grid_width") and dev.get("grid_height"):
            return dev
    return None


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
                dev = discover_block(sock)
                if dev is None:
                    with state.lock:
                        state.block = {"connected": False, "serial": "",
                                       "battery": None}
                    if not announced_wait:
                        log("blocksd up, block absent — will keep checking")
                        announced_wait = True
                    time.sleep(3)
                    continue
                announced_wait = False
                with state.lock:
                    state.block = {"connected": True, "serial": dev["serial"],
                                   "battery": dev.get("battery_level")}
                log(f"streaming to {dev['serial']} "
                    f"(battery {dev.get('battery_level')}%)")
                header = struct.pack("<BBQ", 0xBD, 0x01, dev["uid"])
                rejects = 0
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
                    frame = build_frame(mood, mono - start, phase,
                                        energy, state, touch)
                    events = state.active_events(now)
                    if events:
                        apply_overlays(frame, events, now)
                    sock.sendall(header + frame)
                    ack = sock.recv(1)
                    if not ack:
                        raise ConnectionError("blocksd closed")
                    rejects = 0 if ack == b"\x01" else rejects + 1
                    if rejects > 60:  # block likely unplugged; re-discover
                        raise ConnectionError("frames not accepted")
                    # petting deserves full frame rate even while asleep
                    fps = FPS_DEFAULT if touch else FPS.get(mood, FPS_DEFAULT)
                    time.sleep(1 / fps)
        except (OSError, ConnectionError, json.JSONDecodeError) as e:
            with state.lock:
                state.block = {"connected": False, "serial": "", "battery": None}
            log(f"stream dropped ({e}); retrying in 3s")
            time.sleep(3)


def touch_loop(state):
    """Feed blocksd touch events into the state machine.

    tap on notify → acknowledge · hold → petting (live x/y/pressure) ·
    double-tap → info glyph cards.
    """
    while True:
        path = blocksd_socket()
        if path is None:
            time.sleep(5)
            continue
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
                sock.connect(path)
                sock.sendall(b'{"type": "subscribe", "events": ["touch"]}\n')
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
                        if ev.get("type") != "touch":
                            continue
                        action = ev.get("action")
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
                            glyph = state.touch_end(now)
                            if glyph:
                                log(f"double-tap → {glyph} glyph")
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
                    except ValueError:
                        reply = {"ok": False, "error": "bad json"}
                    else:
                        reply = state.apply(msg, time.time())
                    conn.sendall(json.dumps(reply).encode() + b"\n")
        except (OSError, TimeoutError):
            return


def load_config():
    path = os.path.expanduser("~/.config/claudeblock/config.json")
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


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
        self.end_headers()
        self.wfile.write(body)

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
        reply = self.state.apply(msg, time.time())
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


def ntfy_loop(state, topic, token):
    """Long-poll ntfy.sh for off-LAN commands. Topic + token are both secret."""
    url = f"https://ntfy.sh/{topic}/json"
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
                    supplied = str(msg.pop("token", ""))
                    if not hmac.compare_digest(supplied, token):
                        log("ntfy message with bad token ignored")
                        continue
                    state.apply(msg, time.time())
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
        threading.Thread(target=ntfy_loop,
                         args=(state, cfg["ntfy_topic"], token),
                         daemon=True).start()
    if not token:
        log("no ~/.config/claudeblock/config.json — remote surfaces off")
    render_loop(state)  # never returns


if __name__ == "__main__":
    main()
