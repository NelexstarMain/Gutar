"""data.py - wspólny zapis danych i adaptery formatów.

Dane będą się zmieniać, więc reszta pakietu zna tylko `Example`:
  notes   lista Note(pitch, onset, offset, velocity?, string?, audible_end?)
  chords  lista (t0, t1, etykieta) albo pusta
  has     które etykiety źródło naprawdę ma: {'onset','frame','offset','velocity','tab','chords'}
          (np. MIDI z syntezatora ma głośność, CSV z ręcznej adnotacji często nie ma końców nut) - strata i metryki pomijają resztę.

Nowy format = jedna funkcja parsująca adnotację, zarejestrowana dekoratorem @annotation_parser('nazwa'),
albo cały adapter źródła (@source_adapter('nazwa')), gdy pliki są ułożone nietypowo. Najprościej: manifest JSONL
(adapter 'manifest'), jedna linia na nagranie:
  {"id": "...", "audio": "ścieżka.wav", "annotation": "ścieżka", "format": "jams|truth_json|notes_csv|midi|...",
   "split": "train|val|test", "group": "dowolna etykieta grupy do raportów", "features": "opcjonalnie gotowe cechy .npy"}
"""
from __future__ import annotations
import csv
import dataclasses as dc
import glob
import json
import os
import struct
import zlib
from typing import Callable, Dict, Iterable, List, Optional, Tuple
import numpy as np
from .config import Config, FeatureConfig, LabelConfig, SourceConfig


@dc.dataclass
class Note:
    pitch: float                 # MIDI (może być ułamkowe)
    onset: float                 # [s]
    offset: float                # [s] zwolnienie struny
    velocity: Optional[float] = None   # 0..1
    string: Optional[int] = None       # 0 = najniższa struna
    audible_end: Optional[float] = None  # koniec słyszalności (korpus/środowiska: 'ta')

    def end(self, use_audible=True):
        if use_audible and self.audible_end is not None:
            return min(self.offset, self.audible_end)
        return self.offset


@dc.dataclass
class Example:
    id: str
    source: str
    notes: List[Note]
    chords: List[Tuple[float, float, str]] = dc.field(default_factory=list)
    has: frozenset = frozenset({'onset', 'frame', 'offset'})
    audio: Optional[str] = None
    features: Optional[str] = None      # gotowe cechy (.npy [T,C,P] albo zrzut silnika .bin)
    features_hop: Optional[int] = None  # krok gotowych cech, jeśli inny niż w konfiguracji
    duration: Optional[float] = None
    group: str = ''
    split: str = 'train'
    weight: float = 1.0
    meta: dict = dc.field(default_factory=dict)


ANNOTATION_PARSERS: Dict[str, Callable] = {}
SOURCE_ADAPTERS: Dict[str, Callable] = {}


def annotation_parser(name):
    def deco(fn):
        ANNOTATION_PARSERS[name] = fn
        return fn
    return deco


def source_adapter(name):
    def deco(fn):
        SOURCE_ADAPTERS[name] = fn
        return fn
    return deco


def parse_annotation(path, fmt, **opt):
    """-> (notes, chords, has, meta)."""
    if fmt not in ANNOTATION_PARSERS:
        raise KeyError('nieznany format adnotacji %r (znane: %s)' % (fmt, ', '.join(sorted(ANNOTATION_PARSERS))))
    return ANNOTATION_PARSERS[fmt](path, **opt)


# ------------------------------------------------------------------ parsery adnotacji

@annotation_parser('truth_json')
def parse_truth_json(path, **_):
    """Korpus (tools/gen_corpus.cpp) i środowiska (tools/gen_env.cpp): notes[midi,t0,t1,ta?,f], chords[name,t0,t1], kind, dur."""
    t = json.load(open(path))
    notes = [Note(float(n['midi']), n['t0'], n['t1'], n.get('vel'), n.get('string'), n.get('ta')) for n in t['notes']]
    chords = [(c['t0'], c['t1'], c['name']) for c in t.get('chords', [])]
    has = {'onset', 'frame', 'offset'}
    if chords:
        has.add('chords')
    if notes and all(n.velocity is not None for n in notes):
        has.add('velocity')
    if notes and all(n.string is not None for n in notes):
        has.add('tab')
    return notes, chords, frozenset(has), {'kind': t.get('kind'), 'duration': t.get('dur')}


