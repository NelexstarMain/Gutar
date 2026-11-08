"""Wykresy rozdziału 11: stabilność spadku gradientu (kryterium eta < 2/lambda) i harmonogram kroku uczenia z prawdziwego uczenia Gen 6."""
import csv
import math

import numpy as np
from figstyle import *
import gutar

EPOKI = gutar.REPO / "docs/wyniki/epoki.csv"


def lr(step, W=1000, T=36000, eta0=1e-3):
    if step < W:
        return eta0 * step / W
    q = (step - W) / (T - W)
    return eta0 * 0.5 * (1 + math.cos(math.pi * q))


def stabilnosc():
    fig, (a1, a2) = nowa_figura("pelna", 2.6, ncols=2)
    lam = 10.0
    uklad_xy(a1, (-1, 32), (-6.5, 3.2), rownaskala=False)
    for eta, kol, lw, ls in ((0.05, NIEBIESKI, 1.5, "-"), (0.15, "#6E9DC8", 1.2, "-"), (0.19, POMARANCZ, 1.3, "-"), (0.21, CZARNY, 1.2, "--")):
        x = 1.0
        xs = [x]
        for _ in range(30):
            x = x - eta * lam * x
            xs.append(x)
        a1.plot(np.arange(31), np.log10(np.abs(xs) + 1e-12), color=kol, lw=lw, ls=ls)
        # sprawdzenie kryterium: |1 - eta*lam| < 1  <=>  eta < 2/lam = 0.2
        assert (abs(1 - eta * lam) < 1) == (eta < 2 / lam)
    a1.plot([0, 31], [0, 0], color=SZARY, lw=0.5, ls=":")
    panel(a1, "a")
    # (b) harmonogram: rozgrzewka 1000 kroków, potem kosinus (sesja 1: 36 000 kroków); punkty z dziennika uczenia
    wiersze = [r for r in csv.DictReader(open(EPOKI, encoding="utf-8")) if r["sesja"] == "1"]
    kroki = np.arange(0, 36001, 50)
    uklad_xy(a2, (-1200, 37500), (-1.3e-4, 1.25e-3), rownaskala=False)
    a2.plot(kroki, [lr(k) for k in kroki], color=NIEBIESKI, lw=1.6)
    for r in wiersze[:-1]:
        e = int(r["epoka"])
        a2.plot([(e + 1) * 1000], [float(r["lr"])], "o", color=POMARANCZ, ms=2.8, zorder=5)
        assert abs(float(r["lr"]) - lr((e + 1) * 1000)) <= 0.01 * float(r["lr"]) + 1e-9    # wzór zgadza się z zapisem
    panel(a2, "b")
    fig.tight_layout(w_pad=1.0)
    zapisz(fig, "optymalizacja")


if __name__ == "__main__":
    stabilnosc()


def adam_dolina():
    f = lambda X, Y: 0.5 * (X ** 2 + 10 * Y ** 2)
    g = lambda p: np.array([p[0], 10 * p[1]])
    # GD z najlepszym krokiem 2/11 oraz Adam (eta = 0,1; beta1 = 0,9; beta2 = 0,999) od (1, 1)
    p = np.array([1.0, 1.0]); G = [p.copy()]
    for _ in range(40):
        p = p - (2 / 11) * g(p); G.append(p.copy())
    G = np.array(G)
    p = np.array([1.0, 1.0]); A = [p.copy()]; m = np.zeros(2); v = np.zeros(2)
    for t in range(1, 41):
        gr = g(p); m = 0.9 * m + 0.1 * gr; v = 0.999 * v + 0.001 * gr ** 2
        p = p - 0.1 * (m / (1 - 0.9 ** t)) / (np.sqrt(v / (1 - 0.999 ** t)) + 1e-8); A.append(p.copy())
    A = np.array(A)
    fig, ax = nowa_figura("tekst", 2.7)
    uklad_xy(ax, (-0.3, 1.2), (-0.8, 1.2), osie=False)
    X, Y = np.meshgrid(np.linspace(-0.3, 1.2, 300), np.linspace(-0.8, 1.2, 300))
    ax.contour(X, Y, f(X, Y), levels=[0.02, 0.06, 0.15, 0.3, 0.6, 1.0, 1.6, 2.5, 4.0], colors="#B8B8B8", linewidths=0.7)
    ax.plot(G[:, 0], G[:, 1], "-o", color=NIEBIESKI, ms=2.4, lw=1.0, zorder=5)
    ax.plot(A[:, 0], A[:, 1], "-o", color=POMARANCZ, ms=2.4, lw=1.0, zorder=6)
    fl = lambda P: f(P[-1, 0], P[-1, 1])
    zapisz(fig, "adam-dolina")
    return fl(G), fl(A)


if __name__ == "__main__":
    print("końcowa strata GD, Adam:", adam_dolina())
