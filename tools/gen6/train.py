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
from .data import TrainSet, load_sources, precompute_features, summarize
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


def pick_device(name='auto'):
    if name == 'auto':
        return torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    return torch.device(name)


class Prefetcher:
    """Paczki (losowanie wycinków + augmentacja w numpy) przygotowywane w wątku w tle, żeby GPU nie czekało na CPU."""

    def __init__(self, ds, cfg, rng, n):
        import queue, threading
        self.q, self.stop = queue.Queue(maxsize=max(1, n)), False
        self.rng = np.random.default_rng(rng.integers(1 << 62))  # osobny strumień losowy wątku

        def work():
            while not self.stop:
                x, tg, avail, valid = ds.batch(cfg.train.batch, cfg.train.crop_frames, self.rng)
                self.q.put((augment(x, cfg.train.augment, self.rng), tg, avail, valid))
        self.t = threading.Thread(target=work, daemon=True)
        self.t.start()

    def get(self):
        return self.q.get()

    def close(self):
        self.stop = True
        try:
            while True:
                self.q.get_nowait()
        except Exception:
            pass


def val_subset(va, n, seed=0):
    """Stała próba walidacyjna (te same nagrania w każdej epoce), równo ze wszystkich źródeł."""
    if not n or len(va) <= n:
        return va
    r = np.random.default_rng(seed)
    by = {}
    for e in va:
        by.setdefault(e.source, []).append(e)
    out, per = [], max(1, n // len(by))
    for s in sorted(by):
        g = by[s]
        out += [g[i] for i in sorted(r.choice(len(g), min(per, len(g)), replace=False))]
    return out


def train(cfg: Config, out, resume=False, examples=None, log=print, jobs=None):
    os.makedirs(out, exist_ok=True)
    torch.manual_seed(cfg.train.seed)
    rng = np.random.default_rng(cfg.train.seed)
    dev = pick_device(cfg.train.device)
    if dev.type == 'cuda':
        torch.backends.cudnn.benchmark = True
        torch.backends.cuda.matmul.allow_tf32 = torch.backends.cudnn.allow_tf32 = True
    exs = examples if examples is not None else load_sources(cfg)
    log(summarize(exs))
    if cfg.train.cache_dir and examples is None:
        exs = precompute_features(exs, cfg, jobs, log)
    tr = [e for e in exs if e.split == 'train']
    va = val_subset([e for e in exs if e.split == 'val'], cfg.train.max_val, cfg.train.seed)
    t_load = time.time()
    ds = TrainSet(tr, cfg, rng)
    log('zbiór uczący: %d nagrań, walidacja: %d (%.0f s)' % (len(ds.items), len(va), time.time() - t_load))
    net = Gen6(cfg).to(dev)
    log('parametry: %d, halo inferencji: %d klatek, urządzenie: %s%s' % (
        net.n_params(), net.halo, dev, ' (%s)' % torch.cuda.get_device_name(dev) if dev.type == 'cuda' else ''))
    opt = torch.optim.AdamW(net.parameters(), lr=cfg.train.lr, weight_decay=cfg.train.weight_decay)
    epochs = cfg.train.epochs
    total = epochs * cfg.train.steps_per_epoch
    ep0, step, best, since = 0, 0, -1e9, 0
    last = os.path.join(out, 'last.pt')
    if resume and os.path.exists(last):
        st = torch.load(last, weights_only=False, map_location=dev)
        net.load_state_dict(st['net']); opt.load_state_dict(st['opt'])
        ep0, step, best, since = st['epoch'] + 1, st['step'], st['best'], st['since']
        epochs = st.get('epochs', epochs); total = epochs * cfg.train.steps_per_epoch
        rng = st['rng']; ds.rng = rng; torch.set_rng_state(st['trng'])
        log('wznowiono od epoki %d' % ep0)
    cfg.save(os.path.join(out, 'config.json'))
    pf = Prefetcher(ds, cfg, rng, cfg.train.prefetch) if cfg.train.prefetch else None
    use_amp = bool(cfg.train.amp and dev.type == 'cuda')
    scaler = torch.amp.GradScaler('cuda', enabled=use_amp)
    t_start = time.time()
    ep = ep0
    while ep < epochs:
        net.train()
        acc = {}
        for _ in range(cfg.train.steps_per_epoch):
            for g in opt.param_groups:
                g['lr'] = lr_at(step, total, cfg.train)
            if pf:
                x, tg, avail, valid = pf.get()
            else:
                x, tg, avail, valid = ds.batch(cfg.train.batch, cfg.train.crop_frames)
                x = augment(x, cfg.train.augment, rng)
            xt = torch.from_numpy(x).permute(0, 2, 1, 3).to(dev, non_blocking=True)  # B C T P
            tgt = {k: torch.from_numpy(v).to(dev, non_blocking=True) for k, v in tg.items()}
            try:
                with torch.autocast(dev.type, dtype=torch.float16, enabled=use_amp):
                    y = net(xt)
                y = {k: v.float() for k, v in y.items()}
                loss, parts = total_loss(y, tgt, torch.from_numpy(avail).to(dev), torch.from_numpy(valid).to(dev), cfg.loss,
                                         as_float=False)  # bez synchronizacji GPU w każdym kroku
                opt.zero_grad(set_to_none=True)
                scaler.scale(loss).backward()
            except torch.cuda.OutOfMemoryError:
                if step > ep0 * cfg.train.steps_per_epoch + 5 or cfg.train.batch <= 1:
                    raise
                del xt, tgt  # brak pamięci na początku: mniejsza paczka
                y = loss = None
                opt.zero_grad(set_to_none=True); torch.cuda.empty_cache()
                cfg.train.batch //= 2
                log('brak pamięci GPU, paczka -> %d' % cfg.train.batch)
                if pf:
                    pf.close(); pf = Prefetcher(ds, cfg, rng, cfg.train.prefetch)
                continue
            if cfg.train.grad_clip:
                scaler.unscale_(opt)
                torch.nn.utils.clip_grad_norm_(net.parameters(), cfg.train.grad_clip)
            scaler.step(opt)
            scaler.update()
            step += 1
            for k, v in parts.items():
                acc[k] = acc.get(k, 0) + v / cfg.train.steps_per_epoch
        acc = {k: float(v) for k, v in acc.items()}
        rec = {'epoch': ep, 'step': step, 'lr': opt.param_groups[0]['lr'], 'loss': acc, 'sec': round(time.time() - t_start, 1)}
        if va:
            with torch.no_grad():
                rows, groups, _ = evaluate_model(net, va, cfg)
            agg = M.aggregate(rows, [g.split(':')[0] for g in groups], micro=False)
            rec['val'] = agg
            score = agg['RAZEM'].get(cfg.train.select_metric, float('nan'))
        else:
            score = -sum(acc.values())
        rec['score'] = score
        if ep == ep0 and cfg.train.time_budget_sec > 0:  # przycięcie liczby epok do budżetu czasu (harmonogram lr też)
            per = time.time() - t_start
            fit = ep0 + max(1, int(cfg.train.time_budget_sec // max(per, 1e-3)))
            if fit < epochs:
                log('budżet %.0f s, epoka %.0f s -> %d epok zamiast %d' % (cfg.train.time_budget_sec, per, fit, epochs))
                epochs = fit; total = epochs * cfg.train.steps_per_epoch
        rec['epochs'] = epochs
        improved = not math.isnan(score) and score > best
        if improved:
            best, since = score, 0
            torch.save({'net': net.state_dict(), 'config': cfg.to_dict(), 'epoch': ep, 'score': score}, os.path.join(out, 'best.pt'))
        else:
            since += 1
        torch.save({'net': net.state_dict(), 'opt': opt.state_dict(), 'epoch': ep, 'step': step, 'best': best, 'since': since,
                    'epochs': epochs, 'rng': rng, 'trng': torch.get_rng_state(), 'config': cfg.to_dict()}, last)
        with open(os.path.join(out, 'log.jsonl'), 'a') as f:
            f.write(json.dumps(rec, ensure_ascii=False, default=float) + '\n')
        val_s = ''
        if va:
            r = agg['RAZEM']
            val_s = '  [nuty F1 %.3f, początek+koniec %.3f, klatki %.3f]' % (r.get('note_F1', float('nan')), r.get('onoff_F1', float('nan')),
                                                                           r.get('frame_F1', float('nan')))
        log('epoka %2d/%d  strata %s  %s=%.4f%s%s  (%.0f s)' % (ep, epochs, ' '.join('%s %.4f' % kv for kv in acc.items()),
                                                              cfg.train.select_metric, score, ' *' if improved else '', val_s,
                                                              time.time() - t_start))
        ep += 1
        if since >= cfg.train.early_stop:
            log('brak poprawy od %d epok, koniec' % since)
            break
    if pf:
        pf.close()
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
    ap.add_argument('--jobs', type=int, help='procesy liczące cechy (domyślnie train.workers albo liczba rdzeni)')
    ap.add_argument('--device', help='nadpisuje train.device (auto / cuda / cpu)')
    a = ap.parse_args(argv)
    if a.smoke:
        from .synth import random_set
        cfg = smoke_config()
        train(cfg, a.out, a.resume, random_set(6, dur=4.0))
    else:
        if not a.config:
            ap.error('--config wymagane (albo --smoke)')
        cfg = Config.load(a.config)
        if a.device:
            cfg.train.device = a.device
        train(cfg, a.out, a.resume, jobs=a.jobs)


if __name__ == '__main__':
    main()
