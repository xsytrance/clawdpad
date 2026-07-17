/* clawd-core.js — the ROLI BLOCKS protocol + Clawd renderer, in the browser.
 *
 * ┌─ THIS FILE IS CANONICAL for Clawd's art and poses. ──────────────────┐
 * │ Change a pose or a costume HERE first, then mirror it into           │
 * │ clawdpadd.py (and costumes.py). Never the other way round.           │
 * │                                                                      │
 * │ Why here: it's the body that runs on the most platforms — every      │
 * │ browser on Linux/macOS/Windows, over USB or Bluetooth, zero install  │
 * │ — and docs/MAKING-COSTUMES.md already tells authors to start here.   │
 * │ Until 2026-07-17 this file said "ported from clawdpadd.py" while     │
 * │ costumes.py said "mirrored from clawd-core.js": each named the other │
 * │ as truth, so there was nothing to diff against and drift was         │
 * │ unresolvable. Poses below still note where they were ported FROM —   │
 * │ that's provenance, not authority.                                    │
 * └──────────────────────────────────────────────────────────────────────┘
 *
 * Protocol is the opposite: blocksd is the reference and this is a replica.
 * The daemon emits frames to blocksd over a socket; a browser can't dial a
 * Unix socket, so the ROLI stack is reimplemented here against WebMIDI. That
 * duplication is forced and legitimate — it's held honest by golden vectors
 * (`node web/test-golden.mjs`), which assert byte-identity against blocksd.
 *
 * With WebMIDI (Chrome/Edge, secure context), a plain web page becomes a
 * complete Clawd host on Linux, macOS, and Windows. Zero install.
 */
"use strict";

const Protocol = {
  SYSEX_HEADER: [0xF0, 0x00, 0x21, 0x10, 0x77],
  MAX_PACKET_BYTES: 194,
  HEAP_SIZE: 7200,
  PROGRAM_SIZE: 100,
  MESSAGE_TYPE: 7, DEVICE_COMMAND: 9, PACKET_INDEX: 16,
  DATA_CHANGE_COMMAND: 3, BYTE_COUNT_FEW: 4, BYTE_COUNT_MANY: 8,
  BYTE_VALUE: 8, BYTE_SEQ_CONTINUES: 1,
  // device→host topology fields, in wire order
  PACKET_TIMESTAMP: 32, PROTOCOL_VERSION_BITS: 8, DEVICE_COUNT: 7,
  CONNECTION_COUNT: 8, SERIAL_CHAR: 7, SERIAL_LENGTH: 16,
  TOPOLOGY_INDEX: 7, BATTERY_LEVEL: 5, BATTERY_CHARGING: 1,
  MSG_DEVICE_TOPOLOGY: 0x01,
  MSG_DEVICE_COMMAND: 0x01, MSG_SHARED_DATA_CHANGE: 0x02,
  CMD_BEGIN_API: 0x00, CMD_REQUEST_TOPOLOGY: 0x01, CMD_END_API: 0x02,
  CMD_PING: 0x03,
  DC_END_OF_PACKET: 0, DC_END_OF_CHANGES: 1, DC_SKIP_FEW: 2, DC_SKIP_MANY: 3,
  DC_SET_SEQUENCE: 4, DC_SET_FEW: 5, DC_SET_FEW_LAST: 6, DC_SET_MANY: 7,
  FEW_MAX: 15, MANY_MAX: 255, COALESCE_THRESHOLD: 32, MIN_RUN_LENGTH: 3,
  SERIAL_DUMP_REQUEST: [0xF0, 0x00, 0x21, 0x10, 0x78, 0x3F, 0xF7],

  checksum(payload) {
    let cs = payload.length & 0xFF;
    for (const b of payload) cs = (cs + (cs * 2 + b)) & 0xFF;
    return cs & 0x7F;
  },
};

class BitWriter {
  constructor(capacity = 256) {
    this.data = new Uint8Array(capacity);
    this.capacity = capacity;
    this.bytesWritten = 0;
    this.bitsInCurrent = 0;
  }
  writeBits(value, numBits) {
    let v = value >>> 0, bits = numBits;
    while (bits > 0) {
      const avail = 7 - this.bitsInCurrent;
      const toWrite = Math.min(avail, bits);
      const mask = (1 << toWrite) - 1;
      this.data[this.bytesWritten] |= (v & mask) << this.bitsInCurrent;
      v = v >>> toWrite;
      bits -= toWrite;
      this.bitsInCurrent += toWrite;
      if (this.bitsInCurrent >= 7) { this.bitsInCurrent = 0; this.bytesWritten++; }
    }
  }
  hasCapacity(bitsNeeded) {
    return (this.bytesWritten + 2) * 7 + this.bitsInCurrent + bitsNeeded
        <= this.capacity * 7;
  }
  get size() { return this.bytesWritten + (this.bitsInCurrent > 0 ? 1 : 0); }
  getData() { return this.data.slice(0, this.size); }
}

class BitReader {
  constructor(data, from = 0, to = data.length) {
    this.data = data; this.pos = from; this.to = to; this.bitOffset = 0;
  }
  readBits(numBits) {
    let value = 0, bitsRead = 0, bits = numBits;
    while (bits > 0) {
      if (this.pos >= this.to) break;
      const avail = 7 - this.bitOffset;
      const toRead = Math.min(avail, bits);
      const mask = (1 << toRead) - 1;
      value |= (((this.data[this.pos] >> this.bitOffset) & mask) << bitsRead) >>> 0;
      bitsRead += toRead; bits -= toRead; this.bitOffset += toRead;
      if (this.bitOffset >= 7) { this.bitOffset = 0; this.pos++; }
    }
    return value >>> 0;
  }
}

/** Decode the device→host topology reply — the only way to learn a block's
 *  real device index. Every packet after the handshake is addressed by it,
 *  and it is NOT always 0: observed 9 on one Lightpad M and 32 on another
 *  (2026-07-16). Hardcoding it means talking to a device that isn't there —
 *  silently, because a wrong index simply goes unanswered.
 *
 *  Mirrors blocksd's _handle_topology / _read_topology_device. */
