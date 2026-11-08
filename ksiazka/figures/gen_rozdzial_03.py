"""Wykresy rozdziału 3 z prawdziwych (syntetycznych, ale liczonych) szarpnięć struny: widmo, wzorzec alikwotów, salience.
Liczby liczone w skrypcie; rysunki bez napisów."""
import numpy as np
import gutar  # noqa: F401  (dodaje repozytorium do sys.path)
from figstyle import *
from tools.gen6.synth import pluck

SR = 11025
NW = 8192
FRQ = np.fft.rfftfreq(NW * 4, 1 / SR)


def f_of(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def widmo(m, seed=0):
    y = pluck(f_of(m), 1.0, SR, rng=np.random.default_rng(seed))[:NW] * np.hanning(NW)
    return np.abs(np.fft.rfft(y, NW * 4))


def wartosc(S, fx):
    lo = np.argmin(abs(FRQ - fx * 2 ** (-1 / 72)))
    hi = np.argmin(abs(FRQ - fx * 2 ** (1 / 72)))
    return S[min(lo, hi):max(lo, hi) + 1].max()


def szereg():
    """(a) oś liniowa: prążki E2 i E3; kreskowane pionowe prowadnice pokazują, że E3 trafia w parzyste prążki E2.
    (b) oś w półtonach: wzorzec E2 i A2 to ta sama figura przesunięta o 5 półtonów (cienkie łączniki h-h)."""
    fig, (a1, a2) = nowa_figura("pelna", 3.3, ncols=2)
    S2, S3 = widmo(40), widmo(52)
    assert np.isclose(f_of(52), 2 * f_of(40))
    top = wartosc(S2, f_of(40))
    uklad_xy(a1, (-30, 700), (-0.12, 1.2), rownaskala=False)
    for h in range(1, 9):
        fh = h * f_of(40)
        v = wartosc(S2, fh) / top
        if h % 2 == 0:
            a1.plot([fh, fh], [0, 1.15], color=SZARY, lw=0.6, ls="--", zorder=0)
        a1.plot([fh, fh], [0, v], color=NIEBIESKI, lw=2.6, solid_capstyle="butt")
        a1.plot([fh], [v], "o", color=NIEBIESKI, ms=4.5)
    for h in range(1, 5):
        fh = h * f_of(52)
        v = wartosc(S3, fh) / top
        a1.plot([fh + 4, fh + 4], [0, v], color=POMARANCZ, lw=1.6, solid_capstyle="butt")
        a1.plot([fh + 4], [v], "D", color=POMARANCZ, ms=4)
    panel(a1, "a")
    uklad_xy(a2, (-2, 39), (-0.12, 1.2), rownaskala=False)
    pts = {}
    for m0, kol, mk in ((40, NIEBIESKI, "o"), (45, POMARANCZ, "D")):
        S = widmo(m0)
        pts[m0] = []
        for h in range(1, 13):
            fh = h * f_of(m0)
            if fh < 2500:
                u = 12 * np.log2(fh / f_of(40))
                v = wartosc(S, fh) / wartosc(S, f_of(m0))
                a2.plot([u, u], [0, v], color=kol, lw=2.0, solid_capstyle="butt")
                a2.plot([u], [v], mk, color=kol, ms=4)
                pts[m0].append((u, v))
    h = np.arange(1, 13)
    assert np.allclose(12 * np.log2(h * f_of(45) / f_of(40)) - 12 * np.log2(h * f_of(40) / f_of(40)), 5.0)
    for (u1, v1), (u2, v2) in list(zip(pts[40], pts[45]))[:6]:
        a2.plot([u1, u2], [v1 + 0.04, v2 + 0.04], color="#9A9A9A", lw=0.5)
    a2.annotate("", xy=(5, 1.12), xytext=(0, 1.12), arrowprops=dict(arrowstyle="<->", color=CZARNY, lw=0.9))
    panel(a2, "b")
    fig.tight_layout(w_pad=1.0)
    zapisz(fig, "szereg-alikwotow")


def salience():
    S = widmo(52)
    ms = np.arange(33, 80)
    sal = np.array([sum(wartosc(S, h * f_of(m)) for h in range(1, 7) if h * f_of(m) < 5000) / 6 for m in ms])
    sal /= sal.max()
    fig, ax = nowa_figura("tekst", 2.7)
    ax.set_axis_off()
    ax.set_xlim(32, 80); ax.set_ylim(-0.08, 1.22)
    os_strzalka(ax, (32, 0), (80, 0))
    ax.plot([32, 80], [1, 1], color=POMARANCZ, lw=0.7, ls=":")
    for m0 in (40, 52, 64):
        ax.plot([m0, m0], [0, 1.15], color="#C8C8C8", lw=0.6, ls="--", zorder=0)
    for m, v in zip(ms, sal):
        kol = POMARANCZ if m == 52 else (NIEBIESKI if m in (40, 64) else "#A8A8A8")
        ax.plot([m, m], [0, v], color=kol, lw=2.6 if kol != "#A8A8A8" else 1.3, solid_capstyle="butt")
    for m in (40, 52, 64):
        v = sal[ms == m][0]
        ax.plot([m], [v], "o", color=POMARANCZ if m == 52 else NIEBIESKI, ms=5)
    assert ms[np.argmax(sal)] == 52 and sal[ms == 40][0] > 0.6
    fig.tight_layout()
    zapisz(fig, "salience")
    return sal[ms == 40][0], sal[ms == 64][0]


if __name__ == "__main__":
    szereg()
    print("salience oktawa niżej / wyżej:", salience())
