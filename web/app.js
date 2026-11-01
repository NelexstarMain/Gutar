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
const store = {
  get(k, d) { try { const v = localStorage.getItem('gs2_' + k); return v === null ? d : JSON.parse(v); } catch (e) { return d; } },
  set(k, v) { try { localStorage.setItem('gs2_' + k, JSON.stringify(v)); } catch (e) {} },
};
const IN_ARTIFACT = !!(window.claude && typeof window.claude.use === 'function');
const ALLOWED_EXT = ['gif', 'png', 'jpg', 'jpeg', 'webp', 'mp4', 'webm', 'mov', 'txt', 'json', 'md', 'docx', 'pptx', 'epub', 'csv', 'ttf', 'html', 'svg', 'pdf', 'xlsx', 'zip', 'fig'];

// ------------------------------------------------------------------ paleta (z tokenów CSS)
let PAL = {};
function readPalette() {
  const cs = getComputedStyle(document.documentElement), g = n => cs.getPropertyValue(n).trim();
  PAL = { tx: g('--tx'), mu: g('--mu'), dim: g('--dim'), line: g('--line'), line2: g('--line-2'), inset: g('--inset'), cpp: g('--cpp'),
    brass: g('--brass'), wood1: g('--wood-1'), wood2: g('--wood-2'), fret: g('--fret'), bone: g('--bone'), ok: g('--ok'), wa: g('--wa'), er: g('--er'),
    s: parseFloat(g('--pc-s')) || 70, l: parseFloat(g('--pc-l')) || 60, pcText: g('--pc-text'), panel: g('--panel-solid') };
}
const hueOf = pc => (pc * 30 + 200) % 360;
const pcCol = (pc, dl) => 'hsl(' + hueOf(pc) + ' ' + PAL.s + '% ' + (PAL.l + (dl || 0)) + '%)';

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
  rev: null, viewT: 0, playing: false, playMode: 'orig', srcs: [], playCtx0: 0, playT0: 0,
  lastPushAt: 0, pushMs: 0, anaMs: 0, win: 0.372, all: null, summary: null,
  frameN: -1, frame: null, tuning: 0, nz: { type: 'none', lvl: -40, pk: [0, 0, 0, 0, 0, 0, 0], ph: 0, scale: 1 },
  downloads: null, cons: [], consAt: 0, logAt: 0, logKey: '', dirty: true,
};

// ------------------------------------------------------------------ ustawienia
const SET_KEYS = ['tuning', 'win', 'a4', 'mains', 'gate', 'autoTune', 'autoGate', 'octaves', 'nzType', 'nzLvl'];
const readSet = () => ({
  tuning: +$('tuning').value || 0, win: +$('win').value, a4: +$('a4').value || 440, mains: +$('mains').value, gate: +$('gate').value,
  autoTune: $('autoTune').checked, autoGate: $('autoGate').checked, octaves: $('octaves').checked,
});
function pushCfg() {
  const s = readSet();
  E.x.gt_config(s.a4, s.win, s.gate, s.mains, s.autoTune ? 1 : 0, s.autoGate ? 1 : 0, s.tuning, s.octaves ? 1 : 0);
  S.tuning = s.tuning;
}
let reTimer = 0;
function onSettings(e) {
  $('gateV').textContent = $('gate').value + ' dB';
  $('nzV').textContent = $('nzLvl').value + ' dBFS';
  S.nz.type = $('nzType').value; S.nz.lvl = +$('nzLvl').value;
  for (const k of SET_KEYS) store.set(k, $(k).type === 'checkbox' ? $(k).checked : $(k).value);
  if (E.x) { pushCfg(); buildStringRow(); updateGateMark(); }
  $('snrNote').textContent = S.nz.type === 'none' ? '' : 'Szum jest dodawany tylko do sygnału trafiającego do analizy (nie słychać go w głośnikach).';
  S.dirty = true;
  if (e && S.mode === 'review' && S.rev) { clearTimeout(reTimer); reTimer = setTimeout(() => reanalyze(), 450); }
}
function loadSettings() {
  $('tuning').innerHTML = E.tunings.map((t, i) => '<option value="' + i + '">' + t.name + '</option>').join('');
  for (const k of SET_KEYS) {
    const v = store.get(k, null);
    if (v !== null) { if ($(k).type === 'checkbox') $(k).checked = !!v; else $(k).value = v; }
    $(k).addEventListener('input', onSettings);
  }
  onSettings();
}
function updateGateMark() { $('gateMark').style.left = clamp((+$('gate').value + 80) / 80, 0, 1) * 100 + '%'; }

// ------------------------------------------------------------------ szum testowy (jak w oryginale)
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

// ------------------------------------------------------------------ interfejs: status, toasty, postęp
function setStatus(t, cls) { const s = $('status'); s.textContent = t; s.className = 'pill' + (cls ? ' ' + cls : ''); }
let toastT = 0;
function toast(msg, ms) { const t = $('toast'); t.textContent = msg; t.classList.add('on'); clearTimeout(toastT); toastT = setTimeout(() => t.classList.remove('on'), ms || 3200); }
function progress(p) { const pr = $('prog'); pr.classList.toggle('on', p >= 0 && p < 1); $('progBar').style.width = Math.round(clamp(p, 0, 1) * 100) + '%'; }

