"""Testy funkcji ewaluacyjnych: przypadki ręczne i zgodność z mir_eval (gdy zainstalowane)."""
import itertools
import numpy as np
import pytest
from tools.gen6 import metrics as M
from tools.gen6.config import LabelConfig
from tools.gen6.data import Note


def rand_notes(rng, n=40, dur=20.0):
    out = []
    for _ in range(n):
        t = rng.uniform(0, dur)
        out.append(Note(float(rng.integers(40, 80)), t, t + rng.uniform(0.05, 1.5), float(rng.uniform(0.2, 1.0)), int(rng.integers(0, 6))))
    return sorted(out, key=lambda n: n.onset)


def jitter(rng, notes, on=0.04, off=0.3, drop=0.2, add=10, octave=0.1):
    est = []
    for n in notes:
        if rng.uniform() < drop:
            continue
        p = n.pitch + (12 if rng.uniform() < octave else 0)
        o = max(0.0, n.onset + rng.uniform(-on, on))
        est.append(Note(p, o, max(o + 0.02, n.offset + rng.uniform(-off, off)), float(np.clip(n.velocity + rng.normal(0, 0.1), 0, 1)), n.string))
    est += rand_notes(rng, add)
    return sorted(est, key=lambda n: n.onset)


def test_perfect_and_shifted():
    ref = [Note(60, 1.0, 2.0), Note(64, 1.0, 2.0), Note(67, 3.0, 3.5)]
    assert M.note_prf(ref, ref)['F1'] == 1.0
    assert M.note_prf(ref, ref, offset_ratio=0.2)['F1'] == 1.0
    shifted = [Note(n.pitch, n.onset + 0.06, n.offset) for n in ref]
    assert M.note_prf(ref, shifted)['F1'] == 0.0
    assert M.note_prf(ref, shifted, onset_tol=0.1)['F1'] == 1.0
    assert M.note_prf(ref, [])['F1'] == 0.0 and M.note_prf([], ref)['fp'] == 3


def test_hopcroft_karp_is_maximum():
    rng = np.random.default_rng(3)
    for _ in range(50):
        nl, nr = int(rng.integers(1, 7)), int(rng.integers(1, 7))
        A = rng.uniform(size=(nl, nr)) < 0.4
        adj = [list(np.nonzero(A[i])[0]) for i in range(nl)]
        m = M.hopcroft_karp(adj, nl, nr)
        assert len({j for _, j in m}) == len(m) and all(A[i, j] for i, j in m)
        best = 0
        for perm in itertools.permutations(range(max(nl, nr)), nl):
            best = max(best, sum(1 for i, j in enumerate(perm) if j < nr and A[i, j]))
        assert len(m) == best


def test_against_mir_eval():
    me = pytest.importorskip('mir_eval')
    rng = np.random.default_rng(0)
    for k in range(10):
        ref = rand_notes(rng, 60)
        est = jitter(rng, ref)
        iv = lambda ns: np.array([[n.onset, n.offset] for n in ns])
        hz = lambda ns: np.array([440 * 2 ** ((n.pitch - 69) / 12) for n in ns])
        P, R, F, _ = me.transcription.precision_recall_f1_overlap(iv(ref), hz(ref), iv(est), hz(est), offset_ratio=None)
        r = M.note_prf(ref, est)
        assert abs(r['F1'] - F) < 1e-9 and abs(r['P'] - P) < 1e-9
        P, R, F, O = me.transcription.precision_recall_f1_overlap(iv(ref), hz(ref), iv(est), hz(est))
        r = M.note_prf(ref, est, offset_ratio=0.2)
        assert abs(r['F1'] - F) < 1e-9 and abs(r['overlap'] - O) < 1e-9
        vel = lambda ns: 127 * np.array([n.velocity for n in ns])
        P, R, F, _ = me.transcription_velocity.precision_recall_f1_overlap(iv(ref), hz(ref), vel(ref), iv(est), hz(est), vel(est))
        r = M.note_prf_velocity(ref, est)
        assert abs(r['F1'] - F) < 1e-9
        # klatki: mir_eval.multipitch na tej samej siatce
        g = M.time_grid(22.0, 0.01)
        rr, er = M.notes_to_roll(ref, g), M.notes_to_roll(est, g)
        to_f = lambda roll: [np.array([440 * 2 ** ((21 + s - 69) / 12) for s in np.nonzero(row)[0]]) for row in roll]
        sc = me.multipitch.metrics(g, to_f(rr), g, to_f(er))
        fm = M.frame_metrics(rr, er)
        assert abs(fm['P'] - sc[0]) < 1e-9 and abs(fm['R'] - sc[1]) < 1e-9 and abs(fm['Acc'] - sc[2]) < 1e-9
        assert abs(fm['E_sub'] - sc[3]) < 1e-9 and abs(fm['E_miss'] - sc[4]) < 1e-9
        assert abs(fm['E_fa'] - sc[5]) < 1e-9 and abs(fm['E_tot'] - sc[6]) < 1e-9


