#!/usr/bin/env python3
"""train_model.py - uczy model oceniający kandydatów na nuty i zapisuje wagi do src/gt_model.hpp.

Dane: zrzuty cech z silnika (GT_DUMP=plik.bin gt_cli analyze nagranie.wav wynik.json), po jednym pliku .bin na nagranie;
wiersz = [czas środka okna, midi, 44 cechy] (float32). Etykieta: czy ta wysokość brzmi w tej chwili według prawdy
(korpus syntetyczny: *.truth.json; GuitarSet: *.jams). Klatki bliżej niż 60 ms od początku i 100 ms od końca nuty są pomijane
(niejednoznaczne: okno analizy zachodzi na granicę).

Użycie:
  train_model.py --syn <zrzuty> <prawda> --gs <zrzuty> <adnotacje_jams> --val-gs '02_' [--out src/gt_model.hpp]

  Plik prawdy szukany jest pod nazwą zrzutu (np. zrzut dev_strum_clean_00.bin -> dev_strum_clean_00.truth.json); zrzuty z trybu
  na żywo mają przedrostek "L_" (GuitarSet) albo "<zbiór>L_" (korpus) i trzeba im podlinkować tę samą prawdę.

Model: sieć 44 -> 64 -> 32 -> 1 (--hidden) (ReLU, sigmoid), Adam, entropia krzyżowa; każde źródło (korpus, GuitarSet) waży tyle samo.
Próg decyzji dobierany na zbiorze walidacyjnym (maksimum F1 obecności nut w klatkach).
"""
import sys, os, glob, json, argparse, zlib
import numpy as np

NF = 44


def load_truth_syn(path):
    t = json.load(open(path))
    return [(n['midi'], n['t0'], min(n['t1'], n.get('ta', n['t1']))) for n in t['notes']]


def load_truth_jams(path):
    j = json.load(open(path))
    out = []
    for a in j['annotations']:
        if a['namespace'] == 'note_midi':
            for d in a['data']:
                out.append((int(round(d['value'])), d['time'], d['time'] + d['duration']))
    return out


def label(rows, notes):
    t, m = rows[:, 0], rows[:, 1].astype(int)
    y = np.zeros(len(rows), np.float32)
    amb = np.zeros(len(rows), bool)
    by = {}
    for mi, a, b in notes:
        by.setdefault(mi, []).append((a, b))
    for i in range(len(rows)):
        for a, b in by.get(m[i], ()):
            if a - 0.06 <= t[i] <= b + 0.10:
                if t[i] < a + 0.06 or t[i] > b - 0.10:
                    amb[i] = True
                else:
                    y[i] = 1
                    amb[i] = False
                    break
    return y, ~amb


def base_name(name):
    # ten sam plik w trybie pliku i na żywo (przedrostek "L_" albo "<zbiór>L_") ląduje po tej samej stronie podziału
    head, _, rest = name.partition('_')
    if head == 'L':
        return rest
    if head.endswith('L') and rest:
        return head[:-1] + '_' + rest
    return name


def load_set(dump_dir, truth_dir, kind, pattern='*'):
    X, Y, F = [], [], []
    for bp in sorted(glob.glob(os.path.join(dump_dir, pattern + '.bin'))):
        name = os.path.splitext(os.path.basename(bp))[0]
        tp = os.path.join(truth_dir, name + ('.truth.json' if kind == 'syn' else '.jams'))
        if not os.path.exists(tp):
            continue
        rows = np.fromfile(bp, np.float32).reshape(-1, 2 + NF)
        notes = load_truth_syn(tp) if kind == 'syn' else load_truth_jams(tp)
        y, keep = label(rows, notes)
        X.append(rows[keep, 2:]); Y.append(y[keep]); F += [base_name(name)] * int(keep.sum())
    return np.concatenate(X), np.concatenate(Y), np.array(F)


