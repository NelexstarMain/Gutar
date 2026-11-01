// gt_spectrum.hpp - widmo (okno Hanna + dopełnienie zerami), lokalny poziom szumu,
// wybór pików z interpolacją paraboliczną oraz detektor uderzeń (spectral flux).
#pragma once
#include "gt_dsp.hpp"

namespace gt {

struct Peak {
  float f = 0, a = 0; // częstotliwość [Hz], amplituda (liniowo, 1.0 = pełna skala)
  bool hum = false;   // częściowy ton brumu sieciowego
};

struct PeakOptions {
  int mains = 0;          // 50 / 60 / 0 = wyłączony filtr brumu
  double minAmp = 1e-4;   // minimalna amplituda piku
  double noiseK = 4.5;    // krotność lokalnego szumu
  double fmin = 60, fmax = 5000;
  double dynDb = 48;      // dynamika względem najsilniejszego piku
};

class Spectrum {
public:
  void init(int N, double fs, int zp = 2) {
    N_ = N; fs_ = fs; M_ = N * zp; K_ = M_ / 2;
    fft_.init(M_);
    win_ = hann(N);
    re_.assign(M_, 0.0); im_.assign(M_, 0.0);
    mag_.assign(K_, 0.0); nf_.assign(K_, 0.0); cs_.assign(K_ + 1, 0.0);
    binHz_ = fs / M_;
  }
  int N() const { return N_; }
  int bins() const { return K_; }
  double binHz() const { return binHz_; }
  const std::vector<double>& mag() const { return mag_; }
  const std::vector<double>& noiseFloor() const { return nf_; }

  // x: N próbek
  void compute(const float* x) {
    double mean = 0;
    for (int i = 0; i < N_; ++i) mean += x[i];
    mean /= N_;
    for (int i = 0; i < N_; ++i) { re_[i] = (x[i] - mean) * win_[i]; im_[i] = 0; }
    for (int i = N_; i < M_; ++i) { re_[i] = 0; im_[i] = 0; }
    fft_.forward(re_.data(), im_.data());
    const double sc = 4.0 / N_;
    for (int k = 0; k < K_; ++k) mag_[k] = std::sqrt(re_[k] * re_[k] + im_[k] * im_[k]) * sc;
    // lokalny szum = średnia geometryczna widma w oknie +-100 Hz
    cs_[0] = 0;
    for (int k = 0; k < K_; ++k) cs_[k + 1] = cs_[k] + std::log(mag_[k] + 1e-9);
    const int W = std::max(6, (int)std::lround(100.0 / binHz_));
    for (int k = 0; k < K_; ++k) {
      const int a = std::max(0, k - W), b = std::min(K_, k + W + 1);
      nf_[k] = std::exp((cs_[b] - cs_[a]) / (b - a));
    }
  }

