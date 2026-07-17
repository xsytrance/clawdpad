#!/usr/bin/env python3
"""test_events.py — the outbound event stream, without a block or a daemon.

The Level 3 contract in one file: a plugin raises something, Clawd holds it,
you tap the glass, the plugin learns it was acknowledged. That round trip is
what makes him an interface instead of a display — and until 2026-07-17 the
daemon had no way to say any of it out loud.

    .venv/bin/python3 tools/test_events.py
"""

from __future__ import annotations

import importlib.util
import queue
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def load():
    spec = importlib.util.spec_from_file_location("cp", ROOT / "clawdpadd.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def drain(q, timeout=0.5):
    out = []
    end = time.time() + timeout
    while time.time() < end:
        try:
            out.append(q.get(timeout=0.05))
        except queue.Empty:
            pass
    return out


def main() -> int:
    m = load()
    fails = []

    def check(name, ok, detail=""):
        print(f"  {'✅' if ok else '❌'} {name}{'  — ' + detail if detail else ''}")
        if not ok:
            fails.append(name)

    # ── the integration loop: raise → hold → tap → ack ──────────────────
    st = m.State()
    q = st.subscribe(None)
    now = time.time()
    st.apply({"cmd": "say", "arg": "you have mail", "seconds": 60}, now)
    evs = drain(q)
    check("a plugin raises something → 'notify' event",
          any(e["event"] == "notify" and e["text"] == "you have mail"
              for e in evs))
    check("he is actually holding it", st.mood(now) == "notify",
          f"mood={st.mood(now)}")

    res = st.touch_start(now + 1, 0.5, 0.5, 0.4)   # you tap the glass
    evs = drain(q)
    ack = [e for e in evs if e["event"] == "ack"]
    check("tap → 'ack' event, carrying what was acknowledged",
          res == "ack" and ack and ack[0]["text"] == "you have mail")
    check("the notify is cleared — he isn't still waving",
          st.mood(now + 1) != "notify")

    # ── filtering: a plugin only hears what it asked for ────────────────
    st2 = m.State()
    only_ack = st2.subscribe({"ack"})
    everything = st2.subscribe(None)
    n = time.time()
    st2.apply({"cmd": "say", "arg": "hi", "seconds": 30}, n)
    st2.touch_start(n + 1, 0.5, 0.5, 0.4)
    picky, greedy = drain(only_ack), drain(everything)
    check("a filtered subscriber gets only its kinds",
          [e["event"] for e in picky] == ["ack"],
          f"got {[e['event'] for e in picky]}")
    check("an unfiltered subscriber gets everything",
          {e["event"] for e in greedy} == {"notify", "ack"},
          f"got {sorted({e['event'] for e in greedy})}")

    # ── taps ────────────────────────────────────────────────────────────
    st3 = m.State()
    q3 = st3.subscribe(None)
    n = time.time()
    st3.touch_start(n, 0.5, 0.5, 0.4)
    st3.touch_end(n + 0.05)
    st3.touch_start(n + 0.1, 0.5, 0.5, 0.4)
    st3.touch_end(n + 0.15)
    kinds = [e["event"] for e in drain(q3)]
    check("double-tap surfaces as an event", "double-tap" in kinds,
          f"got {kinds}")

    # ── robustness: a wedged subscriber must never stall the render loop ─
    st4 = m.State()
    slow = st4.subscribe(None)
    for i in range(m.EVENT_QUEUE_MAX + 50):     # never read → queue fills
        st4.emit("tap", i=i)
    check("a subscriber that stops reading drops events instead of blocking",
          slow.qsize() == m.EVENT_QUEUE_MAX,
          f"queue held at {slow.qsize()}/{m.EVENT_QUEUE_MAX}")

    # ── deadlock: emit() is called from inside self.lock ────────────────
    st5 = m.State()
    st5.subscribe(None)
    done = threading.Event()

    def tap_a_lot():
        n0 = time.time()
        for i in range(200):
            st5.touch_start(n0 + i, 0.5, 0.5, 0.4)
            st5.touch_end(n0 + i + 0.05)
        done.set()

    threading.Thread(target=tap_a_lot, daemon=True).start()
    check("emit() from inside the state lock does not deadlock",
          done.wait(5.0), "touch loop would have frozen Clawd")

    # ── unsubscribe ─────────────────────────────────────────────────────
    st6 = m.State()
    q6 = st6.subscribe(None)
    st6.unsubscribe(q6)
    st6.emit("tap")
    check("unsubscribe detaches cleanly", q6.empty() and not st6.subs)

    print(f"\n{'❌ ' + str(len(fails)) + ' failed' if fails else '✅ the Level 3 loop works: raise → hold → tap → ack'}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
