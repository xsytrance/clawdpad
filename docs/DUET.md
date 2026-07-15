# Duet — two Clawds, together

*Design note, 2026-07-15. Ships in Basic (snap mode) and Pro (federation).
Prompted by: "my coworker charles has one of these."*

## Why this is very possible

ROLI blocks have **DNA connectors** — the magnetic edges. Snapped together,
blocks form a hardware topology the SysEx protocol reports natively (up to
6 devices; each connection says which block, which edge). The master block
relays every snapped block over the single USB/BLE link, and blocksd
already parses this (`Topology: N devices, M connections`) and can address
each block's heap by uid. Two snapped Lightpads = one host sees a
**30×15 (or 15×30) canvas across a visible seam**.

So the no-middleman answer is literal: **the blocks interact by touching.**

## Three tiers

### 1. Snap mode (Basic) — same desk, zero middleman

Charles's block clicks onto yours. clawdpadd notices the topology change
(a doorbell moment: both Clawds turn and look at the seam), loads the LED
program on the guest block, and switches to duo scenes:

- **greet** — both walk to the seam, wave at each other
- **dance** — mirrored bobbing, alternating jumps, synced to a beat the
  host plays through its speakers
- **chase** — one runs off the edge of block A and *appears on block B*
  (the seam is a doorway, not a wall), the other follows
- **fight** — square up at the seam, bump, stagger back, shake it off;
  loser sits down; winner jumps (nobody gets hurt, it's slapstick)
- **pair-code** — one paces (driving), one sits watching with tracking
  eyes (reviewing); they swap when the real Claude Code session's energy
  spikes; both jump when a task lands
- **talk** — see Voices, below

Both surfaces stay touch-alive: pet either Clawd; tap one to make it the
scene leader. Guest identity: Charles's block carries its serial — his
Clawd can render subtly his (a different eye-blink rhythm, a one-pixel
accessory), so it's *his* creature visiting, not a clone.

Scenes render **mini Clawds** (`_mini()`, shipped 2026-07-15 — 5x4 body,
chibi proportions, `blockctl size mini`): full-size Clawd fills a whole
block, so duets need small actors with room to move. Solo mini mode is the
same sprite roaming his block like a room (and the surface the companion
app's home/items build on — see APP.md).

Implementation notes (all within the current stack):
- blocksd: `set_led_data(uid, …)` is already per-device; needs verifying
  that `_load_led_program` runs for DNA-relayed guests (it should — it's
  keyed on API-connect per uid).
- clawdpadd: render a W×2H or 2W×H scene buffer and split it per uid using
  the topology connection map (edge + orientation).
- Scenes are data: a timeline of `(actor, pose, dx, dy, sound)` keyframes —
  the same format Pro later opens to the community.

### 2. LAN / tailnet federation (Basic-friendly) — two desks, no third box

Each block keeps its own host running clawdpadd (that's not a middleman —
it's the creature's own body). The daemons peer directly:

- Pairing: `blockctl befriend http://<host>:8137 <token>` (or mDNS
  discovery on the LAN).
- Sync: the leader sends `{"scene": "dance", "t0": <epoch+2s>}`; both
  daemons render the same scene timeline locally from t0 — no frame
  streaming between hosts, so sync survives jitter (NTP-close clocks are
  plenty at 20 fps).
- Presence: each Clawd shows a tiny "friend online" tell (an occasional
  glance toward the friend's edge of the glass).

### 3. Internet federation (Pro) — different buildings, ntfy as the wire

The ntfy.sh channel clawdpadd already speaks becomes the duet wire: a
shared secret topic per friendship, scene/feeling events (never pixels),
same t0 sync trick. Latency is irrelevant because only *scene starts* are
synchronized, not frames.

**The killer feature — Traveling Clawd:** your Clawd walks off the edge of
your block… and walks onto Charles's, across the office or the planet. His
glass shows *your* creature (guest rendering by serial/identity), yours sits
empty except a tiny "away" ember until he walks home. Visits, greetings,
leaving a prop behind as a gift. This falls out of federation + scenes
almost for free, and nobody who sees it will shut up about it.

## Voices (the "talk" and music ask)

The Lightpad has no speaker — sound comes from each host's speakers (or a
Bluetooth speaker per desk; PipeWire doesn't care). The synth engine
already in clawdpadd is enough for:

- **Clawd-speak**: Animal-Crossing-style melodic babble — call-and-response
  phrases generated from a per-Clawd voice (Rod's a fourth lower than
  Charles's, say). A "conversation" is alternating babble + matching poses
  (lean in, nod, the occasional shocked jump). Text-free, universal, very
  funny when one of them does a long rant.
- **Jam mode**: leader emits a chord progression as events; follower
  harmonizes (arpeggios over the same changes). Snapped mode = one host
  plays both voices in stereo. Federated = each desk plays its own part —
  same t0 trick keeps them in time.
- Pro: MIDI-out of the jam (the block is, after all, an instrument), so a
  real synth/DAW can render what they're playing.

## What ships where

| capability | Basic | Pro |
|---|---|---|
| Snap mode: topology detect, duo scenes (greet/dance/chase/fight/pair-code) | ✅ | ✅ |
| Clawd-speak voices + jam (local) | ✅ | ✅ |
| LAN/tailnet befriend | ✅ | ✅ |
| Internet federation (ntfy), Traveling Clawd | — | ✅ |
| Custom/community scenes + voices | — | ✅ |
| Colony (3–6 blocks, one creature each) | — | ✅ |

Open verification items (need a second block in hand — hi, Charles):
DNA-relayed program upload; per-guest frame bandwidth over one USB link at
2×20 fps (worst case: drop to 15 fps each, invisible); topology edge/
orientation mapping for the seam math.
