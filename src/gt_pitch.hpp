// gt_pitch.hpp - wykrywanie wielu wysokości naraz (grzebień harmoniczny na pikach
// widma + iteracyjne kasowanie) oraz YIN do stroika.
#pragma once
#include <cstdio>
#include "gt_spectrum.hpp"

namespace gt {

struct NoteDet {
  int midi = 0;
  float f = 0;      // dopasowana częstotliwość podstawowa [Hz]
  float cents = 0;  // odchyłka od nominalnej (względem aktualnego odniesienia A4)
  float amp = 0;    // siła (pierwiastek z sumy kwadratów amplitud 4 pierwszych alikwotów)
  float score = 0;
  int nh = 0;       // ile z 6 pierwszych alikwotów znaleziono
  bool sustained = false; // nuta podtrzymana: wykryta z obniżonym progiem, bo już brzmiała
  bool octave = false; // podwojenie oktawowe niższej nuty (wykryte po nadmiarze parzystych alikwotów)
};

class MultiPitch {
public:
  struct Options {
    double fs = 11025;
    int lo = 36, hi = 88;
    double B = 2.5e-4;     // nieharmoniczność struny (f_h = h f0 sqrt(1+B h^2))
    int maxH = 14;
    double dynDb = 42;
    double relThr = 0.2;
    int maxNotes = 6;
    bool octaves = true;     // wykrywaj oktawowe podwojenia
    bool joint = true;       // ocena łączna po wyborze zachłannym (poduktawy, nuty w całości wyjaśnione przez inne)
    double jointSwap = 0.0;  // poduktawa -> oktawa wyżej, gdy jej własny wkład < tej części całości
    double jointDrop = 0.12; // usuń nutę, gdy jej własny wkład < tej części całości
    double octRatio = 1.4;
    double octRatioMono = 2.2;
    bool octModel = true;          // test oktaw z modelem miejsca szarpnięcia
    double octModelThr = 1.4, octModelThrMono = 2.5;
  };

  void init(const Options& o, double a4) {
    o_ = o;
    setA4(a4);
  }

  void setRange(int lo, int hi) {
    if (lo == o_.lo && hi == o_.hi) return;
    o_.lo = lo; o_.hi = hi;
    setA4(a4_);
  }

  void setA4(double a4) {
    a4_ = a4;
    cands_.clear();
    for (int m = o_.lo; m <= o_.hi; ++m) {
      Cand c;
      c.m = m;
      c.f0 = midiFreq(m, a4);
      for (int h = 1; h <= o_.maxH; ++h) {
        const double f = h * c.f0 * std::sqrt(1 + o_.B * h * h);
        if (f > o_.fs * 0.5 * 0.92) break;
        c.hf.push_back((float)f);
        c.w.push_back((float)((c.f0 + 52) / (h * c.f0 + 320)));
      }
      for (int h = 1; h <= 40; ++h) {
        const double f = h * c.f0 * std::sqrt(1 + o_.B * h * h);
        if (f > 4800) break;
        c.all.push_back((float)f);
      }
      cands_.push_back(std::move(c));
    }
  }

  double a4() const { return a4_; }
  double jointTol0_ = 18, jointTol1_ = 1.0, jointH1_ = 0.35;
  void setOctModel(bool on, double thr, double mono) { o_.octModel = on; o_.octModelThr = thr; o_.octModelThrMono = mono; }
  void setJoint(bool j, double swap, double drop) { o_.joint = j; o_.jointSwap = swap; o_.jointDrop = drop; }
#ifdef GT_DEBUG
  int dbgMidi_ = -1;
#endif

  // indeks najsilniejszego piku w przedziale +-tol centów wokół f, albo -1
  static int find(const std::vector<Peak>& peaks, double f, double tol) {
    const double lo = f * std::pow(2.0, -tol / 1200), hi = f * std::pow(2.0, tol / 1200);
    int a = 0, b = (int)peaks.size();
    while (a < b) {
      const int mid = (a + b) >> 1;
      if (peaks[mid].f < lo) a = mid + 1; else b = mid;
    }
    int best = -1;
    float ba = 0;
    for (int i = a; i < (int)peaks.size() && peaks[i].f <= hi; ++i)
      if (peaks[i].a > ba) { ba = peaks[i].a; best = i; }
    return best;
  }