@annotation_parser('jams')
def parse_jams(path, **_):
    """GuitarSet: 6 adnotacji note_midi (po jednej na strunę, data_source = numer struny), akordy 'performed' (ostatnie)."""
    j = json.load(open(path))
    notes, chords_all = [], []
    k = 0
    for a in j['annotations']:
        if a['namespace'] == 'note_midi':
            ds = a.get('annotation_metadata', {}).get('data_source')
            try:
                s = int(ds)
            except (TypeError, ValueError):
                s = k
            for d in a['data']:
                notes.append(Note(float(d['value']), d['time'], d['time'] + d['duration'], None, s))
            k += 1
        elif a['namespace'] == 'chord':
            chords_all.append([(d['time'], d['time'] + d['duration'], d['value']) for d in a['data']])
    has = {'onset', 'frame', 'offset'}
    if k == 6:
        has.add('tab')
    chords = chords_all[-1] if chords_all else []
    if chords:
        has.add('chords')
    dur = j.get('file_metadata', {}).get('duration')
    return notes, chords, frozenset(has), {'duration': dur}


@annotation_parser('notes_csv')
def parse_notes_csv(path, onset='onset', offset='offset', pitch='pitch', velocity='velocity', string='string',
                    pitch_unit='midi', velocity_max=None, delimiter=None, **_):
    """Ogólny CSV/TSV. Nazwy kolumn konfigurowalne; bez nagłówka: onset, offset, pitch[, velocity[, string]].
    pitch_unit: 'midi' albo 'hz'; velocity_max: skala głośności (np. 127), domyślnie wykrywana."""
    txt = open(path, newline='').read()
    if delimiter is None:
        delimiter = '\t' if '\t' in txt.split('\n', 1)[0] else ','
    rows = list(csv.reader(txt.splitlines(), delimiter=delimiter))
    rows = [r for r in rows if r and not r[0].startswith('#')]
    if not rows:
        return [], [], frozenset({'onset', 'frame', 'offset'}), {}
    try:
        float(rows[0][0]); header = None
    except ValueError:
        header = [h.strip().lower() for h in rows[0]]; rows = rows[1:]
    def col(name, i):
        if header is None:
            return i
        return header.index(name) if name in header else None
    ci = [col(onset, 0), col(offset, 1), col(pitch, 2), col(velocity, 3), col(string, 4)]
    notes = []
    for r in rows:
        g = lambda c: float(r[c]) if c is not None and c < len(r) and r[c].strip() != '' else None
        p = g(ci[2])
        if pitch_unit == 'hz':
            p = 69 + 12 * np.log2(p / 440.0)
        notes.append(Note(float(p), g(ci[0]), g(ci[1]) if g(ci[1]) is not None else g(ci[0]), g(ci[3]),
                          int(g(ci[4])) if g(ci[4]) is not None else None))
    has = {'onset', 'frame'}
    if ci[1] is not None and all(n.offset > n.onset for n in notes):
        has.add('offset')
    if notes and all(n.velocity is not None for n in notes):
        vm = velocity_max or (127.0 if max(n.velocity for n in notes) > 1 else 1.0)
        for n in notes:
            n.velocity = n.velocity / vm
        has.add('velocity')
    if notes and all(n.string is not None for n in notes):
        has.add('tab')
    return notes, [], frozenset(has), {}


