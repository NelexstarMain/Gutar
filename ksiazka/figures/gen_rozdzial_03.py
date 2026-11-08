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
    fig, (a1, a2) = nowa_figura("pelna", 2.3, ncols=2)
    # (a) oś liniowa: E2 (niebieskie) i E3 (pomarańczowe)
    S2, S3 = widmo(40), widmo(52)
    for ax in (a1,):
        uklad_xy(ax, (-60, 1250), (-0.12, 1.15), rownaskala=False)
    for h in range(1, 14):
        fh = h * f_of(40)
        if fh < 1200:
            a1.plot([fh, fh], [0, wartosc(S2, fh) / wartosc(S2, f_of(40))], color=NIEBIESKI, lw=1.6)
    for h in range(1, 8):
        fh = h * f_of(52)
        a1.plot([fh + 5, fh + 5], [0, wartosc(S3, fh) / wartosc(S2, f_of(40))], color=POMARANCZ, lw=1.1)
    # E3 = 2 f0(E2): pokrywa się z parzystymi alikwotami E2
    assert np.isclose(f_of(52), 2 * f_of(40))
    panel(a1, "a")
    # (b) oś logarytmiczna w półtonach: E2 i A2, ten sam wzorzec przesunięty o 5 półtonów
    uklad_xy(a2, (-1.5, 40), (-0.12, 1.15), rownaskala=False)
    for m0, kol, dx in ((40, NIEBIESKI, 0.0), (45, POMARANCZ, 0.0)):
        S = widmo(m0)
        for h in range(1, 13):
            fh = h * f_of(m0)
            if fh < 2500:
                u = 12 * np.log2(fh / f_of(40))
                a2.plot([u + dx, u + dx], [0, wartosc(S, fh) / wartosc(S, f_of(m0))], color=kol, lw=1.4)
    # wzorzec identyczny: pozycje (45 - 40) = 5 półtonów w prawo
    h = np.arange(1, 13)
    u1 = 12 * np.log2(h * f_of(40) / f_of(40))
    u2 = 12 * np.log2(h * f_of(45) / f_of(40))
    assert np.allclose(u2 - u1, 5.0)
    a2.annotate("", xy=(5, 1.08), xytext=(0, 1.08), arrowprops=dict(arrowstyle="<->", color=SZARY, lw=0.8))
    panel(a2, "b")
    fig.tight_layout(w_pad=1.0)
    zapisz(fig, "szereg-alikwotow")


def salience():
    S = widmo(52)
    ms = np.arange(33, 80)
    sal = np.array([sum(wartosc(S, h * f_of(m)) for h in range(1, 7) if h * f_of(m) < 5000) / 6 for m in ms])
    sal /= sal.max()
    fig, ax = nowa_figura("tekst", 2.0)
    ax.set_axis_off()
    ax.set_xlim(32, 80)
    ax.set_ylim(-0.12, 1.12)
    os_strzalka(ax, (32, 0), (80, 0))
    for m, v in zip(ms, sal):
        kol = POMARANCZ if m == 52 else (NIEBIESKI if m in (40, 64) else "#B0B0B0")
        ax.plot([m, m], [0, v], color=kol, lw=2.0 if kol != "#B0B0B0" else 1.0)
    # prawdziwa nuta ma największą salience, ale oktawa niżej (40) jest tuż za nią
    assert ms[np.argmax(sal)] == 52 and sal[ms == 40][0] > 0.6
    ax.plot([52], [sal[ms == 52][0]], "o", color=POMARANCZ, ms=4)
    fig.tight_layout()
    zapisz(fig, "salience")
    return sal[ms == 40][0], sal[ms == 64][0]


if __name__ == "__main__":
    szereg()
    print("salience oktawa niżej / wyżej:", salience())
