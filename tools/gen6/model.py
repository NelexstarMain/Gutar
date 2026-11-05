"""model.py - sieć generacji 6.

  wejście  HCQT  [B, C, T, P]   (P = 3 biny na półton)
  1. trzon         conv 3x7, C -> H
  2. bloki harmoniczne (n_harm_blocks): każdy łączy wartości z binów leżących na alikwotach (0,5x, 1x, 2x ... 6x względem f0 kandydata,
     przesunięcia o 36*log2(h) binów) - jedna warstwa widzi całą serię harmoniczną, także alikwoty powyżej kanałów HCQT - potem
     konwolucja sąsiednich binów (rozstrojenie, nieharmoniczność) i konwolucja w czasie z rosnącą dylatacją; połączenia resztkowe.
  3. zejście do półtonów (conv 1x3, krok 3) + wyuczone osadzenie wysokości (sieć wie, w którym rejestrze jest kandydat).
  4. warstwy kontekstu (n_ctx_layers), każda: uwaga w czasie dla każdej wysokości (okno +-time_window klatek, w obie strony przy
     analizie nagrania, tylko wstecz gdy causal=True), uwaga między wysokościami w tej samej klatce (oktawy, alikwoty innych strun,
     akord jako całość), feed-forward. Pre-norm, premie za odległość (w czasie i w półtonach).
  5. głowice: początek, brzmi (dostaje p(początek), jak w Onsets and Frames), koniec, głośność, tabulatura (struna x próg).

Różnice względem gen 5: krok 23 ms zamiast 46 ms, głowice końca/głośności/tabulatury, uwaga w obie strony i między wysokościami,
osadzenie wysokości, normalizacja warstw, dropout, maski dostępności etykiet (dane różnych formatów).
"""
from __future__ import annotations
import math
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from .config import Config, FeatureConfig, LabelConfig, ModelConfig


class ChanNorm(nn.Module):
    """LayerNorm po kanałach dla tensora [B, H, T, P]."""
    def __init__(self, H):
        super().__init__()
        self.ln = nn.LayerNorm(H)

    def forward(self, x):
        return self.ln(x.permute(0, 2, 3, 1)).permute(0, 3, 1, 2)


def shift_pitch(x, k):
    """y[..., p] = x[..., p + k] (zera poza zakresem)."""
    if k == 0:
        return x
    P = x.shape[-1]
    if abs(k) >= P:
        return torch.zeros_like(x)
    if k > 0:
        return F.pad(x[..., k:], (0, k))
    return F.pad(x[..., :k], (-k, 0))