// ------------------------------------------------------------------ audio: kontekst, wejście z mikrofonu
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
  } catch (e) { console.error(e); setStatus('błąd analizy: ' + e.message, 'err'); }
}
function showMicHint(html) { const h = $('micHint'); h.innerHTML = html; h.hidden = !html; }
async function startMic() {
  try {
    await stopAll(true);
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) throw Object.assign(new Error('brak dostępu do mikrofonu'), { name: 'NotSupportedError' });
    await ensureCtx(); pushCfg();
    const stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: false, noiseSuppression: false, autoGainControl: false, channelCount: 1 } });
    S.fs = S.ctx.sampleRate; E.x.gt_init(S.fs); S.pushMs = 0; S.frameN = -1; S.rev = null; S.all = null;
    S.stream = stream; await ensureNode();
    S.src = S.ctx.createMediaStreamSource(stream); S.src.connect(S.node);
    S.mode = 'mic'; setStatus('słucham · ' + Math.round(S.fs / 1000) + ' kHz', 'on');
    showMicHint('');
    showTransport(false); updateButtons(); S.dirty = true;
  } catch (e) {
    stopCapture(); S.mode = S.rev ? 'review' : 'idle'; updateButtons();
    const denied = e.name === 'NotAllowedError' || e.name === 'SecurityError';
    setStatus(denied ? 'mikrofon zablokowany' : 'błąd: ' + e.message, 'err');
    showMicHint(micHelp());
  }
}
function micHelp() {
  return IN_ARTIFACT
    ? '<b>Mikrofon nie działa w artefakcie</b>, bo platforma blokuje urządzenia. Użyj <b>Wgraj plik audio</b> albo <b>Demo</b>. Żeby grać na żywo, pobierz aplikację przyciskiem <b>Aplikacja (.html)</b> niżej i otwórz ją z dysku. To jeden plik z tym samym silnikiem C++ i działa offline.'
    : 'Przeglądarka nie dała dostępu do mikrofonu. Sprawdź zgodę w pasku adresu. Mikrofon wymaga HTTPS albo pliku otwartego z dysku. Możesz też użyć <b>Wgraj plik audio</b>.';
}
function stopCapture() {
  try { if (S.stream) S.stream.getTracks().forEach(t => t.stop()); } catch (e) {}
  try { if (S.src) S.src.disconnect(); } catch (e) {}
  S.stream = S.src = null;
}

// ------------------------------------------------------------------ analiza całego nagrania w C++
async function analyze(samples, fs, label) {
  stopCapture(); stopSources();
  S.mode = 'busy'; updateButtons(); showTransport(false);
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
  showTransport(true); updateButtons();
  const s = S.summary;
  setStatus((S.label || 'nagranie').slice(0, 26) + ' · ' + S.rev.dur.toFixed(1) + ' s · ' + s.notes + ' nut', 'on');
  $('scrub').value = Math.round(S.viewT / S.rev.dur * 1000);
  S.dirty = true; renderLog(true);
}
async function reanalyze() {
  if (!S.rev || S.mode === 'busy') return;
  const keep = S.viewT, r = S.rev;
  S.viewT = keep;
  await analyze(r.samples, r.fs, r.label);
}
async function finalizeLive() {
  const X = E.x;
  X.gt_finish();
  const n = X.gt_rec_len(), fs = X.gt_rec_rate();
  if (n < fs * 0.6) { S.mode = 'idle'; setStatus('za krótkie nagranie', ''); updateButtons(); return; }
  const pcm = new Int16Array(E.mem.buffer, X.gt_rec_ptr(), n), samples = new Float32Array(n);
  for (let i = 0; i < n; i++) samples[i] = pcm[i] / 32768;
  S.viewT = 0;
  await analyze(samples, fs, 'nagranie z mikrofonu');
}
async function stopAll(silent) {
  const wasLive = S.mode === 'mic';
  stopSources(); stopCapture();
  if (wasLive) { S.mode = 'busy'; await finalizeLive(); return; }
  if (S.mode !== 'review') { S.mode = S.rev ? 'review' : 'idle'; if (!silent) setStatus('wyłączony', ''); }
  updateButtons();
}

async function loadDemo(autoplay) {
  const X = E.x, fs = 44100;
  await stopAll(true);
  const n = X.gt_demo_render(fs), samples = f32(X.gt_synth_ptr(), n).slice();
  S.viewT = autoplay ? 0 : 3.7;
  await analyze(samples, fs, 'demo: Am C G E D Em F Am7');
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
  } catch (e) { S.mode = S.rev ? 'review' : 'idle'; updateButtons(); progress(1); setStatus('nie mogę odczytać pliku', 'err'); toast('Nie udało się wczytać pliku: ' + (e && e.message ? e.message : 'nieobsługiwany format')); }
}

