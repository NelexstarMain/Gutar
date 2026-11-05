"""decode.py - nuty z map sieci (prawdopodobieństwa numpy). Ten sam algorytm co dekoder gen 5 w C++, rozszerzony o głowicę końca,
głośność, strunę i scalanie duplikatów.

Nuta zaczyna się w lokalnym maksimum p(początek) >= th_onset (przy p(brzmi) >= 0,3) albo, bez początku, gdy p(brzmi) >= th_start przez
min_frames klatek; trwa, dopóki p(brzmi) >= th_frame; kończy się po gap_frames klatkach poniżej progu albo w lokalnym maksimum
p(koniec) >= th_offset. Nowy początek w trakcie nuty = ponowne szarpnięcie.
"""
from __future__ import annotations
import numpy as np
from .config import DecodeConfig, FeatureConfig, LabelConfig
from .data import Note


def apply_decode_override(cfg, ckpt_path):
    """Dostrojone progi dekodera: plik decode.json obok punktu kontrolnego (wynik tune_decoder.py) nadpisuje cfg.decode."""
    import json
    import os
    p = os.path.join(os.path.dirname(os.path.abspath(ckpt_path)), 'decode.json')
    if os.path.exists(p):
        for k, v in json.load(open(p)).get('decode', {}).items():
            if hasattr(cfg.decode, k):
                setattr(cfg.decode, k, type(getattr(cfg.decode, k))(v))
    return cfg


def _peaks(x, th):
    """lokalne maksima >= th wzdłuż osi 0 (pierwsze z równych)."""
    prev = np.vstack([np.full((1,) + x.shape[1:], -np.inf), x[:-1]])
    nxt = np.vstack([x[1:], np.full((1,) + x.shape[1:], -np.inf)])
    return (x >= th) & (x >= prev) & (x > nxt)


def decode_notes(p, f: FeatureConfig, d: DecodeConfig, lc: LabelConfig = None):
    """p: słownik z Gen6.predict. Zwraca listę Note z conf (średnie p(brzmi)) w meta-polu velocity/string, gdy są głowice."""
    fr, on = p['frame'], p['onset']
    off = p.get('offset')
    T, S = fr.shape
    pk_on = _peaks(on, d.th_onset) & (fr >= d.th_onset_frame)
    pk_off = _peaks(off, d.th_offset) if off is not None else np.zeros_like(fr, bool)
    cen = f.frame_center(np.arange(T))
    half = 0.5 * f.hop / f.sr
    out = []
    for s in range(S):
        start, last, gap, conf = -1, -1, 0, []

        def finish():
            if start < 0 or last - start + 1 < d.min_frames:
                return
            t0 = max(0.0, cen[start])
            t1 = max(t0 + d.min_dur, cen[last] + half)
            n = Note(float(f.midi_lo + s), float(t0), float(t1))
            if 'velocity' in p:
                n.velocity = float(p['velocity'][start, s])
            if 'tab' in p and lc is not None:
                n.string = _string_for(p['tab'], start, last, f.midi_lo + s, lc)
            n.audible_end = None
            out.append((n, float(np.mean(conf)) if conf else 0.5))
        for t in range(T):
            if pk_on[t, s]:
                if start >= 0:
                    finish()
                start, last, gap, conf = t, t, 0, []
            elif start < 0 and fr[t, s] >= d.th_start and t + d.min_frames - 1 < T and (fr[t:t + d.min_frames, s] >= d.th_start).all():
                start, last, gap, conf = t, t, 0, []
            if start >= 0:
                if fr[t, s] >= d.th_frame:
                    last, gap = t, 0
                    conf.append(fr[t, s])
                else:
                    gap += 1
                    if gap > d.gap_frames:
                        finish(); start = -1
                        continue
                if pk_off[t, s] and t > start:
                    last = t
                    finish(); start = -1
        finish()
    out.sort(key=lambda nc: (nc[0].onset, nc[0].pitch))
    return merge_duplicates(out, d.merge_sec)


def _string_for(tab, a, b, midi, lc: LabelConfig):
    """struna o największym średnim p(ta struna gra ten próg) w klatkach nuty."""
    best, bs = None, -1.0
    for s, op in enumerate(lc.tuning):
        fret = midi - op
        if 0 <= fret < lc.n_frets:
            v = float(tab[a:b + 1, s, 1 + fret].mean())
            if v > bs:
                best, bs = s, v
    return best


def merge_duplicates(nc, merge_sec):
    """Ta sama wysokość, początki bliżej niż merge_sec: jedna nuta (dłuższa). Zwraca listę Note (pewność w atrybucie conf)."""
    res = []
    last = {}
    for n, c in nc:
        k = n.pitch
        j = last.get(k)
        if j is not None and n.onset - res[j].onset < merge_sec:
            res[j].offset = max(res[j].offset, n.offset)
            continue
        n.conf = c
        last[k] = len(res)
        res.append(n)
    return res


def frames_to_pianoroll(p, th=0.5):
    """[T,S] bool: obecność dźwięku wprost z mapy (do metryk klatkowych bez dekodera)."""
    return p['frame'] >= th