@annotation_parser('midi')
def parse_midi(path, string_from_channel=False, **_):
    """Standardowy plik MIDI (format 0/1), z mapą tempa. string_from_channel: kanał 0..5 = struna (częsta konwencja nagrań z
    przetwornikiem heksafonicznym)."""
    data = open(path, 'rb').read()
    if data[:4] != b'MThd':
        raise ValueError('%s: to nie jest MIDI' % path)
    _, ntr, div = struct.unpack('>HHH', data[8:14])
    pos = 8 + struct.unpack('>I', data[4:8])[0]
    events, tempos = [], [(0, 500000)]
    for _ in range(ntr):
        assert data[pos:pos + 4] == b'MTrk'
        ln = struct.unpack('>I', data[pos + 4:pos + 8])[0]
        p, end, tick, status = pos + 8, pos + 8 + ln, 0, 0
        while p < end:
            v = 0
            while True:
                b = data[p]; p += 1; v = (v << 7) | (b & 127)
                if b < 128:
                    break
            tick += v
            b = data[p]
            if b == 0xFF:
                typ, p = data[p + 1], p + 2
                ln2 = 0
                while True:
                    c = data[p]; p += 1; ln2 = (ln2 << 7) | (c & 127)
                    if c < 128:
                        break
                if typ == 0x51:
                    tempos.append((tick, int.from_bytes(data[p:p + 3], 'big')))
                p += ln2
                continue
            if b in (0xF0, 0xF7):
                p += 1; ln2 = 0
                while True:
                    c = data[p]; p += 1; ln2 = (ln2 << 7) | (c & 127)
                    if c < 128:
                        break
                p += ln2
                continue
            if b >= 128:
                status = b; p += 1
            hi = status & 0xF0
            nd = 1 if hi in (0xC0, 0xD0) else 2
            d = data[p:p + nd]; p += nd
            if hi in (0x80, 0x90):
                on = hi == 0x90 and d[1] > 0
                events.append((tick, on, status & 15, d[0], d[1]))
        pos = end
    tempos.sort()
    if div & 0x8000:
        raise ValueError('%s: czas SMPTE nieobsługiwany' % path)

    def sec(tk):
        s, last_t, last_us = 0.0, 0, 500000
        for t, us in tempos:
            if t >= tk:
                break
            s += (t - last_t) * last_us / div / 1e6; last_t, last_us = t, us
        return s + (tk - last_t) * last_us / div / 1e6
    events.sort(key=lambda e: (e[0], e[1]))
    open_, notes = {}, []
    for tk, on, ch, key, vel in events:
        k = (ch, key)
        if on:
            open_.setdefault(k, []).append((tk, vel))
        elif open_.get(k):
            t0, v = open_[k].pop(0)
            notes.append(Note(float(key), sec(t0), sec(tk), v / 127.0, ch if string_from_channel and ch < 6 else None))
    has = {'onset', 'frame', 'offset', 'velocity'}
    if string_from_channel and notes and all(n.string is not None for n in notes):
        has.add('tab')
    notes.sort(key=lambda n: (n.onset, n.pitch))
    return notes, [], frozenset(has), {}


@annotation_parser('engine_json')
def parse_engine_json(path, **_):
    """Wynik silnika C++ (gt_cli analyze ... wynik.json): używany jako *przewidywanie* w ewaluacji, nie jako prawda."""
    r = json.load(open(path))
    notes = [Note(float(e['midi']), e['t0'], e['t1'], e.get('vel', 0) / 127.0 if 'vel' in e else None, e.get('string')) for e in r['notes']]
    win = r.get('winSec', 0.3715)
    chords, cur = [], None
    for f in r.get('frames', []):
        t, lab = f['t'] - win / 2, (f.get('chord') or None)
        if cur and cur[2] == lab:
            cur[1] = t
        else:
            if cur and cur[2]:
                chords.append(tuple(cur))
            cur = [t, t, lab]
    if cur and cur[2]:
        chords.append(tuple(cur))
    return notes, chords, frozenset({'onset', 'frame', 'offset', 'velocity', 'chords'}), {'duration': r.get('audioSec')}


# ------------------------------------------------------------------ podział na zbiory

def assign_split(ex_id, val_rule='hash:5', test_rule='none', given=None):
    def match(rule):
        if rule in (None, 'none', ''):
            return False
        kind, _, arg = rule.partition(':')
        if kind == 'hash':
            return zlib.crc32(ex_id.encode()) % int(arg) == 0
        if kind == 'prefix':
            return any(ex_id.startswith(a) for a in arg.split(','))
        if kind == 'contains':
            return any(a in ex_id for a in arg.split(','))
        if kind == 'manifest':
            return False
        raise ValueError('nieznana reguła podziału %r' % rule)
    if given in ('train', 'val', 'test') and 'manifest' in (val_rule, test_rule):
        return given
    if match(test_rule):
        return 'test'
    if match(val_rule):
        return 'val'
    return given if given in ('train', 'val', 'test') else 'train'


