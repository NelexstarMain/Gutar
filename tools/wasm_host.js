// wasm_host.js - ładuje dist/gt_engine.wasm w node i udostępnia wygodne opakowanie API (do testów).
'use strict';
const fs = require('fs');
const path = require('path');

async function load(file) {
  const bytes = fs.readFileSync(file || path.join(__dirname, '..', 'dist', 'gt_engine.wasm'));
  let mem = null;
  const wasi = {
    fd_close: () => 0, fd_seek: () => 70, fd_write: (fd, iov, n, out) => {
      const dv = new DataView(mem.buffer); let w = 0;
      for (let i = 0; i < n; i++) w += dv.getUint32(iov + i * 8 + 4, true);
      dv.setUint32(out, w, true); return 0;
    },
  };
  let x;
  if (process.env.GT_ASMJS) { // wariant rezerwowy: czysty JS z wasm2js
    x = eval(fs.readFileSync(process.env.GT_ASMJS, 'utf8'))(wasi);
  } else {
    x = (await WebAssembly.instantiate(bytes, { wasi_snapshot_preview1: wasi })).instance.exports;
  }
  mem = x.memory;
  if (x._initialize) x._initialize();
  const dec = new TextDecoder();
  const text = n => dec.decode(new Uint8Array(mem.buffer, x.gt_text(), n));
  const api = {
    x,
    config(o) { x.gt_config(o.a4 || 440, o.win || 4096, o.gate === undefined ? -62 : o.gate, o.mains === undefined ? 50 : o.mains,
      o.autoTune === false ? 0 : 1, o.autoGate === false ? 0 : 1, o.tuning || 0, o.octaves === false ? 0 : 1, o.hand === false ? 0 : 1); },
    frame(i) { return JSON.parse(text(x.gt_frame_json(i === undefined ? -1 : i))); },
    roll(t0, t1) { return JSON.parse(text(x.gt_roll_json(t0, t1))); },
    summary() { return JSON.parse(text(x.gt_summary_json())); },
    tunings() { return JSON.parse(text(x.gt_tuning_json())); },
    bin(kind) { const n = x.gt_export(kind); return Buffer.from(new Uint8Array(mem.buffer, x.gt_bin(), n)); },
    text,
    // analiza całego bufora (Float32Array) tak jak w aplikacji: przed-przebieg + pętla kroków
    analyzeFile(samples, fs, prepass = true) {
      const p = x.gt_file_alloc(samples.length);
      new Float32Array(mem.buffer, p, samples.length).set(samples);
      x.gt_file_begin(fs, prepass ? 1 : 0);
      let pr = 0; while (pr < 1000) pr = x.gt_file_step(1 << 18);
      x.gt_file_free();
    },
    live(samples, fs, chunk = 1024) {
      x.gt_init(fs);
      for (let i = 0; i < samples.length; i += chunk) {
        const n = Math.min(chunk, samples.length - i);
        const p = x.gt_input(n); new Float32Array(mem.buffer, p, n).set(samples.subarray(i, i + n)); x.gt_push(n);
      }
      x.gt_finish();
    },
  };
  return api;
}

function readWav(file) {
  const b = fs.readFileSync(file); let p = 12, ch = 1, rate = 44100;
  while (p + 8 <= b.length) {
    const id = b.toString('ascii', p, p + 4), len = b.readUInt32LE(p + 4);
    if (id === 'fmt ') { ch = b.readUInt16LE(p + 10); rate = b.readUInt32LE(p + 12); }
    if (id === 'data') {
      const n = Math.floor(Math.min(len, b.length - p - 8) / 2 / ch), x = new Float32Array(n);
      for (let i = 0; i < n; i++) x[i] = b.readInt16LE(p + 8 + i * 2 * ch) / 32768;
      return { x, rate };
    }
    p += 8 + len + (len & 1);
  }
  throw new Error('no data');
}

module.exports = { load, readWav };