  void detect(const std::vector<Peak>& peaks, std::vector<NoteDet>& notes) {
    notes.clear();
    const int P = (int)peaks.size();
    if (!P) return;
    double aMax = 0;
    for (const auto& p : peaks) aMax = std::max<double>(aMax, p.a);
    v_.assign(P, 0.0);
    for (int i = 0; i < P; ++i) v_[i] = clampd(1 + 20 * std::log10(peaks[i].a / aMax) / o_.dynDb, 0, 1);
    expl_.assign(P, 0);
    chosen_.assign(cands_.size(), 0);
    double base = 0;
    for (int it = 0; it < o_.maxNotes; ++it) {
      int bestC = -1;
      double bestScore = 0;
      int bestM6 = 0;
      for (size_t ci = 0; ci < cands_.size(); ++ci) {
        if (chosen_[ci]) continue;
        const Cand& c = cands_[ci];
        double sal = 0;
        int m6 = 0, un = 0;
        bool h1un = false;
        for (size_t h = 0; h < c.hf.size(); ++h) {
          const int pi = find(peaks, c.hf[h], 28 + 1.5 * h);
          idx_[h] = pi;
          if (pi < 0) continue;
          const uint8_t e = expl_[pi];
          sal += c.w[h] * v_[pi] * (e ? 0.25 : 1.0);
          if (h < 6) ++m6;
          if (h < 8 && !e && v_[pi] > 0.12) ++un;
          if (h == 0 && !e && v_[pi] > 0.25) h1un = true;
        }
#ifdef GT_DEBUG
        if (dbgMidi_ == c.m) fprintf(stderr, "  [dbg] it=%d midi=%d f0=%.1f m6=%d un=%d h1un=%d sal=%.3f\n", it, c.m, c.f0, m6, un, (int)h1un, sal);
#endif
        if (m6 < (c.f0 < 450 ? 3 : 2) || (un < 2 && !(h1un && m6 >= 3))) continue;
        const double score = sal * (0.55 + 0.45 * m6 / std::min<size_t>(6, c.hf.size()));
        if (bestC < 0 || score > bestScore) {
          bestC = (int)ci; bestScore = score; bestM6 = m6;
          for (size_t h = 0; h < c.hf.size(); ++h) bestIdx_[h] = idx_[h];
        }
      }
      if (bestC < 0) break;
      if (it == 0) base = bestScore;
      else if (bestScore < o_.relThr * base) break;
      chosen_[bestC] = 1;
      const Cand& c = cands_[bestC];
      double num = 0, den = 0, a2 = 0;
      // regresja ważona: (f_h/h)^2 = f0^2 (1 + B h^2)  ->  prosta względem x = h^2
      double sw = 0, sx = 0, sy = 0, sxx = 0, sxy = 0;
      int np = 0;
      for (size_t h = 0; h < c.hf.size(); ++h) {
        const int pi = bestIdx_[h];
        if (pi < 0) continue;
        if (!expl_[pi] && h < 8) {
          const double a = peaks[pi].a;
          num += a * peaks[pi].f / ((h + 1) * std::sqrt(1 + o_.B * (h + 1) * (h + 1)));
          den += a;
          if (h < 4) a2 += a * a;
          const double hh = (double)(h + 1), y = (peaks[pi].f / hh) * (peaks[pi].f / hh), x = hh * hh;
          sw += a; sx += a * x; sy += a * y; sxx += a * x * x; sxy += a * x * y;
          ++np;
        }
        expl_[pi] = 1;
      }
      for (size_t h = 0; h < c.all.size(); ++h) {
        const int pi = find(peaks, c.all[h], 28 + 1.5 * h);
        if (pi >= 0) expl_[pi] = 1;
      }
      double fe = den > 0 ? num / den : c.f0;
      if (np >= 3) {
        const double dd = sw * sxx - sx * sx;
        if (std::fabs(dd) > 1e-9 * sw * sxx) {
          const double c1 = (sw * sxy - sx * sy) / dd, c0 = (sy - c1 * sx) / sw;
          const double B = c0 > 0 ? c1 / c0 : -1;
          if (c0 > 0 && B > -2e-4 && B < 1.5e-3) fe = std::sqrt(c0);
        }
      }
      NoteDet n;
      n.midi = c.m; n.f = (float)fe; n.cents = (float)(1200 * std::log2(fe / c.f0));
      n.amp = (float)std::sqrt(a2); n.score = (float)bestScore; n.nh = bestM6;
      notes.push_back(n);
    }
    if (o_.joint && notes.size() >= 1) jointRevise(peaks, notes);
    if (o_.octaves) addOctaveDoubles(peaks, notes);
    std::sort(notes.begin(), notes.end(), [](const NoteDet& a, const NoteDet& b) { return a.midi < b.midi; });
  }

