"""metrics.py - wszystkie funkcje ewaluacyjne gen 6. Sam numpy (bez mir_eval), definicje zgodne z mir_eval tam, gdzie jest
odpowiednik (sprawdzane w testach, gdy mir_eval jest zainstalowane), więc wyniki są porównywalne z publikacjami i z
tools/guitarset_eval.py.

Wejście: listy nut (obiekty z polami pitch, onset, offset, opcjonalnie velocity, string, audible_end) - z prawdy, z dekodera gen 6
albo z JSON silnika C++ (data.parse_engine_json), więc te same funkcje oceniają wszystkie generacje.

Grupy metryk
  1. nuty           note_prf (początek; początek+koniec; z głośnością), dopasowanie maksymalne (Hopcroft-Karp), błędy czasu
  2. klatki         frame_metrics na siatce czasu: P/R/F1, accuracy, rozkład błędów E_sub/E_miss/E_fa/E_tot (Poliner i Ellis 2007),
                    klasy dźwięku (chroma), błędy oktawowe i harmoniczne
  3. mapy sieci     map_metrics bez progu: średnia precyzja (AP), najlepszy próg i F1, kalibracja (ECE, Brier)
  4. podtrzymanie   sustain_metrics: pokrycie słyszalnego czasu nuty, % nut pokrytych w 80 %, poszatkowanie, przedłużenie
  5. akordy         chord_metrics na siatce: prima, dur/moll (jak mir_eval majmin), pełna etykieta, bas, segmentacja
                    (directional Hamming), akord na uderzenie (głosowanie jak w tools/score.py), akordy z nut (chords_from_notes)
  6. tabulatura     tab_metrics: P/R/F1 par struna-próg w klatkach, TDR (Wiggins i Kim 2019), poprawna struna nut dopasowanych
  7. stroik         tuner_metrics (wynik silnika: trafiony dźwięk, pokrycie, błąd w centach)
  8. zbiorczo       evaluate_file (wszystko dla jednego nagrania), aggregate (mikro i makro, po grupach), bootstrap_ci,
                    paired_bootstrap (czy system A jest istotnie lepszy od B na tych samych plikach), format_table
"""
from __future__ import annotations
import math
from collections import defaultdict
import numpy as np

# =============================================================== pomocnicze

def prf(tp, fp, fn):
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    return p, r, (2 * p * r / (p + r) if p + r else 0.0)


def _arr(notes):
    if not notes:
        return np.zeros(0), np.zeros(0), np.zeros(0)
    return (np.array([n.onset for n in notes], float), np.array([n.offset for n in notes], float),
            np.array([n.pitch for n in notes], float))


def midi_to_hz(m):
    return 440.0 * 2 ** ((np.asarray(m, float) - 69) / 12)


def hopcroft_karp(adj, n_left, n_right):
    """Maksymalne skojarzenie w grafie dwudzielnym (Hopcroft-Karp). adj[i] = lista j. Zwraca listę par (i, j)."""
    import sys
    sys.setrecursionlimit(max(sys.getrecursionlimit(), 4 * n_left + 100))
    INF = 1 << 30
    mu, mv, dist = [-1] * n_left, [-1] * n_right, [0] * n_left

    def bfs():
        q = []
        for u in range(n_left):
            if mu[u] < 0:
                dist[u] = 0; q.append(u)
            else:
                dist[u] = INF
        found, qi = False, 0
        while qi < len(q):
            u = q[qi]; qi += 1
            for v in adj[u]:
                w = mv[v]
                if w < 0:
                    found = True
                elif dist[w] == INF:
                    dist[w] = dist[u] + 1; q.append(w)
        return found

    def dfs(u):
        for v in adj[u]:
            w = mv[v]
            if w < 0 or (dist[w] == dist[u] + 1 and dfs(w)):
                mu[u], mv[v] = v, u
                return True
        dist[u] = INF
        return False

    while bfs():
        for u in range(n_left):
            if mu[u] < 0:
                dfs(u)
    return [(u, mu[u]) for u in range(n_left) if mu[u] >= 0]


# =============================================================== 1. nuty

def match_notes(ref, est, onset_tol=0.05, pitch_tol=50.0, offset_ratio=0.2, offset_min_tol=0.05, use_audible_end=False):
    """Dopasowanie nut jak mir_eval.transcription.match_notes: para możliwa, gdy |Δ początku| <= onset_tol, |Δ wysokości| <= pitch_tol
    centów i (gdy offset_ratio nie None) |Δ końca| <= max(offset_min_tol, offset_ratio * długość nuty wzorcowej); potem maksymalne
    skojarzenie. Zwraca listę par (i_ref, j_est)."""
    ro, rf, rp = _arr(ref)
    if use_audible_end and ref:
        rf = np.array([n.end(True) for n in ref])
    eo, ef, ep = _arr(est)
    if not len(ro) or not len(eo):
        return []
    od = np.around(np.abs(ro[:, None] - eo[None]), 7) <= onset_tol
    pd = np.abs(1200 * np.log2(midi_to_hz(rp)[:, None] / midi_to_hz(ep)[None])) <= pitch_tol
    ok = od & pd
    if offset_ratio is not None:
        tol = np.maximum(offset_min_tol, offset_ratio * (rf - ro))
        ok &= np.around(np.abs(rf[:, None] - ef[None]), 7) <= tol[:, None]
    adj = [list(np.nonzero(ok[i])[0]) for i in range(len(ro))]
    return hopcroft_karp(adj, len(ro), len(eo))


