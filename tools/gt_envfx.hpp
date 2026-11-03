// gt_envfx.hpp - wspólne "otoczenie" dla generatorów danych (gen_env, gen_classical): kąt mikrofonu, szum o losowej barwie,
// stałe tony, brum, stuki, kliknięcia, hałas przerywany. Wydzielone z tools/gen_env.cpp bez zmian (te same ziarna = te same nagrania).
#pragma once
#include <string>
#include <vector>
#include "../src/gt_synth.hpp"

namespace envfx {
using namespace gt;
static const int FS = 22050;

struct OnePole { double a = 0, z = 0; float lp(float x) { z += a * (x - z); return (float)z; } };

// "kąt mikrofonu": kilka losowych filtrów pasmowych + wczesne odbicie (filtr grzebieniowy) + nachylenie widma
static void micAngle(Rng& r, std::vector<float>& x) {
  const int nf = r.range(1, 4);
  for (int i = 0; i < nf; ++i) detail::Biquad::peaking(FS, std::exp(r.uni(std::log(80.0), std::log(7000.0))), r.uni(-10, 9), r.uni(0.6, 4)).run(x);
  if (r.uni() < 0.7) {
    const int d = (int)(r.uni(0.0004, 0.008) * FS);
    const double g = r.uni(0.15, 0.7) * (r.uni() < 0.5 ? -1 : 1);
    for (size_t i = x.size(); i-- > (size_t)d;) x[i] += (float)(g * x[i - d]);
  }
  const double tilt = r.uni(-0.6, 0.6); // <0: ciemniej, >0: jaśniej
  OnePole lp; lp.a = 0.25;
  for (auto& v : x) { const float l = lp.lp(v); v = (float)(v + tilt * (v - l) * 0.8); }
}

static std::vector<float> colored(Rng& r, size_t n) {
  std::vector<float> o(n);
  const double a = r.uni(0.01, 1.0); // 1 = biały, małe = brązowy
  const double hp = r.uni() < 0.5 ? r.uni(0.0, 0.9) : 0.0; // czasem przewaga wysokich
  double z = 0, prev = 0;
  for (size_t i = 0; i < n; ++i) {
    const double w = r.gauss();
    z += a * (w - z);
    const double y = z - hp * prev;
    prev = z;
    o[i] = (float)y;
  }
  return o;
}

static double rmsv(const std::vector<float>& x) { double s = 0; for (float v : x) s += (double)v * v; return std::sqrt(s / std::max<size_t>(1, x.size())) + 1e-12; }

static void addScaled(std::vector<float>& mix, const std::vector<float>& src, double target) {
  const double k = target / rmsv(src);
  for (size_t i = 0; i < mix.size(); ++i) mix[i] += (float)(src[i] * k);
}

struct EnvDesc { std::string parts; };

static void environment(Rng& r, std::vector<float>& noise, double gRms, double gPeak, EnvDesc& d) {
  const size_t n = noise.size();
  auto snr = [&](double lo, double hi) { return gRms / std::pow(10.0, r.uni(lo, hi) / 20.0); };
  // 1. szum szerokopasmowy o losowej barwie, czasem powoli falujący
  if (r.uni() < 0.85) {
    std::vector<float> s = colored(r, n);
    if (r.uni() < 0.4) {
      const double f = r.uni(0.05, 0.6), dep = r.uni(0.2, 0.9), ph = r.uni(0, 6.28);
      for (size_t i = 0; i < n; ++i) s[i] *= (float)(1 - dep * 0.5 * (1 + std::sin(2 * kPi * f * i / FS + ph)));
    }
    addScaled(noise, s, snr(3, 40)); d.parts += "szum ";
  }
  // 2. stałe tony (wentylator, zasilacz, silnik z harmonicznymi), lekko pływające
  if (r.uni() < 0.55) {
    const int nt = r.range(1, 5);
    for (int k = 0; k < nt; ++k) {
      std::vector<float> s(n);
      const double f = std::exp(r.uni(std::log(60.0), std::log(4500.0))), drift = r.uni(0, 0.004);
      const int nh = r.uni() < 0.4 ? r.range(2, 6) : 1;
      double ph = r.uni(0, 6.28);
      for (size_t i = 0; i < n; ++i) {
        const double fi = f * (1 + drift * std::sin(2 * kPi * 0.13 * i / FS));
        ph += 2 * kPi * fi / FS;
        double v = 0;
        for (int h = 1; h <= nh; ++h) v += std::sin(h * ph) / h;
        s[i] = (float)v;
      }
      addScaled(noise, s, snr(12, 45));
    }
    d.parts += "tony ";
  }
  // 3. brum sieci 50/60 Hz z losowymi harmonicznymi
  if (r.uni() < 0.3) {
    std::vector<float> s(n);
    const double f = r.uni() < 0.5 ? 50 : 60;
    double a[6]; for (auto& x : a) x = r.uni(0, 1);
    for (size_t i = 0; i < n; ++i) { double v = 0; for (int h = 0; h < 6; ++h) v += a[h] * std::sin(2 * kPi * f * (h + 1) * i / FS + h); s[i] = (float)v; }
    addScaled(noise, s, snr(15, 40)); d.parts += "brum ";
  }
  // 4. stuki: wygasające rezonanse (stół, pudło, krok) + krótki szum, każdy z innego kierunku (własny filtr), różna głośność
  if (r.uni() < 0.75) {
    const double rate = r.uni(0.1, 2.0);
    double t = r.uni(0, 1.0 / rate);
    while (t < n / (double)FS) {
      const size_t i0 = (size_t)(t * FS);
      const size_t L = std::min<size_t>(n - i0, (size_t)(0.35 * FS));
      std::vector<float> s(L, 0.f);
      const int nm = r.range(1, 3);
      for (int k = 0; k < nm; ++k) {
        const double f = std::exp(r.uni(std::log(60.0), std::log(3500.0))), tau = r.uni(0.004, 0.09), a = r.uni(0.3, 1.0);
        for (size_t i = 0; i < L; ++i) s[i] += (float)(a * std::exp(-(double)i / FS / tau) * std::sin(2 * kPi * f * i / FS));
      }
      const size_t nb = (size_t)(r.uni(0.001, 0.012) * FS);
      for (size_t i = 0; i < nb && i < L; ++i) s[i] += (float)(r.gauss() * (1 - (double)i / nb));
      micAngle(r, s);
      const double peak = gPeak * std::pow(10.0, r.uni(-36, 4) / 20.0);
      double mx = 1e-9; for (float v : s) mx = std::max(mx, (double)std::fabs(v));
      for (size_t i = 0; i < L; ++i) noise[i0 + i] += (float)(s[i] * peak / mx);
      t += -std::log(r.uni() + 1e-9) / rate;
    }
    d.parts += "stuki ";
  }
  // 5. kliknięcia (pojedyncze impulsy)
  if (r.uni() < 0.35) {
    const double rate = r.uni(0.2, 4);
    double t = 0;
    while ((t += -std::log(r.uni() + 1e-9) / rate) < n / (double)FS) {
      const size_t i0 = (size_t)(t * FS);
      const double a = gPeak * std::pow(10.0, r.uni(-40, -6) / 20.0) * (r.uni() < 0.5 ? -1 : 1);
      for (int k = 0; k < 3 && i0 + k < n; ++k) noise[i0 + k] += (float)(a * (k == 0 ? 1 : -0.5));
    }
    d.parts += "klik ";
  }
  // 6. hałas przerywany: pasmowy szum z rytmem sylab (rozmowa w tle, ruch), losowe odcinki
  if (r.uni() < 0.35) {
    std::vector<float> s(n, 0.f);
    double t = r.uni(0, 2);
    while (t < n / (double)FS) {
      const double len = r.uni(0.4, 3.0), fs4 = r.uni(3, 6), fc = std::exp(r.uni(std::log(250.0), std::log(2500.0)));
      const size_t a = (size_t)(t * FS), b = std::min(n, (size_t)((t + len) * FS));
      detail::Biquad bp = detail::Biquad::peaking(FS, fc, 18, 1.2);
      std::vector<float> seg(b - a);
      for (auto& v : seg) v = (float)r.gauss() * 0.05f;
      bp.run(seg);
      for (size_t i = a; i < b; ++i) s[i] = seg[i - a] * (float)(0.5 + 0.5 * std::sin(2 * kPi * fs4 * (i - a) / FS));
      t += len + r.uni(0.3, 4);
    }
    addScaled(noise, s, snr(5, 30)); d.parts += "rozmowa ";
  }
}

} // namespace envfx
