// gen_classical.cpp - dane generacji 6: partytury muzyki klasycznej (MIDI) zagrane na wielu instrumentach w wielu miejscach.
//
// Dla każdego utworu z manifestu (tools/gen6/fetch_classical.py) powstaje kilka WERSJI:
//   forma 0 oryginał, 1 odwrócenie („do góry nogami”: wysokości odbite wokół środka skali utworu, zakres zostaje ten sam),
//   2 rak (utwór od końca), 3 rak odwrócenia; kolejne wersje (4, 5, …) powtarzają formy z innymi modyfikatorami.
//   Modyfikatory losowane dla każdej wersji: transpozycja (−7..+7 półtonów; od wersji 4 zawsze), tempo ×0,6–1,6, artykulacja
//   (staccato … legato), humanizacja (rozrzut czasu i dynamiki), usunięcie głosu, przeniesienie głosu o oktawę.
// Z każdej wersji wycinane są fragmenty (domyślnie 2 × 10–20 s) i każdy jest grany osobno:
//   * obsada: solo (wszystkie głosy na jednym instrumencie), zespół (każdy głos inny instrument) albo gitara + zespół;
//     27 instrumentów (gitary, ukulele, mandolina, lutnia, harfa, klawesyn, fortepian, dzwonki, marimba, wibrafon, organy, smyczki,
//     pizzicato, flet, klarnet, obój, fagot, waltornia, trąbka, chór, syntezator, akordeon), rodzina gitar ma osobny udział;
//     nuty spoza zakresu instrumentu przenoszone o oktawy; każdy instrument losuje własną barwę (inny egzemplarz);
//   * miejsce: studio, pokój, salon, sala koncertowa, kościół, plener (wiatr), telefon, dyktafon/kaseta (szum, kołysanie
//     wysokości), płyta winylowa (trzaski), transmisja internetowa (kompresja), próba w domu (pełne otoczenie z gen_env);
//     do tego kąt mikrofonu i otoczenie z gen 4 (szumy, tony, brum, stuki, kliknięcia, rozmowa), czasem przester i kompresja.
//
// Wyjście (format jak gen_env, więc train_gen5.py czyta je bez zmian):
//   <out>/<id>.wav               mikrofon (22050 Hz, 16 bit)
//   <out>/<id>.clean.wav         same instrumenty bez otoczenia (z --clean)
//   <out>/<id>.truth.json        nuty: midi, t0, t1, ta (koniec słyszalności), f, i (instrument), v (głos) + opis nagrania
//   <out>/midi/<utwór>_v<k>.mid  pełna wersja utworu jako MIDI (z --midi)
//   <out>/index.csv              jeden wiersz na nagranie (utwór, wersja, forma, modyfikatory, obsada, miejsce, liczba nut)
//
// Użycie: gen_classical <manifest.csv> <katalog_korpusu> <katalog_wyjścia> [--split train] [--versions 4] [--clips 2]
//         [--len 10 20] [--seed 1] [--jobs 4] [--limit N] [--clean] [--midi] [--guitar 0.35] [--inst nazwa,nazwa] [--place nazwa]
#include <algorithm>
#include <array>
#include <atomic>
#include <cstdio>
#include <cstring>
#include <fstream>
#include <map>
#include <mutex>
#include <set>
#include <sstream>
#include <string>
#include <thread>
#include "../src/gt_synth.hpp"
#include "wavio.hpp"
#include "gt_envfx.hpp"
#include "gt_instruments.hpp"

using namespace gt;

static const int SR = envfx::FS;
static const int kLo = 36, kHi = 88; // zakres wyjścia modelu gen 5 (MIDI 36..88)

// ------------------------------------------------------------ MIDI
struct MNote { double t0, t1key, t1ped; int midi, vel, voice; };

static uint32_t vlq(const std::vector<uint8_t>& d, size_t& q) {
  uint32_t v = 0;
  for (int k = 0; k < 4 && q < d.size(); ++k) { const uint8_t b = d[q++]; v = (v << 7) | (b & 127); if (b < 128) break; }
  return v;
}

