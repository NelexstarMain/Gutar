// gt_engine.hpp - główny silnik: strumień audio -> ramki analizy, nuty, akordy, stroik.
#pragma once
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include "gt_chords.hpp"
#include "gt_tracker.hpp"

namespace gt {

// Stroje gitary (struny od najniższej): MIDI pustych strun
struct TuningPreset { const char* name; int open[6]; };
static const TuningPreset kTunings[] = {
    {"Standard (E A D G B e)", {40, 45, 50, 55, 59, 64}},
    {"Drop D", {38, 45, 50, 55, 59, 64}},
    {"Pół tonu niżej (Eb)", {39, 44, 49, 54, 58, 63}},
    {"Cały ton niżej (D)", {38, 43, 48, 53, 57, 62}},
    {"DADGAD", {38, 45, 50, 55, 57, 62}},
    {"Open G (DGDGBD)", {38, 43, 50, 55, 59, 62}},
    {"Open D (DADF#AD)", {38, 45, 50, 54, 57, 62}},
    {"Drop C", {36, 43, 48, 53, 57, 62}},
};
static const int kNumTunings = sizeof(kTunings) / sizeof(kTunings[0]);

struct EngineConfig {
  double a4 = 440;
  int win = 4096;          // okno analizy w próbkach po decymacji (2048/4096/8192)
  double gateDb = -62;     // próg ciszy [dB, moc względem pełnej skali]
  int mains = 50;          // brum sieci: 50 / 60 / 0
  bool autoTune = true;    // automatyczna korekta stroju odniesienia
  bool autoGate = true;    // automatyczne podniesienie progu przy szumie
  bool octaves = true;     // wykrywanie oktawowych podwojeń
  double octRatio = 2.0;
  int tuning = 0;          // indeks w kTunings
  int recordMaxSec = 1200; // limit nagrania w pamięci
  ChordParams chord;
};

struct FrameNote { int16_t midi = 0; float f = 0, cents = 0, amp = 0; bool stable = false; };

struct FrameRec {
  float t = 0, levelDb = -120;
  bool silent = true, onset = false;
  int16_t chord = -1;          // indeks w tabeli nazw akordów
  float chordScore = 0;
  int16_t alt[2] = {-1, -1};
  uint8_t nNotes = 0, nPeaks = 0;
  FrameNote notes[8];
  bool tunerOk = false;
  int16_t tMidi = 0;
  float tF = 0, tCents = 0, tCentsSm = 0, tProb = 0;
  float pk[24][2];
};

class Engine {
public:
  static constexpr int kHop = 512;

  // ---------------------------------------------------------------- konfiguracja
  void configure(const EngineConfig& c) {
    const bool rebuild = (c.win != cfg_.win) || !ready_;
    cfg_ = c;
    if (!ready_) return;
    if (rebuild) setupWindow();
    mp_.setRange(kTunings[cfg_.tuning].open[0], kTunings[cfg_.tuning].open[5] + 24);
    setReference(cfg_.a4 * std::pow(2.0, tuneCents_ / 1200.0));
  }
  const EngineConfig& config() const { return cfg_; }

  // sampleRate: częstotliwość próbkowania wejścia
  void begin(int sampleRate) {
    fs_ = sampleRate;
    D_ = std::max(1, (int)std::lround(fs_ / 11025.0));
    fsd_ = (double)fs_ / D_;
    dec_.init(D_);
    ring_.init(1 << 16);
    onset_.init(fsd_);
    ready_ = true;
    setupWindow();
    resetState();
    configure(cfg_);
  }

  void resetState() {
    ring_.init(1 << 16);
    onset_.init(fsd_);
    dec_.init(D_);
    tracker_.reset();
    frames_.clear(); chordNames_.clear(); chordLog_.clear(); onsets_.clear();
    recording_.clear();
    nd_ = 0; sinceFrame_ = 0; pendingOnset_ = -1; lastOnset_ = -1;
    prevStable_.clear();
    resetChordState();
    tuneCents_ = 0; tuneHist_.assign(100, 0.0); tuneWeight_ = 0;
    lvHist_.clear(); gateEff_ = cfg_.gateDb;
    tunerHist_.clear(); tunerMidi_ = -1;
    finished_ = false;
    prepassed_ = false;
    prevSilent_ = true;
    if (ready_) setReference(cfg_.a4);
  }

