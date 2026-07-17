# Making Costumes for Clawd 👒

Clawd's wardrobe is just pixel art on a 15×15 grid. Anyone can add to it —
here's how, plus a pile of ideas to steal.

## Two kinds of costume

- **Prop** — something Clawd *wears*. His normal body renders first, then
  your prop paints on top. It rides his bob, lean, and jumps automatically
  because you offset every pixel by `dx, dy`. Good for: hats, glasses,
  bowties, halos, anything on/around him.
- **Skin** — a whole *different body*. You render whatever you want; Clawd's
  behaviors (breathe, blink, pace, dance) still drive `brightness`, `dx/dy`,
  and `eyesOpen`, so your creature stays alive. Good for: characters.

## Where the art lives

One function, mirrored in three places (keep them identical):
- `web/clawd-core.js` — **canonical. Author here first**, always (see below).
- `clawdpad-app/.../Costumes.kt` — the Android app.
- `costumes.py` — the desk daemon.

The arrow only ever points *out* of `clawd-core.js`. This isn't a style
preference: until 2026-07-17 `costumes.py` called clawd-core.js the source of
truth while clawd-core.js called `clawdpadd.py` the source of truth, and with
each naming the other there was nothing to diff against — so when a costumed
Clawd could wave in the browser but not on the desk, neither side was wrong.
Author in JS, mirror out, and that can't happen again.

Register the costume in each file's list (`COSTUMES` / `Clawdrobe.ALL`)
with an id, emoji, label, and the skin flag; add a dispatch branch.

Mirroring by hand is the tax for having three bodies. `tools/check.sh` catches
a costume that renders blank, but nothing catches a costume that renders
*differently* in each — so do them in one sitting, not "later".

## The one trick that saves you: verify headlessly

You do **not** need a Lightpad to design a costume. Render it as ASCII in
your terminal:

```bash
node -e '
  const {Clawd} = require("./web/clawd-core.js");
  Clawd.costume = "pumpkin";                 // your id
  const f = Clawd.awake(1.0);
  for (let y=0; y<15; y++) {
    let r="";
    for (let x=0; x<15; x++){const i=(y*15+x)*3;
      r += (f[i]+f[i+1]+f[i+2])>0 ? " #" : " .";}
    console.log(r);
  }'
```

If it looks right in the terminal, it looks right on the glass. Every
shipped costume was tuned this way before touching hardware.

## Pixel tips for 15×15

- **Chunky beats detailed.** The silicone weave diffuses thin 1px lines —
  solid shapes read; hairlines vanish. (We learned this the hard way.)
- The body sits roughly x2–12, y3–10; eyes at y5–6; hats go y0–2; a
  chin/neck accessory sits around y10–11.
- Colors get quantized to RGB565 on the block — pick punchy hues; muddy
  midtones wash out.
- Multiply your colors by `brightness` so the costume dims/brightens with
  his breathing (props can skip this for hard accents like a gold crown).

## Idea prompts (draw your own — no copying real IP)

- a hungry yellow circle that chomps
- a shy pink puffball who inhales trouble
- four spooky arcade roommates in four colors
- a certain plumber's hat, legally distinct
- a green pipe-dwelling fellow
- a blocky sandbox miner
- a red-capped mushroom with white spots
- a tiny wizard, a tiny knight, a tiny astronaut
- googly-eyed slime, a disco ball, a lava lamp
- seasonal: jack-o-lantern, snowman, cupid heart, four-leaf clover,
  turkey, menorah, fireworks
- your pet, your team's mascot, your own logo

If you make something great, PR it to the originals pack. Keep famous
characters in your own local pack — personal use is yours; publishing
someone else's IP is the only line.

## Minimal prop example (JavaScript)

```js
// in Clawd.prop(), add a branch:
} else if (id === "antenna") {
  P(7 + dx, 0 + dy, 255, 80, 80);   // red bulb
  P(7 + dx, 1 + dy, 120, 120, 120); // stalk
}
```

That's a whole costume. Add it to `COSTUMES`, mirror into Kotlin/Python,
ASCII-check, done.
