// gt_hcqt.hpp - wejście modelu gen 5: harmonicznie ułożone widmo (HCQT, Bittner i in. 2017) z całego nagrania.
// Dla każdej wysokości co 1/3 półtonu (MIDI 36 - 88) i każdej klatki (co 512 próbek po decymacji, wyrównane z ramkami silnika)
// 9 kanałów: amplituda na alikwotach 0,5x, 1x, 2x, 3x, 4x, 5x z okna 4096 (rozdzielczość częstotliwości) oraz 1x, 2x, 3x z okna
// 1024 (rozdzielczość czasu). Wartość: dB względem 99,5. percentyla nagrania, przeskalowane do ok. 0..1. Dzięki ułożeniu alikwotów
// jedna konwolucja widzi naraz całą serię harmoniczną kandydata.
#pragma once
#include "gt_dsp.hpp"

namespace gt {

struct Hcqt {
  static constexpr int kMidi0 = 36, kSemis = 53, P = kSemis * 3, C = 9, kHop = 512;
  static constexpr int kLong = 4096, kShort = 1024;
  int T = 0;
  std::vector<float> v; // T x C x P
  float at(int t, int c, int p) const { return v[((size_t)t * C + c) * P + p]; }

  static double binMidi(int p) { return kMidi0 + (p - 1) / 3.0; } // p = 3s+1 to środek półtonu s

  // d: cały sygnał po decymacji, fsd: jego częstotliwość próbkowania
  void compute(const std::vector<float>& d, double fsd) {
    const int64_t N = (int64_t)d.size();
    T = N >= kLong ? (int)((N - kLong) / kHop + 1) : 0;
    v.assign((size_t)T * C * P, 0.f);
    if (!T) return;
    FFT fl, fs;
    const int ML = kLong * 4, MS = kShort * 4;
    fl.init(ML); fs.init(MS);
    const std::vector<double> wl = hann(kLong), ws = hann(kShort);
    std::vector<double> re(ML), im(ML), ml(ML / 2), rs(MS), is(MS), ms(MS / 2);
    static const double hl[6] = {0.5, 1, 2, 3, 4, 5}, hs[3] = {1, 2, 3};
    // zakresy binów dla każdej (alikwot, wysokość): +-1/6 półtonu wokół h * f(p)
    struct R { int a, b; };
    std::vector<R> rl(6 * P), rsr(3 * P);
    auto mk = [&](double h, int p, int M, R& r) {
      const double f = h * 440.0 * std::pow(2.0, (binMidi(p) - 69) / 12.0);
      if (f > 0.46 * fsd) { r.a = 1; r.b = 0; return; }
      const double bh = fsd / M;
      r.a = std::max(1, (int)std::floor(f * std::pow(2.0, -1.0 / 72) / bh));
      r.b = std::min(M / 2 - 1, std::max(r.a, (int)std::ceil(f * std::pow(2.0, 1.0 / 72) / bh)));
    };
    for (int k = 0; k < 6; ++k) for (int p = 0; p < P; ++p) mk(hl[k], p, ML, rl[k * P + p]);
    for (int k = 0; k < 3; ++k) for (int p = 0; p < P; ++p) mk(hs[k], p, MS, rsr[k * P + p]);
    std::vector<float> dbL, dbS;
    dbL.reserve((size_t)T * 6 * P / 4); dbS.reserve((size_t)T * 3 * P / 4);
    for (int t = 0; t < T; ++t) {
      const int64_t s0 = (int64_t)t * kHop, c = s0 + kLong / 2;
      double mean = 0;
      for (int i = 0; i < kLong; ++i) mean += d[s0 + i];
      mean /= kLong;
      for (int i = 0; i < ML; ++i) { re[i] = i < kLong ? (d[s0 + i] - mean) * wl[i] : 0; im[i] = 0; }
      fl.forward(re.data(), im.data());
      for (int k = 0; k < ML / 2; ++k) ml[k] = std::sqrt(re[k] * re[k] + im[k] * im[k]) * (4.0 / kLong);
      const int64_t a0 = c - kShort / 2;
      for (int i = 0; i < MS; ++i) {
        const int64_t j = a0 + i;
        rs[i] = (i < kShort && j >= 0 && j < N) ? d[j] * ws[i] : 0; is[i] = 0;
      }
      fs.forward(rs.data(), is.data());
      for (int k = 0; k < MS / 2; ++k) ms[k] = std::sqrt(rs[k] * rs[k] + is[k] * is[k]) * (4.0 / kShort);
      float* out = &v[(size_t)t * C * P];
      for (int k = 0; k < 6; ++k)
        for (int p = 0; p < P; ++p) {
          const R& r = rl[k * P + p];
          double m = 0;
          for (int q = r.a; q <= r.b; ++q) m = std::max(m, ml[q]);
          out[k * P + p] = (float)(20 * std::log10(m + 1e-9));
          if (r.b >= r.a && (t % 4) == 0) dbL.push_back(out[k * P + p]);
        }
      for (int k = 0; k < 3; ++k)
        for (int p = 0; p < P; ++p) {
          const R& r = rsr[k * P + p];
          double m = 0;
          for (int q = r.a; q <= r.b; ++q) m = std::max(m, ms[q]);
          out[(6 + k) * P + p] = (float)(20 * std::log10(m + 1e-9));
          if (r.b >= r.a && (t % 4) == 0) dbS.push_back(out[(6 + k) * P + p]);
        }
    }
    // normalizacja do głośności nagrania: 0 dB = 99,5. percentyl, skala 60 dB
    auto pct = [](std::vector<float>& x) {
      if (x.empty()) return -60.f;
      const size_t k = (size_t)(0.995 * (x.size() - 1));
      std::nth_element(x.begin(), x.begin() + k, x.end());
      return x[k];
    };
    const float refL = pct(dbL), refS = pct(dbS);
    for (int t = 0; t < T; ++t)
      for (int k = 0; k < C; ++k) {
        const float ref = k < 6 ? refL : refS;
        float* o = &v[((size_t)t * C + k) * P];
        for (int p = 0; p < P; ++p) {
          float x = (o[p] - ref) / 60.f + 1.f;
          o[p] = x < 0 ? 0 : (x > 1.3f ? 1.3f : x);
        }
      }
    // alikwoty powyżej Nyquista: zero (zakres pusty)
    for (int k = 0; k < 6; ++k) for (int p = 0; p < P; ++p) if (rl[k * P + p].b < rl[k * P + p].a) for (int t = 0; t < T; ++t) v[((size_t)t * C + k) * P + p] = 0;
    for (int k = 0; k < 3; ++k) for (int p = 0; p < P; ++p) if (rsr[k * P + p].b < rsr[k * P + p].a) for (int t = 0; t < T; ++t) v[((size_t)t * C + 6 + k) * P + p] = 0;
  }
  // środek okna klatki t [s]
  static double frameCenter(int t, double fsd) { return (t * (double)kHop + kLong / 2.0) / fsd; }
};

} // namespace gt