  // ---------------------------------------------------------------- strumień audio
  void push(const float* x, int n) {
    if (finished_) return;
    if (recordCap_ > 0 && (int64_t)recording_.size() < recordCap_) {
      const size_t room = (size_t)(recordCap_ - (int64_t)recording_.size());
      const size_t m = std::min<size_t>(room, (size_t)n);
      for (size_t i = 0; i < m; ++i) {
        const float v = x[i] > 1.f ? 1.f : (x[i] < -1.f ? -1.f : x[i]);
        recording_.push_back((int16_t)std::lrintf(v * 32767.f));
      }
    }
    decOut_.clear();
    dec_.process(x, n, decOut_);
    feed(decOut_.data(), (int)decOut_.size());
  }

  void finish() {
    if (finished_) return;
    tracker_.endAll(nd_ / fsd_);
    finished_ = true;
  }

  // Przed-przebieg po całym nagraniu: szacuje strój odniesienia i próg szumu.
  void prepass(const float* x, size_t n) {
    Decimator dec;
    dec.init(D_);
    std::vector<float> d;
    d.reserve(n / D_ + 64);
    const size_t CH = 1 << 16;
    for (size_t i = 0; i < n; i += CH) dec.process(x + i, (int)std::min(CH, n - i), d);
    std::vector<double> hist(100, 0.0);
    double weight = 0;
    std::vector<double> levels;
    std::vector<Peak> pk;
    PeakOptions po;
    po.mains = cfg_.mains;
    const int step = kHop * 3;
    for (size_t p = (size_t)win_; p + 1 <= d.size(); p += step) {
      double e = 0;
      for (size_t i = p - kHop; i < p; ++i) e += (double)d[i] * d[i];
      const double lv = 10 * std::log10(e / kHop + 1e-12);
      levels.push_back(lv);
      if (lv < cfg_.gateDb) continue;
      spec_.compute(d.data() + p - win_);
      po.minAmp = std::pow(10.0, cfg_.gateDb / 20) * 0.35;
      spec_.pickPeaks(po, pk);
      addTuningVotes(pk, hist, weight, 1.0);
    }
    if (cfg_.autoGate && levels.size() > 8) {
      std::sort(levels.begin(), levels.end());
      gateEff_ = std::max(cfg_.gateDb, std::min(-40.0, levels[levels.size() / 20] + 10));
    }
    if (cfg_.autoTune) {
      double est;
      if (tuneEstimate(hist, weight, est)) tuneCents_ = est;
      setReference(cfg_.a4 * std::pow(2.0, tuneCents_ / 1200.0));
    }
    prepassed_ = true;
    resetStreamKeepTuning();
  }

  // ---------------------------------------------------------------- odczyt
  double time() const { return nd_ / fsd_; }
  double winSec() const { return win_ / fsd_; }
  double hopSec() const { return kHop / fsd_; }
  double fsDecimated() const { return fsd_; }
  int sampleRate() const { return fs_; }
  double tuneCents() const { return tuneCents_; }
  double gate() const { return gateEff_; }
  const std::vector<FrameRec>& frames() const { return frames_; }
  const std::vector<std::string>& chordNames() const { return chordNames_; }
  const std::vector<ChordLogEntry>& chordLog() const { return chordLog_; }
  const std::vector<double>& onsets() const { return onsets_; }
  const NoteTracker& tracker() const { return tracker_; }
  const std::vector<int16_t>& recording() const { return recording_; }
  void setRecordLimit(int64_t samples) { recordCap_ = samples; }
  void clearHistory() {
    tracker_.events.clear(); chordLog_.clear(); onsets_.clear();
  }
  bool finished() const { return finished_; }

