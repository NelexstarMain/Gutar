"""Rysunek rozdziału 18: macierz zależności (które rozdziały matematyki wymagają kolejne elementy modelu)."""
import numpy as np
from figstyle import *

# wiersze: elementy modelu (rozdz. 12-17), kolumny: rozdziały 1-11; 1 = element wymaga tego rozdziału
ZAL = {
    12: [1, 2, 3],
    13: [1, 3, 4, 6, 7, 9],
    14: [3, 4, 8, 9, 10],
    15: [5, 8, 11],
    16: [1, 2, 8],
    17: [1, 2, 8],
}


def macierz():
    wiersze = sorted(ZAL)
    M = np.zeros((len(wiersze), 11))
    for i, r in enumerate(wiersze):
        for c in ZAL[r]:
            M[i, c - 1] = 1
    fig, ax = nowa_figura("tekst", 2.5)
    ax.set_xlim(-0.8, 11.0)
    ax.set_ylim(-0.9, len(wiersze) + 0.2)
    ax.set_axis_off()
    for j in range(11):
        ax.text(j + 0.5, len(wiersze) + 0.05, str(j + 1), ha="center", va="bottom", fontsize=7.5)
    for i, r in enumerate(wiersze):
        y = len(wiersze) - 1 - i + 0.5
        ax.text(-0.15, y, str(r), ha="right", va="center", fontsize=7.5, fontweight="bold")
        ax.plot([0, 11], [y - 0.5, y - 0.5], color="#D8D8D8", lw=0.4)
        for j in range(11):
            if M[i, j]:
                ax.plot([j + 0.5], [y], "o", color=NIEBIESKI, ms=6.5)
    ax.plot([0, 11], [len(wiersze), len(wiersze)], color="#D8D8D8", lw=0.4)
    for j in range(12):
        ax.plot([j, j], [0, len(wiersze)], color="#ECECEC", lw=0.4, zorder=0)
    assert M.sum() == sum(len(v) for v in ZAL.values())
    fig.tight_layout()
    zapisz(fig, "zaleznosci")
    return int(M.sum())


if __name__ == "__main__":
    print(macierz())
