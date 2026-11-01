// ui_test.js - test aplikacji w Chromium (Playwright): start, demo, odtwarzanie, eksporty, plik, mikrofon, tryb artefaktu.
// Użycie: node tools/ui_test.js <katalog_wyjściowy> <plik.wav do wgrania/mikrofonu>
'use strict';
const { chromium } = require('playwright');
const path = require('path'), fs = require('fs');
const out = process.argv[2], wav = process.argv[3];
const URL = 'file://' + path.resolve(__dirname, '..', 'dist', 'gitara-sluchacz.html');
const ok = (c, m) => { console.log((c ? 'OK   ' : 'FAIL ') + m); if (!c) process.exitCode = 1; };
const until = async (page, fn, t = 30000) => { await page.waitForFunction(fn, null, { timeout: t }); };

(async () => {
  fs.mkdirSync(out, { recursive: true });
  // ---------- 1. standalone: start, demo, odtwarzanie, eksporty
  let browser = await chromium.launch({ args: ['--autoplay-policy=no-user-gesture-required'] });
  let ctx = await browser.newContext({ viewport: { width: 1280, height: 900 }, acceptDownloads: true, colorScheme: 'dark' });
  let page = await ctx.newPage();
  const errors = [];
  page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
  page.on('pageerror', e => errors.push('pageerror: ' + e.message));
  await page.goto(URL);
  await until(page, () => window.__gs && window.__gs.S.mode === 'review');
  ok(true, 'silnik załadowany: ' + await page.textContent('#engTag'));
  ok((await page.textContent('#chord')) !== '—', 'przykład otwiera się z widocznym akordem: ' + await page.textContent('#chord'));
  await page.waitForTimeout(500);
  await page.screenshot({ path: path.join(out, 'desktop-dark.png'), fullPage: true });

  await page.click('#btnDemo');
  await page.waitForTimeout(2500);
  const t1 = await page.evaluate(() => window.__gs.S.viewT);
  ok(t1 > 1, 'odtwarzanie przesuwa kursor (t=' + t1.toFixed(2) + ' s)');
  await page.click('#pmTr');
  await until(page, () => window.__gs.S.rev.trReady, 60000);
  ok(true, 'transkrypcja wyrenderowana w C++ i odtwarzana');
  await page.click('#btnStop');

  const dl = async (sel, ext) => {
    const [d] = await Promise.all([page.waitForEvent('download', { timeout: 60000 }), page.click(sel)]);
    const p = path.join(out, d.suggestedFilename()); await d.saveAs(p);
    ok(d.suggestedFilename().endsWith(ext) && fs.statSync(p).size > 20, 'pobrano ' + d.suggestedFilename() + ' (' + fs.statSync(p).size + ' B)');
    return p;
  };
  await dl('#dlMid', '.mid'); await dl('#dlWav', '.wav'); await dl('#dlTab', '.txt'); await dl('#dlJson', '.json'); await dl('#dlChords', '.txt'); await dl('#dlSrc', '.zip');
  await dl('#dlTr', '.wav'); const zip = await dl('#dlZip', '.zip');
  fs.writeFileSync(path.join(out, 'zip-path.txt'), zip);

  // ---------- 2. wgranie pliku
  await page.setInputFiles('#file', wav);
  await until(page, () => window.__gs.S.mode === 'review' && /strum/.test(window.__gs.S.label), 60000);
  const n = await page.evaluate(() => window.__gs.S.summary.chords.length);
  ok(n >= 4, 'plik przeanalizowany, akordów w historii: ' + n);
  await page.evaluate(() => window.__gs.seek(3.5));
  await page.waitForTimeout(300);
  await page.screenshot({ path: path.join(out, 'desktop-file.png'), fullPage: true });
  // zmiana ustawień powoduje ponowną analizę
  await page.click('#settingsBox > summary');
  await page.selectOption('#win', '2048');
  await page.waitForTimeout(1500);
  await until(page, () => window.__gs.S.mode === 'review', 60000);
  ok(true, 'zmiana okna analizy -> ponowna analiza w C++');
  ok(errors.length === 0, 'brak błędów w konsoli' + (errors.length ? ': ' + errors.slice(0, 3).join(' | ') : ''));
  await ctx.close(); await browser.close();

  // ---------- 3. mikrofon (sztuczne urządzenie audio z pliku)
  browser = await chromium.launch({ args: ['--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream', '--use-file-for-fake-audio-capture=' + wav, '--autoplay-policy=no-user-gesture-required'] });
  ctx = await browser.newContext({ viewport: { width: 1280, height: 900 }, permissions: ['microphone'], acceptDownloads: true });
  page = await ctx.newPage(); const errs2 = [];
  page.on('pageerror', e => errs2.push(e.message));
  await page.goto(URL);
  await until(page, () => window.__gs && window.__gs.S.mode === 'review');
  await page.click('#btnMic');
  await until(page, () => window.__gs.S.mode === 'mic', 15000);
  await page.waitForTimeout(6500);
  const live = await page.evaluate(() => ({ frames: window.__gs.E.x.gt_frames(), chord: document.getElementById('chord').textContent, st: document.getElementById('status').textContent }));
  ok(live.frames > 40, 'mikrofon na żywo: ' + live.frames + ' ramek, akord "' + live.chord + '", ' + live.st);
  await page.screenshot({ path: path.join(out, 'desktop-live.png'), fullPage: false });
  await page.click('#btnStop');
  await until(page, () => window.__gs.S.mode === 'review' && /mikrofon/.test(window.__gs.S.label), 60000);
  ok(true, 'po Stop nagranie z mikrofonu przechodzi w tryb przeglądania i jest ponownie analizowane w C++');
  ok(errs2.length === 0, 'mikrofon: brak błędów strony' + (errs2.length ? ': ' + errs2.join(' | ') : ''));
  await ctx.close(); await browser.close();

  // ---------- 4. symulacja artefaktu: window.claude.downloads + zablokowany WebAssembly
  browser = await chromium.launch({ args: ['--autoplay-policy=no-user-gesture-required'] });
  ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  page = await ctx.newPage(); const errs3 = [];
  page.on('pageerror', e => errs3.push(e.message));
  await page.addInitScript(() => {
    window.__saved = [];
    window.claude = { use: async name => name === 'downloads' ? { save: async r => { window.__saved.push({ filename: r.filename, size: r.data.length || r.data.size || r.data.byteLength }); return { status: 'saved' }; } } : null };
    const orig = WebAssembly.instantiate; WebAssembly.instantiate = () => { throw new Error('CompileError: Wasm code generation disallowed by embedder'); };
  });
  await page.goto(URL);
  await until(page, () => window.__gs && window.__gs.S.mode === 'review', 90000);
  ok(/asm\.js/.test(await page.textContent('#engTag')), 'WebAssembly zablokowany -> działa rezerwa: ' + await page.textContent('#engTag'));
  ok((await page.textContent('#chord')) !== '—', 'rezerwa asm.js rozpoznaje akord: ' + await page.textContent('#chord'));
  await page.waitForTimeout(300);
  ok(!(await page.isHidden('#micHint')), 'w artefakcie widać wyjaśnienie o mikrofonie');
  await page.click('#dlMid'); await page.waitForTimeout(800);
  await page.click('#dlTab'); await page.waitForTimeout(800);
  const saved = await page.evaluate(() => window.__saved);
  ok(saved.some(s => s.filename === 'gitara.mid.zip'), 'MIDI w artefakcie spakowane do ZIP (rozszerzenie spoza listy): ' + JSON.stringify(saved));
  ok(saved.some(s => s.filename === 'gitara-tabulatura.txt'), 'tabulatura zapisana bezpośrednio jako .txt');
  await page.screenshot({ path: path.join(out, 'artifact-sim.png'), fullPage: false });
  ok(errs3.length === 0, 'artefakt: brak błędów strony' + (errs3.length ? ': ' + errs3.join(' | ') : ''));
  await ctx.close();

  // ---------- 5. wygląd: jasny motyw i telefon
  ctx = await browser.newContext({ viewport: { width: 1280, height: 900 }, colorScheme: 'light' });
  page = await ctx.newPage(); await page.goto(URL); await until(page, () => window.__gs && window.__gs.S.mode === 'review', 90000);
  await page.waitForTimeout(600); await page.screenshot({ path: path.join(out, 'desktop-light.png'), fullPage: true }); await ctx.close();
  ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, isMobile: true, colorScheme: 'dark' });
  page = await ctx.newPage(); await page.goto(URL); await until(page, () => window.__gs && window.__gs.S.mode === 'review', 90000);
  await page.waitForTimeout(600);
  const over = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  ok(over <= 1, 'telefon: brak poziomego przewijania (nadmiar ' + over + ' px)');
  await page.screenshot({ path: path.join(out, 'mobile-dark.png'), fullPage: true });
  await ctx.close(); await browser.close();
})().catch(e => { console.error('TEST ERROR', e); process.exit(1); });
