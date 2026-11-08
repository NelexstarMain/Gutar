"""Wykresy rozdziału 6: przeciek widma (okno prostokątne i Hanna) oraz rozdzielczość dwóch niskich tonów (prawdziwe obliczenia FFT)."""
import numpy as np
from figstyle import *

FS = 11025.0


def f_of(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def widmo(N, freqs, okno, Z=8):
    n = np.arange(N)
    x = sum(np.cos(2 * np.pi * fr * n / FS) for fr in freqs)
    w = np.hanning(N + 1)[:N] if okno == "hann" else np.ones(N)
    X = np.abs(np.fft.rfft(x * w, N * Z))
    return np.fft.rfftfreq(N * Z, 1 / FS), X


def przeciek():
    N = 128
    fig, (a1, a2) = nowa_figura("pelna", 2.5, ncols=2, sharey=True)
    for ax, delta, lab in ((a1, 0.0, "a"), (a2, 0.5, "b")):
        n = np.arange(N)
        x = np.cos(2 * np.pi * (20 + delta) * n / N)
        for okno, kol, lw in (("rect", "#9A9A9A", 1.0), ("hann", NIEBIESKI, 1.5)):
            w = np.hanning(N + 1)[:N] if okno == "hann" else np.ones(N)
            X = np.abs(np.fft.rfft(x * w, N * 16))
            X = X / X.max()
            k = np.arange(len(X)) / 16
            ax.plot(k, np.maximum(20 * np.log10(X + 1e-9), -90), color=kol, lw=lw)
        ax.set_xlim(8, 32)
        ax.set_ylim(-95, 6)
        ax.set_axis_off()
        os_strzalka(ax, (8, -95), (32, -95))
        panel(ax, lab)
    # sprawdzenie: pierwszy listek boczny okna prostokątnego ok. -13 dB, Hanna ok. -31 dB
    Xr = np.abs(np.fft.rfft(np.ones(256), 256 * 32)); Xh = np.abs(np.fft.rfft(np.hanning(257)[:256], 256 * 32))
    assert -14 < 20 * np.log10(Xr[33:].max() / Xr.max()) < -12.5
    assert -33 < 20 * np.log10(Xh[65:].max() / Xh.max()) < -30
    fig.tight_layout(w_pad=1.0)
    zapisz(fig, "przeciek")


def rozdzielczosc():
    fig, axs = nowa_figura("pelna", 2.6, ncols=2, sharey=True)
    for ax, (m2, lab) in zip(axs, ((41, "a"), (42, "b"))):
        for N, kol, lw in ((4096, NIEBIESKI, 1.6), (1024, POMARANCZ, 1.3)):
            F, X = widmo(N, [f_of(40), f_of(m2)], "hann")
            msk = (F > 62) & (F < 112)
            ax.plot(F[msk], X[msk] / X[msk].max(), color=kol, lw=lw)
        for fr in (f_of(40), f_of(m2)):
            ax.plot([fr, fr], [0, 1.08], color=SZARY, lw=0.8, ls=":")
        ax.set_xlim(62, 112)
        ax.set_ylim(-0.05, 1.15)
        ax.set_axis_off()
        os_strzalka(ax, (62, 0), (112, 0))
        panel(ax, lab)
    # kontrola: dla E2+F#2 oba piki (N=4096) są rozdzielone; dla E2+F2 nie widać dwóch poprawnych pików
    F, X = widmo(4096, [f_of(40), f_of(42)], "hann")
    msk = (F > 62) & (F < 112)
    x, fr = X[msk] / X[msk].max(), F[msk]
    pk = [i for i in range(1, len(x) - 1) if x[i] > x[i - 1] and x[i] >= x[i + 1] and x[i] > 0.5]
    assert len(pk) == 2
    fig.tight_layout(w_pad=1.0)
    zapisz(fig, "rozdzielczosc")


if __name__ == "__main__":
    przeciek()
    rozdzielczosc()