def note_prf(ref, est, onset_tol=0.05, pitch_tol=50.0, offset_ratio=None, offset_min_tol=0.05):
    """-> dict tp, fp, fn, P, R, F1, overlap (średni stosunek pokrycia dopasowanych nut, jak w mir_eval)."""
    m = match_notes(ref, est, onset_tol, pitch_tol, offset_ratio, offset_min_tol)
    tp = len(m)
    p, r, f = prf(tp, len(est) - tp, len(ref) - tp)
    ov = []
    for i, j in m:
        a, b = ref[i], est[j]
        inter = min(a.offset, b.offset) - max(a.onset, b.onset)
        union = max(a.offset, b.offset) - min(a.onset, b.onset)
        ov.append(max(0.0, inter) / union if union > 0 else 0.0)
    return {'tp': tp, 'fp': len(est) - tp, 'fn': len(ref) - tp, 'P': p, 'R': r, 'F1': f, 'overlap': float(np.mean(ov)) if ov else 0.0}


def note_prf_velocity(ref, est, onset_tol=0.05, pitch_tol=50.0, offset_ratio=0.2, offset_min_tol=0.05, velocity_tol=0.1):
    """Jak mir_eval.transcription_velocity (Hawthorne i in. 2018): głośności w skali MIDI 0..127 (u nas 0..1, więc x127); wzorzec
    przeskalowany do [0,1] (zakres co najmniej 1), przewidziane dopasowane liniowo (najmniejsze kwadraty) do wzorca na parach
    dopasowanych nut; para zostaje, gdy różnica < velocity_tol."""
    m = match_notes(ref, est, onset_tol, pitch_tol, offset_ratio, offset_min_tol)
    if not m or any(ref[i].velocity is None or est[j].velocity is None for i, j in m):
        tp = 0
    else:
        rv = 127.0 * np.array([n.velocity for n in ref], float)
        lo, hi = rv.min(), rv.max()
        rvn = (rv - lo) / max(1.0, hi - lo)
        a = np.array([rvn[i] for i, _ in m]); e = 127.0 * np.array([est[j].velocity for _, j in m], float)
        sl, ic = np.linalg.lstsq(np.vstack([e, np.ones_like(e)]).T, a, rcond=None)[0]
        tp = int(np.sum(np.abs(sl * e + ic - a) < velocity_tol))
    p, r, f = prf(tp, len(est) - tp, len(ref) - tp)
    return {'tp': tp, 'fp': len(est) - tp, 'fn': len(ref) - tp, 'P': p, 'R': r, 'F1': f}


def onset_timing(ref, est, onset_tol=0.05, pitch_tol=50.0):
    """Błędy czasu dopasowanych początków [s]: mediana |Δ|, średnia ze znakiem (przesunięcie systematyczne), 90. percentyl."""
    m = match_notes(ref, est, onset_tol, pitch_tol, None)
    d = np.array([est[j].onset - ref[i].onset for i, j in m])
    if not len(d):
        return {'n': 0, 'med_abs': float('nan'), 'bias': float('nan'), 'p90_abs': float('nan')}
    return {'n': len(d), 'med_abs': float(np.median(np.abs(d))), 'bias': float(d.mean()), 'p90_abs': float(np.percentile(np.abs(d), 90))}


# =============================================================== 2. klatki

def time_grid(duration, hop=0.01, start=0.0):
    return np.arange(start, max(start, duration), hop)


def notes_to_roll(notes, times, midi_lo=21, n_pitch=88, use_audible_end=True, min_onset_delay=0.0):
    """[len(times), n_pitch] bool: nuta brzmi w chwili g, gdy onset + min_onset_delay <= g < koniec."""
    roll = np.zeros((len(times), n_pitch), bool)
    for n in notes:
        s = int(round(n.pitch)) - midi_lo
        if 0 <= s < n_pitch:
            end = n.end(use_audible_end) if hasattr(n, 'end') else n.offset
            a, b = np.searchsorted(times, n.onset + min_onset_delay), np.searchsorted(times, end)
            roll[a:b, s] = True
    return roll


