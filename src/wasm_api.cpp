// wasm_api.cpp - interfejs C silnika dla przeglądarki (WebAssembly).
// Budowa: build.sh (zig c++ -target wasm32-wasi). Wszystkie funkcje gt_* są eksportowane.
#include <cstdarg>
#include <cstdio>
#include <cstring>
#include <map>
#include <string>
#include "gt_engine.hpp"
#include "gt_export.hpp"
#include "gt_synth.hpp"

using namespace gt;

#define GT_EXPORT(name) extern "C" __attribute__((export_name(#name), visibility("default")))

namespace {

struct State {
  Engine eng;
  EngineConfig cfg;
  std::vector<float> in, file, synth;
  size_t filePos = 0;
  std::string out;
  Bytes bin;
  int fs = 44100, synthFs = 0;
  bool synthReady = false;
  std::map<std::string, std::vector<FretPos>> fingerCache;
  std::vector<NoteEvent2> synthEvents;
};

State& S() {
  static State s;
  return s;
}
uint8_t*& scratchPtr() {
  static uint8_t* p = nullptr;
  return p;
}
std::vector<ZipEntry>& zipFiles() {
  static std::vector<ZipEntry> z;
  return z;
}

const int* openStrings() { return kTunings[S().cfg.tuning].open; }

void append(std::string& o, const char* fmt, ...) __attribute__((format(printf, 2, 3)));
void append(std::string& o, const char* fmt, ...) {
  char buf[512];
  va_list ap;
  va_start(ap, fmt);
  const int n = vsnprintf(buf, sizeof buf, fmt, ap);
  va_end(ap);
  if (n > 0) o.append(buf, (size_t)std::min<int>(n, (int)sizeof buf - 1));
}

const std::vector<FretPos>& fingerCached(const std::vector<int>& midis) {
  State& s = S();
  std::string key = std::to_string(s.cfg.tuning);
  for (int m : midis) { key += ','; key += std::to_string(m); }
  auto it = s.fingerCache.find(key);
  if (it != s.fingerCache.end()) return it->second;
  if (s.fingerCache.size() > 4000) s.fingerCache.clear();
  return s.fingerCache[key] = fingerGroup(midis, openStrings());
}

int finish(const std::string& o) { return (int)o.size(); }

} // namespace

GT_EXPORT(gt_api_version) int gt_api_version() { return 3; }

GT_EXPORT(gt_config)
void gt_config(double a4, int win, double gateDb, int mains, int autoTune, int autoGate, int tuning, int octaves) {
  State& s = S();
  s.cfg.a4 = a4 < 400 || a4 > 480 ? 440 : a4;
  s.cfg.win = (win == 2048 || win == 8192) ? win : 4096;
  s.cfg.gateDb = clampd(gateDb, -90, -30);
  s.cfg.mains = mains;
  s.cfg.autoTune = autoTune != 0;
  s.cfg.autoGate = autoGate != 0;
  s.cfg.tuning = (tuning >= 0 && tuning < kNumTunings) ? tuning : 0;
  s.cfg.octaves = octaves != 0;
  s.eng.configure(s.cfg);
}

GT_EXPORT(gt_init)
void gt_init(int sampleRate) {
  State& s = S();
  s.fs = sampleRate > 8000 ? sampleRate : 44100;
  s.eng.configure(s.cfg);
  s.eng.begin(s.fs);
  s.eng.setRecordLimit((int64_t)s.cfg.recordMaxSec * s.fs);
  s.fingerCache.clear();
  s.synthReady = false;
}

GT_EXPORT(gt_reset) void gt_reset() { S().eng.resetState(); }

GT_EXPORT(gt_input)
float* gt_input(int n) {
  State& s = S();
  if ((int)s.in.size() < n) s.in.resize(n);
  return s.in.data();
}

GT_EXPORT(gt_push) void gt_push(int n) { S().eng.push(S().in.data(), n); }
GT_EXPORT(gt_finish) void gt_finish() { S().eng.finish(); }

// --- analiza całego pliku -----------------------------------------------------------------
GT_EXPORT(gt_file_alloc)
float* gt_file_alloc(int n) {
  State& s = S();
  s.file.assign((size_t)n, 0.f);
  return s.file.data();
}

