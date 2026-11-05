#!/usr/bin/env python3
"""make_manifest.py - manifest JSONL z folderu nagrań piezo i ręcznych opisów (do dostrajania modelu).

  python3 tools/gen6/piezo/make_manifest.py FOLDER [--out FOLDER/manifest_piezo.jsonl] [--val-every 5] [--test-every 0]

W FOLDERZE pary o tej samej nazwie: <nazwa>.wav + <nazwa>.mid / .midi (nuty z MIDI) albo <nazwa>.csv / .tsv / .txt
(kolumny: onset [s], pitch [numer MIDI], opcjonalnie offset [s]; z nagłówkiem albo bez: onset, offset, pitch).
  * Opis tylko z początkami i wysokościami (bez końców nut): uczy się tylko głowica początków (etykiety 'brzmi' i 'koniec' pomijane).
  * Z końcami nut: uczą się wszystkie głowice; to lepsze, bo model w domenie piezo uczy się też, jak długo nuty brzmią.
Podział: co --val-every-te nagranie (po nazwie, stabilnie) do walidacji, co --test-every-te do testu (0 = bez testu).
Waga źródła i nagrań: pole "weight" w manifeście (domyślnie 1).
"""
import argparse, json, os, sys, zlib

EXT_FMT = {'.mid': 'midi', '.midi': 'midi', '.csv': 'notes_csv', '.tsv': 'notes_csv', '.txt': 'notes_csv'}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('folder'); ap.add_argument('--out')
    ap.add_argument('--val-every', type=int, default=5); ap.add_argument('--test-every', type=int, default=0)
    ap.add_argument('--group', default='piezo')
    a = ap.parse_args()
    names = sorted(f[:-4] for f in os.listdir(a.folder) if f.lower().endswith('.wav'))
    out = a.out or os.path.join(a.folder, 'manifest_piezo.jsonl')
    n_tr = n_va = n_te = skipped = 0
    with open(out, 'w') as fo:
        for nm in names:
            ann = next((nm + e for e in EXT_FMT if os.path.exists(os.path.join(a.folder, nm + e))), None)
            if ann is None:
                print('brak opisu dla %s.wav, pomijam' % nm, file=sys.stderr); skipped += 1; continue
            h = zlib.crc32(nm.encode())
            sp = 'test' if a.test_every and h % a.test_every == 1 else ('val' if a.val_every and h % a.val_every == 0 else 'train')
            rec = {'id': nm, 'audio': nm + '.wav', 'annotation': ann, 'format': EXT_FMT[os.path.splitext(ann)[1].lower()],
                   'split': sp, 'group': a.group}
            if rec['format'] == 'midi':  # głośność z ręcznego opisu jest stała, nie uczymy na niej głowicy głośności
                rec['has'] = ['onset', 'frame', 'offset']
            fo.write(json.dumps(rec, ensure_ascii=False) + '\n')
            n_tr += sp == 'train'; n_va += sp == 'val'; n_te += sp == 'test'
    print('%s: train %d, val %d, test %d, pominięto %d' % (out, n_tr, n_va, n_te, skipped))
    if n_va == 0:
        print('UWAGA: brak nagrań walidacyjnych; przy kilku nagraniach ustaw --val-every 2 albo 3', file=sys.stderr)


if __name__ == '__main__':
    main()
