/* Gitara Słuchacz - interfejs. Cała analiza dźwięku jest w silniku C++ (src/*.hpp), skompilowanym do WebAssembly.
   Ten plik: ładowanie silnika, mikrofon/plik, odtwarzanie, rysowanie i pobieranie. */
(function () {
'use strict';
const $ = id => document.getElementById(id);
const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
const NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'];
const midiName = m => NAMES[((m % 12) + 12) % 12] + (Math.floor(m / 12) - 1);
const tick = () => new Promise(r => setTimeout(r, 0));
const fmtT = t => Math.floor(t / 60) + ':' + (t % 60).toFixed(1).padStart(4, '0');
const esc = s => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
const store = {
  get(k, d) { try { const v = localStorage.getItem('gs3_' + k); return v === null ? d : JSON.parse(v); } catch (e) { return d; } },
  set(k, v) { try { localStorage.setItem('gs3_' + k, JSON.stringify(v)); } catch (e) {} },
};
const IN_ARTIFACT = !!(window.claude && typeof window.claude.use === 'function');
const ALLOWED_EXT = ['gif', 'png', 'jpg', 'jpeg', 'webp', 'mp4', 'webm', 'mov', 'txt', 'json', 'md', 'docx', 'pptx', 'epub', 'csv', 'ttf', 'html', 'svg', 'pdf', 'xlsx', 'zip', 'fig'];

// ------------------------------------------------------------------ paleta (z tokenów CSS)
let PAL = {};
function readPalette() {
  const cs = getComputedStyle(document.documentElement), g = n => cs.getPropertyValue(n).trim();
  PAL = { ink: g('--ink'), ink2: g('--ink-2'), mute: g('--mute'), hair: g('--hair'), hair2: g('--hair-2'), surface: g('--surface'), paper: g('--paper'),
    accent: g('--accent'), emph: g('--emph'), good: g('--good'), warn: g('--warn'), crit: g('--crit'),
    wood1: g('--wood-1'), wood2: g('--wood-2'), fret: g('--fret'), bone: g('--bone') };
}

// ------------------------------------------------------------------ silnik C++ (WebAssembly albo asm.js)
const E = { x: null, mem: null, kind: '', wasmBytes: 0, tunings: [] };
const dec = new TextDecoder();
const J = n => JSON.parse(dec.decode(new Uint8Array(E.mem.buffer, E.x.gt_text(), n)));
const f32 = (p, n) => new Float32Array(E.mem.buffer, p, n);

async function bootEngine() {
  const wasi = {
    fd_close: () => 0, fd_seek: () => 70,
    fd_write: (fd, iov, n, out) => {
      const dv = new DataView(E.mem.buffer); let w = 0;
      for (let i = 0; i < n; i++) w += dv.getUint32(iov + i * 8 + 4, true);
      dv.setUint32(out, w, true); return 0;
    },
  };
  const b64 = $('wasmB64').textContent.replace(/\s+/g, '');
  const bin = atob(b64), bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  E.wasmBytes = bytes.length;
  let x = null, kind = '';
  try {
    if (typeof WebAssembly !== 'object') throw new Error('brak WebAssembly');
    x = (await WebAssembly.instantiate(bytes, { wasi_snapshot_preview1: wasi })).instance.exports;
    kind = 'WebAssembly';
  } catch (e) {
    // platforma może zabraniać kompilacji WebAssembly (CSP): ten sam silnik przetłumaczony na JS (wasm2js)
    if (typeof window.__gtAsmEngine === 'function') { x = window.__gtAsmEngine(wasi); kind = 'asm.js'; }
    else throw e;
  }
  E.x = x; E.mem = x.memory; E.kind = kind;
  if (x._initialize) x._initialize();
  E.tunings = J(x.gt_tuning_json());
}

// ------------------------------------------------------------------ stan
const S = {
  mode: 'idle', ctx: null, node: null, src: null, stream: null, fs: 44100, label: '',
  rev: null, viewT: 0, playing: false, playMode: 'orig', srcs: [], playCtx0: 0, playT0: 0, view: 'chart',
  lastPushAt: 0, pushMs: 0, anaMs: 0, win: 0.372, all: null, summary: null,
  frameN: -1, frame: null, tuning: 0, nz: { type: 'none', lvl: -40, pk: [0, 0, 0, 0, 0, 0, 0], ph: 0, scale: 1 },
  downloads: null, logAt: 0, logKey: '', tl: null, drag: false,
};

// ------------------------------------------------------------------ ustawienia
const SET_KEYS = ['tuning', 'win', 'a4', 'mains', 'gate', 'sustain', 'autoTune', 'autoGate', 'hand', 'octaves', 'nzType', 'nzLvl'];
const readSet = () => ({
  tuning: +$('tuning').value || 0, win: +$('win').value, sustain: +$('sustain').value, a4: +$('a4').value || 440, mains: +$('mains').value, gate: +$('gate').value,
  autoTune: $('autoTune').checked, autoGate: $('autoGate').checked, hand: $('hand').checked, octaves: $('octaves').checked,
});
function pushCfg() {
  const s = readSet();
  E.x.gt_config(s.a4, s.win, s.gate, s.mains, s.autoTune ? 1 : 0, s.autoGate ? 1 : 0, s.tuning, s.octaves ? 1 : 0, s.hand ? 1 : 0, s.sustain);
  S.tuning = s.tuning;
}
let reTimer = 0;
function onSettings(e) {
  $('gateV').textContent = $('gate').value + ' dB';
  $('nzV').textContent = $('nzLvl').value + ' dBFS';
  S.nz.type = $('nzType').value; S.nz.lvl = +$('nzLvl').value;
  for (const k of SET_KEYS) store.set(k, $(k).type === 'checkbox' ? $(k).checked : $(k).value);
  if (E.x) { pushCfg(); buildStringRow(); }
  if (e && S.mode === 'review' && S.rev) { clearTimeout(reTimer); reTimer = setTimeout(() => reanalyze(), 450); }
}
function loadSettings() {
  $('tuning').innerHTML = E.tunings.map((t, i) => '<option value="' + i + '">' + esc(t.name) + '</option>').join('');
  for (const k of SET_KEYS) {
    const v = store.get(k, null);
    if (v !== null) { if ($(k).type === 'checkbox') $(k).checked = !!v; else $(k).value = v; }
    $(k).addEventListener('input', onSettings);
  }
  onSettings();
}

// ------------------------------------------------------------------ szum testowy
function gauss() { return Math.sqrt(-2 * Math.log(Math.random() + 1e-12)) * Math.cos(6.283185307 * Math.random()); }
function pinkStep(p, w) {
  p[0] = 0.99886 * p[0] + w * 0.0555179; p[1] = 0.99332 * p[1] + w * 0.0750759; p[2] = 0.969 * p[2] + w * 0.153852;
  p[3] = 0.8665 * p[3] + w * 0.3104856; p[4] = 0.55 * p[4] + w * 0.5329522; p[5] = -0.7616 * p[5] - w * 0.016898;
  const o = p[0] + p[1] + p[2] + p[3] + p[4] + p[5] + p[6] + w * 0.5362; p[6] = w * 0.115926; return o;
}
(function calibratePink() { const p = [0, 0, 0, 0, 0, 0, 0]; let s = 0; const N = 100000; for (let i = 0; i < N; i++) { const v = pinkStep(p, gauss()); s += v * v; } S.nz.scale = 1 / Math.sqrt(s / N); })();
const HUMA = [1, 0.6, 0.35, 0.2, 0.12], HUMN = 1 / Math.sqrt(HUMA.reduce((a, b) => a + b * b, 0) / 2);
function injectNoise(x, fs) {
  const z = S.nz; if (z.type === 'none') return x;
  const y = new Float32Array(x.length), A = Math.pow(10, z.lvl / 20), hf = (+$('mains').value || 50), dph = 6.283185307 * hf / fs;
  for (let i = 0; i < x.length; i++) {
    let v = 0;
    if (z.type === 'white') v = gauss();
    else if (z.type === 'pink') v = pinkStep(z.pk, gauss()) * z.scale;
    if (z.type === 'hum' || z.type === 'mix') {
      let h = 0; for (let k = 0; k < 5; k++) h += HUMA[k] * Math.sin((k + 1) * z.ph + k); h *= HUMN; z.ph += dph; if (z.ph > 628.3185) z.ph -= 628.3185;
      v = z.type === 'hum' ? h + 0.02 * gauss() : 0.8 * pinkStep(z.pk, gauss()) * z.scale + 0.45 * gauss() + 0.4 * h;
    }
    y[i] = x[i] + v * A;
  }
  return y;
}
function noisyCopy(samples, fs) {
  const out = new Float32Array(samples.length); S.nz.pk = [0, 0, 0, 0, 0, 0, 0]; S.nz.ph = 0;
  for (let i = 0; i < samples.length; i += 8192) out.set(injectNoise(samples.subarray(i, Math.min(samples.length, i + 8192)), fs), i);
  return out;
}

// ------------------------------------------------------------------ status, powiadomienia
function setStatus(t, cls) { const s = $('status'); s.textContent = t; s.className = 'status' + (cls ? ' ' + cls : ''); }
let toastT = 0;
function toast(msg, ms) { const t = $('toast'); t.textContent = msg; t.classList.add('on'); clearTimeout(toastT); toastT = setTimeout(() => t.classList.remove('on'), ms || 3000); }
function progress(p) { $('prog').classList.toggle('on', p >= 0 && p < 1); $('progBar').style.width = Math.round(clamp(p, 0, 1) * 100) + '%'; }
function showMicHint(html) { const h = $('micHint'); h.innerHTML = html; h.hidden = !html; }
const micHelp = () => IN_ARTIFACT
  ? 'Mikrofon jest w artefakcie zablokowany. Użyj Demo albo Pliku audio, a żeby grać na żywo, pobierz aplikację (Więcej formatów) i otwórz ją z dysku.'
  : 'Brak dostępu do mikrofonu. Sprawdź zgodę w pasku adresu (wymagany HTTPS albo plik z dysku) albo wgraj plik audio.';

// ------------------------------------------------------------------ audio: kontekst, mikrofon
async function ensureCtx() {
  if (!S.ctx) S.ctx = new (window.AudioContext || window.webkitAudioContext)({ latencyHint: 'interactive' });
  if (S.ctx.state !== 'running') { try { await S.ctx.resume(); } catch (e) {} }
  return S.ctx;
}
async function ensureNode() {
  if (S.node) return;
  const ctx = S.ctx;
  if (ctx.audioWorklet) {
    try {
      const code = "class Cap extends AudioWorkletProcessor{constructor(){super();this.b=new Float32Array(1024);this.n=0}process(i){const x=i[0]&&i[0][0];if(x){for(let k=0;k<x.length;k++){this.b[this.n++]=x[k];if(this.n===1024){this.port.postMessage(this.b.slice(0));this.n=0}}}return true}}registerProcessor('cap',Cap)";
      const url = URL.createObjectURL(new Blob([code], { type: 'application/javascript' }));
      await ctx.audioWorklet.addModule(url);
      S.node = new AudioWorkletNode(ctx, 'cap', { numberOfInputs: 1, numberOfOutputs: 1, channelCount: 1 });
      S.node.port.onmessage = e => feed(e.data);
    } catch (e) { S.node = null; }
  }
  if (!S.node) {
    S.node = ctx.createScriptProcessor(2048, 1, 1);
    S.node.onaudioprocess = e => feed(new Float32Array(e.inputBuffer.getChannelData(0)));
  }
  const mute = ctx.createGain(); mute.gain.value = 0; S.node.connect(mute); mute.connect(ctx.destination);
}
function feed(chunk) {
  if (S.mode !== 'mic') return;
  try {
    const x = injectNoise(chunk, S.ctx.sampleRate), n = x.length, X = E.x;
    const p = X.gt_input(n); f32(p, n).set(x);
    const t0 = performance.now(); X.gt_push(n); S.pushMs += performance.now() - t0; S.lastPushAt = performance.now();
  } catch (e) { console.error(e); setStatus('błąd analizy', 'err'); }
}
async function startMic() {
  try {
    await stopAll(true);
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) throw Object.assign(new Error('brak mikrofonu'), { name: 'NotSupportedError' });
    await ensureCtx(); pushCfg();
    const stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: false, noiseSuppression: false, autoGainControl: false, channelCount: 1 } });
    S.fs = S.ctx.sampleRate; E.x.gt_init(S.fs); S.pushMs = 0; S.frameN = -1; S.rev = null; S.all = null; S.summary = null;
    S.stream = stream; await ensureNode();
    S.src = S.ctx.createMediaStreamSource(stream); S.src.connect(S.node);
    S.mode = 'mic'; setStatus('słucham', 'on'); showMicHint('');
    setReview(false); updateButtons();
  } catch (e) {
    stopCapture(); S.mode = S.rev ? 'review' : 'idle'; updateButtons();
    setStatus(e.name === 'NotAllowedError' || e.name === 'SecurityError' ? 'mikrofon zablokowany' : 'błąd mikrofonu', 'err');
    showMicHint(micHelp());
  }
}
function stopCapture() {
  try { if (S.stream) S.stream.getTracks().forEach(t => t.stop()); } catch (e) {}
  try { if (S.src) S.src.disconnect(); } catch (e) {}
  S.stream = S.src = null;
}

