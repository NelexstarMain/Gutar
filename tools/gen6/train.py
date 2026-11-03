"""train.py - pętla uczenia gen 6 (szkielet gotowy do uruchomienia, gdy będą nowe dane).

  python3 -m tools.gen6.train --config cfg.json --out run/          # uczenie
  python3 -m tools.gen6.train --config cfg.json --out run/ --resume # wznowienie od run/last.pt
  python3 -m tools.gen6.train --smoke --out /tmp/run                # próba na danych syntetycznych (sprawdza, że wszystko działa)

Po każdej epoce: pełna walidacja (dekoder + metrics.evaluate_file), zapis run/last.pt; najlepsza epoka według
cfg.train.select_metric -> run/best.pt; wcześniejsze zatrzymanie po cfg.train.early_stop epokach bez poprawy; dziennik run/log.jsonl.
"""
from __future__ import annotations
import argparse
import json
import math
import os
import time
import numpy as np
import torch
from . import metrics as M
from .config import Config
from .data import TrainSet, load_sources, summarize
from .evaluate import evaluate_model
from .losses import total_loss
from .model import Gen6


def augment(x, aug, rng):
    """x: [B, T, C, P] numpy. Wzmocnienie (przesunięcie skali dB), szum, maskowanie pasm i chwil (SpecAugment)."""
    x = x.copy()
    if aug.get('gain_db'):
        g = rng.uniform(-aug['gain_db'], aug['gain_db'], (len(x), 1, 1, 1)) / 60.0
        x = np.where(x > 0, np.clip(x + g, 0, 1.3), 0).astype(np.float32)
    if aug.get('noise'):
        x = np.clip(x + aug['noise'] * rng.standard_normal(x.shape).astype(np.float32), 0, 1.3)
    if aug.get('spec_mask'):
        B, T, C, P = x.shape
        for b in range(B):
            if rng.uniform() < aug['spec_mask']:
                w = int(rng.integers(1, max(2, T // 10))); t0 = int(rng.integers(0, T - w + 1)); x[b, t0:t0 + w] = 0
            if rng.uniform() < aug['spec_mask']:
                w = int(rng.integers(1, max(2, P // 12))); p0 = int(rng.integers(0, P - w + 1)); x[b, :, :, p0:p0 + w] = 0
    return x


def lr_at(step, total, cfg):
    if step < cfg.warmup_steps:
        return cfg.lr * (step + 1) / cfg.warmup_steps
    q = (step - cfg.warmup_steps) / max(1, total - cfg.warmup_steps)
    return cfg.lr * 0.5 * (1 + math.cos(math.pi * min(1.0, q)))


def train(cfg: Config, out, resume=False, examples=None, log=print):
    os.makedirs(out, exist_ok=True)
    torch.manual_seed(cfg.train.seed)
    rng = np.random.default_rng(cfg.train.seed)
    exs = examples if examples is not None else load_sources(cfg)
    log(summarize(exs))
    tr = [e for e in exs if e.split == 'train']
    va = [e for e in exs if e.split == 'val']
    ds = TrainSet(tr, cfg, rng)
    net = Gen6(cfg)
    log('parametry: %d, halo inferencji: %d klatek' % (net.n_params(), net.halo))
    opt = torch.optim.AdamW(net.parameters(), lr=cfg.train.lr, weight_decay=cfg.train.weight_decay)
    total = cfg.train.epochs * cfg.train.steps_per_epoch
    ep0, step, best, since = 0, 0, -1e9, 0
    last = os.path.join(out, 'last.pt')
    if resume and os.path.exists(last):
        st = torch.load(last, weights_only=False)
        net.load_state_dict(st['net']); opt.load_state_dict(st['opt'])
        ep0, step, best, since = st['epoch'] + 1, st['step'], st['best'], st['since']
        rng = st['rng']; ds.rng = rng; torch.set_rng_state(st['trng'])
        log('wznowiono od epoki %d' % ep0)
    cfg.save(os.path.join(out, 'config.json'))
    t_start = time.time()
    for ep in range(ep0, cfg.train.epochs):
        net.train()
        acc = {}
        for _ in range(cfg.train.steps_per_epoch):
            for g in opt.param_groups:
                g['lr'] = lr_at(step, total, cfg.train)
            x, tg, avail, valid = ds.batch(cfg.train.batch, cfg.train.crop_frames)
            x = augment(x, cfg.train.augment, rng)
            xt = torch.from_numpy(x).permute(0, 2, 1, 3)  # B C T P
            tgt = {k: torch.from_numpy(v) for k, v in tg.items()}
            y = net(xt)
            loss, parts = total_loss(y, tgt, torch.from_numpy(avail), torch.from_numpy(valid), cfg.loss)
            opt.zero_grad()
            loss.backward()
            if cfg.train.grad_clip:
                torch.nn.utils.clip_grad_norm_(net.parameters(), cfg.train.grad_clip)
            opt.step()
            step += 1
            for k, v in parts.items():
                acc[k] = acc.get(k, 0) + v / cfg.train.steps_per_epoch
        rec = {'epoch': ep, 'step': step, 'loss': acc, 'sec': round(time.time() - t_start, 1)}
        if va:
            rows, groups, _ = evaluate_model(net, va, cfg)
            agg = M.aggregate(rows, [g.split(':')[0] for g in groups], micro=False)
            rec['val'] = agg
            score = agg['RAZEM'].get(cfg.train.select_metric, float('nan'))
        else:
            score = -sum(acc.values())
        rec['score'] = score
        improved = not math.isnan(score) and score > best
        if improved:
            best, since = score, 0
            torch.save({'net': net.state_dict(), 'config': cfg.to_dict(), 'epoch': ep, 'score': score}, os.path.join(out, 'best.pt'))
        else:
            since += 1
        torch.save({'net': net.state_dict(), 'opt': opt.state_dict(), 'epoch': ep, 'step': step, 'best': best, 'since': since,
                    'rng': rng, 'trng': torch.get_rng_state(), 'config': cfg.to_dict()}, last)
        with open(os.path.join(out, 'log.jsonl'), 'a') as f:
            f.write(json.dumps(rec, ensure_ascii=False, default=float) + '\n')
        log('epoka %2d  strata %s  %s=%.2f%s  (%.0f s)' % (ep, ' '.join('%s %.4f' % kv for kv in acc.items()), cfg.train.select_metric,
                                                          score, ' *' if improved else '', time.time() - t_start))
        if since >= cfg.train.early_stop:
            log('brak poprawy od %d epok, koniec' % since)
            break
    return net, best


def smoke_config():
    cfg = Config()
    cfg.model.hidden, cfg.model.d_model, cfg.model.n_harm_blocks, cfg.model.n_ctx_layers, cfg.model.time_window = 8, 16, 2, 1, 8
    cfg.train.epochs, cfg.train.steps_per_epoch, cfg.train.batch, cfg.train.crop_frames, cfg.train.warmup_steps = 2, 5, 2, 64, 2
    return cfg


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--config'); ap.add_argument('--out', required=True)
    ap.add_argument('--resume', action='store_true'); ap.add_argument('--smoke', action='store_true')
    a = ap.parse_args(argv)
    if a.smoke:
        from .synth import random_set
        cfg = smoke_config()
        train(cfg, a.out, a.resume, random_set(6, dur=4.0))
    else:
        if not a.config:
            ap.error('--config wymagane (albo --smoke)')
        train(Config.load(a.config), a.out, a.resume)


if __name__ == '__main__':
    main()
