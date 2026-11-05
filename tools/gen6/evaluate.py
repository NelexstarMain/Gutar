"""evaluate.py - ewaluacja gen 6 i (tymi samymi funkcjami) wyników silnika C++ z dowolnej generacji.

  python3 -m tools.gen6.evaluate model  --config cfg.json --ckpt run/best.pt [--split val|test|all] [--out raport.json]
  python3 -m tools.gen6.evaluate engine --config cfg.json --results katalog_json [--split ...] [--out raport.json]
  python3 -m tools.gen6.evaluate compare A.json B.json [--metric note_F1]

`engine`: dla każdego nagrania ze źródeł z konfiguracji szuka <id>.json (wynik `gt_cli analyze`), więc gen 3/4/5 i gen 6 są
porównywane na tych samych plikach i tymi samymi miarami. `compare`: sparowany bootstrap na metryce po plikach.
Raport JSON: konfiguracja, tabela zbiorcza (mikro i makro), wyniki per plik (do porównań).
"""
from __future__ import annotations
import argparse
import json
import math
import os
import sys
import numpy as np
from . import metrics as M
from .config import Config
from .data import example_features, load_sources, parse_engine_json, summarize
from .decode import decode_notes
from .labels import make_targets


def _clean(o):
    if isinstance(o, dict):
        return {k: _clean(v) for k, v in o.items() if not k.startswith('_raw')}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    if isinstance(o, (np.floating, float)):
        return None if math.isnan(float(o)) else float(o)
    if isinstance(o, (np.integer,)):
        return int(o)
    return o


def evaluate_example(ex, est_notes, cfg: Config, probs=None, X_len=None, est_chords=None, tuner_frames=None):
    tg = valid = None
    if probs is not None:
        maps, _ = make_targets(ex, X_len, cfg.features, cfg.labels)
        tg = {k: maps[k] for k in ('onset', 'frame', 'offset')}
    return M.evaluate_file(ex.notes, est_notes, ex.duration, ex.chords, est_chords, ex.has, probs, tg, valid, cfg.labels,
                           tuner_frames=tuner_frames)


def evaluate_model(net, examples, cfg: Config, with_maps=True, progress=False):
    """-> (wiersze per plik, nazwy grup, identyfikatory). Używane też przez train.py do walidacji po każdej epoce."""
    rows, groups, ids = [], [], []
    for k, ex in enumerate(examples):
        X = example_features(ex, cfg.features, cfg.train.cache_dir, fp16=cfg.train.cache_fp16, mmap=cfg.train.lazy)
        X = np.asarray(X, np.float32)
        if not len(X):
            continue
        p = net.predict(X)
        est = decode_notes(p, cfg.features, cfg.decode, cfg.labels)
        rows.append(evaluate_example(ex, est, cfg, p if with_maps else None, len(X)))
        groups.append(ex.source + ':' + (ex.group or ''))
        ids.append(ex.id)
        if progress:
            print('\r%d/%d' % (k + 1, len(examples)), end='', file=sys.stderr, flush=True)
    if progress:
        print(file=sys.stderr)
    return rows, groups, ids


def engine_rows(examples, cfg: Config, results_dir):
    rows, groups, ids = [], [], []
    for ex in examples:
        rp = os.path.join(results_dir, ex.id + '.json')
        if not os.path.exists(rp):
            continue
        est, chords, _, _ = parse_engine_json(rp)
        r = json.load(open(rp))
        win = r.get('winSec', 0.3715)
        tf = [(f['t'] - win / 2, f['tuner']['midi'] if f.get('tuner') else None, f['tuner']['f'] if f.get('tuner') else None)
              for f in r.get('frames', [])]
        rows.append(evaluate_example(ex, est, cfg, est_chords=chords, tuner_frames=tf if ex.meta.get('kind') == 'melody' else None))
        groups.append(ex.source + ':' + (ex.group or '')); ids.append(ex.id)
    return rows, groups, ids


def report(rows, groups, ids, cfg, out=None, title=''):
    mi, ma = M.aggregate(rows, groups, micro=True), M.aggregate(rows, groups, micro=False)
    print('== %s: mikro (suma po plikach) ==' % title); print(M.format_table(mi))
    print('== %s: makro (średnia po plikach, jak w publikacjach) ==' % title); print(M.format_table(ma))
    ci = {m: M.bootstrap_ci([M.per_file_score(r, m) for r in rows]) for m in ('note_F1', 'onoff_F1', 'frame_F1')}
    print('95 % przedziały (bootstrap po plikach): ' + '; '.join('%s %.2f [%.2f, %.2f]' % ((k,) + v) for k, v in ci.items()))
    if out:
        json.dump(_clean({'title': title, 'config': cfg.to_dict(), 'micro': mi, 'macro': ma, 'ci': ci,
                          'files': [dict(id=i, group=g, **r) for i, g, r in zip(ids, groups, rows)]}), open(out, 'w'), indent=1, ensure_ascii=False)
        print('zapisano', out)
    return mi, ma


def compare(a_path, b_path, metric='note_F1'):
    A, B = json.load(open(a_path)), json.load(open(b_path))
    fa = {f['id']: f for f in A['files']}; fb = {f['id']: f for f in B['files']}
    common = sorted(set(fa) & set(fb))
    def score(f):
        v = M.per_file_score(f, metric)
        return float('nan') if v is None else v
    a = [score(fa[i]) for i in common]; b = [score(fb[i]) for i in common]
    r = M.paired_bootstrap(a, b)
    print('%s: A = %s, B = %s, wspólne pliki: %d' % (metric, A.get('title'), B.get('title'), r['n']))
    print('A - B = %.2f pkt, 95 %% [%.2f, %.2f], p(A <= B) = %.4f' % (r['diff'], r['lo'], r['hi'], r['p']))
    return r


def main(argv=None):
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd', required=True)
    for name in ('model', 'engine'):
        s = sub.add_parser(name)
        s.add_argument('--config', required=True)
        s.add_argument('--split', default='val', choices=['train', 'val', 'test', 'all'])
        s.add_argument('--out')
        if name == 'model':
            s.add_argument('--ckpt', required=True)
        else:
            s.add_argument('--results', required=True)
    c = sub.add_parser('compare')
    c.add_argument('a'); c.add_argument('b'); c.add_argument('--metric', default='note_F1')
    a = ap.parse_args(argv)
    if a.cmd == 'compare':
        compare(a.a, a.b, a.metric); return
    cfg = Config.load(a.config)
    exs = load_sources(cfg)
    if a.split != 'all':
        exs = [e for e in exs if e.split == a.split]
    print(summarize(exs))
    if a.cmd == 'model':
        import torch
        from .model import Gen6
        st = torch.load(a.ckpt, map_location='cpu', weights_only=False)
        if 'config' in st:
            cfg = Config.from_dict(st['config']) if isinstance(st['config'], dict) else cfg
        net = Gen6(cfg); net.load_state_dict(st['net'] if 'net' in st else st)
        rows, groups, ids = evaluate_model(net, exs, cfg, progress=True)
        report(rows, groups, ids, cfg, a.out, 'gen 6: ' + os.path.basename(a.ckpt))
    else:
        rows, groups, ids = engine_rows(exs, cfg, a.results)
        report(rows, groups, ids, cfg, a.out, 'silnik: ' + a.results)


if __name__ == '__main__':
    main()