// Plik SMF (format 0/1): nuty z mapą tempa; pedał (CC64) przedłuża nuty do jego puszczenia (t1ped). Głos = (ścieżka, kanał).
// Kanał perkusji (10) pomijany.
static bool readMidi(const std::string& path, std::vector<MNote>& out) {
  std::ifstream f(path, std::ios::binary);
  std::vector<uint8_t> d((std::istreambuf_iterator<char>(f)), std::istreambuf_iterator<char>());
  if (d.size() < 14 || memcmp(d.data(), "MThd", 4)) return false;
  const int ntrk = d[10] << 8 | d[11], div = d[12] << 8 | d[13];
  if (div & 0x8000) return false; // SMPTE: rzadkie, pomijamy
  struct Ev { uint64_t tick; int type, a, b, voice; }; // type: 0 tempo, 1 on, 2 off, 3 pedał
  std::vector<Ev> ev;
  size_t p = 14;
  std::map<int, int> voiceId;
  for (int ti = 0; ti < ntrk && p + 8 <= d.size(); ++ti) {
    if (memcmp(&d[p], "MTrk", 4)) break;
    const size_t len = (size_t)d[p + 4] << 24 | d[p + 5] << 16 | d[p + 6] << 8 | d[p + 7];
    size_t q = p + 8; const size_t end = std::min(d.size(), q + len);
    uint64_t tick = 0; int rs = 0;
    while (q < end) {
      tick += vlq(d, q);
      if (q >= end) break;
      int st = d[q];
      if (st == 0xFF) {
        const int typ = d[q + 1]; q += 2; const uint32_t l = vlq(d, q);
        if (typ == 0x51 && l == 3 && q + 3 <= end) ev.push_back({tick, 0, d[q] << 16 | d[q + 1] << 8 | d[q + 2], 0, 0});
        q += l; continue;
      }
      if (st == 0xF0 || st == 0xF7) { ++q; q += vlq(d, q); continue; }
      if (st & 0x80) { rs = st; ++q; }
      if (!rs) break;
      const int hi = rs & 0xF0, ch = rs & 15;
      const int nb = (hi == 0xC0 || hi == 0xD0) ? 1 : 2;
      if (q + nb > end) break;
      const int a = d[q], b = nb > 1 ? d[q + 1] : 0;
      q += nb;
      if (ch == 9) continue;
      const int key = ti * 16 + ch;
      if (hi == 0x90 || hi == 0x80) {
        if (!voiceId.count(key)) { const int id = (int)voiceId.size(); voiceId[key] = id; }
        ev.push_back({tick, (hi == 0x90 && b > 0) ? 1 : 2, a, b, voiceId[key]});
      } else if (hi == 0xB0 && a == 64) {
        ev.push_back({tick, 3, b >= 64, 0, ch});
      }
    }
    p = end;
  }
  std::stable_sort(ev.begin(), ev.end(), [](const Ev& x, const Ev& y) { return x.tick < y.tick; });
  double t = 0, tempo = 500000; uint64_t last = 0;
  std::map<std::pair<int, int>, std::vector<size_t>> open; // (głos, wysokość) -> otwarte nuty
  bool pedal[16] = {};
  std::vector<size_t> held; // nuty puszczone przy wciśniętym pedale
  for (const auto& e : ev) {
    t += (double)(e.tick - last) * tempo / 1e6 / div; last = e.tick;
    if (e.type == 0) { tempo = e.a; continue; }
    if (e.type == 3) {
      const bool down = e.a;
      if (!down) { for (size_t i : held) out[i].t1ped = std::max(out[i].t1ped, t); held.clear(); }
      for (auto& pd : pedal) pd = down; // MAESTRO: jeden kanał; upraszczamy do pedału wspólnego
      continue;
    }
    auto& o = open[{e.voice, e.a}];
    if (e.type == 1) {
      if (!o.empty()) { for (size_t i : o) out[i].t1key = out[i].t1ped = t; o.clear(); } // ponowne uderzenie kończy poprzednią
      out.push_back({t, -1, -1, e.a, e.b, e.voice});
      o.push_back(out.size() - 1);
    } else {
      for (size_t i : o) { out[i].t1key = out[i].t1ped = t; if (pedal[0]) held.push_back(i); }
      o.clear();
    }
  }
  for (auto& n : out) if (n.t1key < 0) n.t1key = n.t1ped = n.t0 + 0.5;
  out.erase(std::remove_if(out.begin(), out.end(), [](const MNote& n) { return n.t1key - n.t0 < 0.01; }), out.end());
  std::sort(out.begin(), out.end(), [](const MNote& a, const MNote& b) { return a.t0 < b.t0 || (a.t0 == b.t0 && a.midi < b.midi); });
  return !out.empty();
}

static void putVlq(std::vector<uint8_t>& o, uint32_t v) {
  uint8_t b[5]; int n = 0;
  do { b[n++] = v & 127; v >>= 7; } while (v);
  while (n--) o.push_back(b[n] | (n ? 128 : 0));
}

// zapis MIDI (format 1, 480 tików na ćwierćnutę, 120 BPM): ścieżka na głos, kanał = głos (bez 10)
static void writeMidi(const std::string& path, const std::vector<MNote>& notes, const std::vector<int>& prog) {
  int nv = 0; for (const auto& n : notes) nv = std::max(nv, n.voice + 1);
  nv = std::min(nv, 15);
  std::vector<uint8_t> o = {'M', 'T', 'h', 'd', 0, 0, 0, 6, 0, 1, 0, (uint8_t)(nv + 1), 0x01, 0xE0};
  auto track = [&](const std::vector<uint8_t>& tr) {
    o.insert(o.end(), {'M', 'T', 'r', 'k'});
    const uint32_t L = (uint32_t)tr.size();
    o.insert(o.end(), {(uint8_t)(L >> 24), (uint8_t)(L >> 16), (uint8_t)(L >> 8), (uint8_t)L});
    o.insert(o.end(), tr.begin(), tr.end());
  };
  track({0, 0xFF, 0x51, 3, 0x07, 0xA1, 0x20, 0, 0xFF, 0x2F, 0});
  for (int v = 0; v < nv; ++v) {
    const int ch = v >= 9 ? v + 1 : v;
    std::vector<std::pair<uint64_t, std::array<uint8_t, 3>>> ev;
    for (const auto& n : notes) if (std::min(n.voice, 14) == v) {
      ev.push_back({(uint64_t)std::llround(n.t0 * 960), {(uint8_t)(0x90 | ch), (uint8_t)n.midi, (uint8_t)std::clamp(n.vel, 1, 127)}});
      ev.push_back({(uint64_t)std::llround(n.t1ped * 960), {(uint8_t)(0x80 | ch), (uint8_t)n.midi, 0}});
    }
    std::stable_sort(ev.begin(), ev.end(), [](const auto& a, const auto& b) { return a.first < b.first || (a.first == b.first && (a.second[0] & 0xF0) < (b.second[0] & 0xF0)); });
    std::vector<uint8_t> tr = {0, (uint8_t)(0xC0 | ch), (uint8_t)(v < (int)prog.size() ? prog[v] : 0)};
    uint64_t last = 0;
    for (const auto& e : ev) { putVlq(tr, (uint32_t)(e.first - last)); last = e.first; tr.insert(tr.end(), e.second.begin(), e.second.end()); }
    tr.insert(tr.end(), {0, 0xFF, 0x2F, 0});
    track(tr);
  }
  FILE* f = fopen(path.c_str(), "wb");
  if (f) { fwrite(o.data(), 1, o.size(), f); fclose(f); }
}

