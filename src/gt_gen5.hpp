// gt_gen5.hpp - model gen 5: konwolucyjna sieć na harmonicznie ułożonym widmie (gt_hcqt.hpp), wagi w gt_gen5model.hpp
// (tools/train_gen5.py). Dla każdej klatki i półtonu MIDI 36..88 zwraca p(nuta brzmi) i p(nuta zaczyna się), a dekoder składa z tego
// nuty (por. Onsets and Frames, Hawthorne i in. 2018; Basic Pitch, Bittner i in. 2022). Działa na całym nagraniu (kontekst przed i po).
#pragma once
#include "gt_hcqt.hpp"
#include "gt_tracker.hpp"
#include "gt_gen5model.hpp"

namespace gt {

class Gen5 {
public:
  static constexpr int S = Hcqt::kSemis, P = Hcqt::P, C = Hcqt::C;
  std::vector<float> frame, onset; // T x S
  int T = 0;

  // wejście: in[ci][t][p] (Cin x Tc x Pin); wyjście out[co][t][q] (Cout x Tc x Pout); wagi PyTorch [co][ci][kt][kp]
  static void conv(const std::vector<float>& in, int Cin, int Tc, int Pin, std::vector<float>& out, int Cout, int Pout,
                   int kt, int kp, int pt, int pp, int dp, int sp, const float* w, const float* b, bool relu, const std::vector<float>* res) {
    out.assign((size_t)Cout * Tc * Pout, 0.f);
    for (int co = 0; co < Cout; ++co) {
      float* o = &out[(size_t)co * Tc * Pout];
      for (size_t i = 0; i < (size_t)Tc * Pout; ++i) o[i] = b[co];
      for (int ci = 0; ci < Cin; ++ci)
        for (int dt = 0; dt < kt; ++dt)
          for (int dk = 0; dk < kp; ++dk) {
            const float wv = w[((co * Cin + ci) * kt + dt) * kp + dk];
            const int off = dk * dp - pp;
            for (int t = 0; t < Tc; ++t) {
              const int ti = t + dt - pt;
              if (ti < 0 || ti >= Tc) continue;
              const float* x = &in[((size_t)ci * Tc + ti) * Pin];
              float* y = &o[(size_t)t * Pout];
              int q0 = 0, q1 = Pout;
              // q * sp + off w [0, Pin)
              while (q0 < q1 && q0 * sp + off < 0) ++q0;
              while (q1 > q0 && (q1 - 1) * sp + off >= Pin) --q1;
              if (sp == 1) for (int q = q0; q < q1; ++q) y[q] += wv * x[q + off];
              else for (int q = q0; q < q1; ++q) y[q] += wv * x[q * sp + off];
            }
          }
      if (relu || res) {
        const float* r = res ? &(*res)[(size_t)co * Tc * Pout] : nullptr;
        for (size_t i = 0; i < (size_t)Tc * Pout; ++i) { float v = o[i]; if (relu && v < 0) v = 0; o[i] = r ? r[i] + v : v; }
      }
    }
  }

  void run(const Hcqt& h) {
    T = h.T;
    frame.assign((size_t)T * S, 0.f); onset.assign((size_t)T * S, 0.f);
    if (!kGen5Ready || !T) return;
    const int H = kGen5H, CH = 256, HALO = kGen5Attn ? 32 : 6; // uwaga patrzy 21 klatek wstecz
    std::vector<float> x, a, b2;
    for (int c0 = 0; c0 < T; c0 += CH) {
      const int lo = std::max(0, c0 - HALO), hi = std::min(T, c0 + CH + HALO), Tc = hi - lo;
      x.assign((size_t)C * Tc * P, 0.f);
      for (int t = 0; t < Tc; ++t)
        for (int c = 0; c < C; ++c)
          for (int p = 0; p < P; ++p) x[((size_t)c * Tc + t) * P + p] = h.at(lo + t, c, p);
      conv(x, C, Tc, P, a, H, P, 3, 7, 1, 3, 1, 1, kG5_c1_w, kG5_c1_b, true, nullptr);
      conv(a, H, Tc, P, b2, H, P, 3, 7, 1, 3, 1, 1, kG5_c2_w, kG5_c2_b, true, &a);
      conv(b2, H, Tc, P, a, H, P, 5, 3, 2, 1, 1, 1, kG5_c3_w, kG5_c3_b, true, &b2);
      conv(a, H, Tc, P, b2, H, P, 1, 3, 0, 36, 36, 1, kG5_c4_w, kG5_c4_b, true, &a);
      conv(b2, H, Tc, P, a, H, P, 3, 3, 1, 1, 1, 1, kG5_c5_w, kG5_c5_b, true, &b2);
      if (kGen5Attn) attention(a, Tc);
      conv(a, H, Tc, P, b2, 2, S, 1, 3, 0, 0, 1, 3, kG5_out_w, kG5_out_b, false, nullptr);
      for (int t = c0; t < std::min(T, c0 + CH); ++t)
        for (int s = 0; s < S; ++s) {
          const int tt = t - lo;
          frame[(size_t)t * S + s] = 1.f / (1.f + std::exp(-b2[((size_t)0 * Tc + tt) * S + s]));
          onset[(size_t)t * S + s] = 1.f / (1.f + std::exp(-b2[((size_t)1 * Tc + tt) * S + s]));
        }
    }
  }

