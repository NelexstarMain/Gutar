"""Wykresy rozdziału 15: przebieg uczenia Gen 6 (97 epok, trzy sesje) z prawdziwego dziennika docs/wyniki/epoki.csv."""
import csv

import numpy as np
import gutar
from figstyle import *

KOL = {"1": NIEBIESKI, "3": POMARANCZ, "4": "#5F5F5F"}


def uczenie():
    rows = list(csv.DictReader(open(gutar.REPO / "docs/wyniki/epoki.csv", encoding="utf-8")))
    e = np.array([int(r["epoka"]) for r in rows])
    ses = [r["sesja"] for r in rows]
    F1 = np.array([float(r["val_RAZEM_note_F1"]) for r in rows])
    best = int(np.argmax(F1))
    assert len(rows) == 97 and e[best] == 81 and abs(F1[best] - 90.27) < 1e-9
    fig, (a1, a2) = nowa_figura("pelna", 2.7, ncols=2)
    uklad_xy(a1, (-4, 102), (66, 93), rownaskala=False)
    for s in "134":
        idx = [i for i, x in enumerate(ses) if x == s]
        a1.plot(e[idx], F1[idx], "-", color=KOL[s], lw=1.5)
    a1.plot([e[best]], [F1[best]], "o", color=CZARNY, ms=4.5, zorder=6)
    for x in (35.5, 47.5):
        a1.plot([x, x], [66, 93], color=SZARY, lw=0.5, ls=":")
    panel(a1, "a")
    uklad_xy(a2, (-4, 102), (-2.1, -0.4), rownaskala=False)
    for nazwa, kol, ls in (("strata_onset", NIEBIESKI, "-"), ("strata_frame", POMARANCZ, "-"), ("strata_tab", "#5F5F5F", "-")):
        y = np.log10([float(r[nazwa]) for r in rows])
        a2.plot(e, y, ls, color=kol, lw=1.3)
    for x in (35.5, 47.5):
        a2.plot([x, x], [-2.1, -0.4], color=SZARY, lw=0.5, ls=":")
    panel(a2, "b")
    fig.tight_layout(w_pad=1.0)
    zapisz(fig, "uczenie")
    return F1[0], F1[best]


if __name__ == "__main__":
    print(uczenie())
