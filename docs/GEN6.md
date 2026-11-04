# Generacja 6: architektura (bez wag)

Gen 6 to nowa architektura modelu i cały tor wokół niego, przygotowane pod **nowe dane w nieznanym jeszcze formacie**.
Ta wersja zawiera kod, testy i konfigurację; modelu jeszcze nie uczono, a silnik C++ nadal używa gen 5
(`src/gt_gen5*.hpp` bez zmian). Kod: `tools/gen6/` (Python 3, numpy, PyTorch; `pip install -r tools/gen6/requirements.txt`).

## Przepływ

```
dowolny format ──adapter──▶ Example (nuty, akordy, które etykiety są znane)
                              │
dźwięk ──front-end──▶ HCQT [T, 9, 159] ──▶ Gen6 ──▶ mapy: początek / brzmi / koniec / głośność / struna-próg
                              │                            │
                     labels: mapy celów + maski     decode: lista nut (+ głośność, struna)
                              │                            │
                     losses: strata z maskami       metrics: wszystkie miary ewaluacji
```

## Dane (`data.py`): zawsze ten sam zapis, adaptery dla formatów

Reszta pakietu zna tylko `Example` i `Note(pitch, onset, offset, velocity?, string?, audible_end?)`. Pole `has` mówi, które
etykiety źródło **naprawdę** ma (`onset, frame, offset, velocity, tab, chords`). Strata i metryki pomijają brakujące, więc można
mieszać nagrania z MIDI (z głośnością), z ręcznej adnotacji (bez końców nut) i z GuitarSet (ze strunami).

| adapter (`format` źródła) | dane |
|---|---|
| `manifest` | **dla nowych danych**: plik JSONL, jedna linia na nagranie: `audio`, `annotation`, `format`, `split`, `group`, opcjonalnie `features`, `has`, `weight`, `parser_options` (przykład: `tools/gen6/configs/manifest.example.jsonl`) |
| `guitarset` | GuitarSet (JAMS, 6 strun → tabulatura, akordy „performed”) |
| `truth_json` | korpus (`gen_corpus`) i środowiska (`gen_env`): `*.wav` + `*.truth.json` |
| `paired` | dowolne pary `<nazwa>.wav` + `<nazwa>.<ext>` z wybranym parserem |
| `engine_dump` | zgodność z gen 5: zrzuty HCQT z silnika (`GT_DUMPH`, krok 512) |

Parsery adnotacji: `jams`, `truth_json`, `notes_csv` (CSV/TSV, nazwy kolumn konfigurowalne, wysokość w MIDI albo Hz, głośność
0–1 albo 0–127, kolumna struny), `midi` (własny parser SMF z mapą tempa; opcja: kanał = struna), `engine_json` (wynik `gt_cli`).
Nowy format to jedna funkcja z dekoratorem `@annotation_parser('nazwa')`.
Podział na zbiory: `hash:K`, `prefix:a,b`, `contains:x`, `manifest` (pole `split`), osobno dla walidacji i testu.

## Cechy (`features.py`, `audio.py`)

HCQT taki jak w `src/gt_hcqt.hpp`: 9 kanałów (alikwoty 0,5×…5× z okna 372 ms i 1×–3× z okna 93 ms), 159 binów co 1/3 półtonu
(MIDI 36–88), dB względem 99,5. percentyla nagrania. Zmiany:

* **krok 256 zamiast 512** (23 ms zamiast 46 ms). Tolerancja początku w publikacjach to 50 ms, więc klatka 46 ms była za gruba;
* **dokładna zmiana próbkowania do 11025 Hz**. Silnik C++ dzieli częstotliwość przez całkowite D, więc przy 48 kHz liczył cechy przy
  12 kHz: inny krok w sekundach i inne biny niż przy 44,1 kHz. Front-end `engine` (`FeatureConfig.frontend`) odtwarza filtr
  decymatora silnika; test sprawdza zgodność ze zrzutem z C++ (średnia różnica < 1e-4);
* cechy liczone w Pythonie, z pamięcią podręczną na dysku (`train.cache_dir`). Do uczenia nie są potrzebne zrzuty z silnika.

## Sieć (`model.py`)

1. **Trzon**: konwolucja 3×7, 9 → 32 kanały.
2. **3 bloki harmoniczne**: każdy zbiera wartości z binów na alikwotach kandydata (0,5×, 1×, 2×…6×, przesunięcia 36·log₂h binów),
   więc jedna warstwa widzi całą serię harmoniczną (w gen 5 tylko konwolucje 3×7 i jedna warstwa „oktawa niżej/wyżej”). Potem
   konwolucja sąsiednich binów (rozstrojenie, nieharmoniczność struny), konwolucja w czasie z dylatacją 1, 2, 4,
   normalizacja warstw, połączenia resztkowe.
