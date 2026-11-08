"""Wykresy rozdziału 4: iloczyn skalarny jako rzut, macierz jako przekształcenie siatki."""
import numpy as np
from matplotlib import cm
from figstyle import *


def rzut():
    u, v = np.array([3.0, 0.8]), np.array([1.4, 2.0])
    p = (u @ v) / (u @ u) * u
    r = v - p
    assert abs(r @ u) < 1e-12                                   # reszta prostopadła do u
    assert np.isclose(u @ v, np.linalg.norm(u) * np.linalg.norm(v) * np.cos(
        np.arccos(u @ v / (np.linalg.norm(u) * np.linalg.norm(v)))))
    fig, ax = nowa_figura("tekst", 2.2)
    uklad_xy(ax, (-0.3, 3.5), (-0.3, 2.4), osie=False)
    strzalka(ax, (0, 0), u, NIEBIESKI)
    strzalka(ax, (0, 0), v, POMARANCZ)
    strzalka(ax, (0, 0), p, CZARNY, lw=1.2)
    ax.plot([v[0], p[0]], [v[1], p[1]], color=SZARY, lw=1.0, ls="--")
    prosty_kat(ax, p, -u / np.linalg.norm(u), r / np.linalg.norm(r), 0.13)
    th = np.linspace(0, np.arctan2(v[1], v[0]) - np.arctan2(u[1], u[0]), 30) + np.arctan2(u[1], u[0])
    ax.plot(0.7 * np.cos(th), 0.7 * np.sin(th), color=CZARNY, lw=0.8)
    etykieta(ax, (0.95, 0.38), r"$\theta$", dx=2)
    etykieta(ax, u * 0.62, r"$%s$" % wek("u"), dy=-10)
    etykieta(ax, v * 0.6, r"$%s$" % wek("v"), dx=-9)
    etykieta(ax, p * 0.5, r"$p$", dy=9)
    fig.tight_layout()
    zapisz(fig, "rzut")


def siatka():
    A = np.array([[1.6, 0.7], [-0.4, 1.2]])
    g = np.linspace(-1, 1, 9)
    X, Y = np.meshgrid(g, g)
    P = np.stack([X.ravel(), Y.ravel()])
    kol = cm.viridis((X.ravel() + 1) / 2)
    Q = A @ P
    fig, (a1, a2) = nowa_figura("pelna", 2.5, ncols=2)
    for ax, M, lab, lim in ((a1, P, "a", (-1.4, 1.4)), (a2, Q, "b", (-2.6, 2.6))):
        uklad_xy(ax, lim, lim)
        ax.scatter(M[0], M[1], c=kol, s=16, zorder=4)
        for i in range(9):          # linie siatki: obrazy prostych też są prostymi
            idx = np.arange(9) + 9 * i
            ax.plot(M[0, idx], M[1, idx], color=SZARY, lw=0.4, zorder=1)
            idx = np.arange(9) * 9 + i
            ax.plot(M[0, idx], M[1, idx], color=SZARY, lw=0.4, zorder=1)
        panel(ax, lab)
    strzalka(a2, (0, 0), A[:, 0], NIEBIESKI, lw=1.6)
    strzalka(a2, (0, 0), A[:, 1], POMARANCZ, lw=1.6)
    assert np.isclose(abs(np.linalg.det(A)), 1.6 * 1.2 + 0.7 * 0.4)
    fig.tight_layout(w_pad=1.0)
    zapisz(fig, "macierz-siatka")


if __name__ == "__main__":
    rzut()
    siatka()
