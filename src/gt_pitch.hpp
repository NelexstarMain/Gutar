// gt_pitch.hpp - wykrywanie wielu wysokości naraz (grzebień harmoniczny na pikach
// widma + iteracyjne kasowanie) oraz YIN do stroika.
#pragma once
#include <cstdio>
#include "gt_spectrum.hpp"

namespace gt {

struct NoteDet {
  int midi = 0;
  float f = 0;      // dopasowana częstotliwość podstawowa [Hz]
  float cents = 0;  // odchyłka od nominalnej (względem aktualnego odniesienia A4)
  float amp = 0;    // siła (pierwiastek z sumy kwadratów amplitud 4 pierwszych alikwotów)
  float score = 0;
  int nh = 0;       // ile z 6 pierwszych alikwotów znaleziono
  bool sustained = false; // nuta podtrzymana: wykryta z obniżonym progiem, bo już brzmiała
  bool octave = false; // podwojenie oktawowe niższej nuty (wykryte po nadmiarze parzystych alikwotów)
};

class MultiPitch {
public:
  struct Options {
    double fs = 11025;
    int lo = 36, hi = 88;
    double B = 2.5e-4;     // nieharmoniczność struny (f_h = h f0 sqrt(1+B h^2))
    int maxH = 14;
    double dynDb = 42;
    double relThr = 0.2;
    int maxNotes = 6;
    bool octaves = true;     // wykrywaj oktawowe podwojenia
    double octRatio = 2.0;
  };

  void init(const Options& o, double a4) {
    o_ = o;
    setA4(a4);
  }

  void setRange(int lo, int hi) {
    if (lo == o_.lo && hi == o_.hi) return;
    o_.lo = lo; o_.hi = hi;
    setA4(a4_);
  }

  void setA4(double a4) {
    a4_ = a4;
    cands_.clear();
    for (int m = o_.lo; m <= o_.hi; ++m) {
      Cand c;
      c.m = m;
      c.f0 = midiFreq(m, a4);
      for (int h = 1; h <= o_.maxH; ++h) {
        const double f = h * c.f0 * std::sqrt(1 + o_.B * h * h);
        if (f > o_.fs * 0.5 * 0.92) break;
        c.hf.push_back((float)f);
        c.w.push_back((float)((c.f0 + 52) / (h * c.f0 + 320)));
      }
      for (int h = 1; h <= 40; ++h) {
        const double f = h * c.f0 * std::sqrt(1 + o_.B * h * h);
        if (f > 4800) break;
        c.all.push_back((float)f);
      }
      cands_.push_back(std::move(c));
    }
  }

  double a4() const { return a4_; }
#ifdef GT_DEBUG
  int dbgMidi_ = -1;
#endif

  // indeks najsilniejszego piku w przedziale +-tol centów wokół f, albo -1
  static int find(const std::vector<Peak>& peaks, double f, double tol) {
    const double lo = f * std::pow(2.0, -tol / 1200), hi = f * std::pow(2.0, tol / 1200);
    int a = 0, b = (int)peaks.size();
    while (a < b) {
      const int mid = (a + b) >> 1;
      if (peaks[mid].f < lo) a = mid + 1; else b = mid;
    }
    int best = -1;
    float ba = 0;
    for (int i = a; i < (int)peaks.size() && peaks[i].f <= hi; ++i)
      if (peaks[i].a > ba) { ba = peaks[i].a; best = i; }
    return best;
  }

