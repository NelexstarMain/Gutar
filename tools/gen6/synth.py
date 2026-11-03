"""synth.py - małe syntetyczne nagrania gitary do testów i próbnego uruchomienia (nie do uczenia właściwego modelu).
Szarpnięta struna: alikwoty z nieharmonicznością, zanik zależny od częstotliwości, losowa struna i próg, akordy i melodie."""
from __future__ import annotations
import numpy as np
from .config import LabelConfig
from .data import Example, Note


def pluck(f0, dur, sr, vel=0.7, B=1e-4, rng=None):
    rng = rng or np.random.default_rng()
    n = int(dur * sr)
    t = np.arange(n) / sr
    y = np.zeros(n)
    for h in range(1, 16):
        fh = h * f0 * np.sqrt(1 + B * h * h)
        if fh > 0.45 * sr:
            break
        y += (1.0 / h) * np.exp(-t * (1.5 + 0.6 * h)) * np.sin(2 * np.pi * fh * t + rng.uniform(0, 2 * np.pi))
    a = min(n, int(0.003 * sr))
    y[:a] *= np.linspace(0, 1, a)
    r = min(n, int(0.03 * sr))
    y[n - r:] *= np.linspace(1, 0, r)
    return vel * y


def random_example(i, sr=11025, dur=6.0, seed=0, lc: LabelConfig = None, noise=0.003):
    lc = lc or LabelConfig()
    rng = np.random.default_rng(seed * 1000 + i)
    x = np.zeros(int(dur * sr) + sr)
    notes, chords = [], []
    t = 0.3
    while t < dur - 0.6:
        if rng.uniform() < 0.5:  # akord: kilka strun naraz, jeden próg bazowy
            base = int(rng.integers(0, 8))
            strings = sorted(rng.choice(6, size=int(rng.integers(3, 6)), replace=False))
            ln = float(rng.uniform(0.6, 1.4))
            for k, s in enumerate(strings):
                fret = base + int(rng.integers(0, 3))
                m = lc.tuning[s] + fret
                t0 = t + 0.012 * k
                v = float(rng.uniform(0.4, 1.0))
                notes.append(Note(float(m), t0, t0 + ln, v, int(s)))
            t += ln + float(rng.uniform(0.05, 0.3))
        else:  # melodia
            for _ in range(int(rng.integers(2, 6))):
                s = int(rng.integers(0, 6)); fret = int(rng.integers(0, 12))
                ln = float(rng.uniform(0.15, 0.6))
                notes.append(Note(float(lc.tuning[s] + fret), t, t + ln, float(rng.uniform(0.4, 1.0)), s))
                t += ln + float(rng.uniform(0.0, 0.1))
                if t > dur - 0.6:
                    break
    for n in notes:
        y = pluck(440 * 2 ** ((n.pitch - 69) / 12), n.offset - n.onset, sr, n.velocity, rng=rng)
        a = int(n.onset * sr)
        x[a:a + len(y)] += y
    x = x[:int(dur * sr)]
    x = 0.3 * x / (np.abs(x).max() + 1e-9) + noise * rng.standard_normal(len(x))
    ex = Example('synth_%03d' % i, 'synth', notes, [], frozenset({'onset', 'frame', 'offset', 'velocity', 'tab'}),
                 duration=dur, group='synth', split='val' if i % 5 == 0 else 'train')
    ex.meta['signal'] = x.astype(np.float32)
    return ex


def random_set(n, sr=11025, dur=6.0, seed=0):
    return [random_example(i, sr, dur, seed) for i in range(n)]
