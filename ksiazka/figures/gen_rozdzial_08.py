"""Wykresy rozdziału 8: entropia krzyżowa (BCE), jej gradient na tle błędu kwadratowego oraz kalibracja przy wadze klasy dodatniej."""
import numpy as np
from figstyle import *

sig = lambda z: 1 / (1 + np.exp(-z))


def bce():
    fig, (a1, a2) = nowa_figura("pelna", 2.5, ncols=2)
    p = np.linspace(0.004, 0.996, 400)
    # (a) strata dla y = 1 (waga 1 i 4) i dla y = 0
    uklad_xy(a1, (-0.05, 1.1), (-0.3, 5.6), rownaskala=False)
    a1.plot(p, -np.log(p), color=NIEBIESKI, lw=1.6)
    a1.plot(p, -4 * np.log(p), color=POMARANCZ, lw=1.4)
    a1.plot(p, -np.log(1 - p), color=SZARY, lw=1.2, ls="--")
    panel(a1, "a")
    # (b) gradient po logicie: BCE (sigma - y) vs błąd kwadratowy 2(sigma - y) sigma (1 - sigma), dla y = 1
    z = np.linspace(-8, 8, 400)
    s = sig(z)
    uklad_xy(a2, (-8.5, 8.5), (-2.2, 0.6), rownaskala=False)
    a2.plot(z, s - 1, color=NIEBIESKI, lw=1.6)
    a2.plot(z, 2 * (s - 1) * s * (1 - s), color=POMARANCZ, lw=1.4)
    # sprawdzenie: pochodna BCE po z równa się sigma - y (różnice skończone)
    z0, e = 0.7, 1e-6
    f = lambda zz, y: -(y * np.log(sig(zz)) + (1 - y) * np.log(1 - sig(zz)))
    for y in (0, 1):
        assert abs((f(z0 + e, y) - f(z0 - e, y)) / (2 * e) - (sig(z0) - y)) < 1e-6
    panel(a2, "b")
    fig.tight_layout(w_pad=1.0)
    zapisz(fig, "bce")


def kalibracja():
    fig, ax = nowa_figura("tekst", 2.5)
    uklad_xy(ax, (-0.04, 1.08), (-0.04, 1.08))
    q = np.linspace(0, 1, 300)
    ax.plot([0, 1], [0, 1], color=SZARY, lw=0.8, ls=":")
    for a, kol, lw in ((1, NIEBIESKI, 1.6), (4, POMARANCZ, 1.5)):
        ax.plot(q, a * q / (a * q + 1 - q), color=kol, lw=lw)
    # kontrola: minimum średniej straty ważonej leży w p* = a q / (a q + 1 - q)
    qq, a = 0.1, 4.0
    pp = np.linspace(0.001, 0.999, 200000)
    L = -(qq * a * np.log(pp) + (1 - qq) * np.log(1 - pp))
    assert abs(pp[np.argmin(L)] - a * qq / (a * qq + 1 - qq)) < 1e-4
    fig.tight_layout()
    zapisz(fig, "kalibracja")


if __name__ == "__main__":
    bce()
    kalibracja()
