#!/usr/bin/env python3
"""train_gen5.py - uczy model gen 5 (konwolucyjna sieć na harmonicznie ułożonym widmie) i zapisuje wagi do src/gt_gen5model.hpp.

Wejście: zrzuty HCQT z silnika (GT_DUMPH=plik.bin gt_cli analyze nagranie.wav wynik.json): nagłówek int32 [T, C=9, P=159], potem
float32 T x C x P. Klatka t ma środek okna w (t*512 + 2048) / 11025 s; wysokość p = MIDI 36 + (p - 1)/3.
Wyjście sieci: dla każdej klatki i każdego półtonu MIDI 36..88: p(nuta brzmi), p(nuta zaczyna się w tej klatce).
Etykiety: korpus i środowiska (*.truth.json: t0 .. min(t1, ta)), GuitarSet (*.jams). Początek: najbliższa klatka 1, sąsiednie 0,4.

Opcja --attn dodaje blok uwagi (attention) w czasie: dla każdej wysokości klatka patrzy na ostatnią sekundę (22 klatki) tej samej
wysokości, 2 głowy, wyuczona premia za odległość, potem feed-forward; uwaga tylko wstecz.

Użycie:
  train_gen5.py --src środowiska <zrzuty> <prawda> 0.25 --src korpus <zrzuty> <prawda> 0.25 --src GuitarSet <zrzuty> <jams> 0.5
                [--val-gs 02_Funk] [--hidden 24] [--epochs 14] [--out src/gt_gen5model.hpp]
"""
import os, sys, glob, json, argparse, zlib, time
import numpy as np
import torch, torch.nn as nn, torch.nn.functional as F

M0, S, P, C, HOP, WIN, FSD = 36, 53, 159, 9, 512, 4096, 11025.0


def truth_notes(path):
    if path.endswith('.jams'):
        j = json.load(open(path)); out = []
        for a in j['annotations']:
            if a['namespace'] == 'note_midi':
                out += [(int(round(d['value'])), d['time'], d['time'] + d['duration']) for d in a['data']]
        return out
    t = json.load(open(path))
    return [(n['midi'], n['t0'], min(n['t1'], n.get('ta', n['t1']))) for n in t['notes']]


def labels(T, notes):
    fr = np.zeros((T, S), np.float32); on = np.zeros((T, S), np.float32)
    c = (np.arange(T) * HOP + WIN / 2) / FSD
    for m, a, b in notes:
        s = m - M0
        if s < 0 or s >= S:
            continue
        fr[(c >= a) & (c <= b), s] = 1
        k = int(round((a * FSD - WIN / 2) / HOP))
        for d, v in ((0, 1.0), (-1, 0.4), (1, 0.4)):
            if 0 <= k + d < T:
                on[k + d, s] = max(on[k + d, s], v)
    return fr, on


def load_dump(p):
    b = np.fromfile(p, np.uint8)
    T, Cc, Pp = np.frombuffer(b[:12].tobytes(), np.int32)
    return np.frombuffer(b[12:].tobytes(), np.float32).reshape(T, Cc, Pp)


def truth_path(tdir, name):
    for ext in ('.truth.json', '.jams'):
        p = os.path.join(tdir, name + ext)
        if os.path.exists(p):
            return p
    # zrzuty korpusów mają przedrostek zbioru (dev_, tr10000_): prawda bez niego
    if '_' in name:
        return truth_path(tdir, name.split('_', 1)[1]) if not name.startswith('env_') else None
    return None


class TimeAttention(nn.Module):
    """Uwaga w czasie dla każdej wysokości osobno: klatka t patrzy na klatki t-W+1..t (ostatnia sekunda) tej samej wysokości.
    nh głów po H/nh wymiarów, wyuczona premia za odległość w czasie, potem warstwa feed-forward (jak w transformerze)."""
    def __init__(self, H, W=22, nh=2):
        super().__init__()
        self.W, self.nh, self.dh = W, nh, H // nh
        self.qkv = nn.Conv2d(H, 3 * H, 1)
        self.o = nn.Conv2d(H, H, 1)
        self.rel = nn.Parameter(torch.zeros(nh, W))
        self.f1 = nn.Conv2d(H, 2 * H, 1); self.f2 = nn.Conv2d(2 * H, H, 1)

    def forward(self, h):  # B x H x T x P
        B, H, T, P = h.shape
        q, k, v = self.qkv(h).chunk(3, dim=1)
        def heads(x):  # -> (B*P) x nh x T x dh
            return x.reshape(B, self.nh, self.dh, T, P).permute(0, 4, 1, 3, 2).reshape(B * P, self.nh, T, self.dh)
        q, k, v = heads(q), heads(k), heads(v)
        sc = q @ k.transpose(-1, -2) / self.dh ** 0.5  # (BP) x nh x T x T
        ti = torch.arange(T)
        d = ti[:, None] - ti[None, :]                  # t - s
        ok = (d >= 0) & (d < self.W)
        bias = self.rel[:, d.clamp(0, self.W - 1)]      # nh x T x T
        sc = sc + bias[None]
        sc = sc.masked_fill(~ok[None, None], float('-inf'))
        att = torch.softmax(sc, dim=-1) @ v             # (BP) x nh x T x dh
        att = att.reshape(B, P, self.nh, T, self.dh).permute(0, 2, 4, 3, 1).reshape(B, H, T, P)
        h = h + self.o(att)
        return h + self.f2(F.relu(self.f1(h)))


