# The levels — how far Clawd travels from the tab

*Written 2026-07-17, from Rod's sketch. Rod gave levels 0, 2 and 3; the gap at
1, the level 4, and everything under "ideas" are mine and are proposals, not
decisions. The ladder is the spine — argue with the rungs, not the shape.*

The question this answers: **how much do you install, and what is Clawd allowed
to talk to?** Every rung must be a complete, shippable creature on its own. A
level is not a milestone toward the next one — it's a product someone stops at.

## The ladder

| | Name | Install | Clawd talks to | State |
|---|---|---|---|---|
| **L0** | The Tab | nothing | the block in front of you | ✅ **shipped** |
| **L1** | The Daemon | clone + venv + units | the block, your hooks, your LAN | ✅ **shipped** (Linux) |
| **L2** | The App | one signed download | the source device + its blocks | 🔜 the ask |
| **L3** | The Connected App | L2 + consented integrations | + email, chat, agents, calendar | 🔜 the ask |
| **L4** | The Colony | L3 + a peer | + other blocks, other people's Clawds | 💭 my proposal |

### You skipped 1, and I think I know why

Rod's sketch went 0 → 2 → 3. I don't know whether that was a typo or a slot
held open, but **level 1 already exists and has for months: it's `clawdpadd`.**
It's an install, it's headless, it's always-on, it owns the hooks and the
multi-block topology, and it talks to nothing but your own machine and your
own network. It was invisible in the sketch precisely because it's the thing
we've been living in.

Naming it costs nothing and buys a lot: it means **L2 is not a from-scratch
project.** It's L1 with a face and a code-signing certificate.

### Two axes, not one

The ladder looks like a single line but it's two different questions, and
conflating them is how a scope doubles by accident:

- **L0 → L1 → L2 is distribution.** Same creature, same capabilities; the only
  thing changing is how much a stranger has to install and whether it survives
  a reboot. **This axis is mostly build engineering, not product.**
- **L2 → L3 → L4 is connectivity.** Same install; what changes is the trust
  boundary and the blast radius. **This axis is mostly product and consent,
  not engineering.**

They're independent. A connected daemon (L1+L3) is a real, useful thing that
exists today via ntfy. Don't let the numbering imply you must ship L2 to earn
L3.

### Hosts and controllers — an existing collision

`docs/APP.md` (`clawdpad-app`, Expo) and `docs/WEAR.md` (`clawdpad-wear`,
Kotlin) both already describe apps. **They are not this.** Their iron rule is
"the app talks to the daemon, never the block" — they are *controllers*, and
they require an L1 daemon somewhere.

Rod's L2 is the opposite: the app **is** the host, no daemon at all.

So the family sorts into two kinds, and every future doc should say which:

- **Hosts** own the block: keepalive, frames, topology. The tab (L0), the
  daemon (L1), the app (L2). Exactly one host per block, always.
- **Controllers** poke a host over HTTP/ntfy: the phone, the watch. They can't
  exist alone and they never touch the glass.

L2 makes the phone app *both*, which is genuinely new and should be a
deliberate decision rather than a merge conflict.

---

## L0 — The Tab ✅

**Who:** an office visitor. Charles, at a table, with a block and no
permission to install anything.

Shipped and proven: `web/index.html` + `clawd-core.js`, Chrome/Edge over
WebMIDI, **USB or Bluetooth**, no daemon (docs/MACBOOK.md Phase 2–3).

**The constraint that shapes everything above it: iOS cannot do L0.** No
WebMIDI in any iOS browser, Safari included, and that is not changing on our
schedule. Android Chrome is fine. So the iPhone's *only* path to hosting Clawd
is L2 — which means L2 isn't a convenience tier, it's the only door for a
whole platform. That is the strongest argument for building it.

**Keep true:** L0 must never require the levels above it. It's the demo, the
onboarding, and the fallback when a signed app won't install.

## L1 — The Daemon ✅

**Who:** us. Anyone with a terminal and a machine that's always on.

Shipped: `clawdpadd.py` + `blockctl`, systemd units, hooks, soul link, HTTP
:8137, ntfy, the event stream. Linux today; macOS proven for the stack but not
packaged (docs/MACBOOK.md Phase 1).