class HarmonicBlock(nn.Module):
    def __init__(self, H, offsets_bins, time_kernel=3, dilation=1, dropout=0.0):
        super().__init__()
        self.offs = list(offsets_bins)
        self.norm = ChanNorm(H)
        self.harm = nn.Conv2d(H * len(self.offs), H, 1)
        self.local = nn.Conv2d(H, H, (1, 5), padding=(0, 2), groups=H)
        self.time = nn.Conv2d(H, H, (time_kernel, 1), padding=(dilation * (time_kernel // 2), 0), dilation=(dilation, 1))
        self.drop = nn.Dropout(dropout)

    def forward(self, x):
        h = self.norm(x)
        h = self.harm(torch.cat([shift_pitch(h, k) for k in self.offs], dim=1))
        h = F.gelu(self.local(F.gelu(h)))
        h = self.time(h)
        return x + self.drop(F.gelu(h))


class LocalTimeAttention(nn.Module):
    """Uwaga w czasie w oknie +-W klatek (blokowo: blok W patrzy na bloki sąsiednie, pamięć O(T*3W)), osobno dla każdej wysokości.
    x: [N, T, D] (N = B * S). causal: tylko klatki <= t."""
    def __init__(self, D, nh, W, causal=False, dropout=0.0):
        super().__init__()
        self.D, self.nh, self.dh, self.W, self.causal = D, nh, D // nh, W, causal
        self.qkv = nn.Linear(D, 3 * D)
        self.o = nn.Linear(D, D)
        self.rel = nn.Parameter(torch.zeros(nh, 2 * W + 1))
        self.drop = nn.Dropout(dropout)

    def forward(self, x):
        N, T, D = x.shape
        W, nh, dh = self.W, self.nh, self.dh
        nb = (T + W - 1) // W
        Tp = nb * W
        q, k, v = self.qkv(F.pad(x, (0, 0, 0, Tp - T))).chunk(3, dim=-1)
        q = q.view(N, nb, W, nh, dh).permute(0, 3, 1, 2, 4)                       # N nh nb W dh
        def ctx(z):
            z = z.view(N, nb, W, nh, dh).permute(0, 3, 1, 2, 4)
            zp = F.pad(z, (0, 0, 0, 0, 1, 1))                                     # blok przed i po
            return torch.cat([zp[:, :, :-2], zp[:, :, 1:-1], zp[:, :, 2:]], dim=3)  # N nh nb 3W dh
        k, v = ctx(k), ctx(v)
        sc = (q @ k.transpose(-1, -2)) / math.sqrt(dh)                            # N nh nb W 3W
        ti = torch.arange(W, device=x.device)[:, None]
        si = torch.arange(3 * W, device=x.device)[None] - W
        d = si - ti                                                               # s - t
        ok = d.abs() <= W
        if self.causal:
            ok = ok & (d <= 0)
        bi = torch.arange(nb, device=x.device)[:, None, None] * W
        absk = bi + si[None]                                                      # numer klatki klucza
        okb = ok[None] & (absk >= 0) & (absk < T)                                 # nb W 3W
        sc = sc + self.rel[:, (d.clamp(-W, W) + W)][:, None]
        sc = sc.masked_fill(~okb[None, None], float('-inf'))
        a = self.drop(torch.softmax(sc, dim=-1))
        y = (a @ v).permute(0, 2, 3, 1, 4).reshape(N, Tp, D)[:, :T]
        return self.o(y)


class PitchAttention(nn.Module):
    """Uwaga między wysokościami w jednej klatce; premia zależna od odległości w półtonach (oktawa = 12, duodecyma = 19 ...).
    x: [N, S, D] (N = B * T)."""
    def __init__(self, D, nh, S, dropout=0.0):
        super().__init__()
        self.nh, self.dh, self.S = nh, D // nh, S
        self.qkv = nn.Linear(D, 3 * D)
        self.o = nn.Linear(D, D)
        self.rel = nn.Parameter(torch.zeros(nh, 2 * S - 1))
        self.drop = nn.Dropout(dropout)

    def forward(self, x):
        N, S, D = x.shape
        q, k, v = self.qkv(x).view(N, S, 3, self.nh, self.dh).permute(2, 0, 3, 1, 4)
        sc = (q @ k.transpose(-1, -2)) / math.sqrt(self.dh)
        i = torch.arange(S, device=x.device)
        sc = sc + self.rel[:, (i[None] - i[:, None]) + self.S - 1][None]
        a = self.drop(torch.softmax(sc, dim=-1))
        return self.o((a @ v).transpose(1, 2).reshape(N, S, D))


class ContextLayer(nn.Module):
    def __init__(self, D, nh, S, W, causal, pitch_attention, dropout):
        super().__init__()
        self.n1, self.ta = nn.LayerNorm(D), LocalTimeAttention(D, nh, W, causal, dropout)
        self.pa = PitchAttention(D, nh, S, dropout) if pitch_attention else None
        self.n2 = nn.LayerNorm(D) if pitch_attention else None
        self.n3 = nn.LayerNorm(D)
        self.ff = nn.Sequential(nn.Linear(D, 4 * D), nn.GELU(), nn.Dropout(dropout), nn.Linear(4 * D, D))
        self.drop = nn.Dropout(dropout)

    def forward(self, h):  # [B, T, S, D]
        B, T, S, D = h.shape
        z = self.n1(h).permute(0, 2, 1, 3).reshape(B * S, T, D)
        h = h + self.drop(self.ta(z).view(B, S, T, D).permute(0, 2, 1, 3))
        if self.pa is not None:
            h = h + self.drop(self.pa(self.n2(h).reshape(B * T, S, D)).view(B, T, S, D))
        return h + self.drop(self.ff(self.n3(h)))


class TabHead(nn.Module):
    """Tabulatura: dla struny s i progu f logit z cech półtonu tuning[s]+f (wagi osobne dla struny), plus logit ciszy struny
    z maksimum cech w jej zakresie. Wyjście [B, T, n_strings, 1 + n_frets]."""
    def __init__(self, D, lc: LabelConfig, fc: FeatureConfig):
        super().__init__()
        self.ns, self.nf = lc.n_strings, lc.n_frets
        idx = torch.tensor([[t + f - fc.midi_lo for f in range(lc.n_frets)] for t in lc.tuning])
        self.register_buffer('ok', (idx >= 0) & (idx < fc.n_semis), persistent=False)
        self.register_buffer('idx', idx.clamp(0, fc.n_semis - 1), persistent=False)
        self.fret = nn.Linear(D, self.ns)
        self.fret_pos = nn.Parameter(torch.zeros(self.ns, self.nf))  # premia za próg (wysokie progi rzadsze)
        self.silent = nn.Sequential(nn.Linear(D, D), nn.GELU(), nn.Linear(D, 1))

    def forward(self, h):  # [B, T, S, D]
        B, T, S, D = h.shape
        per = self.fret(h)                                            # B T S ns
        g = per[:, :, self.idx, torch.arange(self.ns, device=h.device)[:, None]]  # B T ns nf
        g = (g + self.fret_pos).masked_fill(~self.ok, float('-inf'))
        hs = h[:, :, self.idx]                                        # B T ns nf D
        hs = hs.masked_fill(~self.ok[..., None], -1e4).amax(dim=3)    # B T ns D
        return torch.cat([self.silent(hs), g], dim=-1)


class Gen6(nn.Module):
    def __init__(self, cfg: Config):
        super().__init__()
        f, m, lc = cfg.features, cfg.model, cfg.labels
        self.cfg = cfg
        self.S, self.bps = f.n_semis, f.bins_per_semi
        H, D = m.hidden, m.d_model
        offs = sorted({int(round(12 * f.bins_per_semi * math.log2(h))) for h in m.harm_offsets})
        self.stem = nn.Conv2d(f.n_channels, H, (3, 7), padding=(1, 3))
        dil = list(m.time_dilations) + [m.time_dilations[-1]] * max(0, m.n_harm_blocks - len(m.time_dilations))
        self.blocks = nn.ModuleList([HarmonicBlock(H, offs, m.time_kernel, dil[i], m.dropout) for i in range(m.n_harm_blocks)])
        self.down = nn.Conv2d(H, D, (1, f.bins_per_semi), stride=(1, f.bins_per_semi))
        self.pitch_emb = nn.Parameter(torch.zeros(f.n_semis, D))
        self.ctx = nn.ModuleList([ContextLayer(D, m.n_heads, f.n_semis, m.time_window, m.causal, m.pitch_attention, m.dropout)
                                  for _ in range(m.n_ctx_layers)])
        self.norm = nn.LayerNorm(D)
        heads = set(m.heads)
        self.heads = heads
        mlp = lambda i, o: nn.Sequential(nn.Linear(i, D), nn.GELU(), nn.Linear(D, o))
        self.h_onset = mlp(D, 1)
        self.h_frame = mlp(D + (1 if m.onset_to_frame else 0), 1)
        self.h_offset = mlp(D, 1) if 'offset' in heads else None
        self.h_vel = mlp(D, 1) if 'velocity' in heads else None
        self.h_tab = TabHead(D, lc, f) if 'tab' in heads else None
        self.onset_to_frame = m.onset_to_frame
        # receptive field w czasie (do inferencji kawałkami)
        self.halo = 1 + sum(d * (m.time_kernel // 2) for d in dil[:m.n_harm_blocks]) + m.n_ctx_layers * 2 * m.time_window
        nn.init.constant_(self.h_onset[-1].bias, -3.0)
        nn.init.constant_(self.h_frame[-1].bias, -2.0)
        if self.h_offset is not None:
            nn.init.constant_(self.h_offset[-1].bias, -3.0)

    def encode(self, x):  # [B, C, T, P] -> [B, T, S, D]
        h = F.gelu(self.stem(x))
        for b in self.blocks:
            h = b(h)
        h = self.down(h).permute(0, 2, 3, 1) + self.pitch_emb
        for c in self.ctx:
            h = c(h)
        return self.norm(h)

    def forward(self, x):
        """x: [B, C, T, P]. Zwraca słownik logitów: onset/frame/offset [B,T,S], velocity [B,T,S] (przed sigmoid),
        tab [B,T,ns,1+nf]."""
        h = self.encode(x)
        out = {'onset': self.h_onset(h)[..., 0]}
        fin = torch.cat([h, torch.sigmoid(out['onset']).detach()[..., None]], -1) if self.onset_to_frame else h
        out['frame'] = self.h_frame(fin)[..., 0]
        if self.h_offset is not None:
            out['offset'] = self.h_offset(h)[..., 0]
        if self.h_vel is not None:
            out['velocity'] = self.h_vel(h)[..., 0]
        if self.h_tab is not None:
            out['tab'] = self.h_tab(h)
        return out

    def n_params(self):
        return sum(p.numel() for p in self.parameters())

    @torch.no_grad()
    def predict(self, X, chunk=512):
        """Całe nagranie X [T, C, P] (numpy) -> prawdopodobieństwa numpy: onset/frame/offset/velocity [T,S], tab [T,ns,1+nf].
        Kawałkami z zakładką `halo`, więc wynik nie zależy od długości kawałka."""
        was = self.training
        self.eval()
        T = len(X)
        dev = next(self.parameters()).device
        res = {}
        for c0 in range(0, T, chunk):
            lo, hi = max(0, c0 - self.halo), min(T, c0 + chunk + self.halo)
            x = torch.from_numpy(np.ascontiguousarray(X[lo:hi].transpose(1, 0, 2)))[None].to(dev)
            y = self.forward(x)
            a, b = c0 - lo, c0 - lo + min(chunk, T - c0)
            for k, v in y.items():
                p = torch.softmax(v, -1) if k == 'tab' else torch.sigmoid(v)
                res.setdefault(k, []).append(p[0, a:b].cpu().numpy())
        self.train(was)
        return {k: np.concatenate(v) for k, v in res.items()}
