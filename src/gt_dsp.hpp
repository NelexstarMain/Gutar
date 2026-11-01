// gt_dsp.hpp - podstawowe bloki DSP: FFT, decymator, bufor kołowy, okna.
// Czysty C++17, bez zależności poza biblioteką standardową.
#pragma once
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <vector>

namespace gt {

constexpr double kPi = 3.14159265358979323846;

// ---------------------------------------------------------------- FFT radix-2
class FFT {
public:
  FFT() = default;
  explicit FFT(int n) { init(n); }

  void init(int n) {
    n_ = n;
    int levels = 0;
    while ((1 << levels) < n) ++levels;
    cos_.assign(n / 2, 0.0);
    sin_.assign(n / 2, 0.0);
    for (int i = 0; i < n / 2; ++i) {
      cos_[i] = std::cos(2.0 * kPi * i / n);
      sin_[i] = std::sin(2.0 * kPi * i / n);
    }
    rev_.assign(n, 0);
    for (int i = 0; i < n; ++i) {
      uint32_t r = 0;
      for (int b = 0; b < levels; ++b) r |= ((i >> b) & 1u) << (levels - 1 - b);
      rev_[i] = r;
    }
  }

  int size() const { return n_; }

  // transformata w przód, w miejscu
  void forward(double* re, double* im) const {
    const int n = n_;
    for (int i = 0; i < n; ++i) {
      const int j = (int)rev_[i];
      if (j > i) {
        std::swap(re[i], re[j]);
        std::swap(im[i], im[j]);
      }
    }
    for (int size = 2; size <= n; size <<= 1) {
      const int half = size >> 1, step = n / size;
      for (int i = 0; i < n; i += size) {
        for (int j = i, k = 0; j < i + half; ++j, k += step) {
          const int l = j + half;
          const double tr = re[l] * cos_[k] + im[l] * sin_[k];
          const double ti = -re[l] * sin_[k] + im[l] * cos_[k];
          re[l] = re[j] - tr;
          im[l] = im[j] - ti;
          re[j] += tr;
          im[j] += ti;
        }
      }
    }
  }

private:
  int n_ = 0;
  std::vector<double> cos_, sin_;
  std::vector<uint32_t> rev_;
};

inline std::vector<double> hann(int n) {
  std::vector<double> w(n);
  for (int i = 0; i < n; ++i) w[i] = 0.5 - 0.5 * std::cos(2.0 * kPi * i / n);
  return w;
}

// -------------------------------------------- strumieniowy decymator (FIR sinc)
// Okno Blackmana, odcięcie 0.42 * fs_out. Zachowuje stan między wywołaniami.
class Decimator {
public:
  void init(int D) {
    D_ = std::max(1, D);
    const int T = 12 * D_ + 1;
    const double fc = 0.42 / D_, mid = (T - 1) / 2.0;
    h_.assign(T, 0.f);
    double sum = 0;
    std::vector<double> tmp(T);
    for (int i = 0; i < T; ++i) {
      const double x = i - mid;
      const double s = (x == 0) ? 2 * fc : std::sin(2 * kPi * fc * x) / (kPi * x);
      const double w = 0.42 - 0.5 * std::cos(2 * kPi * i / (T - 1)) + 0.08 * std::cos(4 * kPi * i / (T - 1));
      tmp[i] = s * w;
      sum += tmp[i];
    }
    for (int i = 0; i < T; ++i) h_[i] = (float)(tmp[i] / sum);
    hist_.assign(T - 1, 0.f);
    next_ = T - 1;
  }

  int factor() const { return D_; }

  // dopisuje zdecymowane próbki do `out`
  void process(const float* in, int n, std::vector<float>& out) {
    const int T = (int)h_.size(), H = T - 1;
    work_.resize((size_t)H + n);
    std::copy(hist_.begin(), hist_.end(), work_.begin());
    std::copy(in, in + n, work_.begin() + H);
    const float* x = work_.data();
    const float* h = h_.data();
    int p = next_;
    const int total = H + n;
    while (p < total) {
      float s = 0;
      for (int j = 0; j < T; ++j) s += h[j] * x[p - j];
      out.push_back(s);
      p += D_;
    }
    next_ = p - n;
    std::copy(work_.begin() + (total - H), work_.begin() + total, hist_.begin());
  }

private:
  int D_ = 1, next_ = 0;
  std::vector<float> h_, hist_, work_;
};

// ------------------------------------------------------------- bufor kołowy
class Ring {
public:
  void init(int cap) {
    b_.assign(cap, 0.f);
    cap_ = cap;
    w_ = 0;
    total_ = 0;
  }
  void push(const float* a, int n) {
    for (int i = 0; i < n; ++i) {
      b_[w_] = a[i];
      if (++w_ == cap_) w_ = 0;
    }
    total_ += n;
  }
  // ostatnie n próbek, od najstarszej
  void last(int n, float* out) const {
    int r = ((w_ - n) % cap_ + cap_) % cap_;
    for (int i = 0; i < n; ++i) {
      out[i] = b_[r];
      if (++r == cap_) r = 0;
    }
  }
  int64_t total() const { return total_; }

private:
  std::vector<float> b_;
  int cap_ = 1, w_ = 0;
  int64_t total_ = 0;
};

inline double midiFreq(double m, double a4 = 440.0) { return a4 * std::pow(2.0, (m - 69.0) / 12.0); }
inline double freqMidi(double f, double a4 = 440.0) { return 69.0 + 12.0 * std::log2(f / a4); }
inline double clampd(double v, double a, double b) { return v < a ? a : (v > b ? b : v); }

} // namespace gt
