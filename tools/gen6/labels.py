"""labels.py - mapy celów dla sieci z listy nut (wspólne dla wszystkich formatów danych).

Dla T klatek i S półtonów:
  frame    [T,S]  1, gdy nuta brzmi w środku okna klatki (od pół klatki przed początkiem do min(koniec, koniec słyszalności))
  onset    [T,S]  1 w klatce najbliższej początkowi, onset_soft w sąsiednich
  offset   [T,S]  to samo dla końca
  velocity [T,S]  głośność 0..1 w klatkach początku (vel_mask = 1 tam, gdzie jest znana)
  tab      [T,6]  numer klasy na strunę: 0 = milczy, 1 + próg (0..n_frets-1); -1 = nieznane
Dostępność (avail) mówi, które etykiety źródło ma naprawdę (Example.has); strata ignoruje pozostałe.
"""
from __future__ import annotations
import numpy as np
from .config import FeatureConfig, LabelConfig

HEADS = ('onset', 'frame', 'offset', 'velocity', 'tab')


def make_targets(ex, T, f: FeatureConfig, lc: LabelConfig):
    S = f.n_semis
    fr = np.zeros((T, S), np.float32); on = np.zeros_like(fr); off = np.zeros_like(fr)
    vel = np.zeros_like(fr); vmask = np.zeros_like(fr)
    tab = np.zeros((T, lc.n_strings), np.int64)
    cen = f.frame_center(np.arange(T))
    has = ex.has
    for n in ex.notes:
        s = int(round(n.pitch)) - f.midi_lo
        if s < 0 or s >= S:
            continue
        end = n.end(lc.use_audible_end)
        # od pół klatki przed początkiem: klatka "początku" (najbliższa) zawsze też "brzmi" (w gen 5 mogła mieć brzmi = 0,
        # bo jej środek wypadał tuż przed początkiem, a dekoder wymaga p(brzmi) >= 0,3 przy początku)
        act = (cen >= n.onset - 0.5 * f.frame_sec) & (cen <= max(end, n.onset))
        fr[act, s] = 1
        k = int(round(f.time_to_frame(n.onset)))
        for d in range(-lc.onset_width, lc.onset_width + 1):
            if 0 <= k + d < T:
                on[k + d, s] = max(on[k + d, s], 1.0 if d == 0 else lc.onset_soft)
        if 0 <= k < T and n.velocity is not None:
            vel[k, s] = n.velocity; vmask[k, s] = 1
        ke = int(round(f.time_to_frame(n.offset)))
        for d in range(-lc.offset_width, lc.offset_width + 1):
            if 0 <= ke + d < T:
                off[ke + d, s] = max(off[ke + d, s], 1.0 if d == 0 else lc.offset_soft)
        if n.string is not None and 0 <= n.string < lc.n_strings:
            fret = int(round(n.pitch)) - lc.tuning[n.string]
            if 0 <= fret < lc.n_frets:
                tab[act, n.string] = 1 + fret
    if 'tab' not in has:
        tab[:] = -1
    avail = np.array([h in has for h in HEADS], np.float32)
    if 'velocity' not in has:
        vmask[:] = 0
    return {'onset': on, 'frame': fr, 'offset': off, 'velocity': vel, 'vel_mask': vmask, 'tab': tab}, avail