GT_EXPORT(gt_file_begin)
void gt_file_begin(int sampleRate, int prepass) {
  State& s = S();
  s.fs = sampleRate;
  s.eng.configure(s.cfg);
  s.eng.begin(sampleRate);
  s.eng.setRecordLimit((int64_t)s.file.size());
  s.synthReady = false;
  if (prepass) s.eng.prepass(s.file.data(), s.file.size());
  s.filePos = 0;
}

// zwraca postęp w promilach (1000 = koniec)
GT_EXPORT(gt_file_step)
int gt_file_step(int count) {
  State& s = S();
  const size_t n = s.file.size();
  if (s.filePos >= n) return 1000;
  const size_t take = std::min<size_t>((size_t)count, n - s.filePos);
  size_t done = 0;
  while (done < take) {
    const size_t c = std::min<size_t>(8192, take - done);
    s.eng.push(s.file.data() + s.filePos + done, (int)c);
    done += c;
  }
  s.filePos += take;
  if (s.filePos >= n) {
    s.eng.finish();
    return 1000;
  }
  return (int)(1000.0 * (double)s.filePos / (double)n);
}

GT_EXPORT(gt_file_free)
void gt_file_free() {
  std::vector<float>().swap(S().file);
}

GT_EXPORT(gt_clear) void gt_clear() { S().eng.clearHistory(); }

// --- odczyt stanu -------------------------------------------------------------------------
GT_EXPORT(gt_frames) int gt_frames() { return (int)S().eng.frames().size(); }
GT_EXPORT(gt_time) double gt_time() { return S().eng.time(); }

GT_EXPORT(gt_frame_at)
int gt_frame_at(double t) {
  const auto& f = S().eng.frames();
  if (f.empty()) return -1;
  int lo = 0, hi = (int)f.size() - 1;
  while (lo < hi) {
    const int m = (lo + hi) >> 1;
    if (f[m].t < t) lo = m + 1; else hi = m;
  }
  return lo;
}

GT_EXPORT(gt_text) const char* gt_text() { return S().out.data(); }
GT_EXPORT(gt_bin) const uint8_t* gt_bin() { return S().bin.data(); }

GT_EXPORT(gt_frame_json)
int gt_frame_json(int idx) {
  State& s = S();
  const auto& fr = s.eng.frames();
  std::string& o = s.out;
  o.clear();
  if (fr.empty()) { o = "null"; return finish(o); }
  if (idx < 0 || idx >= (int)fr.size()) idx = (int)fr.size() - 1;
  const FrameRec& f = fr[idx];
  const auto& names = s.eng.chordNames();
  append(o, "{\"i\":%d,\"t\":%.3f,\"lv\":%.1f,\"sil\":%d,\"on\":%d,", idx, f.t, f.levelDb, f.silent ? 1 : 0, f.onset ? 1 : 0);
  if (f.chord >= 0) append(o, "\"ch\":\"%s\",\"cs\":%.2f,", jsonEsc(names[f.chord]).c_str(), f.chordScore);
  else o += "\"ch\":null,\"cs\":0,";
  o += "\"alt\":[";
  bool first = true;
  for (int k = 0; k < 2; ++k)
    if (f.alt[k] >= 0) { append(o, "%s\"%s\"", first ? "" : ",", jsonEsc(names[f.alt[k]]).c_str()); first = false; }
  o += "],\"n\":[";
  std::vector<int> stable, all;
  for (int i = 0; i < f.nNotes; ++i) {
    const FrameNote& n = f.notes[i];
    append(o, "%s[%d,%.2f,%.1f,%.4f,%d]", i ? "," : "", n.midi, n.f, n.cents, n.amp, n.stable ? 1 : 0);
    all.push_back(n.midi);
    if (n.stable) stable.push_back(n.midi);
  }
  o += "],\"tu\":";
  if (f.tunerOk) append(o, "[%d,%.2f,%.1f,%.1f,%.2f]", f.tMidi, f.tF, f.tCents, f.tCentsSm, f.tProb);
  else o += "null";
  o += ",\"pk\":[";
  for (int i = 0; i < f.nPeaks; ++i) append(o, "%s[%.1f,%.5f]", i ? "," : "", f.pk[i][0], f.pk[i][1]);
  o += "],\"fg\":[";
  if (!f.silent) {
    const auto& fg = fingerCached(stable.empty() ? all : stable);
    first = true;
    for (const auto& p : fg) {
      if (p.s < 0) continue;
      append(o, "%s[%d,%d,%d]", first ? "" : ",", p.midi, p.s + 1, p.f);
      first = false;
    }
  }
  o += "]}";
  return finish(o);
}