def frame_metrics(ref_roll, est_roll):
    """Miary wielogłosowe na siatce (Poliner i Ellis 2007; jak mir_eval.multipitch):
    P, R, F1, Acc = TP/(TP+FP+FN), E_sub, E_miss, E_fa, E_tot (względem liczby nut wzorca)."""
    n = min(len(ref_roll), len(est_roll))
    r, e = ref_roll[:n], est_roll[:n]
    tp = int((r & e).sum()); fp = int((~r & e).sum()); fn = int((r & ~e).sum())
    nr, ne, nc = r.sum(1), e.sum(1), (r & e).sum(1)
    tot = max(1, int(nr.sum()))
    p, rc, f = prf(tp, fp, fn)
    return {'tp': tp, 'fp': fp, 'fn': fn, 'P': p, 'R': rc, 'F1': f, 'Acc': tp / max(1, tp + fp + fn),
            'E_sub': float((np.minimum(nr, ne) - nc).sum() / tot), 'E_miss': float(np.maximum(0, nr - ne).sum() / tot),
            'E_fa': float(np.maximum(0, ne - nr).sum() / tot),
            'E_tot': float((np.maximum(nr, ne) - nc).sum() / tot)}


def chroma_roll(roll, midi_lo):
    out = np.zeros((len(roll), 12), bool)
    for s in range(roll.shape[1]):
        out[:, (midi_lo + s) % 12] |= roll[:, s]
    return out


HARMONIC_INTERVALS = {'oktawa': (12, -12), 'dwie_oktawy': (24, -24), 'duodecyma': (19, -19), 'kwinta': (7, -7)}


def harmonic_errors(ref_roll, est_roll):
    """Udział fałszywych alarmów, które leżą w interwale harmonicznym od nuty wzorca brzmiącej w tej samej chwili
    (typowe błędy: alikwot uznany za nutę). Zwraca udział względem wszystkich FP i liczbę FP."""
    n = min(len(ref_roll), len(est_roll))
    r, e = ref_roll[:n], est_roll[:n]
    fp = e & ~r
    nfp = int(fp.sum())
    out = {'fp': nfp}
    for name, ivs in HARMONIC_INTERVALS.items():
        hit = np.zeros_like(fp)
        for iv in ivs:
            sh = np.zeros_like(r)
            if iv > 0:
                sh[:, iv:] = r[:, :-iv]
            else:
                sh[:, :iv] = r[:, -iv:]
            hit |= sh
        out[name] = float((fp & hit).sum() / nfp) if nfp else 0.0
    return out


# =============================================================== 3. mapy sieci (bez progu)

def average_precision(prob, target, mask=None):
    """AP (pole pod krzywą precyzja-czułość, jak sklearn average_precision_score). target binarny (>= 0,5)."""
    p, t = np.asarray(prob).ravel(), np.asarray(target).ravel() >= 0.5
    if mask is not None:
        m = np.asarray(mask).ravel() > 0
        p, t = p[m], t[m]
    npos = int(t.sum())
    if npos == 0:
        return float('nan')
    o = np.argsort(-p, kind='mergesort')
    p, t = p[o], t[o]
    tp = np.cumsum(t); k = np.arange(1, len(t) + 1)
    last = np.r_[p[1:] != p[:-1], True]  # progi tylko na granicach równych wartości
    prec, rec = tp[last] / k[last], tp[last] / npos
    return float(np.sum(np.diff(np.r_[0.0, rec]) * prec))


def best_threshold(prob, target, mask=None, grid=None):
    """Próg dający największe F1 (do strojenia dekodera na walidacji). -> (próg, F1, P, R)."""
    p, t = np.asarray(prob).ravel(), np.asarray(target).ravel() >= 0.5
    if mask is not None:
        m = np.asarray(mask).ravel() > 0
        p, t = p[m], t[m]
    grid = np.linspace(0.05, 0.95, 19) if grid is None else grid
    best = (0.5, -1.0, 0.0, 0.0)
    for th in grid:
        e = p >= th
        P, R, F = prf(int((e & t).sum()), int((e & ~t).sum()), int((~e & t).sum()))
        if F > best[1]:
            best = (float(th), F, P, R)
    return best


def calibration(prob, target, mask=None, bins=15):
    """ECE (oczekiwany błąd kalibracji, przedziały równej szerokości) i Brier."""
    p, t = np.asarray(prob).ravel(), (np.asarray(target).ravel() >= 0.5).astype(float)
    if mask is not None:
        m = np.asarray(mask).ravel() > 0
        p, t = p[m], t[m]
    if not len(p):
        return {'ECE': float('nan'), 'Brier': float('nan')}
    b = np.minimum((p * bins).astype(int), bins - 1)
    ece = 0.0
    for k in range(bins):
        s = b == k
        if s.any():
            ece += s.mean() * abs(p[s].mean() - t[s].mean())
    return {'ECE': float(ece), 'Brier': float(np.mean((p - t) ** 2))}


