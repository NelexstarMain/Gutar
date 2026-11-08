"""Wykresy rozdziału 13: wagi bloków harmonicznych prawdziwego, wytrenowanego modelu Gen 6 (średni |w| w grupach wejść o danym przesunięciu)."""
import numpy as np
import gutar
from figstyle import *


def wagi_bloku():
    m, cfg, _ = gutar.model()
    offs = m.blocks[0].offs                            # [-36, 0, 36, 57, 72, 84, 93]
    harm = [0.5, 1, 2, 3, 4, 5, 6]
    assert offs == [-36, 0, 36, 57, 72, 84, 93] and len(m.blocks) == 3
    H = 48
    M = np.zeros((3, 7))
    for bi, b in enumerate(m.blocks):
        w = b.harm.weight.detach().numpy()[:, :, 0, 0]       # [48, 7*48]
        assert w.shape == (H, 7 * H)
        for i in range(7):
            M[bi, i] = np.abs(w[:, i * H:(i + 1) * H]).mean()
    fig, axs = nowa_figura("pelna", 2.2, ncols=3, sharey=True)
    for bi, ax in enumerate(axs):
        ax.set_axis_off()
        ax.set_xlim(-0.8, 7.0)
        ax.set_ylim(-0.012, 0.125)
        os_strzalka(ax, (-0.6, 0), (6.9, 0))
        ax.bar(np.arange(7), M[bi], color=NIEBIESKI, width=0.62)
        for i, h in enumerate(harm):
            ax.text(i, -0.004, r"$\frac{1}{2}$" if h == 0.5 else f"${h:g}$", ha="center", va="top", fontsize=7.5)
        panel(ax, "abc"[bi])
    fig.tight_layout(w_pad=0.6)
    zapisz(fig, "harm-wagi")
    return M


if __name__ == "__main__":
    M = wagi_bloku()
    print(np.round(M, 4))
