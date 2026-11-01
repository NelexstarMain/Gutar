// gt_export.hpp - eksport: MIDI, WAV, ZIP, tabulatura, lista akordów, sesja JSON.
#pragma once
#include <cctype>
#include <cstdio>
#include <map>
#include <string>
#include "gt_chords.hpp"
#include "gt_fingering.hpp"
#include "gt_tracker.hpp"

namespace gt {

using Bytes = std::vector<uint8_t>;

inline void putU16le(Bytes& b, uint32_t v) { b.push_back(v & 255); b.push_back((v >> 8) & 255); }
inline void putU32le(Bytes& b, uint32_t v) { for (int i = 0; i < 4; ++i) b.push_back((v >> (8 * i)) & 255); }
inline void putU32be(Bytes& b, uint32_t v) { for (int i = 3; i >= 0; --i) b.push_back((v >> (8 * i)) & 255); }
inline void putStr(Bytes& b, const std::string& s) { b.insert(b.end(), s.begin(), s.end()); }

// ------------------------------------------------------------------- WAV 16-bit mono
inline Bytes wav16(const int16_t* pcm, size_t n, int fs) {
  Bytes b;
  b.reserve(44 + n * 2);
  putStr(b, "RIFF"); putU32le(b, (uint32_t)(36 + n * 2)); putStr(b, "WAVEfmt ");
  putU32le(b, 16); putU16le(b, 1); putU16le(b, 1); putU32le(b, (uint32_t)fs); putU32le(b, (uint32_t)fs * 2);
  putU16le(b, 2); putU16le(b, 16); putStr(b, "data"); putU32le(b, (uint32_t)(n * 2));
  for (size_t i = 0; i < n; ++i) putU16le(b, (uint16_t)pcm[i]);
  return b;
}

inline Bytes wav16f(const float* x, size_t n, int fs) {
  std::vector<int16_t> p(n);
  for (size_t i = 0; i < n; ++i) {
    const float v = x[i] > 1.f ? 1.f : (x[i] < -1.f ? -1.f : x[i]);
    p[i] = (int16_t)std::lrintf(v * 32767.f);
  }
  return wav16(p.data(), n, fs);
}

// ------------------------------------------------------------------- ZIP (bez kompresji)
struct ZipEntry {
  std::string name;
  Bytes data;
};

inline uint32_t crc32(const uint8_t* d, size_t n) {
  static uint32_t table[256];
  static bool init = false;
  if (!init) {
    for (uint32_t i = 0; i < 256; ++i) {
      uint32_t c = i;
      for (int k = 0; k < 8; ++k) c = (c & 1) ? 0xEDB88320u ^ (c >> 1) : c >> 1;
      table[i] = c;
    }
    init = true;
  }
  uint32_t c = 0xFFFFFFFFu;
  for (size_t i = 0; i < n; ++i) c = table[(c ^ d[i]) & 255] ^ (c >> 8);
  return c ^ 0xFFFFFFFFu;
}

inline Bytes makeZip(const std::vector<ZipEntry>& files) {
  Bytes out, central;
  const uint16_t dosTime = 12 << 11, dosDate = ((2026 - 1980) << 9) | (1 << 5) | 1; // 12:00, 2026-01-01
  for (const auto& f : files) {
    const uint32_t crc = crc32(f.data.data(), f.data.size()), off = (uint32_t)out.size();
    // lokalny nagłówek
    putU32le(out, 0x04034b50); putU16le(out, 20); putU16le(out, 0x0800); putU16le(out, 0);
    putU16le(out, dosTime); putU16le(out, dosDate); putU32le(out, crc);
    putU32le(out, (uint32_t)f.data.size()); putU32le(out, (uint32_t)f.data.size());
    putU16le(out, (uint32_t)f.name.size()); putU16le(out, 0);
    putStr(out, f.name);
    out.insert(out.end(), f.data.begin(), f.data.end());
    // katalog centralny
    putU32le(central, 0x02014b50); putU16le(central, 20); putU16le(central, 20); putU16le(central, 0x0800); putU16le(central, 0);
    putU16le(central, dosTime); putU16le(central, dosDate); putU32le(central, crc);
    putU32le(central, (uint32_t)f.data.size()); putU32le(central, (uint32_t)f.data.size());
    putU16le(central, (uint32_t)f.name.size()); putU16le(central, 0); putU16le(central, 0);
    putU16le(central, 0); putU16le(central, 0); putU32le(central, 0); putU32le(central, off);
    putStr(central, f.name);
  }
  const uint32_t cdOff = (uint32_t)out.size();
  out.insert(out.end(), central.begin(), central.end());
  putU32le(out, 0x06054b50); putU16le(out, 0); putU16le(out, 0);
  putU16le(out, (uint32_t)files.size()); putU16le(out, (uint32_t)files.size());
  putU32le(out, (uint32_t)central.size()); putU32le(out, cdOff); putU16le(out, 0);
  return out;
}

// ------------------------------------------------------------------- tempo i MIDI
// Szacuje tempo z odstępów między uderzeniami (histogram z fałdowaniem oktaw tempa).
inline double estimateBpm(const std::vector<double>& onsets) {
  std::vector<double> hist(241, 0.0);
  int n = 0;
  for (size_t i = 0; i + 1 < onsets.size(); ++i)
    for (size_t j = i + 1; j < std::min(onsets.size(), i + 4); ++j) {
      double d = onsets[j] - onsets[i];
      if (d < 0.15 || d > 3.0) continue;
      double bpm = 60.0 / d;
      while (bpm < 70) bpm *= 2;
      while (bpm > 160) bpm /= 2;
      const int b = (int)std::lround(bpm);
      if (b >= 60 && b <= 240) { for (int k = -2; k <= 2; ++k) if (b + k >= 0 && b + k <= 240) hist[b + k] += 3 - std::fabs((double)k); ++n; }
    }
  if (n < 6) return 120.0;
  int best = 120;
  for (int b = 60; b <= 200; ++b) if (hist[b] > hist[best]) best = b;
  return (double)best;
}

inline void putVlq(Bytes& b, uint32_t v) {
  uint8_t tmp[5];
  int n = 0;
  tmp[n++] = v & 127;
  while ((v >>= 7)) tmp[n++] = (uint8_t)((v & 127) | 128);
  while (n--) b.push_back(tmp[n]);
}

inline Bytes makeMidi(const std::vector<NoteEvent2>& events, double bpm, const std::vector<ChordLogEntry>& chords) {
  const int PPQ = 480;
  const double tps = PPQ * bpm / 60.0;
  struct Ev { long tick; int order; Bytes data; };
  std::vector<Ev> ev;
  for (const auto& e : events) {
    const long on = std::lround(e.t0 * tps), off = std::max(on + 1, (long)std::lround(e.t1 * tps));
    ev.push_back({on, 1, {0x90, (uint8_t)(e.midi & 127), (uint8_t)clampd(e.vel, 1, 127)}});
    ev.push_back({off, 0, {0x80, (uint8_t)(e.midi & 127), 0}});
  }
  for (const auto& c : chords) {
    Bytes m = {0xFF, 0x06, (uint8_t)c.name.size()};
    putStr(m, c.name);
    ev.push_back({std::lround(c.t * tps), 2, m});
  }
  std::stable_sort(ev.begin(), ev.end(), [](const Ev& a, const Ev& b) { return a.tick != b.tick ? a.tick < b.tick : a.order < b.order; });
  Bytes body;
  const uint32_t mpq = (uint32_t)std::lround(60000000.0 / bpm);
  body.insert(body.end(), {0x00, 0xFF, 0x51, 0x03, (uint8_t)(mpq >> 16), (uint8_t)(mpq >> 8), (uint8_t)mpq});
  const std::string nm = "Gitara";
  body.insert(body.end(), {0x00, 0xFF, 0x03, (uint8_t)nm.size()});
  putStr(body, nm);
  body.insert(body.end(), {0x00, 0xC0, 25}); // GM: Acoustic Guitar (steel)
  long last = 0;
  for (const auto& e : ev) {
    putVlq(body, (uint32_t)(e.tick - last));
    body.insert(body.end(), e.data.begin(), e.data.end());
    last = e.tick;
  }
  body.insert(body.end(), {0x00, 0xFF, 0x2F, 0x00});
  Bytes out;
  putStr(out, "MThd"); putU32be(out, 6); out.insert(out.end(), {0, 0, 0, 1, (uint8_t)(PPQ >> 8), (uint8_t)(PPQ & 255)});
  putStr(out, "MTrk"); putU32be(out, (uint32_t)body.size());
  out.insert(out.end(), body.begin(), body.end());
  return out;
}

// ------------------------------------------------------------------- grupy nut, tabulatura
struct NoteGroup {
  double t0 = 0;
  std::vector<int> midis;
};

inline std::vector<NoteGroup> groupNotes(std::vector<NoteEvent2> ev, double window = 0.14) {
  std::sort(ev.begin(), ev.end(), [](const NoteEvent2& a, const NoteEvent2& b) { return a.t0 < b.t0; });
  std::vector<NoteGroup> g;
  for (const auto& e : ev) {
    if (!g.empty() && e.t0 - g.back().t0 < window) g.back().midis.push_back(e.midi);
    else { NoteGroup n; n.t0 = e.t0; n.midis.push_back(e.midi); g.push_back(n); }
  }
  return g;
}

inline std::string fmtTime(double t) {
  char b[32];
  snprintf(b, sizeof b, "%d:%04.1f", (int)(t / 60), t - 60 * (int)(t / 60));
  return b;
}

inline std::string tabString(const std::vector<NoteEvent2>& events, const std::vector<ChordLogEntry>& chords, const int open[6],
                             const char* tuningName, double bpm) {
  auto groups = groupNotes(events);
  std::vector<std::vector<int>> gm;
  for (const auto& g : groups) gm.push_back(g.midis);
  auto fing = fingerSequence(gm, open);
  std::string out = "# Tabulatura (Gitara Słuchacz)\n# Strój: ";
  out += tuningName;
  char hb[64];
  snprintf(hb, sizeof hb, "   tempo ~%d BPM\n\n", (int)bpm);
  out += hb;
  if (groups.empty()) return out + "(brak nut)\n";
  static const int COLS = 12, W = 4;
  char lab[6];
  for (int s = 0; s < 6; ++s) {
    lab[s] = kNoteNames[open[s] % 12][0];
    if (s == 5) lab[s] = (char)std::tolower(lab[s]);
  }
  // kolumna, w której zaczyna się każdy akord (pierwsza grupa nie wcześniej niż 0.15 s przed akordem)
  std::vector<long> chordCol(chords.size(), -1);
  for (size_t ci = 0; ci < chords.size(); ++ci)
    for (size_t k = 0; k < groups.size(); ++k)
      if (groups[k].t0 + 0.15 >= chords[ci].t) { chordCol[ci] = (long)k; break; }
  for (size_t i = 0; i < groups.size(); i += COLS) {
    const size_t e = std::min(groups.size(), i + COLS);
    std::string chordRow(2 + (e - i) * W + 1, ' ');
    for (size_t ci = 0; ci < chords.size(); ++ci) {
      const long k = chordCol[ci];
      if (k < (long)i || k >= (long)e) continue;
      const size_t pos = 2 + (size_t)(k - (long)i) * W;
      for (size_t q = 0; q < chords[ci].name.size() && pos + q < chordRow.size(); ++q)
        if (chordRow[pos + q] == ' ') chordRow[pos + q] = chords[ci].name[q];
    }
    while (!chordRow.empty() && chordRow.back() == ' ') chordRow.pop_back();
    out += "[" + fmtTime(groups[i].t0) + "]\n";
    if (!chordRow.empty()) out += chordRow + "\n";
    for (int s = 5; s >= 0; --s) {
      std::string line;
      line += lab[s];
      line += '|';
      for (size_t k = i; k < e; ++k) {
        std::string cell = "-";
        for (const auto& p : fing[k]) if (p.s == s) cell = std::to_string(p.f);
        std::string col(W, '-');
        col.replace(W - cell.size(), cell.size(), cell);
        line += col;
      }
      line += "-|\n";
      out += line;
    }
    out += "\n";
  }
  return out;
}

inline std::string chordText(const std::vector<ChordLogEntry>& chords) {
  std::string out;
  for (const auto& c : chords) out += fmtTime(c.t) + "  " + c.name + "\n";
  return out.empty() ? "(brak akordów)\n" : out;
}

inline std::string jsonEsc(const std::string& s) {
  std::string o;
  for (char c : s) {
    if (c == '"' || c == '\\') { o += '\\'; o += c; }
    else if ((unsigned char)c < 32) o += ' ';
    else o += c;
  }
  return o;
}

inline std::string sessionJson(const std::vector<NoteEvent2>& events, const std::vector<ChordLogEntry>& chords, const std::vector<double>& onsets,
                               const char* tuningName, const int open[6], double bpm, double duration, double tuneCents, int sampleRate) {
  auto groups = groupNotes(events);
  std::vector<std::vector<int>> gm;
  for (const auto& g : groups) gm.push_back(g.midis);
  auto fing = fingerSequence(gm, open);
  std::map<std::pair<size_t, int>, FretPos> byGroup; // (grupa, midi) -> pozycja
  for (size_t g = 0; g < fing.size(); ++g) for (const auto& p : fing[g]) byGroup[{g, p.midi}] = p;
  auto groupOf = [&](double t0) {
    size_t gi = 0;
    for (size_t i = 0; i < groups.size(); ++i) if (groups[i].t0 <= t0 + 1e-9) gi = i; else break;
    return gi;
  };
  std::string o = "{\n  \"format\": \"gitara-sluchacz-session\",\n  \"version\": 1,\n";
  char b[256];
  snprintf(b, sizeof b, "  \"sampleRate\": %d,\n  \"duration\": %.3f,\n  \"bpm\": %.0f,\n  \"tuneCents\": %.2f,\n", sampleRate, duration, bpm, tuneCents);
  o += b;
  o += "  \"tuning\": \"" + jsonEsc(tuningName) + "\",\n  \"chords\": [";
  for (size_t i = 0; i < chords.size(); ++i) {
    snprintf(b, sizeof b, "%s\n    {\"t\": %.3f, \"name\": \"%s\"}", i ? "," : "", chords[i].t, jsonEsc(chords[i].name).c_str());
    o += b;
  }
  o += "\n  ],\n  \"notes\": [";
  std::vector<NoteEvent2> sorted = events;
  std::sort(sorted.begin(), sorted.end(), [](const NoteEvent2& a, const NoteEvent2& c) { return a.t0 < c.t0; });
  for (size_t i = 0; i < sorted.size(); ++i) {
    const auto& e = sorted[i];
    const size_t gi = groupOf(e.t0);
    auto it = byGroup.find({gi, e.midi});
    snprintf(b, sizeof b, "%s\n    {\"midi\": %d, \"name\": \"%s\", \"t0\": %.3f, \"t1\": %.3f, \"velocity\": %d, \"string\": %d, \"fret\": %d}",
             i ? "," : "", e.midi, midiName(e.midi).c_str(), e.t0, e.t1, e.vel, it != byGroup.end() ? it->second.s + 1 : 0,
             it != byGroup.end() ? it->second.f : -1);
    o += b;
  }
  o += "\n  ],\n  \"onsets\": [";
  for (size_t i = 0; i < onsets.size(); ++i) { snprintf(b, sizeof b, "%s%.3f", i ? ", " : "", onsets[i]); o += b; }
  o += "]\n}\n";
  (void)open;
  return o;
}

} // namespace gt