// zdarzenia widoczne w oknie czasu [t0, t1]: nuty (też trwające), uderzenia, akordy
GT_EXPORT(gt_roll_json)
int gt_roll_json(double t0, double t1) {
  State& s = S();
  std::string& o = s.out;
  o.clear();
  append(o, "{\"now\":%.3f,\"ev\":[", s.eng.time());
  bool first = true;
  for (const auto& e : s.eng.events()) {
    if (e.t1 < t0 || e.t0 > t1) continue;
    append(o, "%s[%d,%.3f,%.3f,%d,0]", first ? "" : ",", e.midi, e.t0, e.t1, e.vel);
    first = false;
  }
  if (!s.eng.finished())
    for (const auto& kv : s.eng.tracker().active) {
      append(o, "%s[%d,%.3f,%.3f,%d,1]", first ? "" : ",", kv.first, kv.second.t0, s.eng.time(), kv.second.vel);
      first = false;
    }
  o += "],\"on\":[";
  first = true;
  const auto& on = s.eng.onsets();
  size_t lo = 0, hi = on.size();
  while (lo < hi) { const size_t m = (lo + hi) / 2; if (on[m] < t0) lo = m + 1; else hi = m; }
  for (size_t i = lo; i < on.size() && on[i] <= t1; ++i) { append(o, "%s%.3f", first ? "" : ",", on[i]); first = false; }
  o += "],\"ch\":[";
  first = true;
  for (const auto& c : s.eng.chordLog()) {
    if (c.t < t0 || c.t > t1) continue;
    append(o, "%s[%.3f,\"%s\"]", first ? "" : ",", c.t, jsonEsc(c.name).c_str());
    first = false;
  }
  o += "]}";
  return finish(o);
}

GT_EXPORT(gt_summary_json)
int gt_summary_json() {
  State& s = S();
  std::string& o = s.out;
  o.clear();
  const auto ev = s.eng.allEvents();
  append(o, "{\"time\":%.3f,\"frames\":%d,\"notes\":%d,\"onsets\":%d,\"tune\":%.2f,\"gate\":%.1f,\"bpm\":%.0f,\"rec\":%d,\"fs\":%d,\"win\":%.4f,\"hop\":%.4f,\"chords\":[",
         s.eng.time(), (int)s.eng.frames().size(), (int)ev.size(), (int)s.eng.onsets().size(), s.eng.tuneCents(), s.eng.gate(),
         estimateBpm(s.eng.onsets()), (int)s.eng.recording().size(), s.fs, s.eng.winSec(), s.eng.hopSec());
  bool first = true;
  for (const auto& c : s.eng.chordLog()) {
    append(o, "%s[%.3f,\"%s\"]", first ? "" : ",", c.t, jsonEsc(c.name).c_str());
    first = false;
  }
  o += "]}";
  return finish(o);
}

GT_EXPORT(gt_tuning_json)
int gt_tuning_json() {
  std::string& o = S().out;
  o = "[";
  for (int i = 0; i < kNumTunings; ++i) {
    append(o, "%s{\"name\":\"%s\",\"open\":[%d,%d,%d,%d,%d,%d]}", i ? "," : "", kTunings[i].name, kTunings[i].open[0], kTunings[i].open[1],
           kTunings[i].open[2], kTunings[i].open[3], kTunings[i].open[4], kTunings[i].open[5]);
  }
  o += "]";
  return finish(o);
}

// --- nagranie sesji (int16 przy częstotliwości wejścia) -------------------------------------
GT_EXPORT(gt_rec_len) int gt_rec_len() { return (int)S().eng.recording().size(); }
GT_EXPORT(gt_rec_ptr) const int16_t* gt_rec_ptr() { return S().eng.recording().data(); }
GT_EXPORT(gt_rec_rate) int gt_rec_rate() { return S().fs; }