**What it still owes:** `blockctl doctor` and `install.sh` (ROADMAP Basic 1–2).
Those are L1's real gap, and — see below — **they are also L2's foundation.**

## L2 — The App 🔜

**Who:** someone who bought a block, has no terminal, and wants a creature.

**The bar:** download, open, Clawd is alive. No Python, no venv, no units, no
Chrome tab left open forever. Launch at login, tray/menu-bar presence, survives
sleep and replug.

**Talks to:** the source device and its blocks. Nothing else. Airplane mode is
a supported configuration.

**Platforms:** macOS first (Rod's ask, and Charles's demo machine), then
Windows/Linux, then iOS/Android.

**Done when:** a stranger with a block and no dev tools has Clawd on their desk
in under two minutes, and it's still there tomorrow morning.

## L3 — The Connected App 🔜

**Who:** the person who wants the creature to *know things*.

**Talks to:** L2 plus integrations the user consented to, one at a time, each
revocable. Email, chat, Claude Code, calendar, CI.

**The good news: the plumbing shipped on 2026-07-17.** The outbound event
stream (`subscribe` / `GET /events`, `notify` → `ack`) is already the
integration API. L3 is not new protocol — it's a **plugin host over the
existing event contract**, plus a consent UI. See docs/MANUAL.md §7b and
ROADMAP's Pro section, which is L3 in all but name.

**Done when:** an integration can be installed, seen doing something, and
revoked, without the user learning what a Bearer token is.

## L4 — The Colony 💭 *(my proposal)*

**Who:** two people who each have a block, and every agent you run.

Not speculative — it's mostly shipped and unnamed. `visit` already migrates
Clawd XC5G → SH8T, pong already spans a pair, DNA-linked blocks already merge
into one house (docs/DUET.md). L4 is that, across a network instead of a
ribbon cable: **Clawd walks off your block and onto your friend's.** ROADMAP
already calls this "Traveling Clawd" and calls the agent version a "colony —
one block per agent."

L4 is the only level with a *product* argument rather than a convenience one.
Nobody else is selling a creature that visits.

---

## The spine — one soul, N bodies

The rule that makes this ladder affordable, and the one thing I'd protect
above all else:

> **Platforms port the transport. They never port the art.**

`web/clawd-core.js` is canonical (CLAUDE.md, docs/POSES.md) and it does two
things: it draws Clawd, and it speaks ROLI — and golden vectors prove the
second is bit-identical to blocksd. So **a new body needs exactly one new
thing: a `send(bytes)` that reaches a block.** Poses are pure functions. The
protocol is solved. The platform-specific surface is MIDI I/O and nothing else.

This is why **a native Swift host is the wrong instinct**, tempting as it is
for iOS (docs/CHARLES.md:130 currently floats it as a roadmap item). It forks
the art, breaks the one-arrow rule that 2026-07-17's audit was written in
blood to establish, and turns `parity.py` from a 2-body problem into an N-body
one. Swift should write a CoreMIDI transport and hand bytes to `clawd-core.js`.
Then parity stays green for free, forever, and it stays a 2-body problem no
matter how many platforms ship.

### The webview trap — check this before choosing a shell

**This will cost an evening if we get it wrong, so it goes in writing now.**
WebMIDI is a Chromium feature, not a web standard everyone implements:

| Shell | Engine | WebMIDI? | Verdict |
|---|---|---|---|
| Electron | bundles Chromium | **yes** | works today, ~150 MB, boring, ships |
| Tauri | *system* webview (WKWebView on macOS) | **no** | needs a native MIDI bridge |
| Capacitor / iOS | WKWebView | **no** | needs a native MIDI bridge |
| Capacitor / Android | Chrome WebView | probably | **verify before planning** |

So the choice is: **Electron and inherit L0's working transport unchanged**, or
**Tauri/Capacitor and write the `send(bytes)` bridge per platform** — which is
the same bridge iOS needs regardless, and which the spine above says is cheap
and correct.

My lean: **Tauri on desktop, Capacitor on mobile, one shared native transport
plugin per OS.** Electron is the fast path to a Mac demo, and if the goal is a
thing in Charles's hands, take it and don't apologize. But the bridge is
unavoidable for iOS, so writing it once buys every platform and a 10 MB binary
instead of 150.