class MLP:
    def __init__(self, sizes, rng):
        self.W = [rng.normal(0, np.sqrt(2 / a), (a, b)).astype(np.float32) for a, b in zip(sizes, sizes[1:])]
        self.b = [np.zeros(b, np.float32) for b in sizes[1:]]
        self.m = [np.zeros_like(p) for p in self.W + self.b]; self.v = [np.zeros_like(p) for p in self.W + self.b]; self.k = 0

    def forward(self, x):
        hs = [x]
        for i, (W, b) in enumerate(zip(self.W, self.b)):
            z = hs[-1] @ W + b
            hs.append(np.maximum(z, 0) if i < len(self.W) - 1 else z)
        return hs

    def predict(self, x):
        z = self.forward(x)[-1][:, 0]
        return 1 / (1 + np.exp(-np.clip(z, -30, 30)))

    def step(self, x, y, w, lr):
        hs = self.forward(x)
        p = 1 / (1 + np.exp(-np.clip(hs[-1][:, 0], -30, 30)))
        g = ((p - y) * w / w.sum())[:, None].astype(np.float32)
        gW, gb = [], []
        for i in range(len(self.W) - 1, -1, -1):
            gW.insert(0, hs[i].T @ g); gb.insert(0, g.sum(0))
            if i > 0:
                g = (g @ self.W[i].T) * (hs[i] > 0)
        self.k += 1
        for j, (p_, g_) in enumerate(zip(self.W + self.b, gW + gb)):
            self.m[j] = 0.9 * self.m[j] + 0.1 * g_
            self.v[j] = 0.999 * self.v[j] + 0.001 * g_ * g_
            mh = self.m[j] / (1 - 0.9 ** self.k); vh = self.v[j] / (1 - 0.999 ** self.k)
            p_ -= lr * mh / (np.sqrt(vh) + 1e-8)


class Ensemble:
    def __init__(self, models): self.models = models
    def predict(self, x): return np.mean([m.predict(x) for m in self.models], axis=0)


def f1_at(p, y, thr):
    tp = np.sum((p >= thr) & (y > 0)); fp = np.sum((p >= thr) & (y == 0)); fn = np.sum((p < thr) & (y > 0))
    return 2 * tp / max(1, 2 * tp + fp + fn), tp / max(1, tp + fp), tp / max(1, tp + fn)


