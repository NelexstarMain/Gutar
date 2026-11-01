// run_old.js - uruchamia ORYGINALNY silnik JS (z pliku original-gitara-sluchacz.html) na pliku WAV
// i zapisuje wynik w tym samym formacie JSON, co `gt_cli analyze`.
// Użycie: node run_old.js in.wav out.json
'use strict';
const fs = require('fs'), vm = require('vm'), path = require('path');
const html = fs.readFileSync(path.join(__dirname, 'original-gitara-sluchacz.html'), 'utf8');
const m = html.match(/<script>([\s\S]*?)<\/script>/);          // pierwszy blok = biblioteka GT
vm.runInThisContext(m[1]);
const GT = globalThis.GT;

function readWav(file) {
  const b = fs.readFileSync(file);
  let p = 12, ch = 1, rate = 44100;
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

const { x, rate } = readWav(process.argv[2]);
const frames = [], chordLog = [];
let pend = null, lastChord = null;
const eng = new GT.Engine({
  fs: rate, win: 4096, a4: 440, mains: 50, gateDb: -62,
  onFrame: (f, e) => {
    // ta sama logika wpisów do historii akordów co w interfejsie oryginału
    const name = f.chord ? f.chord.name : null;
    if (name) pend = name;
    const settled = f.silent || f.t > (e.latchUntil || 0);
    if (pend && settled && pend !== lastChord) {
      const t0 = e.tracker.lastOnset !== null && e.tracker.lastOnset !== undefined ? e.tracker.lastOnset : f.t;
      chordLog.push({ t: t0, name: pend }); lastChord = pend;
    }
    if (f.silent) { lastChord = null; pend = null; }
    frames.push({
      t: +f.t.toFixed(3), silent: f.silent, chord: f.chord ? f.chord.name : null,
      notes: (f.stable.length ? f.stable : f.notes).map(n => n.midi),
      tuner: f.tuner && f.notes.length === 1 ? { midi: f.tuner.midi, f: f.tuner.f, cents: f.tuner.cents } : null,
    });
  },
});
const t0 = process.hrtime.bigint();
for (let i = 0; i < x.length; i += 2048) eng.push(x.subarray(i, Math.min(x.length, i + 2048)));
eng.finish();
const ms = Number(process.hrtime.bigint() - t0) / 1e6;
fs.writeFileSync(process.argv[3], JSON.stringify({
  engine: 'original-js', cpuMs: ms, audioSec: x.length / rate, frames, chordLog,
  notes: eng.tracker.events.map(e => ({ midi: e.midi, t0: +e.t0.toFixed(3), t1: +e.t1.toFixed(3) })),
  onsets: eng.onsets.map(t => +t.toFixed(3)),
}));