**Verify before committing to any of this:** does a WKWebView Tauri app get
Web *Bluetooth*? BLE is half of what made Phase 3 historic, and losing it would
undo the best result we have.

## Rules that hold at every level

1. **Every level degrades downward.** L3 offline is a well-behaved L2. L2 with
   no integrations is a creature, not a settings screen. L0 works when the
   signed app won't install — which, on a locked-down office laptop, is the
   likeliest failure on demo day.
2. **Integrations never draw.** They say *what happened*; Clawd decides how to
   be about it. This is ROADMAP's props-and-poses rule and it's what keeps
   every integration looking like him.
3. **The attention budget.** *(new — I think L3 dies without it.)* Cap the
   interruptions: N per hour, one held thing at a time, everything else becomes
   ambient body language instead of a wave. Twelve integrations at default
   settings is a notification firehose with a mascot, and that is exactly the
   dashboard the whole project refuses to be. **The budget is the feature.**
4. **Local-first, consent per integration.** Integrations run on the source
   device. No cloud relay by default, nothing enabled it didn't ask for,
   everything revocable in one click. Charles *will* ask where the email
   goes; the answer should be "nowhere."
5. **One host per block, always.** Two hosts fight over the keepalive. When the
   app takes over from the tab, the tab must visibly let go.

---

## The idea bank

Tagged by level. None of these are decided. Everything here obeys rule 2 —
the integration reports an event, Clawd emits body language.

### Bootstrapping and onboarding

1. **The glass is the installer.** *(L0→L2)* The QR pose already works. Block
   shows a QR → phone scans → tab opens → tab offers the app. L0 becomes the
   funnel into L2, and the block onboards itself with no packaging or URL to
   type. This is my favorite idea in the doc.
2. **`blockctl doctor` becomes the app's first-run screen.** *(L1→L2)* Doctor
   is already the top of the roadmap and it's the same work twice — the checks
   a CLI prints are exactly the checks a first-run wizard shows with a Fix
   button. **Build doctor as a library with two faces, not a script.**
3. **The tab hands off.** *(L0→L2)* If the app is installed, the tab detects it
   and offers "let the app take it" — one host, gracefully transferred (rule 5).
4. **Demo mode.** *(L0)* No block? Render Clawd on a canvas in the page. The
   whole art layer is pure functions already; `webpreview.mjs` proves it runs
   headless. Now the project has a landing page that *is* the product.

### The app itself

5. **Clawd in the menu bar.** *(L2)* The tray icon is Clawd, mirroring the
   glass at 16×16 — same pose, same mood. `mini`/chibi already renders at
   quarter scale. His body language leaks into your desktop.
6. **The block is the second monitor.** *(L2)* Screensaver mode: when the Mac
   sleeps or locks, Clawd sleeps too. Wake together. Free, and it's the kind of
   detail that makes people say it's alive.
7. **Costume packs as files you double-click.** *(L2)* `.clawdfit` opens in the
   app. The Clawdrobe becomes shareable without a registry.
8. **Multi-block canvas in the app.** *(L2)* The daemon does DNA topology
   today; the app should show it — drag blocks into their physical arrangement,
   see the seam, see him walk between them.
9. **Battery-aware host.** *(L2)* Extend battery body language to the *host*:
   on laptop battery, drop fps and dim. The multipliers already compose
   (`battery_pace`/`vigor`/`tired`) — this is a new input to shipped machinery,
   not a new feature.

### Integrations (L3) — each is an event, never a drawing

