/* clawd-core.js — the ROLI BLOCKS protocol + Clawd renderer, in the browser.
 *
 * Third sibling of the proven Python stack and the golden-tested Kotlin
 * port. Held to the same golden vectors (web/test-golden.mjs, node).
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
  costume: "none",
  COSTUMES: [
    { id: "none", emoji: "🐾", label: "just clawd" },
    { id: "tophat", emoji: "🎩", label: "dapper" },
    { id: "shades", emoji: "😎", label: "too cool" },
    { id: "party", emoji: "🥳", label: "party" },
    { id: "crown", emoji: "👑", label: "royalty" },
    { id: "phones", emoji: "🎧", label: "vibin'" },
    { id: "scarf", emoji: "🧣", label: "cozy" },
    { id: "ghost", emoji: "👻", label: "spooky pal", skin: true },
    { id: "puff", emoji: "🌸", label: "pink puff", skin: true },
    { id: "chomper", emoji: "🟡", label: "chomper", skin: true },
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
      const yy = 5 + dy;
      for (let x = 3; x <= 5; x++) P(x + dx + look, yy, 18, 16, 20);
      for (let x = 9; x <= 11; x++) P(x + dx + look, yy, 18, 16, 20);
      for (let x = 6; x <= 8; x++) P(x + dx + look, yy, 30, 26, 32);
      P(4 + dx + look, yy, 90, 90, 110); P(10 + dx + look, yy, 90, 90, 110);
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
    }
  },

  dressed(brightness, dx, dy, eyesOpen, look, t, armL = 0, armR = 0, tint) {
    const c = this.costume;
    let buf;
    if (c === "ghost") buf = this.ghost(brightness, dx, dy, eyesOpen, look, t);
    else if (c === "puff") buf = this.puff(brightness, dx, dy, eyesOpen, look);
    else if (c === "chomper")
      buf = this.chomper(brightness, dx, dy, t, Math.sin(t * 0.13) >= 0);
    else buf = this.body(brightness, dx, dy, eyesOpen, look, armL, armR, tint);
    const meta = this.COSTUMES.find(k => k.id === c);
    if (c !== "none" && meta && !meta.skin) this.prop(c, buf, dx, dy, look, t);
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
    DataChangeEncoder, HeapDiff, HeapStreamer, Clawd };
}