// ------------------------------------------------------------------ analiza całego nagrania w C++
async function analyze(samples, fs, label) {
  stopCapture(); stopSources();
  S.mode = 'busy'; updateButtons(); setReview(false);
  const X = E.x, t0 = performance.now();
  pushCfg();
  const input = S.nz.type !== 'none' ? noisyCopy(samples, fs) : samples;
  const p = X.gt_file_alloc(input.length); f32(p, input.length).set(input);
  setStatus('analiza…', 'on'); progress(0.02); await tick();
  X.gt_file_begin(fs, 1);
  let pr = 0;
  while (pr < 1000) { pr = X.gt_file_step(1 << 17); progress(pr / 1000); setStatus('analiza ' + Math.round(pr / 10) + '%', 'on'); await tick(); }
  X.gt_file_free(); progress(1);
  S.anaMs = performance.now() - t0; S.fs = fs; S.label = label;
  S.rev = { samples, fs, dur: samples.length / fs, label, buf: null, trBuf: null, trReady: false };
  afterAnalysis();
}
function afterAnalysis() {
  const X = E.x;
  S.mode = 'review'; S.playing = false; S.frameN = -1;
  S.summary = J(X.gt_summary_json()); S.win = S.summary.win;
  S.all = J(X.gt_roll_json(-1, S.rev.dur + 1));
  S.logKey = ''; S.viewT = Math.min(S.viewT, S.rev.dur);
  setReview(true); updateButtons();
  setStatus((S.label || 'nagranie').slice(0, 24) + ', ' + Math.round(S.rev.dur) + ' s', 'on');
  $('sub').title = E.kind + ' ' + Math.round(E.wasmBytes / 1024) + ' KB, analiza ' + (S.anaMs / 1000 / Math.max(0.1, S.rev.dur)).toFixed(3) + '× czasu nagrania';
  renderChords(true); if (S.view === 'table') renderTable();
}
async function reanalyze() { if (S.rev && S.mode !== 'busy') { const r = S.rev; await analyze(r.samples, r.fs, r.label); } }
async function finalizeLive() {
  const X = E.x; X.gt_finish();
  const n = X.gt_rec_len(), fs = X.gt_rec_rate();
  if (n < fs * 0.6) { S.mode = 'idle'; setStatus('za krótkie nagranie'); updateButtons(); return; }
  const pcm = new Int16Array(E.mem.buffer, X.gt_rec_ptr(), n), samples = new Float32Array(n);
  for (let i = 0; i < n; i++) samples[i] = pcm[i] / 32768;
  S.viewT = 0;
  await analyze(samples, fs, 'mikrofon');
}
async function stopAll(silent) {
  const wasLive = S.mode === 'mic';
  stopSources(); stopCapture();
  if (wasLive) { S.mode = 'busy'; await finalizeLive(); return; }
  if (S.mode !== 'review') { S.mode = S.rev ? 'review' : 'idle'; if (!silent) setStatus('gotowy'); }
  updateButtons();
}
async function loadDemo(autoplay) {
  const X = E.x, fs = 44100;
  await stopAll(true);
  const n = X.gt_demo_render(fs), samples = f32(X.gt_synth_ptr(), n).slice();
  S.viewT = autoplay ? 0 : 3.7;
  await analyze(samples, fs, 'demo');
  if (autoplay) await play(0);
}
async function openFile(file) {
  try {
    await stopAll(true);
    setStatus('wczytuję…', 'on'); await ensureCtx();
    const ab = await file.arrayBuffer();
    const buf = await new Promise((res, rej) => { const p = S.ctx.decodeAudioData(ab, res, rej); if (p && p.then) p.then(res, rej); });
    const mono = new Float32Array(buf.length);
    for (let c = 0; c < buf.numberOfChannels; c++) { const d = buf.getChannelData(c); for (let i = 0; i < d.length; i++) mono[i] += d[i] / buf.numberOfChannels; }
    S.viewT = 0;
    await analyze(mono, buf.sampleRate, file.name);
  } catch (e) { S.mode = S.rev ? 'review' : 'idle'; updateButtons(); progress(1); setStatus('nie mogę odczytać pliku', 'err'); toast('Nie udało się wczytać pliku. Spróbuj WAV, MP3 albo M4A.'); }
}

