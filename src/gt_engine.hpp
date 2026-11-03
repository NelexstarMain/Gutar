// gt_engine.hpp - główny silnik: strumień audio -> ramki analizy, nuty, akordy, stroik.
#pragma once
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include "gt_chords.hpp"
#include "gt_hand.hpp"
#include "gt_tracker.hpp"
#include "gt_mask.hpp"
#include "gt_gen5.hpp"

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
  int win = 4096;          // okno analizy w próbkach po decymacji (2048/4096/8192); 2048: lepsze nuty w szybkiej grze, gorsze akordy
  double gateDb = -62;     // próg ciszy [dB, moc względem pełnej skali]
  int mains = 50;          // brum sieci: 50 / 60 / 0
  bool autoTune = true;    // automatyczna korekta stroju odniesienia
  bool autoGate = true;    // automatyczne podniesienie progu przy szumie
  bool octaves = true;     // wykrywanie oktawowych podwojeń
  bool sustain = true;     // podtrzymanie: obniżony próg dla nut, które już brzmią
  double susK = 2.0;       // próg szumu dla nuty podtrzymanej tuż po mocnym wykryciu (zwykły: 4,5)
  double susEvidence = 2.5; // ile punktów dowodu potrzeba (alikwot niezależny = 1, wspólny z niższą nutą = 0,5)
  bool refine = true;
  // docinanie granic nut krótkim oknem po analizie pliku (refine)
  // odszumianie z wielu klatek (analiza pliku): widmo szumu tła = kwantyl amplitudy w każdym binie przez wszystkie klatki nagrania.
  // Na żywo wyłączone: statystyka minimów (Martin 2001) i szum z klatek ciszy wycinały brzmiące struny (README).
  bool gen5 = true;         // model gen 5 (gt_gen5.hpp) przy analizie pliku: zastępuje listę nut
  double g5On = 0.5, g5Fr = 0.5, g5Start = 0.7;
  bool model = true;        // wytrenowany model wybiera nuty spośród kandydatów (gt_model.hpp), przy analizie pliku
  bool modelLive = false;   // ... także na żywo (w pomiarze akordy na żywo gorsze: 95,4 -> 88,9 %)
  double modelThr = -1;    // próg prawdopodobieństwa (-1 = dobrany przy uczeniu, kModelThr)
  bool mask = true;         // model maski (gt_mask.hpp), przy analizie pliku
  bool maskClean = true;    // odrzucaj piki w pasmach, gdzie maska < maskThr
  double maskThr = 0.3;
  bool denoise = true;
  double noiseQ = 0.15;     // kwantyl amplitudy w binie przez wszystkie klatki nagrania = szum tła
  double noiseTK = 3.0;     // pik musi być tyle razy (~9,5 dB) ponad szumem tła
  double prior = 1.0;       // premia w detektorze dla wysokości słyszanych niedawno (1 = wyłączona)
  double priorSec = 3.0;    // jak daleko wstecz [s]
  // kontekst czasowy (analiza pliku): poprzednie i następne chwile pomagają poprawić bieżącą
  bool context = false;    // w pomiarze bez zysku (README), dostępne do eksperymentów
  bool ctxFill = true;     // dopowiadanie nut z sąsiednich uderzeń, gdy w ich alikwotach widać atak
  double ctxSpan = 4.0;    // jak daleko [s] w przód i w tył szukać kandydatów
  double ctxAt = 0.30;     // środek okna sprawdzającego dopowiadaną nutę [s po uderzeniu]
  double ctxK = 4.5;       // próg szumu dla alikwotów dopowiadanej nuty (zwykły próg pików: 4,5)
  double ctxEvidence = 4;  // ile punktów dowodu (alikwot niezależny = 1, wspólny z niższą nutą = 0,5)
  double ctxRise = 6.0;    // minimalny atak [dB / 35 ms] we własnych alikwotach kandydata
  double ctxDrop = 18.0;   // poziom po ataku najwyżej tyle dB poniżej poziomu tej nuty w sąsiednim uderzeniu
  bool ctxMerge = true;    // sklejanie przerwanej nuty (ta sama wysokość, krótka przerwa, bez nowego ataku)
  double ctxGap = 0.25;    // najdłuższa przerwa do sklejenia [s]
  bool ctxPrune = true;    // usuwanie krótkich nut bez ataku we własnych alikwotach
  double ctxShort = 0.15;  // "krótka" nuta [s]
  bool resplit = true;     // dzielenie nuty na ponowne szarpnięcia tej samej struny
  bool segShared = true;   // funkcja początku tylko z alikwotów niewspólnych z innymi nutami
  double splitDb = 8;      // skok energii [dB], od którego brzmiąca nuta jest uznana za ponownie szarpniętą
  double segRise = 6;      // minimalne narastanie [dB / 35 ms] przy szukaniu początku
  double segBack = 0.30;   // jak daleko przed dotychczasowym początkiem szukać [s]
  double segMove = 0.0;    // przesuwaj początek tylko o więcej niż tyle [s]
  double segOffset = 0.03; // poprawka czasu (środek okna -> rzeczywisty początek) [s]
  double endLag = 0.25;    // część okna analizy odejmowana od końca nuty (0,5 = dokładnie dla nut urwanych, 0 = dla zanikających)
  double release = 0.13;   // tolerancja na chwilowy zanik nuty [s] (0,22 sprawdzone: wynik mieszany, README)
  double susHold = 4.0;    // jak długo [s] próg pozostaje niski; potem rośnie do zwykłego w ciągu kolejnych 10 s
  bool freshFull = true;   // nowe nuty liczą się do akordu od pierwszej ramki po uderzeniu
  bool chordsFromNotes = true; // analiza pliku: akordy składane z gotowej listy nut (nuty są podstawą, akord to ich nazwa)
  bool liveNotes = false;  // na żywo: akord tylko z nut potwierdzonych przez tracker
  double chGroup = 0.08;   // początki nut bliżej niż tyle [s] od poprzedniego to jedno uderzenie
  double chCarryTau = 1.2; // waga nut brzmiących z wcześniejszych uderzeń maleje z tą stałą czasu [s]
  double chLate = 0.6;     // spóźnione nuty do tylu [s] po pełnym uderzeniu dopełniają jego akord (0 = wyłączone)
  int chKeepMax = 3;       // uderzenie z mniej niż tyloma nowymi klasami dźwięków, wszystkimi w bieżącym akordzie, nie zmienia akordu
  double chConfPow = 2.0;  // waga nuty w akordzie ~ pewność^chConfPow
  double chFrameW = 0.6;   // waga dowodu z pojedynczych ramek (wysokości niepotwierdzone jako nuty), względem najsilniejszej nuty
  double chShort = 0.8;    // nuty krótsze niż tyle [s] ważą proporcjonalnie mniej
  double chBassRel = 0.3;  // bas = najniższa nuta o wadze >= tej części najsilniejszej
  int chFreshMin = 2;      // od tylu różnych klas dźwięków w samym uderzeniu akord bierze tylko nowe nuty
  bool hand = true;        // śledzenie ręki: odrzucaj nuty niemożliwe do zagrania razem
  bool handMotion = true;  // ... także skoki ręki szybsze, niż ręka zdąży
  double octRatio = 1.4;     // próg nadwyżki parzystych alikwotów dla podwojenia oktawowego w akordzie
  double octRatioMono = 2.2; // ... przy pojedynczej nucie
  bool learnB = true;        // nieharmoniczność mierzona dla każdej wysokości (węższe dopasowanie alikwotów)
  double learnTol0 = 25, learnTol1 = 1.2;
  bool octModel = true;      // test podwojeń oktawowych z modelem miejsca szarpnięcia (Traube i Smith)
  double octModelThr = 1.4, octModelThrMono = 2.5;
  bool joint = true;         // ocena łączna zbioru nut (poduktawy, nuty wyjaśnione przez inne)
  double jointSwap = 0.0, jointDrop = 0.12; // zamiana poduktawy wyłączona: w pomiarze gubiła prawdziwy bas
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
  uint8_t nFg = 0;
  struct { int16_t midi; int8_t s, f; } fg[6];
  int8_t handLo = -1, handHi = -1;
  uint8_t handRejected = 0;  // ile nut odrzucono w tej ramce jako niemożliwe do zagrania
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
    tracker_.releaseSec = c.release; tracker_.endLagFrac = c.endLag;
    if (!ready_) return;
    if (rebuild) setupWindow();
    mp_.setJoint(cfg_.joint, cfg_.jointSwap, cfg_.jointDrop);
    mp_.setOctModel(cfg_.octModel, cfg_.octModelThr, cfg_.octModelThrMono);
    applyModelCfg();
    mp_.setLearnB(cfg_.learnB, cfg_.learnTol0, cfg_.learnTol1);
    mp_.setRange(kTunings[cfg_.tuning].open[0], kTunings[cfg_.tuning].open[5] + 24);
    hand_.configure(kTunings[cfg_.tuning].open, cfg_.hand, cfg_.handMotion);
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
    hand_.reset();
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
    keepDecimated_ = false;
    std::vector<float>().swap(dfull_);
    prevSilent_ = true;
    noiseAmp_.clear(); noiseFixed_ = false; bm_.reset();
    applyModelCfg();
    if (ready_) { mp_.resetLearned(); setReference(cfg_.a4); }
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
    const bool g5 = keepDecimated_ && !dfull_.empty() && cfg_.gen5 && kGen5Ready;
    if (keepDecimated_ && !dfull_.empty() && (dumpH_ || g5)) {
      Hcqt h; h.compute(dfull_, fsd_);
      if (dumpH_) {
        const int32_t hdr[3] = {h.T, Hcqt::C, Hcqt::P};
        fwrite(hdr, sizeof(int32_t), 3, dumpH_);
        fwrite(h.v.data(), sizeof(float), h.v.size(), dumpH_);
      }
      if (g5) applyGen5(h);
    }
    if (keepDecimated_ && cfg_.refine && !dfull_.empty()) refineEvents();
    if (keepDecimated_ && cfg_.context && !dfull_.empty()) contextRepair();
    if (keepDecimated_ && cfg_.chordsFromNotes) chordsFromNotes();
    std::vector<float>().swap(dfull_);
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
    const int K = spec_.bins(), NB = 180;
    std::vector<uint16_t> nh;
    int nFr = 0;
    if (cfg_.denoise) nh.assign((size_t)K * NB, 0);
    for (size_t p = (size_t)win_; p + 1 <= d.size(); p += step) {
      double e = 0;
      for (size_t i = p - kHop; i < p; ++i) e += (double)d[i] * d[i];
      const double lv = 10 * std::log10(e / kHop + 1e-12);
      levels.push_back(lv);
      if (lv < cfg_.gateDb && !cfg_.denoise) continue;
      spec_.compute(d.data() + p - win_);
      if (cfg_.denoise && nFr < 65000) {
        // histogram log10(amplitudy) w każdym binie, od 1e-9 do 1 co 0,05
        const auto& mg = spec_.mag();
        for (int k = 0; k < K; ++k) {
          const int b = std::max(0, std::min(NB - 1, (int)((std::log10(mg[k] + 1e-12) + 9.0) * 20.0)));
          ++nh[(size_t)k * NB + b];
        }
        ++nFr;
      }
      if (lv < cfg_.gateDb) continue;
      po.minAmp = std::pow(10.0, cfg_.gateDb / 20) * 0.35;
      spec_.pickPeaks(po, pk);
      addTuningVotes(pk, hist, weight, 1.0);
    }
    noiseAmp_.clear();
    if (cfg_.denoise && nFr >= 20) {
      noiseAmp_.assign(K, 0.0);
      const int target = std::max(1, (int)(cfg_.noiseQ * nFr));
      for (int k = 0; k < K; ++k) {
        int acc = 0, b = 0;
        for (; b < NB; ++b) { acc += nh[(size_t)k * NB + b]; if (acc >= target) break; }
        noiseAmp_[k] = std::pow(10.0, (b + 0.5) / 20.0 - 9.0);
      }
      // wygładzenie w częstotliwości (sąsiednie biny), żeby nie wycinać pojedynczych pików
      std::vector<double> sm(K);
      for (int k = 0; k < K; ++k) { double s2 = 0; int n2 = 0; for (int j = std::max(0, k - 3); j <= std::min(K - 1, k + 3); ++j) { s2 += noiseAmp_[j]; ++n2; } sm[k] = s2 / n2; }
      noiseAmp_.swap(sm);
      noiseFixed_ = true;
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
    keepDecimated_ = true;
    applyModelCfg();
    dfull_.clear();
    dfull_.reserve(n / D_ + 1024);
  }

  // ---------------------------------------------------------------- odczyt
  double time() const { return nd_ / fsd_; }
  double winSec() const { return win_ / fsd_; }
  double hopSec() const { return kHop / fsd_; }
  double fsDecimated() const { return fsd_; }
  int sampleRate() const { return fs_; }
  double tuneCents() const { return tuneCents_; }
  long handRejected() const { return hand_.rejected(); }
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
  MultiPitch& dbgPitch() { return mp_; }
  FILE* dumpH_ = nullptr;    // zrzut wejścia HCQT do uczenia modelu gen 5 (tools/train_gen5.py)
  FILE* dumpMask_ = nullptr; // zrzut cech pasm do uczenia modelu maski (tools/train_mask.py)
  FILE* dumpFile_ = nullptr; // zrzut cech kandydatów do uczenia modelu (tools/train_model.py)

  const std::vector<NoteEvent2>& events() const { return tracker_.events; }
  std::vector<NoteEvent2> allEvents() const {
    std::vector<NoteEvent2> ev = tracker_.events;
    const double t = nd_ / fsd_;
    for (const auto& kv : tracker_.active) {
      NoteEvent2 e;
      e.midi = kv.first; e.t0 = kv.second.t0; e.t1 = std::max(t, kv.second.t0 + 0.05); e.vel = kv.second.vel;
      ev.push_back(e);
    }
    std::sort(ev.begin(), ev.end(), [](const NoteEvent2& a, const NoteEvent2& b) { return a.t0 < b.t0 || (a.t0 == b.t0 && (a.midi < b.midi || (a.midi == b.midi && a.t1 < b.t1))); });
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
  BandMask bm_;
  // szum tła z wielu klatek
  std::vector<double> noiseAmp_;            // amplituda szumu na bin (gotowa)
  bool noiseFixed_ = false;                 // z całego nagrania (plik) zamiast statystyki minimów
  mutable Spectrum spx_;   // widmo pomocnicze dla poprawek z kontekstu
  MultiPitch mp_;
  NoteTracker tracker_;
  HandTracker hand_;
  std::vector<float> decOut_, xbuf_;
  std::vector<double> onsetTmp_, onsets_;
  std::vector<Peak> peaks_;
  std::vector<NoteDet> dets_;
  std::vector<FrameRec> frames_;
  std::vector<std::string> chordNames_;
  std::vector<ChordLogEntry> chordLog_;
  std::vector<int16_t> recording_;
  std::vector<float> dfull_;   // cały sygnał po decymacji (tylko analiza pliku, do docinania granic)
  bool keepDecimated_ = false;
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
  std::vector<int> preOnset_;
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
    std::vector<double> na; na.swap(noiseAmp_);
    const bool nfx = noiseFixed_;
    resetState();
    tuneCents_ = tc; prepassed_ = lock; gateEff_ = g;
    noiseAmp_.swap(na); noiseFixed_ = nfx;
    setReference(cfg_.a4 * std::pow(2.0, tuneCents_ / 1200.0));
  }

  void setupWindow() {
    win_ = cfg_.win;
    spec_.init(win_, fsd_, win_ <= 4096 ? 4 : 2);
    spx_.init(win_, fsd_, win_ <= 4096 ? 4 : 2);
    xbuf_.assign(win_, 0.f);
    MultiPitch::Options o;
    o.fs = fsd_;
    o.octaves = cfg_.octaves;
    o.octRatio = cfg_.octRatio;
    o.octRatioMono = cfg_.octRatioMono;
    o.joint = cfg_.joint; o.jointSwap = cfg_.jointSwap; o.jointDrop = cfg_.jointDrop;
    mp_.init(o, cfg_.a4);
  }

  void applyModelCfg() {
    mp_.setModel(cfg_.model && kModelReady && (keepDecimated_ || cfg_.modelLive), cfg_.modelThr >= 0 ? cfg_.modelThr : kModelThr);
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
      if (keepDecimated_) dfull_.insert(dfull_.end(), d + i, d + i + seg);
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
    const double onsetT = pendingOnset_;
    pendingOnset_ = -1;
    fr.onset = onsetT >= 0;
    if (onsetT >= 0) lastOnset_ = onsetT;
    dets_.clear(); peaks_.clear();
    if (silent && cfg_.mask && keepDecimated_) bm_.silent();
    if (!silent) {
      spec_.compute(xbuf_.data());
      PeakOptions po;
      po.mains = cfg_.mains;
      po.minAmp = std::pow(10.0, gateEff_ / 20) * 0.35;
      if (cfg_.denoise && noiseFixed_ && (int)noiseAmp_.size() == spec_.bins()) { po.tnoise = &noiseAmp_; po.tK = cfg_.noiseTK; }
      spec_.pickPeaks(po, peaks_);
      // model maski: ile w każdym paśmie jest gitary; piki w pasmach zdominowanych przez otoczenie odpadają
      if (cfg_.mask && keepDecimated_) { // tylko analiza pliku: maska uczona z widmem szumu z całego nagrania (na żywo: akordy 95 -> 36 %)
        static const std::vector<double> none;
        bm_.compute(spec_, noiseFixed_ ? noiseAmp_ : none, peaks_, (float)clampd((levelDb - gateEff_) / 40.0, 0, 1.5));
        if (dumpMask_) {
          const auto& F = bm_.features();
          for (int b = 0; b < BandMask::NB; ++b) {
            if (F[b * BandMask::NF] < -8.0 / 6.0) continue; // pasma prawie puste
            float row[2 + BandMask::NF];
            row[0] = (float)(t - 0.5 * wSec); row[1] = (float)b;
            for (int k = 0; k < BandMask::NF; ++k) row[2 + k] = F[b * BandMask::NF + k];
            fwrite(row, sizeof(float), 2 + BandMask::NF, dumpMask_);
          }
        }
        if (kMaskReady && cfg_.maskClean) {
          size_t w = 0;
          for (size_t i = 0; i < peaks_.size(); ++i) if (bm_.at(peaks_[i].f) >= cfg_.maskThr) peaks_[w++] = peaks_[i];
          peaks_.resize(w);
        }
      }
      if (cfg_.autoTune && !prepassed_) liveTuning();
      if (cfg_.prior > 1.0) {
        // historia: nuty brzmiące teraz albo zakończone w ostatnich priorSec sekundach
        std::vector<int> pm;
        for (const auto& kv : tracker_.active) pm.push_back(kv.first);
        for (auto it = tracker_.events.rbegin(); it != tracker_.events.rend() && it->t1 > t - cfg_.priorSec; ++it) pm.push_back(it->midi);
        mp_.setPrior(pm, cfg_.prior);
      }
      {
        MultiPitch::FrameInfo fi;
        fi.onset = onsetT >= 0 ? 1.f : 0.f;
        fi.sinceOnset = lastOnset_ < 0 ? 1.f : (float)clampd(t - lastOnset_, 0, 1);
        fi.level = (float)clampd((levelDb - gateEff_) / 40.0, 0, 1.5);
        mp_.setFrameInfo(fi);
        mp_.setMask(cfg_.mask && keepDecimated_ ? &bm_ : nullptr);
      }
      mp_.detect(peaks_, dets_);
      if (dumpFile_) {
        const auto& F = mp_.features(); const auto& ok = mp_.featureOk();
        for (size_t ci = 0; ci < mp_.numCands(); ++ci) {
          if (!ok[ci]) continue;
          float row[2 + MultiPitch::NF];
          row[0] = (float)(t - 0.5 * wSec); row[1] = (float)mp_.candMidi(ci);
          for (int k = 0; k < MultiPitch::NF; ++k) row[2 + k] = F[ci * MultiPitch::NF + k];
          fwrite(row, sizeof(float), 2 + MultiPitch::NF, dumpFile_);
        }
      }
      if (cfg_.sustain) addSustained(t);
      fr.handRejected = (uint8_t)std::min(255, hand_.filter(dets_, t, lastOnset_ < 0 ? 1e9 : t - lastOnset_, wSec));
#ifdef GT_DEBUG
      if (!hand_.lastRej.empty() && std::getenv("GT_TRACE_HAND")) { fprintf(stderr, "HAND t=%.3f rej:", t); for (int m : hand_.lastRej) fprintf(stderr, " %d", m); fprintf(stderr, " | kept:"); for (const auto& d : dets_) fprintf(stderr, " %d", d.midi); fprintf(stderr, "\n"); }
#endif
    }
    tracker_.update(t, dets_, silent, onsetT, hopSec, wSec);

    // stabilne = wykryte teraz i w poprzedniej ramce (albo aktywne w trackerze)
    std::vector<int> cur;
    for (const auto& n : dets_) cur.push_back(n.midi);
    std::vector<const NoteDet*> stable;
    for (const auto& n : dets_) {
      const bool prev = std::find(prevStable_.begin(), prevStable_.end(), n.midi) != prevStable_.end();
      // liveNotes: dowodem dla akordu są tylko nuty potwierdzone przez tracker (akord z nut, nie z pojedynczych ramek)
      // przy analizie pliku zawsze (akordy i tak powstają tam z listy nut); na żywo tylko z liveNotes, bo w pomiarze
      // dawało to większe opóźnienie i migotanie akordu
      const bool notesOnly = cfg_.liveNotes || (keepDecimated_ && cfg_.chordsFromNotes);
      if (notesOnly ? tracker_.active.count(n.midi) > 0 : (prev || tracker_.active.count(n.midi))) stable.push_back(&n);
    }
    if (stable.empty() && prevSilent_) for (const auto& n : dets_) stable.push_back(&n);
    prevStable_ = cur;
    prevSilent_ = silent;

    // ręka: ułożenie palców dla stabilnych nut i strefa na gryfie
    if (!silent) {
      std::vector<int> hm;
      for (const auto* n : stable) hm.push_back(n->midi);
      if (hm.empty()) for (const auto& n : dets_) hm.push_back(n.midi);
      std::vector<FretPos> fgp;
      hand_.observe(hm, t, fgp);
      for (const auto& p : fgp) if (p.s >= 0 && fr.nFg < 6) { fr.fg[fr.nFg].midi = (int16_t)p.midi; fr.fg[fr.nFg].s = (int8_t)p.s; fr.fg[fr.nFg].f = (int8_t)p.f; ++fr.nFg; }
      const auto z = hand_.zone();
      fr.handLo = (int8_t)z.lo; fr.handHi = (int8_t)z.hi;
    }
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



  // ---------------------------------------------------------------- granice nut krótkim oknem
  // Długie okno (372 ms) dobrze rozpoznaje wysokość, ale rozmywa czas. Po analizie pliku każda nuta dostaje własną funkcję
  // początku (pitch-wise onset, por. Onsets and Frames; Ryynänen i Klapuri): energia w oknie 93 ms, krok 11,6 ms, tylko w jej
  // alikwotach powyżej ~380 Hz i tylko w tych, których nie dzieli z innymi nutami brzmiącymi w tym czasie (inaczej wejście
  // innej struny wyglądałoby jak ponowne szarpnięcie). Z tej funkcji:
  //  * początek: najstromsze narastanie przy dotychczasowym początku (w uderzeniu każda struna dostaje własny czas),
  //  * ponowne szarpnięcie tej samej struny w trakcie nuty: wyraźny skok energii po spadku -> podział na dwie nuty,
  //  * koniec: najstromszy spadek, ale tylko wyraźny (>= 10 dB), więc nuty zanikające naturalnie zostają.
  // energia każdego alikwotu osobno (okno 1024 = 93 ms, krok 128 = 11,6 ms), czasy = środki okien
  void partialTracks(const std::vector<double>& parts, double ta, double tb, std::vector<double>& tt, std::vector<std::vector<double>>& en) const {
    const int L = 1024, hop = 128;
    const double fsd = fsd_;
    static std::vector<double> win;
    if ((int)win.size() != L) { win.resize(L); for (int i = 0; i < L; ++i) win[i] = 0.5 - 0.5 * std::cos(2 * kPi * i / L); }
    const int64_t N = (int64_t)dfull_.size();
    tt.clear(); en.assign(parts.size(), std::vector<double>());
    const int64_t s0 = std::max<int64_t>(0, (int64_t)(ta * fsd) - L / 2), s1 = std::min<int64_t>(N - L, (int64_t)(tb * fsd) - L / 2);
    for (int64_t s = s0; s <= s1; s += hop) {
      for (size_t k = 0; k < parts.size(); ++k) {
        const double w = 2 * kPi * parts[k] / fsd, cw = std::cos(w), sw = std::sin(w);
        double c = 1, sn = 0, re = 0, im = 0;
        const float* x = dfull_.data() + s;
        for (int i = 0; i < L; ++i) {
          const double v = x[i] * win[i];
          re += v * c; im -= v * sn;
          const double c2 = c * cw - sn * sw; sn = sn * cw + c * sw; c = c2;
        }
        en[k].push_back(re * re + im * im);
      }
      tt.push_back((s + L / 2) / fsd);
    }
  }

  void refineEvents() {
    const double fsd = fsd_, B = 2.5e-4, minF = 35.0 * fsd / 1024, hopT = 128 / fsd;
    auto& evs = tracker_.events;
    std::sort(evs.begin(), evs.end(), [](const NoteEvent2& a, const NoteEvent2& b) { return a.t0 < b.t0 || (a.t0 == b.t0 && (a.midi < b.midi || (a.midi == b.midi && a.t1 < b.t1))); });
    std::vector<NoteEvent2> out;
    std::vector<double> tt;
    std::vector<std::vector<double>> en;
    for (size_t ei = 0; ei < evs.size(); ++ei) {
      NoteEvent2 e = evs[ei];
      const double f0 = e.f > 0 ? e.f : midiFreq(e.midi, mp_.a4());
      std::vector<double> parts;
      for (int h = 1; h <= 16 && parts.size() < 4; ++h) {
        const double fh = h * f0 * std::sqrt(1 + B * h * h);
        if (fh > 0.45 * fsd || fh > 3500) break;
        if (fh >= minF) parts.push_back(fh);
      }
      if (parts.empty()) { out.push_back(e); continue; }
      // dla każdego alikwotu: początki innych nut (innej wysokości), które go współdzielą; w ich pobliżu ten alikwot nie świadczy
      std::vector<std::vector<double>> sharedOn(parts.size());
      if (cfg_.segShared)
        for (size_t j = 0; j < evs.size(); ++j) {
          if (j == ei || evs[j].midi == e.midi || evs[j].t0 > e.t1 + 0.3 || evs[j].t1 < e.t0 - 0.6) continue;
          const double fo = evs[j].f > 0 ? evs[j].f : midiFreq(evs[j].midi, mp_.a4());
          for (int h = 1; h <= 16; ++h) {
            const double fh = h * fo * std::sqrt(1 + B * h * h);
            if (fh > 3600) break;
            for (size_t k = 0; k < parts.size(); ++k) if (std::fabs(1200 * std::log2(parts[k] / fh)) < 60) sharedOn[k].push_back(evs[j].t0);
          }
        }
      partialTracks(parts, e.t0 - 0.5, e.t1 + 0.45, tt, en);
      const int M = (int)tt.size(), d = 3; // narastanie na 3 krokach (35 ms)
      if (M < 12) { out.push_back(e); continue; }
      // alikwoty użyteczne w chwili t: bez innych nut zaczynających się w [t-0,12; t+0,12]
      auto usable = [&](double t, std::vector<int>& u) {
        u.clear();
        for (size_t k = 0; k < parts.size(); ++k) {
          bool bad = false;
          for (double o : sharedOn[k]) if (std::fabs(o - t) < 0.12) { bad = true; break; }
          if (!bad) u.push_back((int)k);
        }
      };
      auto dbAt = [&](const std::vector<int>& u, int i) {
        i = std::max(0, std::min(M - 1, i));
        double x = 0;
        for (int k : u) x += en[k][i];
        return 10 * std::log10(x + 1e-12);
      };
      std::vector<int> all, u;
      for (size_t k = 0; k < parts.size(); ++k) all.push_back((int)k);
      double peak = -1e9;
      for (int i = 0; i < M; ++i) if (tt[i] >= e.t0 - 0.1 && tt[i] <= e.t1) peak = std::max(peak, dbAt(all, i));
      // początek
      int bi = -1; double br = 0;
      for (int i = 1; i + d < M; ++i) {
        if (tt[i] < e.t0 - cfg_.segBack || tt[i] > e.t0 + 0.15) continue;
        usable(tt[i] + cfg_.segOffset, u);
        if (u.empty()) u = all;
        const double r = dbAt(u, i + d) - dbAt(u, i - 1);
        if (r >= cfg_.segRise && dbAt(all, i + d) >= peak - 14 && r > br + 0.3) { br = r; bi = i; }
      }
      if (bi >= 0 && std::fabs(tt[bi] + cfg_.segOffset - e.t0) > cfg_.segMove) e.t0 = std::max(0.0, tt[bi] + cfg_.segOffset);
      // ponowne szarpnięcia: skok energii w alikwotach, których nie dzieli żadna nuta zaczynająca się w tej chwili
      if (cfg_.resplit) {
        int last = -1000;
        std::vector<double> rs(M, 0.0);
        for (int i = 1; i + d < M; ++i) {
          usable(tt[i] + cfg_.segOffset, u);
          if (u.empty()) continue;
          double pre = -1e9;
          for (int q = std::max(0, i - 6); q <= i - 1; ++q) pre = std::max(pre, dbAt(u, q));
          rs[i] = std::min(dbAt(u, i + d) - dbAt(u, i - 1), dbAt(u, i + d) - pre);
        }
        for (int i = 2; i + d + 1 < M; ++i) {
          const double ts = tt[i] + cfg_.segOffset;
          if (ts < e.t0 + 0.15 || tt[i] > e.t1 - 0.12) continue;
          if (rs[i] < cfg_.splitDb || rs[i - 1] > rs[i] || rs[i + 1] > rs[i] || i - last < 8) continue;
          if (dbAt(all, i + d) < peak - 15) continue;
          NoteEvent2 a = e; a.t1 = ts;
          if (a.t1 - a.t0 >= 0.08) out.push_back(a);
          e.t0 = ts;
          last = i;
        }
      }
      // koniec: najstromszy spadek w [t1-0,4; t1+0,4], tylko wyraźny
      int ki = -1; double bd = 0;
      for (int i = 1; i + d < M; ++i) {
        if (tt[i] < e.t1 - 0.4 || tt[i] > e.t1 + 0.4 || tt[i] < e.t0 + 0.08) continue;
        const double drop = dbAt(all, i - 1) - dbAt(all, i + d);
        if (drop >= 10 && drop > bd) { bd = drop; ki = i; }
      }
      if (ki >= 0) e.t1 = tt[ki] + 1.5 * hopT;
      if (e.t1 < e.t0 + 0.08) e.t1 = e.t0 + 0.08;
      out.push_back(e);
    }
    // duplikaty: ta sama wysokość z początkami bliżej niż 30 ms (np. dwa kawałki przesunięte do tego samego ataku) -> jedna nuta
    std::sort(out.begin(), out.end(), [](const NoteEvent2& a, const NoteEvent2& b) { return a.midi < b.midi || (a.midi == b.midi && a.t0 < b.t0); });
    std::vector<NoteEvent2> ded;
    for (const auto& e : out) {
      if (!ded.empty() && ded.back().midi == e.midi && e.t0 - ded.back().t0 < 0.03) {
        NoteEvent2& d = ded.back();
        d.t1 = std::max(d.t1, e.t1); d.vel = std::max(d.vel, e.vel); d.conf = std::max(d.conf, e.conf);
        continue;
      }
      ded.push_back(e);
    }
    out.swap(ded);
    std::sort(out.begin(), out.end(), [](const NoteEvent2& a, const NoteEvent2& b) { return a.t0 < b.t0 || (a.t0 == b.t0 && (a.midi < b.midi || (a.midi == b.midi && a.t1 < b.t1))); });
    evs.swap(out);
  }

  // ---------------------------------------------------------------- model gen 5
  // Analiza pliku: sieć na całym nagraniu zastępuje listę nut i nuty w ramkach; potem jak dotąd docinanie początków i akordy z nut.
  void applyGen5(const Hcqt& h) {
    Gen5 net;
    net.run(h);
    Gen5::DecodeOpt o;
    o.thOn = cfg_.g5On; o.thFr = cfg_.g5Fr; o.thStart = cfg_.g5Start;
    net.decode(h, fsd_, mp_.a4(), o, tracker_.events);
    tracker_.active.clear();
    for (size_t m = 0; m < frames_.size() && (int)m < net.T; ++m) {
      FrameRec& fr = frames_[m];
      struct Q { int s; float p; };
      std::vector<Q> q;
      for (int s = 0; s < Gen5::S; ++s) if (net.fr((int)m, s) >= cfg_.g5Fr) q.push_back({s, net.fr((int)m, s)});
      std::sort(q.begin(), q.end(), [](const Q& a, const Q& b) { return a.p > b.p; });
      if (q.size() > 8) q.resize(8);
      std::sort(q.begin(), q.end(), [](const Q& a, const Q& b) { return a.s < b.s; });
      fr.nNotes = (uint8_t)q.size();
      for (size_t i = 0; i < q.size(); ++i) {
        FrameNote& n = fr.notes[i];
        n.midi = (int16_t)(Hcqt::kMidi0 + q[i].s); n.f = (float)midiFreq(n.midi, mp_.a4()); n.cents = 0;
        n.amp = h.at((int)m, 1, 3 * q[i].s + 1); n.stable = true;
      }
    }
  }

  // ---------------------------------------------------------------- kontekst czasowy
  // Atak nuty o częstotliwości f0 w chwili t: narastanie energii w jej alikwotach (bez tych, które dzieli z nutami `excl`
  // zaczynającymi się w tej chwili). rise = największe narastanie [dB/35 ms] w [t-0,06; t+0,12], before/after = poziom przed i po.
  bool attackAt(double f0, double t, const std::vector<double>& excl, double& rise, double& before, double& after) const {
    const double fsd = fsd_, B = 2.5e-4, minF = 35.0 * fsd / 1024;
    std::vector<double> parts;
    for (int h = 1; h <= 16 && parts.size() < 4; ++h) {
      const double fh = h * f0 * std::sqrt(1 + B * h * h);
      if (fh > 0.45 * fsd || fh > 3500) break;
      if (fh < minF) continue;
      bool sh = false;
      for (double fo : excl) {
        for (int k = 1; k <= 16 && !sh; ++k) { const double x = k * fo * std::sqrt(1 + B * k * k); if (x > 3600) break; if (std::fabs(1200 * std::log2(fh / x)) < 60) sh = true; }
        if (sh) break;
      }
      if (!sh) parts.push_back(fh);
    }
    if (parts.empty()) return false;
    std::vector<double> tt;
    std::vector<std::vector<double>> en;
    partialTracks(parts, t - 0.35, t + 0.35, tt, en);
    const int M = (int)tt.size(), d = 3;
    if (M < 10) return false;
    std::vector<double> db(M);
    for (int i = 0; i < M; ++i) { double x = 0; for (const auto& e : en) x += e[i]; db[i] = 10 * std::log10(x + 1e-12); }
    rise = -1e9; before = 1e9; after = -1e9;
    for (int i = 1; i + d < M; ++i) {
      const double tc = tt[i] + cfg_.segOffset;
      if (tc >= t - 0.06 && tc <= t + 0.12) rise = std::max(rise, db[i + d] - db[i - 1]);
      if (tt[i] >= t - 0.30 && tt[i] <= t - 0.12) before = std::min(before, db[i]);
      if (tt[i] >= t + 0.05 && tt[i] <= t + 0.30) after = std::max(after, db[i]);
    }
    return rise > -1e8 && after > -1e8;
  }

  double evF0(const NoteEvent2& e) const { return e.f > 0 ? e.f : midiFreq(e.midi, mp_.a4()); }

  // Dowód obecności wysokości f0 w widmie spx_: alikwoty 1..8 wyraźnie ponad lokalnym szumem (ctxK), niewspólne z nutami `other`
  // (1 pkt), wspólne tylko z nutą niższą (0,5 pkt, jak przy podtrzymaniu). Zwraca sumę punktów.
  double harmonicEvidence(double f0, const std::vector<double>& other) const {
    const auto& mag = spx_.mag();
    const auto& nf = spx_.noiseFloor();
    const double bh = spx_.binHz(), B = 2.5e-4;
    const int K = (int)mag.size();
    double evd = 0;
    for (int h = 1; h <= 8; ++h) {
      const double fh = h * f0 * std::sqrt(1 + B * h * h);
      if (fh > 4800 || fh > 0.45 * fsd_) break;
      const double tol = 25 + 1.5 * h;
      const int k0 = std::max(2, (int)std::floor(fh * std::pow(2.0, -tol / 1200) / bh)), k1 = std::min(K - 2, (int)std::ceil(fh * std::pow(2.0, tol / 1200) / bh));
      double mb = 0; int kb = -1;
      for (int q = k0; q <= k1; ++q) if (mag[q] > mb && mag[q] >= mag[q - 1] && mag[q] >= mag[q + 1]) { mb = mag[q]; kb = q; }
      if (kb < 0 || mb < cfg_.ctxK * nf[kb] || mb < std::pow(10.0, gateEff_ / 20) * 0.35) continue;
      bool low = false, high = false;
      for (double fo : other)
        for (int k = 1; k <= 12; ++k) {
          const double x = k * fo * std::sqrt(1 + B * k * k);
          if (std::fabs(1200 * std::log2(fh / x)) < 45) { (fo < f0 ? low : high) = true; break; }
        }
      if (high) continue;
      evd += low ? 0.5 : 1.0;
    }
    return evd;
  }

  // Poprawki z kontekstu czasowego, po dopracowaniu granic nut:
  //  1. dopowiadanie: wysokość grana w sąsiednich uderzeniach (do ctxSpan s wstecz i w przód), a w tym uderzeniu niewykryta,
  //     jest dodawana, jeśli w jej własnych alikwotach widać atak (>= ctxRise) i poziom po ataku jest podobny jak tam,
  //  2. sklejanie: ta sama wysokość przerwana na krótko (< ctxGap) bez nowego ataku to jedna nuta,
  //  3. usuwanie: nuta krótsza niż ctxShort bez ataku we własnych alikwotach to przebłysk, nie zagrany dźwięk.
  void contextRepair() {
    auto& ev = tracker_.events;
    auto byT = [](const NoteEvent2& a, const NoteEvent2& b) { return a.t0 < b.t0 || (a.t0 == b.t0 && (a.midi < b.midi || (a.midi == b.midi && a.t1 < b.t1))); };
    std::sort(ev.begin(), ev.end(), byT);
    // 3. usuwanie przebłysków
    if (cfg_.ctxPrune) {
      std::vector<NoteEvent2> keep;
      for (size_t i = 0; i < ev.size(); ++i) {
        const NoteEvent2& e = ev[i];
        if (e.t1 - e.t0 >= cfg_.ctxShort) { keep.push_back(e); continue; }
        std::vector<double> ex;
        for (const auto& o : ev) if (&o != &e && o.midi != e.midi && std::fabs(o.t0 - e.t0) < 0.12) ex.push_back(evF0(o));
        double r, b, a;
        if (!attackAt(evF0(e), e.t0, ex, r, b, a) || r >= cfg_.ctxRise) keep.push_back(e);
      }
      ev.swap(keep);
    }
    // 2. sklejanie przerwanych nut
    if (cfg_.ctxMerge) {
      std::sort(ev.begin(), ev.end(), [](const NoteEvent2& a, const NoteEvent2& b) { return a.midi < b.midi || (a.midi == b.midi && a.t0 < b.t0); });
      std::vector<NoteEvent2> out;
      for (const auto& e : ev) {
        if (!out.empty() && out.back().midi == e.midi && e.t0 - out.back().t1 < cfg_.ctxGap && e.t0 >= out.back().t0) {
          std::vector<double> ex;
          for (const auto& o : ev) if (o.midi != e.midi && std::fabs(o.t0 - e.t0) < 0.12) ex.push_back(evF0(o));
          double r, b, a;
          const bool attack = attackAt(evF0(e), e.t0, ex, r, b, a) && r >= cfg_.splitDb;
          if (!attack) { out.back().t1 = std::max(out.back().t1, e.t1); out.back().vel = std::max(out.back().vel, e.vel); continue; }
        }
        out.push_back(e);
      }
      ev.swap(out);
      std::sort(ev.begin(), ev.end(), byT);
    }
    // 1. dopowiadanie z sąsiednich uderzeń
    if (cfg_.ctxFill) {
      std::vector<double> starts, ends;
      for (const auto& e : ev) {
        if (starts.empty() || e.t0 - ends.back() > cfg_.chGroup || e.t0 - starts.back() > 0.25) { starts.push_back(e.t0); ends.push_back(e.t0); }
        else ends.back() = e.t0;
      }
      std::vector<NoteEvent2> add;
      for (size_t g = 0; g < starts.size(); ++g) {
        const double a = starts[g], ga = ends[g];
        std::vector<int> here;
        std::vector<double> exF;
        double gEnd = a;
        int nHere = 0;
        for (const auto& e : ev) {
          if (e.t0 >= a - 0.02 && e.t0 <= ga + 0.02) { here.push_back(e.midi); exF.push_back(evF0(e)); gEnd = std::max(gEnd, e.t1); ++nHere; }
          else if (e.t0 < a && e.t1 > a + 0.05) here.push_back(e.midi); // nadal brzmi
        }
        if (nHere < 3) continue; // dopowiadamy tylko w uderzeniach (kilka strun naraz)
        std::vector<const NoteEvent2*> cands;
        for (const auto& e : ev) {
          if (std::fabs(e.t0 - a) > cfg_.ctxSpan || (e.t0 >= a - 0.02 && e.t0 <= ga + 0.02)) continue;
          if (std::find(here.begin(), here.end(), e.midi) != here.end()) continue;
          bool dup = false;
          for (const auto* c : cands) if (c->midi == e.midi) { dup = true; if (std::fabs(e.t0 - a) < std::fabs(c->t0 - a)) { const NoteEvent2* x = &e; for (auto& cc : cands) if (cc->midi == e.midi) cc = x; } }
          if (!dup) cands.push_back(&e);
        }
        // widmo ustalone po uderzeniu (długie okno), wysokości brzmiące w tej chwili
        const double tc = a + cfg_.ctxAt;
        const int64_t c0 = (int64_t)(tc * fsd_) - win_ / 2;
        if (c0 < 0 || c0 + win_ > (int64_t)dfull_.size()) continue;
        // widmo tuż przed uderzeniem (okno kończy się przed atakiem): wysokość słyszalna już wtedy to wybrzmiewanie, nie nowe szarpnięcie
        const int64_t p0 = (int64_t)((a - 0.02) * fsd_) - win_;
        std::vector<double> preEv(cands.size(), 0.0);
        if (p0 >= 0) {
          spx_.compute(dfull_.data() + p0);
          std::vector<double> preF;
          for (const auto& e : ev) if (e.t0 <= a - 0.1 && e.t1 >= a - 0.1) preF.push_back(evF0(e));
          for (size_t k = 0; k < cands.size(); ++k) preEv[k] = harmonicEvidence(evF0(*cands[k]), preF);
        }
        spx_.compute(dfull_.data() + c0);
        std::vector<double> soundF;
        for (const auto& e : ev) if (e.t0 <= tc && e.t1 >= tc) soundF.push_back(evF0(e));
        for (size_t k = 0; k < cands.size(); ++k) {
          const NoteEvent2* c = cands[k];
          if (preEv[k] >= cfg_.ctxEvidence - 1) continue;
          const double ev_ = harmonicEvidence(evF0(*c), soundF);
          if (ev_ < cfg_.ctxEvidence) continue;
          NoteEvent2 n = *c;
          n.t0 = a; n.t1 = std::max(a + 0.1, gEnd);
          for (const auto& o : ev) if (o.midi == c->midi && o.t0 > a) n.t1 = std::min(n.t1, o.t0);
          n.vel = std::max(20, c->vel - 8);
          add.push_back(n);
          here.push_back(c->midi);
          soundF.push_back(evF0(*c));
        }
      }
      for (const auto& n : add) ev.push_back(n);
      std::sort(ev.begin(), ev.end(), byT);
    }
  }

  // ---------------------------------------------------------------- akordy z nut
  // Nuty są wynikiem podstawowym, akord jest ich nazwą. Po analizie pliku (i po dopracowaniu granic nut) grupujemy początki nut
  // w uderzenia, a dla każdego odcinka między uderzeniami bierzemy nuty, które wtedy brzmią:
  //  * jeśli samo uderzenie ma >= chFreshMin klas dźwięków (uderzenie w akord), liczą się tylko nowe nuty,
  //  * inaczej (arpeggio, pojedyncze struny) także nuty brzmiące z wcześniejszych uderzeń, z wagą malejącą z czasem.
  // Nazwę daje ten sam dobór szablonu co dotąd (recognizeChord), bas = najniższa nowa nuta. Wynik zastępuje etykiety
  // akordów w ramkach i historię akordów.
  void chordsFromNotes() {
    std::vector<NoteEvent2> ev = tracker_.events;
    std::sort(ev.begin(), ev.end(), [](const NoteEvent2& a, const NoteEvent2& b) { return a.t0 < b.t0 || (a.t0 == b.t0 && (a.midi < b.midi || (a.midi == b.midi && a.t1 < b.t1))); });
    struct Seg { double a, b; std::string name; float score; std::string alt[2]; int nAlt; int pcs; int freshPcs; int nFresh; };
    std::vector<Seg> segs;
    // uderzenia: kolejne początki bliżej niż chGroup od poprzedniego (łańcuch), całość najwyżej 0,25 s
    std::vector<double> starts, ends;
    std::vector<int> pcsOf;
    for (size_t i = 0; i < ev.size(); ++i) {
      if (starts.empty() || ev[i].t0 - ends.back() > cfg_.chGroup || ev[i].t0 - starts.back() > 0.25) { starts.push_back(ev[i].t0); ends.push_back(ev[i].t0); pcsOf.push_back(0); }
      else ends.back() = ev[i].t0;
      pcsOf.back() |= 1 << (ev[i].midi % 12);
    }
    // dopełnianie akordu: uderzenie z niewielu nowych dźwięków krótko po pełnym uderzeniu (spóźniona struna, nuta wykryta
    // z opóźnieniem) dołącza do niego, a akord jest liczony ze wszystkich jego nut
    if (cfg_.chLate > 0) {
      std::vector<double> s2, e2;
      std::vector<int> p2;
      for (size_t g = 0; g < starts.size(); ++g) {
        const int n = __builtin_popcount(pcsOf[g]);
        if (!s2.empty() && n < cfg_.chKeepMax && __builtin_popcount(p2.back()) >= cfg_.chKeepMax && starts[g] - s2.back() < cfg_.chLate) {
          e2.back() = ends[g]; p2.back() |= pcsOf[g];
        } else { s2.push_back(starts[g]); e2.push_back(ends[g]); p2.push_back(pcsOf[g]); }
      }
      starts.swap(s2); ends.swap(e2);
    }
    for (size_t g = 0; g < starts.size(); ++g) {
      const double a = starts[g], b = g + 1 < starts.size() ? starts[g + 1] : 1e9, ga = ends[g];
      double w[12] = {0}, wf[12] = {0};
      struct Use { int midi; double wt; bool fresh; };
      std::vector<Use> used;
      double end = a;
      for (const auto& e : ev) {
        if (e.t0 > ga + 0.02) continue;
        const bool fresh = e.t0 >= a - 0.02;
        // ogon poprzedniego uderzenia, który kończy się zaraz po nim, nie należy do nowego akordu
        if (!fresh && e.t1 <= ga + 0.12) continue;
        const double amp = std::pow(10.0, (e.vel - 64) / 28.0); // odwrotność NoteTracker::velocity (amplituda względna)
        // krótkie nuty (zwykle duchy albo urwane ogony) ważą mniej
        const double dur = std::min(1.0, (e.t1 - e.t0) / cfg_.chShort);
        // pewność nuty (przy modelu: średnie prawdopodobieństwo); niepewne nuty ważą mniej
        const double cf = std::pow(clampd(e.conf, 0.05, 1.0), cfg_.chConfPow);
        const double x = std::sqrt(amp) * dur * cf * (fresh ? 1.0 : std::exp(-(a - e.t0) / cfg_.chCarryTau));
        const int pc = e.midi % 12;
        if (fresh) wf[pc] += x;
        w[pc] += x;
        used.push_back({e.midi, x, fresh});
        end = std::max(end, e.t1);
      }
      int nf = 0;
      for (int p = 0; p < 12; ++p) if (wf[p] > 0) ++nf;
      const bool freshOnly = nf >= cfg_.chFreshMin;
      // uzupełnienie: wysokości widoczne w ramkach odcinka, ale niepotwierdzone jako nuty (słaby dowód, chFrameW)
      if (cfg_.chFrameW > 0) {
        const double half = 0.5 * win_ / fsd_, fb = std::min(b, a + 1.0);
        double fw[12] = {0};
        int nfr = 0;
        for (const auto& fr : frames_) {
          const double tc = fr.t - half;
          if (tc < a + 0.05 || tc >= fb || fr.silent) continue;
          ++nfr;
          for (int k = 0; k < fr.nNotes; ++k) fw[fr.notes[k].midi % 12] += std::sqrt(std::max(1e-6f, fr.notes[k].amp));
        }
        if (nfr > 0) {
          double ref = 0;
          for (const auto& u : used) ref = std::max(ref, u.wt);
          double fmax = 0;
          for (int p = 0; p < 12; ++p) fmax = std::max(fmax, fw[p]);
          if (fmax > 0 && ref > 0)
            for (int p = 0; p < 12; ++p) {
              const double x = cfg_.chFrameW * ref * fw[p] / fmax;
              wf[p] += x; w[p] += x;
            }
        }
      }
      const double* src = freshOnly ? wf : w;
      double tot = 0, wmax = 0;
      for (int p = 0; p < 12; ++p) tot += src[p];
      for (const auto& u : used) if (u.fresh || !freshOnly) wmax = std::max(wmax, u.wt);
      // bas: najniższa wyraźna nuta spośród liczonych
      int bass = 1000;
      for (const auto& u : used) if ((u.fresh || !freshOnly) && u.wt >= cfg_.chBassRel * wmax) bass = std::min(bass, u.midi);
      Seg sg{a, std::min(b, end), std::string(), 0.f, {}, 0, 0, 0, nf};
      for (int p = 0; p < 12; ++p) if (wf[p] > 0) sg.freshPcs |= 1 << p;
      if (tot > 0) {
        double ww[12];
        for (int p = 0; p < 12; ++p) ww[p] = src[p] / tot;
        const ChordResult r = recognizeChord(ww, bass < 1000 ? bass % 12 : -1, cfg_.chord);
        if (r.ok) {
          sg.name = r.name; sg.score = r.score; sg.nAlt = r.nAlt; for (int k = 0; k < r.nAlt; ++k) sg.alt[k] = r.alt[k];
          const ChordTemplate& T = kChordTemplates[r.tpl];
          for (int q = 0; q < T.n; ++q) sg.pcs |= 1 << ((r.root + T.iv[q]) % 12);
        }
      }
      segs.push_back(sg);
    }
    // nowe nuty, które należą do bieżącego akordu (pojedyncza struna w arpeggio, spóźniona struna uderzenia), nie zmieniają
    // jego nazwy; odcinek bez nazwy przejmuje poprzednią
    for (size_t i = 1; i < segs.size(); ++i) {
      Seg& p = segs[i - 1];
      Seg& c = segs[i];
      if (p.name.empty() || c.a > p.b + 0.05) continue;
      const bool fits = c.nFresh < cfg_.chKeepMax && (c.freshPcs & ~p.pcs) == 0;
      if (c.name.empty() || (fits && c.name != p.name)) {
        c.name = p.name; c.score = p.score; c.pcs = p.pcs; c.nAlt = p.nAlt; for (int k = 0; k < p.nAlt; ++k) c.alt[k] = p.alt[k];
      }
    }
    // ramki: etykieta odcinka, w którym leży środek okna analizy
    const double half = 0.5 * win_ / fsd_;
    size_t si = 0;
    for (auto& fr : frames_) {
      const double tc = fr.t - half;
      while (si + 1 < segs.size() && segs[si + 1].a <= tc) ++si;
      fr.chord = -1; fr.chordScore = 0; fr.alt[0] = fr.alt[1] = -1;
      if (segs.empty() || fr.silent || tc < segs[si].a || tc > segs[si].b || segs[si].name.empty()) continue;
      fr.chord = (int16_t)chordId(segs[si].name);
      fr.chordScore = segs[si].score;
      for (int k = 0; k < segs[si].nAlt; ++k) fr.alt[k] = (int16_t)chordId(segs[si].alt[k]);
    }
    chordLog_.clear();
    double prevEnd = -1;
    for (const auto& sg : segs) {
      if (sg.name.empty()) continue;
      if (chordLog_.empty() || chordLog_.back().name != sg.name || sg.a > prevEnd + 0.3) chordLog_.push_back({sg.a, sg.name});
      prevEnd = std::max(prevEnd, sg.b);
    }
  }

  // Czułość podtrzymania. Nuta, która już brzmi, ale w tej ramce nie przeszła zwykłych progów (zanikła pod nowszymi dźwiękami,
  // cichnie), jest sprawdzana jeszcze raz w widmie z obniżonym progiem szumu, tylko w miejscach jej alikwotów.
  // Próg jest najniższy tuż po mocnym wykryciu i rośnie z czasem do zwykłego. Alikwoty wspólne z innymi nutami nie liczą się
  // jako dowód (inaczej poduktawa podtrzymywałaby się na energii wyższej nuty).
  void addSustained(double t) {
    if (tracker_.active.empty()) return;
    const auto& mag = spec_.mag();
    const auto& nf = spec_.noiseFloor();
    const double bh = spec_.binHz(), B = 2.5e-4;
    const int K = (int)mag.size();
    std::vector<NoteDet> add;
    for (const auto& kv : tracker_.active) {
      const int m = kv.first;
      const NoteTracker::Active& a = kv.second;
      bool present = false;
      for (const auto& d : dets_) if (d.midi == m) { present = true; break; }
      if (present || a.f <= 0) continue;
      const double age = t - a.lastStrong;
      if (age > cfg_.susHold + 10.0) continue;
      const bool struck = lastOnset_ >= 0 && a.lastStrong < lastOnset_;
      const double k = cfg_.susK + (age <= cfg_.susHold ? 0.0 : (4.5 - cfg_.susK) * (age - cfg_.susHold) / 10.0);
      int hits = 0, indep = 0;
      double a2 = 0, evidence = 0;
      for (int h = 1; h <= 8; ++h) {
        const double fh = h * a.f * std::sqrt(1 + B * h * h);
        if (fh > 4800 || fh > 0.45 * fsd_) break;
        const double tol = 25 + 1.5 * h;
        const int k0 = std::max(2, (int)std::floor(fh * std::pow(2.0, -tol / 1200) / bh)), k1 = std::min(K - 2, (int)std::ceil(fh * std::pow(2.0, tol / 1200) / bh));
        int kb = -1;
        double mb = 0;
        for (int q = k0; q <= k1; ++q) if (mag[q] > mb && mag[q] >= mag[q - 1] && mag[q] >= mag[q + 1]) { mb = mag[q]; kb = q; }
        if (kb < 0 || mb < k * nf[kb] || mb < std::pow(10.0, gateEff_ / 20) * 0.2) continue;
        ++hits;
        // dowód: alikwot niezależny liczy się w całości; wspólny z nutą niższą (typowa wyższa oktawa) w połowie;
        // wspólny z nutą wyższą wcale (tak podtrzymywałaby się poduktawa na energii wyższej nuty)
        bool sharedLow = false, sharedHigh = false;
        auto share = [&](const NoteDet& o) {
          for (int h2 = 1; h2 <= 12; ++h2)
            if (std::fabs(1200 * std::log2(fh / (h2 * o.f * std::sqrt(1 + B * h2 * h2)))) < 45) { (o.f < a.f ? sharedLow : sharedHigh) = true; return; }
        };
        for (const auto& o : dets_) share(o);
        for (const auto& o : add) share(o);
        if (sharedHigh) continue;
        // po nowym uderzeniu stara nuta, której nikt nie potwierdził, przeżywa tylko na własnych alikwotach
        // (wspólne z nowymi, niższymi nutami nie dowodzą, że ona jeszcze brzmi)
        if (sharedLow && struck) continue;
        evidence += sharedLow ? 0.5 : 1.0;
        if (!sharedLow) ++indep;
        if (h <= 4) a2 += mb * mb;
      }
#ifdef GT_DEBUG
      if (std::getenv("GT_TRACE_SUS") && std::atoi(std::getenv("GT_TRACE_SUS")) == m) fprintf(stderr, "SUS t=%.2f midi=%d f=%.1f age=%.2f k=%.2f hits=%d indep=%d evidence=%.1f -> %s\n", t, m, a.f, age, k, hits, indep, evidence, evidence >= cfg_.susEvidence ? "podtrzymana" : "koniec");
#endif
      if (evidence < cfg_.susEvidence) continue;
      NoteDet n;
      n.midi = m; n.f = (float)a.f; n.cents = (float)(1200 * std::log2(a.f / midiFreq(m, mp_.a4())));
      n.amp = (float)std::sqrt(a2); n.score = (float)(a.score * 0.6); n.nh = hits; n.sustained = true;
      add.push_back(n);
    }
    for (const auto& n : add) dets_.push_back(n);
    if (!add.empty()) std::sort(dets_.begin(), dets_.end(), [](const NoteDet& x, const NoteDet& y) { return x.midi < y.midi; });
  }

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
      preOnset_.clear();
      for (const auto& kv : tracker_.active) preOnset_.push_back(kv.first); // co brzmiało przed uderzeniem
      segStart_ = onsetT; segLogged_ = -1;
    }
    const double settle = lastOnset_ < 0 ? 1.0 : clampd((t - lastOnset_ - 0.05) / (wSec - 0.05), 0, 1);
    const double ws = std::pow(settle, 1.5);
    const double lam = std::exp(-hopSec / 2.5);
    if (!changed_) for (int p = 0; p < 12; ++p) { harmEv_[p] *= lam; harmBass_[p] *= lam; }
    // nuty podtrzymane z obniżonym progiem nie są dowodem dla akordu tuż po uderzeniu: okno zawiera jeszcze energię starego akordu
    auto stale = [&](const NoteDet* n) { return n->sustained && settle < 1.0; };
    double sMax = 0, aMax = 0;
    for (const auto* n : stable) { if (stale(n)) continue; sMax = std::max<double>(sMax, n->score); aMax = std::max<double>(aMax, n->amp); }
    int bass = 1000;
    for (const auto* n : stable) {
      if (stale(n)) continue;
      const double a = std::sqrt(std::max<double>(n->amp, 1e-6));
      const int pc = n->midi % 12;
      // tuż po uderzeniu okno zawiera jeszcze stary akord, ale nuta, która wcześniej nie brzmiała, jest czystym dowodem nowego
      const bool fresh = cfg_.freshFull && std::find(preOnset_.begin(), preOnset_.end(), n->midi) == preOnset_.end();
      segEv_[pc] += (fresh ? std::max(ws, 0.6) : ws) * a;
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
    for (const auto& d : dets_) if (!d.octave && !d.sustained) { ++nBase; single = &d; }
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