const TopologyDecoder = {
  /** @returns {{devices: Array<{index:number, serial:string, battery:number,
   *              charging:boolean}>}|null} null if not a topology packet */
  decode(bytes) {
    const h = Protocol.SYSEX_HEADER;
    if (bytes.length < h.length + 3) return null;
    for (let i = 0; i < h.length; i++) if (bytes[i] !== h[i]) return null;
    if (bytes[bytes.length - 1] !== 0xF7) return null;

    const payload = bytes.slice(h.length + 1, bytes.length - 2);
    if (Protocol.checksum(payload) !== bytes[bytes.length - 2]) return null;

    const r = new BitReader(payload);
    r.readBits(Protocol.PACKET_TIMESTAMP);

    const msgType = r.readBits(Protocol.MESSAGE_TYPE);
    if (msgType !== Protocol.MSG_DEVICE_TOPOLOGY) return null;

    r.readBits(Protocol.PROTOCOL_VERSION_BITS);
    const numDevices = r.readBits(Protocol.DEVICE_COUNT);
    r.readBits(Protocol.CONNECTION_COUNT);

    const devices = [];
    for (let d = 0; d < numDevices; d++) {
      let serial = "";
      for (let c = 0; c < Protocol.SERIAL_LENGTH; c++) {
        const ch = r.readBits(Protocol.SERIAL_CHAR);
        if (ch !== 0) serial += String.fromCharCode(ch);
      }
      devices.push({
        index: r.readBits(Protocol.TOPOLOGY_INDEX),
        serial,
        battery: r.readBits(Protocol.BATTERY_LEVEL),
        charging: !!r.readBits(Protocol.BATTERY_CHARGING),
      });
    }
    return { devices };
  },
};

class PacketBuilder {
  constructor(maxBytes = 64) { this.writer = new BitWriter(maxBytes); this.header = []; }
  sysexHeader(deviceIndex) {
    this.header = [...Protocol.SYSEX_HEADER, deviceIndex & 0x3F];
  }
  deviceCommand(cmd) {
    this.writer.writeBits(Protocol.MSG_DEVICE_COMMAND, Protocol.MESSAGE_TYPE);
    this.writer.writeBits(cmd, Protocol.DEVICE_COMMAND);
  }
  beginDataChanges(packetIndex) {
    this.writer.writeBits(Protocol.MSG_SHARED_DATA_CHANGE, Protocol.MESSAGE_TYPE);
    this.writer.writeBits(packetIndex, Protocol.PACKET_INDEX);
  }
  build() {
    const payload = this.writer.getData();
    return Uint8Array.from(
      [...this.header, ...payload, Protocol.checksum(payload), 0xF7]);
  }
  static command(idx, cmd) {
    const b = new PacketBuilder();
    b.sysexHeader(idx); b.deviceCommand(cmd);
    return b.build();
  }
  static ping(i) { return PacketBuilder.command(i, Protocol.CMD_PING); }
  static beginApi(i) { return PacketBuilder.command(i, Protocol.CMD_BEGIN_API); }
  static endApi(i) { return PacketBuilder.command(i, Protocol.CMD_END_API); }
  static requestTopology(i) { return PacketBuilder.command(i, Protocol.CMD_REQUEST_TOPOLOGY); }
}

class DataChangeEncoder {
  constructor(writer) { this.w = writer; this.lastValue = null; }
  cmd(c) { this.w.writeBits(c, Protocol.DATA_CHANGE_COMMAND); }
  skipBytes(count) {
    while (count > 0) {
      if (count > Protocol.FEW_MAX) {
        const chunk = Math.min(count, Protocol.MANY_MAX);
        this.cmd(Protocol.DC_SKIP_MANY);
        this.w.writeBits(chunk, Protocol.BYTE_COUNT_MANY);
        count -= chunk;
      } else {
        this.cmd(Protocol.DC_SKIP_FEW);
        this.w.writeBits(count, Protocol.BYTE_COUNT_FEW);
        count = 0;
      }
    }
  }
  setSequence(values, from, len) {
    if (len <= 0) return;
    this.cmd(Protocol.DC_SET_SEQUENCE);
    for (let i = 0; i < len; i++) {
      const v = values[from + i];
      this.w.writeBits(v, Protocol.BYTE_VALUE);
      this.w.writeBits(i < len - 1 ? 1 : 0, Protocol.BYTE_SEQ_CONTINUES);
      this.lastValue = v;
    }
  }
  setRepeated(value, count) {
    while (count > 0) {
      if (count > Protocol.FEW_MAX) {
        const chunk = Math.min(count, Protocol.MANY_MAX);
        this.cmd(Protocol.DC_SET_MANY);
        this.w.writeBits(chunk, Protocol.BYTE_COUNT_MANY);
        this.w.writeBits(value, Protocol.BYTE_VALUE);
        count -= chunk;
      } else if (this.lastValue !== null && value === this.lastValue) {
        this.cmd(Protocol.DC_SET_FEW_LAST);
        this.w.writeBits(count, Protocol.BYTE_COUNT_FEW);
        count = 0;
      } else {
        this.cmd(Protocol.DC_SET_FEW);
        this.w.writeBits(count, Protocol.BYTE_COUNT_FEW);
        this.w.writeBits(value, Protocol.BYTE_VALUE);
        count = 0;
      }
    }
    this.lastValue = value;
  }
  end(isLast) {
    this.cmd(isLast ? Protocol.DC_END_OF_CHANGES : Protocol.DC_END_OF_PACKET);
  }
}