// ------------------------------------------------------------------ odtwarzanie całości
function revBuffer() {
  const r = S.rev;
  if (!r.buf) { r.buf = S.ctx.createBuffer(1, r.samples.length, r.fs); r.buf.copyToChannel(r.samples, 0); }
  return r.buf;
}
async function renderTranscription() {
  await ensureCtx();
  const X = E.x, prev = $('status').textContent;
  X.gt_synth_begin(22050);
  const n = X.gt_synth_count();
  if (!n) { toast('Brak wykrytych nut do odtworzenia.'); return false; }
  for (let i = 0; i < n; i += 24) {
    X.gt_synth_step(i, Math.min(n, i + 24));
    progress(i / n); setStatus('transkrypcja ' + Math.round(100 * i / n) + '%', 'on'); await tick();
  }
  X.gt_synth_end(); progress(1);
  const len = X.gt_synth_len(), buf = S.ctx.createBuffer(1, len, 22050);
  buf.copyToChannel(f32(X.gt_synth_ptr(), len).slice(), 0);
  S.rev.trBuf = buf; S.rev.trReady = true;
  setStatus(prev, 'on');
  return true;
}
function stopSources() {
  for (const s of S.srcs) { try { s.onended = null; s.stop(); s.disconnect(); } catch (e) {} }
  S.srcs = []; S.playing = false; setPlayUi();
}
function addSource(buf, offset, when, gain) {
  const s = S.ctx.createBufferSource(), g = S.ctx.createGain();
  s.buffer = buf; g.gain.value = gain; s.connect(g); g.connect(S.ctx.destination);
  s.start(when, clamp(offset, 0, Math.max(0, buf.duration - 0.01)));
  S.srcs.push(s);
}
async function play(t) {
  if (S.mode !== 'review' || !S.rev) return;
  await ensureCtx();
  const mode = S.playMode;
  if (mode !== 'orig' && !S.rev.trReady) { const ok = await renderTranscription(); if (!ok && mode === 'tr') return; }
  stopSources();
  const when = S.ctx.currentTime + 0.05;
  if (mode !== 'tr') addSource(revBuffer(), t, when, mode === 'both' ? 0.85 : 1);
  if (mode !== 'orig' && S.rev.trReady) addSource(S.rev.trBuf, t, when, mode === 'both' ? 0.75 : 1);
  S.playCtx0 = when; S.playT0 = t; S.playing = true; S.viewT = t;
  setPlayUi(); updateButtons();
}
function pause() { stopSources(); updateButtons(); }
async function togglePlay() { if (S.mode !== 'review') return; if (S.playing) pause(); else await play(S.viewT >= S.rev.dur - 0.05 ? 0 : S.viewT); }
function seek(t) { if (!S.rev) return; S.viewT = clamp(t, 0, S.rev.dur); if (S.playing) play(S.viewT); }
function setPlayUi() {
  $('playTxt').textContent = S.playing ? 'Pauza' : 'Odtwórz';
  $('btnPlay').querySelector('svg').innerHTML = S.playing ? '<path d="M7 5h4v14H7zM13 5h4v14h-4z"/>' : '<path d="M7 5v14l12-7z"/>';
}
function setPlayMode(m) {
  S.playMode = m;
  for (const [id, k] of [['pmOrig', 'orig'], ['pmTr', 'tr'], ['pmBoth', 'both']]) $(id).setAttribute('aria-pressed', String(m === k));
  if (S.playing) play(S.viewT);
}
function advancePlayhead() {
  if (!S.playing) return;
  const t = S.playT0 + Math.max(0, S.ctx.currentTime - S.playCtx0);
  if (t >= S.rev.dur) { S.viewT = S.rev.dur; stopSources(); updateButtons(); } else S.viewT = t;
}
function setReview(on) {
  $('bar').style.visibility = on ? 'visible' : 'hidden';
  S.view = 'chart'; applyView();
}
function applyView() {
  const table = S.view === 'table' && S.mode === 'review';
  $('roll').hidden = table; $('tblWrap').hidden = !table;
  $('vwChart').setAttribute('aria-pressed', String(!table)); $('vwTable').setAttribute('aria-pressed', String(table));
  if (table) renderTable();
}
function renderTable() {
  if (!S.all) return;
  const ev = S.all.ev.slice().sort((a, b) => a[1] - b[1]).slice(0, 3000);
  $('tblBody').innerHTML = ev.map(e => '<tr><td>' + fmtT(e[1]) + '</td><td>' + midiName(e[0]) + '</td><td>' + (e[2] - e[1]).toFixed(2) + ' s</td><td>' + e[3] + '</td></tr>').join('');
}

