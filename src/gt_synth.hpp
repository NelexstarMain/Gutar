// gt_synth.hpp - syntezator szarpanej struny (addytywny, z nieharmonicznością,
// dudnieniem polaryzacji, ślizgiem wysokości przy ataku i rezonansem pudła).
// Używany do: (1) odtwarzania transkrypcji w przeglądarce, (2) generowania
// korpusu testowego z różnymi zniekształceniami.
#pragma once
#include <string>
#include "gt_dsp.hpp"

namespace gt {

struct Rng {
  uint64_t s;
  explicit Rng(uint64_t seed = 1) : s(seed * 0x9E3779B97F4A7C15ull + 0x1234567ull) {}
  uint64_t next() {
    uint64_t z = (s += 0x9E3779B97F4A7C15ull);
    z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9ull;
    z = (z ^ (z >> 27)) * 0x94D049BB133111EBull;
    return z ^ (z >> 31);
  }
  double uni() { return (double)(next() >> 11) * (1.0 / 9007199254740992.0); }
  double uni(double a, double b) { return a + (b - a) * uni(); }
  double gauss() {
    const double u = uni() + 1e-12, v = uni();
    return std::sqrt(-2.0 * std::log(u)) * std::cos(2.0 * kPi * v);
  }
  int range(int a, int b) { return a + (int)(uni() * (b - a + 1)); } // obustronnie domknięty
};

struct NoteEvent {
  double t0 = 0, t1 = 0; // początek i moment puszczenia struny [s]
  int midi = 60;
  float vel = 0.8f;      // 0..1
};

struct SynthOptions {
  double globalCents = 0;  // przestrojenie całego instrumentu
  double noteCentsSd = 0;  // losowe przestrojenie każdej nuty (odch. std.)
  bool varied = false;     // losowa nieharmoniczność, miejsce szarpnięcia, zanik (korpus testowy)
  bool body = true;        // rezonanse pudła
  double gain = 0.2;
  uint64_t seed = 1;
  int maxPartials = 60;    // ile alikwotów na nutę (mniej = szybciej)
  double minRel = 1e-3;    // pomijaj alikwoty słabsze niż to (względem amplitudy nuty)
};

namespace detail {

struct Biquad {
  double b0 = 1, b1 = 0, b2 = 0, a1 = 0, a2 = 0;
  static Biquad peaking(double fs, double f0, double gainDb, double q) {
    const double A = std::pow(10.0, gainDb / 40.0), w0 = 2 * kPi * f0 / fs, al = std::sin(w0) / (2 * q);
    const double a0 = 1 + al / A;
    Biquad b;
    b.b0 = (1 + al * A) / a0;
    b.b1 = -2 * std::cos(w0) / a0;
    b.b2 = (1 - al * A) / a0;
    b.a1 = -2 * std::cos(w0) / a0;
    b.a2 = (1 - al / A) / a0;
    return b;
  }
  void run(std::vector<float>& x) const {
    double z1 = 0, z2 = 0;
    for (auto& v : x) {
      const double in = v, out = b0 * in + z1;
      z1 = b1 * in - a1 * out + z2;
      z2 = b2 * in - a2 * out;
      v = (float)out;
    }
  }
};

// jeden częściowy ton z zanikiem wykładniczym; ślizg wysokości tylko na początku
inline void addPartial(float* out, int64_t n0, int64_t nEnd, int64_t nRel, double fs, double f, double a,
                       double tau, double phase, double glideCents, double glideTau) {
  const double w = 2 * kPi * f / fs, dec = std::exp(-1.0 / (tau * fs));
  double env = a;
  int64_t n = n0;
  double ph = phase;
  if (glideCents != 0) {
    const int64_t gEnd = std::min<int64_t>(nEnd, n0 + (int64_t)(glideTau * 5 * fs));
    const double k = glideCents * 0.0005776227;
    for (; n < gEnd; ++n) {
      const double t = (double)(n - n0) / fs;
      const double ramp = (n - n0) < 30 ? (double)(n - n0) / 30.0 : 1.0;
      double rel = 1.0;
      if (n >= nRel) rel = std::max(0.0, 1.0 - (double)(n - nRel) / (double)std::max<int64_t>(1, nEnd - nRel));
      out[n] += (float)(env * std::sin(ph) * ramp * rel);
      ph += w * (1.0 + k * std::exp(-t / glideTau));
      env *= dec;
    }
  }
  double c = std::cos(ph), s = std::sin(ph);
  const double dc = std::cos(w), ds = std::sin(w);
  for (; n < nEnd; ++n) {
    const double ramp = (n - n0) < 30 ? (double)(n - n0) / 30.0 : 1.0;
    double rel = 1.0;
    if (n >= nRel) rel = std::max(0.0, 1.0 - (double)(n - nRel) / (double)std::max<int64_t>(1, nEnd - nRel));
    out[n] += (float)(env * s * ramp * rel);
    const double c2 = c * dc - s * ds;
    s = s * dc + c * ds;
    c = c2;
    env *= dec;
  }
}

} // namespace detail

// rezonanse pudła gitary akustycznej + łagodne zaokrąglenie góry (filtr liniowy, można stosować po zsumowaniu)
inline void applyBody(std::vector<float>& mix, int fs) {
  detail::Biquad::peaking(fs, 98, 6.0, 4.0).run(mix);
  detail::Biquad::peaking(fs, 205, 4.0, 5.0).run(mix);
  detail::Biquad::peaking(fs, 430, 3.0, 6.0).run(mix);
  detail::Biquad::peaking(fs, 1250, -3.0, 3.0).run(mix);
  float lp = 0;
  for (auto& v : mix) { lp += 0.55f * (v - lp); v = lp * 0.85f + v * 0.15f; }
}

// Dodaje nuty do bufora `out` (o długości `n` próbek). Zwraca rzeczywiste f0 każdej nuty (do testów).
inline std::vector<double> renderNotes(float* out, size_t n, int fs, const std::vector<NoteEvent>& ev,
                                       const SynthOptions& o, std::vector<double>* audibleEnd = nullptr) {
  Rng r(o.seed);
  std::vector<double> freqs;
  freqs.reserve(ev.size());
  std::vector<float> mixBuf;
  if (o.body) mixBuf.assign(n, 0.f);
  std::vector<float>& mix = mixBuf;
  float* dst = o.body ? mixBuf.data() : out;
  for (const auto& e : ev) {
    const double cents = o.globalCents + (o.noteCentsSd > 0 ? o.noteCentsSd * r.gauss() : 0.0);
    const double f0 = 440.0 * std::pow(2.0, (e.midi - 69) / 12.0 + cents / 1200.0);
    freqs.push_back(f0);
    const double B = o.varied ? std::exp(r.uni(std::log(4e-5), std::log(5e-4))) : 1.5e-4;
    const double pos = o.varied ? r.uni(0.08, 0.30) : 0.15;
    const double slope = o.varied ? r.uni(1.0, 1.5) : 1.2;
    const double tau1 = (o.varied ? r.uni(0.9, 3.0) : 2.0) * std::pow(110.0 / f0, 0.3);
    const double kdec = o.varied ? r.uni(0.1, 0.5) : 0.3;
    const double amp = o.gain * std::pow((double)e.vel, 1.3);
    const double glide = o.varied ? r.uni(0, 18) * e.vel : 6.0 * e.vel;
    const int64_t n0 = (int64_t)std::llround(e.t0 * fs);
    if (n0 >= (int64_t)n) { if (audibleEnd) audibleEnd->push_back(e.t0); continue; }
    const int64_t nRel = (int64_t)std::llround(std::max(e.t1, e.t0 + 0.05) * fs);
    const int64_t nEnd = std::min<int64_t>((int64_t)n, std::min<int64_t>(nRel + (int64_t)(0.06 * fs), n0 + (int64_t)(tau1 * 9.2 * fs)));
    if (nEnd <= n0) { if (audibleEnd) audibleEnd->push_back(e.t0); continue; }
    double domA = -1, domTau = tau1;
    for (int h = 1; h <= o.maxPartials; ++h) {
      const double fh = h * f0 * std::sqrt(1 + B * h * h);
      if (fh > 0.45 * fs || fh > 9000) break;
      double a = std::fabs(std::sin(kPi * h * pos)) / std::pow((double)h, slope);
      if (h == 1 && f0 < 110) a *= 0.5; // słaba prima na basowych strunach
      a *= amp * 2;
      if (a < amp * 2 * o.minRel) continue;
      const double tau = tau1 / (1 + kdec * (h - 1));
      if (a > domA) { domA = a; domTau = tau; }
      const double ph = r.uni(0, 2 * kPi);
      if (o.varied && h <= 8) {
        const double eps = r.uni(0.1, 0.35), d = r.uni(0.05, 0.9);
        detail::addPartial(dst, n0, nEnd, nRel, fs, fh, a * (1 - eps), tau, ph, h == 1 ? glide : glide * 0.5, 0.09);
        detail::addPartial(dst, n0, nEnd, nRel, fs, fh + d, a * eps, tau, r.uni(0, 2 * kPi), 0, 0.09);
      } else {
        detail::addPartial(dst, n0, nEnd, nRel, fs, fh, a, tau, ph, h == 1 ? glide : glide * 0.5, 0.09);
      }
    }
    if (audibleEnd) audibleEnd->push_back(std::min(e.t1, e.t0 + domTau * std::log(100.0))); // -40 dB dominującego alikwotu
    // krótki szum szarpnięcia
    const int64_t nb = (int64_t)(0.006 * fs);
    double lp = 0;
    for (int64_t i = 0; i < nb && n0 + i < (int64_t)n; ++i) {
      lp = 0.6 * lp + 0.4 * (r.uni() * 2 - 1);
      dst[n0 + i] += (float)(lp * amp * 0.9 * (1.0 - (double)i / nb));
    }
  }
  if (o.body) {
    applyBody(mix, fs);
    for (size_t i = 0; i < n; ++i) out[i] += mix[i];
  }
  return freqs;
}

// ------------------------------------------------------------ szum i pogłos
inline double rmsOf(const float* x, size_t a, size_t b) {
  double s = 0;
  for (size_t i = a; i < b; ++i) s += (double)x[i] * x[i];
  return std::sqrt(s / std::max<size_t>(1, b - a));
}

inline void schroederReverb(std::vector<float>& x, int fs, double rt60, double wet) {
  const double sc = fs / 44100.0;
  const int combs[4] = {1687, 1601, 2053, 2251};
  std::vector<float> acc(x.size(), 0.f);
  for (int ci = 0; ci < 4; ++ci) {
    const int d = (int)std::round(combs[ci] * sc);
    const double g = std::pow(10.0, -3.0 * d / (rt60 * fs));
    std::vector<float> buf(d, 0.f);
    int p = 0;
    double lp = 0;
    for (size_t i = 0; i < x.size(); ++i) {
      const double y = buf[p];
      lp = 0.6 * lp + 0.4 * y;
      buf[p] = (float)(x[i] + g * lp);
      if (++p == d) p = 0;
      acc[i] += (float)(y * 0.25);
    }
  }
  for (size_t i = 0; i < x.size(); ++i) x[i] = (float)(x[i] * (1 - wet) + acc[i] * wet * 1.6);
}

// typy: "white", "pink", "hum", "mix"; snrDb względem RMS sygnału na odcinku [a,b)
inline void addNoise(std::vector<float>& x, int fs, const std::string& type, double snrDb, uint64_t seed, size_t a, size_t b) {
  if (type == "none") return;
  Rng r(seed * 7919 + 13);
  const size_t n = x.size();
  const double sig = rmsOf(x.data(), a, b);
  std::vector<double> nz(n, 0.0);
  auto pink = [&](std::vector<double>& o, double scale) {
    double b0 = 0, b1 = 0, b2 = 0, b3 = 0, b4 = 0, b5 = 0, b6 = 0;
    for (size_t i = 0; i < n; ++i) {
      const double w = r.gauss();
      b0 = 0.99886 * b0 + w * 0.0555179; b1 = 0.99332 * b1 + w * 0.0750759; b2 = 0.969 * b2 + w * 0.153852;
      b3 = 0.8665 * b3 + w * 0.3104856;  b4 = 0.55 * b4 + w * 0.5329522;   b5 = -0.7616 * b5 - w * 0.016898;
      o[i] += scale * (b0 + b1 + b2 + b3 + b4 + b5 + b6 + w * 0.5362);
      b6 = w * 0.115926;
    }
  };
  if (type == "white") for (size_t i = 0; i < n; ++i) nz[i] = r.gauss();
  else if (type == "pink") pink(nz, 1.0);
  else if (type == "hum") {
    const double amps[5] = {1, 0.6, 0.35, 0.2, 0.12};
    for (int k = 0; k < 5; ++k)
      for (size_t i = 0; i < n; ++i) nz[i] += amps[k] * std::sin(2 * kPi * 50 * (k + 1) * (double)i / fs + k);
    for (size_t i = 0; i < n; ++i) nz[i] += 0.02 * r.gauss();
  } else if (type == "mix") {
    pink(nz, 0.6);
    for (size_t i = 0; i < n; ++i)
      nz[i] += 0.25 * r.gauss() + 0.25 * std::sin(2 * kPi * 50 * (double)i / fs) + 0.12 * std::sin(2 * kPi * 150 * (double)i / fs);
  }
  double e = 0;
  for (double v : nz) e += v * v;
  e = std::sqrt(e / std::max<size_t>(1, n)) + 1e-12;
  const double k = sig / std::pow(10.0, snrDb / 20.0) / e;
  for (size_t i = 0; i < n; ++i) x[i] += (float)(nz[i] * k);
}

} // namespace gt
