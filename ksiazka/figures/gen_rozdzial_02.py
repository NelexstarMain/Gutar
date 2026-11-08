"""Wykresy rozdziału 2: sinusoida i próbki, aliasing, półtony na osi liniowej i logarytmicznej."""
import numpy as np
from figstyle import *

FS = 11025.0


def probkowanie():
    fig, (a1, a2) = nowa_figura("pelna", 2.3, ncols=2)
    # (a) sinusoida 440 Hz i jej próbki przy FS = 11025 (okres = 25,06 próbki)
    f = 440.0
    t = np.linspace(0, 3 / f, 600)
    n = np.arange(0, int(3 / f * FS) + 1)
    for ax in (a1, a2):
        uklad_xy(ax, (-0.02 / f, 3.15 / f), (-1.5, 1.5), rownaskala=False)
    a1.plot(t, np.sin(2 * np.pi * f * t), color=NIEBIESKI, lw=1.4)
    a1.plot(n / FS, np.sin(2 * np.pi * f * n / FS), "o", color=POMARANCZ, ms=2.6)
    for k in n:
        a1.plot([k / FS] * 2, [0, np.sin(2 * np.pi * f * k / FS)], color=POMARANCZ, lw=0.4)
    panel(a1, "a")
    # (b) aliasing: f1 = 0,2 FS i f2 = 0,8 FS dają te same próbki z przeciwnym znakiem
    f1, f2 = 0.15 * FS, 0.85 * FS
    n2 = np.arange(0, 11)
    t2 = np.linspace(0, 10 / FS, 1500)
    for ax in (a2,):
        ax.set_xlim(-0.2 / FS, 10.4 / FS)
    a2.plot(t2, np.sin(2 * np.pi * f1 * t2), color=NIEBIESKI, lw=1.2)
    a2.plot(t2, -np.sin(2 * np.pi * f2 * t2), color=POMARANCZ, lw=1.0, ls="--")
    s1 = np.sin(2 * np.pi * f1 * n2 / FS)
    s2 = -np.sin(2 * np.pi * f2 * n2 / FS)
    assert np.allclose(s1, s2)
    a2.plot(n2 / FS, s1, "o", color=CZARNY, ms=3.6, zorder=5)
    panel(a2, "b")
    fig.tight_layout(w_pad=1.2)
    zapisz(fig, "probkowanie")


def polsl_osie():
    fig, (a1, a2) = nowa_figura("pelna", 1.7, nrows=2)
    m = np.arange(40, 65)                 # E2 ... E4
    f = 440.0 * 2 ** ((m - 69) / 12)
    struny = [40, 45, 50, 55, 59, 64]
    for ax, x, lab in ((a1, f, "a"), (a2, np.log2(f), "b")):
        ax.set_axis_off()
        lo, hi = x.min(), x.max()
        pad = 0.04 * (hi - lo)
        ax.set_xlim(lo - pad, hi + pad)
        ax.set_ylim(-1.3, 1.2)
        os_strzalka(ax, (lo - pad, 0), (hi + pad * 0.9, 0))
        for xi, mi in zip(x, m):
            ax.plot([xi, xi], [-0.15, 0.15], color=SZARY, lw=0.7)
        for mi in struny:
            xi = x[mi - 40]
            ax.plot([xi], [0], "o", color=NIEBIESKI, ms=5, zorder=5)
        ax.text(0.5, -0.02, f"({lab})", transform=ax.transAxes, ha="center", va="top", fontsize=8.5)
    # w (a) odstępy między półtonami rosną ~ wykładniczo, w (b) są równe
    d_lin = np.diff(f)
    d_log = np.diff(np.log2(f))
    assert np.isclose(d_lin[-1] / d_lin[0], 2 ** (23 / 12)) and np.allclose(d_log, 1 / 12)
    fig.tight_layout(h_pad=0.4)
    zapisz(fig, "polsl-osie")


if __name__ == "__main__":
    probkowanie()
    polsl_osie()
