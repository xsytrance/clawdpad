#!/usr/bin/env node
/* webpreview.mjs — render web/clawd-core.js frames as ASCII, no browser.
 *
 * CLAUDE.md's rule for the daemon ("preview frames as ASCII before shipping",
 * because Claude cannot see the glass) applies double to the web page: its
 * frames live in a browser tab, behind a WebMIDI permission prompt, on
 * hardware. This makes them inspectable from a terminal.
 *
 *     node tools/webpreview.mjs             # every pose, full + mini
 *     node tools/webpreview.mjs qr          # just the QR
 *     node tools/webpreview.mjs awake mini  # one pose, one size
 *
 * Exits non-zero if a pose renders blank — the failure mode that looks
 * exactly like "the glass is broken" from across the room.
 */

import { createRequire } from "module";
import { fileURLToPath } from "url";
import path from "path";

const require = createRequire(import.meta.url);
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const { Clawd } = require(path.join(root, "web/clawd-core.js"));
const { QR_BAKED } = require(path.join(root, "web/qr-data.js"));
globalThis.QR_BAKED = QR_BAKED;   // clawd-core reads it as a global, as in the page

const lit = (buf) => buf.reduce((n, v) => n + (v > 8 ? 1 : 0), 0);

function show(buf, title) {
  if (!buf) { console.log(`\n${title}\n  (null)`); return 0; }
  console.log(`\n${title}   [${lit(buf)} subpixels lit]`);
  for (let y = 0; y < 15; y++) {
    let row = "";
    for (let x = 0; x < 15; x++) {
      const i = (y * 15 + x) * 3;
      const l = (buf[i] + buf[i + 1] + buf[i + 2]) / 3;
      row += l > 90 ? "#" : l > 30 ? "+" : l > 6 ? "." : " ";
    }
    console.log("  |" + row + "|");
  }
  return lit(buf);
}

const POSES = {
  sleep:     { full: t => Clawd.dressed(0.22, 0, 0, false, 0, t), mini: t => Clawd.miniSleep(t) },
  awake:     { full: t => Clawd.awake(t),        mini: t => Clawd.miniAwake(t) },
  // thinking takes a phase accumulator, not t — pass a fixed phase to preview
  thinking:  { full: t => Clawd.thinking(2.0, t), mini: t => Clawd.miniThinking(2.0, t) },
  wave:      { full: t => Clawd.wave(t),         mini: t => Clawd.miniWave(t) },
  celebrate: { full: t => Clawd.celebrate(t),    mini: t => Clawd.miniCelebrate(t) },
  dance:     { full: t => Clawd.dance(t, 0.8, 0.9), mini: t => Clawd.miniDance(t, 0.8, 0.9) },
  qr:        { full: () => Clawd.qr("CLAWDPAD"), mini: () => Clawd.qr("CLAWDPAD") },
};

const [wantPose, wantSize] = process.argv.slice(2);
const poses = wantPose ? [wantPose] : Object.keys(POSES);
const sizes = wantSize ? [wantSize] : ["full", "mini"];

let blank = [];
for (const p of poses) {
  if (!POSES[p]) { console.error(`unknown pose: ${p}`); process.exit(2); }
  for (const s of sizes) {
    const n = show(POSES[p][s](0.3), `${p} · ${s}`);
    if (n === 0) blank.push(`${p}/${s}`);
  }
}

if (blank.length) {
  console.error(`\n❌ BLANK: ${blank.join(", ")} — renders nothing`);
  process.exit(1);
}
console.log("\n✅ every pose renders something");