// ------------------------------------------------------------------ odtwarzanie całości
function revBuffer() {
  const r = S.rev;
  if (!r.buf) { r.buf = S.ctx.createBuffer(1, r.samples.length, r.fs); r.buf.copyToChannel(r.samples, 0); }
  return r.buf;
}
async function renderTranscription() {
  await ensureCtx();
  const X = E.x;
  const prevStatus = $('status').textContent;
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
  setStatus(prevStatus, 'on');
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
async function togglePlay() {
  if (S.mode !== 'review') return;
  if (S.playing) pause(); else await play(S.viewT >= S.rev.dur - 0.05 ? 0 : S.viewT);
}
function seek(t) {
  if (!S.rev) return;
  S.viewT = clamp(t, 0, S.rev.dur); S.dirty = true;
  $('scrub').value = Math.round(S.viewT / S.rev.dur * 1000);
  if (S.playing) play(S.viewT);
}
function setPlayUi() {
  $('playTxt').textContent = S.playing ? 'Pauza' : 'Odtwórz';
  $('btnPlay').querySelector('svg').innerHTML = S.playing ? '<path d="M7 5h4v14H7zM13 5h4v14h-4z"/>' : '<path d="M7 5v14l12-7z"/>';
}
function setPlayMode(m) {
  S.playMode = m;
  $('pmOrig').setAttribute('aria-pressed', String(m === 'orig')); $('pmTr').setAttribute('aria-pressed', String(m === 'tr')); $('pmBoth').setAttribute('aria-pressed', String(m === 'both'));
  if (S.playing) play(S.viewT);
}
function advancePlayhead() {
  if (!S.playing) return;
  const t = S.playT0 + Math.max(0, S.ctx.currentTime - S.playCtx0);
  if (t >= S.rev.dur) { S.viewT = S.rev.dur; stopSources(); updateButtons(); }
  else S.viewT = t;
  $('scrub').value = Math.round(S.viewT / S.rev.dur * 1000);
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
        toast('Artefakt zapisuje tylko wybrane formaty, więc plik ' + name + ' jest w archiwum ZIP. W pobranej aplikacji zapisze się bez pakowania.', 5200);
        return;
      }
      toast('Zapisano ' + name);
    } catch (e) { toast(e && e.code === 'declined' ? 'Anulowano zapis.' : 'Nie udało się zapisać: ' + (e && e.message ? e.message : 'błąd')); }
    return;
  }
  const url = URL.createObjectURL(new Blob([data], { type: mime || 'application/octet-stream' }));
  const a = document.createElement('a'); a.href = url; a.download = name; document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 4000);
  toast('Pobrano ' + name);
}
function haveData() { return !!(E.x && E.x.gt_frames() > 0 && (S.mode === 'review' || S.mode === 'mic')); }
async function doExport(kind, name, mime) {
  if (!haveData()) { toast('Najpierw zagraj, wgraj plik albo uruchom demo.'); return; }
  if (kind === 6 || kind === 5) { if (S.rev && !S.rev.trReady && E.x.gt_frames() > 0) { await ensureCtx(); const ok = await renderTranscription(); if (!ok && kind === 6) return; } }
  const bytes = readBin(kind);
  if (!bytes.length) { toast('Brak danych do zapisania.'); return; }
  await saveFile(name, bytes, mime);
}
async function copyText(t) {
  try { await navigator.clipboard.writeText(t); toast('Skopiowano do schowka'); }
  catch (e) {
    const a = document.createElement('textarea'); a.value = t; a.style.position = 'fixed'; a.style.opacity = '0'; document.body.appendChild(a); a.select();
    try { document.execCommand('copy'); toast('Skopiowano do schowka'); } catch (er) { toast('Schowek jest zablokowany. Pobierz tabulaturę jako plik.'); } a.remove();
  }
}
async function downloadApp() {
  try {
    const r = await fetch('gitara-sluchacz.html'); if (!r.ok) throw new Error('HTTP ' + r.status);
    await saveFile('gitara-sluchacz.html', await r.text(), 'text/html');
  } catch (e) { toast('Nie mogę pobrać pliku aplikacji z tej strony. Użyj menu artefaktu albo wersji z repozytorium.', 5200); }
}
function wireExports() {
  $('dlZip').onclick = () => doExport(5, 'gitara-sesja.zip', 'application/zip');
  $('dlWav').onclick = () => doExport(1, 'gitara-nagranie.wav', 'audio/wav');
  $('dlMid').onclick = () => doExport(0, 'gitara.mid', 'audio/midi');
  $('dlTr').onclick = () => doExport(6, 'gitara-transkrypcja.wav', 'audio/wav');
  $('dlTab').onclick = () => doExport(2, 'gitara-tabulatura.txt', 'text/plain');
  $('dlChords').onclick = () => doExport(3, 'gitara-akordy.txt', 'text/plain');
  $('dlJson').onclick = () => doExport(4, 'gitara-sesja.json', 'application/json');
  $('dlSrc').onclick = () => saveFile('gitara-kod-cpp.zip', zipFiles(SRC.files.map(f => ({ name: 'src/' + f.name, data: f.code }))), 'application/zip');
  $('dlApp').onclick = downloadApp;
  $('cpTab').onclick = () => { if (!haveData()) { toast('Najpierw zagraj, wgraj plik albo uruchom demo.'); return; } copyText(new TextDecoder().decode(readBin(2))); };
  if (IN_ARTIFACT) {
    $('dlApp').hidden = false;
    window.claude.use('downloads').then(d => { S.downloads = d; $('dlNote').textContent = d ? 'zapis przez okno potwierdzenia' : ''; if (!d) $('dlApp').hidden = true; }).catch(() => { $('dlApp').hidden = true; });
  }
}

// ------------------------------------------------------------------ kod źródłowy (podgląd + tło)
let SRC = { files: [] };
const KW = new Set('alignas auto bool break case catch char class const constexpr continue default delete do double else enum explicit extern false float for if inline int long namespace new nullptr operator private public return short signed sizeof static struct switch template this true typedef typename union unsigned using virtual void volatile while'.split(' '));
const TY = new Set('int8_t int16_t int32_t int64_t uint8_t uint16_t uint32_t uint64_t size_t string vector map pair FFT Spectrum Engine MultiPitch NoteDet Peak Rng'.split(' '));
const esc = s => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
function highlight(code, cls) {
  const re = /(\/\/[^\n]*|\/\*[\s\S]*?\*\/)|("(?:\\.|[^"\\\n])*")|(^[ \t]*#[^\n]*)|\b(0x[0-9a-fA-F]+|\d+\.?\d*(?:[eE][+-]?\d+)?[fFuUlL]*)\b|\b([A-Za-z_]\w*)\b/gm;
  let out = '', last = 0, m;
  while ((m = re.exec(code))) {
    out += esc(code.slice(last, m.index)); last = re.lastIndex;
    if (m[1]) out += '<span class="' + cls.c + '">' + esc(m[1]) + '</span>';
    else if (m[2]) out += '<span class="' + cls.s + '">' + esc(m[2]) + '</span>';
    else if (m[3]) out += '<span class="' + cls.p + '">' + esc(m[3]) + '</span>';
    else if (m[4]) out += '<span class="' + cls.n + '">' + m[4] + '</span>';
    else if (KW.has(m[5])) out += '<span class="' + cls.k + '">' + m[5] + '</span>';
    else if (TY.has(m[5])) out += '<span class="' + cls.t + '">' + m[5] + '</span>';
    else out += m[5];
  }
  return out + esc(code.slice(last));
}
function showSource(i) {
  const f = SRC.files[i]; if (!f) return;
  const html = highlight(f.code, { c: 'tk-c', s: 'tk-s', p: 'tk-p', n: 'tk-n', k: 'tk-k', t: 'tk-t' });
  $('srcView').firstElementChild.innerHTML = html.split('\n').map(l => '<span class="l">' + l + '</span>').join('');
  [...$('srcTabs').children].forEach((b, k) => b.setAttribute('aria-selected', String(k === i)));
  $('srcInfo').textContent = f.name + ' · ' + f.code.split('\n').length + ' linii · ' + (f.code.length / 1024).toFixed(1) + ' KB';
}
function initSource() {
  try { SRC = JSON.parse($('srcData').textContent); } catch (e) { SRC = { files: [] }; }
  const tabs = $('srcTabs');
  tabs.innerHTML = '';
  SRC.files.forEach((f, i) => { const b = document.createElement('button'); b.type = 'button'; b.setAttribute('role', 'tab'); b.textContent = f.name; b.onclick = () => showSource(i); tabs.appendChild(b); });
  if (SRC.files.length) showSource(Math.max(0, SRC.files.findIndex(f => f.name === 'gt_engine.hpp')));
  // tło: prawdziwy kod silnika, podwojony dla płynnego przewijania
  const eng = SRC.files.find(f => f.name === 'gt_engine.hpp') || SRC.files[0];
  if (eng) {
    const lines = eng.code.split('\n').slice(0, 150).join('\n');
    const h = highlight(lines, { c: 'c', s: 'k', p: 'c', n: 'k', k: 'k', t: 'k' });
    $('codeBg').innerHTML = h + '\n\n' + h;
  }
}