// ------------------------------------------------------------------ pobieranie
function readBin(kind) { const X = E.x, n = X.gt_export(kind); return new Uint8Array(E.mem.buffer, X.gt_bin(), n).slice(); }
function zipFiles(files) {
  const X = E.x; X.gt_zip_reset();
  const enc = new TextEncoder();
  for (const f of files) {
    const nm = enc.encode(f.name), data = typeof f.data === 'string' ? enc.encode(f.data) : f.data;
    const p = X.gt_scratch(nm.length + data.length), u = new Uint8Array(E.mem.buffer, p, nm.length + data.length);
    u.set(nm, 0); u.set(data, nm.length); X.gt_zip_add(nm.length, data.length);
  }
  const n = X.gt_zip_finish(); return new Uint8Array(E.mem.buffer, X.gt_bin(), n).slice();
}
async function saveFile(name, data, mime) {
  if (S.downloads) {
    const ext = name.split('.').pop().toLowerCase();
    try {
      if (ALLOWED_EXT.indexOf(ext) >= 0) await S.downloads.save({ filename: name, data });
      else {
        await S.downloads.save({ filename: name + '.zip', data: zipFiles([{ name, data }]) });
        toast('Artefakt zapisuje tylko wybrane formaty, więc ' + name + ' jest w ZIP-ie. W pobranej aplikacji zapisze się bez pakowania.', 5000);
        return;
      }
      toast('Zapisano ' + name);
    } catch (e) { toast(e && e.code === 'declined' ? 'Anulowano zapis.' : 'Nie udało się zapisać pliku.'); }
    return;
  }
  const url = URL.createObjectURL(new Blob([data], { type: mime || 'application/octet-stream' }));
  const a = document.createElement('a'); a.href = url; a.download = name; document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 4000);
  toast('Pobrano ' + name);
}
const haveData = () => !!(E.x && E.x.gt_frames() > 0 && (S.mode === 'review' || S.mode === 'mic'));
async function doExport(kind, name, mime) {
  if (!haveData()) { toast('Najpierw zagraj, wgraj plik albo włącz demo.'); return; }
  if ((kind === 6 || kind === 5) && S.rev && !S.rev.trReady) { const ok = await renderTranscription(); if (!ok && kind === 6) return; }
  const bytes = readBin(kind);
  if (!bytes.length) { toast('Brak danych do zapisania.'); return; }
  await saveFile(name, bytes, mime);
}
async function copyText(t) {
  try { await navigator.clipboard.writeText(t); toast('Skopiowano'); }
  catch (e) {
    const a = document.createElement('textarea'); a.value = t; a.style.position = 'fixed'; a.style.opacity = '0'; document.body.appendChild(a); a.select();
    try { document.execCommand('copy'); toast('Skopiowano'); } catch (er) { toast('Schowek jest zablokowany. Pobierz tabulaturę jako plik.'); } a.remove();
  }
}
async function downloadApp() {
  try {
    const r = await fetch('gitara-sluchacz.html'); if (!r.ok) throw new Error('HTTP ' + r.status);
    await saveFile('gitara-sluchacz.html', await r.text(), 'text/html');
  } catch (e) { toast('Nie mogę pobrać pliku aplikacji z tej strony. Jest w repozytorium: dist/gitara-sluchacz.html.', 5000); }
}
let SRC = { files: [] };
function wireExports() {
  const pick = (id, fn) => { $(id).onclick = () => { $('menu').open = false; fn(); }; };
  $('dlZip').onclick = () => doExport(5, 'gitara-sesja.zip', 'application/zip');
  pick('dlWav', () => doExport(1, 'gitara-nagranie.wav', 'audio/wav'));
  pick('dlMid', () => doExport(0, 'gitara.mid', 'audio/midi'));
  pick('dlTr', () => doExport(6, 'gitara-transkrypcja.wav', 'audio/wav'));
  pick('dlTab', () => doExport(2, 'gitara-tabulatura.txt', 'text/plain'));
  pick('dlChords', () => doExport(3, 'gitara-akordy.txt', 'text/plain'));
  pick('dlJson', () => doExport(4, 'gitara-sesja.json', 'application/json'));
  pick('dlSrc', () => saveFile('gitara-kod-cpp.zip', zipFiles(SRC.files.map(f => ({ name: 'src/' + f.name, data: f.code }))), 'application/zip'));
  pick('dlApp', downloadApp);
  pick('cpTab', () => { if (!haveData()) { toast('Najpierw zagraj, wgraj plik albo włącz demo.'); return; } copyText(new TextDecoder().decode(readBin(2))); });
  document.addEventListener('click', e => { const m = $('menu'); if (m.open && !m.contains(e.target)) m.open = false; });
  if (IN_ARTIFACT) {
    $('dlApp').hidden = false;
    window.claude.use('downloads').then(d => { S.downloads = d; if (!d) $('dlApp').hidden = true; }).catch(() => { $('dlApp').hidden = true; });
  }
}

// ------------------------------------------------------------------ tło z kodu silnika
function initSource() {
  try { SRC = JSON.parse($('srcData').textContent); } catch (e) { SRC = { files: [] }; }
  const eng = SRC.files.find(f => f.name === 'gt_engine.hpp') || SRC.files[0];
  if (!eng) return;
  const re = /(\/\/[^\n]*)|\b(?:auto|bool|class|const|constexpr|double|else|float|for|if|inline|int|namespace|return|static|struct|void|while|true|false|std)\b/g;
  const code = eng.code.split('\n').slice(0, 130).join('\n');
  let out = '', last = 0, m;
  while ((m = re.exec(code))) { out += esc(code.slice(last, m.index)) + '<span class="' + (m[1] ? 'c' : 'k') + '">' + esc(m[0]) + '</span>'; last = re.lastIndex; }
  out += esc(code.slice(last));
  $('codeBg').innerHTML = out + '\n\n' + out;
}