// program General MIDI odpowiadający instrumentowi (dla zapisanych wersji MIDI)
static int gmProgram(int id) {
  static const int gm[] = {24, 25, 27, 24, 105, 24, 46, 6, 0, 9, 12, 11, 19, 40, 41, 42, 43, 45, 73, 71, 68, 70, 60, 56, 52, 81, 21};
  return id < (int)(sizeof(gm) / sizeof(gm[0])) ? gm[id] : 0;
}

// ------------------------------------------------------------ wersje utworu
struct Version {
  int form = 0, transpose = 0; double tempo = 1, artic = 1, humanT = 0, humanV = 0; int dropVoice = -1, octVoice = -1, octShift = 0;
  std::string desc() const {
    static const char* F[] = {"oryginal", "odwrocenie", "rak", "rak_odwrocenia"};
    char b[200];
    snprintf(b, sizeof b, "%s;transp=%+d;tempo=%.2f;artyk=%.2f;humT=%.3f;humV=%.2f;bez_glosu=%d;oktawa_glosu=%d:%+d", F[form], transpose,
             tempo, artic, humanT, humanV, dropVoice, octVoice, octShift);
    return b;
  }
};

static Version randomVersion(Rng& r, int k, int nVoices) {
  Version v;
  v.form = k % 4;
  if (k > 0 || r.uni() < 0.3) v.tempo = std::exp(r.uni(std::log(0.6), std::log(1.6)));
  if (k >= 4 || r.uni() < 0.5) { do v.transpose = r.range(-7, 7); while (k >= 4 && v.transpose == 0); }
  v.artic = r.uni() < 0.5 ? 1.0 : r.uni(0.35, 1.3);
  v.humanT = r.uni() < 0.6 ? r.uni(0, 0.025) : 0;
  v.humanV = r.uni(0, 0.25);
  if (nVoices >= 3 && r.uni() < 0.25) v.dropVoice = r.range(0, nVoices - 1);
  if (nVoices >= 2 && r.uni() < 0.15) { v.octVoice = r.range(0, nVoices - 1); v.octShift = r.uni() < 0.5 ? -12 : 12; }
  return v;
}

static std::vector<MNote> applyVersion(const std::vector<MNote>& src, const Version& v, Rng& r) {
  int lo = 127, hi = 0; double T = 0;
  for (const auto& n : src) { lo = std::min(lo, n.midi); hi = std::max(hi, n.midi); T = std::max(T, n.t1key); }
  const bool inv = v.form == 1 || v.form == 3, retro = v.form == 2 || v.form == 3;
  std::vector<MNote> o;
  o.reserve(src.size());
  for (auto n : src) {
    if (n.voice == v.dropVoice) continue;
    if (inv) n.midi = lo + hi - n.midi;
    if (n.voice == v.octVoice) n.midi += v.octShift;
    n.midi += v.transpose;
    if (retro) { // rak: kolejność początków odwrócona (początek = koniec klawisza od końca), długość brzmienia z pedałem zostaje
      const double dk = n.t1key - n.t0, dp = n.t1ped - n.t0;
      n.t0 = T - n.t1key; n.t1key = n.t0 + dk; n.t1ped = n.t0 + dp;
    }
    const double d = std::max(0.08, (n.t1ped - n.t0) * v.artic); // najkrótsza nuta 80 ms (krótsze to tylko zapis MIDI, nie dźwięk)
    n.t0 /= v.tempo; n.t1ped = n.t0 + d / v.tempo; n.t1key = n.t0 + std::min(d, (n.t1key - n.t0) * v.artic) / v.tempo;
    if (v.humanT > 0) { const double j = r.gauss() * v.humanT; n.t0 += j; n.t1key += j; n.t1ped += j; }
    n.vel = std::clamp((int)std::lround(n.vel * (1 + v.humanV * r.gauss() * 0.5)), 8, 127);
    if (n.midi < 0 || n.midi > 127) continue;
    o.push_back(n);
  }
  double m = 1e9; for (const auto& n : o) m = std::min(m, n.t0);
  if (o.empty()) return o;
  for (auto& n : o) { n.t0 -= m; n.t1key -= m; n.t1ped -= m; }
  std::sort(o.begin(), o.end(), [](const MNote& a, const MNote& b) { return a.t0 < b.t0; });
  return o;
}

// ------------------------------------------------------------ miejsca nagrania
static const char* kPlaces[] = {"studio", "pokoj", "salon", "sala_koncertowa", "kosciol", "plener", "telefon", "dyktafon",
                                "winyl", "transmisja", "proba_w_domu"};
