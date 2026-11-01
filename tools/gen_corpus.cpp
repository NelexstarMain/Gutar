// gen_corpus.cpp - generuje syntetyczny korpus testowy: nagrania WAV + prawdę (JSON).
// Użycie: gen_corpus <katalog_wyjściowy>
#include <cstdio>
#include <string>
#include "../src/gt_synth.hpp"
#include "wavio.hpp"

using namespace gt;

static const int kOpen[6] = {40, 45, 50, 55, 59, 64};
static const char* kNames[12] = {"C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"};

struct Shape {
  const char* suffix;
  int fr[6]; // -1 = zagłuszona
  int rootStr;
  int minOff, maxOff; // dozwolone przesunięcie (barre/kapodaster)
};

// kształty (progi na strunach E A D G B e)
static const Shape kShapes[] = {
    {"", {0, 2, 2, 1, 0, 0}, 0, 0, 9},      {"m", {0, 2, 2, 0, 0, 0}, 0, 0, 9},
    {"7", {0, 2, 0, 1, 0, 0}, 0, 0, 9},     {"m7", {0, 2, 0, 0, 0, 0}, 0, 0, 9},
    {"maj7", {0, 2, 1, 1, 0, 0}, 0, 0, 9},  {"sus4", {0, 2, 2, 2, 0, 0}, 0, 0, 9},
    {"5", {0, 2, 2, -1, -1, -1}, 0, 0, 9},  {"", {-1, 0, 2, 2, 2, 0}, 1, 0, 9},
    {"m", {-1, 0, 2, 2, 1, 0}, 1, 0, 9},    {"7", {-1, 0, 2, 0, 2, 0}, 1, 0, 9},
    {"m7", {-1, 0, 2, 0, 1, 0}, 1, 0, 9},   {"maj7", {-1, 0, 2, 1, 2, 0}, 1, 0, 9},
    {"sus2", {-1, 0, 2, 2, 0, 0}, 1, 0, 9}, {"sus4", {-1, 0, 2, 2, 3, 0}, 1, 0, 9},
    {"5", {-1, 0, 2, 2, -1, -1}, 1, 0, 9},  {"", {-1, -1, 0, 2, 3, 2}, 2, 0, 5},
    {"m", {-1, -1, 0, 2, 3, 1}, 2, 0, 5},   {"7", {-1, -1, 0, 2, 1, 2}, 2, 0, 5},
    {"sus2", {-1, -1, 0, 2, 3, 0}, 2, 0, 5}, {"sus4", {-1, -1, 0, 2, 3, 3}, 2, 0, 5},
    {"", {-1, 3, 2, 0, 1, 0}, 1, 0, 0},     {"", {3, 2, 0, 0, 0, 3}, 0, 0, 0},
    {"add9", {-1, 3, 2, 0, 3, 0}, 1, 0, 0}, {"maj7", {-1, 3, 2, 0, 0, 0}, 1, 0, 0},
    {"7", {-1, 3, 2, 3, 1, 0}, 1, 0, 0},    {"7", {3, 2, 0, 0, 0, 1}, 0, 0, 0},
};
static const int kNShapes = sizeof(kShapes) / sizeof(kShapes[0]);

struct Voicing {
  std::string name;
  std::vector<int> notes; // MIDI, od basu
};

static Voicing makeVoicing(Rng& r) {
  const Shape& s = kShapes[r.range(0, kNShapes - 1)];
  int off = s.minOff == s.maxOff ? s.minOff : r.range(s.minOff, s.maxOff);
  Voicing v;
  for (int i = 0; i < 6; ++i)
    if (s.fr[i] >= 0) v.notes.push_back(kOpen[i] + s.fr[i] + off);
  const int rootMidi = kOpen[s.rootStr] + s.fr[s.rootStr] + off;
  v.name = std::string(kNames[rootMidi % 12]) + s.suffix;
  return v;
}

struct TNote { double t0, t1, f; int midi; };
struct TChord { double t0, t1; std::string name; };

struct Piece {
  std::string id, kind, noise;
  double snr = 99, cents = 0, reverb = 0;
  std::vector<TNote> notes;
  std::vector<TChord> chords;
  std::vector<float> audio;
};