  // Blok uwagi (jak w transformerze, tools/train_gen5.py TimeAttention): dla każdej wysokości p klatka t patrzy na klatki
  // t-W+1..t tej samej wysokości; kGen5Heads głów, wyuczona premia za odległość; h += o(uwaga); h += f2(relu(f1(h))).
  static void attention(std::vector<float>& h, int Tc) {
    const int H = kGen5H, W = kGen5W, NH = kGen5Heads, DH = H / NH;
    std::vector<float> qkv, att((size_t)H * Tc * P, 0.f), tmp, f;
    conv(h, H, Tc, P, qkv, 3 * H, P, 1, 1, 0, 0, 1, 1, kG5_att_qkv_w, kG5_att_qkv_b, false, nullptr);
    const float sc = 1.f / std::sqrt((float)DH);
    std::vector<float> w(W);
    for (int hd = 0; hd < NH; ++hd)
      for (int t = 0; t < Tc; ++t) {
        const int s0 = std::max(0, t - W + 1);
        for (int p = 0; p < P; ++p) {
          float mx = -1e30f;
          for (int s = s0; s <= t; ++s) {
            float d = 0;
            for (int k = 0; k < DH; ++k) {
              const int c = hd * DH + k;
              d += qkv[((size_t)c * Tc + t) * P + p] * qkv[((size_t)(H + c) * Tc + s) * P + p];
            }
            d = d * sc + kG5_att_rel[hd * W + (t - s)];
            w[s - s0] = d; mx = std::max(mx, d);
          }
          float sum = 0;
          for (int s = s0; s <= t; ++s) { w[s - s0] = std::exp(w[s - s0] - mx); sum += w[s - s0]; }
          for (int k = 0; k < DH; ++k) {
            const int c = hd * DH + k;
            float acc = 0;
            for (int s = s0; s <= t; ++s) acc += w[s - s0] * qkv[((size_t)(2 * H + c) * Tc + s) * P + p];
            att[((size_t)c * Tc + t) * P + p] = acc / sum;
          }
        }
      }
    conv(att, H, Tc, P, tmp, H, P, 1, 1, 0, 0, 1, 1, kG5_att_o_w, kG5_att_o_b, false, &h);   // h + o(uwaga)
    conv(tmp, H, Tc, P, f, 2 * H, P, 1, 1, 0, 0, 1, 1, kG5_att_f1_w, kG5_att_f1_b, true, nullptr);
    conv(f, 2 * H, Tc, P, h, H, P, 1, 1, 0, 0, 1, 1, kG5_att_f2_w, kG5_att_f2_b, false, &tmp); // + f2(relu(f1))
  }

  float fr(int t, int s) const { return frame[(size_t)t * S + s]; }
  float on(int t, int s) const { return onset[(size_t)t * S + s]; }

  struct DecodeOpt { double thOn = 0.5, thFr = 0.5, thStart = 0.7; int minFrames = 2; };

  // nuty z map: początek w lokalnym maksimum p(początek) >= thOn (albo bez początku, gdy p(brzmi) >= thStart przez 2 klatki),
  // koniec, gdy p(brzmi) < thFr dłużej niż 1 klatkę; nowy początek w trakcie nuty = ponowne szarpnięcie
  void decode(const Hcqt& h, double fsd, double a4, const DecodeOpt& o, std::vector<NoteEvent2>& out) const {
    out.clear();
    auto cen = [&](int t) { return Hcqt::frameCenter(t, fsd); };
    for (int s = 0; s < S; ++s) {
      int start = -1, last = -1, gap = 0;
      double conf = 0; int nconf = 0;
      auto finish = [&](int endT) {
        if (start < 0) return;
        if (last - start + 1 >= o.minFrames) {
          NoteEvent2 e;
          e.midi = Hcqt::kMidi0 + s;
          e.t0 = std::max(0.0, cen(start));
          e.t1 = std::max(e.t0 + 0.06, cen(last) + 0.5 * Hcqt::kHop / fsd);
          float amp = 0;
          for (int t = start; t <= std::min(endT, start + 3) && t < T; ++t) amp = std::max(amp, h.at(t, 1, 3 * s + 1));
          e.vel = (int)clampd(30 + 90 * amp, 20, 127);
          e.f = (float)midiFreq(e.midi, a4);
          e.conf = nconf ? (float)(conf / nconf) : 0.5f;
          out.push_back(e);
        }
        start = -1; gap = 0; conf = 0; nconf = 0;
      };
      for (int t = 0; t < T; ++t) {
        const float f = fr(t, s), on_ = on(t, s);
        const bool peak = on_ >= o.thOn && (t == 0 || on_ >= on(t - 1, s)) && (t + 1 >= T || on_ > on(t + 1, s));
        if (peak && f >= 0.3f) {
          if (start >= 0) finish(t - 1);
          start = t; last = t; gap = 0;
        } else if (start < 0 && f >= o.thStart && t + 1 < T && fr(t + 1, s) >= o.thStart) {
          start = t; last = t; gap = 0;
        }
        if (start >= 0) {
          if (f >= o.thFr) { last = t; gap = 0; conf += f; ++nconf; }
          else if (++gap > 1) finish(t);
        }
      }
      finish(T - 1);
    }
    std::sort(out.begin(), out.end(), [](const NoteEvent2& a, const NoteEvent2& b) { return a.t0 < b.t0 || (a.t0 == b.t0 && (a.midi < b.midi || (a.midi == b.midi && a.t1 < b.t1))); });
  }
};

} // namespace gt
