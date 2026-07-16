// Golden-vector validation for clawd-core.js (node web/test-golden.mjs)
import { createRequire } from "module";
import { readFileSync } from "fs";
const require = createRequire(import.meta.url);
const { Protocol, BitWriter, PacketBuilder, HeapStreamer } =
  require("./clawd-core.js");

const golden = JSON.parse(readFileSync(
  new URL("../../clawdpad-app/app/src/test/resources/golden.json",
    import.meta.url).pathname.startsWith("/") ?
  "/home/xsyprime/clawdpad-app/app/src/test/resources/golden.json" :
  "golden.json", "utf8"));

const b64 = s => Uint8Array.from(Buffer.from(s, "base64"));
const eq = (a, b) => a.length === b.length && a.every((v, i) => v === b[i]);
let failures = 0;
const check = (label, ok) => {
  if (!ok) { console.error("FAIL", label); failures++; }
};

// packing
golden.packing.forEach((c, i) => {
  const w = new BitWriter(256);
  for (const [v, bits] of c.fields) {
    if (bits > 16) {
      w.writeBits(v & 0xFFFF, 16);
      w.writeBits(Math.floor(v / 65536) & 0xFFFF, bits - 16);
    } else w.writeBits(v, bits);
  }
  check(`packing ${i}`, eq(Array.from(w.getData()), Array.from(b64(c.packed))));
});

// checksums
golden.checksum.forEach((c, i) =>
  check(`checksum ${i}`, Protocol.checksum(b64(c.payload)) === c.checksum));

// commands
const cmds = golden.commands;
check("ping9", eq(Array.from(PacketBuilder.ping(9)), Array.from(b64(cmds.ping_idx9))));
check("ping0", eq(Array.from(PacketBuilder.ping(0)), Array.from(b64(cmds.ping_idx0))));
check("topo0", eq(Array.from(PacketBuilder.requestTopology(0)), Array.from(b64(cmds.topology_idx0))));
check("begin9", eq(Array.from(PacketBuilder.beginApi(9)), Array.from(b64(cmds.begin_api_idx9))));
check("end9", eq(Array.from(PacketBuilder.endApi(9)), Array.from(b64(cmds.end_api_idx9))));

// boot + transitions
const program = b64(golden.program);
const hs = new HeapStreamer(9, 1);
hs.setBytes(0, program);
const boot = hs.drain();
check("boot count", boot.length === golden.boot.length);
boot.forEach((p, i) =>
  check(`boot ${i}`, eq(Array.from(p), Array.from(b64(golden.boot[i])))));
golden.transitions.forEach((tr, t) => {
  hs.setBytes(program.length, b64(tr.frame));
  const pkts = hs.drain();
  check(`transition ${t} count`, pkts.length === tr.packets.length);
  pkts.forEach((p, i) =>
    check(`transition ${t} pkt ${i}`, eq(Array.from(p), Array.from(b64(tr.packets[i])))));
});

console.log(failures === 0
  ? "GOLDEN: ALL PASS — clawd-core.js speaks bit-identical ROLI"
  : `GOLDEN: ${failures} FAILURES`);
process.exit(failures === 0 ? 0 : 1);
