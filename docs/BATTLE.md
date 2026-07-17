# Battle mode — Bug · Ship · Test

*Design, 2026-07-17, from Rod's ask: "rock paper scissors, but with a Claude
touch, make it coding related." Lives in the `clawdpad-app` repo (Expo,
Android first); needs small daemon additions listed at the bottom. Nothing
built yet — this is the design.*

## The throw

Rock-paper-scissors is a perfect machine and you don't improve it by adding a
fourth move. You improve it by making the three mean something:

| | beats | because |
|---|---|---|
| 🧪 **Test** | 🐛 Bug | a test catches it |
| 🐛 **Bug** | 🚀 Ship | a bug blocks the release |
| 🚀 **Ship** | 🧪 Test | "ship it" overrules the test |

Test → Bug → Ship → Test. Every edge is a one-line joke that every developer
has lived, and the third one is the one that gets the laugh, because everybody
knows who wins that argument in real life.

The ceremony is git: each round is a **commit**, you lock in your throw
(**commit**), the glass counts down, both reveal (**push**), and a match —
best of five — is a **sprint**. Winning the sprint is **merged**. Losing is
**reverted**.

## The Claude touch — you're playing against your own workday

Here's the part that isn't rock-paper-scissors: **Clawd does not throw
`random()`.** His hand comes from his actual state, which comes from your
actual day.

- **High energy** (you've been hammering Claude Code all afternoon — the hooks
  already drive energy with a 25 s tau) → he throws **Ship** more. He's caught
  your momentum and he's reckless with it.
- **Tired** — low battery, late hour, an idle stretch → he throws **Test**. The
  cautious hand.
- **Hungry / neglected** (dazzler's soul: vigor and hunger, mirrored read-only)
  → he throws **Bug**. He's a little feral and he wants to break your stuff.

So the metagame is: *you already know what kind of day you had.* A Clawd who's
been watching you push to main since breakfast is a Clawd who will throw Ship,
and you can punish him for it — with a Bug. The game reads your work back to
you and lets you exploit it. **That's the touch.** No other RPS can do this,
because no other RPS is attached to a creature that's been watching.

Weight the distribution; never make it deterministic. Something like a base
33/33/33 shifted by ±20 points on the strongest signal. **If it becomes
readable enough to solve, it stops being a game** — he should lean, not
telegraph a solved answer. Tune it against real logs, not vibes.

## The tell — the skill layer, and it's canon

**Everything on the glass is body language** (iron rule). So Clawd doesn't get
a UI hint that leaks his move — he gets *nervous*.

During the three-second countdown he paces, and **his gait leaks his hand**:

- about to **Ship** → he bounces, front-heavy, leaning toward you
- about to **Test** → he goes still, weight back, watching
- about to **Bug** → a twitch, a glance away

Subtle enough that round one is a coin flip and round five isn't. This is the
one thing that turns RPS from luck into a read, it costs nothing but three
gaits, and it's *exactly* what the project already claims to be: a creature you
learn to read. Make the tell honest — it must correlate with the real throw, or
players will find out and it'll feel like a slot machine.

## Commit, then reveal — the fairness rule

**Clawd must lock his throw before yours is accepted, and the daemon must be
able to prove it.** Emit the committed hand on the event stream (or a hash of
it, which is the joke: `commit` then `reveal`) the moment the countdown starts.
Any design where the host picks *after* seeing your hand is not a game, it's a
mood ring, and someone reading the source will notice within a minute.

This matters more than it sounds: the tell is only fun if the throw was real.

## Rules that keep it alive

- **No repeats.** You can't throw the same hand twice in a row. Kills spam and
  forces mixing; the tell does the rest.
- **Best of five**, because three is a coin flip and seven is a chore.
- **Stakes tie to the soul.** Winning feeds him a little XP (the app already
  has hunger/xp/level/meals — APP.md). Losing, he *gloats*: the celebrate pose
  is already built and it is genuinely annoying to lose to, which is correct.
- **He remembers.** A running record — "you're 12–9 down" — and a grudge: beat
  him three straight and he starts throwing meaner.
- **The block is the arena; the phone is your hand.** Fits the hosts/controllers
  rule exactly (LEVELS.md): the app is a controller, the glass is the show. You
  throw on the phone, Clawd throws on the glass, and *the countdown happens on
  the block* so both people at the desk are watching the same object.

## Levels

- **Today (L1 + controller):** phone app vs your Clawd, one block. This is the
  buildable version.
- **L4, the good one:** battle a *friend's* Clawd across the network. Two
  blocks, two glasses, each showing its own creature's hand — pong already
  spans a pair (DUET.md), so the arena code mostly exists. Rod vs Charles, two
  desks, two blocks, one throw. That's the demo.
- **Glass-only, no phone (L0/L1):** throw with a gesture on the block itself —
  swipe up = Ship, tap = Test, scribble = Bug. Depends on the $1-recognizer
  from ROADMAP's gesture-commands item. Worth it later: a game with no screen
  at all.

## Art — three props, not three pictures

The throws are **props** (ROADMAP's props system, the L3 foundation): 5×4-ish
sprites with an anchor, composed onto a pose — Clawd *holds* his hand out, he
doesn't get replaced by an icon.

**Solid chunky shapes only.** The rocket is a fat wedge, the flask a squat
beaker, the bug a blob with two legs and two antennae. The silicone diffuses
1-px detail into disconnected dots — this is the "creepy spider" rule
(2026-07-15) and a 15×15 rocket is exactly where someone will forget it.

Per POSES.md, the order is not negotiable: **author in `web/clawd-core.js`
first**, preview with `node tools/webpreview.mjs`, mirror into `clawdpadd.py` /
`costumes.py`, add to `CASES` in `tools/parity.py`, then `tools/check.sh`
green. The countdown and reveal are poses; the props ride on top.

## What the daemon owes this

Small, and mostly things the roadmap already wants:

| addition | notes |
|---|---|
| `POST /battle` → `{"cmd":"battle","hand":"ship"}` | start a round / submit a hand |
| `battle` events on the stream | `countdown`, `commit` (hash), `reveal`, `result` — the event stream shipped 2026-07-17, so this is a new kind, not new plumbing |
| three props + countdown/reveal poses | clawd-core.js first |
| `GET /battle/record` | the running score and the grudge |

The state machine is tiny — idle → countdown(3s) → locked → reveal → result —
but it must live in the **daemon**, not the app. The glass has to show the
countdown even if the phone dies mid-round, and an L4 match has two apps and
one truth. Put the referee where the block is.

## Open questions

1. **Is the tell too subtle on a 15×15 glass?** Three gaits that read at arm's
   length is the whole skill layer and it might just not fit. Prototype the
   gaits before building the game around them — `webpreview.mjs` costs minutes.
2. **Does energy-weighting make him exploitable?** A player who knows the rule
   might beat him 70/30, which is either delicious or broken. Needs real logs.
3. **Does losing hurt the soul?** Tempting, and probably wrong — the soul is
   dazzler's and it's read-only here (iron rule). Battle XP should be the app's
   own counter until Rod says otherwise.
4. **Does he ever refuse to play?** A sleeping Clawd at 2 a.m. who rolls over
   and ignores you is better character than a game that's always available.