// ------------------------------------------------------------------ rysowanie: wspólne
function fit(c) {
  if (!c.dataset.h) { c.dataset.h = c.getAttribute('height'); c.style.height = c.dataset.h + 'px'; }
  const r = c.getBoundingClientRect(), d = Math.min(2, window.devicePixelRatio || 1);
  const w = Math.max(10, Math.round((r.width || 300) * d)), h = Math.round(+c.dataset.h * d);
  if (c.width !== w || c.height !== h) { c.width = w; c.height = h; }
  return { g: c.getContext('2d'), w, h, d };
}
function rrect(g, x, y, w, h, r) { g.beginPath(); g.moveTo(x + r, y); g.arcTo(x + w, y, x + w, y + h, r); g.arcTo(x + w, y + h, x, y + h, r); g.arcTo(x, y + h, x, y, r); g.arcTo(x, y, x + w, y, r); g.closePath(); }
const FONT = 'Hanken Grotesk, system-ui, sans-serif', FDISP = 'Bricolage Grotesque, system-ui, sans-serif';
const openMidis = () => (E.tunings[S.tuning] || { open: [40, 45, 50, 55, 59, 64] }).open;
const rootPcOf = name => { if (!name) return -1; if (name[1] === '#') return NAMES.indexOf(name.slice(0, 2)); return NAMES.indexOf(name[0]); };

// gryf: wszystkie nuty w kolorze akcentu, pryma akordu w kolorze wyróżnienia, strefa ręki jako jasny pas
function drawNeck(fg, rootPc, hz) {
  const { g, w, h, d } = fit($('neck')); g.clearRect(0, 0, w, h);
  const NF = 17, L = 62 * d, R = w - 12 * d, T = 32 * d, B = h - 32 * d;
  const fx = n => L + (R - L) * (1 - Math.pow(2, -n / 12)) / (1 - Math.pow(2, -NF / 12)), sy = i => T + (B - T) * (5 - i) / 5;
  const open = openMidis();
  const grd = g.createLinearGradient(0, T - 14 * d, 0, B + 14 * d); grd.addColorStop(0, PAL.wood2); grd.addColorStop(1, PAL.wood1);
  g.fillStyle = grd; rrect(g, L, T - 14 * d, R - L, B - T + 28 * d, 6 * d); g.fill();
  g.globalAlpha = 0.07; g.strokeStyle = '#000'; g.lineWidth = d;
  for (let i = 0; i < 26; i++) { const y = T - 14 * d + (B - T + 28 * d) * ((i * 0.618) % 1); g.beginPath(); g.moveTo(L, y); g.lineTo(R, y + ((i % 3) - 1) * 2 * d); g.stroke(); }
  g.globalAlpha = 1;
  if (hz) { // strefa ręki
    const x1 = hz[0] <= 0 ? L : fx(hz[0] - 1) + 2 * d, x2 = fx(Math.min(hz[1], NF)) - 2 * d;
    g.fillStyle = 'rgba(255,255,255,.10)'; rrect(g, x1, T - 12 * d, x2 - x1, B - T + 24 * d, 8 * d); g.fill();
    g.strokeStyle = 'rgba(255,255,255,.32)'; g.lineWidth = d; g.stroke();
  }
  g.fillStyle = 'rgba(233,226,208,.26)';
  const my = (T + B) / 2;
  for (const n of [3, 5, 7, 9, 15, 17]) { g.beginPath(); g.arc((fx(n - 1) + fx(n)) / 2, my, 5 * d, 0, 7); g.fill(); }
  for (const dy of [-1.5, 1.5]) { g.beginPath(); g.arc((fx(11) + fx(12)) / 2, my + dy * (B - T) / 5 * 0.9, 5 * d, 0, 7); g.fill(); }
  for (let n = 1; n <= NF; n++) {
    const x = fx(n), fg2 = g.createLinearGradient(x - 1.5 * d, 0, x + 1.5 * d, 0);
    fg2.addColorStop(0, 'rgba(0,0,0,.35)'); fg2.addColorStop(0.5, PAL.fret); fg2.addColorStop(1, 'rgba(0,0,0,.25)');
    g.fillStyle = fg2; g.fillRect(x - 1.6 * d, T - 14 * d, 3.2 * d, B - T + 28 * d);
  }
  g.fillStyle = PAL.bone; g.fillRect(L - 6 * d, T - 16 * d, 7 * d, B - T + 32 * d);
  const gauge = [2.7, 2.2, 1.8, 1.3, 1.0, 0.8];
  g.font = '600 ' + 12 * d + 'px ' + FDISP; g.textAlign = 'center'; g.textBaseline = 'middle';
  for (let i = 0; i < 6; i++) {
    const y = sy(i);
    g.strokeStyle = 'rgba(0,0,0,.35)'; g.lineWidth = (gauge[i] + 1.2) * d; g.beginPath(); g.moveTo(L - 4 * d, y + 1.5 * d); g.lineTo(R, y + 1.5 * d); g.stroke();
    g.strokeStyle = i < 3 ? '#c9a45a' : '#d8dee7'; g.lineWidth = gauge[i] * d; g.beginPath(); g.moveTo(L - 4 * d, y); g.lineTo(R, y); g.stroke();
    g.fillStyle = PAL.mute; g.fillText(NAMES[open[i] % 12], 12 * d, y);
  }
  g.fillStyle = PAL.mute; g.font = '500 ' + 11 * d + 'px ' + FONT;
  for (const n of [3, 5, 7, 9, 12, 15]) g.fillText(String(n), (fx(n - 1) + fx(n)) / 2, B + 22 * d);
  if (hz) { g.fillStyle = PAL.ink2; g.textAlign = 'left'; g.fillText('ręka ' + (hz[0] === hz[1] ? hz[0] : hz[0] + '–' + hz[1]), Math.max(L + 4 * d, fx(Math.max(0, hz[0] - 1))), T - 22 * d); g.textAlign = 'center'; }
  const r = Math.min(13 * d, (B - T) / 5 * 0.44);
  g.font = '700 ' + 11.5 * d + 'px ' + FDISP;
  for (const p of fg) {
    const midi = p[0], s = p[1] - 1, fret = p[2], pc = midi % 12, y = sy(s), isRoot = pc === rootPc;
    const x = fret === 0 ? L - 24 * d : (fx(fret - 1) + fx(Math.min(fret, NF))) / 2;
    const col = isRoot ? PAL.emph : PAL.accent;
    g.beginPath(); g.arc(x, y, r, 0, 7);
    if (fret === 0) { g.fillStyle = PAL.surface; g.fill(); g.lineWidth = 2.4 * d; g.strokeStyle = col; g.stroke(); g.fillStyle = PAL.ink; }
    else { g.fillStyle = col; g.fill(); g.lineWidth = 2 * d; g.strokeStyle = 'rgba(0,0,0,.35)'; g.stroke(); g.fillStyle = '#fff'; }
    g.fillText(NAMES[pc], x, y + 0.5 * d);
  }
}