const HeapDiff = {
  computeDiff(current, target) {
    const size = target.length, regions = [];
    let i = 0;
    while (i < size) {
      const start = i;
      if (current[i] === target[i]) {
        while (i < size && current[i] === target[i]) i++;
        regions.push({ isSkip: true, offset: start, count: i - start });
      } else {
        while (i < size && current[i] !== target[i]) i++;
        regions.push({ isSkip: false, offset: start, count: i - start });
      }
    }
    // coalesce SET,skip,SET when total < threshold (right to left)
    let k = regions.length - 1;
    while (k > 1) {
      const right = regions[k], skip = regions[k - 1], left = regions[k - 2];
      if (!right.isSkip && skip.isSkip && !left.isSkip) {
        const total = left.count + skip.count + right.count;
        if (total < Protocol.COALESCE_THRESHOLD) {
          left.count = total;
          regions.splice(k - 1, 2);
          k -= 2;
          continue;
        }
      }
      k--;
    }
    if (regions.length && regions[regions.length - 1].isSkip) regions.pop();
    return regions;
  },

  encodeLimited(enc, w, regions, target, resultState) {
    const END = Protocol.DATA_CHANGE_COMMAND;
    const SEQ_BYTE = Protocol.BYTE_VALUE + Protocol.BYTE_SEQ_CONTINUES;
    const FEW_BITS = Protocol.DATA_CHANGE_COMMAND + Protocol.BYTE_COUNT_FEW + Protocol.BYTE_VALUE;
    const FEW_LAST = Protocol.DATA_CHANGE_COMMAND + Protocol.BYTE_COUNT_FEW;
    const MANY_BITS = Protocol.DATA_CHANGE_COMMAND + Protocol.BYTE_COUNT_MANY + Protocol.BYTE_VALUE;

    const maxRepeated = (value, count) => {
      if (count > Protocol.FEW_MAX && w.hasCapacity(MANY_BITS + END))
        return Math.min(count, Protocol.MANY_MAX);
      if (value === enc.lastValue && w.hasCapacity(FEW_LAST + END))
        return Math.min(count, Protocol.FEW_MAX);
      if (w.hasCapacity(FEW_BITS + END)) return Math.min(count, Protocol.FEW_MAX);
      return 0;
    };
    const maxSequence = (count) => {
      let low = 0, high = count;
      while (low < high) {
        const mid = (low + high + 1) >> 1;
        if (w.hasCapacity(Protocol.DATA_CHANGE_COMMAND + mid * SEQ_BYTE + END)) low = mid;
        else high = mid - 1;
      }
      return low;
    };

    for (const region of regions) {
      if (region.isSkip) { enc.skipBytes(region.count); continue; }
      const { offset, count } = region;
      let i = 0;
      while (i < count) {
        let runLen = 1;
        while (i + runLen < count &&
               target[offset + i + runLen] === target[offset + i]) runLen++;
        const remaining = count - i;
        if (runLen >= Protocol.MIN_RUN_LENGTH || remaining <= Protocol.MIN_RUN_LENGTH) {
          const chunk = maxRepeated(target[offset + i], runLen);
          if (chunk === 0) return false;
          enc.setRepeated(target[offset + i], chunk);
          resultState.set(target.subarray(offset + i, offset + i + chunk), offset + i);
          i += chunk;
          continue;
        }
        let j = i + 1;
        while (j < count) {
          if (j + 2 < count && target[offset + j] === target[offset + j + 1] &&
              target[offset + j] === target[offset + j + 2]) break;
          j++;
        }
        const chunk = maxSequence(j - i);
        if (chunk === 0) return false;
        enc.setSequence(target, offset + i, chunk);
        resultState.set(target.subarray(offset + i, offset + i + chunk), offset + i);
        i += chunk;
      }
      if (i < count) return false;
    }
    return true;
  },
};

class HeapStreamer {
  constructor(deviceIndex, startIndex) {
    this.deviceIndex = deviceIndex;
    this.deviceState = new Uint8Array(Protocol.HEAP_SIZE);
    this.target = new Uint8Array(Protocol.HEAP_SIZE);
    this.packetIndex = startIndex & 0x3FF;
    this.virgin = true;
  }
  setBytes(offset, data) { this.target.set(data, offset); }
  seedIndex(i) { this.packetIndex = i & 0x3FF; }
  adoptState() { this.virgin = false; }
  markUnknownFrameArea(from) {
    for (let i = from; i < Protocol.HEAP_SIZE; i++)
      this.deviceState[i] = (~this.target[i]) & 0xFF;
  }
  drain() {
    if (this.virgin) {
      for (let i = 0; i < Protocol.HEAP_SIZE; i++)
        this.deviceState[i] = (~this.target[i]) & 0xFF;
      this.virgin = false;
    }
    const out = [];
    for (;;) {
      const regions = HeapDiff.computeDiff(this.deviceState, this.target);
      if (!regions.length) break;
      const builder = new PacketBuilder(Protocol.MAX_PACKET_BYTES);
      builder.sysexHeader(this.deviceIndex);
      builder.beginDataChanges(this.packetIndex);
      const enc = new DataChangeEncoder(builder.writer);
      const resultState = this.deviceState.slice();
      const complete = HeapDiff.encodeLimited(
        enc, builder.writer, regions, this.target, resultState);
      let changed = false;
      for (let i = 0; i < resultState.length; i++)
        if (resultState[i] !== this.deviceState[i]) { changed = true; break; }
      if (!changed) break;
      enc.end(complete);
      out.push(builder.build());
      this.deviceState = resultState;
      this.packetIndex = (this.packetIndex + 1) & 0x3FF;
    }
    return out;
  }
}

/* ── Clawd renderer + Clawdrobe (port of ClawdRenderer.kt/Costumes.kt) ── */