3. **Zejście do półtonów** (konwolucja 1×3, krok 3) i wyuczone **osadzenie wysokości**: sieć wie, w którym rejestrze jest kandydat.
4. **2 warstwy kontekstu**, każda składa się z:
   * uwagi w czasie dla każdej wysokości, w oknie ±32 klatki (±0,74 s), **w obie strony** przy analizie nagrania (gen 5 patrzyła
     tylko wstecz, choć analizuje całe nagranie), z premią za odległość; `causal=True` daje wariant na żywo;
   * **uwagi między wysokościami** w tej samej klatce (nowość): oktawy, alikwoty innych strun, akord jako całość; premia za
     odległość w półtonach (12, 19, 24…);
   * warstwy feed-forward (pre-norm, dropout).
5. **5 głowic**: początek; brzmi (dostaje p(początek), jak w Onsets and Frames); **koniec**; **głośność**; **tabulatura**
   (dla każdej struny: cisza albo próg 0–19, logity z cech półtonu `strój[s] + próg`, wagi osobne dla struny).

134 tys. parametrów (gen 5: 37 tys.), w PyTorch na CPU ok. 1 s na 23 s nagrania. `Gen6.predict` liczy całe nagranie kawałkami
z zakładką (`halo`), a test sprawdza, że wynik nie zależy od długości kawałka. Wszystkie rozmiary są w `ModelConfig`.

## Etykiety, strata, dekoder

* `labels.py`: mapy celów (brzmi, początek z miękkimi sąsiadami, koniec, głośność w klatce początku, klasa struna-próg) oraz
  wektor dostępności. **Poprawka względem gen 5**: klatka początku zawsze też „brzmi”. W gen 5 jej środek mógł wypaść tuż
  przed początkiem nuty, wtedy etykieta „brzmi” wynosiła 0, a dekoder wymaga p(brzmi) ≥ 0,3 przy początku.
* `losses.py`: BCE (opcjonalnie strata ogniskowa) z wagami pozytywów, MSE głośności tylko w klatkach początku, entropia krzyżowa
  tabulatury; maski dostępności per przykład i maska dopełnienia wycinka.
* `decode.py`: algorytm dekodera gen 5, do tego koniec z głowicy końca, głośność, struna (średnie p na klatkach nuty) i scalanie
  duplikatów. Test: idealne mapy przez dekoder dają z powrotem nuty (F1 > 0,97).

## Ewaluacja (`metrics.py`, `evaluate.py`)

Wszystkie miary są w jednym module numpy. Przyjmują listy nut, więc tak samo oceniają gen 6 i wyniki JSON silnika z dowolnej
generacji. Definicje są zgodne z mir_eval; testy porównują je z mir_eval 0.8 z dokładnością 1e-9.

| grupa | miary |
|---|---|
| nuty | F1/P/R początków (50 ms, ±50¢; też 100 ms), początek+koniec (20 % / 50 ms), z głośnością (jak `transcription_velocity`), średnie pokrycie; dopasowanie maksymalne (Hopcroft–Karp); błędy czasu początków (mediana, przesunięcie systematyczne, 90. percentyl) |
| klatki (siatka 10 ms) | P/R/F1, Acc, E_sub/E_miss/E_fa/E_tot (Poliner i Ellis 2007), klasy dźwięku, udział fałszywych alarmów w oktawie/duodecymie/kwincie od prawdziwej nuty |
| mapy sieci | AP (bez progu), najlepszy próg i F1 przy nim (strojenie dekodera), ECE, Brier |
| podtrzymanie | pokrycie słyszalnego czasu nuty, % nut pokrytych w 80 %, poszatkowanie, przedłużenie (jak `tools/score.py`) |
| akordy | prima, dur/moll (jak `mir_eval.chord.majmin`), zbiór dźwięków, bas, segmentacja (directional Hamming), akord na uderzenie; `chords_from_notes` nazywa akordy z nut, gdy system sam ich nie podaje |
| tabulatura | P/R/F1 par struna-próg, TDR (Wiggins i Kim 2019), % nut z poprawną struną |
| stroik | trafiony dźwięk, pokrycie, mediana błędu w centach (z JSON silnika) |
| zbiorczo | mikro (suma po plikach) i makro (średnia po plikach, jak w publikacjach), po grupach; 95 % przedziały bootstrap; sparowany bootstrap A vs B |

```bash
# wyniki silnika C++ (dowolna generacja) na źródłach z konfiguracji
python3 -m tools.gen6.evaluate engine --config cfg.json --results wyniki_json/ --split test --out silnik.json
# model gen 6
python3 -m tools.gen6.evaluate model --config cfg.json --ckpt run/best.pt --split test --out gen6.json
# czy różnica jest istotna (te same pliki)
python3 -m tools.gen6.evaluate compare gen6.json silnik.json --metric note_F1
```

