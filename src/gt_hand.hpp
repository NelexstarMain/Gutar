// gt_hand.hpp - śledzenie lewej ręki na gryfie.
// Ręka jest jedna, więc zestaw nut brzmiących naraz musi dać się zagrać jednym ułożeniem palców, a pozycja ręki
// nie może skakać szybciej, niż ręka potrafi. Nuty, które łamią te zasady, są prawie zawsze fałszywymi wykryciami
// (podwojenia oktawowe, alikwoty, ogony poprzedniej nuty), więc są odrzucane przed dalszą analizą.
#pragma once
#include <unordered_map>
#include "gt_fingering.hpp"
#include "gt_pitch.hpp"

namespace gt {

class HandTracker {
public:
  struct Zone {
    double pos = -1;     // środek ręki [próg]
    int lo = -1, hi = -1; // skrajne wciśnięte progi
  };

  void configure(const int open[6], bool enabled, bool motion) {
    bool changed = false;
    for (int i = 0; i < 6; ++i) if (open_[i] != open[i]) changed = true;
    for (int i = 0; i < 6; ++i) open_[i] = open[i];
    if (changed) cache_.clear();
    enabled_ = enabled;
    motion_ = motion;
  }

  void reset() {
    pos_ = -1; tMove_ = -1e9; tSeen_ = -1e9; rejected_ = 0; prevAcc_.clear();
  }

  long rejected() const { return rejected_; }
#ifdef GT_DEBUG
  std::vector<int> lastRej;
#endif
  Zone zone() const { Zone z; z.pos = pos_; z.lo = lo_; z.hi = hi_; return z; }

  // Zostawia w `dets` tylko nuty, które da się zagrać razem jedną ręką. Zwraca liczbę odrzuconych.
  // Pierwszeństwo: w stanie ustalonym (od ostatniego uderzenia minęło więcej niż okno analizy) nuty przyjęte w poprzedniej
  // ramce, bo trzymają rękę na miejscu i nowa nuta musi do nich pasować; potem siła wykrycia. Zaraz po uderzeniu pamięć
  // jest pomijana, bo stare nuty są już nieaktualne, a okno analizy jeszcze je zawiera.
  int filter(std::vector<NoteDet>& dets, double t, double sinceOnset, double winSec) {
    if (!enabled_) return 0;
    const bool sticky = sinceOnset > winSec && !prevAcc_.empty();
    std::vector<size_t> order(dets.size());
    for (size_t i = 0; i < order.size(); ++i) order[i] = i;
    auto est = [&](size_t i) { return sticky && std::binary_search(prevAcc_.begin(), prevAcc_.end(), dets[i].midi); };
    std::stable_sort(order.begin(), order.end(), [&](size_t a, size_t b) {
      const bool ea = est(a), eb = est(b);
      if (ea != eb) return ea;
      return dets[a].score > dets[b].score;
    });
    std::vector<int> acc;
    std::vector<char> keep(dets.size(), 0);
    int dropped = 0;
    for (size_t k : order) {
      std::vector<int> trial = acc;
      trial.insert(std::upper_bound(trial.begin(), trial.end(), dets[k].midi), dets[k].midi);
      const auto& opts = options(trial);
      bool ok = false;
      for (const auto& o : opts) if (reachable(o, t)) { ok = true; break; }
      if (ok) { acc = trial; keep[k] = 1; } else ++dropped;
    }
#ifdef GT_DEBUG
    lastRej.clear();
    for (size_t i = 0; i < dets.size(); ++i) if (!keep[i]) lastRej.push_back(dets[i].midi);
#endif
    prevAcc_ = acc;
    if (dropped) {
      std::vector<NoteDet> kept;
      for (size_t i = 0; i < dets.size(); ++i) if (keep[i]) kept.push_back(dets[i]);
      dets.swap(kept);
      rejected_ += dropped;
    }
    return dropped;
  }

  // Wybiera ułożenie dla stabilnych nut (najbliższe aktualnej pozycji ręki) i aktualizuje pozycję ręki.
  void observe(const std::vector<int>& midis, double t, std::vector<FretPos>& fg) {
    fg.clear();
    if (midis.empty()) return;
    std::vector<int> ms = midis;
    std::sort(ms.begin(), ms.end());
    ms.erase(std::unique(ms.begin(), ms.end()), ms.end());
    const auto& opts = options(ms);
    const FingerOption* best = nullptr;
    double bc = 1e18;
    const bool known = pos_ >= 0 && t - tSeen_ < 1.2;
    for (const auto& o : opts) {
      double c = o.cost;
      if (known && o.hasFretted) {
        const double d = std::fabs(o.meanFret - pos_);
        c += d * 0.4 + (motion_ && d > handReach(t - tMove_) ? 30.0 : 0.0);
      }
      if (c < bc) { bc = c; best = &o; }
    }
    if (!best) { // zestaw niemożliwy do zagrania (np. wszystko stabilne, ale rozbite na dwie ręce): bez ułożenia
      fg = fingerGroup(ms, open_, known ? pos_ : -1);
      return;
    }
    fg = best->pos;
    tSeen_ = t;
    if (best->hasFretted) {
      int lo = 99, hi = -1;
      for (const auto& p : best->pos) if (p.f > 0) { lo = std::min(lo, p.f); hi = std::max(hi, p.f); }
      if (!known || std::fabs(best->meanFret - pos_) > 1.5) tMove_ = t;
      pos_ = best->meanFret; lo_ = lo; hi_ = hi;
    }
  }

private:
  int open_[6] = {40, 45, 50, 55, 59, 64};
  bool enabled_ = true, motion_ = true;
  double pos_ = -1, tMove_ = -1e9, tSeen_ = -1e9;
  int lo_ = -1, hi_ = -1;
  long rejected_ = 0;
  std::vector<int> prevAcc_; // nuty przyjęte w poprzedniej ramce (posortowane)
  std::unordered_map<uint64_t, std::vector<FingerOption>> cache_;

  // fizycznie grywalne układy zestawu (posortowane rosnąco po koszcie), z pamięcią podręczną
  const std::vector<FingerOption>& options(const std::vector<int>& sorted) {
    uint64_t key = 0;
    bool inRange = true;
    for (int m : sorted) { if (m < 28 || m > 91) { inRange = false; break; } key |= 1ull << (m - 28); }
    static const std::vector<FingerOption> none;
    if (!inRange) return none;
    auto it = cache_.find(key);
    if (it != cache_.end()) return it->second;
    if (cache_.size() > 20000) cache_.clear();
    auto& v = cache_[key];
    handOptions(sorted, open_, 22, 8, v);
    return v;
  }

  bool reachable(const FingerOption& o, double t) const {
    if (!motion_ || !o.hasFretted || pos_ < 0 || t - tSeen_ > 1.2) return true;
    return std::fabs(o.meanFret - pos_) <= handReach(t - tMove_);
  }
};

} // namespace gt