static const int kNumPlaces = 11;

static double rmsv(const std::vector<float>& x) { double s = 0; for (float v : x) s += (double)v * v; return std::sqrt(s / std::max<size_t>(1, x.size())) + 1e-12; }

static void lowpass(std::vector<float>& x, double fc) { // 2 × jednobiegunowy
  const double a = 1 - std::exp(-2 * kPi * fc / SR); double z1 = 0, z2 = 0;
  for (auto& v : x) { z1 += a * (v - z1); z2 += a * (z1 - z2); v = (float)z2; }
}
static void highpass(std::vector<float>& x, double fc) {
  const double a = 1 - std::exp(-2 * kPi * fc / SR); double z = 0;
  for (auto& v : x) { z += a * (v - z); v = (float)(v - z); }
}
static void compress(std::vector<float>& x, double ratio, double thrRel) {
  const double thr = rmsv(x) * thrRel, at = std::exp(-1.0 / (0.005 * SR)), re = std::exp(-1.0 / (0.15 * SR));
  double env = 0;
  for (auto& v : x) {
    const double a = std::fabs(v); env = a > env ? at * env + (1 - at) * a : re * env + (1 - re) * a;
    if (env > thr) v = (float)(v * std::pow(env / thr, 1.0 / ratio - 1));
  }
}
static void softClip(std::vector<float>& x, double drive) {
  double pk = 1e-9; for (float v : x) pk = std::max(pk, (double)std::fabs(v));
  for (auto& v : x) v = (float)(std::tanh(drive * v / pk) / std::tanh(drive) * pk);
}
// kołysanie wysokości (wow & flutter): zmienne opóźnienie z interpolacją; przesuwa wysokość o ułamek centa .. kilka centów
static void wowFlutter(std::vector<float>& x, Rng& r) {
  const double wd = r.uni(0.0002, 0.0012) * SR, wr = r.uni(0.3, 1.2), fd = r.uni(0.00002, 0.0001) * SR, fr = r.uni(6, 12);
  std::vector<float> y(x.size());
  for (size_t i = 0; i < x.size(); ++i) {
    const double d = 2 + wd * (1 + std::sin(2 * kPi * wr * i / SR)) + fd * (1 + std::sin(2 * kPi * fr * i / SR));
    const double p = (double)i - d; const long k = (long)std::floor(p); const double u = p - k;
    y[i] = (k >= 0 && k + 1 < (long)x.size()) ? (float)(x[k] * (1 - u) + x[k + 1] * u) : 0.f;
  }
  x.swap(y);
}

struct PlaceOut { std::string name, desc; };

