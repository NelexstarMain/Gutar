"""Testy reszty architektury: dźwięk, cechy (także zgodność z silnikiem C++), adaptery formatów, etykiety -> dekoder, sieć."""
import json
import os
import shutil
import struct
import subprocess
import numpy as np
import pytest
import torch
from tools.gen6 import metrics as M
from tools.gen6.audio import engine_frontend, read_wav, resample, write_wav
from tools.gen6.config import Config, FeatureConfig, SourceConfig
from tools.gen6.data import SOURCE_ADAPTERS, Example, Note, parse_annotation
from tools.gen6.decode import decode_notes
from tools.gen6.features import hcqt, load_engine_dump
from tools.gen6.labels import make_targets
from tools.gen6.model import Gen6
from tools.gen6.synth import random_example

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))


def small_cfg(**kw):
    c = Config()
    c.model.hidden, c.model.d_model, c.model.n_harm_blocks, c.model.n_ctx_layers, c.model.time_window = 8, 16, 2, 2, 6
    c.model.dropout = 0.0
    for k, v in kw.items():
        setattr(c.model, k, v)
    return c


def test_wav_and_resample(tmp_path):
    sr = 22050
    t = np.arange(sr) / sr
    x = 0.5 * np.sin(2 * np.pi * 441 * t).astype(np.float32)
    write_wav(tmp_path / 'a.wav', x, sr)
    y, s = read_wav(str(tmp_path / 'a.wav'))
    assert s == sr and np.abs(y - x).max() < 1e-4
    z = resample(np.tile(x, 8), sr, 11025)
    assert abs(len(z) - 8 * 11025) <= 1
    f = np.argmax(np.abs(np.fft.rfft(z[1000:1000 + 11025]))) * 11025 / 11025
    assert abs(f - 441) <= 1


