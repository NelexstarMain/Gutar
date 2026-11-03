"""audio.py - wczytywanie WAV (PCM 8/16/24/32 bit, float 32/64, WAVE_FORMAT_EXTENSIBLE) i zmiana częstotliwości próbkowania.
Bez scipy: zmiana próbkowania przez FFT w nakładających się blokach (dokładna dla sygnałów pasmowo ograniczonych)."""
from __future__ import annotations
import struct
import numpy as np


def read_wav(path):
    """Zwraca (mono float32 w [-1, 1], częstotliwość próbkowania)."""
    with open(path, 'rb') as f:
        data = f.read()
    if data[:4] != b'RIFF' or data[8:12] != b'WAVE':
        raise ValueError('%s: to nie jest plik WAV' % path)
    pos, fmt, raw = 12, None, None
    while pos + 8 <= len(data):
        cid, size = data[pos:pos + 4], struct.unpack('<I', data[pos + 4:pos + 8])[0]
        body = data[pos + 8:pos + 8 + size]
        if cid == b'fmt ':
            tag, ch, sr, _, _, bits = struct.unpack('<HHIIHH', body[:16])
            if tag == 0xFFFE and len(body) >= 26:
                tag = struct.unpack('<H', body[24:26])[0]
            fmt = (tag, ch, sr, bits)
        elif cid == b'data':
            raw = body
        pos += 8 + size + (size & 1)
    if fmt is None or raw is None:
        raise ValueError('%s: brak fmt/data' % path)
    tag, ch, sr, bits = fmt
    if tag == 3:
        x = np.frombuffer(raw[:len(raw) // (bits // 8) * (bits // 8)], np.float32 if bits == 32 else np.float64).astype(np.float32)
    elif tag == 1:
        if bits == 8:
            x = (np.frombuffer(raw, np.uint8).astype(np.float32) - 128) / 128
        elif bits == 16:
            x = np.frombuffer(raw[:len(raw) // 2 * 2], '<i2').astype(np.float32) / 32768
        elif bits == 24:
            b = np.frombuffer(raw[:len(raw) // 3 * 3], np.uint8).reshape(-1, 3).astype(np.int32)
            v = b[:, 0] | (b[:, 1] << 8) | (b[:, 2] << 16)
            v = np.where(v >= 1 << 23, v - (1 << 24), v)
            x = v.astype(np.float32) / (1 << 23)
        elif bits == 32:
            x = np.frombuffer(raw[:len(raw) // 4 * 4], '<i4').astype(np.float32) / 2 ** 31
        else:
            raise ValueError('%s: nieobsługiwana głębia %d' % (path, bits))
    else:
        raise ValueError('%s: nieobsługiwany format %d' % (path, tag))
    x = x[:len(x) // ch * ch].reshape(-1, ch).mean(axis=1)
    return x.astype(np.float32), sr


def write_wav(path, x, sr):
    x = np.clip(np.asarray(x, np.float32), -1, 1)
    pcm = (x * 32767).astype('<i2').tobytes()
    with open(path, 'wb') as f:
        f.write(b'RIFF' + struct.pack('<I', 36 + len(pcm)) + b'WAVE')
        f.write(b'fmt ' + struct.pack('<IHHIIHH', 16, 1, 1, sr, sr * 2, 2, 16))
        f.write(b'data' + struct.pack('<I', len(pcm)) + pcm)


def resample(x, sr_in, sr_out, block=1 << 16):
    """Zmiana próbkowania przez FFT w blokach z zakładką (okno Hanna, OLA); filtr antyaliasingowy to obcięcie widma."""
    if sr_in == sr_out or len(x) == 0:
        return np.asarray(x, np.float32)
    ratio = sr_out / sr_in
    n_out = int(round(len(x) * ratio))
    if len(x) <= 2 * block:
        X = np.fft.rfft(x)
        m = int(round(len(x) * ratio))
        Y = np.zeros(m // 2 + 1, complex)
        k = min(len(X), len(Y))
        Y[:k] = X[:k]
        return (np.fft.irfft(Y, m) * ratio).astype(np.float32)[:n_out]
    hop = block // 2
    w = np.hanning(block + 1)[:block]  # suma okien z krokiem block/2 = 1
    out = np.zeros(n_out + int(block * ratio) + 2, np.float64)
    pad = np.concatenate([np.zeros(hop), x, np.zeros(block)])
    for s in range(0, len(x) + hop, hop):
        seg = pad[s:s + block]
        if len(seg) < block:
            seg = np.pad(seg, (0, block - len(seg)))
        y = resample(seg * w, sr_in, sr_out, block=block * 4)
        o = int(round((s - hop) * ratio))
        a, b = max(0, o), min(len(out), o + len(y))
        if b > a:
            out[a:b] += y[a - o:b - o]
    return out[:n_out].astype(np.float32)


def engine_fir(D):
    """Filtr decymatora silnika C++ (gt_dsp.hpp, Decimator): sinc z oknem Blackmana, odcięcie 0,42 / D, 12 D + 1 współczynników."""
    T = 12 * D + 1
    fc, mid = 0.42 / D, (T - 1) / 2
    i = np.arange(T)
    x = i - mid
    s = np.where(x == 0, 2 * fc, np.sin(2 * np.pi * fc * x) / (np.pi * np.where(x == 0, 1, x)))
    w = 0.42 - 0.5 * np.cos(2 * np.pi * i / (T - 1)) + 0.08 * np.cos(4 * np.pi * i / (T - 1))
    h = s * w
    return (h / h.sum()).astype(np.float32)


def engine_frontend(x, sr):
    """Dokładnie to, co silnik C++ robi z dźwiękiem przed analizą: D = round(sr / 11025), filtr FIR (przyczynowy, opóźnienie 6 D
    próbek), co D-ta próbka. Zwraca (sygnał, fsd = sr / D). Uwaga: fsd nie zawsze = 11025 (48 kHz -> 12 kHz), więc gen 5 widziała
    przy 48 kHz inne cechy niż przy 44,1 kHz; gen 6 domyślnie zmienia próbkowanie dokładnie do FeatureConfig.sr."""
    D = max(1, int(round(sr / 11025.0)))
    h = engine_fir(D)
    y = np.convolve(np.asarray(x, np.float32), h)[:len(x)]
    return y[::D].astype(np.float32), sr / D


def load_audio(path, sr, frontend='resample'):
    """frontend: 'resample' (dokładnie sr) albo 'engine' (jak silnik C++; wymaga, by sr / D == sr docelowe)."""
    x, s = read_wav(path)
    if frontend == 'engine':
        y, fsd = engine_frontend(x, s)
        if abs(fsd - sr) > 1e-6:
            return resample(y, fsd, sr)
        return y
    return resample(x, s, sr)