def map_metrics(probs, targets, valid=None):
    """Dla każdej głowicy z mapą [T,S] (onset, frame, offset): AP, najlepszy próg i F1 przy nim, ECE, Brier."""
    out = {}
    for k in ('onset', 'frame', 'offset'):
        if k not in probs or k not in targets:
            continue
        mask = None if valid is None else np.broadcast_to(np.asarray(valid)[:, None], targets[k].shape)
        th, f, p, r = best_threshold(probs[k], targets[k], mask)
        out[k] = {'AP': average_precision(probs[k], targets[k], mask), 'best_th': th, 'best_F1': f, **calibration(probs[k], targets[k], mask)}
    return out


# =============================================================== 4. podtrzymanie

def sustain_metrics(ref, est, min_len=0.5, onset_slack=0.15):
    """Dla nut wzorca dłuższych niż min_len (do końca słyszalności): jaka część czasu jest pokryta przez przewidziane nuty tej
    wysokości (zaczynające się nie wcześniej niż onset_slack przed nutą), na ile kawałków pocięto nutę i o ile przedłużono koniec
    (jak w tools/score.py). -> cov [%], cov80 [%], frag, over [s], n."""
    cov, frag, over = [], [], []
    for n in ref:
        ta = n.end(True)
        if ta - n.onset < min_len:
            continue
        pcs = sorted((max(e.onset, n.onset), min(e.offset, ta)) for e in est
                     if round(e.pitch) == round(n.pitch) and e.offset > n.onset and e.onset < ta and e.onset > n.onset - onset_slack)
        pcs = [p for p in pcs if p[1] > p[0]]
        if not pcs:
            cov.append(0.0); frag.append(0); continue
        tot, cur = 0.0, pcs[0]
        for p in pcs[1:]:
            if p[0] <= cur[1]:
                cur = (cur[0], max(cur[1], p[1]))
            else:
                tot += cur[1] - cur[0]; cur = p
        tot += cur[1] - cur[0]
        cov.append(min(1.0, tot / (ta - n.onset))); frag.append(len(pcs))
        for e in est:
            if round(e.pitch) == round(n.pitch) and abs(e.onset - n.onset) < onset_slack:
                over.append(max(0.0, e.offset - max(ta, n.offset)))
    fr = [x for x in frag if x > 0]
    return {'n': len(cov), 'cov': 100 * float(np.mean(cov)) if cov else float('nan'),
            'cov80': 100 * float(np.mean([c >= 0.8 for c in cov])) if cov else float('nan'),
            'frag': float(np.mean(fr)) if fr else float('nan'), 'over': float(np.mean(over)) if over else 0.0,
            '_raw': (cov, frag, over)}


# =============================================================== 5. akordy

PC = {'C': 0, 'C#': 1, 'Db': 1, 'D': 2, 'D#': 3, 'Eb': 3, 'E': 4, 'Fb': 4, 'E#': 5, 'F': 5, 'F#': 6, 'Gb': 6, 'G': 7, 'G#': 8,
      'Ab': 8, 'A': 9, 'A#': 10, 'Bb': 10, 'B': 11, 'Cb': 11, 'B#': 0}
# rodzina akordu: 'maj' / 'min' / inna (w majmin liczą się tylko maj i min, jak w mir_eval) + interwały
QUALITY = {'': ('maj', (0, 4, 7)), 'maj': ('maj', (0, 4, 7)), 'm': ('min', (0, 3, 7)), 'min': ('min', (0, 3, 7)),
           '7': ('maj', (0, 4, 7, 10)), 'maj7': ('maj', (0, 4, 7, 11)), 'm7': ('min', (0, 3, 7, 10)), 'min7': ('min', (0, 3, 7, 10)),
           '6': ('maj', (0, 4, 7, 9)), 'maj6': ('maj', (0, 4, 7, 9)), 'm6': ('min', (0, 3, 7, 9)), 'min6': ('min', (0, 3, 7, 9)),
           '9': ('maj', (0, 4, 7, 10, 2)), 'add9': ('maj', (0, 4, 7, 2)), 'maj(9)': ('maj', (0, 4, 7, 2)),
           'madd9': ('min', (0, 3, 7, 2)), 'min(9)': ('min', (0, 3, 7, 2)), 'm9': ('min', (0, 3, 7, 10, 2)), 'min9': ('min', (0, 3, 7, 10, 2)),
           'mMaj7': ('min', (0, 3, 7, 11)), 'minmaj7': ('min', (0, 3, 7, 11)),
           '5': ('other', (0, 7)), 'sus2': ('other', (0, 2, 7)), 'sus4': ('other', (0, 5, 7)), '7sus4': ('other', (0, 5, 7, 10)),
           'sus4(b7)': ('other', (0, 5, 7, 10)), 'dim': ('other', (0, 3, 6)), 'dim7': ('other', (0, 3, 6, 9)),
           'm7b5': ('other', (0, 3, 6, 10)), 'hdim7': ('other', (0, 3, 6, 10)), 'aug': ('other', (0, 4, 8))}