  // Oktawowe podwojenie (np. E2 + E3): jego alikwoty pokrywają się z parzystymi alikwotami niższej nuty,
  // więc zwykłe kasowanie je ukrywa. Zdradza je nadmiar energii w parzystych alikwotach względem
  // gładkiej obwiedni nieparzystych: a(2k) / sqrt(a(2k-1) a(2k+1)) > próg (dla samotnej struny < 1).
  void addOctaveDoubles(const std::vector<Peak>& peaks, std::vector<NoteDet>& notes) {
    const size_t n0 = notes.size();
    // w akordzie podwojenia oktawowe są częste, przy pojedynczej nucie rzadkie: tam wymagamy wyraźniejszej nadwyżki
    const double thr = n0 >= 2 ? o_.octRatio : o_.octRatioMono;
    for (size_t i = 0; i < n0; ++i) {
      const NoteDet base = notes[i];
      const int m2 = base.midi + 12;
      if (m2 > o_.hi || base.nh < 5) continue;
      bool dup = false;
      for (const auto& q : notes) if (q.midi == m2) dup = true;
      if (dup) continue;
      const Cand& c = cands_[base.midi - o_.lo];
      float a[9] = {0};
      for (int h = 1; h <= 7 && h <= (int)c.hf.size(); ++h) {
        const int pi = find(peaks, c.hf[h - 1] * std::pow(2.0, base.cents / 1200.0), 22 + 1.5 * h);
        a[h] = pi >= 0 ? peaks[pi].a : 0.f;
      }
      int votes = 0, tried = 0;
      bool yes = false;
      double ex = 0;
      if (o_.octModel && pluckExcess(peaks, notes, i, ex)) {
        yes = ex > (n0 >= 2 ? o_.octModelThr : o_.octModelThrMono);
      } else {
        for (int k = 1; k <= 3; ++k) {
          if (k == 1 && c.f0 < 110) continue;
          if (a[2 * k - 1] <= 0 || a[2 * k + 1] <= 0 || a[2 * k] <= 0) continue;
          ++tried;
          if (a[2 * k] > thr * std::sqrt(a[2 * k - 1] * a[2 * k + 1])) ++votes;
        }
        yes = tried >= 2 && votes >= 2;
      }
      if (yes) {
        NoteDet n;
        n.midi = m2; n.f = base.f * 2; n.cents = base.cents;
        n.amp = a[2] * 0.5f; n.score = base.score * 0.3f; n.nh = 4; n.octave = true;
        notes.push_back(n);
      }
    }
  }

  // Model miejsca szarpnięcia (Traube i Smith 2000): struna szarpnięta w punkcie p (ułamek długości) ma alikwoty mnożone przez
  // |sin(pi h p)|, więc przy p = 1/3 brakuje 3., 6., 9. alikwotu, przy p = 1/4 4. i 8. itd. Stary test oktaw zakładał gładką
  // obwiednię i przy takiej "dziurze" w nieparzystym alikwocie dokładał fałszywą oktawę. Tu dopasowujemy p i nachylenie s
  // do alikwotów NIEPARZYSTYCH (podwojenie oktawowe ich nie dotyka), przewidujemy parzyste i zwracamy medianę nadwyżki
  // zmierzone/przewidziane. Alikwoty wspólne z innymi nutami zbioru pomijamy. false = za mało danych (użyj starego testu).
  bool pluckExcess(const std::vector<Peak>& peaks, const std::vector<NoteDet>& notes, size_t bi, double& excess) const {
    const NoteDet& base = notes[bi];
    const Cand& c = cands_[base.midi - o_.lo];
    const int H = std::min<int>(12, (int)c.hf.size());
    if (H < 8) return false;
    const double k = std::pow(2.0, base.cents / 1200.0);
    double amin = 1e9, amax = 0;
    for (const auto& p : peaks) { amin = std::min<double>(amin, p.a); amax = std::max<double>(amax, p.a); }
    const double floor = 0.7 * amin;
    double a[13] = {0};
    bool shared[13] = {false};
    for (int h = 1; h <= H; ++h) {
      const double fh = c.hf[h - 1] * k;
      const int pi = find(peaks, fh, 22 + 1.5 * h);
      a[h] = pi >= 0 ? peaks[pi].a : 0.0;
      for (size_t j = 0; j < notes.size() && !shared[h]; ++j) {
        if (j == bi || notes[j].octave) continue;
        const Cand& o = cands_[notes[j].midi - o_.lo];
        const double ko = std::pow(2.0, notes[j].cents / 1200.0);
        for (size_t q = 0; q < o.hf.size(); ++q)
          if (std::fabs(1200 * std::log2(fh / (o.hf[q] * ko))) < 35) { shared[h] = true; break; }
      }
    }
    int nOdd = 0;
    for (int h = (c.f0 < 110 ? 3 : 1); h <= H; h += 2) if (!shared[h] && a[h] > 0) ++nOdd;
    if (nOdd < 3) return false;
    double best = 1e18, bp = 0, bs = 0, bA = 0;
    for (double p = 0.05; p <= 0.351; p += 0.005) {
      for (double sl = 0.6; sl <= 2.41; sl += 0.3) {
        double sum = 0; int n = 0;
        double r[13];
        for (int h = (c.f0 < 110 ? 3 : 1); h <= H; h += 2) {
          if (shared[h] || a[h] <= 0) continue;
          r[h] = std::log(a[h]) - std::log(std::max(std::fabs(std::sin(kPi * h * p)), 0.01) / std::pow((double)h, sl));
          sum += r[h]; ++n;
        }
        const double lA = sum / n;
        double err = 0;
        for (int h = (c.f0 < 110 ? 3 : 1); h <= H; h += 2) {
          if (shared[h]) continue;
          const double m = lA + std::log(std::max(std::fabs(std::sin(kPi * h * p)), 0.01) / std::pow((double)h, sl));
          if (a[h] > 0) err += (r[h] - lA) * (r[h] - lA);
          else if (m > std::log(floor)) err += (m - std::log(floor)) * (m - std::log(floor)); // model przewiduje pik, którego nie ma
        }
        if (err < best) { best = err; bp = p; bs = sl; bA = lA; }
      }
    }
    if (best / nOdd > 0.35) return false; // model nie pasuje (np. silne rezonanse pudła): stary test
    double ex[6]; int ne = 0;
    for (int h = 2; h <= H && ne < 6; h += 2) {
      if (shared[h]) continue;
      const double pred = std::exp(bA) * std::max(std::fabs(std::sin(kPi * h * bp)), 0.01) / std::pow((double)h, bs);
      if (pred < 3 * floor) continue; // przewidziana dziura: z tego alikwotu nic nie wiadomo
      ex[ne++] = std::max(a[h], floor) / pred;
    }
    if (ne < 2) return false;
    std::sort(ex, ex + ne);
    excess = ne % 2 ? ex[ne / 2] : std::sqrt(ex[ne / 2 - 1] * ex[ne / 2]);
    (void)amax;
    return true;
  }