// analizator: poziom (słupek po lewej, ze znacznikiem progu ciszy) i widmo pików na skali logarytmicznej w jednym pasku
function drawAnalyzer(f) {
  const { g, w, h, d } = fit($('an')); g.clearRect(0, 0, w, h);
  const fmin = 60, fmax = 5000, L = 22 * d, R = w - 4 * d, T = 6 * d, B = h - 20 * d, lg = Math.log(fmax / fmin);
  const X = fr => L + Math.log(fr / fmin) / lg * (R - L);
  g.font = '500 ' + 10.5 * d + 'px ' + FONT; g.textAlign = 'center';
  for (const fr of [100, 500, 1000, 4000]) { const x = X(fr); g.strokeStyle = PAL.hair; g.lineWidth = d; g.beginPath(); g.moveTo(x, T); g.lineTo(x, B); g.stroke(); g.fillStyle = PAL.mute; g.fillText(fr >= 1000 ? fr / 1000 + 'k' : String(fr), x, h - 5 * d); }
  g.strokeStyle = PAL.hair2; g.beginPath(); g.moveTo(L, B); g.lineTo(R, B); g.stroke();
  const lv = f ? clamp((f.lv + 80) / 80, 0, 1) : 0, gate = clamp((+$('gate').value + 80) / 80, 0, 1);
  g.fillStyle = PAL.hair; rrect(g, 4 * d, T, 8 * d, B - T, 4 * d); g.fill();
  if (lv > 0) { g.fillStyle = lv > 0.93 ? PAL.crit : PAL.accent; const hh = (B - T) * lv; rrect(g, 4 * d, B - hh, 8 * d, hh, 4 * d); g.fill(); }
  g.fillStyle = PAL.mute; g.fillRect(2 * d, B - (B - T) * gate, 12 * d, d);
  if (!f || f.sil) return;
  const own = p => { for (const n of f.n) for (let k = 1; k <= 14; k++) { const fh = k * n[1] * Math.sqrt(1 + 2.5e-4 * k * k); if (Math.abs(1200 * Math.log2(p[0] / fh)) < 35) return n; } return null; };
  for (const p of f.pk) {
    if (p[0] < fmin || p[0] > fmax) continue;
    const db = 20 * Math.log10(p[1] + 1e-9), y = B - clamp((db + 90) / 80, 0, 1) * (B - T), x = X(p[0]);
    g.strokeStyle = own(p) ? PAL.accent : PAL.mute; g.lineWidth = 1.6 * d; g.beginPath(); g.moveTo(x, B); g.lineTo(x, y); g.stroke();
    g.fillStyle = g.strokeStyle; g.beginPath(); g.arc(x, y, 2.4 * d, 0, 7); g.fill();
  }
  g.fillStyle = PAL.ink2; g.font = '600 ' + 11 * d + 'px ' + FDISP;
  let lastX = -1e9;
  for (const n of f.n.slice().sort((a, b) => a[1] - b[1])) { const x = X(n[1]); if (x - lastX > 26 * d) { g.fillText(midiName(n[0]), x, T + 9 * d); lastX = x; } }
}

// oś czasu w jednym płótnie: okno 12 s z nutami oraz mapa całego nagrania (tylko w trybie przeglądania)
function drawTimeline(R, live) {
  const { g, w, h, d } = fit($('roll')); g.clearRect(0, 0, w, h);
  const review = !live && S.mode === 'review' && S.rev;
  const miniH = review ? 40 * d : 0, gap = review ? 14 * d : 0, mainH = h - miniH - gap;
  const span = 12, frac = live ? 0.96 : 0.5;
  const tNow = live ? (R ? R.now : 0) : S.viewT, t0v = tNow - span * frac, t1v = t0v + span;
  const open = openMidis(), evs = R ? R.ev : [];
  let lo = Math.min(40, open[0]), hi = 76;
  for (const e of evs) { lo = Math.min(lo, e[0] - 1); hi = Math.max(hi, e[0] + 1); }
  lo = Math.max(36, lo); hi = Math.min(90, hi);
  const rows = hi - lo + 1, L = 40 * d, T = 22 * d, B = mainH - 4 * d, rh = (B - T) / rows;
  const X = t => L + (t - t0v) / span * (w - L - 6 * d), Y = m => B - (m - lo + 1) * rh;
  S.tl = { d, L, Rr: w - 6 * d, t0v, span, mainH, miniTop: mainH + gap, miniH, rects: [], review };
  g.textBaseline = 'middle'; g.textAlign = 'left'; g.font = '500 ' + 11 * d + 'px ' + FONT;
  for (let m = lo; m <= hi; m++) {
    const isOpen = open.indexOf(m) >= 0, c = m % 12 === 0, nearOpen = open.some(o => Math.abs(o - m) <= 2);
    if (isOpen || (c && !nearOpen)) { g.strokeStyle = PAL.hair; g.lineWidth = d; g.beginPath(); g.moveTo(L, Y(m) + rh / 2); g.lineTo(w, Y(m) + rh / 2); g.stroke(); g.fillStyle = isOpen ? PAL.ink2 : PAL.mute; g.fillText(midiName(m), 4 * d, Y(m) + rh / 2); }
  }
  if (R) {
    g.lineWidth = d; g.strokeStyle = PAL.hair2;
    for (const o of R.on) if (o >= t0v && o <= t1v) { g.beginPath(); g.moveTo(X(o), T); g.lineTo(X(o), B); g.stroke(); }
    for (const e of evs) {
      const t1 = Math.min(e[2], t1v), y = Y(e[0]);
      const x1 = X(Math.max(e[1], t0v)), x2 = Math.max(x1 + 2 * d, X(t1));
      if (x2 < L) continue;
      const now = e[4] || (review && e[1] <= S.viewT && e[2] >= S.viewT);
      g.globalAlpha = 0.5 + 0.5 * clamp(e[3] / 110, 0.2, 1); g.fillStyle = now ? PAL.emph : PAL.accent;
      rrect(g, x1, y + 1, x2 - x1, Math.max(2 * d, rh - 2 * d), Math.min(3 * d, rh / 2)); g.fill(); g.globalAlpha = 1;
      if (x2 - x1 > 28 * d && rh > 9 * d) { g.fillStyle = '#fff'; g.fillText(NAMES[e[0] % 12], x1 + 5 * d, y + rh / 2 + 0.5 * d); }
      S.tl.rects.push({ x1: x1 / d, x2: x2 / d, y1: y / d, y2: (y + rh) / d, e });
    }
    g.fillStyle = PAL.ink; g.font = '700 ' + 13 * d + 'px ' + FDISP; g.textBaseline = 'alphabetic';
    let lastX = -1e9;
    for (const c of R.ch) { const x = X(c[0]); if (x - lastX > 36 * d) { g.fillText(c[1], x + 3 * d, 15 * d); lastX = x; } }
  }
  g.strokeStyle = PAL.emph; g.lineWidth = 1.8 * d; g.beginPath(); g.moveTo(X(tNow), T - 4 * d); g.lineTo(X(tNow), B); g.stroke();
  if (!review || !S.all) return;
  // mapa całego nagrania
  const dur = S.rev.dur, ML = 6 * d, MR = w - 6 * d, MX = t => ML + t / dur * (MR - ML), MT = S.tl.miniTop, MB = MT + miniH;
  g.fillStyle = PAL.hair; g.globalAlpha = 0.5; rrect(g, ML, MT, MR - ML, miniH, 6 * d); g.fill(); g.globalAlpha = 1;
  let mlo = 100, mhi = 0;
  for (const e of S.all.ev) { mlo = Math.min(mlo, e[0]); mhi = Math.max(mhi, e[0]); }
  if (mhi < mlo) { mlo = 40; mhi = 76; }
  const mrh = Math.max(1.6 * d, (miniH - 8 * d) / (mhi - mlo + 2));
  g.fillStyle = PAL.accent; g.globalAlpha = 0.85;
  for (const e of S.all.ev) g.fillRect(MX(e[1]), MB - 4 * d - (e[0] - mlo + 1) * mrh, Math.max(1.4 * d, MX(e[2]) - MX(e[1])), mrh * 0.8);
  g.globalAlpha = 1;
  g.strokeStyle = PAL.ink2; g.lineWidth = 1.4 * d; rrect(g, MX(clamp(t0v, 0, dur)), MT + d, Math.max(4 * d, MX(clamp(t1v, 0, dur)) - MX(clamp(t0v, 0, dur))), miniH - 2 * d, 4 * d); g.stroke();
  g.fillStyle = PAL.emph; g.fillRect(MX(S.viewT) - d, MT - 3 * d, 2 * d, miniH + 6 * d);
}

