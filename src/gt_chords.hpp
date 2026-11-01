// gt_chords.hpp - rozpoznawanie akordów z profilu klas dźwięków (pitch-class) + basu.
#pragma once
#include <string>
#include "gt_dsp.hpp"

namespace gt {

static const char* const kNoteNames[12] = {"C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"};

inline std::string midiName(int m) {
  return std::string(kNoteNames[((m % 12) + 12) % 12]) + std::to_string(m / 12 - 1);
}

struct ChordLogEntry {
  double t;
  std::string name;
};

struct ChordTemplate {
  const char* suffix;
  int n;
  int iv[6];
  float imp[6];
  float prior; // kara/premia za typ akordu (prostsze akordy są częstsze)
};

// interwały i ich ważność; prior < 0 = akord rzadszy
static const ChordTemplate kChordTemplates[] = {
    {"", 3, {0, 4, 7}, {1, .9f, .5f}, 0.0f},
    {"m", 3, {0, 3, 7}, {1, .9f, .5f}, 0.0f},
    {"5", 2, {0, 7}, {1, .8f}, -0.02f},
    {"7", 4, {0, 4, 7, 10}, {1, .8f, .4f, .9f}, -0.01f},
    {"maj7", 4, {0, 4, 7, 11}, {1, .8f, .4f, .9f}, -0.01f},
    {"m7", 4, {0, 3, 7, 10}, {1, .8f, .4f, .9f}, -0.01f},
    {"sus2", 3, {0, 2, 7}, {1, .9f, .5f}, -0.01f},
    {"sus4", 3, {0, 5, 7}, {1, .9f, .5f}, -0.01f},
    {"dim", 3, {0, 3, 6}, {1, .9f, .9f}, -0.04f},
    {"aug", 3, {0, 4, 8}, {1, .9f, .9f}, -0.04f},
    {"6", 4, {0, 4, 7, 9}, {1, .8f, .4f, .8f}, -0.02f},
    {"m6", 4, {0, 3, 7, 9}, {1, .8f, .4f, .8f}, -0.02f},
    {"add9", 4, {0, 2, 4, 7}, {1, .8f, .9f, .4f}, -0.02f},
    {"madd9", 4, {0, 2, 3, 7}, {1, .8f, .9f, .4f}, -0.03f},
    {"9", 5, {0, 2, 4, 7, 10}, {1, .7f, .7f, .3f, .8f}, -0.03f},
    {"m9", 5, {0, 2, 3, 7, 10}, {1, .7f, .7f, .3f, .8f}, -0.03f},
    {"7sus4", 4, {0, 5, 7, 10}, {1, .9f, .4f, .8f}, -0.03f},
    {"dim7", 4, {0, 3, 6, 9}, {1, .9f, .9f, .9f}, -0.04f},
    {"m7b5", 4, {0, 3, 6, 10}, {1, .9f, .9f, .9f}, -0.04f},
    {"mMaj7", 4, {0, 3, 7, 11}, {1, .8f, .4f, .9f}, -0.04f},
};
static const int kNumChordTemplates = sizeof(kChordTemplates) / sizeof(kChordTemplates[0]);

struct ChordResult {
  bool ok = false;
  int root = -1, tpl = -1, bass = -1;
  float score = 0;
  std::string name;
  std::string alt[2];
  int nAlt = 0;
};

struct ChordParams {
  float extraPenalty = 1.3f;   // kara za dźwięki spoza akordu
  float missPenalty = 0.25f;   // kara za brakujące tony akordu
  float bassBonus = 0.12f;     // premia, gdy bas = pryma
  float sizePenalty = 0.025f;  // kara za złożoność (liczba tonów powyżej 3)
  float minScore = 0.5f;
  float presence = 0.10f;      // udział klasy dźwięku, od którego uznajemy ją za obecną (miękko)
};

inline std::string formatChord(int root, int tpl, int bass) {
  std::string s = std::string(kNoteNames[root]) + kChordTemplates[tpl].suffix;
  if (bass >= 0 && bass != root) {
    const ChordTemplate& t = kChordTemplates[tpl];
    for (int i = 0; i < t.n; ++i)
      if ((root + t.iv[i]) % 12 == bass) { s += "/"; s += kNoteNames[bass]; break; }
  }
  return s;
}

// w: 12 wag klas dźwięków (suma = 1), bassPc: klasa basu lub -1
inline ChordResult recognizeChord(const double w[12], int bassPc, const ChordParams& P = ChordParams()) {
  ChordResult out;
  int present = 0;
  for (int p = 0; p < 12; ++p) if (w[p] > 1e-9) ++present;
  if (present < 2) return out;
  struct Cand { int root, tpl; float score; };
  Cand top[3] = {{-1, -1, -1e9f}, {-1, -1, -1e9f}, {-1, -1, -1e9f}};
  for (int r = 0; r < 12; ++r) {
    for (int ti = 0; ti < kNumChordTemplates; ++ti) {
      const ChordTemplate& T = kChordTemplates[ti];
      bool inSet[12] = {false};
      for (int i = 0; i < T.n; ++i) inSet[(T.iv[i]) % 12] = true;
      double match = 0, extra = 0, miss = 0;
      for (int p = 0; p < 12; ++p) {
        if (w[p] <= 1e-9) continue;
        if (inSet[(p - r + 12) % 12]) match += w[p]; else extra += w[p];
      }
      for (int i = 0; i < T.n; ++i) {
        const double have = std::min(1.0, w[(r + T.iv[i]) % 12] / P.presence);
        miss += T.imp[i] * (1.0 - have);
      }
      const double score = match - P.extraPenalty * extra - P.missPenalty * miss + (bassPc == r ? P.bassBonus : 0.0) -
                           P.sizePenalty * (T.n - 3) + T.prior;
      Cand c = {r, ti, (float)score};
      // wstaw do top-3
      for (int k = 0; k < 3; ++k) {
        if (c.score > top[k].score) std::swap(c, top[k]);
      }
    }
  }
  if (top[0].score < P.minScore) return out;
  out.ok = true;
  out.root = top[0].root; out.tpl = top[0].tpl; out.bass = bassPc; out.score = top[0].score;
  out.name = formatChord(top[0].root, top[0].tpl, bassPc);
  for (int k = 1; k < 3; ++k)
    if (top[k].root >= 0 && top[k].score > top[0].score - 0.25f && out.nAlt < 2)
      out.alt[out.nAlt++] = formatChord(top[k].root, top[k].tpl, bassPc);
  return out;
}

} // namespace gt