static void writeTruth(const std::string& dir, const Piece& p, int fs) {
  FILE* f = fopen((dir + "/" + p.id + ".truth.json").c_str(), "w");
  fprintf(f, "{\"id\":\"%s\",\"kind\":\"%s\",\"noise\":\"%s\",\"snr\":%.1f,\"cents\":%.1f,\"reverb\":%.2f,\"fs\":%d,\"dur\":%.3f,\n", p.id.c_str(),
          p.kind.c_str(), p.noise.c_str(), p.snr, p.cents, p.reverb, fs, p.audio.size() / (double)fs);
  fprintf(f, "\"chords\":[");
  for (size_t i = 0; i < p.chords.size(); ++i)
    fprintf(f, "%s{\"t0\":%.3f,\"t1\":%.3f,\"name\":\"%s\"}", i ? "," : "", p.chords[i].t0, p.chords[i].t1, p.chords[i].name.c_str());
  fprintf(f, "],\n\"notes\":[");
  for (size_t i = 0; i < p.notes.size(); ++i)
    fprintf(f, "%s{\"midi\":%d,\"t0\":%.3f,\"t1\":%.3f,\"f\":%.4f}", i ? "," : "", p.notes[i].midi, p.notes[i].t0, p.notes[i].t1, p.notes[i].f);
  fprintf(f, "]}\n");
  fclose(f);
}

static void finish(Piece& p, const std::vector<NoteEvent>& ev, double total, int fs, uint64_t seed, double fstart) {
  SynthOptions so;
  so.varied = true;
  so.globalCents = p.cents;
  so.noteCentsSd = 4.0;
  so.seed = seed;
  p.audio.assign((size_t)(total * fs), 0.f);
  auto freqs = renderNotes(p.audio.data(), p.audio.size(), fs, ev, so);
  for (size_t i = 0; i < ev.size(); ++i) {
    TNote n;
    n.t0 = ev[i].t0; n.t1 = ev[i].t1; n.f = freqs[i]; n.midi = ev[i].midi;
    p.notes.push_back(n);
  }
  if (p.reverb > 0) schroederReverb(p.audio, fs, 0.5, p.reverb);
  if (p.noise != "none") addNoise(p.audio, fs, p.noise, p.snr, seed, (size_t)(fstart * fs), p.audio.size());
  // normalizacja szczytu do -3 dBFS (jak sensowne nagranie)
  float pk = 0;
  for (float v : p.audio) pk = std::max(pk, std::fabs(v));
  if (pk > 0) for (auto& v : p.audio) v *= 0.7f / pk;
}

// seria uderzeń w akordy
static Piece strumPiece(const std::string& id, uint64_t seed, const std::string& noise, double snr, double cents, double reverb) {
  Piece p; p.id = id; p.kind = "strum"; p.noise = noise; p.snr = snr; p.cents = cents; p.reverb = reverb;
  Rng r(seed);
  std::vector<NoteEvent> ev;
  double t = 0.5;
  std::string prev;
  const int nChords = r.range(6, 8);
  for (int c = 0; c < nChords; ++c) {
    Voicing v;
    do v = makeVoicing(r); while (v.name == prev);
    prev = v.name;
    const double dur = r.uni(1.9, 2.5);
    const bool down = r.uni() < 0.75;
    const double gap = r.uni(0.006, 0.028);
    std::vector<int> nn = v.notes;
    if (!down) std::reverse(nn.begin(), nn.end()); // uderzenie w górę: te same struny, od najwyższej
    const double vel0 = r.uni(0.6, 1.0);
    for (size_t i = 0; i < nn.size(); ++i) {
      NoteEvent e;
      e.midi = nn[i];
      e.t0 = t + i * gap + r.uni(-0.002, 0.002);
      e.t1 = t + dur;
      e.vel = (float)clampd(vel0 * r.uni(0.8, 1.15), 0.2, 1.0);
      ev.push_back(e);
    }
    p.chords.push_back({t, t + dur, v.name});
    t += dur;
  }
  finish(p, ev, t + 0.6, 44100, seed, 0.3);
  return p;
}

// melodia jednogłosowa
static Piece melodyPiece(const std::string& id, uint64_t seed, const std::string& noise, double snr, double cents) {
  Piece p; p.id = id; p.kind = "melody"; p.noise = noise; p.snr = snr; p.cents = cents;
  Rng r(seed);
  std::vector<NoteEvent> ev;
  double t = 0.4;
  int m = r.range(45, 62);
  while (t < 10.5) {
    m = (int)clampd(m + r.range(-7, 7), 40, 79);
    const double dur = r.uni(0.35, 0.9);
    NoteEvent e;
    e.midi = m; e.t0 = t; e.t1 = t + dur; e.vel = (float)r.uni(0.55, 1.0);
    ev.push_back(e);
    t += dur + r.uni(0.04, 0.2);
  }
  finish(p, ev, t + 0.6, 44100, seed, 0.3);
  return p;
}