// --- ZIP z dowolnych plików (używane do pakowania w aplikacji) ----------------------------
GT_EXPORT(gt_scratch)
uint8_t* gt_scratch(int n) {
  static std::vector<uint8_t> buf;
  if ((int)buf.size() < n) buf.resize(n);
  scratchPtr() = buf.data();
  return buf.data();
}
GT_EXPORT(gt_zip_reset) void gt_zip_reset() { zipFiles().clear(); }
// w gt_scratch: [nazwa nameLen bajtów][dane dataLen bajtów]
GT_EXPORT(gt_zip_add)
void gt_zip_add(int nameLen, int dataLen) {
  const uint8_t* p = scratchPtr();
  ZipEntry z;
  z.name.assign((const char*)p, (size_t)nameLen);
  z.data.assign(p + nameLen, p + nameLen + dataLen);
  zipFiles().push_back(std::move(z));
}
GT_EXPORT(gt_zip_finish)
int gt_zip_finish() {
  S().bin = makeZip(zipFiles());
  return (int)S().bin.size();
}

// --- demo: progresja akordów + arpeggio zsyntezowane w C++ ------------------------------
GT_EXPORT(gt_demo_render)
int gt_demo_render(int fsOut) {
  State& s = S();
  static const std::vector<std::vector<int>> P = {{45, 52, 57, 60, 64}, {48, 52, 55, 60, 64}, {43, 47, 50, 55, 59, 67}, {40, 47, 50, 56, 59, 64},
                                                  {50, 57, 62, 66},     {40, 47, 52, 55, 59, 64}, {41, 48, 53, 57, 60, 65}, {45, 52, 57, 62, 64}};
  std::vector<NoteEvent> ev;
  for (size_t i = 0; i < P.size(); ++i)
    for (size_t k = 0; k < P[i].size(); ++k) {
      NoteEvent e;
      e.midi = P[i][k]; e.t0 = 0.4 + i * 2.0 + k * 0.012; e.t1 = 0.4 + i * 2.0 + 2.2; e.vel = 0.85f;
      ev.push_back(e);
    }
  static const int arp[8] = {45, 52, 57, 60, 64, 60, 57, 52};
  for (int i = 0; i < 8; ++i) {
    NoteEvent e;
    e.midi = arp[i]; e.t0 = 16.4 + i * 0.3; e.t1 = e.t0 + 1.2; e.vel = 0.8f;
    ev.push_back(e);
  }
  s.synth.assign((size_t)(20.5 * fsOut), 0.f);
  s.synthFs = fsOut;
  SynthOptions so;
  so.varied = true; so.gain = 0.2; so.seed = 5; so.noteCentsSd = 2.5;
  renderNotes(s.synth.data(), s.synth.size(), fsOut, ev, so);
  float pk = 0;
  for (float v : s.synth) pk = std::max(pk, std::fabs(v));
  if (pk > 0) for (auto& v : s.synth) v *= 0.7f / pk;
  s.synthReady = false; // bufor demo nie jest transkrypcją
  return (int)s.synth.size();
}

// --- syntezator transkrypcji (porcjami, żeby nie blokować interfejsu) --------------------
GT_EXPORT(gt_synth_begin)
int gt_synth_begin(int fsOut) {
  State& s = S();
  s.synthEvents = s.eng.allEvents();
  double tmax = 0.5;
  for (const auto& e : s.synthEvents) tmax = std::max(tmax, e.t1);
  s.synthFs = fsOut;
  s.synth.assign((size_t)((tmax + 1.5) * fsOut), 0.f);
  s.synthReady = false;
  return (int)s.synth.size();
}

GT_EXPORT(gt_synth_count) int gt_synth_count() { return (int)S().synthEvents.size(); }