  // piki posortowane rosnąco po częstotliwości
  void pickPeaks(const PeakOptions& o, std::vector<Peak>& res) const {
    res.clear();
    const double bh = binHz_;
    const int k0 = std::max(2, (int)std::floor(o.fmin / bh)), k1 = std::min(K_ - 2, (int)std::floor(o.fmax / bh));
    cand_.clear();
    for (int k = k0; k < k1; ++k) {
      const double m = mag_[k];
      if (m > mag_[k - 1] && m >= mag_[k + 1] && m > o.minAmp && m > o.noiseK * nf_[k]) {
        const double a = std::log(mag_[k - 1] + 1e-12), b = std::log(m + 1e-12), c = std::log(mag_[k + 1] + 1e-12);
        const double den = a - 2 * b + c;
        const double d = den < 0 ? 0.5 * (a - c) / den : 0.0;
        const double fr = (k + d) * bh;
        Peak p;
        p.f = (float)fr;
        p.a = (float)std::exp(b - 0.25 * (a - c) * d);
        p.hum = o.mains && fr < 900 && std::fabs(fr - o.mains * std::round(fr / o.mains)) < 0.5;
        cand_.push_back(p);
      }
    }
    if (cand_.empty()) return;
    std::sort(cand_.begin(), cand_.end(), [](const Peak& p, const Peak& q) { return p.a > q.a; });
    double amax = 0;
    for (const auto& p : cand_) if (!p.hum && p.a > amax) amax = p.a;
    if (amax <= 0) return;
    const double lim = amax * std::pow(10.0, -o.dynDb / 20.0), excl = 3.3 * fs_ / N_;
    kept_.clear();
    for (const auto& p : cand_) {
      if (p.a < lim) break;
      bool side = false;
      for (const auto& q : kept_)
        if (std::fabs(p.f - q.f) < excl && p.a < 0.1 * q.a) { side = true; break; }
      if (!side) kept_.push_back(p);
    }
    for (const auto& p : kept_) if (!p.hum) res.push_back(p);
    std::sort(res.begin(), res.end(), [](const Peak& p, const Peak& q) { return p.f < q.f; });
  }

private:
  int N_ = 0, M_ = 0, K_ = 0;
  double fs_ = 11025, binHz_ = 1;
  FFT fft_;
  std::vector<double> win_, re_, im_, mag_, nf_, cs_;
  mutable std::vector<Peak> cand_, kept_;
};

// --------------------------------------------------------- detektor uderzeń
// Spectral flux w skali logarytmicznej (okno 512, krok 128) z maksymalnym filtrem
// po sąsiednich binach (tłumi vibrato) i adaptacyjnym progiem opartym na medianie.
class OnsetDetector {
public:
  void init(double fsd) {
    fsd_ = fsd;
    fft_.init(512);
    win_ = hann(512);
    re_.assign(512, 0.0); im_.assign(512, 0.0);
    left_.clear(); gpos_ = 0; havePrev_ = false; hist_.clear(); tt_.clear(); last_ = -1;
  }
  // dopisuje czasy wykrytych uderzeń [s] do `out`
  void push(const float* d, int n, std::vector<double>& out) {
    left_.insert(left_.end(), d, d + n);
    size_t p = 0;
    while (p + 512 <= left_.size()) {
      for (int i = 0; i < 512; ++i) { re_[i] = left_[p + i] * win_[i]; im_[i] = 0; }
      fft_.forward(re_.data(), im_.data());
      double L[190];
      for (int k = 0; k < 190; ++k) L[k] = 0;
      for (int k = 4; k < 190; ++k) L[k] = std::log(1 + 100 * std::sqrt(re_[k] * re_[k] + im_[k] * im_[k]) / 128);
      double f = 0;
      if (havePrev_)
        for (int k = 4; k < 189; ++k) {
          const double m = std::max(prev_[k - 1], std::max(prev_[k], prev_[k + 1]));
          const double dd = L[k] - m;
          if (dd > 0) f += dd;
        }
      for (int k = 0; k < 190; ++k) prev_[k] = L[k];
      havePrev_ = true;
      const double tEnd = (double)(gpos_ + (int64_t)p + 512) / fsd_;
      hist_.push_back(f); tt_.push_back(tEnd);
      if (hist_.size() > 180) { hist_.erase(hist_.begin()); tt_.erase(tt_.begin()); }
      const size_t m = hist_.size();
      if (m >= 3) {
        const double a = hist_[m - 3], b = hist_[m - 2], c = hist_[m - 1];
        if (b > a && b >= c) {
          sorted_ = hist_;
          std::nth_element(sorted_.begin(), sorted_.begin() + sorted_.size() / 2, sorted_.end());
          const double med = sorted_[sorted_.size() / 2];
          const double thr = std::max(7.0, 1.6 * med + 4), tp = tt_[m - 2] - 0.045;
          if (b > thr && tp - last_ > 0.12) { last_ = tp; out.push_back(tp); }
        }
      }
      p += 128;
    }
    left_.erase(left_.begin(), left_.begin() + p);
    gpos_ += (int64_t)p;
  }

private:
  double fsd_ = 11025;
  FFT fft_;
  std::vector<double> win_, re_, im_, hist_, tt_, sorted_;
  std::vector<float> left_;
  double prev_[190] = {0};
  bool havePrev_ = false;
  int64_t gpos_ = 0;
  double last_ = -1;
};

} // namespace gt