def _finish(ex: Example, src: SourceConfig, given_split=None):
    if ex.duration is None and ex.notes:
        ex.duration = max(n.offset for n in ex.notes) + 0.5
    ex.split = assign_split(ex.id, src.val_rule, src.test_rule, given_split)
    ex.weight = src.weight
    return ex


# ------------------------------------------------------------------ adaptery źródeł

@source_adapter('truth_json')
def adapt_truth_json(src: SourceConfig):
    """Katalog z <id>.wav i <id>.truth.json (korpus, środowiska)."""
    for tp in sorted(glob.glob(os.path.join(src.root, '*.truth.json'))):
        i = os.path.basename(tp)[:-len('.truth.json')]
        wav = os.path.join(src.root, i + '.wav')
        notes, chords, has, meta = parse_truth_json(tp)
        yield _finish(Example(i, src.name, notes, chords, has, wav if os.path.exists(wav) else None,
                              duration=meta.get('duration'), group=i.rsplit('_', 1)[0], meta=meta), src)


@source_adapter('guitarset')
def adapt_guitarset(src: SourceConfig):
    """GuitarSet: options.annotations (katalog .jams), options.audio (katalog WAV), options.audio_suffix (domyślnie _mic.wav)."""
    o = src.options
    adir, wdir, suf = o.get('annotations', src.root), o.get('audio', src.root), o.get('audio_suffix', '_mic.wav')
    for jp in sorted(glob.glob(os.path.join(adir, '*.jams'))):
        i = os.path.splitext(os.path.basename(jp))[0]
        notes, chords, has, meta = parse_jams(jp)
        wav = os.path.join(wdir, i + suf)
        style = i.split('_')[1].split('-')[0].rstrip('0123456789') if '_' in i else ''
        yield _finish(Example(i, src.name, notes, chords, has, wav if os.path.exists(wav) else None,
                              duration=meta.get('duration'), group=style + ('_comp' if i.endswith('comp') else '_solo'), meta=meta), src)


@source_adapter('paired')
def adapt_paired(src: SourceConfig):
    """Dowolne pary <stem>.wav + <stem>.<ext> w jednym katalogu; options.format = parser adnotacji, options.ext = rozszerzenie."""
    fmt, ext = src.options.get('format', 'notes_csv'), src.options.get('ext', '.csv')
    popt = src.options.get('parser_options', {})
    for ap in sorted(glob.glob(os.path.join(src.root, '*' + ext))):
        i = os.path.basename(ap)[:-len(ext)]
        notes, chords, has, meta = parse_annotation(ap, fmt, **popt)
        wav = os.path.join(src.root, i + '.wav')
        yield _finish(Example(i, src.name, notes, chords, has, wav if os.path.exists(wav) else None,
                              duration=meta.get('duration'), group=src.name, meta=meta), src)


@source_adapter('manifest')
def adapt_manifest(src: SourceConfig):
    """Manifest JSONL (patrz opis modułu). Ścieżki względne liczone od katalogu manifestu."""
    base = os.path.dirname(os.path.abspath(src.manifest))
    rel = lambda p: p if p is None or os.path.isabs(p) else os.path.join(base, p)
    for line in open(src.manifest):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        m = json.loads(line)
        notes, chords, has, meta = parse_annotation(rel(m['annotation']), m.get('format', 'notes_csv'), **m.get('parser_options', {}))
        if 'has' in m:  # manifest może zawęzić dostępne etykiety
            has = frozenset(has) & frozenset(m['has'])
        ex = Example(m.get('id') or os.path.splitext(os.path.basename(m['annotation']))[0], src.name, notes, chords, has,
                     rel(m.get('audio')), rel(m.get('features')), m.get('features_hop'), m.get('duration', meta.get('duration')),
                     m.get('group', src.name), meta=meta)
        _finish(ex, src, m.get('split'))
        ex.weight *= float(m.get('weight', 1.0))
        yield ex


