// dbg_frame.cpp - podgląd pików i kandydatów w jednej ramce (diagnostyka algorytmu)
// użycie: dbg_frame in.wav czas_s midi
#define GT_DEBUG 1
#include <cstdio>
#include <cstdlib>
#include "../src/gt_engine.hpp"
#include "wavio.hpp"
using namespace gt;
int main(int argc, char** argv) {
  std::vector<float> x; int fs;
  wavio::read16(argv[1], x, fs);
  const double T = atof(argv[2]); const int midi = atoi(argv[3]);
  Decimator dec; int D = std::max(1, (int)std::lround(fs / 11025.0)); dec.init(D);
  std::vector<float> d; dec.process(x.data(), (int)x.size(), d);
  const double fsd = (double)fs / D; const int N = 4096;
  size_t end = (size_t)(T * fsd);
  Spectrum sp; sp.init(N, fsd, 4);
  sp.compute(d.data() + end - N);
  PeakOptions po; po.mains = 50; po.minAmp = std::pow(10.0, -62.0 / 20) * 0.35;
  std::vector<Peak> pk; sp.pickPeaks(po, pk);
  printf("%zu peaks (f,a dB):", pk.size());
  for (auto& p : pk) if (p.f < 1500) printf(" %.1f/%.0f", p.f, 20 * std::log10(p.a));
  printf("\n");
  for (int mode = 0; mode < 2; ++mode) {
    MultiPitch mp; MultiPitch::Options o; o.fs = fsd; o.octaves = false; mp.init(o, 440); mp.dbgMidi_ = midi;
    std::vector<NoteDet> nd; mp.detect(pk, nd);
    printf("%s:", mode ? "gładkość" : "binarne  ");
    for (auto& n : nd) printf("  %s(%.2f)", midiName(n.midi).c_str(), n.score);
    printf("\n");
  }
}