// ------------------------------------------------------------------ rysowanie
function fit(c) {
  if (!c.dataset.h) { c.dataset.h = c.getAttribute('height'); c.style.height = c.dataset.h + 'px'; }
  const r = c.getBoundingClientRect(), d = Math.min(2, window.devicePixelRatio || 1);
  const w = Math.max(10, Math.round((r.width || 300) * d)), h = Math.round(+c.dataset.h * d);
  if (c.width !== w || c.height !== h) { c.width = w; c.height = h; }
  return { g: c.getContext('2d'), w, h, d };
}
function rrect(g, x, y, w, h, r) { g.beginPath(); g.moveTo(x + r, y); g.arcTo(x + w, y, x + w, y + h, r); g.arcTo(x + w, y + h, x, y + h, r); g.arcTo(x, y + h, x, y, r); g.arcTo(x, y, x + w, y, r); g.closePath(); }
const openMidis = () => (E.tunings[S.tuning] || { open: [40, 45, 50, 55, 59, 64] }).open;
const rootPcOf = name => { if (!name) return -1; const i = NAMES.indexOf(name.slice(0, 2)); if (i >= 0 && name[1] === '#') return i; return NAMES.indexOf(name[0]); };

function drawNeck(fg, rootPc) {
  const { g, w, h, d } = fit($('neck')); g.clearRect(0, 0, w, h);
  const NF = 17, L = 66 * d, R = w - 14 * d, T = 30 * d, B = h - 34 * d;
  const fx = n => L + (R - L) * (1 - Math.pow(2, -n / 12)) / (1 - Math.pow(2, -NF / 12)), sy = i => T + (B - T) * (5 - i) / 5;
  const open = openMidis();
  const grd = g.createLinearGradient(0, T - 14 * d, 0, B + 14 * d); grd.addColorStop(0, PAL.wood2); grd.addColorStop(1, PAL.wood1);
  g.fillStyle = grd; rrect(g, L, T - 14 * d, R - L, B - T + 28 * d, 6 * d); g.fill();
  g.globalAlpha = 0.07; g.strokeStyle = '#000'; g.lineWidth = d;
  for (let i = 0; i < 26; i++) { const y = T - 14 * d + (B - T + 28 * d) * ((i * 0.618) % 1); g.beginPath(); g.moveTo(L, y); g.lineTo(R, y + ((i % 3) - 1) * 2 * d); g.stroke(); }
  g.globalAlpha = 1;
  // wstawki
  g.fillStyle = 'rgba(233,226,208,.28)';
  const my = (T + B) / 2;
  for (const n of [3, 5, 7, 9, 15, 17]) { g.beginPath(); g.arc((fx(n - 1) + fx(n)) / 2, my, 5 * d, 0, 7); g.fill(); }
  for (const dy of [-1.5, 1.5]) { g.beginPath(); g.arc((fx(11) + fx(12)) / 2, my + dy * (B - T) / 5 * 0.9, 5 * d, 0, 7); g.fill(); }
  // progi
  for (let n = 1; n <= NF; n++) {
    const x = fx(n), fg2 = g.createLinearGradient(x - 1.5 * d, 0, x + 1.5 * d, 0);
    fg2.addColorStop(0, 'rgba(0,0,0,.35)'); fg2.addColorStop(0.5, PAL.fret); fg2.addColorStop(1, 'rgba(0,0,0,.25)');
    g.fillStyle = fg2; g.fillRect(x - 1.6 * d, T - 14 * d, 3.2 * d, B - T + 28 * d);
  }
  g.fillStyle = PAL.bone; g.fillRect(L - 6 * d, T - 16 * d, 7 * d, B - T + 32 * d);
  // struny
  const gauge = [2.7, 2.2, 1.8, 1.3, 1.0, 0.8];
  g.font = '600 ' + 12 * d + 'px JetBrains Mono, monospace'; g.textAlign = 'center'; g.textBaseline = 'middle';
  for (let i = 0; i < 6; i++) {
    const y = sy(i), wound = i < 3;
    g.strokeStyle = 'rgba(0,0,0,.35)'; g.lineWidth = (gauge[i] + 1.2) * d; g.beginPath(); g.moveTo(L - 4 * d, y + 1.5 * d); g.lineTo(R, y + 1.5 * d); g.stroke();
    g.strokeStyle = wound ? '#c9a45a' : '#d8dee7'; g.lineWidth = gauge[i] * d; g.beginPath(); g.moveTo(L - 4 * d, y); g.lineTo(R, y); g.stroke();
    g.fillStyle = PAL.mu; g.fillText(NAMES[open[i] % 12], 12 * d, y);
  }
  g.fillStyle = PAL.mu; g.font = '500 ' + 11 * d + 'px JetBrains Mono, monospace';
  for (const n of [3, 5, 7, 9, 12, 15]) g.fillText(String(n), (fx(n - 1) + fx(n)) / 2, B + 24 * d);
  // dźwięki
  const r = Math.min(13 * d, (B - T) / 5 * 0.44);
  g.font = '700 ' + 11.5 * d + 'px JetBrains Mono, monospace';
  for (const p of fg) {
    const midi = p[0], s = p[1] - 1, fret = p[2], pc = midi % 12, y = sy(s);
    const x = fret === 0 ? L - 24 * d : (fx(fret - 1) + fx(Math.min(fret, NF))) / 2;
    g.save(); g.shadowColor = pcCol(pc); g.shadowBlur = 14 * d;
    g.beginPath(); g.arc(x, y, r, 0, 7);
    if (fret === 0) { g.lineWidth = 2.6 * d; g.strokeStyle = pcCol(pc); g.stroke(); g.fillStyle = PAL.panel; g.fill(); g.restore(); g.fillStyle = pcCol(pc); }
    else { g.fillStyle = pcCol(pc); g.fill(); g.restore(); if (pc === rootPc) { g.lineWidth = 2.6 * d; g.strokeStyle = '#fff'; g.beginPath(); g.arc(x, y, r, 0, 7); g.stroke(); } g.fillStyle = PAL.pcText; }
    g.fillText(NAMES[pc], x, y + 0.5 * d);
  }
}

