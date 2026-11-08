"""Most do repozytorium Gutar: ładuje prawdziwy, wytrenowany model Gen 6 (tools/gen6/server/model/best.pt)
oraz funkcje HCQT/dekodera z repozytorium, żeby rysunki książki pochodziły z działającego modelu."""
import sys
from functools import lru_cache
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))


@lru_cache(maxsize=1)
def model():
    import torch
    from tools.gen6.config import Config
    from tools.gen6.model import Gen6
    ck = torch.load(REPO / "tools/gen6/server/model/best.pt", map_location="cpu", weights_only=False)
    cfg = Config.from_dict(ck["config"])
    m = Gen6(cfg)
    m.load_state_dict(ck["net"])
    m.eval()
    return m, cfg, ck


def przyklad(i=3, seed=1, dur=6.0):
    from tools.gen6.synth import random_example
    return random_example(i, dur=dur, seed=seed)


@lru_cache(maxsize=4)
def wynik(i=3, seed=1, dur=6.0):
    """(przykład, HCQT [T,C,P], prawdopodobieństwa modelu)"""
    from tools.gen6.features import hcqt
    m, cfg, _ = model()
    ex = przyklad(i, seed, dur)
    X = hcqt(ex.meta["signal"], cfg.features)
    return ex, X, m.predict(X)


def uwaga_wysokosci(X, warstwa=0, t=None):
    """Wagi uwagi między wysokościami w klatce t (warstwa kontekstu `warstwa`): tablica [n_heads, S, S] (średnia po paczce=1)."""
    import math
    import torch
    import torch.nn.functional as F
    m, cfg, _ = model()
    x = torch.from_numpy(X.transpose(1, 0, 2).copy())[None]
    with torch.no_grad():
        h = F.gelu(m.stem(x))
        for b in m.blocks:
            h = b(h)
        h = m.down(h).permute(0, 2, 3, 1) + m.pitch_emb                       # [1, T, S, D]
        for l, c in enumerate(m.ctx):
            B, T, S, D = h.shape
            z = c.n1(h).permute(0, 2, 1, 3).reshape(B * S, T, D)
            if l == warstwa:
                pass
            h = h + c.ta(z).view(B, S, T, D).permute(0, 2, 1, 3)
            if l == warstwa:
                u = c.n2(h)[0, t]                                             # [S, D]
                pa = c.pa
                q, k, v = pa.qkv(u).view(S, 3, pa.nh, pa.dh).permute(1, 2, 0, 3)
                sc = (q @ k.transpose(-1, -2)) / math.sqrt(pa.dh)
                i = torch.arange(S)
                sc = sc + pa.rel[:, (i[None] - i[:, None]) + S - 1]
                return torch.softmax(sc, dim=-1).numpy()
            h = h + c.pa(c.n2(h).reshape(B * T, S, D)).view(B, T, S, D)
            h = h + c.ff(c.n3(h))
