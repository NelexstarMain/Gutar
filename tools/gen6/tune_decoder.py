#!/usr/bin/env python3
"""tune_decoder.py - strojenie progów dekodera na walidacji i sprawdzenie na teście.

  python3 -m tools.gen6.tune_decoder --config cfg.json --ckpt best.pt --out wynik/ [--max-val 150,60] [--passes 2] [--procs 4]

1. Sieć liczy mapy (początek / brzmi / koniec / tabulatura) raz dla każdego nagrania walidacyjnego (stała, równomierna próbka ze źródeł).
2. Przeszukiwanie współrzędnych (po kolei każdy parametr dekodera, wartości z siatki, kilka przebiegów): cel = średnia po źródłach
   z makro-średniej (F1 nut + F1 nut z końcem) / 2, wagi źródeł GuitarSet 0,4, klasyka 0,4, środowiska 0,2.
3. Zbiór testowy (nigdy nie używany do strojenia): wszystkie miary dla progów domyślnych i dostrojonych, sparowany bootstrap różnicy.
Wynik: <out>/decode.json (progi + historia prób), <out>/test_domyslne.json, <out>/test_dostrojone.json; decode.json skopiowany obok
best.pt przy serwerze jest czytany automatycznie (decode.apply_decode_override).
"""
from __future__ import annotations
import argparse
import dataclasses as dc
import json
import multiprocessing as mp
import os
import time
import numpy as np
from . import metrics as M
from .config import Config, DecodeConfig
from .data import example_features, load_sources
from .decode import apply_decode_override, decode_notes
from .evaluate import evaluate_example, report

WEIGHTS = {'GuitarSet': 0.4, 'klasyka': 0.4, 'srodowiska': 0.2}
GRID = [('th_onset', [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]), ('th_onset_frame', [0.1, 0.2, 0.3, 0.4, 0.5]),
        ('th_frame', [0.3, 0.4, 0.5, 0.6, 0.7]), ('th_offset', [0.3, 0.4, 0.5, 0.6, 0.7, 0.8]),
        ('th_start', [0.5, 0.6, 0.7, 0.8, 0.9, 1.01]), ('min_frames', [1, 2, 3, 4]), ('gap_frames', [0, 1, 2, 3]),
        ('merge_sec', [0.02, 0.03, 0.05, 0.08]), ('min_dur', [0.03, 0.06, 0.1, 0.15])]
_ITEMS = []   # (ex, probs, T) - dziedziczone przez fork, bez kopiowania map do procesów


def pick(exs, split, caps):
    """Równomiernie rozłożona stała próba: caps = {źródło: najwyżej tyle nagrań}."""
    out = []
    for s in sorted({e.source for e in exs}):
        g = [e for e in exs if e.split == split and e.source == s]
        cap = caps.get(s, caps.get('*', len(g)))
        if len(g) > cap:
            g = [g[i] for i in np.linspace(0, len(g) - 1, cap).round().astype(int)]
        out += g
    return out


def collect(net, cfg, exs, log=print):
    items, t0 = [], time.time()
    for k, ex in enumerate(exs):
        X = np.asarray(example_features(ex, cfg.features, None, fp16=cfg.train.cache_fp16, mmap=True), np.float32)
        if not len(X):
            continue
        items.append((ex, net.predict(X), len(X)))
        if (k + 1) % 25 == 0 or k + 1 == len(exs):
            log('mapy %d/%d (%.0f s)' % (k + 1, len(exs), time.time() - t0))
    return items


def _one(args):
    i, dec = args
    ex, p, _ = _ITEMS[i]
    d = DecodeConfig(**dec)
    est = decode_notes(p, _CFG.features, d, _CFG.labels)
    on = M.note_prf(ex.notes, est, offset_ratio=None)['F1']
    off = M.note_prf(ex.notes, est, offset_ratio=0.2)['F1'] if 'offset' in ex.has else on
    return ex.source, on, off


def objective(pool, dec):
    res = pool.map(_one, [(i, dec) for i in range(len(_ITEMS))], chunksize=4)
    by = {}
    for s, on, off in res:
        by.setdefault(s, []).append((on + off) / 2)
    w = {s: WEIGHTS.get(s, 0.2) for s in by}
    tot = sum(w.values())
    return 100 * sum(w[s] * np.mean(v) for s, v in by.items()) / tot, {s: 100 * float(np.mean(v)) for s, v in by.items()}