function drawRoll(R, live) {
  const { g, w, h, d } = fit($('roll')); g.clearRect(0, 0, w, h);
  const span = 12, frac = live ? 0.96 : 0.5;
  const tNow = live ? (R ? R.now : 0) : S.viewT, t0v = tNow - span * frac, t1v = t0v + span;
  const open = openMidis();
  let lo = Math.min(40, open[0]), hi = 76;
  const evs = R ? R.ev : [];
  for (const e of evs) { lo = Math.min(lo, e[0] - 1); hi = Math.max(hi, e[0] + 1); }
  lo = Math.max(36, lo); hi = Math.min(90, hi);
  const rows = hi - lo + 1, L = 40 * d, T = 24 * d, B = h - 6 * d, rh = (B - T) / rows;
  const X = t => L + (t - t0v) / span * (w - L - 4 * d), Y = m => B - (m - lo + 1) * rh;
  g.font = '500 ' + 11 * d + 'px JetBrains Mono, monospace'; g.textAlign = 'left'; g.textBaseline = 'middle';
  for (let m = lo; m <= hi; m++) {
    const isOpen = open.indexOf(m) >= 0, c = m % 12 === 0, black = [1, 3, 6, 8, 10].indexOf(m % 12) >= 0;
    if (black) { g.fillStyle = 'rgba(128,150,180,.06)'; g.fillRect(L, Y(m), w - L, rh); }
    const nearOpen = open.some(o => Math.abs(o - m) === 1);
    if (isOpen || (c && !nearOpen)) { g.strokeStyle = PAL.line; g.lineWidth = d; g.beginPath(); g.moveTo(L, Y(m) + rh / 2); g.lineTo(w, Y(m) + rh / 2); g.stroke(); g.fillStyle = isOpen ? PAL.mu : PAL.dim; g.fillText(midiName(m), 4 * d, Y(m) + rh / 2); }
  }
  if (R) {
    g.lineWidth = d; g.strokeStyle = PAL.line2;
    for (const o of R.on) if (o >= t0v && o <= t1v) { g.beginPath(); g.moveTo(X(o), T - 4 * d); g.lineTo(X(o), B); g.stroke(); }
    for (const e of evs) {
      const t0 = e[1], t1 = Math.min(e[2], t1v), pc = e[0] % 12, y = Y(e[0]);
      const x1 = X(Math.max(t0, t0v)), x2 = Math.max(x1 + 2 * d, X(t1));
      g.globalAlpha = 0.55 + 0.45 * clamp(e[3] / 110, 0.2, 1); g.fillStyle = pcCol(pc, e[4] ? 8 : 0);
      rrect(g, x1, y + 1, x2 - x1, Math.max(2 * d, rh - 2 * d), Math.min(3 * d, rh / 2)); g.fill(); g.globalAlpha = 1;
      if (x2 - x1 > 26 * d && rh > 9 * d) { g.fillStyle = PAL.pcText; g.fillText(NAMES[pc], x1 + 4 * d, y + rh / 2 + 0.5 * d); }
    }
    g.fillStyle = PAL.tx; g.font = '700 ' + 12.5 * d + 'px Bricolage Grotesque, system-ui, sans-serif'; g.textBaseline = 'alphabetic';
    let lastX = -1e9;
    for (const c of R.ch) { const x = X(c[0]); if (x - lastX > 34 * d) { g.fillText(c[1], x + 3 * d, 16 * d); lastX = x; } }
  }
  g.strokeStyle = PAL.cpp; g.lineWidth = 1.8 * d; g.beginPath(); g.moveTo(X(tNow), T - 6 * d); g.lineTo(X(tNow), B); g.stroke();
  g.fillStyle = PAL.cpp; g.beginPath(); g.moveTo(X(tNow) - 5 * d, T - 8 * d); g.lineTo(X(tNow) + 5 * d, T - 8 * d); g.lineTo(X(tNow), T - 1 * d); g.fill();
}