## Uczenie (`train.py`): gotowe, nieuruchomione na prawdziwych danych

AdamW, rozgrzewka i kosinus, przycinanie gradientu, ważenie źródeł, losowe wycinki (192 klatki = 4,4 s), augmentacja (poziom,
szum, maskowanie pasm i chwil). Po każdej epoce pełna walidacja tymi samymi miarami i zapis `run/last.pt`; najlepsza epoka według
`train.select_metric` (domyślnie `note_F1`) trafia do `run/best.pt`; uczenie kończy się po `early_stop` epokach bez poprawy;
dziennik w `run/log.jsonl`; `--resume`.

```bash
python3 -m tools.gen6.train --smoke --out /tmp/run               # próba na syntetycznych danych (ok. 10 s)
python3 -m tools.gen6.train --config tools/gen6/configs/gen6.json --out run/
python3 -m pytest tools/gen6/tests                                # 18 testów
```

## Co zostaje

1. Nowe dane: manifest (albo adapter) i wpis w `sources` konfiguracji; `data.summarize` pokaże, co się wczytało.
2. Uczenie i strojenie progów dekodera (`map_metrics` → `best_th` na walidacji).
3. Porównanie z gen 5 na zbiorze testowym (`evaluate engine` vs `evaluate model`, `compare`).
4. Przeniesienie do C++/WASM: eksport wag i inferencja jak `src/gt_gen5.hpp`, w tym bloki harmoniczne, normalizacja warstw,
   uwaga w obie strony i między wysokościami oraz nowe głowice.

## Uczenie na Kaggle (`tools/gen6/kaggle/`)

Dwa etapy, żeby nie zużywać limitu GPU na generowanie danych:

| etap | notatnik | sprzęt | co robi |
|---|---|---|---|
| A, `prepare.py` | `gutar-gen6-dane` | CPU (4 rdzenie), internet | korpus MIDI (MAESTRO + music21) → `gen_classical` (train: 2 wersje × 1 fragment na utwór, validation/test: 2 wersje) → 900 środowisk gitarowych `gen_env` → GuitarSet (zenodo) → cechy HCQT gen 6 w float16, równolegle → `manifest_<źródło>.jsonl`. Ok. 7 tys. nagrań, ok. 14 GB (limit wyjścia Kaggle: 20 GB). |
| B, `train_kaggle.py` | `gutar-gen6-trening` | GPU T4, wynik etapu A jako wejście | uczenie gen 6 (`configs/gen6_kaggle.json`: większa sieć, `hidden` 48, `d_model` 64, 250 tys. parametrów; paczka 16, mieszana precyzja), budżet czasu dopasowany do sesji 12 h, potem ocena najlepszej epoki na zbiorach testowych → `run/test.json` |

Źródła i wagi: klasyka 0,5 (podział po utworach), GuitarSet 0,3 (walidacja: funk gracza 02, test: gracze 03–05, jak w gen 5),
środowiska 0,2 (co 10. nagranie do walidacji). Walidacja po każdej epoce na stałej próbie 180 nagrań.

Nowe opcje `train` (wszystkie z wartościami domyślnymi jak dotąd): `device` (auto/cuda/cpu), `amp`, `lazy` (cechy przez memmap,
nie w RAM), `cache_fp16`, `max_val`, `prefetch` (paczki przygotowywane w wątku w tle), `time_budget_sec` (po pierwszej epoce liczba
epok i harmonogram lr przycinane do budżetu), `workers` (równoległe liczenie cech przed uczeniem). Przy braku pamięci GPU na początku
uczenia paczka jest zmniejszana o połowę.

```bash
export KAGGLE_API_TOKEN=...                       # klucza nie zapisujemy w repozytorium
python3 tools/gen6/kaggle/push.py dane            # etap A
kaggle kernels status <użytkownik>/gutar-gen6-dane
python3 tools/gen6/kaggle/push.py trening         # etap B, gdy A skończy się powodzeniem
kaggle kernels output <użytkownik>/gutar-gen6-trening -p wynik/   # best.pt, log.jsonl, test.json, train.log
```
Kod jest wklejany do skryptu notatnika (tar.gz w base64), więc Kaggle nie potrzebuje dostępu do repozytorium.
Notatnik na koncie bez weryfikacji telefonem nie ma internetu, dlatego wejścia są prywatnymi zbiorami danych:
`<użytkownik>/gutar-gen6-korpus` dla etapu A (`korpus.zip` = wynik `fetch_classical.py`: `manifest.csv` + `midi/`) oraz
`<użytkownik>/gutar-guitarset-czesci` dla etapu B (`annotation.zip`, `audio_00.zip` … `audio_05.zip`, po graczu; jednego pliku
626 MB Kaggle nie przetworzył). Etap B liczy cechy GuitarSet sam (ok. 10 min), `prepare.py --input` rozpakowuje zipy.