def export(model, thr, path, info):
    def arr(name, a):
        return 'static const float %s[%d] = {%s};\n' % (name, a.size, ', '.join('%.7gf' % v for v in a.ravel()))
    models = model.models if isinstance(model, Ensemble) else [model]
    s = ('// gt_model.hpp - wagi modelu oceniającego kandydatów na nuty. WYGENEROWANE przez tools/train_model.py, nie edytować.\n'
         '// ' + info + '\n#pragma once\n#include <cmath>\nnamespace gt {\nstatic constexpr bool kModelReady = true;\n'
         'static constexpr float kModelThr = %.4ff;\n' % thr)
    body = ''
    for m_i, m in enumerate(models):
        sizes = [m.W[0].shape[0]] + [W.shape[1] for W in m.W]
        for i, (W, b) in enumerate(zip(m.W, m.b)):
            s += arr('kW%d_%d' % (m_i, i), W) + arr('kB%d_%d' % (m_i, i), b)
        body += '  {\n'
        prev = 'x'
        for i in range(len(m.W)):
            a, b = sizes[i], sizes[i + 1]; last = i == len(m.W) - 1
            body += '    float h%d[%d];\n    for (int j = 0; j < %d; ++j) { float z = kB%d_%d[j]; for (int i = 0; i < %d; ++i) z += %s[i] * kW%d_%d[i * %d + j]; h%d[j] = %s; }\n' % (
                i, b, b, m_i, i, a, prev, m_i, i, b, i, 'z' if last else 'z > 0 ? z : 0')
            prev = 'h%d' % i
        body += '    const float z = %s[0] < -30 ? -30 : (%s[0] > 30 ? 30 : %s[0]);\n    sum += 1.f / (1.f + std::exp(-z));\n  }\n' % (prev, prev, prev)
    s += 'inline float modelPredict(const float* x) {\n  float sum = 0;\n' + body + '  return sum / %d.f;\n}\n} // namespace gt\n' % len(models)
    open(path, 'w').write(s)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--syn', nargs=2); ap.add_argument('--gs', nargs=2); ap.add_argument('--val-gs', default='02_')
    ap.add_argument('--out', default=os.path.join(os.path.dirname(__file__), '..', 'src', 'gt_model.hpp'))
    ap.add_argument('--epochs', type=int, default=12); ap.add_argument('--seed', type=int, default=1)
    ap.add_argument('--weights', default='', help='np. korpus=0.25,środowiska=0.25,GuitarSet=0.5')
    ap.add_argument('--ensemble', type=int, default=1, help='ile sieci (różne ziarna), wynik = średnia')
    ap.add_argument('--drop', default='', help='zakres cech zerowanych przy uczeniu, np. 32-39 (test wpływu)')
    ap.add_argument('--hidden', default='64,32'); ap.add_argument('--env', nargs=2, help='zrzuty i katalog tools/gen_env')
    a = ap.parse_args()
    rng = np.random.default_rng(a.seed)
    parts = []
    if a.syn:
        X, Y, F = load_set(a.syn[0], a.syn[1], 'syn')
        val = np.array([zlib.crc32(f.encode()) % 5 == 0 for f in F])
        parts.append(('korpus', X, Y, val))
    if a.env:
        X, Y, F = load_set(a.env[0], a.env[1], 'syn')
        val = np.array([zlib.crc32(f.encode()) % 5 == 0 for f in F])
        parts.append(('środowiska', X, Y, val))
    if a.gs:
        X, Y, F = load_set(a.gs[0], a.gs[1], 'gs')
        val = np.array([f.startswith(a.val_gs) for f in F])
        parts.append(('GuitarSet', X, Y, val))
    if a.drop:
        lo, hi = (int(x) for x in a.drop.split('-'))
        for _, X, Y, v in parts: X[:, lo:hi + 1] = 0
    Xtr = np.concatenate([X[~v] for _, X, Y, v in parts]); Ytr = np.concatenate([Y[~v] for _, X, Y, v in parts])
    sw = {k: float(x) for k, x in (kv.split('=') for kv in a.weights.split(','))} if a.weights else {}
    Wtr = np.concatenate([np.full((~v).sum(), sw.get(name, 1.0) / (~v).sum(), np.float32) for name, X, Y, v in parts])
    for name, X, Y, v in parts:
        print('%-10s wierszy %8d  (walidacja %d)  dodatnich %.1f %%' % (name, len(X), v.sum(), 100 * Y.mean()))
    models = []
    for k in range(a.ensemble):
        rng = np.random.default_rng(a.seed + 101 * k)
        model = MLP([NF] + [int(h) for h in a.hidden.split(',')] + [1], rng)
        n, bs = len(Xtr), 4096
        for ep in range(a.epochs):
            idx = rng.permutation(n)
            lr = 2e-3 if ep < a.epochs * 0.6 else 5e-4
            for i in range(0, n, bs):
                j = idx[i:i + bs]
                model.step(Xtr[j], Ytr[j], Wtr[j] * n, lr)
        models.append(model)
        print('sieć %d: ' % k + '  '.join('%s F1 %.3f' % (name, f1_at(model.predict(X[v]), Y[v], 0.5)[0]) for name, X, Y, v in parts))
    model = Ensemble(models)
    # próg: maksimum średniego F1 na walidacji obu źródeł
    best = (0, 0.5)
    for thr in np.arange(0.2, 0.81, 0.025):
        f = np.mean([f1_at(model.predict(X[v]), Y[v], thr)[0] for _, X, Y, v in parts])
        if f > best[0]: best = (f, thr)
    thr = float(best[1])
    info = []
    for name, X, Y, v in parts:
        p = model.predict(X[v]); f, pr, rc = f1_at(p, Y[v], thr)
        # odniesienie: decyzja detektora zachłannego (cecha 18)
        fg, pg, rg = f1_at(X[v][:, 18], Y[v], 0.5)
        print('%-10s walidacja: model F1 %.3f (P %.3f R %.3f) | detektor zachłanny F1 %.3f (P %.3f R %.3f)' % (name, f, pr, rc, fg, pg, rg))
        info.append('%s: F1 kandydatów %.3f (detektor zachłanny %.3f)' % (name, f, fg))
    print('próg', thr)
    export(model, thr, a.out, 'próg %.3f; walidacja: ' % thr + '; '.join(info))
    print('zapisano', a.out)


if __name__ == '__main__':
    main()