const Clawd = {
  CORAL: [217, 119, 87],
  CELEBRATE_SECONDS: 2.4,   // clawdpadd.py mirrors this
  costume: "none",
  size: "full",        // "full" | "mini" — chibi-Clawd roaming a big room
  msg: "",             // marquee text ("" = off)
  FONT: {
    "A":["010","101","111","101","101"],"B":["110","101","110","101","110"],
    "C":["011","100","100","100","011"],"D":["110","101","101","101","110"],
    "E":["111","100","110","100","111"],"F":["111","100","110","100","100"],
    "G":["011","100","101","101","011"],"H":["101","101","111","101","101"],
    "I":["111","010","010","010","111"],"J":["001","001","001","101","010"],
    "K":["101","110","100","110","101"],"L":["100","100","100","100","111"],
    "M":["101","111","111","101","101"],"N":["101","111","111","111","101"],
    "O":["010","101","101","101","010"],"P":["110","101","110","100","100"],
    "Q":["010","101","101","011","001"],"R":["110","101","110","110","101"],
    "S":["011","100","010","001","110"],"T":["111","010","010","010","010"],
    "U":["101","101","101","101","111"],"V":["101","101","101","101","010"],
    "W":["101","101","111","111","101"],"X":["101","101","010","101","101"],
    "Y":["101","101","010","010","010"],"Z":["111","001","010","100","111"],
    "0":["111","101","101","101","111"],"1":["010","110","010","010","111"],
    "2":["111","001","111","100","111"],"3":["111","001","011","001","111"],
    "4":["101","101","111","001","001"],"5":["111","100","111","001","111"],
    "6":["111","100","111","101","111"],"7":["111","001","001","010","010"],
    "8":["111","101","111","101","111"],"9":["111","101","111","001","111"],
    "!":["010","010","010","000","010"],"?":["111","001","011","000","010"],
    "-":["000","000","111","000","000"],".":["000","000","000","000","010"],
    " ":["000","000","000","000","000"],":":["000","010","000","010","000"],
    "<3":["000","101","111","111","010"],
  },
  COSTUMES: [
    { id: "none", emoji: "🐾", label: "just clawd" },
    { id: "tophat", emoji: "🎩", label: "dapper" },
    { id: "shades", emoji: "😎", label: "too cool" },
    { id: "party", emoji: "🥳", label: "party" },
    { id: "crown", emoji: "👑", label: "royalty" },
    { id: "phones", emoji: "🎧", label: "vibin'" },
    { id: "scarf", emoji: "🧣", label: "cozy" },
    { id: "bow", emoji: "🎀", label: "cutie" },
    { id: "halo", emoji: "😇", label: "angel" },
    { id: "horns", emoji: "😈", label: "lil devil" },
    { id: "wizard", emoji: "🧙", label: "wizard" },
    { id: "cowboy", emoji: "🤠", label: "howdy" },
    { id: "flower", emoji: "🌻", label: "bloom" },
    { id: "ghost", emoji: "👻", label: "spooky pal", skin: true },
    { id: "puff", emoji: "🌸", label: "pink puff", skin: true },
    { id: "chomper", emoji: "🟡", label: "chomper", skin: true },
    { id: "robot", emoji: "🤖", label: "beep boop", skin: true },
    { id: "cat", emoji: "🐱", label: "kitty", skin: true },
    { id: "frog", emoji: "🐸", label: "froggy", skin: true },
    { id: "alien", emoji: "👽", label: "alien", skin: true },
    { id: "pumpkin", emoji: "🎃", label: "spooky", skin: true },
    { id: "star", emoji: "⭐", label: "superstar", skin: true },
    { id: "bee", emoji: "🐝", label: "buzzy", skin: true },
  ],

  px(buf, x, y, r, g, b) {
    if (x >= 0 && x < 15 && y >= 0 && y < 15) {
      const i = (y * 15 + x) * 3;
      buf[i] = Math.min(255, Math.max(0, r | 0));
      buf[i + 1] = Math.min(255, Math.max(0, g | 0));
      buf[i + 2] = Math.min(255, Math.max(0, b | 0));
    }
  },

  body(brightness, dx, dy, eyesOpen, look, armL, armR, tint) {
    const buf = new Uint8Array(675);
    const [tr, tg, tb] = tint || this.CORAL;
    const r = tr * brightness, g = tg * brightness, b = tb * brightness;
    const rect = (x0, y0, x1, y1, oy = 0) => {
      for (let y = y0 + dy + oy; y < y1 + dy + oy; y++)
        for (let x = x0 + dx; x < x1 + dx; x++) this.px(buf, x, y, r, g, b);
    };
    rect(2, 3, 13, 11);
    rect(0, 7, 2, 9, armL); rect(13, 7, 15, 9, armR);
    for (const lx of [3, 5, 9, 11]) rect(lx, 11, lx + 1, 13);
    for (const ex of [4, 10]) {
      const x = ex + dx + look;
      this.px(buf, x, 6 + dy, 0, 0, 0);
      if (eyesOpen) this.px(buf, x, 5 + dy, 0, 0, 0);
    }
    return buf;
  },

  ghost(brightness, dx, dy, eyesOpen, look, t) {
    const buf = new Uint8Array(675);
    const r = 150 * brightness, g = 190 * brightness, b = 255 * brightness;
    for (let y = 2; y <= 12; y++) for (let x = 2; x <= 12; x++) {
      const cx = x - 7 - dx;
      const topDist = Math.hypot(cx, (y - 6 - dy) * 1.1);
      const inDome = y <= 6 + dy && topDist < 5.4;
      const inBody = y >= 6 + dy && y <= 11 + dy && Math.abs(cx) < 5.2;
      const skirt = y === 12 + dy && Math.abs(cx) < 5.2 &&
          ((x + Math.floor(t * 3)) % 2 === 0);
      if (inDome || inBody || skirt) this.px(buf, x, y, r, g, b);
    }
    for (const side of [-1, 1]) {
      const ex = 7 + side * 2 + dx, ey = 5 + dy;
      this.px(buf, ex, ey, 245, 245, 250);
      this.px(buf, ex, ey + 1, 245, 245, 250);
      if (eyesOpen) this.px(buf, ex + Math.max(-1, Math.min(1, look)), ey + 1, 30, 30, 60);
    }
    return buf;
  },

  puff(brightness, dx, dy, eyesOpen, look) {
    const buf = new Uint8Array(675);
    for (let y = 0; y < 15; y++) for (let x = 0; x < 15; x++)
      if (Math.hypot(x - 7 - dx, y - 7 - dy) < 5.2)
        this.px(buf, x, y, 255 * brightness, 150 * brightness, 185 * brightness);
    for (const side of [-1, 1]) {
      for (let f = 0; f < 2; f++)
        this.px(buf, 7 + side * 3 - f * side + dx, 12 + dy,
          200 * brightness, 40 * brightness, 70 * brightness);
      this.px(buf, 7 + side * 3 + dx, 8 + dy,
        255 * brightness, 110 * brightness, 150 * brightness);
      const ex = 7 + side * 2 + dx + Math.max(-1, Math.min(1, look));
      this.px(buf, ex, 6 + dy, 25, 20, 35);
      if (eyesOpen) {
        this.px(buf, ex, 5 + dy, 25, 20, 35);
        this.px(buf, ex, 4 + dy, 90, 85, 120);
      }
    }
    return buf;
  },

  chomper(brightness, dx, dy, t, facingRight) {
    const buf = new Uint8Array(675);
    const mouth = 0.18 + 0.42 * Math.abs(Math.sin(t * 5));
    for (let y = 0; y < 15; y++) for (let x = 0; x < 15; x++) {
      const cx = x - 7 - dx, cy = y - 7 - dy;
      if (Math.hypot(cx, cy) < 5.4) {
        const ang = Math.atan2(cy, facingRight ? cx : -cx);
        if (Math.abs(ang) > mouth)
          this.px(buf, x, y, 255 * brightness, 215 * brightness, 0);
      }
    }
    this.px(buf, 7 + dx + (facingRight ? 1 : -1), 4 + dy, 25, 22, 18);
    return buf;
  },

  prop(id, buf, dx, dy, look, t) {
    const P = (x, y, r, g, b) => this.px(buf, x, y, r, g, b);
    if (id === "tophat") {
      for (let x = 3; x <= 11; x++) P(x + dx, 2 + dy, 40, 36, 44);
      for (let y = 0; y <= 1; y++) for (let x = 5; x <= 9; x++)
        P(x + dx, y + dy, 52, 46, 58);
      for (let x = 5; x <= 9; x++) P(x + dx, 1 + dy, 180, 60, 70);
    } else if (id === "shades") {
      for (const yy of [5 + dy, 6 + dy]) {          // full eye coverage
        for (let x = 3; x <= 5; x++) P(x + dx + look, yy, 18, 16, 20);
        for (let x = 9; x <= 11; x++) P(x + dx + look, yy, 18, 16, 20);
      }
      for (let x = 6; x <= 8; x++) P(x + dx + look, 5 + dy, 30, 26, 32);
      P(4 + dx + look, 5 + dy, 90, 90, 110); P(10 + dx + look, 5 + dy, 90, 90, 110);
    } else if (id === "party") {
      P(7 + dx, 0 + dy, 255, 210, 60);
      for (let x = 6; x <= 8; x++) P(x + dx, 1 + dy, 235, 90, 160);
      for (let x = 5; x <= 9; x++) {
        const even = (x + dx) % 2 === 0;
        P(x + dx, 2 + dy, even ? 90 : 235, even ? 170 : 90, even ? 235 : 160);
      }
    } else if (id === "crown") {
      for (const x of [4, 7, 10]) P(x + dx, 1 + dy, 255, 205, 40);
      for (let x = 4; x <= 10; x++) P(x + dx, 2 + dy, 255, 205, 40);
      P(7 + dx, 2 + dy, 220, 60, 90);
    } else if (id === "phones") {
      for (let x = 4; x <= 10; x++) P(x + dx, 1 + dy, 46, 42, 50);
      for (const side of [-1, 1]) {
        const cx = 7 + side * 6;
        for (let y = 5; y <= 7; y++) {
          P(cx + dx, y + dy, 46, 42, 50);
          P(cx - side + dx, y + dy, 217, 119, 87);
        }
        P(cx + dx, 4 + dy, 46, 42, 50);
        P(cx + dx, 3 + dy, 46, 42, 50);
      }
    } else if (id === "scarf") {
      for (let x = 3; x <= 11; x++) P(x + dx, 10 + dy, 200, 60, 60);
      for (let x = 4; x <= 10; x++) P(x + dx, 11 + dy, 170, 45, 45);
      P(10 + dx, 12 + dy, 200, 60, 60);
      if (Math.sin(t * 2.3) > 0.3) P(11 + dx, 12 + dy, 200, 60, 60);
    } else if (id === "bow") {           // bowtie under the chin
      P(6 + dx, 10 + dy, 235, 90, 140); P(8 + dx, 10 + dy, 235, 90, 140);
      P(7 + dx, 10 + dy, 255, 150, 190);
      P(6 + dx, 9 + dy, 235, 90, 140); P(8 + dx, 9 + dy, 235, 90, 140);
    } else if (id === "halo") {          // floating gold ring
      for (let x = 5; x <= 9; x++) P(x + dx, 0 + dy, 255, 225, 90);
      P(5 + dx, 1 + dy, 255, 225, 90); P(9 + dx, 1 + dy, 255, 225, 90);
    } else if (id === "horns") {         // little devil horns
      P(3 + dx, 2 + dy, 200, 40, 40); P(3 + dx, 1 + dy, 220, 60, 60);
      P(11 + dx, 2 + dy, 200, 40, 40); P(11 + dx, 1 + dy, 220, 60, 60);
    } else if (id === "wizard") {        // tall starry hat
      P(7 + dx, 0 + dy, 120, 80, 200);
      for (let x = 6; x <= 8; x++) P(x + dx, 1 + dy, 120, 80, 200);
      for (let x = 4; x <= 10; x++) P(x + dx, 2 + dy, 100, 66, 175);
      P(7 + dx, 1 + dy, 255, 235, 120);   // star
    } else if (id === "cowboy") {        // wide-brim hat
      for (let x = 2; x <= 12; x++) P(x + dx, 2 + dy, 150, 100, 55);
      for (let x = 5; x <= 9; x++) P(x + dx, 1 + dy, 120, 80, 45);
      for (let x = 5; x <= 9; x++) P(x + dx, 0 + dy, 120, 80, 45);
    } else if (id === "flower") {        // a happy bloom on his head
      P(7 + dx, 0 + dy, 255, 210, 70);   // center
      P(6 + dx, 0 + dy, 235, 100, 170); P(8 + dx, 0 + dy, 235, 100, 170);
      P(7 + dx, 1 + dy, 90, 190, 90);    // petal below / stem hint
    }
  },


  robot(brightness, dx, dy, eyesOpen) {
    const buf = new Uint8Array(675);
    const s = 200 * brightness, d = 120 * brightness;
    for (let y = 3; y <= 11; y++) for (let x = 3; x <= 11; x++)
      this.px(buf, x + dx, y + dy, s, s, 210 * brightness);
    for (let x = 2; x <= 12; x++) { this.px(buf, x + dx, 3 + dy, d, d, d);
      this.px(buf, x + dx, 11 + dy, d, d, d); }
    this.px(buf, 7 + dx, 1 + dy, d, d, d);      // antenna
    this.px(buf, 7 + dx, 0 + dy, 255, 80, 80);
    for (const ex of [5, 9]) {                   // square eyes
      const on = eyesOpen ? [90, 220, 255] : [40, 60, 70];
      this.px(buf, ex + dx, 6 + dy, on[0]*brightness, on[1]*brightness, on[2]*brightness);
    }
    for (let x = 5; x <= 9; x++) this.px(buf, x + dx, 8 + dy, d, d, d); // mouth grille
    for (const lx of [4, 10]) { this.px(buf, lx + dx, 12 + dy, d, d, d);
      this.px(buf, lx + dx, 13 + dy, d, d, d); }
    return buf;
  },

  cat(brightness, dx, dy, eyesOpen, look, t) {
    const buf = this.body(brightness, dx, dy, eyesOpen, look, 0, 0,
      [230, 150, 90]);
    for (const ex of [2, 12]) {                  // triangle ears
      this.px(buf, ex + dx, 2 + dy, 230*brightness, 150*brightness, 90*brightness);
      this.px(buf, ex + dx, 1 + dy, 200*brightness, 120*brightness, 70*brightness);
    }
    for (const s of [-1, 1]) {                    // whiskers
      this.px(buf, 7 + s*4 + dx, 7 + dy, 240, 240, 230);
      this.px(buf, 7 + s*5 + dx, 7 + dy, 240, 240, 230);
    }
    this.px(buf, 7 + dx, 7 + dy, 255, 150, 170);  // lil nose
    return buf;
  },

  frog(brightness, dx, dy, eyesOpen) {
    const buf = new Uint8Array(675);
    const g = 120 * brightness, gd = 80 * brightness;
    for (let y = 4; y <= 11; y++) for (let x = 2; x <= 12; x++)
      if (Math.hypot(x - 7 - dx, y - 7.5 - dy) < 5.4)
        this.px(buf, x + dx, y + dy, gd, 190*brightness, gd);
    for (const ex of [4, 10]) {                   // bulging eyes on top
      this.px(buf, ex + dx, 3 + dy, 210*brightness, 240*brightness, 210*brightness);
      this.px(buf, ex + dx, 2 + dy, 210*brightness, 240*brightness, 210*brightness);
      if (eyesOpen) this.px(buf, ex + dx, 3 + dy, 20, 30, 20);
    }
    for (let x = 5; x <= 9; x++) this.px(buf, x + dx, 9 + dy, 40, 90, 40); // smile
    return buf;
  },

  alien(brightness, dx, dy, eyesOpen) {
    const buf = new Uint8Array(675);
    for (let y = 2; y <= 12; y++) for (let x = 3; x <= 11; x++) {
      const w = 1 - Math.abs(y - 5) * 0.06;      // big head, narrow chin
      if (Math.abs(x - 7 - dx) < 4.2 * w)
        this.px(buf, x + dx, y + dy, 120*brightness, 210*brightness, 120*brightness);
    }
    for (const ex of [-2, 2]) {                   // big almond eyes
      for (let d2 = 0; d2 <= 1; d2++) {
        this.px(buf, 7 + ex + dx, 5 + dy, 10, 15, 10);
        this.px(buf, 7 + ex + dx - Math.sign(ex), 5 + dy, 10, 15, 10);
        this.px(buf, 7 + ex + dx, 6 + dy, 10, 15, 10);
      }
    }
    return buf;
  },

  pumpkin(brightness, dx, dy, eyesOpen, t) {
    const buf = new Uint8Array(675);
    for (let y = 2; y <= 12; y++) for (let x = 1; x <= 13; x++)
      if (Math.hypot((x - 7 - dx) * 0.85, y - 7 - dy) < 5.6)
        this.px(buf, x + dx, y + dy, 255*brightness, 140*brightness, 20*brightness);
    this.px(buf, 7 + dx, 1 + dy, 90*brightness, 150*brightness, 60*brightness); // stem
    const glow = eyesOpen ? 30 : 10;             // carved face glows dark
    for (const ex of [4, 10]) {                   // triangle eyes
      this.px(buf, ex + dx, 5 + dy, glow, glow, glow);
      this.px(buf, ex + dx, 6 + dy, glow, glow, glow);
    }
    this.px(buf, 7 + dx, 6 + dy, glow, glow, glow);       // nose
    for (let x = 4; x <= 10; x++) this.px(buf, x + dx, 9 + dy, glow, glow, glow);
    for (const x of [5, 7, 9]) this.px(buf, x + dx, 8 + dy, glow, glow, glow); // teeth
    return buf;
  },

  star(brightness, dx, dy, eyesOpen) {
    const buf = new Uint8Array(675);
    const y0 = 205 * brightness;
    // 5-point star, hand-tuned on 15x15
    const rows = [
      "0000001000000","0000011100000","0000011100000","1111111111111",
      "0111111111110","0011111111100","0001111111000","0011111111100",
      "0011110111100","0111100011110","0110000000110","0000000000000"];
    for (let r = 0; r < rows.length; r++)
      for (let c = 0; c < 13; c++)
        if (rows[r][c] === "1")
          this.px(buf, c + 1 + dx, r + 1 + dy, 255*brightness, y0, 60*brightness);
    for (const ex of [5, 9])                      // eyes
      if (eyesOpen) this.px(buf, ex + dx, 6 + dy, 40, 30, 10);
    return buf;
  },

  bee(brightness, dx, dy, eyesOpen, t) {
    const buf = new Uint8Array(675);
    for (let y = 5; y <= 11; y++) for (let x = 4; x <= 10; x++)
      if (Math.hypot(x - 7 - dx, y - 8 - dy) < 3.6) {
        const stripe = ((y + dy) % 2 === 0);
        this.px(buf, x + dx, y + dy,
          stripe ? 30 : 255*brightness, stripe ? 25 : 210*brightness, stripe ? 20 : 30);
      }
    for (const wx of [3, 11]) {                    // flappy wings
      const up = Math.sin(t * 12) > 0 ? 0 : 1;
      this.px(buf, wx + dx, 5 + up + dy, 220, 230, 255);
      this.px(buf, wx + (wx < 7 ? 1 : -1) + dx, 5 + up + dy, 220, 230, 255);
    }
    for (const ex of [6, 8])                        // eyes
      if (eyesOpen) this.px(buf, ex + dx, 6 + dy, 15, 12, 8);
    return buf;
  },

  dressed(brightness, dx, dy, eyesOpen, look, t, armL = 0, armR = 0, tint) {
    const c = this.costume;
    let buf;
    if (c === "ghost") buf = this.ghost(brightness, dx, dy, eyesOpen, look, t);
    else if (c === "puff") buf = this.puff(brightness, dx, dy, eyesOpen, look);
    else if (c === "chomper")
      buf = this.chomper(brightness, dx, dy, t, Math.sin(t * 0.13) >= 0);
    else if (c === "robot") buf = this.robot(brightness, dx, dy, eyesOpen);
    else if (c === "cat") buf = this.cat(brightness, dx, dy, eyesOpen, look, t);
    else if (c === "frog") buf = this.frog(brightness, dx, dy, eyesOpen);
    else if (c === "alien") buf = this.alien(brightness, dx, dy, eyesOpen);
    else if (c === "pumpkin") buf = this.pumpkin(brightness, dx, dy, eyesOpen, t);
    else if (c === "star") buf = this.star(brightness, dx, dy, eyesOpen);
    else if (c === "bee") buf = this.bee(brightness, dx, dy, eyesOpen, t);
    else buf = this.body(brightness, dx, dy, eyesOpen, look, armL, armR, tint);
    const meta = this.COSTUMES.find(k => k.id === c);
    if (c !== "none" && meta && !meta.skin) this.prop(c, buf, dx, dy, look, t);
    return buf;
  },

  marquee(text, t, color) {
    const buf = new Uint8Array(675);
    const glyphs = text.toUpperCase().split("").map(c => this.FONT[c] || this.FONT["?"]);
    const width = glyphs.length * 4;               // 3px + 1 space
    const x0 = 15 - Math.floor((t * 11) % (width + 15));  // enter right, exit left
    let gx = x0;
    for (const rows of glyphs) {
      for (let r = 0; r < 5; r++)
        for (let c = 0; c < 3; c++)
          if (rows[r][c] === "1")
            this.px(buf, gx + c, 5 + r, color[0], color[1], color[2]);
      gx += 4;
    }
    return buf;
  },

  awake(t) {
    const breath = 0.72 + 0.28 * Math.sin(t * 2 * Math.PI / 6.5);
    const dx = Math.round(1.5 * Math.sin(t * 0.13));
    const dy = Math.round(0.5 * Math.sin(t * 2 * Math.PI / 6.5));
    const look = Math.round(0.9 * Math.sin(t * 0.31));
    const blink = (t % 4.3) < 0.13;
    return this.dressed(breath, dx, dy, !blink, look, t);
  },

  /** The glass IS a Micro QR: M3 is exactly 15x15 modules and the dark bezel
   *  doubles as the quiet zone. Lit = dark modules (inverted; scanners cope).
   *  Matrices come baked from tools/make_web_qr.py — see qr-data.js for why.
   *  Mirrored in clawdpadd.py's mood == "qr" branch. */
  qr(payload) {
    const rows = (typeof QR_BAKED !== "undefined") ? QR_BAKED[payload] : null;
    if (!rows) return null;             // caller says something useful
    const buf = new Uint8Array(675);
    for (let y = 0; y < 15; y++)
      for (let x = 0; x < 15; x++)
        if (rows[y][x] === "#") this.px(buf, x, y, 235, 235, 235);
    return buf;
  },

  /** Chibi-Clawd, body's top-left at (px, py). Same soul, quarter the pixels:
   *  5x4 body, 1px arm nubs (raised when armsUp), two legs, 1px eye holes.
   *  Mirrored in clawdpadd.py _mini (originally ported from there). */
  mini(brightness, px, py, eyesOpen, look = 0, armsUp = false) {
    const buf = new Uint8Array(675);
    // Do NOT round here: px() truncates (`r | 0`), matching body() and
    // clawdpadd.py's `int(c * brightness)`. Rounding made chibi exactly one
    // unit brighter than the desk — invisible to the eye, caught by parity.
    const c = this.CORAL.map(v => Math.min(255, v * brightness));
    for (let y = 0; y < 4; y++)
      for (let x = 0; x < 5; x++) this.px(buf, px + x, py + y, c[0], c[1], c[2]);
    const ay = py + (armsUp ? 0 : 2);
    this.px(buf, px - 1, ay, c[0], c[1], c[2]);   // arm nubs poke out each side
    this.px(buf, px + 5, ay, c[0], c[1], c[2]);
    this.px(buf, px + 1, py + 4, c[0], c[1], c[2]);   // legs
    this.px(buf, px + 3, py + 4, c[0], c[1], c[2]);
    if (eyesOpen) {
      this.px(buf, px + 1 + look, py + 1, 0, 0, 0);
      this.px(buf, px + 3 + look, py + 1, 0, 0, 0);
    }
    return buf;
  },

  /** Mini-mode composition: a small Clawd roaming a big room.
   *  Mirrored in clawdpadd.py _mini_frame (awake branch). */
  miniAwake(t) {
    const blink = (t % 4.3) < 0.13;
    const px = Math.max(1, Math.min(9, Math.round(5 + 4.2 * Math.sin(t * 0.09))));
    const py = Math.max(0, Math.min(9, Math.round(4 + 3.2 * Math.sin(t * 0.067 + 1.3))));
    const brightness = 0.72 + 0.28 * Math.sin(t * 2 * Math.PI / 6.5);
    const look = Math.round(0.9 * Math.sin(t * 0.31));
    return this.mini(brightness, px, py, !blink, look);
  },

  miniWave(t) {
    const pulse = 0.78 + 0.22 * Math.sin(t * 2 * Math.PI * 1.4);
    const blink = (t % 4.3) < 0.13;
    return this.mini(pulse, 5, 5, !blink, 0, (t * 2.4) % 1.0 < 0.5);
  },

  miniCelebrate(rel) {
    const bounce = Math.abs(Math.sin(rel * Math.PI / 0.6));
    return this.mini(1.0, 5, 6 - Math.round(3 * bounce), true, 0, true);
  },

  /** Chibi dancing. The daemon has no dance mood (it's a web/Android ear
   *  thing), so this has no counterpart to port — it's dance()'s bounce and
   *  sway on the mini body, so chibi + dance stays chibi. */
  miniDance(t, energy, bounce) {
    const sway = Math.round(1.8 * Math.sin(t * 2.2));
    const brightness = 0.55 + 0.45 * Math.min(1, energy + bounce * 0.5);
    const blink = (t % 3.1) < 0.1;
    return this.mini(brightness, 5 + sway, 6 - Math.round(bounce * 2.5),
                     !blink, 0, bounce > 0.25);
  },

  /** Clawd asleep: dim, slow breathing, eyes closed, occasional peek.
   *  Mirrored in clawdpadd.py frame_sleep. (The tab used to inline a flat
   *  `dressed(0.22, …, false, …)` — he neither breathed nor peeked in the
   *  browser, only on the desk. Found by cross-body parity, 2026-07-17.) */
  sleep(t) {
    const breath = 0.26 + 0.08 * Math.sin(t * 2 * Math.PI / 9.0);
    const peek = (t % 9.7) < 0.4;
    return this.dressed(breath, 0, 0, peek, 0, t);
  },

  miniSleep(t) {
    const breath = 0.26 + 0.08 * Math.sin(t * 2 * Math.PI / 9.0);
    const peek = (t % 9.7) < 0.4;
    return this.mini(breath, 8, 8, peek, 0);
  },

  /** Clawd hard at work: pacing back and forth, eyes leading the way.
   *
   *  `phase` is an ACCUMULATOR in radians, not a timestamp. The host advances
   *  it at 2.5 + 4.5*energy rad/s, so he paces visibly faster the harder the
   *  work is — and winds down with it. Never multiply t by a time-varying
   *  speed: the pacing jumps when the speed changes.
   *
   *  Mirrored in clawdpadd.py frame_thinking. */
  thinking(phase, t, notice = null) {
    const dx = Math.round(2.2 * Math.sin(phase * 0.5));
    const vel = Math.cos(phase * 0.5);
    const look = notice !== null ? notice
      : (vel > 0.25 ? 1 : (vel < -0.25 ? -1 : 0));
    const blink = (t % 2.1) < 0.09;   // quick busy blinks
    return this.dressed(0.9, dx, 0, !blink, look, t);
  },

  /** Chibi at work: pacing a shorter beat on the same energy clock.
   *  Mirrored in clawdpadd.py _mini_frame (thinking branch). */
  miniThinking(phase, t) {
    const px = 5 + Math.round(3.5 * Math.sin(phase * 0.5));
    const c = Math.cos(phase * 0.5);
    const look = c > 0.25 ? 1 : (c < -0.25 ? -1 : 0);
    return this.mini(0.9, px, 6, (t % 2.1) >= 0.09, look);
  },

  /** Clawd needs you: right arm raised, waving, gentle pulse.
   *  Mirrored in clawdpadd.py frame_notify — same body language, both bodies. */
  wave(t) {
    const pulse = 0.78 + 0.22 * Math.sin(t * 2 * Math.PI * 1.4);
    const waveUp = (t * 2.4) % 1.0 < 0.5;
    const blink = (t % 4.3) < 0.13;
    return this.dressed(pulse, 0, 0, !blink, 0, t, 0, waveUp ? -2 : -1);
  },

  /** The one emotion he was missing: slumped, arms drooped, heavy blinks.
   *
   *  Deliberately quiet — no flashing, no colour change. This replaced the old
   *  red error flash, and the whole point is that it's a *feeling*, not an
   *  alarm: he sags, he looks away, his eyes close a beat too long. You read
   *  it the way you read a person across a room.
   *
   *  Use sparingly (repeated failures, a starving soul). Scarcity is what
   *  makes it land — a Clawd who mopes often is just a mopey Clawd.
   *
   *  Mirrored in clawdpadd.py frame_sad. */
  sad(t) {
    // shallow and slow — a smaller breath than awake, dimmer, but never dark
    const breath = 0.46 + 0.08 * Math.sin(t * 2 * Math.PI / 8.0);
    // heavy: closures ~4x longer than awake's 0.13s flick
    const blink = (t % 5.0) < 0.55;
    // he looks down and away, and holds it
    const look = Math.sin(t * 0.19) > 0.55 ? -1 : 0;
    return this.dressed(breath, 0, 1, !blink, look, t, 2, 2);
  },

  /** Chibi moping: same slump, quarter the pixels.
   *  Mirrored in clawdpadd.py _mini_frame (sad branch). */
  miniSad(t) {
    const breath = 0.46 + 0.08 * Math.sin(t * 2 * Math.PI / 8.0);
    const blink = (t % 5.0) < 0.55;
    const look = Math.sin(t * 0.19) > 0.55 ? -1 : 0;
    return this.mini(breath, 8, 9, !blink, look);
  },

  /** Task landed: both arms up, jumping. `rel` is seconds since the burst
   *  began; two full hops per CELEBRATE_SECONDS.
   *  Mirrored in clawdpadd.py frame_celebrate. */
  celebrate(rel) {
    const bounce = Math.abs(Math.sin(rel * Math.PI / 0.6));
    return this.dressed(1.0, 0, -Math.round(2 * bounce), true, 0, rel, -2, -2);
  },

  dance(t, energy, bounce) {
    const dy = -Math.round(bounce * 2.5);
    const armUp = bounce > 0.55 ? -2 : bounce > 0.25 ? -1 : 0;
    const sway = Math.round(1.8 * Math.sin(t * 2.2));
    const brightness = 0.55 + 0.45 * Math.min(1, energy + bounce * 0.5);
    const blink = (t % 3.1) < 0.1;
    const prev = this.costume;
    if (prev === "none") this.costume = "phones";
    const f = this.dressed(brightness, sway, dy, !blink, 0, t, armUp, armUp);
    this.costume = prev;
    return f;
  },

  rgb565(frame) {
    const out = new Uint8Array(450);
    for (let p = 0; p < 225; p++) {
      const r5 = (frame[p * 3] >> 3) & 0x1F;
      const g6 = (frame[p * 3 + 1] >> 2) & 0x3F;
      const b5 = (frame[p * 3 + 2] >> 3) & 0x1F;
      out[p * 2] = r5 | ((g6 & 0x07) << 5);
      out[p * 2 + 1] = (g6 >> 3) | (b5 << 3);
    }
    return out;
  },
};

if (typeof module !== "undefined") {
  module.exports = { Protocol, BitWriter, BitReader, PacketBuilder,
    TopologyDecoder, DataChangeEncoder, HeapDiff, HeapStreamer, Clawd };
}