function drawOverview() {
  const c = $('ov'); if (c.hidden || !S.all || !S.rev) return;
  const { g, w, h, d } = fit(c); g.clearRect(0, 0, w, h);
  const dur = S.rev.dur, L = 6 * d, Rr = w - 6 * d, X = t => L + t / dur * (Rr - L);
  let lo = 100, hi = 0;
  for (const e of S.all.ev) { lo = Math.min(lo, e[0]); hi = Math.max(hi, e[0]); }
  if (hi < lo) { lo = 40; hi = 76; }
  const T = 16 * d, B = h - 4 * d, rh = Math.max(2 * d, (B - T) / (hi - lo + 2));
  for (const e of S.all.ev) {
    g.fillStyle = pcCol(e[0] % 12); g.globalAlpha = 0.85;
    g.fillRect(X(e[1]), B - (e[0] - lo + 1) * rh, Math.max(1.5 * d, X(e[2]) - X(e[1])), rh * 0.8);
  }
  g.globalAlpha = 1; g.fillStyle = PAL.mu; g.font = '600 ' + 10 * d + 'px JetBrains Mono, monospace'; g.textBaseline = 'top';
  let lastX = -1e9;
  for (const c2 of S.all.ch) { const x = X(c2[0]); g.fillStyle = PAL.line2; g.fillRect(x, T - 3 * d, d, B - T + 3 * d); if (x - lastX > 30 * d) { g.fillStyle = PAL.mu; g.fillText(c2[1], x + 3 * d, 1 * d); lastX = x; } }
  const px = X(S.viewT); g.fillStyle = PAL.cpp; g.fillRect(px - d, 0, 2 * d, h);
}

function drawSpec(f) {
  const { g, w, h, d } = fit($('spec')); g.clearRect(0, 0, w, h);
  const fmin = 60, fmax = 5000, L = 8 * d, R = w - 8 * d, T = 12 * d, B = h - 22 * d, lg = Math.log(fmax / fmin);
  const X = fr => L + Math.log(fr / fmin) / lg * (R - L);
  g.font = '500 ' + 11 * d + 'px JetBrains Mono, monospace'; g.textAlign = 'center'; g.textBaseline = 'alphabetic';
  for (const fr of [100, 200, 500, 1000, 2000, 4000]) { const x = X(fr); g.strokeStyle = PAL.line; g.lineWidth = d; g.beginPath(); g.moveTo(x, T); g.lineTo(x, B); g.stroke(); g.fillStyle = PAL.dim; g.fillText(fr >= 1000 ? fr / 1000 + 'k' : String(fr), x, h - 6 * d); }
  g.strokeStyle = PAL.line2; g.beginPath(); g.moveTo(L, B); g.lineTo(R, B); g.stroke();
  if (!f || f.sil) return;
  const own = p => { for (const n of f.n) for (let k = 1; k <= 14; k++) { const fh = k * n[1] * Math.sqrt(1 + 2.5e-4 * k * k); if (Math.abs(1200 * Math.log2(p[0] / fh)) < 35) return n; } return null; };
  for (const p of f.pk) {
    if (p[0] < fmin || p[0] > fmax) continue;
    const db = 20 * Math.log10(p[1] + 1e-9), y = B - clamp((db + 90) / 80, 0, 1) * (B - T), n = own(p), x = X(p[0]);
    const col = n ? pcCol(n[0] % 12) : PAL.dim;
    g.strokeStyle = col; g.lineWidth = 2 * d; g.beginPath(); g.moveTo(x, B); g.lineTo(x, y); g.stroke();
    g.fillStyle = col; g.beginPath(); g.arc(x, y, 3 * d, 0, 7); g.fill();
  }
  g.font = '700 ' + 12 * d + 'px JetBrains Mono, monospace';
  for (const n of f.n) {
    const x = X(n[1]); g.fillStyle = pcCol(n[0] % 12); g.fillText(midiName(n[0]), x, T + 6 * d + (n[0] % 3) * 12 * d);
    for (let k = 2; k <= 12; k++) { const xx = X(k * n[1] * Math.sqrt(1 + 2.5e-4 * k * k)); if (xx > R) break; g.fillRect(xx - d, B - 5 * d, 2 * d, 5 * d); }
  }
}

// ------------------------------------------------------------------ stroik (SVG)
function buildGauge() {
  const cx = 150, cy = 150, ang = c => (c / 50 * 55 - 90) * Math.PI / 180;
  const pt = (c, r) => [cx + r * Math.cos(ang(c)), cy + r * Math.sin(ang(c))];
  const arc = (c0, c1, r) => { const a = pt(c0, r), b = pt(c1, r); return 'M' + a[0].toFixed(1) + ' ' + a[1].toFixed(1) + ' A' + r + ' ' + r + ' 0 0 1 ' + b[0].toFixed(1) + ' ' + b[1].toFixed(1); };
  $('gArc').setAttribute('d', arc(-50, 50, 118)); $('zoneArc').setAttribute('d', arc(-5, 5, 112));
  let t = '';
  for (let c = -50; c <= 50; c += 5) {
    const major = c % 25 === 0, a = pt(c, 118), b = pt(c, major ? 104 : 110);
    t += '<line class="tick' + (major ? ' major' : '') + '" x1="' + a[0].toFixed(1) + '" y1="' + a[1].toFixed(1) + '" x2="' + b[0].toFixed(1) + '" y2="' + b[1].toFixed(1) + '"/>';
    if (major) { const l = pt(c, 92); t += '<text x="' + l[0].toFixed(1) + '" y="' + (l[1] + 3).toFixed(1) + '">' + (c > 0 ? '+' : '') + c + '</text>'; }
  }
  $('gTicks').innerHTML = t;
}
function setNeedle(c, cls) {
  $('needle').style.transform = 'rotate(' + (clamp(c, -50, 50) / 50 * 55) + 'deg)';
  $('gauge').setAttribute('class', 'gauge' + (cls ? ' ' + cls : ''));
}
function buildStringRow() {
  const o = openMidis(), r = $('strRow'); r.innerHTML = '';
  for (let i = 5; i >= 0; i--) { const s = document.createElement('span'); s.dataset.m = o[i]; s.textContent = NAMES[o[i] % 12]; s.title = 'struna ' + (6 - i) + ' · ' + midiName(o[i]); r.appendChild(s); }
}

