// gen_env.cpp - losowe "środowiska" do uczenia i testu modeli: gitara (losowa treść i dynamika) w losowym pokoju, pod losowym
// kątem mikrofonu, z losowymi szumami, tonami, stukami, kliknięciami i hałasem przerywanym. Każde nagranie losuje wszystko od nowa
// (żaden schemat się nie powtarza), więc model nie może nauczyć się konkretnego szumu ani utworu.
//
// Użycie: gen_env <katalog> <ziarno_początkowe> <liczba_nagrań>
// Wyjście dla każdego nagrania: <id>.wav (mikrofon: gitara + otoczenie), <id>.clean.wav (sama gitara w tym samym pokoju i pod tym
// samym kątem, ta sama skala), <id>.truth.json (nuty: midi, t0, t1, ta = koniec słyszalności, f; opis środowiska).
#include <cstdio>
#include <string>
#include "../src/gt_synth.hpp"
#include "wavio.hpp"

using namespace gt;

static const int kOpen[6] = {40, 45, 50, 55, 59, 64};
static const int FS = 22050;

// ------------------------------------------------------------ treść muzyczna
// losowy chwyt możliwy do zagrania: pozycja ręki p, na każdej strunie próg z [p, p+3], pusta (gdy p małe) albo stłumiona
static std::vector<int> randomVoicing(Rng& r) {
  std::vector<int> v;
  const int p = r.uni() < 0.4 ? 0 : r.range(1, 12);
  const int lowest = r.range(0, 2); // od której struny gramy
  for (int s = lowest; s < 6; ++s) {
    const double u = r.uni();
    if (u < 0.15 && s > lowest) continue; // stłumiona
    int fr = (p == 0 && u < 0.45) ? 0 : p + r.range(0, 3);
    if (p > 0 && fr == p + 3 && r.uni() < 0.5) fr = p; // barre częściej
    v.push_back(kOpen[s] + fr);
  }
  if (v.size() < 2) v.push_back(v.empty() ? 52 : v.back() + 5);
  return v;
}

struct Dyn { // dynamika: poziom bazowy, crescendo/decrescendo, akcenty
  double base, slope, t0, accentP;
  double vel(Rng& r, double t) const {
    double v = base * (1 + slope * (t - t0)) * (r.uni() < accentP ? r.uni(1.2, 1.6) : 1.0) * r.uni(0.8, 1.15);
    return clampd(v, 0.08, 1.0);
  }
};

static void strumSection(Rng& r, std::vector<NoteEvent>& ev, double& t, double end, const Dyn& dy) {
  std::vector<int> v = randomVoicing(r);
  while (t < end) {
    if (r.uni() < 0.35) v = randomVoicing(r);
    const double step = r.uni() < 0.3 ? r.uni(0.15, 0.35) : r.uni(0.35, 1.6);
    const bool down = r.uni() < 0.6, muted = r.uni() < 0.12; // stłumione uderzenie (krótkie, perkusyjne)
    const double gap = r.uni(0.004, 0.04), vel = dy.vel(r, t);
    std::vector<int> nn = v;
    if (!down) std::reverse(nn.begin(), nn.end());
    const int skip = r.uni() < 0.3 ? r.range(1, 2) : 0; // nie wszystkie struny trafione
    for (size_t i = 0; i + skip < nn.size(); ++i) {
      NoteEvent e;
      e.midi = nn[i];
      e.t0 = t + i * gap + r.uni(-0.003, 0.003);
      e.t1 = muted ? e.t0 + r.uni(0.04, 0.15) : t + step * r.uni(0.7, 1.0) + (r.uni() < 0.3 ? r.uni(0, 1.0) : 0);
      e.vel = (float)clampd(vel * r.uni(0.7, 1.15), 0.06, 1.0);
      ev.push_back(e);
    }
    t += step;
  }
}

static void arpSection(Rng& r, std::vector<NoteEvent>& ev, double& t, double end, const Dyn& dy) {
  std::vector<int> v = randomVoicing(r);
  std::vector<int> pat(r.range(3, 8));
  for (auto& p : pat) p = r.range(0, (int)v.size() - 1);
  const double step = r.uni(0.09, 0.45), ring = r.uni(0.2, 2.5);
  int k = 0;
  while (t < end) {
    if (k > 0 && k % (int)pat.size() == 0 && r.uni() < 0.4) { v = randomVoicing(r); for (auto& p : pat) p = r.range(0, (int)v.size() - 1); }
    const int n = r.uni() < 0.12 ? 2 : 1; // czasem dwie struny naraz
    for (int j = 0; j < n; ++j) {
      NoteEvent e;
      e.midi = v[(pat[k % pat.size()] + j * 2) % v.size()];
      e.t0 = t + r.uni(-0.01, 0.01);
      e.t1 = e.t0 + ring * r.uni(0.5, 1.3);
      e.vel = (float)dy.vel(r, t);
      ev.push_back(e);
    }
    t += step * r.uni(0.85, 1.15);
    ++k;
  }
}

