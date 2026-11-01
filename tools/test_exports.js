// test_exports.js - uruchamia analizę i zapisuje wszystkie eksporty do katalogu (do walidacji w pythonie)
'use strict';
const fs = require('fs'), path = require('path');
const { load, readWav } = require('./wasm_host');
(async () => {
  const [wav, outDir] = process.argv.slice(2);
  const api = await load(), { x, rate } = readWav(wav), X = api.x;
  api.config({});
  api.analyzeFile(x, rate);
  // transkrypcja -> synteza porcjami
  const total = X.gt_synth_begin(22050), n = X.gt_synth_count();
  const t0 = Date.now();
  for (let i = 0; i < n; i += 40) X.gt_synth_step(i, Math.min(n, i + 40));
  X.gt_synth_end();
  const synthMs = Date.now() - t0;
  const names = ['gitara.mid', 'rec.wav', 'tab.txt', 'akordy.txt', 'sesja.json', 'all.zip', 'transkrypcja.wav'];
  for (const k of [0, 1, 2, 3, 4, 5, 6]) fs.writeFileSync(path.join(outDir, names[k]), api.bin(k));
  console.log(JSON.stringify({ notes: n, synthSamples: total, synthMs, summary: api.summary().bpm }));
})();
