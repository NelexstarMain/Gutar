// gt_instruments.hpp - syntezator wielu instrumentów dla danych generacji 6 (tools/gen_classical.cpp).
// Addytywny: każda nuta to suma alikwotów z obwiednią, a barwę instrumentu dają rozkład alikwotów (miejsce szarpnięcia/uderzenia,
// nachylenie, tylko nieparzyste, sztabki o nieharmonicznych proporcjach), nieharmoniczność strun, kilka strun na nutę (rozstrojenie),
// wibrato, tremolo, szum ataku i oddechu, filtr pudła/formanty. Parametry każdego instrumentu są losowane od nowa dla każdego
// nagrania (inny egzemplarz instrumentu, inny muzyk). Gitara klasyczna to dokładnie syntezator silnika (gt::renderNotes).
#pragma once
#include <string>
#include <vector>
#include "../src/gt_synth.hpp"

namespace inst {
using namespace gt;
using gt::detail::Biquad;

enum Kind { PLUCK, PIANO, MALLET, SUST };

struct InstInfo { const char* name; int lo, hi; Kind kind; bool guitar; };

// zakresy w MIDI (nuty poza zakresem są przenoszone o oktawy do środka); rodzina gitar ma osobny udział w losowaniu
static const InstInfo kInst[] = {
  {"gitara_klasyczna", 40, 88, PLUCK, true},  {"gitara_stalowa", 40, 88, PLUCK, true},   {"gitara_elektryczna", 40, 88, PLUCK, true},
  {"ukulele", 60, 84, PLUCK, true},           {"mandolina", 55, 88, PLUCK, false},       {"lutnia", 40, 79, PLUCK, false},
  {"harfa", 36, 96, PLUCK, false},            {"klawesyn", 36, 89, PLUCK, false},        {"fortepian", 36, 96, PIANO, false},
  {"dzwonki", 67, 96, MALLET, false},         {"marimba", 45, 96, MALLET, false},        {"wibrafon", 53, 89, MALLET, false},
  {"organy", 36, 96, SUST, false},            {"skrzypce", 55, 96, SUST, false},         {"altowka", 48, 88, SUST, false},
  {"wiolonczela", 36, 76, SUST, false},       {"kontrabas", 36, 67, SUST, false},        {"pizzicato", 36, 91, PLUCK, false},
  {"flet", 60, 96, SUST, false},              {"klarnet", 50, 91, SUST, false},          {"oboj", 58, 91, SUST, false},
  {"fagot", 36, 75, SUST, false},             {"waltornia", 41, 77, SUST, false},        {"trabka", 54, 86, SUST, false},
  {"chor", 40, 81, SUST, false},              {"syntezator", 36, 96, SUST, false},       {"akordeon", 41, 93, SUST, false},
};
static const int kNumInst = (int)(sizeof(kInst) / sizeof(kInst[0]));
inline int instByName(const std::string& s) { for (int i = 0; i < kNumInst; ++i) if (s == kInst[i].name) return i; return -1; }

// parametry jednego egzemplarza instrumentu (losowane na nagranie)
struct Params {
  int id = 0;
  double B = 0, pos = 0.15, slope = 1.2, tau110 = 2.0, tauExp = 0.3, kdec = 0.3; // struny / zanik
  double att = 0.002, rel = 0.05;                     // atak i wybrzmienie po puszczeniu [s]
  double evenGain = 1.0, brightVel = 0.0;             // parzyste alikwoty; jaśniej przy mocniejszym ataku
  double vibCents = 0, vibRate = 5.5, vibDelay = 0.2; // wibrato
  double trem = 0, tremRate = 5;                      // tremolo amplitudy (wibrafon, akordeon)
  double burst = 0.5, burstLen = 0.006, breath = 0;   // szum ataku, szum oddechu/smyczka w trakcie nuty
  int strings = 1; double detune = 0;                 // kilka strun/stroików na nutę i ich rozstrojenie [centy]
  std::vector<double> ratios, ramps;                  // sztabki: proporcje i amplitudy alikwotów
  std::vector<Biquad> body;                           // pudło, formanty, przetwornik
  double lp = 0;                                      // dodatkowe przyciemnienie (0 = brak)
  double gain = 1.0;
  int maxH = 40;
  double pickup = 0;                                  // gitara elektryczna: miejsce przetwornika
  double sustTau = 0;                                 // instrumenty ciągłe: powolny zanik w trakcie nuty (0 = brak)
  std::vector<double> stops;                          // organy: rejestry (mnożnik wysokości 1, 2, 4 …) i ich głośność
};

inline Params randomParams(int id, Rng& r) {
  Params p; p.id = id;
  const std::string n = kInst[id].name;
  auto pk = [&](double f, double g, double q) { p.body.push_back(Biquad::peaking(22050, f, g, q)); };
  if (n == "gitara_stalowa") {
    p.B = std::exp(r.uni(std::log(8e-5), std::log(4e-4))); p.pos = r.uni(0.07, 0.2); p.slope = r.uni(0.8, 1.15);
    p.tau110 = r.uni(2.0, 4.5); p.kdec = r.uni(0.1, 0.3); p.burst = r.uni(0.4, 1.0); p.strings = 1;
    pk(r.uni(90, 120), r.uni(3, 8), 4); pk(r.uni(180, 240), r.uni(2, 6), 4); pk(r.uni(2500, 4000), r.uni(0, 4), 1.5);
  } else if (n == "gitara_elektryczna") {
    p.B = std::exp(r.uni(std::log(5e-5), std::log(2e-4))); p.pos = r.uni(0.08, 0.25); p.slope = r.uni(0.9, 1.3);
    p.tau110 = r.uni(3.0, 7.0); p.kdec = r.uni(0.15, 0.4); p.pickup = r.uni(0.04, 0.2); p.burst = 0.2;
    p.lp = r.uni(0.15, 0.6); pk(r.uni(1500, 4500), r.uni(2, 9), r.uni(0.8, 2.5));
  } else if (n == "ukulele") {
    p.B = 2e-4; p.pos = r.uni(0.15, 0.3); p.slope = r.uni(1.1, 1.5); p.tau110 = r.uni(0.6, 1.4); p.kdec = r.uni(0.2, 0.5);
    pk(r.uni(250, 350), 6, 4); pk(r.uni(700, 900), 3, 4);
  } else if (n == "mandolina") {
    p.B = 1.5e-4; p.pos = r.uni(0.06, 0.15); p.slope = r.uni(0.8, 1.1); p.tau110 = r.uni(0.8, 1.6); p.kdec = r.uni(0.25, 0.5);
    p.strings = 2; p.detune = r.uni(1.5, 7); pk(r.uni(350, 500), 5, 3); pk(r.uni(2000, 3500), 3, 2);
  } else if (n == "lutnia") {
    p.B = 8e-5; p.pos = r.uni(0.1, 0.25); p.slope = r.uni(1.2, 1.6); p.tau110 = r.uni(1.0, 2.0); p.kdec = r.uni(0.3, 0.6);
    p.strings = 2; p.detune = r.uni(1, 5); pk(r.uni(150, 250), 5, 3); p.lp = 0.3;
  } else if (n == "harfa") {
    p.B = 5e-5; p.pos = r.uni(0.35, 0.5); p.slope = r.uni(1.3, 1.8); p.tau110 = r.uni(3.0, 6.0); p.tauExp = 0.45;
    p.kdec = r.uni(0.2, 0.5); p.burst = 0.15; p.lp = 0.3;
  } else if (n == "klawesyn") {
    p.B = 4e-5; p.pos = r.uni(0.04, 0.12); p.slope = r.uni(0.55, 0.9); p.tau110 = r.uni(2.0, 4.0); p.kdec = r.uni(0.05, 0.2);
    p.rel = 0.06; p.strings = r.uni() < 0.5 ? 2 : 1; p.detune = r.uni(0.5, 3); p.burst = 0.8; p.burstLen = 0.004;
    pk(r.uni(1500, 3000), 4, 1.5);
  } else if (n == "pizzicato") {
    p.B = 3e-5; p.pos = r.uni(0.2, 0.4); p.slope = r.uni(1.3, 1.8); p.tau110 = r.uni(0.4, 1.0); p.kdec = r.uni(0.4, 0.9);
    p.burst = 0.3; pk(r.uni(270, 300), 8, 5); pk(r.uni(450, 520), 6, 5); pk(r.uni(2500, 3200), 4, 2);
  } else if (n == "fortepian") {
    p.pos = r.uni(1.0 / 9, 1.0 / 7); p.slope = r.uni(0.9, 1.3); p.tau110 = r.uni(3.0, 7.0); p.tauExp = 0.6; p.kdec = r.uni(0.15, 0.35);
    p.rel = r.uni(0.06, 0.18); p.strings = 3; p.detune = r.uni(0.3, 2.0); p.brightVel = r.uni(0.4, 1.0); p.burst = 0.3;
    p.B = r.uni(0.7, 1.5); // skala nieharmoniczności (zależnej od wysokości, liczonej przy nucie)
    p.lp = r.uni(0, 0.4);
  } else if (n == "dzwonki") {
    p.ratios = {1, 2.76, 5.40, 8.93}; p.ramps = {1, 0.25, 0.12, 0.05}; p.tau110 = r.uni(1.5, 3.0); p.kdec = 0.6; p.burst = 0.2;
  } else if (n == "marimba") {
    p.ratios = {1, 3.93, 9.24}; p.ramps = {1, r.uni(0.1, 0.35), 0.05}; p.tau110 = r.uni(0.6, 1.3); p.tauExp = 0.5; p.kdec = 1.5; p.burst = 0.3;
    pk(r.uni(150, 300), 3, 2);
  } else if (n == "wibrafon") {
    p.ratios = {1, 4.0, 10.0}; p.ramps = {1, r.uni(0.1, 0.3), 0.04}; p.tau110 = r.uni(3.0, 6.0); p.tauExp = 0.4; p.kdec = 0.8;
    p.trem = r.uni() < 0.6 ? r.uni(0.2, 0.6) : 0; p.tremRate = r.uni(3, 8); p.rel = r.uni(0.1, 0.5); p.burst = 0.15;
  } else if (n == "organy") {
    p.att = r.uni(0.02, 0.08); p.rel = r.uni(0.03, 0.12); p.slope = r.uni(1.4, 2.4); p.burst = 0; p.breath = r.uni(0.002, 0.02);
    p.stops = {1, 1.0};
    if (r.uni() < 0.6) p.stops.insert(p.stops.end(), {1, r.uni(0.2, 0.7)});
    if (r.uni() < 0.5) p.stops.insert(p.stops.end(), {2, r.uni(0, 0.4)});
    if (r.uni() < 0.3) p.stops.insert(p.stops.end(), {4, r.uni(0, 0.3)});
    p.maxH = 20;
  } else if (n == "skrzypce" || n == "altowka" || n == "wiolonczela" || n == "kontrabas") {
    const double sc = n == "skrzypce" ? 1.0 : n == "altowka" ? 0.8 : n == "wiolonczela" ? 0.55 : 0.4;
    p.att = r.uni(0.04, 0.15); p.rel = r.uni(0.08, 0.25); p.slope = r.uni(0.8, 1.2); p.vibCents = r.uni(5, 30);
    p.vibRate = r.uni(4.5, 7); p.vibDelay = r.uni(0.05, 0.4); p.breath = r.uni(0.01, 0.05); p.burst = r.uni(0.05, 0.3);
    p.burstLen = 0.03; p.strings = r.uni() < 0.3 ? 3 : 1; p.detune = r.uni(3, 10); // czasem sekcja zamiast solisty
    pk(280 * sc / 0.8 * 0.8, 8, 4); pk(r.uni(450, 550) * sc, 6, 4); pk(r.uni(2500, 3200) * std::sqrt(sc), 5, 2);
    pk(r.uni(4000, 5000), -6, 1);
  } else if (n == "flet") {
    p.att = r.uni(0.03, 0.08); p.rel = 0.08; p.slope = r.uni(2.2, 3.2); p.vibCents = r.uni(5, 20); p.vibRate = r.uni(4.5, 6);
    p.breath = r.uni(0.02, 0.08); p.burst = 0.1; p.burstLen = 0.02; p.maxH = 10;
  } else if (n == "klarnet") {
    p.att = r.uni(0.02, 0.06); p.rel = 0.06; p.slope = r.uni(0.9, 1.4); p.evenGain = r.uni(0.03, 0.25); p.vibCents = r.uni(0, 6);
    p.breath = r.uni(0.003, 0.02); p.lp = r.uni(0, 0.3);
  } else if (n == "oboj" || n == "fagot") {
    p.att = r.uni(0.02, 0.06); p.rel = 0.06; p.slope = r.uni(0.6, 1.0); p.vibCents = r.uni(3, 15); p.breath = r.uni(0.003, 0.02);
    if (n == "oboj") { pk(r.uni(1000, 1500), 10, 2); pk(r.uni(2800, 3500), 6, 3); }
    else { pk(r.uni(400, 550), 10, 2); pk(r.uni(1100, 1300), 6, 3); }
  } else if (n == "waltornia" || n == "trabka") {
    p.att = r.uni(0.03, 0.08); p.rel = 0.08; p.slope = n == "trabka" ? r.uni(0.6, 1.1) : r.uni(1.4, 2.0); p.brightVel = r.uni(0.6, 1.4);
    p.vibCents = r.uni(0, 8); p.burst = 0.1; p.burstLen = 0.015;
    if (n == "trabka") pk(r.uni(1100, 1500), 6, 2); else { pk(r.uni(350, 500), 6, 2); p.lp = 0.5; }
  } else if (n == "chor") {
    p.att = r.uni(0.06, 0.2); p.rel = r.uni(0.1, 0.3); p.slope = r.uni(1.0, 1.4); p.vibCents = r.uni(10, 35); p.vibRate = r.uni(4.5, 6);
    p.strings = r.range(1, 3); p.detune = r.uni(4, 15); p.breath = r.uni(0.005, 0.03);
    static const double F[5][3] = {{730, 1090, 2440}, {570, 840, 2410}, {300, 870, 2240}, {530, 1840, 2480}, {270, 2290, 3010}}; // a o u e i
    const int v = r.range(0, 4);
    pk(F[v][0], 14, 4); pk(F[v][1], 11, 5); pk(F[v][2], 8, 6); pk(5000, -10, 0.7);
  } else if (n == "syntezator") {
    p.att = r.uni(0.003, 0.08); p.rel = r.uni(0.05, 0.4); p.slope = 1.0; p.evenGain = r.uni() < 0.5 ? 1.0 : 0.0;
    p.vibCents = r.uni() < 0.3 ? r.uni(3, 15) : 0; p.lp = r.uni(0, 0.7); p.strings = r.range(1, 2); p.detune = r.uni(3, 12);
    p.sustTau = r.uni() < 0.5 ? r.uni(0.5, 3) : 0; p.burst = 0;
  } else if (n == "akordeon") {
    p.att = r.uni(0.03, 0.08); p.rel = 0.05; p.slope = r.uni(0.8, 1.2); p.strings = 2; p.detune = r.uni(5, 20); p.breath = 0.005;
    pk(r.uni(800, 1500), 4, 2);
  }
  p.gain = r.uni(0.8, 1.2);
  return p;
}

// sinus z tablicy (4096 punktów, interpolacja liniowa, błąd < 1e-6): wolna ścieżka z wibrato liczy go dla każdej próbki
struct SinTab {
  float t[4097];
  SinTab() { for (int i = 0; i <= 4096; ++i) t[i] = (float)std::sin(2 * kPi * i / 4096.0); }
  // faza w obrotach (1 = 2π)
  inline float operator()(double turns) const {
    const double x = (turns - std::floor(turns)) * 4096.0; const int i = (int)x; const float u = (float)(x - i);
    return t[i] + (t[i + 1] - t[i]) * u;
  }
};
inline const SinTab& sinTab() { static const SinTab s; return s; }

// jeden alikwot: obwiednia (atak, zanik, puszczenie); fm/am: wspólne dla nuty krzywe wibrato i tremolo (od próbki n0), może być null
struct Partial { double f, a, tau = 0, ph = 0, att = 0.002, relTau = 0.05, glide = 0; };

inline void renderPartial(float* out, int64_t n0, int64_t nRel, int64_t nEnd, double fs, const Partial& p,
                          const float* fm = nullptr, const float* am = nullptr) {
  const int64_t attS = std::max<int64_t>(1, (int64_t)(p.att * fs));
  const double decRun = p.tau > 0 ? std::exp(-1.0 / (p.tau * fs)) : 1.0;
  const double decRel = std::exp(-1.0 / (std::max(0.005, p.relTau) * fs));
  double env = p.a;
  if (!fm && !am && p.glide == 0) { // szybka ścieżka: oscylator z obrotu
    const double w = 2 * kPi * p.f / fs, dc = std::cos(w), ds = std::sin(w);
    double c = std::cos(p.ph), s = std::sin(p.ph);
    for (int64_t n = n0; n < nEnd; ++n) {
      const int64_t k = n - n0;
      const double ramp = k < attS ? (double)k / attS : 1.0;
      out[n] += (float)(env * ramp * s);
      const double c2 = c * dc - s * ds; s = s * dc + c * ds; c = c2;
      env *= n >= nRel ? decRun * decRel : decRun;
    }
    return;
  }
  const SinTab& S = sinTab();
  double ph = p.ph / (2 * kPi), g = p.glide;
  const double inc = p.f / fs, gdec = std::exp(-1.0 / (0.06 * fs));
  for (int64_t n = n0; n < nEnd; ++n) {
    const int64_t k = n - n0;
    const double ramp = k < attS ? (double)k / attS : 1.0;
    out[n] += (float)(env * ramp * (am ? am[k] : 1.0f) * S(ph));
    ph += inc * ((fm ? fm[k] : 1.0f) + g);
    g *= gdec;
    env *= n >= nRel ? decRun * decRel : decRun;
  }
}

// Renderuje nuty jednym instrumentem do `out` (n próbek). audibleEnd: koniec słyszalności każdej nuty (jak w gt::renderNotes).
inline void renderInst(float* out, size_t n, int fs, const std::vector<NoteEvent>& ev, const Params& P, uint64_t seed,
                       std::vector<double>* freqs, std::vector<double>* audibleEnd, double centsSd = 0) {
  const InstInfo& I = kInst[P.id];
  if (std::string(I.name) == "gitara_klasyczna") { // syntezator silnika (ten sam co w korpusie i środowiskach)
    SynthOptions so; so.varied = true; so.seed = seed; so.noteCentsSd = centsSd; so.body = true; so.gain = 0.2 * P.gain;
    const auto f = renderNotes(out, n, fs, ev, so, audibleEnd);
    if (freqs) freqs->insert(freqs->end(), f.begin(), f.end());
    return;
  }
  Rng r(seed);
  std::vector<float> bus(n, 0.f);
  const bool sust = I.kind == SUST;
  for (const auto& e : ev) {
    const double cents = centsSd > 0 ? centsSd * r.gauss() : 0.0;
    const double f0 = 440.0 * std::pow(2.0, (e.midi - 69) / 12.0 + cents / 1200.0);
    if (freqs) freqs->push_back(f0);
    const double vel = std::max(0.05, (double)e.vel);
    const double amp = 0.2 * P.gain * std::pow(vel, sust ? 1.0 : 1.3);
    const int64_t n0 = (int64_t)std::llround(e.t0 * fs);
    const int64_t nRel = (int64_t)std::llround(std::max(e.t1, e.t0 + 0.04) * fs);
    if (n0 >= (int64_t)n) { if (audibleEnd) audibleEnd->push_back(e.t0); continue; }
    double tau1 = P.tau110 * std::pow(110.0 / f0, P.tauExp) * r.uni(0.8, 1.2);
    if (sust) tau1 = P.sustTau;
    const double relTau = P.rel * r.uni(0.8, 1.25);
    int64_t nEnd = nRel + (int64_t)(relTau * 7 * fs);
    if (!sust) nEnd = std::min<int64_t>(nEnd, n0 + (int64_t)(tau1 * 7 * fs));
    nEnd = std::min<int64_t>(nEnd, (int64_t)n);
    const double slope = P.slope - P.brightVel * (vel - 0.5);
    double domA = -1, domTau = tau1;
    const double vibPh = r.uni(0, 2 * kPi), vibCents = P.vibCents * r.uni(0.6, 1.3), tremPh = r.uni(0, 2 * kPi);
    // wibrato (dla każdej struny/stroika własna szybkość) i tremolo: jedna krzywa na nutę, wspólna dla alikwotów
    const int64_t L = std::max<int64_t>(0, nEnd - n0);
    std::vector<std::vector<float>> fmc;
    std::vector<float> amc;
    if (vibCents > 0) {
      for (int s = 0; s < P.strings; ++s) {
        std::vector<float> c(L);
        const double rate = P.vibRate * (P.strings > 1 ? r.uni(0.9, 1.1) : 1), dep = vibCents * 0.000577623, ph0 = vibPh + s;
        for (int64_t k = 0; k < L; ++k) {
          const double t = (double)k / fs;
          c[k] = (float)(1.0 + (t > P.vibDelay ? dep * std::min(1.0, (t - P.vibDelay) / 0.3) * std::sin(2 * kPi * rate * t + ph0) : 0.0));
        }
        fmc.push_back(std::move(c));
      }
    }
    if (P.trem > 0) {
      amc.resize(L);
      for (int64_t k = 0; k < L; ++k) amc[k] = (float)(1.0 - P.trem * 0.5 * (1 + std::sin(2 * kPi * P.tremRate * k / fs + tremPh)));
    }
    auto emit = [&](double fh, double a, double tau, int h) {
      if (fh > 0.45 * fs || fh > 9500 || a <= amp * 1e-3) return;
      if (a > domA) { domA = a; domTau = tau; }
      for (int s = 0; s < P.strings; ++s) {
        Partial q;
        const double dc = P.strings > 1 ? P.detune * (s - 0.5 * (P.strings - 1)) / std::max(1.0, 0.5 * (P.strings - 1)) * r.uni(0.7, 1.0) : 0;
        q.f = fh * std::pow(2.0, dc / 1200.0); q.a = a / P.strings; q.tau = tau; q.ph = r.uni(0, 2 * kPi);
        q.att = P.att; q.relTau = relTau;
        if (I.kind == PLUCK && h == 1) q.glide = r.uni(0, 8) * vel * 0.000577623;
        renderPartial(bus.data(), n0, nRel, nEnd, fs, q, fmc.empty() ? nullptr : fmc[s].data(), amc.empty() ? nullptr : amc.data());
      }
    };
    if (I.kind == MALLET) {
      for (size_t k = 0; k < P.ratios.size(); ++k)
        emit(f0 * P.ratios[k], amp * 2 * P.ramps[k] * std::pow(vel, 0.5 * k), tau1 / (1 + P.kdec * k * k), (int)k + 1);
    } else if (!P.stops.empty()) { // organy: rejestry jako kopie szeregu alikwotów
      for (size_t s = 0; s + 1 < P.stops.size(); s += 2)
        for (int h = 1; h <= P.maxH; ++h)
          emit(f0 * P.stops[s] * h * (s ? 1.0007 : 1.0), amp * 2 * P.stops[s + 1] / std::pow((double)h, P.slope + (s ? -0.6 : 0)), tau1, h);
    } else {
      double B = P.B;
      if (I.kind == PIANO) B = P.B * 1.5e-4 * std::pow(2.0, (e.midi - 60) / 14.0); // nieharmoniczność rośnie z wysokością
      for (int h = 1; h <= P.maxH; ++h) {
        const double fh = h * f0 * std::sqrt(1 + B * h * h);
        double a;
        if (I.kind == PLUCK || I.kind == PIANO) {
          a = std::fabs(std::sin(kPi * h * P.pos)) / std::pow((double)h, slope);
          if (P.pickup > 0) a *= 0.3 + std::fabs(std::sin(kPi * h * P.pickup));
          if (I.kind == PIANO) a *= 1.0 / (1 + std::pow(fh / (900 + 2500 * vel), 2)); // filcowy młotek: miękko przy cichym uderzeniu
          if (h == 1 && f0 < 110) a *= 0.6;
        } else {
          a = 1.0 / std::pow((double)h, slope);
          if (h % 2 == 0) a *= P.evenGain;
        }
        const double tau = sust ? tau1 : tau1 / (1 + P.kdec * (h - 1));
        emit(fh, amp * 2 * a, tau, h);
      }
    }
    if (audibleEnd) {
      double ae = sust ? e.t1 + relTau * 2.3 : std::min(e.t1 + relTau * 2.3, e.t0 + domTau * std::log(100.0));
      audibleEnd->push_back(std::max(e.t0 + 0.02, ae));
    }
    // szum ataku (szarpnięcie, młotek, smyczek, zadęcie) i szum oddechu/smyczka w trakcie nuty
    const int64_t nb = (int64_t)(P.burstLen * fs);
    double lp = 0;
    for (int64_t i = 0; i < nb && n0 + i < (int64_t)n && P.burst > 0; ++i) {
      lp = 0.6 * lp + 0.4 * (r.uni() * 2 - 1);
      bus[n0 + i] += (float)(lp * amp * P.burst * (1.0 - (double)i / nb));
    }
    if (P.breath > 0) { // szum wąskopasmowy wokół podstawy (rezonator dwubiegunowy), z tą samą obwiednią co nuta
      const double w = 2 * kPi * std::min(f0 * 2, 4000.0) / fs, rad = 0.995, a1 = -2 * rad * std::cos(w), a2 = rad * rad;
      double y1 = 0, y2 = 0;
      const int64_t attS = std::max<int64_t>(1, (int64_t)(P.att * fs));
      for (int64_t i = n0; i < nEnd; ++i) {
        const double x = r.gauss(), y = x - a1 * y1 - a2 * y2; y2 = y1; y1 = y;
        double g = (i - n0) < attS ? (double)(i - n0) / attS : 1.0;
        if (i >= nRel) g *= std::exp(-(double)(i - nRel) / (relTau * fs));
        bus[i] += (float)(y * g * amp * P.breath * 0.05);
      }
    }
  }
  for (const auto& b : P.body) b.run(bus);
  if (P.lp > 0) { double z = 0; const double k = 1 - P.lp * 0.85; for (auto& v : bus) { z += k * (v - z); v = (float)z; } }
  for (size_t i = 0; i < n; ++i) out[i] += bus[i];
}

} // namespace inst
