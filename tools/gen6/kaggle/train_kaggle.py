#!/usr/bin/env python3
"""train_kaggle.py - etap B na Kaggle (GPU): uczenie gen 6 na danych z etapu A (prepare.py), potem ocena na zbiorach testowych.

  python3 tools/gen6/kaggle/train_kaggle.py [--data DIR] [--out /kaggle/working/run] [--config tools/gen6/configs/gen6_kaggle.json]
                                            [--hours 11.0] [--resume]
--data: katalog z manifest_*.jsonl (domyślnie szukany w /kaggle/input). Źródła, których manifestu brak, są pomijane.
--hours: cały czas sesji; uczenie dostaje go tyle, żeby zostało miejsce na ocenę testową (Kaggle przerywa sesję po 12 h).
Wynik: <out>/best.pt, last.pt, log.jsonl, config.json, test.json (miary na zbiorach testowych), train.log.
"""
import argparse, glob, json, os, sys, time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
sys.path.insert(0, ROOT)
T0 = time.time()


def find_data(start='/kaggle/input'):
    hits = sorted(glob.glob(os.path.join(start, '**', 'manifest_klasyka.jsonl'), recursive=True))
    if not hits:
        raise SystemExit('nie znaleziono manifest_klasyka.jsonl w %s (najpierw etap A: prepare.py)' % start)
    return os.path.dirname(hits[0])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data'); ap.add_argument('--out', default='/kaggle/working/run')
    ap.add_argument('--config', default=os.path.join(ROOT, 'tools/gen6/configs/gen6_kaggle.json'))
    ap.add_argument('--hours', type=float, default=11.0); ap.add_argument('--eval-hours', type=float, default=0.6)
    ap.add_argument('--no-guitarset', action='store_true', help='nie dokładaj GuitarSet w etapie B')
    ap.add_argument('--continue-from', help="dalsze uczenie: katalog z last.pt (np. wynik poprzedniej sesji w /kaggle/input); 'auto' = szukaj")
    ap.add_argument('--extend', type=int, default=40, help='z --continue-from: najwyżej tyle epok więcej (budżet czasu przycina)')
    ap.add_argument('--extend-lr', type=float, default=4e-4, help='z --continue-from: szczyt lr nowego cyklu')
    ap.add_argument('--resume', action='store_true'); ap.add_argument('--epochs', type=int); ap.add_argument('--steps', type=int)
    a = ap.parse_args()
    import torch
    from tools.gen6.config import Config
    from tools.gen6 import train as T
    from tools.gen6.evaluate import evaluate_model, report
    from tools.gen6.data import load_sources
    from tools.gen6.model import Gen6

    data = a.data or find_data()
    extra_gs = None
    hits = sorted(glob.glob('/kaggle/input/**/dane_gs/manifest_guitarset.jsonl', recursive=True))
    if hits:  # cechy GuitarSet z poprzedniej sesji (wynik notatnika uczenia)
        extra_gs = hits[0]
    resume = a.resume
    if a.continue_from:
        import shutil
        src = a.continue_from
        if src == 'auto':
            c = sorted(glob.glob('/kaggle/input/**/run/last.pt', recursive=True))
            if not c:
                raise SystemExit('brak run/last.pt w /kaggle/input')
            src = os.path.dirname(c[0])
        os.makedirs(a.out, exist_ok=True)
        for f in ('last.pt', 'best.pt', 'log.jsonl', 'train.log'):
            if os.path.exists(os.path.join(src, f)) and not os.path.exists(os.path.join(a.out, f)):
                shutil.copy(os.path.join(src, f), os.path.join(a.out, f))
        resume = True
    os.makedirs(a.out, exist_ok=True)
    logf = open(os.path.join(a.out, 'train.log'), 'a')

    def log(*m):
        s = '[%6.0f s] ' % (time.time() - T0) + ' '.join(str(x) for x in m)
        print(s, flush=True); logf.write(s + '\n'); logf.flush()

    # GuitarSet dołączony do etapu B, a nie do A: cechy liczone tutaj (ok. 10 min na CPU)
    # (z dołączonego zbioru danych albo pobrany z zenodo, gdy notatnik ma internet; bez obu uczenie idzie bez GuitarSet)
    if not extra_gs and not os.path.exists(os.path.join(data, 'manifest_guitarset.jsonl')) and not a.no_guitarset:
        import subprocess
        gsd = os.path.join(os.path.dirname(a.out), 'dane_gs')
        log('liczę cechy GuitarSet do', gsd)
        r = subprocess.run([sys.executable, os.path.join(ROOT, 'tools/gen6/kaggle/prepare.py'), '--no-classical', '--env', '0',
                            '--out', gsd, '--work', '/tmp/g6gs'])
        if r.returncode:
            log('GuitarSet: prepare.py zakończony kodem %d, uczenie bez GuitarSet' % r.returncode)
        if os.path.exists(os.path.join(gsd, 'manifest_guitarset.jsonl')):
            extra_gs = os.path.join(gsd, 'manifest_guitarset.jsonl')
    d = json.load(open(a.config))
    srcs = []
    for s in d['sources']:
        s = dict(s)
        if s.get('manifest'):
            s['manifest'] = s['manifest'].replace('{DANE}', data)
            if s['name'] == 'GuitarSet' and extra_gs:
                s['manifest'] = extra_gs
            if not os.path.exists(s['manifest']):
                log('pomijam źródło %s: brak %s' % (s['name'], s['manifest'])); continue
        srcs.append(s)
    d['sources'] = srcs
    cfg = Config.from_dict(d)
    if a.epochs: cfg.train.epochs = a.epochs
    if a.steps: cfg.train.steps_per_epoch = a.steps
    budget = a.hours * 3600 - (time.time() - T0) - a.eval_hours * 3600 - 300  # wczytanie danych liczone w budżecie z zapasem
    cfg.train.time_budget_sec = max(600.0, budget)
    log('dane: %s, GPU: %s, budżet uczenia %.1f h' % (data, torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'brak',
                                                    cfg.train.time_budget_sec / 3600))
    exs = load_sources(cfg)
    T.train(cfg, a.out, resume, examples=exs, log=log, extend=a.extend if a.continue_from else 0,
            extend_lr=a.extend_lr if a.continue_from else None)

    # ocena końcowa najlepszej epoki na zbiorach testowych (utwory / gracze, których model nie widział)
    st = torch.load(os.path.join(a.out, 'best.pt'), weights_only=False, map_location='cpu')
    net = Gen6(Config.from_dict(st['config']))
    net.load_state_dict(st['net'])
    if torch.cuda.is_available():
        net = net.cuda()
    te = [e for e in exs if e.split == 'test']
    log('ocena testowa: %d nagrań, najlepsza epoka %d (walidacja %.4f)' % (len(te), st['epoch'], st['score']))
    if te:
        with torch.no_grad():
            rows, groups, ids = evaluate_model(net, te, cfg)
        report(rows, groups, ids, cfg, os.path.join(a.out, 'test.json'), title='gen 6, test')
    log('koniec')


if __name__ == '__main__':
    main()