// renderuje nuty o numerach [from, to) (posortowane po czasie)
GT_EXPORT(gt_synth_step)
void gt_synth_step(int from, int to) {
  State& s = S();
  std::vector<NoteEvent> ne;
  for (int i = from; i < to && i < (int)s.synthEvents.size(); ++i) {
    const auto& e = s.synthEvents[i];
    NoteEvent n;
    n.t0 = e.t0; n.t1 = std::max(e.t1, e.t0 + 0.35); n.midi = e.midi; n.vel = (float)clampd(e.vel / 127.0, 0.2, 1.0);
    ne.push_back(n);
  }
  SynthOptions so;
  so.body = false;
  so.gain = 0.16;
  so.maxPartials = 20;
  so.minRel = 6e-3;
  so.seed = 1 + (uint64_t)from;
  renderNotes(s.synth.data(), s.synth.size(), s.synthFs, ne, so);
}

GT_EXPORT(gt_synth_end)
void gt_synth_end() {
  State& s = S();
  applyBody(s.synth, s.synthFs);
  float pk = 0;
  for (float v : s.synth) pk = std::max(pk, std::fabs(v));
  if (pk > 0) for (auto& v : s.synth) v *= 0.8f / pk;
  s.synthReady = true;
}

GT_EXPORT(gt_synth_ptr) const float* gt_synth_ptr() { return S().synth.data(); }
GT_EXPORT(gt_synth_len) int gt_synth_len() { return (int)S().synth.size(); }

// --- eksport -------------------------------------------------------------------------------
// 0 MIDI, 1 WAV (nagranie), 2 tabulatura, 3 akordy, 4 sesja JSON, 5 ZIP (wszystko), 6 WAV (transkrypcja)
GT_EXPORT(gt_export)
int gt_export(int kind) {
  State& s = S();
  const auto ev = s.eng.allEvents();
  const double bpm = estimateBpm(s.eng.onsets());
  const char* tn = kTunings[s.cfg.tuning].name;
  const int* open = openStrings();
  Bytes& b = s.bin;
  b.clear();
  auto text = [&](const std::string& t) { b.assign(t.begin(), t.end()); };
  auto tab = [&]() { return tabString(ev, s.eng.chordLog(), open, tn, bpm); };
  auto session = [&]() { return sessionJson(ev, s.eng.chordLog(), s.eng.onsets(), tn, open, bpm, s.eng.time(), s.eng.tuneCents(), s.fs); };
  const auto& rec = s.eng.recording();
  switch (kind) {
    case 0: b = makeMidi(ev, bpm, s.eng.chordLog()); break;
    case 1: b = wav16(rec.data(), rec.size(), s.fs); break;
    case 2: text(tab()); break;
    case 3: text(chordText(s.eng.chordLog())); break;
    case 4: text(session()); break;
    case 6: if (s.synthReady) b = wav16f(s.synth.data(), s.synth.size(), s.synthFs); break;
    case 5: {
      std::vector<ZipEntry> z;
      auto addText = [&](const char* n, const std::string& t) { z.push_back({n, Bytes(t.begin(), t.end())}); };
      if (!rec.empty()) z.push_back({"gitara-nagranie.wav", wav16(rec.data(), rec.size(), s.fs)});
      z.push_back({"gitara.mid", makeMidi(ev, bpm, s.eng.chordLog())});
      addText("gitara-tabulatura.txt", tab());
      addText("gitara-akordy.txt", chordText(s.eng.chordLog()));
      addText("gitara-sesja.json", session());
      if (s.synthReady) z.push_back({"gitara-transkrypcja.wav", wav16f(s.synth.data(), s.synth.size(), s.synthFs)});
      addText("CZYTAJ.txt",
              "Gitara Słuchacz - eksport sesji\n"
              "gitara-nagranie.wav       całe nagranie (16-bit mono)\n"
              "gitara.mid                wykryte nuty + znaczniki akordów (General MIDI, gitara stalowa)\n"
              "gitara-tabulatura.txt     tabulatura\n"
              "gitara-akordy.txt         lista akordów z czasami\n"
              "gitara-sesja.json         wszystko w jednym pliku (nuty, struny, progi, akordy, uderzenia)\n"
              "gitara-transkrypcja.wav   odsłuch wykrytych nut (jeśli wyrenderowano)\n");
      b = makeZip(z);
      break;
    }
    default: break;
  }
  return (int)b.size();
}