def parse_chord(label):
    """Etykieta silnika ('Am7', 'C/G') albo Harte ('A:min7', 'C:maj/5', 'N', 'X') -> (prima, rodzina, interwały, bas) albo None."""
    if label is None:
        return None
    s = str(label).strip()
    if s in ('', 'N', 'X'):
        return None
    bass = None
    if '/' in s:
        s, b = s.split('/', 1)
    else:
        b = None
    if ':' in s:
        root, q = s.split(':', 1)
    else:
        root = s[:2] if len(s) > 1 and s[1] in '#b' else s[:1]
        q = s[len(root):]
    if root not in PC:
        return None
    r = PC[root]
    fam, iv = QUALITY.get(q, ('other', (0,)))
    if b:
        if b in PC:
            bass = PC[b]
        else:  # Harte: stopień, np. '5', 'b3', '3'
            deg = {'1': 0, 'b2': 1, '2': 2, 'b3': 3, '3': 4, '4': 5, 'b5': 6, '5': 7, '#5': 8, '6': 9, 'b7': 10, '7': 11}
            bass = (r + deg[b]) % 12 if b in deg else None
    return r, fam, tuple(sorted({(r + i) % 12 for i in iv})), (bass if bass is not None else r)


def _label_at(segs, g):
    for a, b, lab in segs:
        if a <= g < b:
            return lab
    return None


def directional_hamming(ref, est):
    """Jakość segmentacji akordów (mir_eval.chord: under/over-segmentation): 1 - średni nadmiar podziału. -> (under, over, seg)."""
    def dh(a, b):
        tot = sum(e - s for s, e, _ in a)
        if tot <= 0:
            return 0.0
        miss = 0.0
        for s, e, _ in a:
            best = max([min(e, e2) - max(s, s2) for s2, e2, _ in b] + [0.0])
            miss += (e - s) - max(0.0, best)
        return miss / tot
    over, under = dh(ref, est), dh(est, ref)
    return 1 - over, 1 - under, min(1 - over, 1 - under)


def chord_metrics(ref_segs, est_segs, hop=0.1):
    """Siatka co hop: prima, majmin (tylko gdzie wzorzec maj/min, jak mir_eval.chord.majmin), pełna zgodność zbioru dźwięków,
    bas, oraz segmentacja (directional Hamming). Zwraca liczniki (do agregacji) i ułamki."""
    if not ref_segs:
        return {}
    end = max(b for _, b, _ in ref_segs)
    c = defaultdict(int)
    for g in np.arange(hop / 2, end, hop):
        r = parse_chord(_label_at(ref_segs, g))
        e = parse_chord(_label_at(est_segs, g))
        if r is None:
            continue
        c['n'] += 1
        c['root'] += e is not None and e[0] == r[0]
        c['tetrads'] += e is not None and e[2] == r[2]
        c['bass'] += e is not None and e[3] == r[3]
        if r[1] in ('maj', 'min'):
            c['n_mm'] += 1
            c['majmin'] += e is not None and e[0] == r[0] and e[1] == r[1]
    under, over, seg = directional_hamming([s for s in ref_segs if s[2] not in (None, 'N')], [s for s in est_segs if s[2] not in (None, 'N')])
    n, nm = max(1, c['n']), max(1, c['n_mm'])
    return {'_counts': dict(c), 'root': c['root'] / n, 'majmin': c['majmin'] / nm, 'pcset': c['tetrads'] / n, 'bass': c['bass'] / n,
            'underseg': under, 'overseg': over, 'seg': seg}


def chord_strum_accuracy(ref_segs, est_segs, settle=0.45, tail=0.10, hop=0.02):
    """Akord na uderzenie (jak chord_seg w tools/score.py): w oknie [t0+settle, t1-tail] etykieta większości; -> (trafione, n)."""
    ok = n = 0
    for a, b, lab in ref_segs:
        w0, w1 = a + settle, b - tail
        if w1 <= w0:
            continue
        votes = defaultdict(int)
        for g in np.arange(w0, w1, hop):
            e = _label_at(est_segs, g)
            if e:
                votes[str(e).split('/')[0]] += 1
        n += 1
        if votes:
            top = max(votes, key=votes.get)
            pr, pe = parse_chord(lab), parse_chord(top)
            ok += pr is not None and pe is not None and pr[0] == pe[0] and pr[2] == pe[2]
    return ok, n


CHORD_TEMPLATES = [(q, fam, iv) for q, (fam, iv) in QUALITY.items() if q in ('', 'm', '7', 'm7', 'maj7', '5', 'sus2', 'sus4', 'dim', 'aug', '6', 'm6', 'add9')]
NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']