  // Ocena łączna (Klapuri 2006, Duan i in. 2010, Yeh i Röbel 2004): zachłanny wybór nie wraca do wybranych nut, więc
  // poduktawa wybrana wcześnie (zbiera energię wszystkich alikwotów nuty o oktawę wyżej) zostaje. Tu dla każdej nuty liczymy
  // jej własny wkład: salience pików, których nie wyjaśnia żadna inna nuta zbioru. Gdy po dodaniu nuty o oktawę wyżej
  // poduktawa nie wnosi prawie nic własnego, zastępujemy ją tą oktawą; gdy nuta nie wnosi nic nawet bez tego, usuwamy ją.
  void jointRevise(const std::vector<Peak>& peaks, std::vector<NoteDet>& notes) {
    const int P = (int)peaks.size();
    auto cover = [&](int midi, double cents, std::vector<uint8_t>& mark) {
      if (midi < o_.lo || midi > o_.hi) return;
      const Cand& c = cands_[midi - o_.lo];
      const double k = std::pow(2.0, cents / 1200.0);
      // tylko alikwoty z grzebienia (do 14.) i węższa tolerancja: gęste wysokie alikwoty niskich strun "wyjaśniałyby" wszystko
      for (size_t h = 0; h < c.hf.size(); ++h) {
        const int pi = find(peaks, c.hf[h] * k, jointTol0_ + jointTol1_ * h);
        if (pi >= 0) mark[pi] = 1;
      }
    };
    // własny wkład nuty i przy pikach oznaczonych w `other`
    auto own = [&](const NoteDet& n, const std::vector<uint8_t>& other, double& tot) {
      const Cand& c = cands_[n.midi - o_.lo];
      const double k = std::pow(2.0, n.cents / 1200.0);
      double u = 0; tot = 0;
      for (size_t h = 0; h < c.hf.size(); ++h) {
        const int pi = find(peaks, c.hf[h] * k, 28 + 1.5 * h);
        if (pi < 0) continue;
        const double s = c.w[h] * v_[pi];
        tot += s;
        if (!other[pi]) u += s;
      }
      return u;
    };
    std::vector<uint8_t> other(P);
    bool changed = true;
    for (int pass = 0; pass < 3 && changed; ++pass) {
      changed = false;
      for (size_t i = 0; i < notes.size(); ++i) {
        std::fill(other.begin(), other.end(), 0);
        for (size_t j = 0; j < notes.size(); ++j) if (j != i) cover(notes[j].midi, notes[j].cents, other);
        double tot = 0;
        const double u0 = own(notes[i], other, tot);
        if (tot <= 0) continue;
        const int up = notes[i].midi + 12;
        bool upChosen = false;
        for (const auto& q : notes) if (q.midi == up) upChosen = true;
        if (!upChosen && up <= o_.hi) {
          std::vector<uint8_t> o2 = other;
          cover(up, notes[i].cents, o2);
          const double u1 = own(notes[i], o2, tot);
          // oktawa wyżej musi mieć własny pik podstawowy
          const int f1 = find(peaks, cands_[up - o_.lo].hf[0] * std::pow(2.0, notes[i].cents / 1200.0), 28);
          // podejrzana jest tylko poduktawa bez wyraźnego własnego tonu podstawowego (prawdziwy bas go ma)
          const int h1 = find(peaks, cands_[notes[i].midi - o_.lo].hf[0] * std::pow(2.0, notes[i].cents / 1200.0), 28);
          const double v1 = h1 >= 0 && !other[h1] ? v_[h1] : 0.0;
          if (u1 < o_.jointSwap * tot && f1 >= 0 && v_[f1] > 0.3 && v1 < jointH1_) {
#ifdef GT_DEBUG
            if (std::getenv("GT_TRACE_JOINT")) fprintf(stderr, "JOINT swap %d -> %d (u1=%.3f tot=%.3f)\n", notes[i].midi, up, u1, tot);
#endif
            NoteDet& n = notes[i];
            n.midi = up; n.f *= 2; n.nh = std::max(3, n.nh / 2);
            changed = true;
            continue;
          }
        }
        // podwojenia oktawowe (ta sama klasa dźwięku niżej) z natury nie mają własnych alikwotów: o nich decyduje addOctaveDoubles
        bool octOfLower = false;
        for (const auto& q : notes) if (q.midi < notes[i].midi && (notes[i].midi - q.midi) % 12 == 0) octOfLower = true;
        if (notes.size() > 1 && !octOfLower && u0 < o_.jointDrop * tot) {
#ifdef GT_DEBUG
          if (std::getenv("GT_TRACE_JOINT")) fprintf(stderr, "JOINT drop %d (u0=%.3f tot=%.3f)\n", notes[i].midi, u0, tot);
#endif
          notes.erase(notes.begin() + i);
          changed = true;
          break;
        }
      }
    }
  }

private:
  struct Cand {
    int m = 0;
    double f0 = 0;
    std::vector<float> hf, w, all;
  };
  Options o_;
  double a4_ = 440;
  std::vector<Cand> cands_;
  std::vector<double> v_;
  std::vector<uint8_t> expl_, chosen_;
  int idx_[32], bestIdx_[32];
};

// YIN: pojedyncza wysokość dla stroika. Zwraca częstotliwość (0 = brak) i pewność 0..1.
struct YinResult { double f = 0, prob = 0; };

inline YinResult yin(const float* x, int n, double fs, double fmin = 70, double fmax = 1200, double thr = 0.12) {
  YinResult res;
  const int W = n / 2;
  const int tauMax = std::min(W - 2, (int)std::floor(fs / fmin)), tauMin = std::max(2, (int)std::floor(fs / fmax));
  if (tauMax <= tauMin + 2) return res;
  std::vector<float> cm(tauMax + 2, 1.f);
  double run = 0;
  for (int tau = 1; tau <= tauMax; ++tau) {
    double s = 0;
    for (int j = 0; j < W; ++j) { const double d = (double)x[j] - x[j + tau]; s += d * d; }
    run += s;
    cm[tau] = run > 0 ? (float)(s * tau / run) : 1.f;
  }
  int tau = -1;
  for (int t = tauMin; t <= tauMax; ++t) {
    if (cm[t] < thr) {
      while (t + 1 <= tauMax && cm[t + 1] < cm[t]) ++t;
      tau = t;
      break;
    }
  }
  if (tau < 0) {
    int m = tauMin;
    for (int t = tauMin; t <= tauMax; ++t) if (cm[t] < cm[m]) m = t;
    if (cm[m] > 0.3f) return res;
    tau = m;
  }
  double bt = tau;
  if (tau > 1 && tau < tauMax) {
    const double a = cm[tau - 1], b = cm[tau], c = cm[tau + 1], den = 2 * (a - 2 * b + c);
    if (den != 0) bt = tau + (a - c) / den;
  }
  res.f = fs / bt;
  res.prob = std::max(0.0, 1.0 - cm[tau]);
  return res;
}

} // namespace gt