class Net(nn.Module):
    def __init__(self, H=24, attn=False):
        super().__init__()
        self.c1 = nn.Conv2d(C, H, (3, 7), padding=(1, 3))     # alikwoty i sąsiednie wysokości
        self.c2 = nn.Conv2d(H, H, (3, 7), padding=(1, 3))
        self.c3 = nn.Conv2d(H, H, (5, 3), padding=(2, 1))     # kontekst w czasie (przed i po)
        self.c4 = nn.Conv2d(H, H, (1, 3), padding=(0, 36), dilation=(1, 36))  # oktawa niżej i wyżej
        self.c5 = nn.Conv2d(H, H, (3, 3), padding=(1, 1))
        self.att = TimeAttention(H) if attn else None
        self.out = nn.Conv2d(H, 2, (1, 3), stride=(1, 3))     # 3 biny -> półton; kanały: brzmi, początek

    def forward(self, x):  # x: B x C x T x P
        h = F.relu(self.c1(x))
        h = h + F.relu(self.c2(h))
        h = h + F.relu(self.c3(h))
        h = h + F.relu(self.c4(h))
        h = h + F.relu(self.c5(h))
        if self.att is not None:
            h = self.att(h)
        return self.out(h)  # B x 2 x T x S (logity)


def export(net, path, info):
    L = [('c1', net.c1), ('c2', net.c2), ('c3', net.c3), ('c4', net.c4), ('c5', net.c5), ('out', net.out)]
    s = ('// gt_gen5model.hpp - wagi modelu gen 5. WYGENEROWANE przez tools/train_gen5.py, nie edytować.\n// ' + info +
         '\n#pragma once\nnamespace gt {\nstatic constexpr bool kGen5Ready = true;\nstatic constexpr int kGen5H = %d;\n' % net.c1.out_channels)
    for name, m in L:
        w = m.weight.detach().numpy().astype(np.float32); b = m.bias.detach().numpy().astype(np.float32)
        s += 'static const float kG5_%s_w[%d] = {%s};\n' % (name, w.size, ','.join('%.6g' % x for x in w.ravel()))
        s += 'static const float kG5_%s_b[%d] = {%s};\n' % (name, b.size, ','.join('%.6g' % x for x in b.ravel()))
    if net.att is not None:
        A = net.att
        s += 'static constexpr int kGen5Attn = 1, kGen5W = %d, kGen5Heads = %d;\n' % (A.W, A.nh)
        for name, t in (('qkv_w', A.qkv.weight), ('qkv_b', A.qkv.bias), ('o_w', A.o.weight), ('o_b', A.o.bias), ('rel', A.rel),
                        ('f1_w', A.f1.weight), ('f1_b', A.f1.bias), ('f2_w', A.f2.weight), ('f2_b', A.f2.bias)):
            x = t.detach().numpy().astype(np.float32)
            s += 'static const float kG5_att_%s[%d] = {%s};\n' % (name, x.size, ','.join('%.6g' % v for v in x.ravel()))
    else:
        s += 'static constexpr int kGen5Attn = 0, kGen5W = 1, kGen5Heads = 1;\n'
        for name in ('qkv_w', 'qkv_b', 'o_w', 'o_b', 'rel', 'f1_w', 'f1_b', 'f2_w', 'f2_b'):
            s += 'static const float kG5_att_%s[1] = {0};\n' % name
    s += '} // namespace gt\n'
    open(path, 'w').write(s)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--src', nargs=4, action='append', metavar=('NAZWA', 'ZRZUTY', 'PRAWDA', 'WAGA'), required=True)
    ap.add_argument('--val-gs', default='02_Funk'); ap.add_argument('--hidden', type=int, default=24)
    ap.add_argument('--epochs', type=int, default=14); ap.add_argument('--steps', type=int, default=400)
    ap.add_argument('--out', default=os.path.join(os.path.dirname(__file__), '..', 'src', 'gt_gen5model.hpp'))
    ap.add_argument('--seed', type=int, default=1)
    ap.add_argument('--resume', action='store_true', help='wznów z <out>.ckpt (zapisywany po każdej epoce)')
    ap.add_argument('--attn', action='store_true', help='blok uwagi w czasie (ostatnia sekunda, 2 głowy)')
    a = ap.parse_args()
    torch.manual_seed(a.seed); rng = np.random.default_rng(a.seed)
    srcs = []
    for name, ddir, tdir, w in a.src:
        tr, va = [], []
        for p in sorted(glob.glob(os.path.join(ddir, '*.bin'))):
            n = os.path.splitext(os.path.basename(p))[0]
            tp = truth_path(tdir, n)
            if not tp:
                continue
            X = load_dump(p); fr, on = labels(len(X), truth_notes(tp))
            item = (torch.from_numpy(X.copy()), torch.from_numpy(fr), torch.from_numpy(on))
            isval = n.startswith(a.val_gs) if tp.endswith('.jams') else zlib.crc32(n.encode()) % 5 == 0
            (va if isval else tr).append(item)
        srcs.append((name, tr, va, float(w)))
        print('%-12s uczące %d, walidacja %d' % (name, len(tr), len(va)))
    net = Net(a.hidden, a.attn)
    print('parametry:', sum(p.numel() for p in net.parameters()))
    opt = torch.optim.Adam(net.parameters(), lr=2e-3)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, a.epochs * a.steps)
    wts = np.array([w for _, _, _, w in srcs]); wts /= wts.sum()
    Lc, B = 96, 12

    def batch():
        xs, fs, os_ = [], [], []
        for _ in range(B):
            k = rng.choice(len(srcs), p=wts); tr = srcs[k][1]
            X, fr, on = tr[rng.integers(len(tr))]
            T = len(X)
            if T <= Lc:
                pad = Lc - T
                X = F.pad(X, (0, 0, 0, 0, 0, pad)); fr = F.pad(fr, (0, 0, 0, pad)); on = F.pad(on, (0, 0, 0, pad)); t0 = 0
            else:
                t0 = rng.integers(T - Lc)
            xs.append(X[t0:t0 + Lc].permute(1, 0, 2)); fs.append(fr[t0:t0 + Lc]); os_.append(on[t0:t0 + Lc])
        return torch.stack(xs), torch.stack(fs), torch.stack(os_)

    def evaluate():
        net.eval(); res = {}
        with torch.no_grad():
            for name, _, va, _ in srcs:
                tp = fp = fn = 0
                otp = ofp = ofn = 0
                for X, fr, on in va:
                    y = torch.sigmoid(net(X.permute(1, 0, 2)[None]))[0]
                    pf = y[0] >= 0.5; tf = fr >= 0.5
                    tp += int((pf & tf).sum()); fp += int((pf & ~tf).sum()); fn += int((~pf & tf).sum())
                    po = y[1] >= 0.5; to = on >= 0.99
                    otp += int((po & to).sum()); ofp += int((po & (on < 0.3)).sum()); ofn += int((~po & to).sum())
                res[name] = (2 * tp / max(1, 2 * tp + fp + fn), 2 * otp / max(1, 2 * otp + ofp + ofn))
        net.train(); return res

    t_start = time.time()
    ep0 = 0
    ck = a.out + '.ckpt'
    if a.resume and os.path.exists(ck):
        st = torch.load(ck, weights_only=False)
        net.load_state_dict(st['net']); opt.load_state_dict(st['opt']); sched.load_state_dict(st['sched'])
        ep0 = st['epoch'] + 1; rng = st['rng']; torch.set_rng_state(st['trng'])
        print('wznowiono od epoki %d' % ep0, flush=True)
    for ep in range(ep0, a.epochs):
        tot = 0
        for st in range(a.steps):
            x, fr, on = batch()
            y = net(x)
            lf = F.binary_cross_entropy_with_logits(y[:, 0], fr)
            lo = F.binary_cross_entropy_with_logits(y[:, 1], on, pos_weight=torch.tensor(4.0))
            loss = lf + lo
            opt.zero_grad(); loss.backward(); opt.step(); sched.step(); tot += float(loss.detach())
        r = evaluate()
        print('epoka %2d  strata %.4f  ' % (ep, tot / a.steps) + '  '.join('%s: klatki F1 %.3f, początki F1 %.3f' % (k, v[0], v[1]) for k, v in r.items()) +
              '  (%.0f s)' % (time.time() - t_start), flush=True)
        torch.save({'net': net.state_dict(), 'opt': opt.state_dict(), 'sched': sched.state_dict(), 'epoch': ep, 'rng': rng,
                    'trng': torch.get_rng_state()}, ck)
    export(net, a.out, 'walidacja: ' + '; '.join('%s klatki %.3f początki %.3f' % (k, v[0], v[1]) for k, v in r.items()))
    torch.save(net.state_dict(), a.out + '.pt')
    print('zapisano', a.out)


if __name__ == '__main__':
    main()
