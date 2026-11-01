// gt_fingering.hpp - dobór strun i progów dla grup dźwięków (palcowanie).
// Dla pojedynczej grupy: przeszukanie wszystkich przypisań dźwięk->struna z kosztem ergonomii.
// Dla całego utworu: Viterbi po grupach, żeby ręka nie skakała po gryfie.
#pragma once
#include <string>
#include "gt_dsp.hpp"

namespace gt {

struct FretPos {
  int midi = 0;
  int s = -1; // struna 0..5 (0 = najniższa), -1 = brak pozycji
  int f = -1; // próg, 0 = pusta struna
};

struct FingerOption {
  std::vector<FretPos> pos;
  double cost = 0;
  double meanFret = 0;
  bool hasFretted = false;
};

namespace detail {

inline double staticCost(const std::vector<FretPos>& cur, int nStrings) {
  int mn = 99, mx = -1, nf = 0, opens = 0;
  double sum = 0;
  for (const auto& c : cur) {
    if (c.f == 0) { ++opens; continue; }
    mn = std::min(mn, c.f); mx = std::max(mx, c.f); sum += c.f; ++nf;
  }
  const double span = nf ? (mx - mn) : 0;
  const double mean = nf ? sum / nf : 0;
  int inv = 0;
  for (size_t a = 0; a < cur.size(); ++a)
    for (size_t b = a + 1; b < cur.size(); ++b)
      if (cur[a].s > cur[b].s) ++inv; // wyższa nuta na niższej strunie
  // przerwy między użytymi strunami (zagłuszone struny w środku akordu)
  int lo = 99, hi = -1;
  bool used[8] = {false};
  for (const auto& c : cur) { lo = std::min(lo, c.s); hi = std::max(hi, c.s); used[c.s] = true; }
  int gaps = 0;
  for (int s = lo; s <= hi; ++s) if (!used[s]) ++gaps;
  (void)nStrings;
  double cost = span * 2 + (span > 4 ? 40 : 0) + mean * 0.15 + inv * 6 - opens * 0.4;
  if (cur.size() >= 3) cost += gaps * 3;
  return cost;
}

} // namespace detail

// ------------------------------------------------------------------------------------------------
// Ograniczenia fizyczne lewej ręki. Używane do: wykluczania niemożliwych do zagrania zestawów nut
// (śledzenie ręki w silniku), palcowania na gryfie i w tabulaturze.
//  * rozpiętość między najniższym a najwyższym progiem zależy od pozycji (progi na dole są szersze),
//  * palce są cztery; kilka strun na tym samym progu to jedno barre albo osobne palce (np. C7: serdeczny i mały na progu 3),
//  * barre przykrywa wszystkie struny między skrajnymi: nie może tam być nuty na niższym progu ani pustej struny.
inline int spanLimit(int minFret) { return minFret < 5 ? 4 : (minFret < 12 ? 5 : 6); }

inline bool physicallyPlayable(const std::vector<FretPos>& cur) {
  int mn = 99, mx = -1;
  uint32_t mask = 0;
  for (const auto& c : cur) if (c.f > 0) { mn = std::min(mn, c.f); mx = std::max(mx, c.f); mask |= 1u << c.f; }
  if (mx < 0) return true; // same puste struny
  if (mx - mn > spanLimit(mn)) return false;
  // ile palców: kilka strun na jednym progu to jedno barre (gdy żadna struna pomiędzy nie leży niżej), inaczej osobne palce
  int fingers = 0;
  for (int fv = mn; fv <= mx; ++fv) {
    if (!(mask & (1u << fv))) continue;
    int smin = 99, smax = -1, n = 0;
    for (const auto& c : cur) if (c.f == fv) { smin = std::min(smin, c.s); smax = std::max(smax, c.s); ++n; }
    bool barre = n >= 2;
    if (barre) for (const auto& c : cur) if (c.s > smin && c.s < smax && c.f < fv) { barre = false; break; }
    fingers += barre ? 1 : n;
  }
  return fingers <= 4;
}

// reakcja ręki: ile progów może przejść w czasie dt [s] (stała część + prędkość po krótkim czasie reakcji)
inline double handReach(double dt) { return 3.0 + std::max(0.0, dt - 0.04) * 60.0; }

// zwraca do K najlepszych przypisań (rosnąco po koszcie statycznym)
inline void fingerOptions(const std::vector<int>& midisIn, const int open[6], int maxFret, int K, std::vector<FingerOption>& out) {
  out.clear();
  std::vector<int> ms = midisIn;
  std::sort(ms.begin(), ms.end());
  ms.erase(std::unique(ms.begin(), ms.end()), ms.end());
  if (ms.size() > 6) ms.resize(6);
  const int n = (int)ms.size();
  if (!n) return;
  std::vector<std::vector<FretPos>> opts(n);
  for (int i = 0; i < n; ++i)
    for (int s = 0; s < 6; ++s) {
      const int f = ms[i] - open[s];
      if (f >= 0 && f <= maxFret) opts[i].push_back({ms[i], s, f});
    }
  std::vector<FretPos> cur;
  std::vector<FingerOption> all;
  struct Rec {
    const std::vector<std::vector<FretPos>>& opts;
    std::vector<FretPos>& cur;
    std::vector<FingerOption>& all;
    int n;
    void go(int i, unsigned used) {
      if (all.size() > 4000) return;
      if (i == n) {
        FingerOption o;
        o.pos = cur;
        o.cost = detail::staticCost(cur, 6);
        double sum = 0; int nf = 0;
        for (const auto& c : cur) if (c.f > 0) { sum += c.f; ++nf; }
        o.hasFretted = nf > 0;
        o.meanFret = nf ? sum / nf : 0;
        all.push_back(std::move(o));
        return;
      }
      for (const auto& o : opts[i]) {
        if (used & (1u << o.s)) continue;
        cur.push_back(o);
        go(i + 1, used | (1u << o.s));
        cur.pop_back();
      }
    }
  } rec{opts, cur, all, n};
  rec.go(0, 0);
  if (all.empty()) { // nie da się zagrać wszystkiego na różnych strunach: pomiń niegrywalne
    FingerOption o;
    for (int m : ms) o.pos.push_back({m, -1, -1});
    out.push_back(o);
    return;
  }
  std::sort(all.begin(), all.end(), [](const FingerOption& a, const FingerOption& b) { return a.cost < b.cost; });
  for (size_t i = 0; i < all.size() && (int)out.size() < K; ++i) out.push_back(all[i]);
}


// jak fingerOptions, ale zostawia wyłącznie układy możliwe do zagrania jedną ręką (puste, gdy zestaw jest niemożliwy)
inline void handOptions(const std::vector<int>& midisIn, const int open[6], int maxFret, int K, std::vector<FingerOption>& out) {
  out.clear();
  std::vector<int> ms = midisIn;
  std::sort(ms.begin(), ms.end());
  ms.erase(std::unique(ms.begin(), ms.end()), ms.end());
  if (ms.size() > 6 || ms.empty()) return;
  const int n = (int)ms.size();
  std::vector<std::vector<FretPos>> opts(n);
  for (int i = 0; i < n; ++i)
    for (int s = 0; s < 6; ++s) {
      const int f = ms[i] - open[s];
      if (f >= 0 && f <= maxFret) opts[i].push_back({ms[i], s, f});
    }
  for (const auto& o : opts) if (o.empty()) return; // nuta poza zakresem gitary
  std::vector<FretPos> cur;
  std::vector<FingerOption> all;
  struct Rec {
    const std::vector<std::vector<FretPos>>& opts;
    std::vector<FretPos>& cur;
    std::vector<FingerOption>& all;
    int n;
    void go(int i, unsigned used, int mn, int mx) {
      if (all.size() > 3000) return;
      if (i == n) {
        if (!physicallyPlayable(cur)) return;
        FingerOption o;
        o.pos = cur;
        o.cost = detail::staticCost(cur, 6);
        double sum = 0; int nf = 0;
        for (const auto& c : cur) if (c.f > 0) { sum += c.f; ++nf; }
        o.hasFretted = nf > 0;
        o.meanFret = nf ? sum / nf : 0;
        all.push_back(std::move(o));
        return;
      }
      for (const auto& o : opts[i]) {
        if (used & (1u << o.s)) continue;
        int nmn = mn, nmx = mx;
        if (o.f > 0) { nmn = std::min(mn, o.f); nmx = std::max(mx, o.f); if (nmx - nmn > 6) continue; }
        cur.push_back(o);
        go(i + 1, used | (1u << o.s), nmn, nmx);
        cur.pop_back();
      }
    }
  } rec{opts, cur, all, n};
  rec.go(0, 0, 99, -1);
  std::sort(all.begin(), all.end(), [](const FingerOption& a, const FingerOption& b) { return a.cost < b.cost; });
  for (size_t i = 0; i < all.size() && (int)out.size() < K; ++i) out.push_back(all[i]);
}

// najlepsze palcowanie jednej grupy; prevFret < 0 = bez kontekstu
inline std::vector<FretPos> fingerGroup(const std::vector<int>& midis, const int open[6], double prevFret = -1, int maxFret = 22) {
  std::vector<FingerOption> o;
  handOptions(midis, open, maxFret, 8, o);
  if (o.empty()) fingerOptions(midis, open, maxFret, 8, o); // zestaw niemożliwy do zagrania: pokaż najlepsze przybliżenie
  if (o.empty()) return {};
  size_t best = 0;
  double bc = 1e18;
  for (size_t i = 0; i < o.size(); ++i) {
    double c = o[i].cost;
    if (prevFret >= 0 && o[i].hasFretted) c += std::fabs(o[i].meanFret - prevFret) * 0.4;
    if (c < bc) { bc = c; best = i; }
  }
  return o[best].pos;
}

// Viterbi po kolejnych grupach (offline); times = czasy początku grup [s]. Zwraca wybrane przypisanie dla każdej grupy.
// Koszt przejścia: odległość ręki; skok większy niż ręka zdąży przejść w danym czasie jest mocno karany.
inline std::vector<std::vector<FretPos>> fingerSequence(const std::vector<std::vector<int>>& groups, const std::vector<double>& times,
                                                        const int open[6], int maxFret = 22) {
  const size_t G = groups.size();
  std::vector<std::vector<FingerOption>> opt(G);
  for (size_t g = 0; g < G; ++g) {
    handOptions(groups[g], open, maxFret, 6, opt[g]);
    if (opt[g].empty()) fingerOptions(groups[g], open, maxFret, 6, opt[g]);
  }
  std::vector<std::vector<double>> best(G);
  std::vector<std::vector<int>> from(G);
  for (size_t g = 0; g < G; ++g) {
    best[g].assign(opt[g].size(), 0.0);
    from[g].assign(opt[g].size(), -1);
    for (size_t i = 0; i < opt[g].size(); ++i) {
      double bestPrev = 0;
      int bp = -1;
      if (g > 0 && !opt[g - 1].empty()) {
        bestPrev = 1e18;
        const double dt = (g < times.size() && g - 1 < times.size()) ? times[g] - times[g - 1] : 1.0;
        for (size_t j = 0; j < opt[g - 1].size(); ++j) {
          double move = 0;
          if (opt[g][i].hasFretted && opt[g - 1][j].hasFretted) {
            const double d = std::fabs(opt[g][i].meanFret - opt[g - 1][j].meanFret);
            move = d * 0.4 + (d > handReach(dt) ? 30.0 : 0.0);
          }
          const double c = best[g - 1][j] + move;
          if (c < bestPrev) { bestPrev = c; bp = (int)j; }
        }
      }
      best[g][i] = opt[g][i].cost + bestPrev;
      from[g][i] = bp;
    }
  }
  std::vector<std::vector<FretPos>> res(G);
  int cur = -1;
  for (size_t g = G; g-- > 0;) {
    if (opt[g].empty()) { cur = -1; continue; }
    if (cur < 0 || cur >= (int)opt[g].size()) {
      cur = 0;
      for (size_t i = 1; i < opt[g].size(); ++i) if (best[g][i] < best[g][cur]) cur = (int)i;
    }
    res[g] = opt[g][cur].pos;
    cur = from[g][cur];
  }
  return res;
}

} // namespace gt
