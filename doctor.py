"""doctor — check everything a new clawdpad owner trips on, and say how to fix it.

Roadmap Basic #1, and the reason it's #1: *adoption lives or dies here.* Every
failure below cost somebody an evening, and every one of them looks like "Clawd
just doesn't appear" from the outside. A blank glass has a dozen causes and no
error message — this turns that into a sentence and a command.

**This is a library first, a CLI second** (docs/LEVELS.md, idea #2). `run()`
returns plain data; `blockctl doctor` renders it to a terminal, and the L2 app's
first-run screen can render the same list with a Fix button. The checks must
never print — a check that prints can't be a wizard.

Stdlib only, like everything else here, and safe to run with nothing installed:
every check catches its own failure and reports it as a finding, because a
doctor that crashes on a sick patient is a bad doctor.

    from doctor import run
    for c in run():
        print(c.status, c.name, c.detail, c.fix)
"""

from __future__ import annotations

import json
import os
import platform
import shutil
import socket
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

OK, WARN, FAIL, SKIP = "ok", "warn", "fail", "skip"


class Check:
    """One finding. `fix` is a command or a sentence — never empty on failure.

    Printing fixes rather than failures is the whole point of this module: an
    error a stranger can act on is worth ten diagnoses they can't.
    """

    __slots__ = ("name", "status", "detail", "fix")

    def __init__(self, name, status, detail="", fix=""):
        self.name = name
        self.status = status
        self.detail = detail
        self.fix = fix

    @property
    def bad(self):
        return self.status == FAIL

    def __repr__(self):
        return f"<Check {self.name} {self.status}>"

    def as_dict(self):
        """For the app's first-run screen, `--json`, and anything else that
        wants findings without a terminal."""
        return {"name": self.name, "status": self.status,
                "detail": self.detail, "fix": self.fix}


# --------------------------------------------------------------------------
# individual checks — each returns a Check and never raises
# --------------------------------------------------------------------------

def check_python():
    v = sys.version_info
    got = f"{v.major}.{v.minor}.{v.micro}"
    if v >= (3, 13):
        return Check("python", OK, f"{got}")
    # macOS ships 3.9 as /usr/bin/python3, and a venv built from it produces
    # the world's most confusing pip error: "Package 'blocksd' requires a
    # different Python". See docs/MACBOOK.md Phase 1.
    return Check("python", FAIL, f"{got} — blocksd needs >= 3.13",
                 "python3.13 -m venv .venv  (brew install python@3.13 on macOS)")


def check_blocksd_installed():
    try:
        import blocksd  # noqa: F401
    except Exception as e:
        return Check("blocksd installed", FAIL, f"import failed: {e}",
                     f".venv/bin/pip install -e {ROOT / 'blocksd'}")
    where = Path(getattr(blocksd, "__file__", "") or "").resolve()
    # The patched fork must win over any PyPI copy, or the fixes below silently
    # revert and the glass goes dark again with no explanation.
    if ROOT in where.parents:
        return Check("blocksd installed", OK, f"editable from {where.parent.parent}")
    return Check("blocksd installed", FAIL,
                 f"using an unpatched copy at {where}",
                 f".venv/bin/pip install -e {ROOT / 'blocksd'}   "
                 "(never `pip install -U blocksd`)")


def _probe_source(mod_name, needle):
    """Look for a fix in the installed source. Crude on purpose: it survives
    version bumps and needs no import side effects."""
    try:
        import importlib.util
        spec = importlib.util.find_spec(mod_name)
        if not spec or not spec.origin:
            return None
        return needle in Path(spec.origin).read_text(errors="ignore")
    except Exception:
        return None


def check_patches():
    """The three vendored fixes. Without #1 the glass renders *nothing* and the
    only clue is a device log nobody thinks to read (docs/BLOCKSD-FIXES.md)."""
    # Each needle is a symbol the patch INTRODUCES, verified against the real
    # source — not a word from its commit message. The first draft of this
    # probed for "port_indices" (which appears nowhere but patch 0003's prose)
    # and cheerfully reported a correctly-patched tree as broken. A doctor that
    # cries wolf gets ignored, which is worse than not existing.
    probes = [
        ("littlefoot jump base", "blocksd.littlefoot.assembler", "code_base",
         "the glass stays dark — every repaint faults with 'Illegal instruction'"),
        ("bitmap LED upload", "blocksd.topology.device_group", "bitmap_led_program",
         "frames ack but never render"),
        ("topology group key", "blocksd.topology.manager", "_GroupKey",
         "a second block on macOS is invisible"),
    ]
    missing = []
    unknown = False
    for label, mod, needle, _sym in probes:
        got = _probe_source(mod, needle)
        if got is None:
            unknown = True
        elif not got:
            missing.append(label)
    if unknown and not missing:
        return Check("blocksd patches", WARN, "could not read blocksd sources",
                     "check by hand: docs/BLOCKSD-FIXES.md")
    if missing:
        return Check("blocksd patches", FAIL,
                     "missing: " + ", ".join(missing),
                     f"cd {ROOT / 'blocksd'} && git am {ROOT / 'patches'}/*.patch"
                     "  — then restart blocksd")
    return Check("blocksd patches", OK, "all three applied")


def _blocksd_socket():
    for base in (os.environ.get("XDG_RUNTIME_DIR"), "/tmp"):
        if base:
            p = Path(base) / "blocksd" / "blocksd.sock"
            if p.exists():
                return p
    return None