// gra w miejscu: pogłos i kąt mikrofonu na instrumentach (mix i clean razem), potem szumy miejsca i otoczenie gen 4 (tylko mix)
static PlaceOut applyPlace(Rng& r, int place, std::vector<float>& g, std::vector<float>& mix) {
  PlaceOut po; po.name = kPlaces[place];
  char b[160];
  double rt = 0, wet = 0;
  switch (place) {
    case 0: if (r.uni() < 0.5) { rt = r.uni(0.1, 0.3); wet = r.uni(0.03, 0.12); } break;
    case 1: rt = r.uni(0.2, 0.7); wet = r.uni(0.08, 0.35); break;
    case 2: rt = r.uni(0.5, 1.1); wet = r.uni(0.15, 0.4); break;
    case 3: rt = r.uni(1.4, 2.6); wet = r.uni(0.25, 0.5); break;
    case 4: rt = r.uni(2.5, 6.0); wet = r.uni(0.4, 0.7); break;
    case 5: break;
    default: if (r.uni() < 0.8) { rt = r.uni(0.15, 1.6); wet = r.uni(0.05, 0.5); } break;
  }
  if (rt > 0) envfx::schroederReverb(g, SR, rt, wet);
  if (place != 0 || r.uni() < 0.5) envfx::micAngle(r, g);
  snprintf(b, sizeof b, "pogłos=%.2f/%.2f", rt, wet); po.desc = b;
  const double gRms = rmsv(g);
  double gPeak = 1e-9; for (float v : g) gPeak = std::max(gPeak, (double)std::fabs(v));
  const size_t n = g.size();
  std::vector<float> nz(n, 0.f);
  // otoczenie z gen 4: zawsze w próbie w domu, w innych miejscach rzadziej i ciszej
  const double envP = place == 10 ? 1.0 : place == 0 ? 0.15 : place == 3 || place == 4 ? 0.4 : 0.6;
  if (r.uni() < envP) {
    envfx::EnvDesc ed; envfx::environment(r, nz, gRms, gPeak, ed);
    const double k = place == 10 ? 1.0 : place == 0 ? r.uni(0.03, 0.2) : r.uni(0.1, 0.7);
    for (auto& v : nz) v *= (float)k;
    po.desc += " otoczenie=" + ed.parts;
  }
  auto addNoise = [&](std::vector<float> s, double snrDb) {
    const double k = gRms / std::pow(10.0, snrDb / 20.0) / rmsv(s);
    for (size_t i = 0; i < n; ++i) nz[i] += (float)(s[i] * k);
  };
  if (place == 3 || place == 4) { // publiczność / ludzie: szum pasmowy, czasem kaszel (stuk szumu)
    std::vector<float> s(n); for (auto& v : s) v = (float)r.gauss(); lowpass(s, r.uni(800, 2500)); highpass(s, 150);
    addNoise(s, r.uni(25, 45));
  }
  if (place == 5) { // wiatr: niski szum w porywach + ptaki (krótkie świergoty)
    std::vector<float> s(n); double z = 0, gst = r.uni(0.1, 0.5);
    for (size_t i = 0; i < n; ++i) { z += 0.002 * (r.gauss() - z); s[i] = (float)(z * (1 + std::sin(2 * kPi * gst * i / SR + std::sin(0.7 * i / SR)))); }
    addNoise(s, r.uni(5, 30));
    if (r.uni() < 0.5) {
      std::vector<float> br(n, 0.f);
      for (double t = r.uni(0, 2); t < n / (double)SR; t += r.uni(0.5, 4)) {
        const double f = r.uni(2500, 6000), len = r.uni(0.05, 0.25), sw = r.uni(-0.5, 0.5);
        double ph = 0;
        for (size_t i = (size_t)(t * SR); i < std::min(n, (size_t)((t + len) * SR)); ++i) {
          const double u = (i - t * SR) / (len * SR);
          ph += 2 * kPi * f * (1 + sw * u) / SR;
          br[i] += (float)(std::sin(ph) * std::sin(kPi * u));
        }
      }
      addNoise(br, r.uni(15, 35));
    }
    po.desc += " wiatr";
  }
  if (place == 8) { // płyta: trzaski i szum, dudnienie talerza
    std::vector<float> s(n, 0.f);
    const double rate = r.uni(2, 20);
    for (double t = 0; t < n / (double)SR; t += -std::log(r.uni() + 1e-9) / rate) {
      const size_t i = (size_t)(t * SR); const double a = std::exp(r.uni(-2, 2)) * (r.uni() < 0.5 ? -1 : 1);
      for (int k = 0; k < 6 && i + k < n; ++k) s[i + k] += (float)(a * std::exp(-k * 0.8));
    }
    addNoise(s, r.uni(18, 35));
    std::vector<float> h(n); for (auto& v : h) v = (float)r.gauss(); highpass(h, 3000); addNoise(h, r.uni(28, 45));
  }
  if (place == 7) { std::vector<float> h(n); for (auto& v : h) v = (float)r.gauss(); highpass(h, 2000); addNoise(h, r.uni(18, 35)); }
  for (size_t i = 0; i < n; ++i) mix[i] = g[i] + nz[i];
  // łańcuch urządzenia: dotyczy całego sygnału z mikrofonu; clean dostaje te same filtry liniowe (bez szumów i przesteru)
  auto both = [&](auto fn) { fn(mix); fn(g); };
  if (place == 6) { both([&](std::vector<float>& x) { highpass(x, r.uni(250, 400)); }); const double fc = r.uni(3000, 3600);
    both([&](std::vector<float>& x) { lowpass(x, fc); }); compress(mix, r.uni(3, 8), 0.5); softClip(mix, r.uni(1.5, 4)); po.desc += " pasmo_telefonu"; }
  if (place == 7) { const double fc = r.uni(4500, 9000); both([&](std::vector<float>& x) { lowpass(x, fc); });
    Rng r2(r.next()); Rng r3 = r2; wowFlutter(mix, r2); wowFlutter(g, r3); compress(mix, r.uni(2, 4), 0.7); po.desc += " kaseta"; }
  if (place == 8) { const double fc = r.uni(6000, 11000); both([&](std::vector<float>& x) { lowpass(x, fc); }); both([&](std::vector<float>& x) { highpass(x, 40); }); }
  if (place == 9) { const double fc = r.uni(5000, 8000); both([&](std::vector<float>& x) { lowpass(x, fc); }); compress(mix, r.uni(3, 10), 0.6); po.desc += " kompresja"; }
  if (place != 6 && r.uni() < 0.08) { softClip(mix, r.uni(1.5, 6)); po.desc += " przester"; }
  if (place != 6 && place != 9 && r.uni() < 0.15) { compress(mix, r.uni(2, 6), r.uni(0.5, 1.5)); po.desc += " kompresor"; }
  return po;
}

// ------------------------------------------------------------ manifest
struct Piece { std::string id, source, composer, title, split, file; };

static std::vector<std::string> csvRow(const std::string& line) {
  std::vector<std::string> o; std::string cur; bool q = false;
  for (size_t i = 0; i < line.size(); ++i) {
    const char c = line[i];
    if (q) { if (c == '"') { if (i + 1 < line.size() && line[i + 1] == '"') { cur += '"'; ++i; } else q = false; } else cur += c; }
    else if (c == '"') q = true;
    else if (c == ',') { o.push_back(cur); cur.clear(); }
    else if (c != '\r') cur += c;
  }
  o.push_back(cur);
  return o;
}

static std::string jsonEsc(const std::string& s) {
  std::string o; for (char c : s) { if (c == '"' || c == '\\') o += '\\'; if ((unsigned char)c >= 32) o += c; } return o;
}

// ------------------------------------------------------------ generator
struct Opts {
  std::string out, root, split = "train"; int versions = 4, clips = 2; double lenLo = 10, lenHi = 20; uint64_t seed = 1;
  bool clean = false, midi = false; double guitar = 0.35; std::vector<int> onlyInst; int onlyPlace = -1;
};

