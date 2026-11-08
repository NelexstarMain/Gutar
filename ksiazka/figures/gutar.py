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