def test_frame_and_harmonic_errors():
    g = M.time_grid(2.0, 0.01)
    ref = [Note(48, 0.0, 2.0)]
    est = [Note(48, 0.0, 2.0), Note(60, 0.0, 2.0)]  # oktawa wyżej = alikwot
    rr, er = M.notes_to_roll(ref, g), M.notes_to_roll(est, g)
    fm = M.frame_metrics(rr, er)
    assert fm['R'] == 1.0 and abs(fm['P'] - 0.5) < 1e-9
    he = M.harmonic_errors(rr, er)
    assert he['oktawa'] == 1.0 and he['kwinta'] == 0.0
    ch = M.frame_metrics(M.chroma_roll(rr, 21), M.chroma_roll(er, 21))
    assert ch['F1'] == 1.0


def test_map_metrics():
    t = np.array([0, 0, 1, 1, 0, 1], float)
    assert M.average_precision(t, t) == 1.0
    p = np.array([0.9, 0.8, 0.7, 0.6, 0.5, 0.4])
    # ręcznie: kolejność 0,0,1,1,0,1 -> precyzje przy trafieniach 1/3, 2/4, 3/6
    assert abs(M.average_precision(p, t) - (1 / 3 + 2 / 4 + 3 / 6) / 3) < 1e-12
    th, f, P, R = M.best_threshold(np.array([0.1, 0.2, 0.8, 0.9]), np.array([0, 0, 1, 1]))
    assert f == 1.0 and 0.2 < th <= 0.8
    c = M.calibration(np.array([0.0, 1.0]), np.array([0, 1]))
    assert c['ECE'] == 0 and c['Brier'] == 0


def test_sustain():
    ref = [Note(60, 0.0, 2.0, audible_end=1.6)]
    est = [Note(60, 0.0, 0.8), Note(60, 1.0, 1.6)]
    s = M.sustain_metrics(ref, est)
    assert abs(s['cov'] - 100 * 1.4 / 1.6) < 1e-9 and s['frag'] == 2 and s['cov80'] == 100.0


def test_chords():
    assert M.parse_chord('Am7')[:3] == (9, 'min', (0, 4, 7, 9))
    assert M.parse_chord('A:min7')[:3] == M.parse_chord('Am7')[:3]
    assert M.parse_chord('C/G')[3] == 7 and M.parse_chord('C:maj/5')[3] == 7
    assert M.parse_chord('N') is None
    ref = [(0.0, 2.0, 'C'), (2.0, 4.0, 'A:min')]
    est = [(0.0, 2.0, 'C'), (2.0, 4.0, 'C')]
    c = M.chord_metrics(ref, est)
    assert abs(c['root'] - 0.5) < 0.03 and abs(c['majmin'] - 0.5) < 0.03
    assert M.chord_strum_accuracy(ref, est) == (1, 2)
    notes = [Note(48, 0, 2), Note(52, 0, 2), Note(55, 0, 2), Note(57, 2, 4), Note(60, 2, 4), Note(64, 2, 4)]
    lab = M.chords_from_notes(notes, [(0, 2), (2, 4)])
    assert [l for _, _, l in lab] == ['C', 'Am']


def test_tab_and_evaluate_file():
    lc = LabelConfig()
    ref = [Note(45, 0.0, 1.0, string=1), Note(50, 0.0, 1.0, string=2)]
    est_good = [Note(45, 0.0, 1.0, string=1), Note(50, 0.0, 1.0, string=2)]
    est_bad = [Note(45, 0.0, 1.0, string=0), Note(50, 0.0, 1.0, string=1)]  # te same wysokości, złe struny
    g = M.time_grid(1.5)
    assert M.tab_metrics(ref, est_good, g, lc)['F1'] == 1.0
    tb = M.tab_metrics(ref, est_bad, g, lc)
    assert tb['F1'] == 0.0 and tb['TDR'] == 0.0 and tb['string_acc'] == 0.0
    r = M.evaluate_file(ref, est_good, 1.5, has=frozenset({'onset', 'frame', 'offset', 'tab'}), label_cfg=lc)
    agg = M.aggregate([r, r], ['a', 'b'])
    assert agg['RAZEM']['note_F1'] == 100 and agg['RAZEM']['tab_F1'] == 100 and agg['a']['n'] == 1
    assert 'note_F1' in M.format_table(agg)


def test_bootstrap():
    m, lo, hi = M.bootstrap_ci([1, 2, 3, 4, 5])
    assert lo <= m <= hi and m == 3
    r = M.paired_bootstrap([5, 6, 7, 8], [1, 2, 3, 4])
    assert r['diff'] == 4 and r['p'] == 0.0
