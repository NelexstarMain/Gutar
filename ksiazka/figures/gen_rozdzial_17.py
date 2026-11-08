"""Wykresy rozdziału 17 z prawdziwych wyników testu (docs/wyniki/test_grupy.csv) i porównania z Gen 5 (docs/WYNIKI.md)."""
import csv

import numpy as np
import gutar
from figstyle import *


def grupy():
    rows = list(csv.DictReader(open(gutar.REPO / "docs/wyniki/test_grupy.csv", encoding="utf-8")))
    mac = [r for r in rows if r["model"] == "sesja4_epoka81" and r["uśrednienie"] == "macro" and r["grupa"] != "RAZEM"]
    assert len(mac) == 31
    mac.sort(key=lambda r: -float(r["note_F1"]))
    f1 = np.array([float(r["note_F1"]) for r in mac])
    gs = np.array([r["grupa"].startswith("GuitarSet") for r in mac])
    fig, (a1, a2) = nowa_figura("pelna", 3.3, ncols=2, gridspec_kw={"width_ratios": [1.6, 1]})
    a1.set_axis_off()
    a1.set_xlim(0, 100)
    a1.set_ylim(-1, len(mac))
    os_strzalka(a1, (0, -0.6), (100, -0.6))
    y = np.arange(len(mac))[::-1]
    a1.barh(y, f1, color=[POMARANCZ if g else NIEBIESKI for g in gs], height=0.7)
    a1.plot([85.94, 85.94], [-0.6, len(mac) - 0.3], color=CZARNY, lw=0.8, ls=":")
    panel(a1, "a")
    # (b) Gen 5 i Gen 6 na GuitarSet 03-05 (dokumentacja projektu; liczby Gen 5 z README)
    m = ["F1 nut razem", "akompaniament", "melodie", "z końcem"]
    g5 = np.array([79.5, 75.6, 83.4, 40.9])
    g6 = np.array([87.2, 85.1, 89.2, 74.8])
    a2.set_axis_off()
    a2.set_xlim(-0.6, 4.4)
    a2.set_ylim(-4, 100)
    os_strzalka(a2, (-0.5, 0), (4.3, 0))
    x = np.arange(4)
    a2.bar(x - 0.2, g5, width=0.38, color="#B0B0B0")
    a2.bar(x + 0.2, g6, width=0.38, color=NIEBIESKI)
    panel(a2, "b")
    fig.tight_layout(w_pad=1.0)
    zapisz(fig, "wyniki-grupy")
    return mac[0]["grupa"], f1[0], mac[-1]["grupa"], f1[-1], float(np.median(f1))


if __name__ == "__main__":
    print(grupy())


def poziomice_f1():
    P, R = np.meshgrid(np.linspace(0.5, 1, 400), np.linspace(0.5, 1, 400))
    F = 2 * P * R / (P + R)
    fig, ax = nowa_figura("tekst", 2.9)
    uklad_xy(ax, (0.5, 1.04), (0.5, 1.04))
    ax.contour(P, R, F, levels=[0.6, 0.7, 0.8, 0.85, 0.9, 0.95], colors="#B8B8B8", linewidths=0.8)
    ax.plot([0.5, 1.0], [0.5, 1.0], color=SZARY, lw=0.6, ls=":")
    pts = ((0.8884, 0.8425, "#5F5F5F"), (0.935, 0.821, NIEBIESKI))
    for p, r, kol in pts:
        ax.plot([p], [r], "o", color=kol, ms=5.5, zorder=5)
    ax.annotate("", xy=(0.935, 0.821), xytext=(0.8884, 0.8425), arrowprops=dict(arrowstyle="-|>", color=POMARANCZ, lw=1.1, shrinkA=4, shrinkB=4))
    fn = lambda p, r: 2 * p * r / (p + r)
    assert fn(0.935, 0.821) > fn(0.8884, 0.8425)       # F1 ze średnich P i R rośnie, mimo spadku czułości
    fig.tight_layout()
    zapisz(fig, "f1-poziomice")
    return fn(0.8884, 0.8425), fn(0.935, 0.821)


if __name__ == "__main__":
    print(poziomice_f1())
