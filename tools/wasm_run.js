// wasm_run.js - analiza WAV silnikiem z pliku .wasm; wynik w formacie jak `gt_cli analyze`.
// Użycie: node wasm_run.js in.wav out.json [--live]
'use strict';
const fs = require('fs');
const { load, readWav } = require('./wasm_host');
(async () => {
  const api = await load();
  const { x, rate } = readWav(process.argv[2]);
  api.config({});
  const t0 = process.hrtime.bigint();
  if (process.argv.includes('--live')) api.live(x, rate); else api.analyzeFile(x, rate);
  const ms = Number(process.hrtime.bigint() - t0) / 1e6;
  const sum = api.summary(), n = sum.frames, frames = [];
  for (let i = 0; i < n; i++) {
    const f = api.frame(i);
    frames.push({ t: f.t, silent: !!f.sil, chord: f.ch, notes: f.n.filter(a => a[4]).map(a => a[0]),
      tuner: f.tu ? { midi: f.tu[0], f: f.tu[1], cents: f.tu[3] } : null });
  }
  const r = api.roll(-1, 1e9);
  fs.writeFileSync(process.argv[3], JSON.stringify({
    engine: 'wasm', cpuMs: ms, audioSec: x.length / rate, winSec: sum.win, frames,
    chordLog: sum.chords.map(c => ({ t: c[0], name: c[1] })),
    notes: r.ev.map(e => ({ midi: e[0], t0: e[1], t1: e[2] })), onsets: r.on,
  }));
})();
