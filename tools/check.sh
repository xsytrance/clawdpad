#!/usr/bin/env bash
# check.sh — everything that can be verified without hardware, in one command.
#
#     tools/check.sh
#
# Claude cannot see the glass and Rod is not always at his desk, so this is the
# safety net: conformance, renderers, and imports. It does NOT touch a block and
# does NOT need blocksd running — run it any time, on any machine.
#
# What it does not cover: whether pixels actually light up. Only eyes do that.

set -uo pipefail
cd "$(dirname "$0")/.."

PASS=0
FAIL=0
step() {
  local name="$1"; shift
  local out
  if out=$("$@" 2>&1); then
    printf '  ✅ %s\n' "$name"; PASS=$((PASS + 1))
  else
    printf '  ❌ %s\n' "$name"; FAIL=$((FAIL + 1))
    printf '%s\n' "$out" | sed 's/^/       /' | tail -12
  fi
}

PY=.venv/bin/python3
[ -x "$PY" ] || PY=python3

echo "conformance — every port must speak bit-identical ROLI"
step "golden vectors: clawd-core.js vs blocksd" node web/test-golden.mjs

echo "parity — the desk and the browser must draw the same creature"
step "clawdpadd.py vs clawd-core.js (41 cases, poses × costumes)" \
  "$PY" tools/parity.py

echo "renderers — every pose must draw something"
step "web poses (full + mini)" node tools/webpreview.mjs

echo "end-to-end — the browser's bytes must render on a device model"
step "software Lightpad: awake" "$PY" tools/emulate_block.py web --pose awake --frames 12
step "software Lightpad: qr (the pose that went blank in 2026-07)" \
  "$PY" tools/emulate_block.py web --pose qr --frames 6

echo "daemon"
step "event stream: raise → hold → tap → ack" "$PY" tools/test_events.py
step "clawdpadd.py imports + renders" "$PY" -c '
import importlib.util
s = importlib.util.spec_from_file_location("cp", "clawdpadd.py")
m = importlib.util.module_from_spec(s); s.loader.exec_module(m)
assert sum(1 for v in m.frame_awake(1.0) if v > 8) > 0, "frame_awake is blank"
assert m.battery_percent(31) == 100, "battery units regressed"
'
step "costumes.py imports + dresses" "$PY" -c '
import costumes
assert len(costumes.COSTUMES) > 0
buf = costumes.dressed("robot", 1.0, 0, 0, True, 0, 1.0)
assert len(buf) == 675 and sum(buf) > 0, "robot costume is blank"
'
# doctor must survive a broken machine — that is the only machine it ever meets.
# Its patch probes double as a regression test on the vendored fork: if someone
# pip installs over it, or a rebase drops a fix, this goes red here rather than
# on a dark glass at 2am.
step "doctor runs + finds the three blocksd patches" "$PY" -c '
import doctor
checks = {c.name: c for c in doctor.run()}
p = checks["blocksd patches"]
assert p.status == doctor.OK, f"patch probe says: {p.detail}"
assert all(c.fix for c in checks.values() if c.status == doctor.FAIL), \
    "a failing check with no fix — doctor prints fixes, not failures"
'

if [ -d blocksd ]; then
  echo "blocksd (vendored fork)"
  step "protocol + topology tests" "$PY" -m pytest blocksd/tests -q \
    --ignore=blocksd/tests/test_websocket.py --ignore=blocksd/tests/test_http.py
fi

echo
if [ "$FAIL" -eq 0 ]; then
  echo "✅ $PASS/$((PASS + FAIL)) — nothing drifted"
else
  echo "❌ $FAIL failed, $PASS passed"
fi
exit $((FAIL > 0))
