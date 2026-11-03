"""config.py - konfiguracja gen 6. Wszystko, co zależy od danych, jest tutaj, a nie w kodzie (dane będą się zmieniać)."""
from __future__ import annotations
import dataclasses as dc
import json
from typing import List, Optional, Tuple


@dc.dataclass
class FeatureConfig:
    """Wejście sieci: HCQT (harmonicznie ułożone widmo). Domyślnie jak w gen 5, ale z krokiem 256 (23 ms zamiast 46 ms):
    tolerancja początku w publikacjach to 50 ms, więc klatka 46 ms była za gruba."""
    sr: int = 11025                 # częstotliwość po zmianie próbkowania
    hop: int = 256                  # krok klatki w próbkach (gen 5: 512)
    midi_lo: int = 36               # najniższa wysokość (C2; najniższa struna w drop C)
    n_semis: int = 53               # liczba półtonów (36..88)
    bins_per_semi: int = 3
    win_long: int = 4096            # okno o dobrej rozdzielczości częstotliwości
    win_short: int = 1024           # okno o dobrej rozdzielczości czasu
    zero_pad: int = 4               # dopełnienie zerami FFT
    harm_long: Tuple[float, ...] = (0.5, 1, 2, 3, 4, 5)
    harm_short: Tuple[float, ...] = (1, 2, 3)
    ref_pct: float = 99.5           # normalizacja: 0 dB = ten percentyl nagrania
    db_range: float = 60.0
    clip_hi: float = 1.3
    frontend: str = 'resample'      # 'resample' = dokładna zmiana próbkowania; 'engine' = filtr decymatora jak w silniku C++

    @property
    def n_bins(self) -> int:
        return self.n_semis * self.bins_per_semi

    @property
    def n_channels(self) -> int:
        return len(self.harm_long) + len(self.harm_short)

    @property
    def frame_sec(self) -> float:
        return self.hop / self.sr

    def frame_center(self, t):
        """Środek okna długiego klatki t [s] (tak samo jak Hcqt::frameCenter w C++)."""
        return (t * self.hop + self.win_long / 2) / self.sr

    def time_to_frame(self, sec):
        return (sec * self.sr - self.win_long / 2) / self.hop


@dc.dataclass
class LabelConfig:
    onset_width: int = 1            # klatki po obu stronach początku z miękką etykietą
    onset_soft: float = 0.4         # wartość miękkiej etykiety
    offset_width: int = 1
    offset_soft: float = 0.4
    use_audible_end: bool = True    # koniec nuty = min(t1, ta), gdy źródło podaje koniec słyszalności
    n_strings: int = 6
    n_frets: int = 20               # progi 0..19; klasa 0 = struna milczy
    tuning: Tuple[int, ...] = (40, 45, 50, 55, 59, 64)


@dc.dataclass
class ModelConfig:
    hidden: int = 32                # kanały na binach 1/3 półtonu
    n_harm_blocks: int = 3          # bloki harmonicznych konwolucji
    harm_offsets: Tuple[float, ...] = (0.5, 1, 2, 3, 4, 5, 6)  # alikwoty, na które patrzy blok (jako krotność f0)
    time_kernel: int = 3
    time_dilations: Tuple[int, ...] = (1, 2, 4)  # dylatacje w czasie w kolejnych blokach
    d_model: int = 48               # kanały po zejściu do półtonów
    n_ctx_layers: int = 2           # warstwy kontekstu (uwaga w czasie + uwaga między wysokościami + FFN)
    n_heads: int = 4
    time_window: int = 43           # klatek po każdej stronie (43 x 23 ms = 1 s)
    causal: bool = False            # True = tylko przeszłość (tryb na żywo); gen 5 miała zawsze tylko przeszłość
    pitch_attention: bool = True    # uwaga między wysokościami w tej samej klatce (oktawy, alikwoty innych strun)
    dropout: float = 0.1
    heads: Tuple[str, ...] = ('onset', 'frame', 'offset', 'velocity', 'tab')
    onset_to_frame: bool = True     # głowica "brzmi" dostaje wynik głowicy "początek" (jak w Onsets and Frames)