def chords_from_notes(notes, segments=None, hop=0.5, simplicity=0.03):
    """Prosty, przejrzysty estymator akordów z listy nut (do oceny modeli, które same nie nazywają akordów): w każdym oknie
    profil klas dźwięku ważony czasem trwania, dopasowanie wzorców (pokrycie - kara za brakujące i nadmiarowe dźwięki, mała kara
    za złożoność). segments: okna (t0, t1) - np. z prawdy; inaczej stała siatka hop. -> [(t0, t1, nazwa)]."""
    if segments is None:
        end = max((n.offset for n in notes), default=0)
        segments = [(t, t + hop) for t in np.arange(0, end, hop)]
    out = []
    for a, b in segments:
        prof = np.zeros(12)
        bass_p, bass_w = None, 0
        for n in notes:
            o = min(b, n.offset) - max(a, n.onset)
            if o > 0:
                prof[int(round(n.pitch)) % 12] += o
                if bass_p is None or n.pitch < bass_p:
                    bass_p = n.pitch
        if prof.sum() <= 0:
            out.append((a, b, 'N')); continue
        prof /= prof.sum()
        best, bs = None, -1e9
        for r in range(12):
            for q, fam, iv in CHORD_TEMPLATES:
                pcs = {(r + i) % 12 for i in iv}
                inside = sum(prof[p] for p in pcs)
                missing = sum(1 for p in pcs if prof[p] < 0.03) / len(pcs)
                sc = inside - 0.5 * missing - simplicity * len(pcs) + (0.05 if bass_p is not None and int(round(bass_p)) % 12 == r else 0)
                if sc > bs:
                    best, bs = NAMES[r] + q, sc
        out.append((a, b, best))
    return out


# =============================================================== 6. tabulatura

def tab_roll(notes, times, lc, use_audible_end=True):
    """[len(times), n_strings, n_frets] bool z nut z polem string."""
    roll = np.zeros((len(times), lc.n_strings, lc.n_frets), bool)
    for n in notes:
        if n.string is None or not 0 <= n.string < lc.n_strings:
            continue
        fret = int(round(n.pitch)) - lc.tuning[n.string]
        if 0 <= fret < lc.n_frets:
            end = n.end(use_audible_end) if hasattr(n, 'end') else n.offset
            roll[np.searchsorted(times, n.onset):np.searchsorted(times, end), n.string, fret] = True
    return roll


def tab_metrics(ref, est, times, lc, midi_lo=21, n_pitch=88):
    """Wiggins i Kim 2019 (TabCNN): P/R/F1 par (struna, próg) w klatkach, oraz TDR = TP_tab / TP_wysokości (jak często poprawna
    wysokość ma też poprawną strunę). Do tego: % dopasowanych nut (początek 50 ms) z poprawną struną."""
    rr, er = tab_roll(ref, times, lc), tab_roll(est, times, lc)
    tp = int((rr & er).sum()); fp = int((~rr & er).sum()); fn = int((rr & ~er).sum())
    pr = notes_to_roll([n for n in ref if n.string is not None], times, midi_lo, n_pitch)
    pe = notes_to_roll([n for n in est if n.string is not None], times, midi_lo, n_pitch)
    tpp = int((pr & pe).sum())
    m = match_notes(ref, est, 0.05, 50.0, None)
    sk = [(ref[i].string, est[j].string) for i, j in m if ref[i].string is not None and est[j].string is not None]
    P, R, F = prf(tp, fp, fn)
    return {'tp': tp, 'fp': fp, 'fn': fn, 'P': P, 'R': R, 'F1': F, 'TDR': tp / tpp if tpp else float('nan'),
            '_tpp': tpp, 'string_acc': float(np.mean([a == b for a, b in sk])) if sk else float('nan'), '_sk': (sum(a == b for a, b in sk), len(sk))}


# =============================================================== 7. stroik (wynik silnika)

def tuner_metrics(ref, frames, hop=0.05, settle=0.3, tail=0.05):
    """frames: lista (t, midi albo None, f Hz) ze stroika. Chwile z jedną brzmiącą nutą (po settle od początku, tail przed końcem,
    bez innej nuty w pobliżu): % trafionych dźwięków, % chwil z jakimkolwiek wskazaniem, mediana |błędu| w centach."""
    if not ref:
        return {}
    ft = np.array([f[0] for f in frames]) if frames else np.zeros(0)
    end = max(n.offset for n in ref)
    ok = cov = tot = 0
    errs = []
    for g in np.arange(0.5, end - 0.3, hop):
        act = [n for n in ref if n.onset + settle <= g <= n.offset - tail]
        near = [n for n in ref if n.onset <= g <= n.offset + 0.3]
        if len(act) != 1 or len(near) != 1:
            continue
        tot += 1
        k = int(np.searchsorted(ft, g, 'right')) - 1
        if k < 0:
            continue
        _, m, f = frames[k]
        if m is not None:
            cov += 1
            if int(round(m)) == int(round(act[0].pitch)):
                ok += 1
                errs.append(abs(1200 * math.log2(f / float(midi_to_hz(act[0].pitch)))))
    return {'_counts': (ok, cov, tot), 'ok': ok / max(1, tot), 'cov': cov / max(1, tot), 'err_cents': float(np.median(errs)) if errs else float('nan')}