// ------------------------------------------------------------------ odświeżanie paneli
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
  let big = '—', dim = true, alt = '';
  if (act && f.ch) { big = f.ch; dim = false; alt = f.alt.length ? 'lub: ' + f.alt.join(', ') : ''; }
  else if (use.length === 1) { big = midiName(use[0][0]); dim = false; alt = 'pojedynczy dźwięk'; }
  else if (use.length > 1) { big = '?'; alt = 'brak pasującego akordu'; }
  setText('chord', big); if (cache.dim !== dim) { cache.dim = dim; $('chord').classList.toggle('dim', dim); }
  const live = !dim && (S.mode === 'mic' || S.playing); if (cache.live !== live) { cache.live = live; $('chord').classList.toggle('live', live); }
  setText('alt', alt);
  setHTML('chips', use.map(n => '<span class="chip" style="background:' + pcCol(n[0] % 12) + '">' + midiName(n[0]) + '</span>').join(''));
  const lv = f ? f.lv : -120; setText('lvlTxt', f ? lv.toFixed(0) + ' dB' : '-- dB');
  const w = clamp((lv + 80) / 80, 0, 1) * 100; if (cache.lvw !== Math.round(w)) { cache.lvw = Math.round(w); $('lvl').style.width = w + '%'; }
  // stroik
  const tu = act && f.tu;
  const hit = $('strRow').children;
  if (tu) {
    const c = tu[3], a = Math.abs(c), midi = tu[0], o = openMidis(), si = o.indexOf(midi);
    setText('tNote', midiName(midi));
    setText('tInfo', tu[1].toFixed(1) + ' Hz · ' + (c > 0 ? '+' : '') + c.toFixed(1) + '¢' + (si >= 0 ? ' · struna ' + (6 - si) : ''));
    setNeedle(c, a < 5 ? 'ok' : a < 15 ? 'mid' : 'bad');
    for (const s of hit) s.classList.toggle('hit', +s.dataset.m === midi);
  } else {
    setText('tNote', '—'); setText('tInfo', act && use.length > 1 ? 'kilka dźwięków naraz, zagraj jedną strunę' : 'zagraj pojedynczy dźwięk');
    setNeedle(0, ''); for (const s of hit) s.classList.remove('hit');
  }
  // gryf
  const fg = act ? f.fg : [], root = act && f.ch ? rootPcOf(f.ch) : -1;
  const key = JSON.stringify(fg) + '|' + root + '|' + S.tuning + '|' + $('neck').getBoundingClientRect().width + '|' + S.dirty;
  if (key !== cache.neckKey || S.dirtyNeck) { cache.neckKey = key; S.dirtyNeck = false; drawNeck(fg, root); }
}
function consoleTick(f, now) {
  if (now - S.consAt < 260) return;
  S.consAt = now;
  const X = E.x, nF = X.gt_frames(), pk = (cls, t) => '<span class="' + cls + '">' + t + '</span>';
  if (f && nF) {
    const names = f.n.map(n => midiName(n[0])).join(' ');
    const line = pk('k', 'frame') + ' #' + String(f.i).padStart(5, ' ') + '  t=' + f.t.toFixed(2).padStart(6, ' ') + 's  lvl=' + f.lv.toFixed(1).padStart(6, ' ') + 'dB  peaks=' + String(f.pk.length).padStart(2, ' ') +
      '  notes=[' + pk('n', names) + ']  chord=' + pk('g', f.ch || '-');
    if (S.cons[S.cons.length - 1] !== line) { S.cons.push(line); if (S.cons.length > 6) S.cons.shift(); }
  }
  let ms = 0, rtf = 0;
  if (S.mode === 'mic' && nF) { ms = S.pushMs / nF; }
  else if (S.mode === 'review' && nF) { ms = S.anaMs / nF; rtf = S.anaMs / 1000 / Math.max(0.1, S.rev.dur); }
  $('console').innerHTML = S.cons.join('\n') || pk('k', '// czekam na dźwięk…');
  setText('stFrame', nF ? ms.toFixed(2) + ' ms' + (rtf ? ' · ' + rtf.toFixed(3) + '×' : '') : '—');
  setText('stTune', (X.gt_frames() && S.summary ? S.summary.tune : 0).toFixed(1) + ' ¢');
  setText('stGate', S.summary ? S.summary.gate.toFixed(0) + ' dB' : $('gate').value + ' dB');
}

function renderLog(force) {
  const X = E.x, el = $('log');
  let list, cur = -1;
  if (S.mode === 'review') { S.summary = S.summary || J(X.gt_summary_json()); list = S.summary.chords; for (let i = 0; i < list.length; i++) if (list[i][0] <= S.viewT + 0.05) cur = i; }
  else if (S.mode === 'mic') { list = J(X.gt_summary_json()).chords; cur = list.length - 1; }
  else list = [];
  const key = S.mode + '|' + list.length + '|' + cur + '|' + (list.length ? list[list.length - 1][1] : '');
  if (!force && key === S.logKey) return;
  S.logKey = key;
  if (!list.length) { el.innerHTML = '<div class="empty">Tu pojawią się rozpoznane akordy.</div>'; return; }
  const seekable = S.mode === 'review';
  const rows = list.map((c, i) => '<div class="' + (seekable ? 'seek ' : '') + (i === cur ? 'cur' : '') + '" data-t="' + c[0] + '"><b>' + fmtT(c[0]) + '</b><span>' + esc(c[1]) + '</span></div>');
  el.innerHTML = (S.mode === 'mic' ? rows.slice(-200).reverse() : rows).join('');
  if (seekable && cur >= 0 && S.playing) { const n = el.children[cur]; if (n) el.scrollTop = n.offsetTop - el.clientHeight / 2; }
}

