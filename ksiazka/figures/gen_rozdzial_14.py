"""Wykresy rozdziału 14 z prawdziwego, wytrenowanego modelu Gen 6: wyuczone premie położenia, uwaga między wysokościami w klatce z akordem, pole widzenia."""
import math

import numpy as np
import torch
import gutar
from figstyle import *

S = 53


def uwaga_wysokosci():
    m, cfg, _ = gutar.model()
    ex, X, _ = gutar.wynik(3, 1, 6.0)
    fc = cfg.features
    cen = fc.frame_center(np.arange(len(X)))
    akt = [[n for n in ex.notes if n.onset <= c <= n.offset] for c in cen]
    t0 = int(np.argmax([len(a) for a in akt]))
    grane = sorted(int(n.pitch) - 36 for n in akt[t0])
    A = gutar.uwaga_wysokosci(X, 0, t0).mean(0)                    # średnia po 4 głowicach, [S, S]
    assert np.allclose(A.sum(1), 1, atol=1e-4)
    rel = m.ctx[0].pa.rel.detach().numpy()[2]                       # warstwa 0, głowica 2: premie dla j - i = d
    d = np.arange(-(S - 1), S)
    fig, (a1, a2, a3) = nowa_figura("pelna", 2.6, ncols=3, gridspec_kw={"width_ratios": [1.15, 1, 1]})
    # (a) wyuczona premia r_d i interwały szeregu alikwotów -12 log2 h
    uklad_xy(a1, (-54, 54), (-2.4, 3.1), rownaskala=False)
    a1.plot(d, rel, color=NIEBIESKI, lw=1.3)
    for h in (2, 3, 4, 5, 6, 7):
        a1.plot([-12 * math.log2(h)] * 2, [-2.2, 2.9], color=POMARANCZ, lw=0.7, ls="--")
    # kontrola: dokładnie siedem odległości ma premię > 0,6: sześć interwałów alikwotów w dół i +12
    wysokie = set(int(x) for x in d[rel > 0.6])
    assert wysokie == {-34, -31, -28, -24, -19, -12, 12}, wysokie
    assert wysokie - {12} == {-round(12 * math.log2(h)) for h in (2, 3, 4, 5, 6, 7)}
    panel(a1, "a")
    # (b) macierz uwagi (wiersz = zapytanie, kolumna = klucz) w klatce z akordem
    a2.imshow(A, cmap="Blues", origin="upper", interpolation="nearest", vmin=0, vmax=np.percentile(A, 99.5))
    for s in grane:
        a2.plot([s], [-1.6], "v", color=POMARANCZ, ms=3.2, clip_on=False)
        a2.plot([-1.6], [s], ">", color=POMARANCZ, ms=3.2, clip_on=False)
    a2.set_axis_off()
    panel(a2, "b")
    # (c) wiersz najniższej nuty akordu: gdzie ona „patrzy”
    s0 = grane[0]
    a3.set_axis_off()
    a3.set_xlim(-1, S)
    a3.set_ylim(-0.03, A[s0].max() * 1.12)
    os_strzalka(a3, (-1, 0), (S, 0))
    for s in range(S):
        kol = POMARANCZ if s in grane else "#B0B0B0"
        a3.plot([s, s], [0, A[s0, s]], color=kol, lw=1.8 if s in grane else 0.9)
    suma_akord = float(sum(A[s0, s] for s in grane if s != s0))
    assert suma_akord > 0.35, suma_akord                          # większość uwagi trafia w inne nuty akordu
    panel(a3, "c")
    fig.tight_layout(w_pad=0.8)
    zapisz(fig, "uwaga-wysokosci")
    return t0, grane, suma_akord


def pole_widzenia_modelu():
    m, cfg, _ = gutar.model()
    ex, X, _ = gutar.wynik(3, 1, 6.0)
    x = torch.from_numpy(X.transpose(1, 0, 2).copy())[None].requires_grad_(True)
    out = m(x)
    t, s = 120, 28
    out["onset"][0, t, s].backward()
    g = x.grad.abs().sum(dim=(0, 1, 3)).numpy()
    nz = np.nonzero(g > 1e-12)[0]
    assert nz.min() - t == -94 and nz.max() - t == 94, (nz.min() - t, nz.max() - t)
    off = np.arange(len(g)) - t
    fig, ax = nowa_figura("tekst", 2.4)
    ax.set_axis_off()
    lim = 125
    ax.set_xlim(-lim, lim)
    ax.set_ylim(-1.2, 1.7)
    os_strzalka(ax, (-lim, -1.0), (lim, -1.0))
    sel = np.abs(off) <= lim
    y = np.log10(g[sel] + 1e-4)                                   # skala logarytmiczna, "dno" = brak zależności
    ax.fill_between(off[sel], -1.0, np.maximum(y, -1.0), color="#B8D4EC", lw=0)
    ax.plot(off[sel], np.maximum(y, -1.0), color=NIEBIESKI, lw=1.1)
    for xx, st in ((8, ":"), (94, "--")):
        for sgn in (-1, 1):
            ax.plot([sgn * xx] * 2, [-1.0, 1.55], color=POMARANCZ, lw=0.8, ls=st)
    for sgn in (-1, 1):
        ax.plot([sgn * 180] * 2, [-1.0, 1.55], color=SZARY, lw=0.6, ls="-.") if 180 <= lim else None
    fig.tight_layout()
    zapisz(fig, "pole-widzenia-modelu")
    return g[t], g[t + 40], g[t + 90], g[t + 95]


if __name__ == "__main__":
    print(uwaga_wysokosci())
    print(pole_widzenia_modelu())