// ------------------------------------------------------------------ stroik (SVG)
function buildGauge() {
  let t = '';
  for (let c = -50; c <= 50; c += 10) {
    const x = 150 + c * 2.8, major = c % 50 === 0 || c === 0;
    t += '<line class="tick' + (major ? ' major' : '') + '" x1="' + x + '" x2="' + x + '" y1="20" y2="' + (major ? 34 : 30) + '"/>';
    if (major) t += '<text x="' + x + '" y="46">' + (c > 0 ? '+' : '') + c + '</text>';
  }
  $('gTicks').innerHTML = t;
  $('zone').setAttribute('x', 150 - 5 * 2.8); $('zone').setAttribute('width', 10 * 2.8); $('zone').setAttribute('y', 18); $('zone').setAttribute('height', 18);
}
function setNeedle(c, cls) {
  $('mark').style.transform = 'translate(' + (150 + clamp(c, -50, 50) * 2.8) + 'px, 2px)';
  $('gauge').setAttribute('class', 'gauge' + (cls ? ' ' + cls : ''));
}
function buildStringRow() {
  const o = openMidis(), r = $('strRow'); r.innerHTML = '';
  for (let i = 0; i < 6; i++) { const s = document.createElement('span'); s.dataset.m = o[i]; s.textContent = NAMES[o[i] % 12]; s.title = 'struna ' + (6 - i) + ', ' + midiName(o[i]); r.appendChild(s); }
}

// ------------------------------------------------------------------ odświeżanie
const cache = {};
const setText = (id, v) => { if (cache[id] !== v) { cache[id] = v; $(id).textContent = v; } };
const setHTML = (id, v) => { if (cache[id] !== v) { cache[id] = v; $(id).innerHTML = v; } };
function viewFrame() {
  const X = E.x;
  if (S.mode === 'review' && S.rev) {
    const idx = X.gt_frame_at(S.viewT + S.win / 2);
    if (idx < 0) return null;
    if (idx === S.frameN && S.frame) return S.frame;
    S.frameN = idx; S.frame = J(X.gt_frame_json(idx)); return S.frame;
  }
  if (S.mode === 'mic' && performance.now() - S.lastPushAt < 1500) {
    const n = X.gt_frames();
    if (n === S.frameN && S.frame) return S.frame;
    S.frameN = n; S.frame = n ? J(X.gt_frame_json(-1)) : null; return S.frame;
  }
  return null;
}
function updatePanels(f) {
  const act = !!(f && !f.sil), notes = act ? f.n : [], st = notes.filter(n => n[4]), use = (st.length ? st : notes).slice().sort((a, b) => a[0] - b[0]);
  const root = act && f.ch ? rootPcOf(f.ch) : -1;
  let big = '—', dim = true, alt = '';
  if (act && f.ch) { big = f.ch; dim = false; alt = f.alt.length ? 'lub ' + f.alt.join(', ') : ''; }
  else if (use.length === 1) { big = midiName(use[0][0]); dim = false; }
  else if (use.length > 1) { big = '?'; }
  setText('chord', big); if (cache.dim !== dim) { cache.dim = dim; $('chord').classList.toggle('dim', dim); }
  setText('alt', alt);
  setHTML('chips', use.map(n => '<span class="chip' + (n[0] % 12 === root ? ' root' : '') + '">' + midiName(n[0]) + '</span>').join(''));
  const tu = act && f.tu, hit = $('strRow').children;
  if (tu) {
    const c = tu[3], a = Math.abs(c), midi = tu[0], si = openMidis().indexOf(midi);
    setText('tNote', midiName(midi)); setText('tHz', tu[1].toFixed(1) + ' Hz' + (si >= 0 ? ', struna ' + (6 - si) : ''));
    setText('tState', a < 5 ? 'w stroju' : (c < 0 ? 'za nisko ' : 'za wysoko +') + c.toFixed(0) + '¢');
    setNeedle(c, a < 5 ? 'ok' : a < 15 ? 'mid' : 'bad');
    for (const s of hit) s.classList.toggle('hit', +s.dataset.m === midi);
  } else {
    setText('tNote', '—'); setText('tHz', ' '); setText('tState', act && use.length > 1 ? 'kilka dźwięków naraz' : 'zagraj jedną strunę');
    setNeedle(0, ''); for (const s of hit) s.classList.remove('hit');
  }
  const key = JSON.stringify([act ? f.fg : [], root, act ? f.hz : null, S.tuning, $('neck').getBoundingClientRect().width, cache.themeV]);
  if (key !== cache.neckKey) { cache.neckKey = key; drawNeck(act ? f.fg : [], root, act ? f.hz : null); }
}
function renderChords(force) {
  const X = E.x, el = $('cstrip');
  let list = [], cur = -1;
  if (S.mode === 'review' && S.summary) { list = S.summary.chords; for (let i = 0; i < list.length; i++) if (list[i][0] <= S.viewT + 0.05) cur = i; }
  else if (S.mode === 'mic') { list = J(X.gt_summary_json()).chords.slice(-14); cur = list.length - 1; }
  const key = S.mode + '|' + list.length + '|' + cur + '|' + (list.length ? list[list.length - 1][1] : '');
  if (!force && key === S.logKey) return;
  const grew = S.logKey.split('|')[1] !== String(list.length);
  S.logKey = key;
  el.innerHTML = list.map((c, i) => '<button type="button" data-t="' + c[0] + '"' + (i === cur ? ' class="cur"' : '') + '>' + esc(c[1]) + '<small>' + fmtT(c[0]) + '</small></button>').join('');
  if (cur >= 0 && (S.playing || S.mode === 'mic' || grew)) { const n = el.children[cur]; if (n) el.scrollLeft = n.offsetLeft - el.clientWidth / 2; }
}
function updateButtons() {
  const live = S.mode === 'mic', busy = S.mode === 'busy', rev = S.mode === 'review';
  $('btnStop').disabled = !(live || S.playing);
  $('btnMic').disabled = busy; $('btnDemo').disabled = busy;
  $('file').disabled = busy; document.querySelector('label[for=file]').setAttribute('aria-disabled', String(busy));
  const data = !!(E.x && E.x.gt_frames() > 0) && (rev || live);
  for (const id of ['dlZip', 'dlWav', 'dlMid', 'dlTr', 'dlTab', 'dlChords', 'dlJson', 'cpTab']) $(id).disabled = !data;
  $('btnPlay').disabled = !rev;
}

