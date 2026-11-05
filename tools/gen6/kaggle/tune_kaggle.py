#!/usr/bin/env python3
"""tune_kaggle.py - strojenie progów dekodera na Kaggle (CPU, bez limitu GPU).

  python3 tools/gen6/kaggle/tune_kaggle.py [--from-kernel gutar-gen6-trening-4] [--max-val 150,60]

Wejścia notatnika: dane z etapu A (manifesty i cechy) oraz notatnik uczenia z run/best.pt (i dane_gs z cechami GuitarSet).
Wynik: /kaggle/working/tune/decode.json, test_domyslne.json, test_dostrojone.json.
"""
import argparse, glob, json, os, subprocess, sys, time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
sys.path.insert(0, ROOT)
INPUT = os.environ.get('GUTAR_INPUT', '/kaggle/input')
OUT = os.environ.get('GUTAR_TUNE_OUT', '/kaggle/working/tune')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--from-kernel', default='gutar-gen6-trening-4'); ap.add_argument('--max-val', default='150,60')
    ap.add_argument('--passes', type=int, default=2); ap.add_argument('--max-test', type=int, default=0)
    a = ap.parse_args()
    hits = sorted(glob.glob(INPUT + '/**/manifest_klasyka.jsonl', recursive=True))
    ck = sorted(glob.glob(INPUT + '/**/%s/run/best.pt' % a.from_kernel, recursive=True))
    if not hits or not ck:
        raise SystemExit('brak danych (%s) albo best.pt notatnika %s' % (hits, a.from_kernel))
    data = os.path.dirname(hits[0])
    gs = sorted(glob.glob(INPUT + '/**/dane_gs/manifest_guitarset.jsonl', recursive=True))
    if not gs:  # bez internetu i bez dane_gs: tuning bez GuitarSet
        print('UWAGA: brak cech GuitarSet (dane_gs), próbuję je policzyć', flush=True)
        gsd = '/kaggle/working/dane_gs'
        subprocess.run([sys.executable, os.path.join(ROOT, 'tools/gen6/kaggle/prepare.py'), '--no-classical', '--env', '0', '--out', gsd,
                        '--work', '/tmp/g6gs'])
        gs = [os.path.join(gsd, 'manifest_guitarset.jsonl')] if os.path.exists(os.path.join(gsd, 'manifest_guitarset.jsonl')) else []
    d = json.load(open(os.path.join(ROOT, 'tools/gen6/configs/gen6_kaggle.json')))
    srcs = []
    for s in d['sources']:
        s = dict(s); s['manifest'] = s['manifest'].replace('{DANE}', data)
        if s['name'] == 'GuitarSet':
            if not gs:
                continue
            s['manifest'] = gs[0]
        if os.path.exists(s['manifest']):
            srcs.append(s)
    d['sources'] = srcs
    os.makedirs(OUT, exist_ok=True)
    cfgp = os.path.join(OUT, 'config_tune.json'); json.dump(d, open(cfgp, 'w'))
    print('dane: %s\nmodel: %s\nźródła: %s' % (data, ck[0], [s['name'] for s in srcs]), flush=True)
    from tools.gen6 import tune_decoder
    t0 = time.time()
    tune_decoder.main(['--config', cfgp, '--ckpt', ck[0], '--out', OUT, '--max-val', a.max_val, '--passes', str(a.passes),
                       '--max-test', str(a.max_test)])
    print('koniec, %.0f s' % (time.time() - t0), flush=True)


if __name__ == '__main__':
    main()
