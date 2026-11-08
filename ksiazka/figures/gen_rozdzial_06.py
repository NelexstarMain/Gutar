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
    """Przeciek: okno prostokątne i Hanna, ton w prążku (linia ciągła) i w pół drogi między prążkami (przerywana)."""
    N, Z = 128, 32
    fig, (a1, a2) = nowa_figura("pelna", 3.2, ncols=2, sharey=True)
    n = np.arange(N)
    prop = {}
    for ax, okno, lit, kol in ((a1, "rect", "a", "#7A7A7A"), (a2, "hann", "b", NIEBIESKI)):
        w = np.hanning(N + 1)[:N] if okno == "hann" else np.ones(N)
        for delta, ls, lw in ((0.0, "-", 1.7), (0.5, "--", 1.2)):
            x = np.cos(2 * np.pi * (20 + delta) * n / N)
            X = np.abs(np.fft.rfft(x * w, N * Z))
            X /= np.abs(np.fft.rfft(np.cos(2 * np.pi * 20 * n / N) * w, N * Z)).max()
            k = np.arange(len(X)) / Z
            ax.plot(k, np.maximum(20 * np.log10(X + 1e-9), -80), color=kol, lw=lw, ls=ls)
            prop[(okno, delta)] = X
        ax.set_xlim(13.5, 26.5); ax.set_ylim(-85, 6); ax.set_axis_off()
        os_strzalka(ax, (13.5, -80), (26.5, -80))
        panel(ax, lit)
    # poziomy pierwszego listka bocznego: prostokątne -13 dB, Hanna -31 dB (kropkowane)
    a1.plot([13.5, 26.5], [-13.3, -13.3], color=POMARANCZ, lw=0.8, ls=":")
    a2.plot([13.5, 26.5], [-31.5, -31.5], color=POMARANCZ, lw=0.8, ls=":")
    Xr = np.abs(np.fft.rfft(np.ones(256), 256 * 32)); Xh = np.abs(np.fft.rfft(np.hanning(257)[:256], 256 * 32))
    assert -14 < 20 * np.log10(Xr[33:].max() / Xr.max()) < -12.5 and -33 < 20 * np.log10(Xh[65:].max() / Xh.max()) < -30
    fig.tight_layout(w_pad=1.0)
    zapisz(fig, "przeciek")


def rozdzielczosc():
    fig, axs = nowa_figura("pelna", 3.0, ncols=2, sharey=True)
    for ax, (m2, lab) in zip(axs, ((41, "a"), (42, "b"))):
        for N, kol, lw, fil in ((1024, POMARANCZ, 1.5, False), (4096, NIEBIESKI, 1.9, True)):
            F, X = widmo(N, [f_of(40), f_of(m2)], "hann")
            msk = (F > 66) & (F < 106)
            y = X[msk] / X[msk].max()
            if fil:
                ax.fill_between(F[msk], 0, y, color=JASNONIEBIESKI, alpha=0.55, lw=0)
            ax.plot(F[msk], y, color=kol, lw=lw)
            xp = F[msk]
            pk = [i for i in range(1, len(y) - 1) if y[i] > y[i - 1] and y[i] >= y[i + 1] and y[i] > 0.4]
            ax.plot(xp[pk], y[pk], "o", color=kol, ms=5, mec="white", mew=0.6, zorder=6)
        for fr in (f_of(40), f_of(m2)):
            ax.plot([fr, fr], [0, 1.1], color=CZARNY, lw=0.9, ls=":")
        ax.set_xlim(66, 106); ax.set_ylim(-0.06, 1.18); ax.set_axis_off()
        os_strzalka(ax, (66, 0), (106, 0))
        panel(ax, lab)
    F, X = widmo(4096, [f_of(40), f_of(42)], "hann")
    msk = (F > 62) & (F < 112)
    x = X[msk] / X[msk].max()
    pk = [i for i in range(1, len(x) - 1) if x[i] > x[i - 1] and x[i] >= x[i + 1] and x[i] > 0.5]
    assert len(pk) == 2
    fig.tight_layout(w_pad=1.0)
    zapisz(fig, "rozdzielczosc")


if __name__ == "__main__":
    przeciek()
    rozdzielczosc()