def tune(cfg, net, val_items, passes=2, procs=4, log=print):
    global _ITEMS, _CFG
    _ITEMS, _CFG = val_items, cfg
    pool = mp.get_context('fork').Pool(procs)
    cur = dc.asdict(cfg.decode)
    best, per = objective(pool, cur)
    start = best
    log('start (progi domyślne): cel %.2f  %s' % (best, {k: round(v, 1) for k, v in per.items()}))
    hist = [{'param': None, 'value': None, 'objective': best}]
    for ps in range(passes):
        improved = False
        for name, vals in GRID:
            scores = {}
            for v in vals:
                if v == cur[name]:
                    scores[v] = best
                    continue
                trial = dict(cur, **{name: type(cur[name])(v)})
                scores[v], _ = objective(pool, trial)
                hist.append({'param': name, 'value': v, 'objective': scores[v], 'pass': ps})
            bv = max(scores, key=scores.get)
            if scores[bv] > best + 1e-6:
                log('przebieg %d: %s %s -> %s  cel %.2f -> %.2f' % (ps + 1, name, cur[name], bv, best, scores[bv]))
                cur[name], best, improved = type(cur[name])(bv), scores[bv], True
        if not improved:
            break
    best, per = objective(pool, cur)
    pool.close(); pool.join()
    log('koniec: cel %.2f (start %.2f)  %s' % (best, start, {k: round(v, 1) for k, v in per.items()}))
    return cur, start, best, per, hist


def _test_one(args):
    i, dec_default, dec_tuned = args
    ex, p, T = _ITEMS[i]
    out = []
    for dec in (dec_default, dec_tuned):
        est = decode_notes(p, _CFG.features, DecodeConfig(**dec), _CFG.labels)
        out.append(evaluate_example(ex, est, _CFG, None, T))
    return out


def test_compare(cfg, net, exs, dec_default, dec_tuned, out, procs=4, log=print):
    global _ITEMS, _CFG
    items = collect(net, cfg, exs, log)
    _ITEMS, _CFG = items, cfg
    with mp.get_context('fork').Pool(procs) as pool:
        res = pool.map(_test_one, [(i, dec_default, dec_tuned) for i in range(len(items))], chunksize=4)
    groups = [ex.source + ':' + (ex.group or '') for ex, _, _ in items]
    ids = [ex.id for ex, _, _ in items]
    cfg_d, cfg_t = Config.from_dict(cfg.to_dict()), Config.from_dict(cfg.to_dict())
    cfg_d.decode, cfg_t.decode = DecodeConfig(**dec_default), DecodeConfig(**dec_tuned)
    rows_d, rows_t = [r[0] for r in res], [r[1] for r in res]
    report(rows_d, groups, ids, cfg_d, os.path.join(out, 'test_domyslne.json'), title='dekoder domyślny, test')
    report(rows_t, groups, ids, cfg_t, os.path.join(out, 'test_dostrojone.json'), title='dekoder dostrojony, test')
    for m in ('note_F1', 'onoff_F1', 'frame_F1'):
        a = [M.per_file_score(r, m) for r in rows_t]; b = [M.per_file_score(r, m) for r in rows_d]
        r = M.paired_bootstrap(a, b)
        log('TEST %s: dostrojony - domyślny = %+.2f pkt, 95 %% [%.2f, %.2f], p(<=0) = %.4f (n=%d)' % (m, r['diff'], r['lo'], r['hi'], r['p'], r['n']))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--config', required=True); ap.add_argument('--ckpt', required=True); ap.add_argument('--out', required=True)
    ap.add_argument('--max-val', default='150,60', help='najwyżej tyle nagrań walidacyjnych: klasyka,środowiska (GuitarSet: wszystkie)')
    ap.add_argument('--passes', type=int, default=2); ap.add_argument('--procs', type=int, default=os.cpu_count() or 2)
    ap.add_argument('--no-test', action='store_true'); ap.add_argument('--max-test', type=int, default=0, help='0 = wszystkie')
    a = ap.parse_args(argv)
    import torch
    from .model import Gen6
    os.makedirs(a.out, exist_ok=True)
    st = torch.load(a.ckpt, weights_only=False, map_location='cpu')
    cfg = Config.from_dict(st['config'])
    cfg.sources = Config.load(a.config).sources
    cfg.train.cache_fp16 = True
    net = Gen6(cfg); net.load_state_dict(st['net']); net.eval()
    torch.set_num_threads(1)  # równoległość przez procesy przy dekodowaniu; sieć liczy mapy raz
    exs = load_sources(cfg)
    kl, en = (int(x) for x in a.max_val.split(','))
    val = pick(exs, 'val', {'klasyka': kl, 'srodowiska': en})
    print('walidacja: %d nagrań (%s)' % (len(val), {s: sum(e.source == s for e in val) for s in sorted({e.source for e in val})}), flush=True)
    torch.set_num_threads(a.procs)
    items = collect(net, cfg, val, lambda m: print(m, flush=True))
    torch.set_num_threads(1)
    default = dc.asdict(cfg.decode)
    tuned, start, best, per, hist = tune(cfg, net, items, a.passes, a.procs, lambda m: print(m, flush=True))
    json.dump({'decode': tuned, 'default': default, 'objective_start': start, 'objective_best': best, 'per_source': per,
               'val_files': len(items), 'history': hist}, open(os.path.join(a.out, 'decode.json'), 'w'), indent=1)
    if not a.no_test:
        te = pick(exs, 'test', {'*': a.max_test or 10 ** 9})
        torch.set_num_threads(a.procs)
        test_compare(cfg, net, te, default, tuned, a.out, a.procs, lambda m: print(m, flush=True))


if __name__ == '__main__':
    main()