  void detect(const std::vector<Peak>& peaks, std::vector<NoteDet>& notes) {
    notes.clear();
    const int P = (int)peaks.size();
    if (!P) return;
    double aMax = 0;
    for (const auto& p : peaks) aMax = std::max<double>(aMax, p.a);
    v_.assign(P, 0.0);
    for (int i = 0; i < P; ++i) v_[i] = clampd(1 + 20 * std::log10(peaks[i].a / aMax) / o_.dynDb, 0, 1);
    expl_.assign(P, 0);
    chosen_.assign(cands_.size(), 0);
    double base = 0;
    for (int it = 0; it < o_.maxNotes; ++it) {
      int bestC = -1;
      double bestScore = 0;
      int bestM6 = 0;
      for (size_t ci = 0; ci < cands_.size(); ++ci) {
        if (chosen_[ci]) continue;
        const Cand& c = cands_[ci];
        double sal = 0;
        int m6 = 0, un = 0;
        bool h1un = false;
        for (size_t h = 0; h < c.hf.size(); ++h) {
          const int pi = find(peaks, c.hf[h], 28 + 1.5 * h);
          idx_[h] = pi;
          if (pi < 0) continue;
          const uint8_t e = expl_[pi];
          sal += c.w[h] * v_[pi] * (e ? 0.25 : 1.0);
          if (h < 6) ++m6;
          if (h < 8 && !e && v_[pi] > 0.12) ++un;
          if (h == 0 && !e && v_[pi] > 0.25) h1un = true;
        }
#ifdef GT_DEBUG
        if (dbgMidi_ == c.m) fprintf(stderr, "  [dbg] it=%d midi=%d f0=%.1f m6=%d un=%d h1un=%d sal=%.3f\n", it, c.m, c.f0, m6, un, (int)h1un, sal);
#endif
        if (m6 < (c.f0 < 450 ? 3 : 2) || (un < 2 && !(h1un && m6 >= 3))) continue;
        const double score = sal * (0.55 + 0.45 * m6 / std::min<size_t>(6, c.hf.size()));
        if (bestC < 0 || score > bestScore) {
          bestC = (int)ci; bestScore = score; bestM6 = m6;
          for (size_t h = 0; h < c.hf.size(); ++h) bestIdx_[h] = idx_[h];
        }
      }
      if (bestC < 0) break;
      if (it == 0) base = bestScore;
      else if (bestScore < o_.relThr * base) break;
      chosen_[bestC] = 1;
      const Cand& c = cands_[bestC];
      double num = 0, den = 0, a2 = 0;
      // regresja ważona: (f_h/h)^2 = f0^2 (1 + B h^2)  ->  prosta względem x = h^2
      double sw = 0, sx = 0, sy = 0, sxx = 0, sxy = 0;
      int np = 0;
      for (size_t h = 0; h < c.hf.size(); ++h) {
        const int pi = bestIdx_[h];
        if (pi < 0) continue;
        if (!expl_[pi] && h < 8) {
          const double a = peaks[pi].a;
          num += a * peaks[pi].f / ((h + 1) * std::sqrt(1 + o_.B * (h + 1) * (h + 1)));
          den += a;
          if (h < 4) a2 += a * a;
          const double hh = (double)(h + 1), y = (peaks[pi].f / hh) * (peaks[pi].f / hh), x = hh * hh;
          sw += a; sx += a * x; sy += a * y; sxx += a * x * x; sxy += a * x * y;
          ++np;
        }
        expl_[pi] = 1;
      }
      for (size_t h = 0; h < c.all.size(); ++h) {
        const int pi = find(peaks, c.all[h], 28 + 1.5 * h);
        if (pi >= 0) expl_[pi] = 1;
      }
      double fe = den > 0 ? num / den : c.f0;
      if (np >= 3) {
        const double dd = sw * sxx - sx * sx;
        if (std::fabs(dd) > 1e-9 * sw * sxx) {
          const double c1 = (sw * sxy - sx * sy) / dd, c0 = (sy - c1 * sx) / sw;
          const double B = c0 > 0 ? c1 / c0 : -1;
          if (c0 > 0 && B > -2e-4 && B < 1.5e-3) fe = std::sqrt(c0);
        }
      }
      NoteDet n;
      n.midi = c.m; n.f = (float)fe; n.cents = (float)(1200 * std::log2(fe / c.f0));
      n.amp = (float)std::sqrt(a2); n.score = (float)bestScore; n.nh = bestM6;
      notes.push_back(n);
    }
    if (o_.octaves) addOctaveDoubles(peaks, notes);
    std::sort(notes.begin(), notes.end(), [](const NoteDet& a, const NoteDet& b) { return a.midi < b.midi; });
  }

