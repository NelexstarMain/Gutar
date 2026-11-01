// gt_tracker.hpp - zamienia wykrycia z pojedynczych ramek na zdarzenia nutowe (początek/koniec).
#pragma once
#include <map>
#include "gt_pitch.hpp"

namespace gt {

struct NoteEvent2 {
  int midi = 0;
  double t0 = 0, t1 = 0;
  int vel = 80;
};

class NoteTracker {
public:
  struct Active {
    double t0 = 0, last = 0, amp = 0, pre = -1;
    int miss = 0, vel = 80;
  };

  std::vector<NoteEvent2> events;
  std::map<int, Active> active;
  double lastOnset = -1;

  void reset() {
    events.clear(); active.clear(); cand_.clear(); recentEnd_.clear(); lastOnset = -1; reUntil_ = -1;
  }

  // t: czas ramki; winSec: długość okna analizy (do korekty końca nuty)
  void update(double t, const std::vector<NoteDet>& dets, bool silent, double onsetT, double hopSec, double winSec) {
    const double endLag = 0.5 * winSec;
    if (silent) {
      for (auto it = active.begin(); it != active.end();) { endNote(it->first, it->second.last - endLag); it = active.erase(it); }
      cand_.clear();
      lastOnset = -1; reUntil_ = -1;
      return;
    }
    if (onsetT >= 0) {
      lastOnset = onsetT;
      reUntil_ = t + 4.5 * hopSec;
      for (auto& kv : active) kv.second.pre = kv.second.amp;
      cand_.clear();
    }
    // zbiór wykrytych
    for (auto it = active.begin(); it != active.end();) {
      const int m = it->first;
      Active& a = it->second;
      const NoteDet* d = nullptr;
      for (const auto& n : dets) if (n.midi == m) { d = &n; break; }
      bool erase = false;
      if (d) {
        if (t <= reUntil_ && a.pre >= 0 && d->amp > 1.5 * a.pre && lastOnset >= 0 && a.t0 < lastOnset - 0.05) {
          endNote(m, lastOnset); // struna uderzona ponownie
          a = Active();
          a.t0 = lastOnset; a.last = t; a.amp = d->amp; a.vel = velocity(d->amp);
        } else {
          a.miss = 0; a.last = t; a.amp = std::max(a.amp * 0.9, (double)d->amp);
        }
      } else if (++a.miss * hopSec >= kReleaseSec) {
        endNote(m, a.last - endLag);
        erase = true;
      }
      if (erase) it = active.erase(it); else ++it;
    }
    for (const auto& n : dets) {
      if (active.count(n.midi)) continue;
      Cand& c = cand_[n.midi];
      if (c.n == 0) c.first = t;
      c.n++;
      c.amp = std::max(c.amp, (double)n.amp);
      if (c.n >= 2 && t - c.first >= kConfirmSec) {
        // ta sama nuta tuż po zakończeniu bez wyraźnego wzrostu siły to ogon poprzedniej, nie nowe uderzenie
        auto re = recentEnd_.find(n.midi);
        if (re != recentEnd_.end() && t - re->second.t < kRetriggerSec && c.amp < 1.3 * re->second.amp) continue;
        Active a;
        a.t0 = (lastOnset >= 0 && c.first - lastOnset < 0.5) ? lastOnset : c.first - winSec * 0.5;
        a.last = t; a.amp = c.amp; a.vel = velocity(c.amp);
        active[n.midi] = a;
        cand_.erase(n.midi);
      }
    }
    for (auto it = cand_.begin(); it != cand_.end();) {
      bool seen = false;
      for (const auto& n : dets) if (n.midi == it->first) { seen = true; break; }
      if (seen) ++it; else it = cand_.erase(it);
    }
  }

  // kończy wszystkie aktywne nuty w chwili t (koniec nagrania)
  void endAll(double t) {
    for (auto& kv : active) endNote(kv.first, std::max(kv.second.last, std::min(t, kv.second.last + 0.3)));
    active.clear(); cand_.clear();
  }

  // nuta musi być widoczna kilka ramek (odporność na krótkie zjawy na styku nut) i znikać na dłużej
  static constexpr double kConfirmSec = 0.085, kReleaseSec = 0.13, kMinNoteSec = 0.08, kRetriggerSec = 0.4;

  static int velocity(double a) {
    return (int)clampd(std::lround(64 + 28 * std::log10(std::max(a, 1e-4) / 0.02)), 20, 127);
  }

private:
  struct Cand { double first = 0, amp = 0; int n = 0; };
  struct Ended { double t = 0, amp = 0; };
  std::map<int, Cand> cand_;
  std::map<int, Ended> recentEnd_;
  double reUntil_ = -1;

  void endNote(int m, double tEnd) {
    auto it = active.find(m);
    if (it == active.end()) return;
    const Active& a = it->second;
    tEnd = std::max(tEnd, a.t0 + kMinNoteSec);
    recentEnd_[m] = {a.last, a.amp};
    if (tEnd - a.t0 >= kMinNoteSec && a.last - a.t0 >= kMinNoteSec * 0.8) {
      NoteEvent2 e;
      e.midi = m; e.t0 = a.t0; e.t1 = tEnd; e.vel = a.vel;
      events.push_back(e);
    }
  }
};

} // namespace gt