  const std::vector<NoteEvent2>& events() const { return tracker_.events; }
  std::vector<NoteEvent2> allEvents() const {
    std::vector<NoteEvent2> ev = tracker_.events;
    const double t = nd_ / fsd_;
    for (const auto& kv : tracker_.active) {
      NoteEvent2 e;
      e.midi = kv.first; e.t0 = kv.second.t0; e.t1 = std::max(t, kv.second.t0 + 0.05); e.vel = kv.second.vel;
      ev.push_back(e);
    }
    std::sort(ev.begin(), ev.end(), [](const NoteEvent2& a, const NoteEvent2& b) { return a.t0 < b.t0; });
    return ev;
  }

private:
  EngineConfig cfg_;
  bool ready_ = false, finished_ = false;
  int fs_ = 44100, D_ = 4, win_ = 4096;
  double fsd_ = 11025;
  Decimator dec_;
  Ring ring_;
  OnsetDetector onset_;
  Spectrum spec_;
  MultiPitch mp_;
  NoteTracker tracker_;
  std::vector<float> decOut_, xbuf_;
  std::vector<double> onsetTmp_, onsets_;
  std::vector<Peak> peaks_;
  std::vector<NoteDet> dets_;
  std::vector<FrameRec> frames_;
  std::vector<std::string> chordNames_;
  std::vector<ChordLogEntry> chordLog_;
  std::vector<int16_t> recording_;
  int64_t recordCap_ = 0;
  int64_t nd_ = 0;
  int sinceFrame_ = 0;
  double pendingOnset_ = -1, lastOnset_ = -1;
  std::vector<int> prevStable_;

  // strój i próg
  double tuneCents_ = 0;
  bool prepassed_ = false;
  std::vector<double> tuneHist_;
  double tuneWeight_ = 0;
  std::vector<double> lvHist_;
  double gateEff_ = -62;

  // stan akordu
  double segEv_[12], segBass_[12], harmEv_[12], harmBass_[12], oldEv_[12];
  bool haveOld_ = false, changed_ = false;
  double segStart_ = 0;
  int segLogged_ = -1;
  bool afterSilence_ = true;
  std::string curChord_, candChord_;
  int candCount_ = 0;
  ChordResult curRes_;

  // stroik
  std::vector<float> tunerHist_;
  int tunerMidi_ = -1;

  void resetStreamKeepTuning() {
    const double tc = tuneCents_;
    const bool lock = prepassed_;
    const double g = gateEff_;
    resetState();
    tuneCents_ = tc; prepassed_ = lock; gateEff_ = g;
    setReference(cfg_.a4 * std::pow(2.0, tuneCents_ / 1200.0));
  }

  void setupWindow() {
    win_ = cfg_.win;
    spec_.init(win_, fsd_, win_ <= 4096 ? 4 : 2);
    xbuf_.assign(win_, 0.f);
    MultiPitch::Options o;
    o.fs = fsd_;
    o.octaves = cfg_.octaves;
    o.octRatio = cfg_.octRatio;
    mp_.init(o, cfg_.a4);
  }

  void setReference(double a4) {
    if (std::fabs(a4 - mp_.a4()) > 1e-6) mp_.setA4(a4);
  }

  void resetChordState() {
    std::memset(segEv_, 0, sizeof segEv_); std::memset(segBass_, 0, sizeof segBass_);
    std::memset(harmEv_, 0, sizeof harmEv_); std::memset(harmBass_, 0, sizeof harmBass_);
    std::memset(oldEv_, 0, sizeof oldEv_);
    haveOld_ = false; changed_ = false;
    segStart_ = 0; segLogged_ = -1; afterSilence_ = true;
    curChord_.clear(); candChord_.clear(); candCount_ = 0; curRes_ = ChordResult();
  }

  // --------------------------------------------------------- strój odniesienia
  void addTuningVotes(const std::vector<Peak>& pk, std::vector<double>& hist, double& weight, double mult) const {
    const double bh = spec_.binHz();
    const auto& nf = spec_.noiseFloor();
    for (const auto& p : pk) {
      if (p.f < 80 || p.f > 1500) continue;
      const int k = (int)(p.f / bh);
      if (k < 0 || k >= (int)nf.size()) continue;
      const double snr = p.a / (nf[k] + 1e-12);
      if (snr < 8) continue;
      const double w = std::min(3.0, std::log10(snr)) * mult;
      const double x = 12 * std::log2(p.f / cfg_.a4);
      const double cents = (x - std::round(x)) * 100.0; // [-50, 50]
      int b = (int)std::floor(cents + 50.0);
      for (int d = -3; d <= 3; ++d) {
        const int bb = ((b + d) % 100 + 100) % 100;
        hist[bb] += w * (1.0 - std::fabs(d) / 4.0);
      }
      weight += w;
    }
  }