@dc.dataclass
class LossConfig:
    w_onset: float = 1.0
    w_frame: float = 1.0
    w_offset: float = 0.5
    w_velocity: float = 0.5
    w_tab: float = 0.5
    onset_pos_weight: float = 4.0
    offset_pos_weight: float = 2.0
    focal_gamma: float = 0.0        # > 0 = strata ogniskowa (focal) zamiast zwykłej BCE
    label_smoothing: float = 0.0


@dc.dataclass
class DecodeConfig:
    th_onset: float = 0.5
    th_frame: float = 0.5
    th_offset: float = 0.5
    th_start: float = 0.7           # nuta bez wykrytego początku: p(brzmi) >= th_start przez min_frames klatek
    min_frames: int = 2
    gap_frames: int = 1             # ile klatek poniżej progu kończy nutę
    merge_sec: float = 0.03         # scalanie duplikatów tej samej wysokości
    min_dur: float = 0.06


@dc.dataclass
class SourceConfig:
    """Jedno źródło danych. `format` to nazwa adaptera z data.ADAPTERS; `root`/`manifest` wskazują dane."""
    name: str
    format: str
    root: Optional[str] = None
    manifest: Optional[str] = None
    weight: float = 1.0
    val_rule: str = 'hash:5'        # 'hash:K' (co K-ty plik), 'prefix:02_', 'manifest' (pole split), 'none'
    test_rule: str = 'none'
    options: dict = dc.field(default_factory=dict)


@dc.dataclass
class TrainConfig:
    epochs: int = 30
    steps_per_epoch: int = 500
    batch: int = 8
    crop_frames: int = 192          # 192 x 23 ms = 4,4 s
    lr: float = 1e-3
    weight_decay: float = 1e-4
    warmup_steps: int = 500
    grad_clip: float = 1.0
    seed: int = 1
    select_metric: str = 'note_F1'  # metryka walidacji wybierająca najlepszą epokę
    early_stop: int = 8             # epok bez poprawy
    augment: dict = dc.field(default_factory=lambda: {'gain_db': 6.0, 'pitch_shift_bins': 0, 'noise': 0.0, 'spec_mask': 0.1})
    cache_dir: Optional[str] = None
    workers: int = 0


@dc.dataclass
class Config:
    features: FeatureConfig = dc.field(default_factory=FeatureConfig)
    labels: LabelConfig = dc.field(default_factory=LabelConfig)
    model: ModelConfig = dc.field(default_factory=ModelConfig)
    loss: LossConfig = dc.field(default_factory=LossConfig)
    decode: DecodeConfig = dc.field(default_factory=DecodeConfig)
    train: TrainConfig = dc.field(default_factory=TrainConfig)
    sources: List[SourceConfig] = dc.field(default_factory=list)

    def to_dict(self):
        return dc.asdict(self)

    def save(self, path):
        with open(path, 'w') as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)

    @staticmethod
    def from_dict(d):
        def build(cls, x):
            if x is None:
                return cls()
            kw = {}
            for fld in dc.fields(cls):
                if fld.name in x:
                    v = x[fld.name]
                    if isinstance(v, list) and 'Tuple' in str(fld.type):
                        v = tuple(v)
                    kw[fld.name] = v
            unknown = set(x) - {f.name for f in dc.fields(cls)}
            if unknown:
                raise ValueError('nieznane pola %s w %s' % (sorted(unknown), cls.__name__))
            return cls(**kw)
        return Config(features=build(FeatureConfig, d.get('features')), labels=build(LabelConfig, d.get('labels')),
                      model=build(ModelConfig, d.get('model')), loss=build(LossConfig, d.get('loss')),
                      decode=build(DecodeConfig, d.get('decode')), train=build(TrainConfig, d.get('train')),
                      sources=[build(SourceConfig, s) for s in d.get('sources', [])])

    @staticmethod
    def load(path):
        with open(path) as f:
            return Config.from_dict(json.load(f))