static void randomNotesSection(Rng& r, std::vector<NoteEvent>& ev, double& t, double end, const Dyn& dy) {
  const double rate = r.uni(1.5, 9);
  while (t < end) {
    NoteEvent e;
    e.midi = r.range(40, 84);
    e.t0 = t;
    e.t1 = t + (r.uni() < 0.3 ? r.uni(0.06, 0.2) : r.uni(0.2, 2.0));
    e.vel = (float)dy.vel(r, t);
    ev.push_back(e);
    t += -std::log(r.uni() + 1e-9) / rate;
  }
}

static void melodySection(Rng& r, std::vector<NoteEvent>& ev, double& t, double end, const Dyn& dy) {
  int m = r.range(45, 72);
  const bool stacc = r.uni() < 0.35;
  while (t < end) {
    m = (int)clampd(m + r.range(-5, 5) + (r.uni() < 0.1 ? r.range(-12, 12) : 0), 40, 86);
    const double d = r.uni(0.08, 0.7);
    NoteEvent e;
    e.midi = m; e.t0 = t; e.t1 = t + d * (stacc ? r.uni(0.3, 0.6) : r.uni(0.9, 1.3)); e.vel = (float)dy.vel(r, t);
    ev.push_back(e);
    t += d + (r.uni() < 0.2 ? r.uni(0.05, 0.4) : 0);
  }
}

// ------------------------------------------------------------ otoczenie
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

// ------------------------------------------------------------ jedno nagranie
static void piece(const std::string& dir, const std::string& id, uint64_t seed) {
  Rng r(seed);
  const double dur = r.uni(9, 18);
  std::vector<NoteEvent> ev;
  Dyn dy{r.uni(0.25, 0.95), r.uni(-0.06, 0.06), 0.0, r.uni(0, 0.3)};
  double t = r.uni(0.3, 1.2);
  while (t < dur - 1.0) {
    const double end = std::min(dur - 0.8, t + r.uni(2.5, 7));
    const double u = r.uni();
    if (r.uni() < 0.25) dy = {r.uni(0.15, 0.95), r.uni(-0.08, 0.08), t, r.uni(0, 0.3)};
    if (u < 0.32) strumSection(r, ev, t, end, dy);
    else if (u < 0.6) arpSection(r, ev, t, end, dy);
    else if (u < 0.8) randomNotesSection(r, ev, t, end, dy);
    else melodySection(r, ev, t, end, dy);
    t += r.uni(0, 0.6);
  }
  const size_t n = (size_t)((dur + 1.5) * FS);
  std::vector<float> g(n, 0.f);
  SynthOptions so;
  so.varied = true; so.seed = seed * 31 + 7; so.globalCents = r.uni() < 0.3 ? r.uni(-40, 40) : r.uni(-5, 5);
  so.noteCentsSd = r.uni(0, 7); so.body = r.uni() < 0.85;
  std::vector<double> aud;
  const auto freqs = renderNotes(g.data(), n, FS, ev, so, &aud);
  // pokój i kąt mikrofonu dla gitary
  if (r.uni() < 0.8) schroederReverb(g, FS, r.uni(0.15, 1.6), r.uni(0.05, 0.5));
  micAngle(r, g);
  const double gRms = rmsv(g);
  double gPeak = 1e-9; for (float v : g) gPeak = std::max(gPeak, (double)std::fabs(v));
  std::vector<float> nz(n, 0.f);
  EnvDesc d;
  environment(r, nz, gRms, gPeak, d);
  std::vector<float> mix(n);
  for (size_t i = 0; i < n; ++i) mix[i] = g[i] + nz[i];
  // poziom nagrania: szczyt od -32 do -1 dBFS
  double pk = 1e-9; for (float v : mix) pk = std::max(pk, (double)std::fabs(v));
  const double k = std::pow(10.0, r.uni(-32, -1) / 20.0) / pk;
  for (size_t i = 0; i < n; ++i) { mix[i] *= (float)k; g[i] *= (float)k; }
  wavio::write16(dir + "/" + id + ".wav", mix, FS);
  wavio::write16(dir + "/" + id + ".clean.wav", g, FS);
  FILE* f = fopen((dir + "/" + id + ".truth.json").c_str(), "w");
  fprintf(f, "{\"id\":\"%s\",\"kind\":\"env\",\"env\":\"%s\",\"fs\":%d,\"dur\":%.3f,\"chords\":[],\n\"notes\":[", id.c_str(), d.parts.c_str(), FS, n / (double)FS);
  for (size_t i = 0; i < ev.size(); ++i)
    fprintf(f, "%s{\"midi\":%d,\"t0\":%.3f,\"t1\":%.3f,\"ta\":%.3f,\"f\":%.4f}", i ? "," : "", ev[i].midi, ev[i].t0, ev[i].t1, aud[i], freqs[i]);
  fprintf(f, "]}\n");
  fclose(f);
}

int main(int argc, char** argv) {
  if (argc < 4) { fprintf(stderr, "użycie: gen_env <katalog> <ziarno> <liczba>\n"); return 2; }
  const std::string dir = argv[1];
  const uint64_t s0 = (uint64_t)atoll(argv[2]);
  const int cnt = atoi(argv[3]);
  for (int i = 0; i < cnt; ++i) {
    char id[64];
    snprintf(id, 64, "env_%05llu", (unsigned long long)(s0 + i));
    piece(dir, id, s0 + i);
  }
  printf("zapisano %d nagrań w %s\n", cnt, dir.c_str());
  return 0;
}