// arpeggio / fingerstyle: pojedyncze struny akordu jedna po drugiej, dźwięki zachodzą na siebie
static Piece arpPiece(const std::string& id, uint64_t seed, const std::string& noise, double snr, double cents) {
  Piece p; p.id = id; p.kind = "arp"; p.noise = noise; p.snr = snr; p.cents = cents;
  Rng r(seed);
  std::vector<NoteEvent> ev;
  double t = 0.4;
  for (int c = 0; c < 3; ++c) {
    Voicing v = makeVoicing(r);
    const double step = r.uni(0.22, 0.4);
    const int reps = 8;
    for (int k = 0; k < reps; ++k) {
      static const int pat[8] = {0, 2, 3, 1, 4, 2, 3, 1};
      const int idx = pat[k] % (int)v.notes.size();
      NoteEvent e;
      e.midi = v.notes[idx]; e.t0 = t + k * step; e.t1 = t + k * step + 1.4; e.vel = (float)r.uni(0.6, 0.95);
      ev.push_back(e);
    }
    p.chords.push_back({t, t + reps * step, v.name});
    t += reps * step;
  }
  finish(p, ev, t + 1.8, 44100, seed, 0.3);
  return p;
}

int main(int argc, char** argv) {
  const std::string dir = argc > 1 ? argv[1] : "corpus";
  const uint64_t off = argc > 2 ? (uint64_t)atoll(argv[2]) : 0; // przesunięcie ziaren: inny zestaw = zbiór kontrolny
  std::vector<Piece> all;
  int n = 0;
  auto add = [&](Piece p) { all.push_back(std::move(p)); ++n; };
  char id[64];
  // akordy: czyste
  for (int i = 0; i < 10; ++i) { snprintf(id, 64, "strum_clean_%02d", i); add(strumPiece(id, off + 100 + i, "none", 99, 0, 0)); }
  // akordy: pogłos pokoju
  for (int i = 0; i < 6; ++i) { snprintf(id, 64, "strum_room_%02d", i); add(strumPiece(id, off + 200 + i, "none", 99, 0, 0.35)); }
  // akordy: szum
  for (int i = 0; i < 6; ++i) { snprintf(id, 64, "strum_pink20_%02d", i); add(strumPiece(id, off + 300 + i, "pink", 20, 0, 0)); }
  for (int i = 0; i < 6; ++i) { snprintf(id, 64, "strum_white12_%02d", i); add(strumPiece(id, off + 400 + i, "white", 12, 0, 0)); }
  for (int i = 0; i < 6; ++i) { snprintf(id, 64, "strum_mix15_%02d", i); add(strumPiece(id, off + 500 + i, "mix", 15, 0, 0)); }
  for (int i = 0; i < 6; ++i) { snprintf(id, 64, "strum_hum18_%02d", i); add(strumPiece(id, off + 600 + i, "hum", 18, 0, 0)); }
  // akordy: rozstrojona gitara
  const double dt[8] = {-35, -18, 14, 25, -8, -28, 32, 5};
  for (int i = 0; i < 8; ++i) { snprintf(id, 64, "strum_detune_%02d", i); add(strumPiece(id, off + 700 + i, "none", 99, dt[i], 0)); }
  // melodie
  for (int i = 0; i < 4; ++i) { snprintf(id, 64, "melody_clean_%02d", i); add(melodyPiece(id, off + 800 + i, "none", 99, 0)); }
  for (int i = 0; i < 3; ++i) { snprintf(id, 64, "melody_pink18_%02d", i); add(melodyPiece(id, off + 850 + i, "pink", 18, 0)); }
  for (int i = 0; i < 3; ++i) { snprintf(id, 64, "melody_detune_%02d", i); add(melodyPiece(id, off + 880 + i, "none", 99, dt[i])); }
  // arpeggia
  for (int i = 0; i < 4; ++i) { snprintf(id, 64, "arp_clean_%02d", i); add(arpPiece(id, off + 900 + i, "none", 99, 0)); }
  for (int i = 0; i < 2; ++i) { snprintf(id, 64, "arp_pink20_%02d", i); add(arpPiece(id, off + 950 + i, "pink", 20, 0)); }

  for (auto& p : all) {
    wavio::write16(dir + "/" + p.id + ".wav", p.audio, 44100);
    writeTruth(dir, p, 44100);
  }
  printf("zapisano %d nagrań w %s\n", n, dir.c_str());
  return 0;
}
