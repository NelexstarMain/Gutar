"""Wykresy rozdziału 16: dekoder na prawdziwych wyjściach wytrenowanego modelu Gen 6 (mapy prawdopodobieństw -> lista nut)."""
import copy

import numpy as np
import gutar
from figstyle import *
from tools.gen6.decode import apply_decode_override, decode_notes


def dekoder():
    m, cfg, _ = gutar.model()
    cfgt = copy.deepcopy(cfg)
    apply_decode_override(cfgt, str(gutar.REPO / "tools/gen6/server/model/best.pt"))
    fc, lc = cfg.features, cfg.labels
    ex, X, p = gutar.wynik(3, 1, 6.0)
    notes = decode_notes(p, fc, cfgt.decode, lc)
    # zgodność z prawdą: dla każdej nuty wzorca najbliższy początek tej samej wysokości
    bl = []
    for n in ex.notes:
        c = [q for q in notes if q.pitch == n.pitch]
        bl.append(min(abs(q.onset - n.onset) for q in c))
    assert len(notes) == len(ex.notes) == 15 and max(bl) < 0.05, (len(notes), max(bl))
    cen = fc.frame_center(np.arange(len(X)))
    t0, t1, s0, s1 = 0, 110, 4, 40
    fig = plt_figura()
    a1, a2 = fig
    a1.imshow(p["frame"][t0:t1, s0:s1].T, origin="lower", aspect="auto", cmap="Blues", vmin=0, vmax=1,
              interpolation="nearest", extent=[t0, t1, s0, s1])
    for n in ex.notes:                                                    # prawda: cienkie czarne kreski
        a1.plot([fc.time_to_frame(n.onset), fc.time_to_frame(n.offset)], [n.pitch - 36 + 0.5 + 0.18] * 2, color=CZARNY, lw=0.9)
    for n in notes:                                                       # wynik dekodera: pomarańczowe
        a1.plot([fc.time_to_frame(n.onset), fc.time_to_frame(n.offset)], [n.pitch - 36 + 0.5 - 0.18] * 2, color=POMARANCZ, lw=1.6)
    a1.set_xlim(t0, t1); a1.set_ylim(s0, s1)
    a1.set_axis_off()
    panel(a1, "a")
    # (b) jeden półton: krzywe p(początek), p(brzmi), p(koniec) i granice nut
    licz = np.bincount([int(n.pitch) - 36 for n in ex.notes], minlength=53)
    s = int(np.argmax(licz))
    tt = np.arange(len(X))
    a2.set_axis_off()
    a2.set_xlim(0, len(X)); a2.set_ylim(-0.1, 1.25)
    os_strzalka(a2, (0, 0), (len(X), 0))
    a2.plot(tt, p["frame"][:, s], color=NIEBIESKI, lw=1.4)
    a2.plot(tt, p["onset"][:, s], color=POMARANCZ, lw=1.1)
    a2.plot(tt, p["offset"][:, s], color=SZARY, lw=1.1, ls="--")
    for yv in (cfgt.decode.th_onset, cfgt.decode.th_offset):
        a2.plot([0, len(X)], [yv, yv], color="#C8C8C8", lw=0.5, ls=":")
    for n in notes:
        if int(n.pitch) - 36 == s:
            for tx in (fc.time_to_frame(n.onset), fc.time_to_frame(n.offset)):
                a2.plot([tx, tx], [-0.06, 1.15], color=CZARNY, lw=0.6)
    panel(a2, "b")
    fig_ = a1.figure
    fig_.tight_layout(w_pad=1.0)
    zapisz(fig_, "dekoder-model")
    return len(notes), max(bl), s, int(licz[s])


def plt_figura():
    fig, axs = nowa_figura("pelna", 2.7, ncols=2, gridspec_kw={"width_ratios": [1.05, 1]})
    return axs


if __name__ == "__main__":
    print(dekoder())