  static bool tuneEstimate(const std::vector<double>& hist, double weight, double& est) {
    if (weight < 12) return false;
    int bi = 0;
    double bv = -1, mean = 0;
    for (int i = 0; i < 100; ++i) { mean += hist[i]; if (hist[i] > bv) { bv = hist[i]; bi = i; } }
    mean /= 100;
    if (mean <= 0 || bv < 1.6 * mean) return false;
    // średnia ważona wokół maksimum (podbinowa)
    double num = 0, den = 0;
    for (int d = -4; d <= 4; ++d) {
      const int bb = ((bi + d) % 100 + 100) % 100;
      num += d * hist[bb]; den += hist[bb];
    }
    est = (bi - 50 + 0.5) + (den > 0 ? num / den : 0.0);
    if (est > 50) est -= 100;
    if (est < -50) est += 100;
    return true;
  }

  // --------------------------------------------------------- przetwarzanie
  void feed(const float* d, int n) {
    int i = 0;
    while (i < n) {
      const int seg = std::min(n - i, kHop - sinceFrame_);
      ring_.push(d + i, seg);
      onsetTmp_.clear();
      onset_.push(d + i, seg, onsetTmp_);
      for (double t : onsetTmp_) {
        onsets_.push_back(t);
        if (pendingOnset_ < 0) pendingOnset_ = t;
      }
      nd_ += seg; sinceFrame_ += seg; i += seg;
      if (sinceFrame_ == kHop) {
        sinceFrame_ = 0;
        if (nd_ >= win_) frame();
      }
    }
  }

  int chordId(const std::string& name) {
    for (size_t i = 0; i < chordNames_.size(); ++i) if (chordNames_[i] == name) return (int)i;
    chordNames_.push_back(name);
    return (int)chordNames_.size() - 1;
  }

  void frame() {
    FrameRec fr;
    const double t = nd_ / fsd_, hopSec = kHop / fsd_, wSec = win_ / fsd_;
    fr.t = (float)t;
    ring_.last(win_, xbuf_.data());
    double e = 0;
    for (int i = win_ - kHop; i < win_; ++i) e += (double)xbuf_[i] * xbuf_[i];
    const double levelDb = 10 * std::log10(e / kHop + 1e-12);
    fr.levelDb = (float)levelDb;
    // adaptacyjny próg ciszy (statystyka minimów)
    lvHist_.push_back(levelDb);
    if (lvHist_.size() > 400) lvHist_.erase(lvHist_.begin());
    if (cfg_.autoGate && !prepassed_ && lvHist_.size() >= 60 && (nd_ / kHop) % 20 == 0) {
      std::vector<double> s = lvHist_;
      std::nth_element(s.begin(), s.begin() + s.size() / 20, s.end());
      gateEff_ = std::max(cfg_.gateDb, std::min(-40.0, s[s.size() / 20] + 10));
    } else if (!cfg_.autoGate) gateEff_ = cfg_.gateDb;
    const bool silent = levelDb < gateEff_;
    fr.silent = silent;
    dets_.clear(); peaks_.clear();
    if (!silent) {
      spec_.compute(xbuf_.data());
      PeakOptions po;
      po.mains = cfg_.mains;
      po.minAmp = std::pow(10.0, gateEff_ / 20) * 0.35;
      spec_.pickPeaks(po, peaks_);
      if (cfg_.autoTune && !prepassed_) liveTuning();
      mp_.detect(peaks_, dets_);
    }
    const double onsetT = pendingOnset_;
    pendingOnset_ = -1;
    fr.onset = onsetT >= 0;
    if (onsetT >= 0) lastOnset_ = onsetT;
    tracker_.update(t, dets_, silent, onsetT, hopSec, wSec);

    // stabilne = wykryte teraz i w poprzedniej ramce (albo aktywne w trackerze)
    std::vector<int> cur;
    for (const auto& n : dets_) cur.push_back(n.midi);
    std::vector<const NoteDet*> stable;
    for (const auto& n : dets_) {
      const bool prev = std::find(prevStable_.begin(), prevStable_.end(), n.midi) != prevStable_.end();
      if (prev || tracker_.active.count(n.midi)) stable.push_back(&n);
    }
    if (stable.empty() && prevSilent_) for (const auto& n : dets_) stable.push_back(&n);
    prevStable_ = cur;
    prevSilent_ = silent;

    updateChord(fr, t, hopSec, wSec, onsetT, silent, stable);
    updateTuner(fr, t, silent);

    fr.nNotes = (uint8_t)std::min<size_t>(8, dets_.size());
    for (int i = 0; i < fr.nNotes; ++i) {
      FrameNote& fn = fr.notes[i];
      fn.midi = (int16_t)dets_[i].midi; fn.f = dets_[i].f; fn.cents = dets_[i].cents; fn.amp = dets_[i].amp;
      for (const auto* s : stable) if (s->midi == dets_[i].midi) fn.stable = true;
    }
    // 24 najsilniejsze piki
    std::vector<Peak> top = peaks_;
    std::sort(top.begin(), top.end(), [](const Peak& a, const Peak& b) { return a.a > b.a; });
    fr.nPeaks = (uint8_t)std::min<size_t>(24, top.size());
    for (int i = 0; i < fr.nPeaks; ++i) { fr.pk[i][0] = top[i].f; fr.pk[i][1] = top[i].a; }
    frames_.push_back(fr);
  }
  bool prevSilent_ = true;

