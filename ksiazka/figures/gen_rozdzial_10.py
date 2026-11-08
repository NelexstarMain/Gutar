"""Wykresy rozdziału 10: uwaga między wysokościami (zabawkowy mechanizm oktawowy), maska okna, skalowanie przez sqrt(d)."""
import numpy as np
from figstyle import *


def softmax(x, ax=-1):
    x = x - x.max(axis=ax, keepdims=True)
    e = np.exp(x)
    return e / e.sum(axis=ax, keepdims=True)


def uwaga():
    fig, (a1, a2, a3) = nowa_figura("pelna", 2.5, ncols=3, gridspec_kw={"width_ratios": [1, 1, 1.1]})
    # (a) zabawka: S = 36 wysokości, zapytanie i klucz = chroma (one-hot po 12), duża skala => uwaga na oktawy
    S = 36
    chroma = np.eye(12)[np.arange(S) % 12]
    scores = 4.0 * chroma @ chroma.T       # = 4 dla tej samej klasy wysokości, 0 dla innej
    A = softmax(scores)
    assert np.allclose(A.sum(1), 1)
    i = 14
    zajete = np.nonzero(A[i] > 0.05)[0]
    assert set(zajete) == {2, 14, 26}                                              # oktawy: 14 +- 12
    a1.imshow(A, cmap="Blues", origin="upper", interpolation="nearest", vmin=0, vmax=A.max())
    a1.plot([i], [i], "s", mfc="none", mec=POMARANCZ, ms=7, mew=1.0)
    a1.set_axis_off()
    panel(a1, "a")
    # (b) maska okna czasowego: |t - u| <= W
    T, W = 30, 5
    M = (np.abs(np.arange(T)[:, None] - np.arange(T)[None]) <= W).astype(float)
    a2.imshow(M, cmap="Blues", origin="upper", interpolation="nearest", vmin=0, vmax=1.4)
    a2.set_axis_off()
    panel(a2, "b")
    # (c) odchylenie standardowe q.k bez i z dzieleniem przez sqrt(d)
    rng = np.random.default_rng(0)
    ds = np.array([4, 16, 64, 256])
    sd, sds = [], []
    for d in ds:
        q = rng.standard_normal((100000, d))
        k = rng.standard_normal((100000, d))
        dp = (q * k).sum(1)
        sd.append(dp.std())
        sds.append((dp / np.sqrt(d)).std())
    assert np.allclose(sd, np.sqrt(ds), rtol=0.03) and np.allclose(sds, 1, rtol=0.03)
    uklad_xy(a3, (-0.1, 6.4), (-0.2, 17.5), rownaskala=False)
    xs = np.log2(ds)
    a3.plot(xs, sd, "-o", color=POMARANCZ, ms=3.5, lw=1.3)
    a3.plot(xs, sds, "-o", color=NIEBIESKI, ms=3.5, lw=1.3)
    panel(a3, "c")
    fig.tight_layout(w_pad=0.9)
    zapisz(fig, "uwaga")
    return sd, sds


if __name__ == "__main__":
    print(uwaga())
