#!/usr/bin/env python3
"""guitarset_eval.py - ocena silnika na prawdziwych nagraniach GuitarSet (Xi i in., ISMIR 2018).

Użycie: guitarset_eval.py <katalog_jams> <katalog_wyników> [--by-style]

  katalog_jams     rozpakowany annotation.zip z https://zenodo.org/records/3371780
  katalog_wyników  JSON z `gt_cli analyze <nazwa>_mic.wav <nazwa>.json` (nazwa jak plik .jams)

Metryki (mir_eval, Raffel i in., ISMIR 2014, standard w publikacjach o transkrypcji):
  on_f1   nuty: F1 początków, tolerancja 50 ms, wysokość +-50 centów (bez końców nut)
  onoff   nuty: F1 z początkiem i końcem (koniec w 20 % długości nuty albo 50 ms)
  P, R    precyzja i czułość dla on_f1
  frm_f1  obecność dźwięku (dokładna wysokość MIDI) w siatce co 50 ms, z listy nut
  root    % siatki 0,1 s z poprawną prymą akordu (adnotacja "performed")
  majmin  % siatki z poprawnym akordem w słowniku dur/moll (mir_eval.chord.majmin)
"""
import sys, os, glob, json, collections
import numpy as np
import mir_eval

SUFFIX = {'': 'maj', 'm': 'min', '5': '5', '7': '7', 'maj7': 'maj7', 'm7': 'min7', 'sus2': 'sus2', 'sus4': 'sus4',
          'dim': 'dim', 'aug': 'aug', '6': 'maj6', 'm6': 'min6', 'add9': 'maj(9)', 'madd9': 'min(9)', '9': '9',
          'm9': 'min9', '7sus4': 'sus4(b7)', 'dim7': 'dim7', 'm7b5': 'hdim7', 'mMaj7': 'minmaj7'}


def harte(name):
    if not name:
        return 'N'
    name = name.split('/')[0]
    root = name[:2] if len(name) > 1 and name[1] == '#' else name[:1]
    q = SUFFIX.get(name[len(root):])
    return root + ':' + q if q else 'X'


def load_jams(path):
    j = json.load(open(path))
    notes, chords = [], []
    for a in j['annotations']:
        if a['namespace'] == 'note_midi':
            for d in a['data']:
                notes.append((d['time'], d['time'] + d['duration'], d['value']))
        elif a['namespace'] == 'chord':
            chords.append([(d['time'], d['time'] + d['duration'], d['value']) for d in a['data']])
    return notes, (chords[-1] if chords else [])


def score(jdir, rdir):
    rows = []
    for jp in sorted(glob.glob(os.path.join(jdir, '*.jams'))):
        name = os.path.splitext(os.path.basename(jp))[0]
        rp = os.path.join(rdir, name + '.json')
        if not os.path.exists(rp):
            continue
        ref_notes, ref_ch = load_jams(jp)
        res = json.load(open(rp))
        est = res['notes']
        ri = np.array([[a, b] for a, b, _ in ref_notes]) if ref_notes else np.zeros((0, 2))
        rpz = np.array([mir_eval.util.midi_to_hz(m) for _, _, m in ref_notes])
        ei = np.array([[e['t0'], max(e['t1'], e['t0'] + 0.01)] for e in est]) if est else np.zeros((0, 2))
        epz = np.array([mir_eval.util.midi_to_hz(e['midi']) for e in est])
        r = {'name': name}
        r['on'] = mir_eval.transcription.precision_recall_f1_overlap(ri, rpz, ei, epz, offset_ratio=None)[:3]
        r['onoff'] = mir_eval.transcription.precision_recall_f1_overlap(ri, rpz, ei, epz)[2]
        # obecność w siatce 50 ms
        dur = res['audioSec']
        tp = fp = fn = 0
        for g in np.arange(0.05, dur, 0.05):
            rs = set(int(round(m)) for a, b, m in ref_notes if a <= g < b)
            es = set(e['midi'] for e in est if e['t0'] <= g < e['t1'])
            tp += len(rs & es); fp += len(es - rs); fn += len(rs - es)
        r['frm'] = (tp, fp, fn)
        # akordy w siatce 0,1 s; etykieta ramki dotyczy środka okna analizy
        win = res.get('winSec', 0.3715)
        ft = np.array([f['t'] - win / 2 for f in res['frames']])
        refl, estl = [], []
        for g in np.arange(0.05, dur, 0.1):
            rl = next((v for a, b, v in ref_ch if a <= g < b), None)
            if rl is None:
                continue
            k = int(np.argmin(np.abs(ft - g))) if len(ft) else -1
            el = res['frames'][k]['chord'] if k >= 0 and abs(ft[k] - g) < 0.1 else None
            refl.append(rl); estl.append(harte(el))
        r['root'] = mir_eval.chord.root(refl, estl) if refl else np.array([])
        r['majmin'] = mir_eval.chord.majmin(refl, estl) if refl else np.array([])
        rows.append(r)
    return rows


def agg(rows):
    on = np.array([r['on'] for r in rows])
    tp = sum(r['frm'][0] for r in rows); fp = sum(r['frm'][1] for r in rows); fn = sum(r['frm'][2] for r in rows)
    p = tp / max(1, tp + fp); rc = tp / max(1, tp + fn)
    root = np.concatenate([r['root'] for r in rows]); mm = np.concatenate([r['majmin'] for r in rows])
    root = root[root >= 0]; mm = mm[mm >= 0]
    return {'n': len(rows), 'on_f1': 100 * on[:, 2].mean(), 'P': 100 * on[:, 0].mean(), 'R': 100 * on[:, 1].mean(),
            'onoff': 100 * np.mean([r['onoff'] for r in rows]), 'frm_f1': 100 * 2 * p * rc / max(1e-9, p + rc),
            'root': 100 * root.mean() if len(root) else float('nan'), 'majmin': 100 * mm.mean() if len(mm) else float('nan')}


def main():
    rows = score(sys.argv[1], sys.argv[2])
    cols = ['n', 'on_f1', 'P', 'R', 'onoff', 'frm_f1', 'root', 'majmin']
    print('%-12s' % 'grupa' + ''.join('%9s' % c for c in cols))
    groups = collections.defaultdict(list)
    if '--by-style' in sys.argv:
        for r in rows:
            style = r['name'].split('_')[1].split('-')[0].rstrip('0123456789')
            groups[style + ('_comp' if r['name'].endswith('comp') else '_solo')].append(r)
    for k in sorted(groups):
        a = agg(groups[k]); print('%-12s' % k + ''.join('%9.2f' % a[c] if c != 'n' else '%9d' % a[c] for c in cols))
    a = agg(rows); print('%-12s' % 'RAZEM' + ''.join('%9.2f' % a[c] if c != 'n' else '%9d' % a[c] for c in cols))


if __name__ == '__main__':
    main()