def _ask(path, payload, timeout=2.0):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
        s.settimeout(timeout)
        s.connect(str(path))
        s.sendall(json.dumps(payload).encode() + b"\n")
        buf = b""
        while b"\n" not in buf:
            chunk = s.recv(4096)
            if not chunk:
                raise ConnectionError("closed early")
            buf += chunk
    return json.loads(buf.split(b"\n")[0])


def check_blocksd_running():
    """blocksd must always run — the block powers off without its keepalive."""
    path = _blocksd_socket()
    if path is None:
        return Check("blocksd running", FAIL, "no socket found",
                     "systemctl --user start blocksd    "
                     "(or: .venv/bin/blocksd run --verbose)")
    try:
        _ask(path, {"type": "discover", "id": "doctor"})
        return Check("blocksd running", OK, f"answering on {path}")
    except Exception as e:
        return Check("blocksd running", FAIL, f"socket is there but dead: {e}",
                     "systemctl --user restart blocksd")


def check_block():
    """Ground truth, straight from blocksd — never blockctl's cache, which has
    been known to hold a phantom block for an hour after it was unplugged."""
    path = _blocksd_socket()
    if path is None:
        return Check("block detected", SKIP, "blocksd isn't running")
    try:
        reply = _ask(path, {"type": "discover", "id": "doctor"})
    except Exception as e:
        return Check("block detected", SKIP, f"could not ask blocksd: {e}")
    grids, seen = [], set()
    for dev in reply.get("devices", []):
        if dev.get("grid_width") and dev.get("uid") not in seen:
            seen.add(dev.get("uid"))
            grids.append(dev)
    if not grids:
        return Check("block detected", FAIL, "blocksd sees no LED grid",
                     "plug the block in over USB and PRESS ITS POWER BUTTON — "
                     "a dark block after a host reboot is the usual answer")
    names = ", ".join(str(d.get("serial") or d.get("uid")) for d in grids)
    return Check("block detected", OK, f"{len(grids)} block(s): {names}")


def check_audio_group():
    """Linux only: blocksd's MIDI scan fails between boot and console login if
    the user isn't in `audio`. It self-heals, which is why it went undiagnosed
    for so long — it only bites on a fresh reboot."""
    if platform.system() != "Linux":
        return Check("audio group", SKIP, f"not Linux ({platform.system()})")
    try:
        import grp
        user = os.environ.get("USER") or ""
        members = set(grp.getgrnam("audio").gr_mem)
        if user in members:
            return Check("audio group", OK, f"{user} is in audio")
        return Check("audio group", WARN,
                     f"{user} is not in the audio group — MIDI scans can fail "
                     "before console login",
                     f"sudo usermod -aG audio {user}   (then log out and back in)")
    except Exception as e:
        return Check("audio group", SKIP, str(e))


def check_daemon():
    for base in (os.environ.get("XDG_RUNTIME_DIR"), "/tmp"):
        if not base:
            continue
        p = Path(base) / "clawdpad" / "clawdpad.sock"
        if p.exists():
            try:
                reply = _ask(p, {"cmd": "status"})
                mood = reply.get("mood", "?")
                return Check("clawdpadd running", OK, f"mood: {mood}")
            except Exception as e:
                return Check("clawdpadd running", FAIL,
                             f"socket is there but dead: {e}",
                             "systemctl --user restart clawdpadd")
    return Check("clawdpadd running", FAIL, "no socket found",
                 "systemctl --user start clawdpadd   "
                 "(or: .venv/bin/python3 clawdpadd.py)")


def check_hooks():
    """Without these Clawd never paces — he just sits there, and the project
    looks broken in the exact way that makes someone give up on it."""
    settings = Path.home() / ".claude" / "settings.json"
    if not settings.exists():
        return Check("Claude Code hooks", WARN, "no ~/.claude/settings.json",
                     "see README — hooks are what make him react to Claude")
    try:
        raw = settings.read_text()
    except Exception as e:
        return Check("Claude Code hooks", SKIP, str(e))
    if "claudebody" in raw or "blockctl" in raw:
        return Check("Claude Code hooks", OK, "wired in settings.json")
    return Check("Claude Code hooks", WARN, "no clawdpad hooks found",
                 "see README — without them he never reacts to Claude")


def check_render():
    """The subtlest failure of all: frames ack, nothing lights up. Acks are not
    pixels. Only the device log knows, and only with --verbose."""
    if shutil.which("systemctl") is None:
        return Check("frames rendering", SKIP, "no systemctl to read logs from")
    try:
        out = subprocess.run(
            ["journalctl", "--user", "-u", "blocksd", "-n", "200", "--no-pager"],
            capture_output=True, text=True, timeout=5).stdout
    except Exception as e:
        return Check("frames rendering", SKIP, str(e))
    if "Illegal instruction" in out:
        return Check("frames rendering", FAIL,
                     "device log shows 'Illegal instruction' — the LittleFoot "
                     "program is faulting, so nothing paints",
                     "the assembler patch is missing or reverted: "
                     f"cd {ROOT / 'blocksd'} && git am {ROOT / 'patches'}/*.patch")
    return Check("frames rendering", OK, "no device faults in recent logs")


CHECKS = (check_python, check_blocksd_installed, check_patches,
          check_blocksd_running, check_block, check_audio_group,
          check_daemon, check_hooks, check_render)


def run(checks=CHECKS):
    """Every check, in dependency order. Never raises: a check that blows up
    becomes a finding, because the whole point is to work on a broken machine."""
    out = []
    for fn in checks:
        try:
            out.append(fn())
        except Exception as e:                     # pragma: no cover
            out.append(Check(getattr(fn, "__name__", "check"), FAIL,
                             f"the check itself crashed: {e!r}",
                             "please file this — doctor should never crash"))
    return out
