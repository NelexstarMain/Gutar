#!/usr/bin/env python3
"""train_mask.py - uczy model maski (gt_mask.hpp): jaka część energii pasma to gitara. Zapisuje wagi do src/gt_maskmodel.hpp.

Dane: nagrania z tools/gen_env (<id>.wav = mikrofon, <id>.clean.wav = sama gitara) i zrzuty cech pasm z silnika:
  GT_DUMPM=zrzuty/<id>.bin gt_cli analyze <id>.wav wynik.json
Wiersz zrzutu: [czas środka okna, pasmo, 15 cech]. Etykieta: idealna maska Ec / (Ec + En) w tym paśmie i tej klatce, liczona z czystej
gitary i szumu (mikrofon - gitara) tym samym oknem co silnik (decymacja do 11025 Hz, Hann 4096, FFT 16384).

Użycie: train_mask.py --train <katalog_env> <zrzuty> --test <katalog_env> <zrzuty> [--out src/gt_maskmodel.hpp]
"""
import os, sys, glob, argparse, wave
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
from train_model import MLP

NF, NB, MIDI0 = 15, 156, 33
FSD, WIN, NFFT = 11025.0, 4096, 16384


def read_wav(p):
    w = wave.open(p); x = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float64) / 32768; fs = w.getframerate(); w.close()
    return x, fs