static int pickInst(Rng& r, const Opts& o) {
  if (!o.onlyInst.empty()) return o.onlyInst[r.range(0, (int)o.onlyInst.size() - 1)];
  std::vector<int> gu, ot;
  for (int i = 0; i < inst::kNumInst; ++i) (inst::kInst[i].guitar ? gu : ot).push_back(i);
  if (r.uni() < o.guitar) return r.uni() < 0.5 ? 0 : gu[r.range(0, (int)gu.size() - 1)]; // połowa gitar to gitara klasyczna
  return ot[r.range(0, (int)ot.size() - 1)];
}

static int fold(int m, int lo, int hi) {
  lo = std::max(lo, kLo); hi = std::min(hi, kHi);
  while (m < lo) m += 12;
  while (m > hi) m -= 12;
  return m < lo ? lo : m;
}

static std::string clip(const Opts& o, const Piece& pc, const std::vector<MNote>& ver, const Version& vd, int vk, int ck, Rng& r) {
  double T = 0; for (const auto& n : ver) T = std::max(T, n.t0);
  const double L = r.uni(o.lenLo, o.lenHi);
  // wybór okna: start w chwili jakiejś nuty, min. 6 nut
  std::vector<MNote> sel;
  for (int tries = 0; tries < 12 && sel.size() < 6; ++tries) {
    sel.clear();
    const double ws = T > L ? ver[r.range(0, (int)ver.size() - 1)].t0 * (T - L * 0.5 > 0 ? 1 : 0) : 0.0;
    const double w0 = std::min(ws, std::max(0.0, T - L * 0.6));
    for (const auto& n : ver) if (n.t0 >= w0 && n.t0 < w0 + L - 0.3) { MNote m = n; m.t0 -= w0; m.t1key -= w0; m.t1ped -= w0; sel.push_back(m); }
  }
  if (sel.size() < 6) return "";
  const double lead = r.uni(0.2, 1.0);
  const size_t n = (size_t)((L + lead + 1.2) * SR);
  const double tEnd = n / (double)SR - 0.05;
  // głosy -> instrumenty
  int nv = 0; for (const auto& m : sel) nv = std::max(nv, m.voice + 1);
  if (nv == 1 && r.uni() < 0.5) { // jeden głos (np. fortepian MAESTRO): czasem podział na dwie ręce, żeby dało się dać dwa instrumenty
    const int split = r.range(55, 64);
    for (auto& m : sel) m.voice = m.midi < split ? 1 : 0;
    nv = 2;
  }
  const double u = r.uni();
  std::vector<int> vi(nv);
  std::string mode;
  if (u < 0.5 || nv == 1) { const int k = pickInst(r, o); for (auto& x : vi) x = k; mode = "solo"; }
  else if (u < 0.85) { for (auto& x : vi) x = pickInst(r, o); mode = "zespol"; }
  else { for (auto& x : vi) x = pickInst(r, o); vi[r.range(0, nv - 1)] = r.uni() < 0.5 ? 0 : r.range(0, 3); mode = "gitara+zespol"; }
  std::set<int> used(vi.begin(), vi.end());
  std::map<int, inst::Params> params;
  for (int k : used) params[k] = inst::randomParams(k, r);
  std::map<int, double> instGain; // balans: każdy instrument inną głośność
  for (int k : used) instGain[k] = std::pow(10.0, r.uni(-8, 3) / 20.0);
  // nuty w zakresie instrumentu
  struct TN { NoteEvent e; int inst, voice; };
  std::vector<TN> tn;
  for (const auto& m : sel) {
    TN t; t.inst = vi[m.voice]; t.voice = m.voice;
    t.e.midi = fold(m.midi, inst::kInst[t.inst].lo, inst::kInst[t.inst].hi);
    t.e.t0 = m.t0 + lead; t.e.t1 = std::min(m.t1ped + lead, tEnd);
    t.e.vel = (float)std::clamp(m.vel / 127.0, 0.06, 1.0);
    if (t.e.t1 - t.e.t0 < 0.03) continue;
    tn.push_back(t);
  }
  // usuń duplikaty (ta sama wysokość, ten sam instrument, nachodzące): po przeniesieniu oktaw i odwróceniu się zdarzają
  std::sort(tn.begin(), tn.end(), [](const TN& a, const TN& b) { return a.e.t0 < b.e.t0; });
  std::vector<TN> keep;
  for (const auto& t : tn) {
    bool dup = false;
    for (auto it = keep.rbegin(); it != keep.rend() && t.e.t0 - it->e.t0 < 8; ++it)
      if (it->e.midi == t.e.midi && it->e.t1 > t.e.t0) { if (t.e.t0 - it->e.t0 < 0.03) { dup = true; break; } it->e.t1 = t.e.t0; }
    if (!dup) keep.push_back(t);
  }
  std::vector<float> g(n, 0.f);
  const double centsG = r.uni() < 0.25 ? r.uni(-30, 30) : r.uni(-5, 5); // strój zespołu (A=440 ± …)
  std::vector<double> freq(keep.size()), aud(keep.size());
  for (int k : used) {
    std::vector<NoteEvent> ev; std::vector<size_t> idx;
    for (size_t i = 0; i < keep.size(); ++i) if (keep[i].inst == k) {
      NoteEvent e = keep[i].e;
      ev.push_back(e); idx.push_back(i);
    }
    std::vector<float> bus(n, 0.f);
    std::vector<double> f, a;
    std::vector<NoteEvent> evc = ev;
    for (auto& e : evc) e.vel = (float)std::clamp(e.vel * instGain[k] / std::max(0.3, instGain[k]), 0.04, 1.0);
    inst::renderInst(bus.data(), n, SR, evc, params[k], r.next(), &f, &a, r.uni(0, 6));
    const double cg = std::pow(2.0, centsG / 1200.0);
    for (size_t j = 0; j < idx.size(); ++j) { freq[idx[j]] = f[j] * cg; aud[idx[j]] = a[j]; }
    // przestrojenie całego zespołu: przesunięcie częstotliwości przez zmianę szybkości odczytu bufora (ułamki procenta)
    if (std::fabs(centsG) > 0.5) {
      std::vector<float> y(n, 0.f);
      for (size_t i = 0; i < n; ++i) { const double p = i * cg; const size_t q = (size_t)p; const double w = p - q; if (q + 1 < n) y[i] = (float)(bus[q] * (1 - w) + bus[q + 1] * w); }
      bus.swap(y);
    }
    const double gk = instGain[k];
    for (size_t i = 0; i < n; ++i) g[i] += (float)(bus[i] * gk);
  }
  if (std::fabs(centsG) > 0.5) { // zmiana szybkości przesuwa też czasy
    const double cg = std::pow(2.0, centsG / 1200.0);
    for (size_t i = 0; i < keep.size(); ++i) { keep[i].e.t0 /= cg; keep[i].e.t1 /= cg; aud[i] /= cg; }
  }
  const int place = o.onlyPlace >= 0 ? o.onlyPlace : r.range(0, kNumPlaces - 1);
  std::vector<float> mix(n);
  const PlaceOut po = applyPlace(r, place, g, mix);
  double pk = 1e-9; for (float v : mix) pk = std::max(pk, (double)std::fabs(v));
  const double k = std::pow(10.0, r.uni(-30, -1) / 20.0) / pk;
  for (size_t i = 0; i < n; ++i) { mix[i] *= (float)k; g[i] *= (float)k; }
  char idb[160]; snprintf(idb, sizeof idb, "cls_%s_v%d_c%d", pc.id.c_str(), vk, ck);
  const std::string id = idb;
  wavio::write16(o.out + "/" + id + ".wav", mix, SR);
  if (o.clean) wavio::write16(o.out + "/" + id + ".clean.wav", g, SR);
  std::string insts; // obsada bez powtórzeń, w kolejności głosów
  std::set<int> seen;
  for (int x : vi) if (seen.insert(x).second) insts += std::string(insts.empty() ? "" : "+") + inst::kInst[x].name;
  FILE* f = fopen((o.out + "/" + id + ".truth.json").c_str(), "w");
  fprintf(f, "{\"id\":\"%s\",\"kind\":\"classical\",\"piece\":\"%s\",\"composer\":\"%s\",\"title\":\"%s\",\"version\":\"%s\","
             "\"ensemble\":\"%s\",\"instruments\":\"%s\",\"place\":\"%s\",\"env\":\"%s\",\"fs\":%d,\"dur\":%.3f,\"chords\":[],\n\"notes\":[",
          id.c_str(), pc.id.c_str(), jsonEsc(pc.composer).c_str(), jsonEsc(pc.title).c_str(), vd.desc().c_str(), mode.c_str(), insts.c_str(),
          po.name.c_str(), jsonEsc(po.desc).c_str(), SR, n / (double)SR);
  for (size_t i = 0; i < keep.size(); ++i)
    fprintf(f, "%s{\"midi\":%d,\"t0\":%.3f,\"t1\":%.3f,\"ta\":%.3f,\"f\":%.4f,\"i\":\"%s\",\"v\":%d}", i ? "," : "", keep[i].e.midi, keep[i].e.t0,
            keep[i].e.t1, aud[i], freq[i], inst::kInst[keep[i].inst].name, keep[i].voice);
  fprintf(f, "]}\n");
  fclose(f);
  char row[600];
  snprintf(row, sizeof row, "%s,%s,%s,%d,\"%s\",%s,%s,%s,%.2f,%zu\n", id.c_str(), pc.id.c_str(), pc.split.c_str(), vk, vd.desc().c_str(), mode.c_str(),
           insts.c_str(), po.name.c_str(), n / (double)SR, keep.size());
  return row;
}

