"""Wykresy rozdziału 1: logarytm zamienia mnożenie na przesunięcie; funkcje pomocnicze (clip, max, wskaźnik, zaokrąglenie)."""
import numpy as np
from figstyle import *


def os_log():
    fig, (a1, a2) = nowa_figura("pelna", 2.5, ncols=2, gridspec_kw={"width_ratios": [1, 1.25]})
    # (a) y = 2^x i jej lustro y = log2 x względem prostej y = x
    x = np.linspace(-1.2, 3.2, 300)
    uklad_xy(a1, (-1.6, 3.6), (-1.6, 3.6))
    a1.plot(x, 2.0 ** x, color=NIEBIESKI, lw=1.6)
    xl = np.linspace(0.18, 3.6, 300)
    a1.plot(xl, np.log2(xl), color=POMARANCZ, lw=1.6)
    a1.plot([-1.4, 3.4], [-1.4, 3.4], color=SZARY, lw=0.7, ls=":")
    # punkt (3, 8) -> (8, 3) poza kadrem; pokażmy (2, 4) i (4, 2)
    for (px, py) in [(2, 4), (4, 2)]:
        pass
    a1.plot([2], [4], "o", color=NIEBIESKI, ms=4)
    a1.plot([1], [2], "o", color=NIEBIESKI, ms=4)
    a1.plot([4], [2], "o", color=POMARANCZ, ms=4)
    a1.plot([2], [1], "o", color=POMARANCZ, ms=4)
    for p, q in [((2, 4), (4, 2)), ((1, 2), (2, 1))]:
        a1.annotate("", xy=q, xytext=p, arrowprops=dict(arrowstyle="->", color=SZARY, lw=0.6, ls="--"))
    etykieta(a1, (3.0, 3.35), r"$2^{x}$", NIEBIESKI, dx=-14)
    etykieta(a1, (3.3, 1.0), r"$\log_2 x$", POMARANCZ)
    panel(a1, "a")
    # (b) oś logarytmiczna: mnożenie przez 2 to zawsze ten sam krok
    a2.set_axis_off()
    a2.set_xlim(-0.5, 6.4)
    a2.set_ylim(-1.1, 2.0)
    os_strzalka(a2, (-0.3, 0), (6.3, 0))
    pts = {1: r"$f$", 2: r"$2f$", 4: r"$4f$", 8: r"$8f$"}
    for k, (v, lab) in enumerate(pts.items()):
        xx = np.log2(v) * 2.0
        a2.plot([xx], [0], "o", color=NIEBIESKI, ms=5, zorder=5)
        etykieta(a2, (xx, 0), lab, dy=-14)
    for k in range(3):
        x0, x1 = 2.0 * k, 2.0 * (k + 1)
        a2.annotate("", xy=(x1, 0.55), xytext=(x0, 0.55),
                    arrowprops=dict(arrowstyle="-|>", color=POMARANCZ, lw=1.2, shrinkA=0, shrinkB=0, mutation_scale=8))
        etykieta(a2, ((x0 + x1) / 2, 0.55), r"$\times 2$", POMARANCZ, dy=9)
    for v in (3, 6):                                   # 3f i 6f: 3 = 2 * 1.5 -> ten sam krok log2(2)
        xx = np.log2(v) * 2.0
        a2.plot([xx], [0], "s", color=SZARY, ms=4, zorder=5)
        etykieta(a2, (xx, 0), rf"${v}f$", SZARY, dy=11)
    assert np.isclose(np.log2(6) - np.log2(3), 1.0) and np.isclose(np.log2(8) - np.log2(4), 1.0)
    panel(a2, "b")
    fig.tight_layout(w_pad=1.2)
    zapisz(fig, "os-log")


def funkcje_pomocnicze():
    fig, axs = nowa_figura("pelna", 1.9, ncols=4)
    x = np.linspace(-2, 2, 400)
    f = [
        (np.clip(x, -1, 1), "ciągła"),
        (np.maximum(0, x), "ciągła"),
        ((x >= 0.5).astype(float), "skok"),
        (np.round(x), "schody"),
    ]
    for ax, (y, _), lit in zip(axs, f, "abcd"):
        uklad_xy(ax, (-2.3, 2.3), (-2.3, 2.3))
        ax.plot(x, x, color=SZARY, lw=0.6, ls=":")
        if lit in "cd":
            # skoki rysujemy bez łączenia pionowych kresek
            y2 = y.copy()
            br = np.where(np.abs(np.diff(y)) > 0.5)[0]
            xx = x.copy().astype(float)
            xx = np.insert(xx, br + 1, np.nan)
            y2 = np.insert(y2, br + 1, np.nan)
            ax.plot(xx, y2, color=NIEBIESKI, lw=1.6)
        else:
            ax.plot(x, y, color=NIEBIESKI, lw=1.6)
        panel(ax, lit)
    fig.tight_layout(w_pad=0.6)
    zapisz(fig, "funkcje-pomocnicze")


if __name__ == "__main__":
    os_log()
    funkcje_pomocnicze()
