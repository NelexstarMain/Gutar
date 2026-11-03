// gt_mask.hpp - model maski: dla każdego pasma (pół półtonu, 55 Hz - 5 kHz) w każdej klatce ocenia, jaka część energii to gitara,
// a jaka szum, stuki i tony otoczenia. Służy do (1) czyszczenia pików przed wykrywaniem wysokości, (2) jako dowód dla modelu nut
// (czy alikwoty kandydata są "czyste") i (3) przy szukaniu początku i końca nut (narastanie i zanik maski w alikwotach).
// Wagi: gt_maskmodel.hpp (tools/train_mask.py), uczone na idealnej masce z tools/gen_env (czysta gitara i szum zapisane osobno).
#pragma once
#include "gt_spectrum.hpp"
#include "gt_maskmodel.hpp"

namespace gt {

class BandMask {
public:
  static constexpr int kMidi0 = 33;      // środek pierwszego pasma: A1, 55 Hz
  static constexpr int NB = 156;         // pasma co pół półtonu, do ok. 5 kHz
  static constexpr int NF = 15;          // cechy pasma (wejście sieci)

  static double bandFreq(double b) { return 440.0 * std::pow(2.0, (kMidi0 + b / 2.0 - 69) / 12.0); }
  // indeks pasma dla częstotliwości (zaokrąglony), -1 poza zakresem
  static int bandOf(double f) {
    if (f <= 0) return -1;
    const int b = (int)std::lround((12 * std::log2(f / 440.0) + 69 - kMidi0) * 2.0);
    return b >= 0 && b < NB ? b : -1;
  }

  void reset() { prev1_.assign(NB, -12.0); prev2_.assign(NB, -12.0); mask_.assign(NB, 1.f); feat_.assign(NB * NF, 0.f); prevMask_.assign(NB, 0.f); have_ = false; }

  // mag/nf: widmo i lokalny szum z Spectrum; tnoise: szum tła (może być pusty); level: poziom klatki względem progu ciszy (0..1,5)
  void compute(const Spectrum& sp, const std::vector<double>& tnoise, const std::vector<Peak>& peaks, float level) {
    if ((int)prev1_.size() != NB) reset();
    const auto& mag = sp.mag();
    const auto& nf = sp.noiseFloor();
    const double bh = sp.binHz();
    const int K = (int)mag.size();
    double E[NB], NFb[NB], TN[NB];
    double emax = 1e-30;
    for (int b = 0; b < NB; ++b) {
      const double fc = bandFreq(b), lo = fc * std::pow(2.0, -1.0 / 48), hi = fc * std::pow(2.0, 1.0 / 48);
      const int k0 = std::max(1, (int)std::floor(lo / bh)), k1 = std::min(K - 1, std::max(k0, (int)std::ceil(hi / bh)));
      double e = 0, n2 = 0, t2 = 0;
      for (int k = k0; k <= k1; ++k) { e += mag[k] * mag[k]; n2 += nf[k] * nf[k]; if (!tnoise.empty()) t2 += tnoise[k] * tnoise[k]; }
      const double cnt = k1 - k0 + 1;
      E[b] = e / cnt; NFb[b] = n2 / cnt; TN[b] = t2 / cnt;
      emax = std::max(emax, E[b]);
    }
    std::vector<int> pk(NB, 0);
    for (const auto& p : peaks) { const int b = bandOf(p.f); if (b >= 0) pk[b] = 1; }
    double L[NB];
    for (int b = 0; b < NB; ++b) L[b] = std::max(-12.0, std::log10(E[b] / emax + 1e-14)); // log10 energii względem najsilniejszego pasma
    auto Lb = [&](int b) { return b >= 0 && b < NB ? L[b] : -12.0; };
    prevMask_ = mask_;
    for (int b = 0; b < NB; ++b) {
      float* f = &feat_[b * NF];
      f[0] = (float)(L[b] / 6.0);
      f[1] = (float)((L[b] - Lb(b - 2)) / 6.0); f[2] = (float)((L[b] - Lb(b - 1)) / 6.0);
      f[3] = (float)((L[b] - Lb(b + 1)) / 6.0); f[4] = (float)((L[b] - Lb(b + 2)) / 6.0);
      f[5] = (float)((L[b] - prev1_[b]) / 6.0); f[6] = (float)((L[b] - prev2_[b]) / 6.0);
      f[7] = (float)clampd(std::log10(E[b] / (NFb[b] + 1e-30)) / 4.0, -2, 2);
      f[8] = tnoise.empty() ? 0.f : (float)clampd(std::log10(E[b] / (TN[b] + 1e-30)) / 4.0, -2, 2);
      f[9] = (float)(b / (double)NB);
      f[10] = level;
      f[11] = (float)pk[b];
      f[12] = (float)((L[b] - Lb(b - 24)) / 6.0); f[13] = (float)((L[b] - Lb(b + 24)) / 6.0); f[14] = (float)((L[b] - Lb(b - 38)) / 6.0);
      mask_[b] = kMaskReady ? maskPredict(f) : 1.f;
    }
    for (int b = 0; b < NB; ++b) { prev2_[b] = prev1_[b]; prev1_[b] = L[b]; }
    have_ = true;
  }
  // klatka bez widma (cisza): poprzednie klatki "puste"
  void silent() {
    if ((int)prev1_.size() != NB) reset();
    for (int b = 0; b < NB; ++b) { prev2_[b] = prev1_[b]; prev1_[b] = -12.0; }
    prevMask_ = mask_;
    std::fill(mask_.begin(), mask_.end(), 0.f);
  }

  float at(double f) const { const int b = bandOf(f); return b >= 0 && !mask_.empty() ? mask_[b] : 1.f; }
  float prevAt(double f) const { const int b = bandOf(f); return b >= 0 && !prevMask_.empty() ? prevMask_[b] : 0.f; }
  const std::vector<float>& mask() const { return mask_; }
  const std::vector<float>& features() const { return feat_; }

private:
  std::vector<double> prev1_, prev2_;
  std::vector<float> mask_, prevMask_, feat_;
  bool have_ = false;
};

} // namespace gt