int main(int argc, char** argv) {
  if (argc < 4) {
    fprintf(stderr, "użycie: gen_classical <manifest.csv> <katalog_korpusu> <katalog_wyjścia> [--split train|validation|test|all] [--versions 4]\n"
                    "        [--clips 2] [--len 10 20] [--seed 1] [--jobs N] [--limit N] [--clean] [--midi] [--guitar 0.35]\n"
                    "        [--inst nazwa,nazwa] [--place nazwa] [--list]\n");
    return 2;
  }
  Opts o; o.root = argv[2]; o.out = argv[3];
  int jobs = (int)std::max(1u, std::thread::hardware_concurrency()), limit = 0;
  for (int i = 4; i < argc; ++i) {
    const std::string a = argv[i];
    auto nx = [&]() { return std::string(i + 1 < argc ? argv[++i] : ""); };
    if (a == "--split") o.split = nx();
    else if (a == "--versions") o.versions = std::stoi(nx());
    else if (a == "--clips") o.clips = std::stoi(nx());
    else if (a == "--len") { o.lenLo = std::stod(nx()); o.lenHi = std::stod(nx()); }
    else if (a == "--seed") o.seed = std::stoull(nx());
    else if (a == "--jobs") jobs = std::stoi(nx());
    else if (a == "--limit") limit = std::stoi(nx());
    else if (a == "--clean") o.clean = true;
    else if (a == "--midi") o.midi = true;
    else if (a == "--guitar") o.guitar = std::stod(nx());
    else if (a == "--inst") { std::stringstream ss(nx()); std::string t; while (std::getline(ss, t, ',')) { const int k = inst::instByName(t); if (k < 0) { fprintf(stderr, "nieznany instrument %s\n", t.c_str()); return 2; } o.onlyInst.push_back(k); } }
    else if (a == "--place") { const std::string p = nx(); for (int k = 0; k < kNumPlaces; ++k) if (p == kPlaces[k]) o.onlyPlace = k; if (o.onlyPlace < 0) { fprintf(stderr, "nieznane miejsce %s\n", p.c_str()); return 2; } }
    else if (a == "--list") {
      printf("instrumenty:"); for (int k = 0; k < inst::kNumInst; ++k) printf(" %s", inst::kInst[k].name);
      printf("\nmiejsca:"); for (int k = 0; k < kNumPlaces; ++k) printf(" %s", kPlaces[k]); printf("\n"); return 0;
    } else { fprintf(stderr, "nieznana opcja %s\n", a.c_str()); return 2; }
  }
  std::ifstream mf(argv[1]);
  if (!mf) { fprintf(stderr, "brak manifestu %s\n", argv[1]); return 1; }
  std::string line; std::getline(mf, line);
  const auto hdr = csvRow(line);
  auto col = [&](const char* nm) { for (size_t i = 0; i < hdr.size(); ++i) if (hdr[i] == nm) return (int)i; return -1; };
  const int cId = col("id"), cSrc = col("source"), cComp = col("composer"), cTit = col("title"), cSpl = col("split"), cFile = col("file");
  std::vector<Piece> pieces;
  while (std::getline(mf, line)) {
    if (line.empty()) continue;
    const auto r = csvRow(line);
    if ((int)r.size() <= std::max({cId, cSrc, cComp, cTit, cSpl, cFile})) continue;
    Piece p{r[cId], r[cSrc], r[cComp], r[cTit], r[cSpl], r[cFile]};
    if (o.split != "all" && p.split != o.split) continue;
    pieces.push_back(p);
  }
  if (limit > 0 && (int)pieces.size() > limit) { // równomiernie po całym manifeście (różne źródła i kompozytorzy)
    std::vector<Piece> s; for (int i = 0; i < limit; ++i) s.push_back(pieces[(size_t)i * pieces.size() / limit]); pieces.swap(s);
  }
  if (o.midi) { const std::string md = o.out + "/midi"; if (system(("mkdir -p '" + md + "'").c_str())) {} }
  else if (system(("mkdir -p '" + o.out + "'").c_str())) {}
  std::vector<std::string> rows(pieces.size());
  std::atomic<size_t> next{0}, done{0}, bad{0};
  std::mutex pm;
  auto worker = [&]() {
    for (size_t pi; (pi = next++) < pieces.size();) {
      const Piece& pc = pieces[pi];
      std::vector<MNote> notes;
      if (!readMidi(o.root + "/" + pc.file, notes)) { ++bad; continue; }
      uint64_t h = o.seed * 0x9E3779B97F4A7C15ull; for (char c : pc.id) h = (h ^ (uint8_t)c) * 0x100000001B3ull;
      int nVoices = 0; for (const auto& m : notes) nVoices = std::max(nVoices, m.voice + 1);
      std::string acc;
      for (int vk = 0; vk < o.versions; ++vk) {
        Rng r(h + vk * 7919);
        const Version vd = randomVersion(r, vk, nVoices);
        const auto ver = applyVersion(notes, vd, r);
        if (ver.size() < 6) continue;
        if (o.midi) {
          std::vector<int> prog(16); for (auto& x : prog) x = gmProgram(pickInst(r, o));
          char mp[300]; snprintf(mp, sizeof mp, "%s/midi/%s_v%d.mid", o.out.c_str(), pc.id.c_str(), vk);
          writeMidi(mp, ver, prog);
        }
        for (int ck = 0; ck < o.clips; ++ck) { Rng rc(h + vk * 7919 + ck * 104729 + 1); acc += clip(o, pc, ver, vd, vk, ck, rc); }
      }
      rows[pi] = acc;
      const size_t d = ++done;
      if (d % 25 == 0 || d == pieces.size()) { std::lock_guard<std::mutex> l(pm); fprintf(stderr, "\r%zu/%zu utworów", d, pieces.size()); }
    }
  };
  std::vector<std::thread> th;
  for (int j = 0; j < jobs; ++j) th.emplace_back(worker);
  for (auto& t : th) t.join();
  FILE* f = fopen((o.out + "/index.csv").c_str(), "w");
  fprintf(f, "id,piece,split,version,transform,ensemble,instruments,place,dur,notes\n");
  size_t clips = 0;
  for (const auto& r : rows) { fputs(r.c_str(), f); clips += std::count(r.begin(), r.end(), '\n'); }
  fclose(f);
  fprintf(stderr, "\nzapisano %zu nagrań z %zu utworów w %s (nieczytelnych MIDI: %zu)\n", clips, (size_t)done, o.out.c_str(), (size_t)bad);
  return 0;
}
