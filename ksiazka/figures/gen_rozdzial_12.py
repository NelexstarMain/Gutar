"""Wykresy rozdziału 12: mapy celów z prawdziwego kodu etykiet repozytorium oraz niejednoznaczność tabulatury na gryfie."""
import numpy as np
import gutar
from figstyle import *
from tools.gen6.data import Example, Note
from tools.gen6.labels import make_targets

STROJ = (40, 45, 50, 55, 59, 64)       # struny od najniższej (indeks 0) do najwyższej; w książce numer struny = 6 - indeks


def mapy_celow():
    m, cfg, _ = gutar.model()
    fc, lc = cfg.features, cfg.labels
    ex, X, _ = gutar.wynik(3, 1, 6.0)
    tg, av = make_targets(ex, len(X), fc, lc)
    t0, t1, s0, s1 = 0, 110, 4, 36
    fig, axs = nowa_figura("pelna", 2.6, ncols=3)
    for ax, (nazwa, lit) in zip(axs, (("frame", "a"), ("onset", "b"), ("offset", "c"))):
        ax.imshow(tg[nazwa][t0:t1, s0:s1].T, origin="lower", aspect="auto", cmap="Blues", vmin=0, vmax=1.15,
                  interpolation="nearest", extent=[t0, t1, s0, s1])
        ax.set_axis_off()
        panel(ax, lit)
    # kontrola: każda nuta ma dokładnie jedną klatkę początku równą 1 i dwie sąsiednie 0,4
    on = tg["onset"]
    assert (on == 1).sum() == len(ex.notes) and np.isclose(on, 0.4).sum() == 2 * len(ex.notes)
    fig.tight_layout(w_pad=0.8)
    zapisz(fig, "mapy-celow")


def gryf():
    pitch = 64
    poz = [(5 - idx, pitch - o) for idx, o in enumerate(STROJ) if 0 <= pitch - o < 20]   # (numer struny 1..6 od najcieńszej -> y, próg)
    assert len(poz) == 5
    fig, ax = nowa_figura("tekst", 1.9)
    ax.set_axis_off()
    ax.set_xlim(-1.2, 20.5)
    ax.set_ylim(-0.8, 5.8)
    for fret in range(0, 21):
        ax.plot([fret, fret], [0, 5], color="#B8B8B8" if fret else CZARNY, lw=0.7 if fret else 2.0)
    for y in range(6):
        ax.plot([0, 20], [y, y], color=SZARY, lw=0.5 + 0.18 * (5 - y))
    for (y, fret) in poz:
        x = fret - 0.5 if fret > 0 else -0.55
        ax.plot([x], [y], "o", color=NIEBIESKI, ms=7, zorder=5)
    # struna "pusta" E4 (próg 0) i najwyższy możliwy próg 19 dla struny A (idx 1)
    fig.tight_layout()
    zapisz(fig, "gryf-e4")


if __name__ == "__main__":
    mapy_celow()
    gryf()