  void liveTuning() {
    addTuningVotes(peaks_, tuneHist_, tuneWeight_, 1.0);
    // powolne zapominanie
    const double decay = std::exp(-(double)kHop / fsd_ / 12.0);
    for (auto& v : tuneHist_) v *= decay;
    tuneWeight_ *= decay;
    if ((nd_ / kHop) % 10 == 0) {
      double est;
      if (tuneEstimate(tuneHist_, tuneWeight_, est) && std::fabs(est - tuneCents_) > 2.5) {
        tuneCents_ = tuneCents_ * 0.6 + est * 0.4;
        setReference(cfg_.a4 * std::pow(2.0, tuneCents_ / 1200.0));
      }
    }
  }

  void updateChord(FrameRec& fr, double t, double hopSec, double wSec, double onsetT, bool silent,
                   const std::vector<const NoteDet*>& stable) {
    if (silent) {
      resetChordState();
      afterSilence_ = true;
      lastOnset_ = -1;
      return;
    }
    if (onsetT >= 0) { // nowy segment (uderzenie): zapamiętaj dotychczasową harmonię
      std::memcpy(oldEv_, harmEv_, sizeof oldEv_);
      double s0 = 0;
      for (int p = 0; p < 12; ++p) s0 += harmEv_[p];
      haveOld_ = s0 > 1e-9;
      std::memset(segEv_, 0, sizeof segEv_); std::memset(segBass_, 0, sizeof segBass_);
      changed_ = false;
      segStart_ = onsetT; segLogged_ = -1;
    }
    const double settle = lastOnset_ < 0 ? 1.0 : clampd((t - lastOnset_ - 0.05) / (wSec - 0.05), 0, 1);
    const double ws = std::pow(settle, 1.5);
    const double lam = std::exp(-hopSec / 2.5);
    if (!changed_) for (int p = 0; p < 12; ++p) { harmEv_[p] *= lam; harmBass_[p] *= lam; }
    double sMax = 0, aMax = 0;
    for (const auto* n : stable) { sMax = std::max<double>(sMax, n->score); aMax = std::max<double>(aMax, n->amp); }
    int bass = 1000;
    for (const auto* n : stable) {
      const double a = std::sqrt(std::max<double>(n->amp, 1e-6));
      const int pc = n->midi % 12;
      segEv_[pc] += ws * a;
      if (!changed_) harmEv_[pc] += a;
      if ((n->score >= 0.2 * sMax || n->amp >= 0.2 * aMax) && n->midi < bass) bass = n->midi;
    }
    if (bass < 1000) { segBass_[bass % 12] += ws; if (!changed_) harmBass_[bass % 12] += 1; }
    // zmiana harmonii: po ustabilizowaniu uderzenia zniknęła jakaś klasa dźwięku z poprzedniego akordu
    // (w arpeggio dawne dźwięki nadal brzmią, więc nic nie znika i dowody się sumują)
    if (!changed_ && haveOld_ && settle > 0.35) {
      double ts = 0, to = 0;
      for (int p = 0; p < 12; ++p) { ts += segEv_[p]; to += oldEv_[p]; }
      if (ts > 0 && to > 0)
        for (int p = 0; p < 12; ++p)
          if (oldEv_[p] / to >= 0.10 && segEv_[p] / ts < 0.10) { changed_ = true; break; }
    }
    if (changed_) { std::memcpy(harmEv_, segEv_, sizeof harmEv_); std::memcpy(harmBass_, segBass_, sizeof harmBass_); }
    double tot = 0;
    for (int p = 0; p < 12; ++p) tot += harmEv_[p];
    ChordResult res;
    if (tot > 1e-9) {
      double w[12];
      for (int p = 0; p < 12; ++p) w[p] = harmEv_[p] / tot;
      int bpc = -1;
      double bb = 0;
      for (int p = 0; p < 12; ++p) if (harmBass_[p] > bb) { bb = harmBass_[p]; bpc = p; }
      res = recognizeChord(w, bpc, cfg_.chord);
    }
#ifdef GT_DEBUG
    if (std::getenv("GT_TRACE")) {
      fprintf(stderr, "t=%.2f onset=%.2f settle=%.2f changed=%d tot=%.3f res=%s sc=%.2f stable=", t, lastOnset_, settle, (int)changed_, tot, res.ok ? res.name.c_str() : "-", res.score);
      for (const auto* n : stable) fprintf(stderr, "%d ", n->midi);
      fprintf(stderr, " w=");
      for (int p = 0; p < 12; ++p) if (tot > 0 && harmEv_[p] / tot > 0.02) fprintf(stderr, "%s:%.2f ", kNoteNames[p], harmEv_[p] / tot);
      fprintf(stderr, "\n");
    }
#endif
    // histereza: zmiana etykiety po 2 kolejnych ramkach
    const std::string nm = res.ok ? res.name : std::string();
    if (nm == curChord_) { candChord_.clear(); candCount_ = 0; if (res.ok) curRes_ = res; }
    else {
      if (nm == candChord_) ++candCount_; else { candChord_ = nm; candCount_ = 1; }
      if (candCount_ >= 2 || curChord_.empty()) { curChord_ = nm; curRes_ = res; candChord_.clear(); candCount_ = 0; }
    }
    if (!curChord_.empty()) {
      fr.chord = (int16_t)chordId(curChord_);
      fr.chordScore = curRes_.score;
      for (int k = 0; k < curRes_.nAlt; ++k) fr.alt[k] = (int16_t)chordId(curRes_.alt[k]);
    }
    // historia akordów: wpis po ustabilizowaniu uderzenia
    const bool settled = (t - segStart_) >= 0.40;
    if (settled && !curChord_.empty()) logChord(curChord_);
  }