# =============================================================== 8. ocena nagrania i agregacja

def evaluate_file(ref_notes, est_notes, duration=None, ref_chords=None, est_chords=None, has=frozenset({'onset', 'frame', 'offset'}),
                  probs=None, targets=None, valid=None, label_cfg=None, grid_hop=0.01, midi_lo=21, n_pitch=88, tuner_frames=None,
                  chord_from_notes_if_missing=True):
    """Wszystkie metryki dla jednego nagrania. Zwraca słownik metryk + liczniki (klucze z '_' służą agregacji)."""
    dur = duration or max([n.offset for n in ref_notes] + [n.offset for n in est_notes] + [0]) + 0.5
    r = {}
    r['note_on'] = note_prf(ref_notes, est_notes, offset_ratio=None)
    r['note_on100'] = note_prf(ref_notes, est_notes, onset_tol=0.1, offset_ratio=None)
    if 'offset' in has:
        r['note_onoff'] = note_prf(ref_notes, est_notes, offset_ratio=0.2)
    if 'velocity' in has and est_notes and all(getattr(n, 'velocity', None) is not None for n in est_notes):
        r['note_vel'] = note_prf_velocity(ref_notes, est_notes)
    r['timing'] = onset_timing(ref_notes, est_notes)
    g = time_grid(dur, grid_hop)
    rr = notes_to_roll(ref_notes, g, midi_lo, n_pitch)
    er = notes_to_roll(est_notes, g, midi_lo, n_pitch, use_audible_end=False)
    r['frame'] = frame_metrics(rr, er)
    r['chroma'] = frame_metrics(chroma_roll(rr, midi_lo), chroma_roll(er, midi_lo))
    r['harm_err'] = harmonic_errors(rr, er)
    if any(n.audible_end is not None for n in ref_notes) or 'offset' in has:
        r['sustain'] = sustain_metrics(ref_notes, est_notes)
    if ref_chords:
        ec = est_chords
        if not ec and chord_from_notes_if_missing:
            ec = chords_from_notes(est_notes, [(a, b) for a, b, _ in ref_chords])
        r['chord'] = chord_metrics(ref_chords, ec or [])
        r['chord_strum'] = chord_strum_accuracy(ref_chords, ec or [])
    if 'tab' in has and label_cfg is not None and any(getattr(n, 'string', None) is not None for n in est_notes):
        r['tab'] = tab_metrics(ref_notes, est_notes, g, label_cfg, midi_lo, n_pitch)
    if probs is not None and targets is not None:
        r['maps'] = map_metrics(probs, targets, valid)
    if tuner_frames is not None:
        r['tuner'] = tuner_metrics(ref_notes, tuner_frames)
    r['_n_ref'], r['_n_est'] = len(ref_notes), len(est_notes)
    return r


def _get(r, path):
    for k in path.split('.'):
        if not isinstance(r, dict) or k not in r:
            return None
        r = r[k]
    return r


SUMMARY = [  # (nazwa w tabeli, ścieżka, rodzaj: 'prf' = mikro z tp/fp/fn + makro z F1, 'mean' = średnia po plikach)
    ('note_F1', 'note_on', 'prf'), ('note_P', 'note_on.P', 'mean'), ('note_R', 'note_on.R', 'mean'),
    ('note100_F1', 'note_on100', 'prf'), ('onoff_F1', 'note_onoff', 'prf'), ('vel_F1', 'note_vel', 'prf'),
    ('frame_F1', 'frame', 'prf'), ('frame_Acc', 'frame.Acc', 'mean'), ('E_tot', 'frame.E_tot', 'mean'),
    ('chroma_F1', 'chroma', 'prf'), ('oct_err', 'harm_err.oktawa', 'mean'),
    ('on_med_ms', 'timing.med_abs', 'mean_ms'), ('on_bias_ms', 'timing.bias', 'mean_ms'),
    ('cov', 'sustain.cov', 'mean'), ('cov80', 'sustain.cov80', 'mean'), ('frag', 'sustain.frag', 'mean'),
    ('chord_root', 'chord.root', 'mean'), ('chord_majmin', 'chord.majmin', 'mean'), ('chord_seg', 'chord.seg', 'mean'),
    ('strum_acc', 'chord_strum', 'ratio'),
    ('tab_F1', 'tab', 'prf'), ('TDR', 'tab.TDR', 'mean'), ('string_acc', 'tab.string_acc', 'mean'),
    ('AP_onset', 'maps.onset.AP', 'mean'), ('AP_frame', 'maps.frame.AP', 'mean'), ('th_onset', 'maps.onset.best_th', 'mean'),
    ('ECE_frame', 'maps.frame.ECE', 'mean'),
    ('tune_ok', 'tuner.ok', 'mean'), ('tune_cents', 'tuner.err_cents', 'mean'),
]