def test_hcqt_pitch():
    cfg = FeatureConfig()
    sr = cfg.sr
    t = np.arange(2 * sr) / sr
    x = 0.3 * np.sin(2 * np.pi * 110.0 * t)  # A2 = MIDI 45
    X = hcqt(x, cfg)
    assert X.shape[1:] == (cfg.n_channels, cfg.n_bins)
    p = int(np.argmax(X[len(X) // 2, 1]))   # kanał 1x
    assert p == 3 * (45 - cfg.midi_lo) + 1


@pytest.mark.skipif(shutil.which('g++') is None, reason='brak g++')
def test_hcqt_matches_engine(tmp_path):
    """Przy kroku 512 cechy z numpy mają być takie jak zrzut HCQT z silnika C++ (gen 5)."""
    cli = tmp_path / 'gt_cli'
    subprocess.run(['g++', '-std=c++17', '-O2', os.path.join(ROOT, 'src', 'cli.cpp'), '-o', str(cli)], check=True)
    ex = random_example(1, sr=11025, dur=4.0)
    write_wav(tmp_path / 'x.wav', ex.meta['signal'], 11025)
    env = dict(os.environ, GT_DUMPH=str(tmp_path / 'x.bin'))
    subprocess.run([str(cli), 'analyze', str(tmp_path / 'x.wav'), str(tmp_path / 'x.json')], check=True, env=env, capture_output=True)
    A = load_engine_dump(str(tmp_path / 'x.bin'))
    x, sr = read_wav(str(tmp_path / 'x.wav'))
    x, _ = engine_frontend(x, sr)
    B = hcqt(x, FeatureConfig(hop=512))
    assert A.shape == B.shape
    d = np.abs(A - B)
    assert d.mean() < 1e-4 and d.max() < 2e-3, (d.mean(), d.max())


def test_annotation_formats(tmp_path):
    (tmp_path / 'a.csv').write_text('onset,offset,pitch,velocity,string\n0.5,1.0,60,100,2\n1.0,1.5,64,90,3\n')
    n, _, has, _ = parse_annotation(str(tmp_path / 'a.csv'), 'notes_csv')
    assert len(n) == 2 and n[0].pitch == 60 and abs(n[0].velocity - 100 / 127) < 1e-9 and 'tab' in has and 'velocity' in has
    (tmp_path / 'b.tsv').write_text('0.5\t1.0\t440\n')
    n, _, has, _ = parse_annotation(str(tmp_path / 'b.tsv'), 'notes_csv', pitch_unit='hz')
    assert abs(n[0].pitch - 69) < 1e-9 and 'velocity' not in has
    # MIDI: format 0, 480 tików na ćwierćnutę, tempo 120 -> 1 tik = 1/960 s
    def vlq(v):
        b = [v & 127]; v >>= 7
        while v:
            b.insert(0, (v & 127) | 128); v >>= 7
        return bytes(b)
    trk = vlq(0) + b'\x90\x3c\x64' + vlq(480) + b'\x80\x3c\x00' + vlq(0) + b'\x91\x40\x50' + vlq(960) + b'\x91\x40\x00' + vlq(0) + b'\xff\x2f\x00'
    (tmp_path / 'c.mid').write_bytes(b'MThd' + struct.pack('>IHHH', 6, 0, 1, 480) + b'MTrk' + struct.pack('>I', len(trk)) + trk)
    n, _, has, _ = parse_annotation(str(tmp_path / 'c.mid'), 'midi', string_from_channel=True)
    assert [(x.pitch, round(x.onset, 3), round(x.offset, 3), x.string) for x in n] == [(60, 0, 0.5, 0), (64, 0.5, 1.5, 1)]
    # JAMS (GuitarSet): 6 strun
    ann = [{'namespace': 'note_midi', 'annotation_metadata': {'data_source': str(s)},
            'data': [{'time': 0.1 * s, 'duration': 0.5, 'value': 40 + 5 * s}] if s < 2 else []} for s in range(6)]
    ann.append({'namespace': 'chord', 'data': [{'time': 0, 'duration': 2, 'value': 'E:min'}]})
    (tmp_path / 'd.jams').write_text(json.dumps({'annotations': ann, 'file_metadata': {'duration': 2.0}}))
    n, ch, has, _ = parse_annotation(str(tmp_path / 'd.jams'), 'jams')
    assert len(n) == 2 and n[1].string == 1 and ch == [(0, 2, 'E:min')] and {'tab', 'chords'} <= has
    # manifest
    (tmp_path / 'm.jsonl').write_text(json.dumps({'id': 'x', 'audio': 'x.wav', 'annotation': 'a.csv', 'format': 'notes_csv',
                                                  'split': 'test', 'has': ['onset', 'frame']}) + '\n')
    exs = list(SOURCE_ADAPTERS['manifest'](SourceConfig('m', 'manifest', manifest=str(tmp_path / 'm.jsonl'), val_rule='manifest')))
    assert exs[0].split == 'test' and exs[0].has == frozenset({'onset', 'frame'}) and exs[0].audio.endswith('x.wav')


def test_config_roundtrip(tmp_path):
    c = Config(); c.sources.append(SourceConfig('gs', 'guitarset', root='/x', val_rule='prefix:02_'))
    c.save(tmp_path / 'c.json')
    d = Config.load(tmp_path / 'c.json')
    assert d.to_dict() == c.to_dict() and isinstance(d.model.harm_offsets, tuple)
    with pytest.raises(ValueError):
        Config.from_dict({'model': {'nie_ma': 1}})


def test_labels_decode_roundtrip():
    """Idealne mapy (cele) przez dekoder mają dać prawie te same nuty: dekoder i etykiety są ze sobą zgodne."""
    cfg = Config()
    ex = random_example(3, dur=8.0)
    X = hcqt(ex.meta['signal'], cfg.features)
    maps, avail = make_targets(ex, len(X), cfg.features, cfg.labels)
    assert avail.tolist() == [1, 1, 1, 1, 1]
    tab = np.zeros(maps['tab'].shape + (1 + cfg.labels.n_frets,), np.float32)
    np.put_along_axis(tab, maps['tab'][..., None], 1, -1)
    p = {'onset': maps['onset'], 'frame': maps['frame'], 'offset': maps['offset'], 'velocity': maps['velocity'], 'tab': tab}
    est = decode_notes(p, cfg.features, cfg.decode, cfg.labels)
    r = M.evaluate_file(ex.notes, est, ex.duration, has=ex.has, label_cfg=cfg.labels)
    assert r['note_on']['F1'] > 0.97, r['note_on']
    assert r['note_onoff']['F1'] > 0.9, r['note_onoff']
    assert r['frame']['F1'] > 0.93
    assert r['tab']['string_acc'] > 0.95
    assert r['note_vel']['F1'] > 0.9


def test_model_shapes_and_chunking():
    cfg = small_cfg()
    net = Gen6(cfg).eval()
    X = np.random.default_rng(0).uniform(0, 1, (150, cfg.features.n_channels, cfg.features.n_bins)).astype(np.float32)
    y = net(torch.from_numpy(X.transpose(1, 0, 2))[None])
    S = cfg.features.n_semis
    assert y['onset'].shape == (1, 150, S) and y['frame'].shape == (1, 150, S) and y['offset'].shape == (1, 150, S)
    assert y['tab'].shape == (1, 150, 6, 1 + cfg.labels.n_frets) and torch.isfinite(y['tab'][..., 0]).all()
    a = net.predict(X, chunk=10000)
    b = net.predict(X, chunk=37)
    for k in a:
        assert np.abs(a[k] - b[k]).max() < 1e-4, k


def test_causal_does_not_see_future():
    cfg = small_cfg(causal=True)
    net = Gen6(cfg).eval()
    X = torch.rand(1, cfg.features.n_channels, 80, cfg.features.n_bins)
    X2 = X.clone(); X2[:, :, 60:] = torch.rand_like(X2[:, :, 60:])
    y1, y2 = net(X), net(X2)
    # warstwy konwolucji mają kontekst +-halo_conv klatek w obie strony; uwaga nie może dodać więcej
    conv = 1 + sum(d for d in cfg.model.time_dilations[:cfg.model.n_harm_blocks])
    assert torch.allclose(y1['frame'][:, :60 - conv], y2['frame'][:, :60 - conv], atol=1e-5)


def test_train_step_and_loss_masks():
    from tools.gen6.data import TrainSet
    from tools.gen6.losses import total_loss
    cfg = small_cfg()
    exs = [random_example(i, dur=3.0) for i in range(3)]
    exs[1].has = frozenset({'onset', 'frame'})  # źródło bez końców, głośności i strun
    ds = TrainSet(exs, cfg)
    x, tg, avail, valid = ds.batch(4, 300)  # dłużej niż nagranie: dopełnienie
    assert x.shape[1] == 300 and valid.min() == 0
    net = Gen6(cfg)
    y = net(torch.from_numpy(x).permute(0, 2, 1, 3))
    loss, parts = total_loss(y, {k: torch.from_numpy(v) for k, v in tg.items()}, torch.from_numpy(avail), torch.from_numpy(valid), cfg.loss)
    loss.backward()
    assert torch.isfinite(loss) and set(parts) == {'onset', 'frame', 'offset', 'velocity', 'tab'}
    assert all(p.grad is None or torch.isfinite(p.grad).all() for p in net.parameters())
