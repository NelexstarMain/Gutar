#!/usr/bin/env python3
"""score.py - ocenia wyniki silnika (JSON) względem prawdy z korpusu.

Użycie: score.py <katalog_korpusu> <katalog_wyników> [--csv plik]

Metryki:
  chord_seg   % akordów rozpoznanych poprawnie (głosowanie większościowe w oknie po ustabilizowaniu uderzenia)
  chord_root  % akordów z poprawną prymą
  chord_frm   % ramek z poprawnym akordem w oknie oceny
  chord_lat   mediana opóźnienia pierwszego poprawnego akordu od uderzenia [s]
  flicker     średnia liczba zmian etykiety w oknie oceny (im mniej, tym stabilniej)
  note_f1     F1 obecności dźwięku (dokładna wysokość MIDI), siatka co 50 ms
  pc_f1       F1 obecności klasy dźwięku (bez oktawy)
  onset_f1    F1 początków dźwięków (dokładna wysokość, tolerancja 120 ms)
  tune_ok     % ramek stroika z poprawnym dźwiękiem (pojedyncza nuta)
  tune_cov    % ramek z pojedynczą nutą, dla których stroik coś pokazał
  tune_err    mediana |błąd| częstotliwości stroika [centy]
  cov         średnie pokrycie słyszalnego czasu nuty przez wykryte nuty tej wysokości [%]
  cov80       % nut pokrytych w co najmniej 80% (ogon nie obcięty)
  frag        średnia liczba kawałków, na które pocięto jedną nutę (1 = bez przerw)
  over        średnie przedłużenie ponad koniec nuty [s]
"""
import json, os, sys, glob, math, statistics as st
from collections import defaultdict

def norm(name):
    return name.split('/')[0] if name else None

NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
def root_pc(name):
    if not name: return None
    n = name[:2] if len(name) > 1 and name[1] == '#' else name[:1]
    return NAMES.index(n) if n in NAMES else None

def f1(tp, fp, fn):
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    return 2 * p * r / (p + r) if p + r else 0.0

def active_truth(notes, g):
    out = []
    for n in notes:
        dur = n['t1'] - n['t0']
        if n['t0'] + 0.12 <= g <= n['t0'] + min(dur, 1.2):
            out.append(n)
    return out

def score_file(truth, res):
    out = {}
    win = res.get('winSec', 0.3715)
    frames = res['frames']
    # --- akordy (tylko uderzenia)
    if truth['kind'] == 'strum':
        seg_ok = seg_root = 0; seg_n = 0; frm_ok = frm_n = 0; lats = []; flick = []
        for c in truth['chords']:
            w0, w1 = c['t0'] + 0.45, c['t1'] - 0.10
            fr = [f for f in frames if w0 <= f['t'] <= w1]
            if not fr: continue
            seg_n += 1
            labels = [norm(f['chord']) for f in fr]
            frm_ok += sum(1 for l in labels if l == c['name']); frm_n += len(labels)
            vote = defaultdict(int)
            for l in labels:
                if l: vote[l] += 1
            top = max(vote, key=vote.get) if vote else None
            seg_ok += top == c['name']
            seg_root += root_pc(top) == root_pc(c['name']) if top else 0
            flick.append(sum(1 for a, b in zip(labels, labels[1:]) if a != b))
            for f in frames:
                if c['t0'] <= f['t'] <= c['t1'] and norm(f['chord']) == c['name']:
                    lats.append(f['t'] - c['t0']); break
        out.update(chord_seg=(seg_ok, seg_n), chord_root=(seg_root, seg_n), chord_frm=(frm_ok, frm_n),
                   chord_lat=lats, flicker=flick)
    # --- obecność dźwięków (siatka 50 ms)
    tp = fp = fn = ptp = pfp = pfn = 0
    g = 0.5
    end = truth['dur'] - 0.3
    fr_t = [f['t'] - win / 2 for f in frames]
    j = 0
    while g < end:
        while j + 1 < len(fr_t) and abs(fr_t[j + 1] - g) <= abs(fr_t[j] - g): j += 1
        if frames and abs(fr_t[j] - g) < 0.12:
            est = set(frames[j]['notes']) if not frames[j]['silent'] else set()
        else:
            est = set()
        ref = set(n['midi'] for n in active_truth(truth['notes'], g))
        tp += len(est & ref); fp += len(est - ref); fn += len(ref - est)
        epc = set(m % 12 for m in est); rpc = set(m % 12 for m in ref)
        ptp += len(epc & rpc); pfp += len(epc - rpc); pfn += len(rpc - epc)
        g += 0.05
    out['note'] = (tp, fp, fn); out['pc'] = (ptp, pfp, pfn)
    # --- początki dźwięków
    tol = 0.12
    used = set(); otp = 0
    for n in truth['notes']:
        best = None
        for i, e in enumerate(res['notes']):
            if i in used or e['midi'] != n['midi']: continue
            d = abs(e['t0'] - n['t0'])
            if d <= tol and (best is None or d < best[0]): best = (d, i)
        if best: used.add(best[1]); otp += 1
    out['onset'] = (otp, len(res['notes']) - otp, len(truth['notes']) - otp)
    # --- stroik (melodie)
    if truth['kind'] == 'melody':
        ok = cov = tot = 0; errs = []
        g = 0.5
        while g < end:
            act = [n for n in truth['notes'] if n['t0'] + 0.3 <= g <= n['t1'] - 0.05]
            anyact = [n for n in truth['notes'] if n['t0'] <= g <= n['t1'] + 0.3]
            if len(act) == 1 and len(anyact) == 1:
                while j > 0 and fr_t[j] > g: j -= 1
                while j + 1 < len(fr_t) and fr_t[j + 1] <= g: j += 1
                tot += 1
                tu = frames[j]['tuner'] if frames else None
                if tu:
                    cov += 1
                    if tu['midi'] == act[0]['midi']:
                        ok += 1; errs.append(abs(1200 * math.log2(tu['f'] / act[0]['f'])))
            g += 0.05
        out['tune'] = (ok, cov, tot, errs)
    # --- podtrzymanie: jaką część słyszalnego czasu nuty pokrywają wykryte nuty tej wysokości i na ile kawałków je pocięto
    cov = []; frag = []; over = []
    for n in truth['notes']:
        ta = n.get('ta')
        if ta is None or ta - n['t0'] < 0.5: continue
        pieces = [(max(e['t0'], n['t0']), min(e['t1'], ta)) for e in res['notes']
                  if e['midi'] == n['midi'] and e['t1'] > n['t0'] and e['t0'] < ta and e['t0'] > n['t0'] - 0.15]
        pieces = [p for p in pieces if p[1] > p[0]]
        if not pieces: cov.append(0.0); frag.append(0); continue
        pieces.sort(); tot = 0.0; cur = pieces[0]
        for p in pieces[1:]:
            if p[0] <= cur[1]: cur = (cur[0], max(cur[1], p[1]))
            else: tot += cur[1] - cur[0]; cur = p
        tot += cur[1] - cur[0]
        cov.append(min(1.0, tot / (ta - n['t0']))); frag.append(len(pieces))
        for e in res['notes']:
            if e['midi'] == n['midi'] and abs(e['t0'] - n['t0']) < 0.15: over.append(max(0.0, e['t1'] - max(ta, n['t1'])))
    out['sustain'] = (cov, frag, over)
    out['rtf'] = res['cpuMs'] / 1000.0 / res['audioSec']
    return out