def summarize_rows(rows, micro=True):
    """Jedna linia metryk dla zbioru plików. Dla 'prf': mikro (suma tp/fp/fn po plikach) albo makro (średnia F1 po plikach,
    jak w publikacjach i tools/guitarset_eval.py). Wartości w %, czasy w ms."""
    out = {'n': len(rows)}
    for name, path, kind in SUMMARY:
        vals = [_get(r, path) for r in rows]
        vals = [v for v in vals if v is not None]
        if not vals:
            continue
        if kind == 'prf':
            if micro:
                tp, fp, fn = (sum(v[k] for v in vals) for k in ('tp', 'fp', 'fn'))
                out[name] = 100 * prf(tp, fp, fn)[2]
            else:
                out[name] = 100 * float(np.mean([v['F1'] for v in vals]))
        elif kind == 'ratio':
            ok, n = sum(v[0] for v in vals), sum(v[1] for v in vals)
            if n:
                out[name] = 100 * ok / n
        else:
            v = np.array([x for x in vals if not (isinstance(x, float) and math.isnan(x))], float)
            if len(v):
                scale = 1000 if kind == 'mean_ms' else (100 if name in ('note_P', 'note_R', 'frame_Acc', 'oct_err', 'chord_root', 'chord_majmin',
                                                                       'chord_seg', 'TDR', 'string_acc', 'AP_onset', 'AP_frame', 'tune_ok') else 1)
                out[name] = scale * float(v.mean())
    return out


def aggregate(rows, groups=None, micro=True):
    """rows: lista wyników evaluate_file; groups: lista nazw grup (ta sama długość). -> {grupa: podsumowanie, 'RAZEM': ...}."""
    res = {}
    if groups is not None:
        by = defaultdict(list)
        for r, g in zip(rows, groups):
            by[g].append(r)
        for g in sorted(by):
            res[g] = summarize_rows(by[g], micro)
    res['RAZEM'] = summarize_rows(rows, micro)
    return res


def per_file_score(r, metric='note_F1'):
    """Wartość jednej metryki dla jednego pliku (do bootstrapu)."""
    path = {name: (p, k) for name, p, k in SUMMARY}[metric]
    v = _get(r, path[0])
    if v is None:
        return float('nan')
    if path[1] == 'prf':
        return 100 * v['F1']
    if path[1] == 'ratio':
        return 100 * v[0] / v[1] if v[1] else float('nan')
    return float(v)


def bootstrap_ci(values, n=2000, alpha=0.05, seed=0):
    """Przedział ufności średniej po plikach (bootstrap percentylowy). -> (średnia, dolna, górna)."""
    v = np.array([x for x in values if not math.isnan(x)], float)
    if not len(v):
        return float('nan'), float('nan'), float('nan')
    rng = np.random.default_rng(seed)
    m = v[rng.integers(0, len(v), (n, len(v)))].mean(1)
    return float(v.mean()), float(np.percentile(m, 100 * alpha / 2)), float(np.percentile(m, 100 * (1 - alpha / 2)))


def paired_bootstrap(a, b, n=5000, seed=0):
    """Czy system A jest lepszy od B na tych samych plikach: różnica średnich, 95 % przedział, p (jednostronne: P(różnica <= 0))."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    ok = ~(np.isnan(a) | np.isnan(b))
    d = a[ok] - b[ok]
    if not len(d):
        return {'diff': float('nan'), 'lo': float('nan'), 'hi': float('nan'), 'p': float('nan'), 'n': 0}
    rng = np.random.default_rng(seed)
    m = d[rng.integers(0, len(d), (n, len(d)))].mean(1)
    return {'diff': float(d.mean()), 'lo': float(np.percentile(m, 2.5)), 'hi': float(np.percentile(m, 97.5)),
            'p': float((m <= 0).mean()), 'n': int(len(d))}


def format_table(agg, cols=None):
    cols = cols or [c for c in ['n'] + [s[0] for s in SUMMARY] if any(c in v for v in agg.values())]
    w = max(12, max(len(k) for k in agg) + 1)
    lines = ['%-*s' % (w, 'grupa') + ''.join('%13s' % c for c in cols)]
    for k, v in agg.items():
        lines.append('%-*s' % (w, k) + ''.join('%13s' % (('%d' % v[c]) if c == 'n' else ('%.2f' % v[c]) if c in v else '-') for c in cols))
    return '\n'.join(lines)