@source_adapter('engine_dump')
def adapt_engine_dump(src: SourceConfig):
    """Zgodność z gen 5: zrzuty HCQT z silnika (GT_DUMPH, krok 512) + prawda (options.truth: katalog .truth.json / .jams)."""
    tdir = src.options['truth']
    for dp in sorted(glob.glob(os.path.join(src.root, '*.bin'))):
        i = os.path.splitext(os.path.basename(dp))[0]
        cands = [i] + ([i.split('_', 1)[1]] if '_' in i and not i.startswith('env_') else [])
        tp = None
        for c in cands:
            for ext, fmt in (('.truth.json', 'truth_json'), ('.jams', 'jams')):
                if os.path.exists(os.path.join(tdir, c + ext)):
                    tp, f = os.path.join(tdir, c + ext), fmt
                    break
            if tp:
                break
        if not tp:
            continue
        notes, chords, has, meta = parse_annotation(tp, f)
        yield _finish(Example(i, src.name, notes, chords, has, None, dp, 512, meta.get('duration'), group=src.name, meta=meta), src)


def load_sources(cfg: Config) -> List[Example]:
    out = []
    for s in cfg.sources:
        if s.format not in SOURCE_ADAPTERS:
            raise KeyError('nieznany adapter źródła %r (znane: %s)' % (s.format, ', '.join(sorted(SOURCE_ADAPTERS))))
        out += list(SOURCE_ADAPTERS[s.format](s))
    return out


def summarize(examples: Iterable[Example]):
    """Krótki opis danych: liczba nagrań i nut na źródło i zbiór, dostępne etykiety (do wypisania przed uczeniem)."""
    from collections import defaultdict
    d = defaultdict(lambda: {'n': 0, 'notes': 0, 'sec': 0.0, 'has': set()})
    for e in examples:
        k = (e.source, e.split)
        d[k]['n'] += 1; d[k]['notes'] += len(e.notes); d[k]['sec'] += e.duration or 0; d[k]['has'] |= set(e.has)
    lines = ['%-14s %-6s %6s %8s %8s  %s' % ('źródło', 'zbiór', 'nagr.', 'nuty', 'min', 'etykiety')]
    for (s, sp), v in sorted(d.items()):
        lines.append('%-14s %-6s %6d %8d %8.1f  %s' % (s, sp, v['n'], v['notes'], v['sec'] / 60, ','.join(sorted(v['has']))))
    return '\n'.join(lines)


# ------------------------------------------------------------------ cechy i zbiór do uczenia

def example_features(ex: Example, fcfg: FeatureConfig, cache_dir=None, fp16=False, mmap=False):
    """[T, C, P] dla przykładu: gotowe cechy (npy / zrzut silnika) albo HCQT liczone z dźwięku.
    fp16 / mmap: pamięć podręczna w float16 i odczyt przez memmap (wtedy wynik może nie być float32: rzutuj wycinki)."""
    from .features import cached_hcqt, hcqt, load_engine_dump
    if 'signal' in ex.meta:  # dźwięk w pamięci (synth, testy), już w fcfg.sr
        return hcqt(ex.meta['signal'], fcfg)
    if ex.features:
        hop = ex.features_hop or fcfg.hop
        if hop != fcfg.hop:
            raise ValueError('%s: cechy mają krok %d, konfiguracja %d (ustaw features.hop=%d)' % (ex.id, hop, fcfg.hop, hop))
        if ex.features.endswith('.bin'):
            return load_engine_dump(ex.features)
        X = np.load(ex.features, mmap_mode='r' if mmap else None)
        return X if mmap else X.astype(np.float32)
    if not ex.audio:
        raise ValueError('%s: brak dźwięku i cech' % ex.id)
    return cached_hcqt(ex.audio, fcfg, cache_dir, fp16=fp16, mmap=mmap)