// ------------------------------------------------------------------ pętla główna
let lastDraw = 0;
function loop(ts) {
  requestAnimationFrame(loop);
  if (!E.x || ts - lastDraw < 32) return;
  lastDraw = ts;
  try {
    if (S.playing) advancePlayhead();
    const f = viewFrame();
    updatePanels(f); drawAnalyzer(f);
    const live = S.mode === 'mic', X = E.x;
    if (!$('roll').hidden) drawTimeline(live || S.mode === 'review' ? J(X.gt_roll_json(live ? X.gt_time() - 12.5 : S.viewT - 6.2, live ? X.gt_time() + 0.5 : S.viewT + 6.2)) : null, live);
    if (S.mode === 'review') { setText('timeTxt', fmtT(S.viewT) + ' / ' + fmtT(S.rev.dur)); renderChords(false); }
    else if (live) { setText('timeTxt', fmtT(X.gt_time())); if (ts - S.logAt > 500) { S.logAt = ts; renderChords(false); } }
    else setText('timeTxt', '');
  } catch (e) { console.error(e); }
}

// ------------------------------------------------------------------ oś czasu: wskaźnik, podpowiedź, przewijanie
function tlPoint(e) { const r = $('roll').getBoundingClientRect(); return { x: e.clientX - r.left, y: e.clientY - r.top, w: r.width }; }
function seekFromPoint(p) {
  const tl = S.tl; if (!tl || !S.rev) return;
  const d = tl.d, y = p.y * d, x = p.x * d;
  if (tl.review && y >= tl.miniTop - 6 * d) seek((p.x - 6) / (p.w - 12) * S.rev.dur);
  else seek(tl.t0v + (x - tl.L) / (tl.Rr - tl.L) * tl.span);
}
function wireTimeline() {
  const c = $('roll'), tip = $('tip');
  c.addEventListener('pointerdown', e => { if (S.mode !== 'review') return; S.drag = true; try { c.setPointerCapture(e.pointerId); } catch (er) {} seekFromPoint(tlPoint(e)); });
  c.addEventListener('pointerup', () => { S.drag = false; });
  c.addEventListener('pointermove', e => {
    const p = tlPoint(e);
    if (S.drag && S.mode === 'review') { seekFromPoint(p); return; }
    const tl = S.tl; let hit = null;
    if (tl) for (let i = tl.rects.length - 1; i >= 0; i--) { const r = tl.rects[i]; if (p.x >= r.x1 - 2 && p.x <= r.x2 + 2 && p.y >= r.y1 - 2 && p.y <= r.y2 + 2) { hit = r.e; break; } }
    if (!hit) { tip.hidden = true; return; }
    tip.innerHTML = '<b>' + midiName(hit[0]) + '</b><span>' + fmtT(hit[1]) + ', ' + (hit[2] - hit[1]).toFixed(2) + ' s, siła ' + hit[3] + '</span>';
    tip.hidden = false;
    tip.style.left = clamp(p.x + 12, 0, c.getBoundingClientRect().width - tip.offsetWidth) + 'px'; tip.style.top = Math.max(0, p.y - tip.offsetHeight - 10) + 'px';
  });
  c.addEventListener('pointerleave', () => { tip.hidden = true; });
  c.addEventListener('keydown', e => {
    if (S.mode !== 'review') return;
    const step = e.shiftKey ? 10 : 2;
    if (e.key === 'ArrowLeft') { seek(S.viewT - step); e.preventDefault(); }
    else if (e.key === 'ArrowRight') { seek(S.viewT + step); e.preventDefault(); }
    else if (e.key === 'Home') { seek(0); e.preventDefault(); }
    else if (e.key === 'End') { seek(S.rev.dur); e.preventDefault(); }
  });
}

function wire() {
  $('btnMic').onclick = startMic;
  $('btnDemo').onclick = () => loadDemo(true);
  $('btnStop').onclick = async () => { if (S.mode === 'mic') await stopAll(); else pause(); };
  $('file').onchange = e => { if (e.target.files[0]) openFile(e.target.files[0]); e.target.value = ''; };
  $('btnPlay').onclick = togglePlay;
  $('pmOrig').onclick = () => setPlayMode('orig'); $('pmTr').onclick = () => setPlayMode('tr'); $('pmBoth').onclick = () => setPlayMode('both');
  $('vwChart').onclick = () => { S.view = 'chart'; applyView(); }; $('vwTable').onclick = () => { S.view = 'table'; applyView(); };
  $('btnSettings').onclick = () => { const s = $('settings'); s.hidden = !s.hidden; $('btnSettings').setAttribute('aria-expanded', String(!s.hidden)); };
  $('cstrip').addEventListener('click', e => { const b = e.target.closest('button[data-t]'); if (b && S.mode === 'review') seek(Math.max(0, +b.dataset.t - 0.1)); });
  window.addEventListener('keydown', e => {
    if (e.code === 'Space' && S.mode === 'review' && !/INPUT|SELECT|TEXTAREA|BUTTON|SUMMARY/.test((document.activeElement || {}).tagName || '')) { e.preventDefault(); togglePlay(); }
  });
  window.addEventListener('dragover', e => e.preventDefault());
  window.addEventListener('drop', e => { e.preventDefault(); const f = e.dataTransfer && e.dataTransfer.files[0]; if (f) openFile(f); });
  const themeChanged = () => { readPalette(); cache.neckKey = ''; cache.themeV = (cache.themeV || 0) + 1; };
  try { matchMedia('(prefers-color-scheme: dark)').addEventListener('change', themeChanged); } catch (e) {}
  new MutationObserver(themeChanged).observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
  wireTimeline();
}

async function main() {
  readPalette(); initSource(); buildGauge(); wire(); wireExports(); setReview(false);
  requestAnimationFrame(loop);
  try { await bootEngine(); }
  catch (e) {
    console.error(e);
    setStatus('silnik C++ się nie uruchomił', 'err'); showMicHint('Pobierz aplikację i otwórz ją z dysku.');
    return;
  }
  $('sub').textContent = 'silnik C++ w ' + (E.kind === 'WebAssembly' ? 'WebAssembly' : 'JavaScript');
  loadSettings(); buildStringRow(); updateButtons();
  if (IN_ARTIFACT) { showMicHint(micHelp()); $('btnMic').classList.remove('solid'); $('btnDemo').classList.add('solid'); }
  try { await loadDemo(false); } catch (e) { console.error(e); setStatus('gotowy'); }
  window.__gs = { S, E, J, seek, play, pause, analyze, loadDemo, doExport, renderTranscription };
}
main();
})();