**Druga sesja (dalsze uczenie).** Jedna sesja Kaggle trwa najwyżej 12 h, więc przy tygodniowym limicie ok. 30 h GPU uczenie
można przedłużyć: `python3 tools/gen6/kaggle/push.py dalej` (notatnik `gutar-gen6-trening-dalej`, wejścia: dane z etapu A i wynik
notatnika `gutar-gen6-trening`). Kopiuje `run/last.pt`, `best.pt` i dziennik, bierze cechy GuitarSet z poprzedniej sesji
i uczy dalej z nowym cyklem lr (ciepły restart, szczyt 4e-4; `--extend-lr`) aż do terminu sesji. `best.pt` zmienia się tylko, gdy walidacja przebije najlepszy wynik z pierwszej sesji.

**Pilnowanie czasu sesji.** Termin jest twardy i liczony od startu skryptu: `--hours` (domyślnie 11,5 h, limit Kaggle 12 h) minus
`--eval-hours` (0,45 h na ocenę testową; zmierzona 16 min na 700 nagrań) minus `--margin-min` (15 min na zapis wyniku). Zegar jest
sprawdzany w każdym kroku, harmonogram lr (kosinus) liczony od ułamka czasu, więc kończy się dokładnie w terminie bez względu na
to, ile trwa krok; zapas na ostatnią walidację i zapis to 1,3 × zmierzony czas walidacji + 30 s; gdy na ocenę testową zostaje
mniej niż 10 min, liczy się ją na próbie. Dziennik podaje godziny (UTC i czas polski): start, koniec uczenia, koniec oceny, limit
sesji. Sesja 1 (stara wersja) szacowała liczbę epok z pierwszej epoki (1013 s, kolejne 723 s), dlatego skończyła ok. 3 h za wcześnie.

### Wyniki sesji 1 (36 epok, najlepsza 29; test: utwory i gracze spoza uczenia, 700 nagrań)

| zbiór testowy (mikro) | gen 5 | **gen 6** |
|---|---:|---:|
| GuitarSet 03–05: nuty F1 (50 ms), akompaniament / melodie | 75,6 / 83,4 % | **84,4 / 88,8 %** |
| GuitarSet: nuty z początkiem i końcem, akompaniament / melodie | 40,9 % (razem) | **68,0 / 77,9 %** |
| klasyka (520 nagrań, 27 instrumentów, 11 miejsc): nuty F1 | 62,4 % (próba walidacyjna) | **≈ 80 %** |
| razem (makro, 95 % przedział bootstrap) | | **84,8 % [83,8; 85,7]** |

Najsłabiej: chór (55 %), kontrabas, wiolonczela i skrzypce (65–73 %), syntezator (70 %); najlepiej: ukulele, pizzicato, gitary (88–94 %).

### Więcej danych (od sesji 3)

* **Augmentacja tempa i wysokości** (`train.augment`: `tempo` 0,12, `p_tempo` 0,5, `pitch_semis` 2, `p_pitch` 0,3; `data.stretch`,
  `data.shift_pitch`): wycinek źródła o długości L·r (r = 1/1,12…1,12) jest ściskany lub rozciągany do L klatek (cechy: interpolacja,
  brzmi / struna: najbliższa klatka, początki / końce / głośność: przeniesienie pików, żaden początek nie ginie), a połowa z nich
  dodatkowo przesuwana o ±1–2 półtony (cechy o 3 biny na półton, mapy o półton; tabulatura wtedy nieznana). Razem daje to też
  „przyspieszoną taśmę” (tempo i wysokość naraz).
* **Drugi zestaw nagrań** `gutar-gen6-dane2` (CPU, bez limitu GPU): `push.py dane2` = `prepare.py --seed-base 7 --env-seed 90000
  --versions 3 --clips 1 --len 8 16 --only-train` (inne transpozycje, tempa, obsady, miejsca; trzy formy utworu; tylko train, bo
  walidacja i test zostają z pierwszego zestawu, żeby wyniki były porównywalne). Uczenie: `push.py dalej --extra-data gutar-gen6-dane2`;
  `train_kaggle.py` dzieli wagę źródła po równo między zestawy.
* **Mniej idealne dane** (`train.augment`, od sesji 3): `noise` 0,02 (szum w cechach), `pitch_shift_bins` 1 z `p_detune` 0,3
  (rozstrojenie: cechy o ±1 bin = ±33 centy, etykiety bez zmian), `label_jitter_frames` 1 z `p_jitter` 0,3 (początki i końce każdej
  wysokości przesunięte o ±1 klatkę = ±23 ms, jak przy ręcznej adnotacji). Wpływu na wynik nie mierzyłem; jitter może minimalnie
  rozmywać początki, więc przy spadku `onoff_F1` wyłączyć go ustawiając `label_jitter_frames` na 0.