  // Oktawowe podwojenie (np. E2 + E3): jego alikwoty pokrywają się z parzystymi alikwotami niższej nuty,
  // więc zwykłe kasowanie je ukrywa. Zdradza je nadmiar energii w parzystych alikwotach względem
  // gładkiej obwiedni nieparzystych: a(2k) / sqrt(a(2k-1) a(2k+1)) > próg (dla samotnej struny < 1).
  void addOctaveDoubles(const std::vector<Peak>& peaks, std::vector<NoteDet>& notes) {
    const size_t n0 = notes.size();
    for (size_t i = 0; i < n0; ++i) {
      const NoteDet base = notes[i];
      const int m2 = base.midi + 12;
      if (m2 > o_.hi || base.nh < 5) continue;
      bool dup = false;
      for (const auto& q : notes) if (q.midi == m2) dup = true;
      if (dup) continue;
      const Cand& c = cands_[base.midi - o_.lo];
      float a[9] = {0};
      for (int h = 1; h <= 7 && h <= (int)c.hf.size(); ++h) {
        const int pi = find(peaks, c.hf[h - 1] * std::pow(2.0, base.cents / 1200.0), 22 + 1.5 * h);
        a[h] = pi >= 0 ? peaks[pi].a : 0.f;
      }
      int votes = 0, tried = 0;
      for (int k = 1; k <= 3; ++k) {
        if (k == 1 && c.f0 < 110) continue;
        if (a[2 * k - 1] <= 0 || a[2 * k + 1] <= 0 || a[2 * k] <= 0) continue;
        ++tried;
        if (a[2 * k] > o_.octRatio * std::sqrt(a[2 * k - 1] * a[2 * k + 1])) ++votes;
      }
      if (tried >= 2 && votes >= 2) {
        NoteDet n;
        n.midi = m2; n.f = base.f * 2; n.cents = base.cents;
        n.amp = a[2] * 0.5f; n.score = base.score * 0.3f; n.nh = 4; n.octave = true;
        notes.push_back(n);
      }
    }
  }

private:
  struct Cand {
    int m = 0;
    double f0 = 0;
    std::vector<float> hf, w, all;
  };
  Options o_;
  double a4_ = 440;
  std::vector<Cand> cands_;
  std::vector<double> v_;
  std::vector<uint8_t> expl_, chosen_;
  int idx_[32], bestIdx_[32];
};

// YIN: pojedyncza wysokość dla stroika. Zwraca częstotliwość (0 = brak) i pewność 0..1.
struct YinResult { double f = 0, prob = 0; };

inline YinResult yin(const float* x, int n, double fs, double fmin = 70, double fmax = 1200, double thr = 0.12) {
  YinResult res;
  const int W = n / 2;
  const int tauMax = std::min(W - 2, (int)std::floor(fs / fmin)), tauMin = std::max(2, (int)std::floor(fs / fmax));
  if (tauMax <= tauMin + 2) return res;
  std::vector<float> cm(tauMax + 2, 1.f);
  double run = 0;
  for (int tau = 1; tau <= tauMax; ++tau) {
    double s = 0;
    for (int j = 0; j < W; ++j) { const double d = (double)x[j] - x[j + tau]; s += d * d; }
    run += s;
    cm[tau] = run > 0 ? (float)(s * tau / run) : 1.f;
  }
  int tau = -1;
  for (int t = tauMin; t <= tauMax; ++t) {
    if (cm[t] < thr) {
      while (t + 1 <= tauMax && cm[t + 1] < cm[t]) ++t;
      tau = t;
      break;
    }
  }
  if (tau < 0) {
    int m = tauMin;
    for (int t = tauMin; t <= tauMax; ++t) if (cm[t] < cm[m]) m = t;
    if (cm[m] > 0.3f) return res;
    tau = m;
  }
  double bt = tau;
  if (tau > 1 && tau < tauMax) {
    const double a = cm[tau - 1], b = cm[tau], c = cm[tau + 1], den = 2 * (a - 2 * b + c);
    if (den != 0) bt = tau + (a - c) / den;
  }
  res.f = fs / bt;
  res.prob = std::max(0.0, 1.0 - cm[tau]);
  return res;
}

} // namespace gt
