"""Wykresy rozdziału 9: GELU i ReLU; pole widzenia konwolucji z dylatacją (schemat i pomiar gradientu w PyTorch)."""
from math import erf, sqrt

import numpy as np
from figstyle import *


def gelu():
    Phi = np.vectorize(lambda z: 0.5 * (1 + erf(z / sqrt(2))))
    z = np.linspace(-3.5, 3.5, 400)
    fig, ax = nowa_figura("tekst", 2.4)
    uklad_xy(ax, (-3.8, 3.8), (-1.0, 3.8))
    ax.plot(z, np.maximum(0, z), color=SZARY, lw=1.1, ls="--")
    ax.plot(z, z * Phi(z), color=NIEBIESKI, lw=1.7)
    assert abs((1.0 * Phi(1.0)) - 0.8413) < 1e-3 and (z * Phi(z)).min() > -0.18
    fig.tight_layout()
    zapisz(fig, "gelu")


def pole_widzenia():
    import torch
    torch.manual_seed(0)

    class S(torch.nn.Module):
        def __init__(s):
            super().__init__()
            s.stem = torch.nn.Conv2d(1, 4, (3, 7), padding=(1, 3))
            s.c = torch.nn.ModuleList([torch.nn.Conv2d(4, 4, (3, 1), padding=(d, 0), dilation=(d, 1)) for d in (1, 2, 4)])

        def forward(s, x):
            h = torch.nn.functional.gelu(s.stem(x))
            for c in s.c:
                h = h + torch.nn.functional.gelu(c(h))
            return h

    m = S()
    T, t0 = 41, 20
    x = torch.randn(1, 1, T, 20, requires_grad=True)
    y = m(x)
    y[0, :, t0, 10].sum().backward()
    g = x.grad.abs().sum(dim=(0, 1, 3)).numpy()
    nz = np.nonzero(g > 0)[0]
    assert nz.min() - t0 == -8 and nz.max() - t0 == 8      # pole widzenia: 1 + (1 + 2 + 4) = 8 klatek z każdej strony

    fig, (a1, a2) = nowa_figura("pelna", 2.7, ncols=2, gridspec_kw={"width_ratios": [1.2, 1]})
    # (a) schemat połączeń: wiersze = warstwy (od wejścia do wyjścia), kropki = klatki
    a1.set_axis_off()
    xs = np.arange(-9, 10)
    warstwy = [("stem", 1), ("b1", 1), ("b2", 2), ("b3", 4)]
    L = len(warstwy)
    a1.set_xlim(-10, 10)
    a1.set_ylim(-0.7, L + 0.6)
    aktywne = {t0 - t0}                 # zbiór klatek (względnych) na wyjściu
    poziomy = [{0}]
    for (nazwa, d) in reversed(warstwy):
        nowe = set()
        for t in poziomy[-1]:
            for dt in (-d, 0, d):
                nowe.add(t + dt)
        poziomy.append(nowe)
    poziomy = poziomy[::-1]               # poziomy[0] = wejście, poziomy[L] = wyjście
    for i, zbior in enumerate(poziomy):
        y_ = i
        for t in xs:
            a1.plot([t], [y_], "o", color="#D0D0D0", ms=2.6)
        for t in zbior:
            a1.plot([t], [y_], "o", color=NIEBIESKI if i < L else POMARANCZ, ms=4)
    for i in range(L):
        d = warstwy[i][1]
        for t in poziomy[i + 1]:
            for dt in (-d, 0, d):
                a1.plot([t, t + dt], [i + 1, i], color=SZARY, lw=0.45, zorder=0)
    assert max(abs(t) for t in poziomy[0]) == 8        # trzon (d=1) i trzy konwolucje z dylatacjami 1,2,4
    panel(a1, "a")
    # (b) zmierzona wartość |gradient| wyjścia w klatce 0 względem wejścia w klatce t
    a2.set_axis_off()
    off = np.arange(T) - t0
    wazne = np.abs(off) <= 14
    a2.set_xlim(-15, 15)
    a2.set_ylim(-0.12 * g.max(), 1.15 * g.max())
    os_strzalka(a2, (-15, 0), (15, 0))
    kol = [NIEBIESKI if abs(o) <= 8 else "#B0B0B0" for o in off[wazne]]
    a2.bar(off[wazne], g[wazne], color=kol, width=0.7)
    a2.plot([-8.5, -8.5], [0, 1.0 * g.max()], color=POMARANCZ, lw=0.8, ls="--")
    a2.plot([8.5, 8.5], [0, 1.0 * g.max()], color=POMARANCZ, lw=0.8, ls="--")
    panel(a2, "b")
    fig.tight_layout(w_pad=1.0)
    zapisz(fig, "pole-widzenia")
    return nz.min() - t0, nz.max() - t0


if __name__ == "__main__":
    gelu()
    print("zakres niezerowego gradientu:", pole_widzenia())