def decimate(x, fs):
    D = max(1, int(round(fs / 11025.0)))
    if D == 1:
        return x
    T = 12 * D + 1; fc = 0.42 / D; mid = (T - 1) / 2; i = np.arange(T); xx = i - mid
    s = np.where(xx == 0, 2 * fc, np.sin(2 * np.pi * fc * xx) / (np.pi * np.where(xx == 0, 1, xx)))
    w = 0.42 - 0.5 * np.cos(2 * np.pi * i / (T - 1)) + 0.08 * np.cos(4 * np.pi * i / (T - 1))
    h = s * w; h /= h.sum()
    return np.convolve(x, h)[T - 1::D][:len(x) // D]


def band_bins():
    bh = FSD / NFFT
    out = []
    for b in range(NB):
        fc = 440.0 * 2 ** ((MIDI0 + b / 2 - 69) / 12)
        k0 = max(1, int(np.floor(fc * 2 ** (-1 / 48) / bh))); k1 = max(k0, int(np.ceil(fc * 2 ** (1 / 48) / bh)))
        out.append((k0, k1))
    return out


BANDS = band_bins()
HANN = 0.5 - 0.5 * np.cos(2 * np.pi * np.arange(WIN) / WIN)


def band_energy(seg):
    m = np.abs(np.fft.rfft((seg - seg.mean()) * HANN, NFFT))
    return np.array([np.mean(m[a:b + 1] ** 2) for a, b in BANDS])


def load(env_dir, dump_dir, keep=0.35, seed=0):
    rng = np.random.default_rng(seed)
    X, Y = [], []
    for dp in sorted(glob.glob(os.path.join(dump_dir, '*.bin'))):
        name = os.path.splitext(os.path.basename(dp))[0]
        rows = np.fromfile(dp, np.float32).reshape(-1, 2 + NF)
        if keep < 1:
            rows = rows[rng.random(len(rows)) < keep]
        mix, fs = read_wav(os.path.join(env_dir, name + '.wav')); cln, _ = read_wav(os.path.join(env_dir, name + '.clean.wav'))
        dm, dc = decimate(mix, fs), decimate(cln, fs)
        dn = dm - dc
        cache = {}
        y = np.zeros(len(rows), np.float32)
        for i, (t, b) in enumerate(rows[:, :2]):
            key = round(float(t), 4)
            if key not in cache:
                nd = int(round((t + 0.5 * WIN / FSD) * FSD))
                if nd < WIN or nd > len(dm):
                    cache[key] = None
                else:
                    cache[key] = (band_energy(dc[nd - WIN:nd]), band_energy(dn[nd - WIN:nd]))
            e = cache[key]
            if e is None:
                y[i] = -1; continue
            ec, en = e[0][int(b)], e[1][int(b)]
            y[i] = ec / (ec + en + 1e-20)
        ok = y >= 0
        X.append(rows[ok, 2:]); Y.append(y[ok])
    return np.concatenate(X), np.concatenate(Y)


def export(model, path, info):
    def arr(name, a):
        return 'static const float %s[%d] = {%s};\n' % (name, a.size, ', '.join('%.7gf' % v for v in a.ravel()))
    sizes = [model.W[0].shape[0]] + [W.shape[1] for W in model.W]
    s = ('// gt_maskmodel.hpp - wagi modelu maski. WYGENEROWANE przez tools/train_mask.py, nie edytować.\n// ' + info +
         '\n#pragma once\n#include <cmath>\nnamespace gt {\nstatic constexpr bool kMaskReady = true;\n')
    for i, (W, b) in enumerate(zip(model.W, model.b)):
        s += arr('kMW%d' % i, W) + arr('kMB%d' % i, b)
    s += 'inline float maskPredict(const float* x) {\n'
    prev = 'x'
    for i in range(len(model.W)):
        a, b = sizes[i], sizes[i + 1]; last = i == len(model.W) - 1
        s += '  float h%d[%d];\n  for (int j = 0; j < %d; ++j) { float z = kMB%d[j]; for (int i = 0; i < %d; ++i) z += %s[i] * kMW%d[i * %d + j]; h%d[j] = %s; }\n' % (
            i, b, b, i, a, prev, i, b, i, 'z' if last else 'z > 0 ? z : 0')
        prev = 'h%d' % i
    s += '  const float z = %s[0] < -30 ? -30 : (%s[0] > 30 ? 30 : %s[0]);\n  return 1.f / (1.f + std::exp(-z));\n}\n} // namespace gt\n' % (prev, prev, prev)
    open(path, 'w').write(s)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--train', nargs=2, required=True); ap.add_argument('--test', nargs=2, required=True)
    ap.add_argument('--out', default=os.path.join(os.path.dirname(__file__), '..', 'src', 'gt_maskmodel.hpp'))
    ap.add_argument('--epochs', type=int, default=8); ap.add_argument('--hidden', default='24,12')
    a = ap.parse_args()
    Xtr, Ytr = load(*a.train); Xte, Yte = load(*a.test, keep=0.25, seed=5)
    print('uczące %d, testowe %d; średnia maska %.3f' % (len(Xtr), len(Xte), Ytr.mean()))
    rng = np.random.default_rng(3)
    model = MLP([NF] + [int(h) for h in a.hidden.split(',')] + [1], rng)
    w = np.ones(len(Xtr), np.float32)
    for ep in range(a.epochs):
        idx = rng.permutation(len(Xtr)); lr = 2e-3 if ep < a.epochs * 0.6 else 5e-4
        for i in range(0, len(idx), 4096):
            j = idx[i:i + 4096]; model.step(Xtr[j], Ytr[j], w[j] * len(Xtr), lr)
        p = model.predict(Xte)
        print('epoka %d  test: błąd bezwzględny %.4f  (stała 0,5: %.4f)  zgodność decyzji gitara/szum (próg 0,5) %.3f' % (
            ep, np.abs(p - Yte).mean(), np.abs(0.5 - Yte).mean(), np.mean((p >= 0.5) == (Yte >= 0.5))))
    # bez modelu (maska = 1): ile pasm z przewagą szumu przepuszczamy
    print('pasma z przewagą otoczenia (idealna maska < 0,3): %.1f %%; model wycina z nich %.1f %%, a z pasm gitary (> 0,7) wycina %.1f %%' % (
        100 * np.mean(Yte < 0.3), 100 * np.mean(p[Yte < 0.3] < 0.3), 100 * np.mean(p[Yte > 0.7] < 0.3)))
    export(model, a.out, 'test: błąd %.4f, zgodność %.3f' % (np.abs(p - Yte).mean(), np.mean((p >= 0.5) == (Yte >= 0.5))))
    print('zapisano', a.out)


if __name__ == '__main__':
    main()