10. **Email → the envelope.** *(Rod's ask.)* He holds it in his mouth until you
    tap. Tap = read. The `notify`→`ack` loop, already shipped, is exactly this
    shape — the envelope prop is the only missing piece.
11. **Claude Code, off-machine.** *(L3)* Hooks are L1 and local-only today. The
    version worth having: your laptop's Clawd paces for the session running on
    your desktop. This is the one integration *we* would use daily, and it's
    the one that makes the project self-hosting.
12. **Chat mention.** *(L3)* Slack/Discord/Messenger: someone says your name,
    Clawd taps the glass from the inside. Not a count. Not a preview. A tap.
13. **Calendar.** *(L3)* The clock prop; he gets antsy as the meeting nears,
    paces faster inside T-5. Tap to snooze. Urgency is already a gait.
14. **CI / deploy.** *(L3)* Red hard-hat while deploying, the jump on green,
    the sad pose on red (ROADMAP Basic 7 — the one missing emotion, and this is
    its best customer).
15. **On-call.** *(L3)* The single integration allowed to override quiet hours
    and the attention budget. Exactly one. It has to be earned, and having a
    named exception is what keeps rule 3 honest.
16. **Weather as costume.** *(L3)* Not a forecast — an umbrella when it'll rain
    today, sunglasses when it's bright. The costume system already exists; this
    is content, not code.
17. **Focus / pomodoro.** *(L3)* He sleeps while you focus and wakes at the
    break — the block becomes a commitment device. Notably this one makes Clawd
    *quieter*, which is the direction rule 3 wants.
18. **Now playing.** *(L3)* `dance` exists and is mic-driven; a real audio
    source makes it accurate instead of ambient. PRISM's `lightpad-out` already
    proves the pipe (docs/CHARLES.md).

### The colony (L4)

19. **Traveling Clawd, for real.** *(L4)* `visit` hops blocks over DNA today.
    Over a tailnet, he walks off your block and onto a friend's, and your glass
    is empty until he comes home. The empty-glass night-light pose already
    exists in Python and was built for exactly this.
20. **Presence.** *(L4)* Your block shows a teammate's Clawd asleep when they're
    heads-down. Ambient, no text, no status string. The most humane
    availability indicator anyone's built.
21. **The agent colony.** *(L4/Pro)* One block per agent, DNA-linked into a
    literal colony; overall mood is the argmax of their states. ROADMAP already
    describes this and it's the most *Anthropic* thing in the whole idea bank —
    a physical, calm, honest display of what your agents are feeling.
22. **Clawd knocks.** *(L4)* Before a visit, the guest block gets a knock and
    the human taps to let him in. Consent (rule 4) as body language rather than
    a permission dialog. This is the pattern the whole L3/L4 trust story should
    copy.
23. **Battle mode.** *(controller today → L4)* Bug · Ship · Test — RPS where
    Clawd's hand comes from your actual workday and his gait tells during the
    countdown. Buildable now against one block; the version worth having is two
    desks, two blocks, Rod vs Charles. Full design: [BATTLE.md](BATTLE.md).

---

## How this maps onto Basic/Pro

ROADMAP.md already has a taxonomy — **Basic** ("he just lives there") and
**Pro** ("the ecosystem"). It isn't wrong and it isn't this. Basic/Pro is a
*feature tier*; levels are a *capability ladder*.

The honest mapping: **Basic ≈ L0–L2. Pro ≈ L3–L4.** Pro's whole section — props,
the event API, the feeling API, agent presence, the registry — is L3's feature
list written a month early, and its "Traveling Clawd" is L4.

**Recommendation: levels become the primary spine and ROADMAP's Pro section
gets folded into L3 rather than maintained twice.** Two taxonomies for one
project is how docs start lying to each other — which is precisely the failure
POSES.md was written to end, when clawd-core.js and clawdpadd.py each named the
other as canonical and drift had no reference to resolve against. I have not
done that surgery yet; it's a real edit to a real doc and it's Rod's call.

## Open questions — the ones that change what gets built

1. **Does L2 replace the daemon or sit beside it?** If a Mac user installs the
    app and also wants Claude Code hooks, is there one host or two? (Rule 5
    says one. It probably means **the app embeds the daemon**, which makes L2
    mostly a packaging project and the L1 → L2 story nearly free — this is the
    single biggest scope question in the doc.)
2. **Electron now for the demo, or the bridge once for everything?** See the
    webview trap. Demo day pressure argues one way; iOS argues the other.
3. **Is L2 for Charles's demo, or after it?** Phase 4 is still unrun. A signed
    Mac app in two weeks and a wireless PRISM finale are not the same bet, and
    L0-over-BLE already *is* the finale.
4. **Does the phone app become a host (L2) or stay a controller (APP.md)?**
    Both is defensible; unstated is not.
5. **Who's the L2 user, really?** "Bought a block, no terminal" is a guess I
    made. If the actual answer is "Rod's colleagues who all have terminals,"
    the whole tier gets smaller and `install.sh` might be the entire product.
