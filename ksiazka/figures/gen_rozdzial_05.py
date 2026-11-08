"""Wykresy rozdziału 5: pochodna jako granica siecznych; gradient prostopadły do warstwic i spadek gradientu (prawdziwe obliczenia)."""
import numpy as np
from figstyle import *


def sieczne():
    fig, ax = nowa_figura("tekst", 2.5)
    x = np.linspace(0.6, 5.0, 300)
    uklad_xy(ax, (0.2, 5.2), (-1.5, 18), rownaskala=False)
    ax.plot(x, x ** 2, color=NIEBIESKI, lw=1.6)
    x0 = 3.0
    xs = np.linspace(1.4, 4.9, 50)
    for h, kol, lw in ((1.5, "#B0B0B0", 0.8), (0.75, "#8A8A8A", 0.8)):
        a = ((x0 + h) ** 2 - x0 ** 2) / h
        ax.plot(xs, x0 ** 2 + a * (xs - x0), color=kol, lw=lw)
        ax.plot([x0 + h], [(x0 + h) ** 2], "o", color=kol, ms=3.5)
    ax.plot(xs, x0 ** 2 + 6 * (xs - x0), color=POMARANCZ, lw=1.5)   # styczna: nachylenie 2 x0 = 6
    ax.plot([x0], [x0 ** 2], "o", color=CZARNY, ms=4.5, zorder=6)
    assert np.isclose(((x0 + 1e-6) ** 2 - x0 ** 2) / 1e-6, 6, atol=1e-4)
    fig.tight_layout()
    zapisz(fig, "sieczne")


def spadek():
    f = lambda X, Y: 0.5 * (X ** 2 + 10 * Y ** 2)
    g = lambda p: np.array([p[0], 10 * p[1]])
    fig, ax = nowa_figura("pelna", 2.7)
    uklad_xy(ax, (-1.35, 1.35), (-1.35, 1.35), osie=False)
    X, Y = np.meshgrid(np.linspace(-1.35, 1.35, 300), np.linspace(-1.35, 1.35, 300))
    ax.contour(X, Y, f(X, Y), levels=[0.05, 0.15, 0.35, 0.7, 1.2, 1.9, 2.8, 4.0], colors="#B8B8B8", linewidths=0.7)
    for eta, kol in ((0.05, NIEBIESKI), (0.15, POMARANCZ)):
        p = np.array([1.0, 1.0])
        P = [p.copy()]
        for _ in range(14):
            p = p - eta * g(p)
            P.append(p.copy())
        P = np.array(P)
        ax.plot(P[:, 0], P[:, 1], "-o", color=kol, ms=2.8, lw=1.2, zorder=5)
    # gradient (strzałki) w kilku punktach: prostopadły do warstwicy, skierowany "pod górę"
    for p in [(-0.9, 0.35), (0.6, -0.5), (-0.2, -0.9), (1.0, 0.0)]:
        p = np.array(p)
        gr = g(p)
        gr = 0.28 * gr / np.linalg.norm(gr)
        strzalka(ax, p, p + gr, CZARNY, lw=1.0)
    # sprawdzenie własności: gradient prostopadły do stycznej do warstwicy (styczna: (-10y, x)/..)
    p = np.array([0.6, -0.5])
    assert abs(g(p) @ np.array([-10 * p[1], p[0]])) < 1e-12
    fig.tight_layout()
    zapisz(fig, "spadek")


if __name__ == "__main__":
    sieczne()
    spadek()
