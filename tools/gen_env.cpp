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
#include "gt_envfx.hpp"

using namespace gt;
using namespace envfx;

static const int kOpen[6] = {40, 45, 50, 55, 59, 64};

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
