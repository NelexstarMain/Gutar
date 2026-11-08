"""Wykresy rozdziału 7: prawdziwa HCQT syntetycznego nagrania gitary (funkcje z repozytorium Gutar)."""
import numpy as np
import gutar
from matplotlib import cm
from figstyle import *
from tools.gen6.features import hcqt


def hcqt_przyklad():
    ex, X, _ = gutar.wynik(3, 1, 6.0)
    m, cfg, _ = gutar.model()
    fc = cfg.features
    cen = fc.frame_center(np.arange(len(X)))
    liczba = [sum(n.onset <= c <= n.offset for n in ex.notes) for c in cen]
    t0 = int(np.argmax(liczba))
    grane = [3 * (int(n.pitch) - fc.midi_lo) + 1 for n in ex.notes if n.onset <= cen[t0] <= n.offset]
    fig, (a1, a2) = nowa_figura("pelna", 3.7, ncols=2, gridspec_kw={"width_ratios": [1.15, 1]})
    a1.imshow(X[:, 1, :].T, origin="lower", aspect="auto", cmap="viridis", vmin=0, vmax=1.2,
              extent=[0, len(X), 0, X.shape[2]], interpolation="nearest")
    for n in ex.notes:
        a1.plot([fc.time_to_frame(n.onset)], [3 * (n.pitch - fc.midi_lo) + 1], "o", color="white", ms=3.4, mec=POMARANCZ, mew=0.9)
    a1.axvline(t0 + 0.5, color=POMARANCZ, lw=1.1, ls="--")
    a1.set_axis_off(); panel(a1, "a")
    a2.imshow(X[t0], origin="upper", aspect="auto", cmap="viridis", vmin=0, vmax=1.2, interpolation="nearest")
    for kanal in (5.5,):                                     # granica okna długiego (6 kanałów) i krótkiego (3 kanały)
        a2.axhline(kanal, color="white", lw=1.6)
    for r in np.arange(0.5, 8.5, 1.0):
        a2.axhline(r, color="white", lw=0.4, alpha=0.6)
    for b in grane:
        a2.axvline(b, color=POMARANCZ, lw=0.9, ls="--", alpha=0.95)
        a2.plot([b], [-0.85], "v", color=POMARANCZ, ms=5.5, clip_on=False)
    a2.set_axis_off(); panel(a2, "b")
    fig.tight_layout(w_pad=1.0)
    zapisz(fig, "hcqt-przyklad")
    return t0, liczba[t0]


def niezmiennik():
    ex, X, _ = gutar.wynik(3, 1, 6.0)
    m, cfg, _ = gutar.model()
    fc = cfg.features
    x = ex.meta["signal"]
    fig, (a1, a2) = nowa_figura("pelna", 2.4, ncols=2)
    # (a) odwzorowanie amplituda -> cecha (oś amplitudy logarytmiczna) dla dwóch głośności nagrania
    A = np.logspace(-6, 1, 400)
    L = lambda a: 20 * np.log10(a + 1e-9)
    ref = -20.0
    cecha = lambda a, r: np.clip((L(a) - r) / 60 + 1, 0, 1.3)
    uklad_xy(a1, (np.log10(A[0]) - 0.2, 1.1), (-0.15, 1.5), rownaskala=False)
    a1.plot(np.log10(A), cecha(A, ref), color=NIEBIESKI, lw=1.6)
    g = 3.0
    a1.plot(np.log10(A * g), cecha(A * g, ref + 20 * np.log10(g)), color=POMARANCZ, lw=1.0, ls="--")
    assert np.allclose(cecha(A, ref), cecha(A * g, ref + 20 * np.log10(g)), atol=1e-3)   # ta sama krzywa po przesunięciu referencji
    panel(a1, "a")
    # (b) cechy dla nagrania i dla nagrania 10 razy cichszego (rozrzut punktów leży na przekątnej)
    Xg = hcqt(x * 0.1, fc)
    idx = np.random.default_rng(0).choice(X.size, 4000, replace=False)
    a2.scatter(X.ravel()[idx], Xg.ravel()[idx], s=3, color=NIEBIESKI, alpha=0.5, lw=0)
    a2.plot([0, 1.3], [0, 1.3], color=SZARY, lw=0.7, ls=":")
    a2.set_xlim(-0.05, 1.35); a2.set_ylim(-0.05, 1.35); a2.set_aspect("equal"); a2.set_axis_off()
    os_strzalka(a2, (-0.05, 0), (1.35, 0)); os_strzalka(a2, (0, -0.05), (0, 1.35))
    assert np.abs(X - Xg).max() < 1e-3
    panel(a2, "b")
    fig.tight_layout(w_pad=1.0)
    zapisz(fig, "niezmiennik-glosnosci")
    return float(np.abs(X - Xg).max())


if __name__ == "__main__":
    print("klatka akordu:", hcqt_przyklad())
    print("max różnica po zmianie głośności 10x:", niezmiennik())
