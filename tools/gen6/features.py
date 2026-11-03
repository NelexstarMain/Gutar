"""features.py - HCQT w numpy, ta sama definicja co src/gt_hcqt.hpp (amplituda = maksimum widma w +-1/6 półtonu wokół h*f(p),
dB względem percentyla nagrania), ale krok, zakres wysokości i alikwoty biorą się z FeatureConfig.

Wynik: float32 [T, C, P], C = len(harm_long) + len(harm_short), P = n_semis * bins_per_semi, bin p = 3s+1 to środek półtonu s.
"""
from __future__ import annotations
import hashlib
import os
import numpy as np
from .config import FeatureConfig


def bin_midi(cfg: FeatureConfig, p):
    return cfg.midi_lo + (np.asarray(p) - (cfg.bins_per_semi // 2)) / cfg.bins_per_semi


def _ranges(cfg, harms, win):
    M = win * cfg.zero_pad
    bh = cfg.sr / M
    p = np.arange(cfg.n_bins)
    f = 440.0 * 2 ** ((bin_midi(cfg, p) - 69) / 12)
    a = np.zeros((len(harms), cfg.n_bins), np.int64)
    b = np.zeros_like(a)
    for k, h in enumerate(harms):
        fh = h * f
        lo = np.maximum(1, np.floor(fh * 2 ** (-1 / 72) / bh)).astype(np.int64)
        hi = np.minimum(M // 2 - 1, np.maximum(lo, np.ceil(fh * 2 ** (1 / 72) / bh))).astype(np.int64)
        bad = fh > 0.46 * cfg.sr
        lo[bad], hi[bad] = 1, 0  # pusty zakres = alikwot ponad Nyquistem
        a[k], b[k] = lo, hi
    return a, b


def _frames(x, win, hop, T, centers):
    """Okna długości win o środkach `centers` (próbki), z dopełnieniem zerami poza sygnałem."""
    pad = win
    xp = np.concatenate([np.zeros(pad, np.float32), x, np.zeros(pad + win, np.float32)])
    idx = (centers - win // 2 + pad)[:, None] + np.arange(win)[None]
    return xp[idx]


def _band_max(mag, a, b):
    """max(mag[:, a[k,p]..b[k,p]]) dla każdego (k, p); pusty zakres -> 0."""
    width = int((b - a).max()) + 1 if b.size else 1
    out = np.zeros((mag.shape[0],) + a.shape, np.float32)
    for j in range(max(1, width)):
        idx = np.minimum(a + j, np.maximum(b, a))
        v = mag[:, idx]
        ok = (a + j <= b)[None]
        out = np.where(ok, np.maximum(out, v), out)
    return out


def hcqt(x, cfg: FeatureConfig, chunk=512):
    """x: mono float32 o częstotliwości cfg.sr. Zwraca [T, C, P]."""
    x = np.asarray(x, np.float32)
    N = len(x)
    T = (N - cfg.win_long) // cfg.hop + 1 if N >= cfg.win_long else 0
    C, P = cfg.n_channels, cfg.n_bins
    if T <= 0:
        return np.zeros((0, C, P), np.float32)
    aL, bL = _ranges(cfg, cfg.harm_long, cfg.win_long)
    aS, bS = _ranges(cfg, cfg.harm_short, cfg.win_short)
    wL = np.hanning(cfg.win_long + 1)[:cfg.win_long].astype(np.float32)  # okresowe okno Hanna jak w gt_dsp.hpp
    wS = np.hanning(cfg.win_short + 1)[:cfg.win_short].astype(np.float32)
    out = np.zeros((T, C, P), np.float32)
    nL = len(cfg.harm_long)
    for t0 in range(0, T, chunk):
        t = np.arange(t0, min(T, t0 + chunk))
        cen = t * cfg.hop + cfg.win_long // 2
        fl = _frames(x, cfg.win_long, cfg.hop, len(t), cen)
        fl = (fl - fl.mean(axis=1, keepdims=True)) * wL
        ml = np.abs(np.fft.rfft(fl, cfg.win_long * cfg.zero_pad, axis=1)).astype(np.float32) * (4.0 / cfg.win_long)
        fs = _frames(x, cfg.win_short, cfg.hop, len(t), cen) * wS
        ms = np.abs(np.fft.rfft(fs, cfg.win_short * cfg.zero_pad, axis=1)).astype(np.float32) * (4.0 / cfg.win_short)
        out[t, :nL] = 20 * np.log10(_band_max(ml, aL, bL) + 1e-9)
        out[t, nL:] = 20 * np.log10(_band_max(ms, aS, bS) + 1e-9)
    validL, validS = bL >= aL, bS >= aS
    sub = out[::4]
    refL = np.percentile(sub[:, :nL][np.broadcast_to(validL, sub[:, :nL].shape)], cfg.ref_pct) if validL.any() else -60
    refS = np.percentile(sub[:, nL:][np.broadcast_to(validS, sub[:, nL:].shape)], cfg.ref_pct) if validS.any() else -60
    out[:, :nL] = (out[:, :nL] - refL) / cfg.db_range + 1
    out[:, nL:] = (out[:, nL:] - refS) / cfg.db_range + 1
    np.clip(out, 0, cfg.clip_hi, out=out)
    out[:, :nL][:, ~validL] = 0
    out[:, nL:][:, ~validS] = 0
    return out


def load_engine_dump(path):
    """Zrzut HCQT z silnika C++ (GT_DUMPH): int32 [T, C, P], potem float32 T x C x P. Zawsze krok 512 przy 11025 Hz."""
    b = np.fromfile(path, np.uint8)
    T, C, P = np.frombuffer(b[:12].tobytes(), np.int32)
    return np.frombuffer(b[12:].tobytes(), np.float32).reshape(T, C, P).copy()


def engine_dump_config():
    """FeatureConfig opisujący zrzuty gen 5 (do etykiet i dekodera, gdy wejściem są zrzuty z C++)."""
    return FeatureConfig(hop=512)


def cache_key(path, cfg: FeatureConfig):
    st = os.stat(path)
    s = '%s|%d|%d|%r' % (os.path.abspath(path), st.st_size, int(st.st_mtime), sorted(vars(cfg).items()))
    return hashlib.sha1(s.encode()).hexdigest()[:20]


def cached_hcqt(audio_path, cfg: FeatureConfig, cache_dir=None, loader=None):
    """HCQT pliku z pamięcią podręczną na dysku (cechy liczone raz na konfigurację)."""
    from .audio import load_audio
    if cache_dir:
        os.makedirs(cache_dir, exist_ok=True)
        cp = os.path.join(cache_dir, cache_key(audio_path, cfg) + '.npy')
        if os.path.exists(cp):
            return np.load(cp)
    x = loader(audio_path) if loader else load_audio(audio_path, cfg.sr, cfg.frontend)
    X = hcqt(x, cfg)
    if cache_dir:
        np.save(cp, X)
    return X