  void logChord(const std::string& name) {
    if (segLogged_ == -1) {
      if (chordLog_.empty() || chordLog_.back().name != name || afterSilence_) {
        chordLog_.push_back({segStart_, name});
        segLogged_ = (int)chordLog_.size() - 1;
      } else segLogged_ = -2; // taki sam jak poprzedni: nie dubluj
      afterSilence_ = false;
    } else if (segLogged_ >= 0) {
      if (chordLog_[segLogged_].name != name) {
        chordLog_[segLogged_].name = name;
        if (segLogged_ > 0 && chordLog_[segLogged_ - 1].name == name) { chordLog_.pop_back(); segLogged_ = -2; }
      }
    } else if (segLogged_ == -2 && !chordLog_.empty() && chordLog_.back().name != name) {
      chordLog_.push_back({segStart_, name});
      segLogged_ = (int)chordLog_.size() - 1;
    }
  }

  void updateTuner(FrameRec& fr, double t, bool silent) {
    (void)t;
    const NoteDet* single = nullptr;
    int nBase = 0;
    for (const auto& d : dets_) if (!d.octave) { ++nBase; single = &d; }
    if (silent || nBase != 1) { tunerHist_.clear(); tunerMidi_ = -1; return; }
    const NoteDet& p = *single;
    double f = p.f;
    const double ref = cfg_.a4;
    double prob = 0.5;
    const YinResult y = yin(xbuf_.data() + (win_ - 2048), 2048, fsd_);
    if (y.prob > 0.9 && y.f > 0) {
      const int m = (int)std::lround(freqMidi(y.f, mp_.a4()));
      if (m == p.midi) { prob = y.prob; }
    }
    // odchyłka względem wzorcowego A4 użytkownika
    const double cents = 1200 * std::log2(f / midiFreq(p.midi, ref));
    if (tunerMidi_ != p.midi) { tunerHist_.clear(); tunerMidi_ = p.midi; }
    tunerHist_.push_back((float)cents);
    if (tunerHist_.size() > 5) tunerHist_.erase(tunerHist_.begin());
    std::vector<float> s = tunerHist_;
    std::sort(s.begin(), s.end());
    fr.tunerOk = true; fr.tMidi = (int16_t)p.midi; fr.tF = (float)f; fr.tCents = (float)cents;
    fr.tCentsSm = s[s.size() / 2]; fr.tProb = (float)prob;
  }
};

} // namespace gt