function updateButtons() {
  const live = S.mode === 'mic', busy = S.mode === 'busy', rev = S.mode === 'review';
  $('btnStop').disabled = !(live || S.playing);
  $('btnMic').disabled = busy; $('btnDemo').disabled = busy;
  $('file').disabled = busy;
  const data = !!(E.x && E.x.gt_frames() > 0) && (rev || live);
  for (const id of ['dlZip', 'dlWav', 'dlMid', 'dlTr', 'dlTab', 'dlChords', 'dlJson', 'cpTab']) $(id).disabled = !data;
  $('btnPlay').disabled = !rev;
}
function showTransport(on) {
  $('transport').hidden = !on; $('ov').hidden = !on; $('ovHint').hidden = !on;
  $('rollNote').textContent = on ? 'okno 12 s wokół kursora' : 'ostatnie 12 s';
  S.dirty = true;
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
    updatePanels(f);
    const live = S.mode === 'mic';
    drawRoll(live || S.mode === 'review' ? J(E.x.gt_roll_json(live ? E.x.gt_time() - 12.5 : S.viewT - 6.2, live ? E.x.gt_time() + 0.5 : S.viewT + 6.2)) : null, live);
    drawSpec(f);
    if (S.mode === 'review') {
      drawOverview();
      $('timeTxt').textContent = fmtT(S.viewT) + ' / ' + fmtT(S.rev.dur);
      if (!S.dragScrub) $('scrub').value = Math.round(S.viewT / S.rev.dur * 1000);
      renderLog(false);
    } else if (S.mode === 'mic' && ts - S.logAt > 500) { S.logAt = ts; renderLog(false); }
    consoleTick(f, ts);
    S.dirty = false;
  } catch (e) { console.error(e); }
}

// ------------------------------------------------------------------ start
function wire() {
  $('btnMic').onclick = startMic;
  $('btnDemo').onclick = () => loadDemo(true);
  $('btnStop').onclick = async () => { if (S.mode === 'mic') await stopAll(); else pause(); };
  $('file').onchange = e => { if (e.target.files[0]) openFile(e.target.files[0]); e.target.value = ''; };
  $('btnPlay').onclick = togglePlay;
  $('pmOrig').onclick = () => setPlayMode('orig'); $('pmTr').onclick = () => setPlayMode('tr'); $('pmBoth').onclick = () => setPlayMode('both');
  const sc = $('scrub');
  sc.addEventListener('input', () => { S.dragScrub = true; if (S.rev) { S.viewT = +sc.value / 1000 * S.rev.dur; } });
  sc.addEventListener('change', () => { S.dragScrub = false; if (S.rev) seek(+sc.value / 1000 * S.rev.dur); });
  const seekFromEvent = (c, e) => { if (!S.rev) return; const r = c.getBoundingClientRect(); seek((e.clientX - r.left) / r.width * S.rev.dur); };
  $('ov').addEventListener('click', e => seekFromEvent($('ov'), e));
  $('log').addEventListener('click', e => { const row = e.target.closest('div[data-t]'); if (row && S.mode === 'review') seek(Math.max(0, +row.dataset.t - 0.1)); });
  window.addEventListener('keydown', e => {
    if (e.code === 'Space' && S.mode === 'review' && !/INPUT|SELECT|TEXTAREA|BUTTON/.test((document.activeElement || {}).tagName || '')) { e.preventDefault(); togglePlay(); }
  });
  window.addEventListener('dragover', e => e.preventDefault());
  window.addEventListener('drop', e => { e.preventDefault(); const f = e.dataTransfer && e.dataTransfer.files[0]; if (f) openFile(f); });
  const ro = typeof ResizeObserver === 'function' ? new ResizeObserver(() => { S.dirty = true; cache.neckKey = ''; }) : null;
  if (ro) for (const id of ['neck', 'roll', 'spec', 'ov']) ro.observe($(id));
  const themeChanged = () => { readPalette(); cache.neckKey = ''; S.dirty = true; };
  try { matchMedia('(prefers-color-scheme: dark)').addEventListener('change', themeChanged); } catch (e) {}
  new MutationObserver(themeChanged).observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
}

async function main() {
  readPalette(); initSource(); buildGauge(); wire(); wireExports();
  $('dlSrc').disabled = !SRC.files.length;
  requestAnimationFrame(loop);
  try { await bootEngine(); }
  catch (e) {
    console.error(e);
    $('engTag').textContent = 'silnik C++ niedostępny'; $('engTag').className = 'pill err';
    setStatus('błąd ładowania silnika', 'err'); showMicHint('Nie udało się uruchomić silnika (' + esc(String(e && e.message || e)) + '). Pobierz aplikację i otwórz ją z dysku.');
    return;
  }
  $('engTag').textContent = 'C++17 · ' + E.kind + ' · ' + Math.round(E.wasmBytes / 1024) + ' KB';
  $('subKind').textContent = E.kind === 'WebAssembly' ? 'WebAssembly' : 'JavaScript (asm.js)';
  setText('stMod', E.kind === 'WebAssembly' ? 'wasm ' + Math.round(E.wasmBytes / 1024) + ' KB' : 'asm.js (wasm2js)');
  loadSettings(); buildStringRow(); updateGateMark(); updateButtons();
  if (IN_ARTIFACT) showMicHint(micHelp());
  // otwarcie w stanie roboczym: gotowy przykład (bez dźwięku, odtwarzanie po kliknięciu)
  try { await loadDemo(false); } catch (e) { console.error(e); setStatus('gotowy', ''); }
  window.__gs = { S, E, J, seek, play, pause, analyze, loadDemo, doExport, renderTranscription };
}
main();
})();
