// cli.cpp - narzędzie wiersza poleceń: analiza pliku WAV silnikiem C++ i zapis wyniku w JSON.
// Użycie: gt_cli analyze in.wav out.json [--live] [--no-autotune] [--no-autogate] [--win N]
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include "gt_engine.hpp"
#include "../tools/wavio.hpp"

using namespace gt;

int main(int argc, char** argv) {
  if (argc < 4 || strcmp(argv[1], "analyze") != 0) {
    fprintf(stderr, "użycie: gt_cli analyze in.wav out.json [--live] [--no-autotune] [--no-autogate] [--win N]\n");
    return 2;
  }
  EngineConfig cfg;
  bool live = false;
  for (int i = 4; i < argc; ++i) {
    if (!strcmp(argv[i], "--live")) live = true;
    else if (!strcmp(argv[i], "--no-autotune")) cfg.autoTune = false;
    else if (!strcmp(argv[i], "--no-autogate")) cfg.autoGate = false;
    else if (!strcmp(argv[i], "--win") && i + 1 < argc) cfg.win = atoi(argv[++i]);
    else if (!strcmp(argv[i], "--no-octaves")) cfg.octaves = false;
    else if (!strcmp(argv[i], "--no-hand")) cfg.hand = false;
    else if (!strcmp(argv[i], "--no-joint")) cfg.joint = false;
    else if (!strcmp(argv[i], "--no-context")) cfg.context = false;
    else if (!strcmp(argv[i], "--no-denoise")) cfg.denoise = false;
    else if (!strcmp(argv[i], "--model")) cfg.model = true;
    else if (!strcmp(argv[i], "--model-live")) cfg.modelLive = true;
    else if (!strcmp(argv[i], "--no-model")) cfg.model = false;
    else if (!strcmp(argv[i], "--mthr") && i + 1 < argc) cfg.modelThr = atof(argv[++i]);
    else if (!strcmp(argv[i], "--noiseq") && i + 1 < argc) cfg.noiseQ = atof(argv[++i]);
    else if (!strcmp(argv[i], "--noisetk") && i + 1 < argc) cfg.noiseTK = atof(argv[++i]);
    else if (!strcmp(argv[i], "--prior") && i + 1 < argc) cfg.prior = atof(argv[++i]);
    else if (!strcmp(argv[i], "--priorsec") && i + 1 < argc) cfg.priorSec = atof(argv[++i]);
    else if (!strcmp(argv[i], "--no-ctxfill")) cfg.ctxFill = false;
    else if (!strcmp(argv[i], "--no-ctxmerge")) cfg.ctxMerge = false;
    else if (!strcmp(argv[i], "--no-ctxprune")) cfg.ctxPrune = false;
    else if (!strcmp(argv[i], "--ctxspan") && i + 1 < argc) cfg.ctxSpan = atof(argv[++i]);
    else if (!strcmp(argv[i], "--ctxk") && i + 1 < argc) cfg.ctxK = atof(argv[++i]);
    else if (!strcmp(argv[i], "--ctxev") && i + 1 < argc) cfg.ctxEvidence = atof(argv[++i]);
    else if (!strcmp(argv[i], "--ctxat") && i + 1 < argc) cfg.ctxAt = atof(argv[++i]);
    else if (!strcmp(argv[i], "--ctxrise") && i + 1 < argc) cfg.ctxRise = atof(argv[++i]);
    else if (!strcmp(argv[i], "--ctxdrop") && i + 1 < argc) cfg.ctxDrop = atof(argv[++i]);
    else if (!strcmp(argv[i], "--ctxgap") && i + 1 < argc) cfg.ctxGap = atof(argv[++i]);
    else if (!strcmp(argv[i], "--ctxshort") && i + 1 < argc) cfg.ctxShort = atof(argv[++i]);
    else if (!strcmp(argv[i], "--no-learnb")) cfg.learnB = false;
    else if (!strcmp(argv[i], "--lt0") && i + 1 < argc) cfg.learnTol0 = atof(argv[++i]);
    else if (!strcmp(argv[i], "--lt1") && i + 1 < argc) cfg.learnTol1 = atof(argv[++i]);
    else if (!strcmp(argv[i], "--no-chnotes")) cfg.chordsFromNotes = false;
    else if (!strcmp(argv[i], "--chgroup") && i + 1 < argc) cfg.chGroup = atof(argv[++i]);
    else if (!strcmp(argv[i], "--chtau") && i + 1 < argc) cfg.chCarryTau = atof(argv[++i]);
    else if (!strcmp(argv[i], "--chbass") && i + 1 < argc) cfg.chBassRel = atof(argv[++i]);
    else if (!strcmp(argv[i], "--chshort") && i + 1 < argc) cfg.chShort = atof(argv[++i]);
    else if (!strcmp(argv[i], "--chkeep") && i + 1 < argc) cfg.chKeepMax = atoi(argv[++i]);
    else if (!strcmp(argv[i], "--chlate") && i + 1 < argc) cfg.chLate = atof(argv[++i]);
    else if (!strcmp(argv[i], "--live-notes")) cfg.liveNotes = true;
    else if (!strcmp(argv[i], "--chframe") && i + 1 < argc) cfg.chFrameW = atof(argv[++i]);
    else if (!strcmp(argv[i], "--chfresh") && i + 1 < argc) cfg.chFreshMin = atoi(argv[++i]);
    else if (!strcmp(argv[i], "--no-resplit")) cfg.resplit = false;
    else if (!strcmp(argv[i], "--no-segshared")) cfg.segShared = false;
    else if (!strcmp(argv[i], "--splitdb") && i + 1 < argc) cfg.splitDb = atof(argv[++i]);
    else if (!strcmp(argv[i], "--segrise") && i + 1 < argc) cfg.segRise = atof(argv[++i]);
    else if (!strcmp(argv[i], "--segback") && i + 1 < argc) cfg.segBack = atof(argv[++i]);
    else if (!strcmp(argv[i], "--segmove") && i + 1 < argc) cfg.segMove = atof(argv[++i]);
    else if (!strcmp(argv[i], "--segoff") && i + 1 < argc) cfg.segOffset = atof(argv[++i]);
    else if (!strcmp(argv[i], "--no-octmodel")) cfg.octModel = false;
    else if (!strcmp(argv[i], "--omthr") && i + 1 < argc) cfg.octModelThr = atof(argv[++i]);
    else if (!strcmp(argv[i], "--ommono") && i + 1 < argc) cfg.octModelThrMono = atof(argv[++i]);
    else if (!strcmp(argv[i], "--jswap") && i + 1 < argc) cfg.jointSwap = atof(argv[++i]);
    else if (!strcmp(argv[i], "--jdrop") && i + 1 < argc) cfg.jointDrop = atof(argv[++i]);
    else if (!strcmp(argv[i], "--no-sustain")) cfg.sustain = false;
    else if (!strcmp(argv[i], "--no-refine")) cfg.refine = false;
    else if (!strcmp(argv[i], "--no-fresh")) cfg.freshFull = false;
    else if (!strcmp(argv[i], "--endlag") && i + 1 < argc) cfg.endLag = atof(argv[++i]);
    else if (!strcmp(argv[i], "--release") && i + 1 < argc) cfg.release = atof(argv[++i]);
    else if (!strcmp(argv[i], "--susev") && i + 1 < argc) cfg.susEvidence = atof(argv[++i]);
    else if (!strcmp(argv[i], "--susk") && i + 1 < argc) cfg.susK = atof(argv[++i]);
    else if (!strcmp(argv[i], "--sushold") && i + 1 < argc) cfg.susHold = atof(argv[++i]);
    else if (!strcmp(argv[i], "--no-hand-motion")) cfg.handMotion = false;
    else if (!strcmp(argv[i], "--octratio") && i + 1 < argc) cfg.octRatio = atof(argv[++i]);
    else if (!strcmp(argv[i], "--octmono") && i + 1 < argc) cfg.octRatioMono = atof(argv[++i]);
    else if (!strcmp(argv[i], "--extra") && i + 1 < argc) cfg.chord.extraPenalty = (float)atof(argv[++i]);
    else if (!strcmp(argv[i], "--miss") && i + 1 < argc) cfg.chord.missPenalty = (float)atof(argv[++i]);
    else if (!strcmp(argv[i], "--bass") && i + 1 < argc) cfg.chord.bassBonus = (float)atof(argv[++i]);
    else if (!strcmp(argv[i], "--size") && i + 1 < argc) cfg.chord.sizePenalty = (float)atof(argv[++i]);
    else if (!strcmp(argv[i], "--presence") && i + 1 < argc) cfg.chord.presence = (float)atof(argv[++i]);
  }
  double jt0 = -1, jt1 = -1, jh1 = -1;
  for (int i = 4; i + 1 < argc; ++i) { if (!strcmp(argv[i], "--jh1")) jh1 = atof(argv[i + 1]); if (!strcmp(argv[i], "--jt0")) jt0 = atof(argv[i + 1]); if (!strcmp(argv[i], "--jt1")) jt1 = atof(argv[i + 1]); }
  std::vector<float> x;
  int fs = 44100;
  if (!wavio::read16(argv[2], x, fs)) { fprintf(stderr, "nie można wczytać %s\n", argv[2]); return 1; }
  const auto t0 = std::chrono::steady_clock::now();
  Engine eng;
  eng.configure(cfg);
  eng.begin(fs);
  if (getenv("GT_DUMP")) eng.dumpFile_ = fopen(getenv("GT_DUMP"), "wb");
  if (jt0 >= 0) eng.dbgPitch().jointTol0_ = jt0;
  if (jt1 >= 0) eng.dbgPitch().jointTol1_ = jt1;
  if (jh1 >= 0) eng.dbgPitch().jointH1_ = jh1;
  if (!live) eng.prepass(x.data(), x.size());
  const size_t chunk = live ? 1024 : 8192;
  for (size_t i = 0; i < x.size(); i += chunk) eng.push(x.data() + i, (int)std::min(chunk, x.size() - i));
  eng.finish();
  if (eng.dumpFile_) fclose(eng.dumpFile_);
  const double ms = std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - t0).count();

  FILE* f = fopen(argv[3], "w");
  fprintf(f, "{\"engine\":\"cpp\",\"handRejected\":%ld,\"cpuMs\":%.2f,\"audioSec\":%.3f,\"winSec\":%.4f,\"tuneCents\":%.2f,\"gate\":%.1f,\n\"frames\":[", eng.handRejected(), ms, x.size() / (double)fs,
          eng.winSec(), eng.tuneCents(), eng.gate());
  const auto& names = eng.chordNames();
  bool first = true;
  for (const auto& fr : eng.frames()) {
    fprintf(f, "%s{\"t\":%.3f,\"silent\":%s,\"chord\":", first ? "" : ",", fr.t, fr.silent ? "true" : "false");
    first = false;
    if (fr.chord >= 0) fprintf(f, "\"%s\"", names[fr.chord].c_str()); else fprintf(f, "null");
    fprintf(f, ",\"notes\":[");
    bool fn = true;
    for (int i = 0; i < fr.nNotes; ++i) {
      if (!fr.notes[i].stable) continue;
      fprintf(f, "%s%d", fn ? "" : ",", fr.notes[i].midi);
      fn = false;
    }
    fprintf(f, "],\"tuner\":");
    if (fr.tunerOk) fprintf(f, "{\"midi\":%d,\"f\":%.4f,\"cents\":%.2f}", fr.tMidi, fr.tF, fr.tCentsSm); else fprintf(f, "null");
    fprintf(f, "}");
  }
  fprintf(f, "],\n\"chordLog\":[");
  first = true;
  for (const auto& c : eng.chordLog()) { fprintf(f, "%s{\"t\":%.3f,\"name\":\"%s\"}", first ? "" : ",", c.t, c.name.c_str()); first = false; }
  fprintf(f, "],\n\"notes\":[");
  first = true;
  for (const auto& e : eng.events()) { fprintf(f, "%s{\"midi\":%d,\"t0\":%.3f,\"t1\":%.3f}", first ? "" : ",", e.midi, e.t0, e.t1); first = false; }
  fprintf(f, "],\n\"onsets\":[");
  first = true;
  for (double o : eng.onsets()) { fprintf(f, "%s%.3f", first ? "" : ",", o); first = false; }
  fprintf(f, "]}\n");
  fclose(f);
  return 0;
}