def main():
    corpus, results = sys.argv[1], sys.argv[2]
    groups = defaultdict(list)
    for tf in sorted(glob.glob(os.path.join(corpus, '*.truth.json'))):
        truth = json.load(open(tf))
        rf = os.path.join(results, truth['id'] + '.json')
        if not os.path.exists(rf): continue
        res = json.load(open(rf))
        key = truth['id'].rsplit('_', 1)[0]
        groups[key].append(score_file(truth, res))
    def agg(rows):
        d = {}
        def s(k, i): return sum(r[k][i] for r in rows if k in r)
        if any('chord_seg' in r for r in rows):
            n = s('chord_seg', 1)
            d['chord_seg'] = 100 * s('chord_seg', 0) / n
            d['chord_root'] = 100 * s('chord_root', 0) / n
            d['chord_frm'] = 100 * s('chord_frm', 0) / max(1, s('chord_frm', 1))
            lat = [x for r in rows if 'chord_lat' in r for x in r['chord_lat']]
            d['chord_lat'] = st.median(lat) if lat else float('nan')
            fl = [x for r in rows if 'flicker' in r for x in r['flicker']]
            d['flicker'] = sum(fl) / len(fl) if fl else float('nan')
        d['note_f1'] = 100 * f1(s('note', 0), s('note', 1), s('note', 2))
        d['pc_f1'] = 100 * f1(s('pc', 0), s('pc', 1), s('pc', 2))
        d['onset_f1'] = 100 * f1(s('onset', 0), s('onset', 1), s('onset', 2))
        if any('tune' in r for r in rows):
            ok = s('tune', 0); cov = s('tune', 1); tot = s('tune', 2)
            d['tune_ok'] = 100 * ok / max(1, tot); d['tune_cov'] = 100 * cov / max(1, tot)
            errs = [e for r in rows if 'tune' in r for e in r['tune'][3]]
            d['tune_err'] = st.median(errs) if errs else float('nan')
        cov = [x for r in rows for x in r['sustain'][0]]; frag = [x for r in rows for x in r['sustain'][1] if x > 0]; over = [x for r in rows for x in r['sustain'][2]]
        if cov:
            d['cov'] = 100 * sum(cov) / len(cov); d['cov80'] = 100 * sum(1 for c in cov if c >= 0.8) / len(cov)
            d['frag'] = sum(frag) / len(frag) if frag else float('nan'); d['over'] = sum(over) / len(over) if over else 0.0
        d['rtf'] = sum(r['rtf'] for r in rows) / len(rows)
        return d
    cols = ['chord_seg', 'chord_root', 'chord_frm', 'chord_lat', 'flicker', 'note_f1', 'pc_f1', 'onset_f1', 'tune_ok', 'tune_cov', 'tune_err', 'cov', 'cov80', 'frag', 'over', 'rtf']
    print('%-16s' % 'grupa' + ''.join('%11s' % c for c in cols))
    allrows = []
    for k in sorted(groups):
        a = agg(groups[k]); allrows += groups[k]
        print('%-16s' % k + ''.join('%11s' % ('%.2f' % a[c] if c in a else '-') for c in cols))
    a = agg(allrows)
    print('%-16s' % 'RAZEM' + ''.join('%11s' % ('%.2f' % a[c] if c in a else '-') for c in cols))
    if '--csv' in sys.argv:
        with open(sys.argv[sys.argv.index('--csv') + 1], 'w') as f:
            f.write('grupa,' + ','.join(cols) + '\n')
            for k in sorted(groups):
                aa = agg(groups[k]); f.write(k + ',' + ','.join('%.3f' % aa[c] if c in aa else '' for c in cols) + '\n')
            f.write('RAZEM,' + ','.join('%.3f' % a[c] if c in a else '' for c in cols) + '\n')

if __name__ == '__main__':
    main()
