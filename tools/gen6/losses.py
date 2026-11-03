"""losses.py - strata wielozadaniowa z maskami: avail [B,5] (czy źródło ma daną etykietę), valid [B,T] (dopełnienie wycinka)."""
from __future__ import annotations
import torch
import torch.nn.functional as F
from .config import LossConfig
from .labels import HEADS


def _bce(logit, target, mask, pos_weight=1.0, gamma=0.0, smooth=0.0):
    if smooth:
        target = target * (1 - smooth) + 0.5 * smooth
    pw = torch.tensor(pos_weight, device=logit.device)
    l = F.binary_cross_entropy_with_logits(logit, target, pos_weight=pw, reduction='none')
    if gamma > 0:
        p = torch.sigmoid(logit)
        pt = target * p + (1 - target) * (1 - p)
        l = l * (1 - pt).clamp(min=0) ** gamma
    return (l * mask).sum() / mask.sum().clamp(min=1)


def total_loss(out, tg, avail, valid, lc: LossConfig):
    """out: logity z Gen6.forward; tg: mapy celów (torch) [B,T,...]; zwraca (strata, słownik składowych)."""
    parts = {}
    a = {h: avail[:, i] for i, h in enumerate(HEADS)}
    vm = valid[:, :, None]  # B T 1
    def m(head):
        return vm * a[head][:, None, None]
    parts['onset'] = _bce(out['onset'], tg['onset'], m('onset').expand_as(tg['onset']), lc.onset_pos_weight, lc.focal_gamma, lc.label_smoothing)
    parts['frame'] = _bce(out['frame'], tg['frame'], m('frame').expand_as(tg['frame']), 1.0, lc.focal_gamma, lc.label_smoothing)
    if 'offset' in out:
        parts['offset'] = _bce(out['offset'], tg['offset'], m('offset').expand_as(tg['offset']), lc.offset_pos_weight, lc.focal_gamma)
    if 'velocity' in out:
        mk = tg['vel_mask'] * m('velocity')
        parts['velocity'] = ((torch.sigmoid(out['velocity']) - tg['velocity']) ** 2 * mk).sum() / mk.sum().clamp(min=1)
    if 'tab' in out:
        t = tg['tab'].clone()
        t[(valid < 0.5)[:, :, None].expand_as(t)] = -1
        t[(a['tab'] < 0.5)[:, None, None].expand_as(t)] = -1
        lg = out['tab'].reshape(-1, out['tab'].shape[-1])
        parts['tab'] = F.cross_entropy(lg, t.reshape(-1), ignore_index=-1) if (t >= 0).any() else lg.sum() * 0
    w = {'onset': lc.w_onset, 'frame': lc.w_frame, 'offset': lc.w_offset, 'velocity': lc.w_velocity, 'tab': lc.w_tab}
    loss = sum(w[k] * v for k, v in parts.items())
    return loss, {k: float(v.detach()) for k, v in parts.items()}