def _feat_job(args):
    ex, fcfg, cache_dir, fp16 = args
    try:
        X = example_features(ex, fcfg, cache_dir, fp16=fp16, mmap=True)
        return ex.id, len(X), None
    except Exception as err:  # uszkodzony plik nie zatrzymuje całego zbioru
        return ex.id, 0, repr(err)


def precompute_features(examples, cfg: Config, jobs=None, log=print):
    """Liczy cechy wszystkich przykładów równolegle do pamięci podręcznej (cfg.train.cache_dir). Zwraca przykłady z cechami."""
    import multiprocessing as mp
    import time
    jobs = jobs or cfg.train.workers or os.cpu_count() or 1
    todo = [(e, cfg.features, cfg.train.cache_dir, cfg.train.cache_fp16) for e in examples]
    ok, t0, bad = set(), time.time(), 0
    if jobs <= 1 or not cfg.train.cache_dir:
        res = map(_feat_job, todo)
    else:
        pool = mp.get_context('fork').Pool(jobs)
        res = pool.imap_unordered(_feat_job, todo, chunksize=4)
    for k, (i, T, err) in enumerate(res):
        if err:
            bad += 1
            log('cechy %s: %s' % (i, err))
        elif T:
            ok.add(i)
        if (k + 1) % 500 == 0 or k + 1 == len(todo):
            log('cechy: %d/%d (%.0f s, błędów %d)' % (k + 1, len(todo), time.time() - t0, bad))
    if jobs > 1 and cfg.train.cache_dir:
        pool.close(); pool.join()
    return [e for e in examples if e.id in ok]


class TrainSet:
    """Losowe wycinki z ważeniem źródeł. Każdy element: x [C, L, P], cele i maski z labels.make_targets, waga."""

    def __init__(self, examples: List[Example], cfg: Config, rng=None, preload=True):
        from .labels import make_targets
        self.cfg, self.rng = cfg, rng or np.random.default_rng(cfg.train.seed)
        self.items = []
        for e in examples:
            X = example_features(e, cfg.features, cfg.train.cache_dir, fp16=cfg.train.cache_fp16, mmap=cfg.train.lazy)
            if not len(X):
                continue
            self.items.append((e, X, make_targets(e, len(X), cfg.features, cfg.labels)))
        if not self.items:
            raise ValueError('brak przykładów do uczenia')
        by_src = {}
        for k, (e, _, _) in enumerate(self.items):
            by_src.setdefault(e.source, []).append(k)
        self.sources = sorted(by_src)
        self.by_src = by_src
        w = np.array([self.items[by_src[s][0]][0].weight for s in self.sources], float)
        self.src_p = w / w.sum()

    def sample(self, L, rng=None):
        """-> (x [L,C,P], mapy celów [L,...], avail [5], valid [L]); krótsze nagrania dopełnione zerami (valid = 0)."""
        rng = rng if rng is not None else self.rng
        s = self.sources[rng.choice(len(self.sources), p=self.src_p)]
        idx = self.by_src[s]
        lens = np.array([len(self.items[k][1]) for k in idx], float)
        e, X, (maps, avail) = self.items[idx[rng.choice(len(idx), p=lens / lens.sum())]]  # dłuższe nagrania częściej
        T = len(X)
        t0 = int(rng.integers(0, T - L + 1)) if T > L else 0
        x = np.asarray(X[t0:t0 + L], np.float32)
        tg = {k: v[t0:t0 + L] for k, v in maps.items()}
        n = len(x)
        valid = np.r_[np.ones(n, np.float32), np.zeros(L - n, np.float32)]
        if n < L:
            x = np.pad(x, ((0, L - n), (0, 0), (0, 0)))
            tg = {k: np.pad(v, ((0, L - n),) + ((0, 0),) * (v.ndim - 1), constant_values=-1 if k == 'tab' else 0)
                  for k, v in tg.items()}
        return x, tg, avail, valid

    def batch(self, B, L, rng=None):
        xs, tgs, av, va = zip(*(self.sample(L, rng) for _ in range(B)))
        return (np.stack(xs), {k: np.stack([t[k] for t in tgs]) for k in tgs[0]}, np.stack(av), np.stack(va))
