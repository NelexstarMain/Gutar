# Gitara Słuchacz (silnik C++17 → WebAssembly)

Rozpoznawanie nut, akordów i stroju gitary na żywo z mikrofonu albo z pliku audio.
Cała analiza dźwięku jest napisana w **C++17** (`src/`), kompilowana do **WebAssembly** i osadzona
w jednym pliku HTML. Ten plik działa jako artefakt i jako samodzielna aplikacja offline.

* `dist/gitara-sluchacz.html`: gotowa aplikacja (jeden plik, ok. 5 MB, mikrofon działa po otwarciu z dysku)
* `dist/gt_engine.wasm`: sam silnik (ok. 400 KB)

## Co potrafi

* wielogłosowe wykrywanie nut (grzebień alikwotów + kasowanie), z podwojeniami oktawowymi (E2+E3),
* **generacja 5: sieć neuronowa na widmie** (przy analizie nagrania): konwolucyjna sieć z blokiem uwagi (attention) na harmonicznie
  ułożonym widmie całego nagrania zwraca dla każdej klatki i półtonu p(brzmi) i p(zaczyna się), dekoder składa z tego nuty;
* **wytrenowane modele (AI)**: przy analizie nagrania model maski ocenia, ile w każdym paśmie jest gitary, a ile otoczenia (szum, stuki,
  tony), a model nut (gen 4: zespół 4 sieci, uczony na losowych środowiskach, korpusie i prawdziwych nagraniach GuitarSet) ocenia każdą kandydującą wysokość w każdej klatce: czy to fala tej gitary, czy
  szum, odbicie albo alikwot innej struny; do tego **odszumianie**: widmo szumu tła liczone z wszystkich klatek nagrania,
* **najpierw nuty, potem akordy**: po analizie nagrania akord jest składany z gotowej listy nut (uderzenia = grupy początków nut,
  spóźnione struny dopełniają akord swojego uderzenia, nuty pasujące do bieżącego akordu nie zmieniają jego nazwy); 20 typów, chwyty z basem, np. `C/G`,
* stroik z wskaźnikiem w centach i wskazaniem struny,
* 8 strojów gitary (standard, drop D, DADGAD, open G, …), palcowanie z programowaniem dynamicznym po całym utworze,
* **śledzenie lewej ręki** (`src/gt_hand.hpp`): zestaw nut brzmiących naraz musi dać się zagrać jednym ułożeniem palców
  (cztery palce, rozpiętość zależna od pozycji, barre bez strun na niższym progu, osobne palce gdy barre jest niemożliwe), a pozycja
  ręki nie skacze szybciej, niż ręka zdąży; nuty niemożliwe do zagrania są odrzucane przed analizą akordów, strefa ręki jest widoczna na gryfie,
* interfejs: akord, stroik i analizator (poziom + widmo w jednym pasku), gryf, oś czasu (okno nut + mapa całego nagrania w jednym płótnie, tabela jako drugi widok), pasek akordów,
* **odtwarzanie całości**: nagranie, transkrypcja zagrana syntezatorem (też w C++), albo oba naraz; kursor, przewijanie, skok po akordzie,
* **pobieranie całości**: ZIP z nagraniem WAV, MIDI (ze znacznikami akordów), tabulaturą, listą akordów, sesją JSON i odsłuchem transkrypcji,
* po zatrzymaniu mikrofonu nagranie jest analizowane jeszcze raz w trybie offline (dokładniejszym).

## Budowanie

```bash
pip install ziglang            # kompilator C++ → wasm32 (albo Emscripten, po zmianie ZIG w build.sh)
npm install binaryen           # opcjonalnie: rezerwa asm.js, gdy platforma zabrania WebAssembly
./build.sh                     # dist/gt_engine.wasm + dist/gitara-sluchacz.html
```

Silnik jest zwykłym C++ (`src/gt_*.hpp`), więc można go też zbudować natywnie:
`g++ -std=c++17 -O2 src/cli.cpp -o gt_cli && ./gt_cli analyze nagranie.wav wynik.json`.

## Co poprawiono względem pierwowzoru (JS)

| | |
|---|---|
| Ramki analizy | w analizie plików pierwowzór liczył kilka ramek z jednej porcji audio na tym samym, ostatnim oknie (czasy przesunięte do ok. 90 ms); teraz krok 512 próbek po decymacji (46 ms), każde okno w swoim miejscu |
| Strój odniesienia | automatyczna estymacja rozstrojenia z histogramu pików (do ±50¢), więc rozstrojona gitara nadal daje poprawne nuty |
| Próg ciszy | automatyczne podnoszenie progu przy szumie tła (przed-przebieg dla plików, statystyka minimów na żywo) |
| Akordy | dowody zbierane od uderzenia (okno obejmujące poprzedni akord nie zaburza decyzji), wykrywanie zmiany harmonii, miękka obecność tonów, preferencja prostszych akordów |
| Stroik | f0 i nieharmoniczność struny dopasowywane regresją ważoną (zamiast stałego B), mediana z 5 ramek |
| Nuty | potwierdzanie w czasie (nie w ramkach), tłumienie ponownych wyzwoleń ogona, oktawowe podwojenia po nadmiarze parzystych alikwotów |
| Palcowanie | Viterbi po całym utworze zamiast zachłannego wyboru, z twardymi ograniczeniami fizycznymi ręki (także w tabulaturze i MIDI) |
| Ręka | odrzucanie nut niemożliwych do zagrania razem; w stanie ustalonym pierwszeństwo mają nuty już trzymane, tuż po uderzeniu pamięć jest pomijana, żeby nie blokować zmiany akordu |
| Wydajność | natywnie RTF 0,020 wobec 0,034 w JS; w WebAssembly (node) ok. 0,03; rezerwa asm.js ok. 0,13 (nadal 7× szybciej niż czas rzeczywisty) |

## Pomiary

`tools/gen_corpus.cpp` generuje syntetyczne nagrania gitary (inna synteza niż w pierwowzorze: losowa nieharmoniczność,
dudnienie polaryzacji, ślizg wysokości przy ataku, rezonans pudła, pogłos, szum biały/różowy/brum, rozstrojenie).
`tools/run_bench.sh` uruchamia **oryginalny silnik JS** (`tools/baseline/`) i nowy silnik na tych samych plikach i liczy te same metryki
(`tools/score.py`). Parametry były strojone na zbiorze `dev`; poniżej zbiór kontrolny `holdout` (64 nagrania, inne ziarna).

| metryka (holdout) | oryginał JS | poprzedni C++ | C++ bez modelu | model gen 3 | **model gen 4** |
|---|---:|---:|---:|---:|---:|
| akord rozpoznany poprawnie (uderzenia) | 90,2 % | 96,3 % | 98,5 % | **98,8 %** | 98,5 % |
| akord poprawny w ramkach okna oceny | 87,0 % | 95,5 % | 97,4 % | **98,4 %** | 98,3 % |
| migotanie etykiety akordu (zmian/akord) | 0,48 | 0,13 | 0,09 | 0,03 | **0,02** |
| akord przy rozstrojonej gitarze (−35…+32¢) | 64,8 % | **100 %** | 98,1 % | 98,1 % | 98,1 % |
| nuty (F1 obecności dźwięku w ramkach) | 74,2 % | 81,0 % | 81,6 % | 91,6 % | **92,1 %** |
| nuty (F1 obecności z listy nut) | | 81,5 % | 82,4 % | 91,6 % | **92,0 %** |
| początki nut (F1, tol. 120 ms) | 70,0 % | 79,5 % | 80,5 % | 86,7 % | **87,6 %** |
| początki nut (F1, tol. 50 ms, jak w publikacjach) | | 54,0 % | 73,5 % | 78,7 % | **79,6 %** |
| pokrycie słyszalnego czasu nuty | 64,8 % | 74,3 % | 75,7 % | 89,9 % | **90,2 %** |
| stroik: trafiony dźwięk (melodie) | 90,5 % | 97,6 % | 96,9 % | **98,5 %** | **98,5 %** |
| stroik: mediana błędu częstotliwości | 0,72¢ | 0,30¢ | 0,30¢ | 0,30¢ | 0,30¢ |
| czas analizy / czas nagrania (WebAssembly w node) | | 0,03 | | | 0,05 |

Model działa przy analizie nagrania (plik, demo i ponowna analiza po zatrzymaniu mikrofonu). Na żywo z mikrofonu zostaje
dotychczasowy detektor: z modelem akordy na żywo spadały (95,4 → 88,9 %, model uczony na analizie plików).

Nuta "brzmi" w miarach od 0,12 s po uderzeniu do końca słyszalności (spadek dominującego alikwotu o 40 dB) albo zwolnienia struny.
Wcześniejsza wersja miary liczyła tylko pierwsze 1,2 s i karała poprawnie podtrzymane nuty; liczby w tabeli są z poprawionej miary dla obu silników.

Opóźnienie pierwszego poprawnego akordu nie jest już w tabeli: w analizie pliku akordy powstają z gotowej listy nut i są
wyrównane w czasie do uderzeń, więc ta liczba przestała mierzyć to samo co dawniej. Analiza jest ok. 3× wolniejsza niż w poprzedniej
wersji (dokładne początki nut liczone osobno dla każdej nuty), nadal kilkanaście razy szybciej niż czas rzeczywisty.

### Prawdziwe nagrania: GuitarSet

Korpus syntetyczny pokazuje różnice między wersjami, ale nie dokładność na prawdziwej gitarze. Dlatego silnik jest też mierzony na
**GuitarSet** (Xi i in., ISMIR 2018: 360 nagrań gitary akustycznej z mikrofonu, 6 gitarzystów, nuty z przetwornika heksafonicznego,
akordy z partytury), skryptem `tools/guitarset_eval.py` z metrykami **mir_eval** (te same co w publikacjach). Strojone na graczach
00–02, poniżej gracze 03–05:

| GuitarSet, gracze 03–05 | poprzedni C++ | C++ bez modelu | model gen 3 | **model gen 4** | bez modelu, okno 186 ms |
|---|---:|---:|---:|---:|---:|
| nuty, F1 początków (50 ms, ±50¢), wszystkie nagrania | 47,7 % | 56,2 % | 61,7 % | **62,5 %** | 57,8 % |
| … precyzja / czułość | 66,5 / 39,8 % | 73,4 / 48,7 % | 80,5 / 52,4 % | **81,0 / 53,2 %** | 75,7 / 50,0 % |
| nuty z początkiem i końcem | 22,7 % | 24,9 % | 26,6 % | 26,9 % | **28,3 %** |
| obecność nut w siatce 50 ms | 63,3 % | 64,1 % | 70,6 % | **71,5 %** | 65,9 % |
| nuty, melodie (solo) | 61,1 % | 69,4 % | 72,9 % | **73,0 %** | 71,0 % |
| nuty, akompaniament | 34,3 % | 42,9 % | 50,6 % | **52,1 %** | 44,6 % |
| akompaniament: prima akordu | 40,4 % | 45,7 % | 49,2 % | **50,0 %** | 45,7 % |
| akompaniament: akord dur/moll (mir_eval majmin) | 34,0 % | 42,3 % | 46,6 % | **48,2 %** | 42,8 % |

(Kolumna „bez modelu” zawiera już odszumianie; liczby bez modelu różnią się od poprzedniej wersji tego README o ±0,3 pkt.)

### Generacja 6 (dane): muzyka klasyczna z MIDI na wielu instrumentach i w wielu miejscach

Dane do uczenia większego modelu. Zamiast losowych nut (środowiska gen 4) prawdziwa muzyka: tysiące partytur klasycznych jako MIDI,
każda w kilku wersjach, grana na wielu instrumentach i nagrywana w wielu miejscach. Wszystko powstaje jednym poleceniem
`tools/gen6/make_gen6.sh` (korpus → nagrania → zrzuty HCQT), format jest ten sam co w gen 4/5, więc `train_gen5.py` czyta go bez zmian.

* **Korpus** (`tools/gen6/fetch_classical.py`, spis utworów i podział: `data/gen6/manifest.csv`): **3236 utworów, 282 h muzyki,
  8,2 mln nut**. MAESTRO v3 (1276 wykonań fortepianowych z konkursu Piano-e-Competition: Chopin, Schubert, Beethoven, Bach, Liszt,
  Rachmaninow, Schumann, Debussy, Haydn, Mozart, Skriabin, Scarlatti, Brahms, …; licencja CC BY-NC-SA 4.0) oraz partytury z korpusu
  music21 (1960: msze Palestriny, chorały i inne utwory Bacha, madrygały Monteverdiego, trecento, Josquin, kwartety Beethovena, Mozarta
  i Haydna, Händel, Corelli, Schumannowie, …; każda partia osobną ścieżką MIDI). Podział train / validation / test po utworach
  (MAESTRO: własny podział; music21: skrót ścieżki 90/5/5 %), więc wersje jednego utworu nie trafiają do dwóch zbiorów.
* **Wersje utworu** (`tools/gen_classical.cpp`, domyślnie 4 na utwór): oryginał, **odwrócenie** („do góry nogami”: wysokości odbite
  wokół środka skali utworu, zakres bez zmian), **rak** (od końca; początki w odwróconej kolejności, długość brzmienia z pedałem zostaje),
  **rak odwrócenia**; każda wersja losuje modyfikatory: transpozycja −7…+7 (od 5. wersji zawsze), tempo ×0,6–1,6, artykulacja od staccato
  do legato, humanizacja czasu (do 25 ms) i dynamiki, usunięcie jednego głosu, przeniesienie głosu o oktawę. Każda wersja zapisywana też
  jako MIDI (`<zbiór>/midi/<utwór>_v<k>.mid`).
* **Fragmenty i obsada**: z każdej wersji 2 losowe fragmenty po 10–20 s. Obsada: solo (połowa nagrań), zespół (każdy głos inny
  instrument) albo gitara + zespół. **27 instrumentów**: gitara klasyczna (syntezator silnika), stalowa, elektryczna, ukulele,
  mandolina, lutnia, harfa, klawesyn, fortepian, dzwonki, marimba, wibrafon, organy, skrzypce, altówka, wiolonczela, kontrabas, pizzicato,
  flet, klarnet, obój, fagot, waltornia, trąbka, chór, syntezator, akordeon (`tools/gt_instruments.hpp`: rozkład alikwotów, nieharmoniczność,
  kilka strun na nutę, sztabki o nieharmonicznych proporcjach, wibrato, tremolo, szum ataku i oddechu, pudło i formanty; barwa losowana
  od nowa w każdym nagraniu). Rodzina gitar ma ok. 35 % obsady (`--guitar`). Nuty spoza zakresu instrumentu i modelu (MIDI 36–88)
  przenoszone o oktawy; strój zespołu A = 440 ± 30 centów.
* **Miejsca** (11): studio, pokój, salon, sala koncertowa (publiczność), kościół (pogłos 2,5–6 s), plener (wiatr, ptaki), telefon
  (pasmo 300–3400 Hz, kompresja, przester), dyktafon/kaseta (szum, kołysanie wysokości), płyta winylowa (trzaski), transmisja
  internetowa (kompresja), próba w domu (pełne otoczenie gen 4). Do tego kąt mikrofonu i, zależnie od miejsca, otoczenie gen 4 (szumy, tony,
  brum, stuki, kliknięcia, rozmowa; wspólny kod w `tools/gt_envfx.hpp`), czasem przester albo kompresor; poziom nagrania −30…−1 dBFS.
* **Prawda** (`<id>.truth.json`): nuty jak dotąd (`midi`, `t0`, `t1`, `ta` = koniec słyszalności, `f`) plus instrument (`i`) i głos (`v`),
  opis wersji, obsady i miejsca; `index.csv` ma jeden wiersz na nagranie. `--clean` zapisuje też same instrumenty bez otoczenia (do maski).

Pełny zbiór (4 wersje × 2 fragmenty): ok. 26 tys. nagrań, ok. 115 h dźwięku (20 razy więcej niż środowiska gen 4), ok. 1 s procesora
na nagranie (2,5 min na 480 nagrań na 4 rdzeniach); .wav ok. 0,7 MB, zrzut HCQT ok. 2 MB na nagranie. `VERSIONS=8` daje każdą formę
dwa razy (inne transpozycje i tempo). `train_gen5.py --lazy` czyta zrzuty z dysku (memmap) zamiast trzymać je w pamięci, a walidację
dzieli po utworze (pole `piece`).

Punkt odniesienia: obecny silnik (gen 5) na próbie zbioru walidacyjnego gen 6 (60 utworów, 480 nagrań, 2,2 h, 60 tys. nut; utwory
spoza uczenia). Silnik uczony tylko na gitarze radzi sobie najgorzej tam, gdzie gen 6 dokłada najwięcej nowego: sztabki
(nieharmoniczne alikwoty), smyczki i chór (wibrato, miękki atak), kościół (długi pogłos).

| próba walidacyjna gen 6 (gen 5 bez douczenia) | nagrań | nuty F1 (klatki) | początki F1 (50 ms) |
|---|---:|---:|---:|
| wszystkie | 480 | 62,4 % | 51,9 % |
| solo: gitara klasyczna / inne gitary | 73 / 29 | 63,6 / 65,2 % | 63,4 / 62,5 % |
| solo: inne szarpane (mandolina, lutnia, harfa, klawesyn, pizzicato) | 41 | 60,5 % | 63,2 % |
| solo: dęte / smyczki / chór | 44 / 37 / 13 | 69,8 / 63,4 / 61,4 % | 50,4 / 32,1 / 22,8 % |
| solo: fortepian / sztabki (dzwonki, marimba, wibrafon) | 7 / 21 | 51,2 / 33,8 % | 44,7 / 17,4 % |
| zespół / gitara + zespół | 131 / 57 | 62,7 / 61,8 % | 52,0 / 55,6 % |
| oryginał / odwrócenie / rak / rak odwrócenia | po 120 | 64,3 / 60,0 / 64,6 / 60,8 % | 55,2 / 49,9 / 54,3 / 48,4 % |
| miejsce: najlepsze (plener, pokój, telefon) | 139 | 65,0–66,0 % | 46,6–57,8 % |
| miejsce: kościół | 52 | 54,7 % | 32,0 % |

Dla porównania nowe środowiska gen 4 (sama gitara): nuty 79,8 %, początki 83,4 %. Dane gen 6 nie są jeszcze użyte do uczenia;
to następny krok (`train_gen5.py --lazy --hidden 32 …`, większa sieć ma teraz ok. 20 razy więcej danych).

### Generacja 5: sieć na widmie z uwagą

Zamiast poprawiać decyzje klasycznego detektora (generacje 3–4: 32–44 ręcznie liczone cechy), generacja 5 uczy się wprost z widma, jak
współczesne modele transkrypcji (Onsets and Frames, Hawthorne i in. 2018; Basic Pitch, Bittner i in. 2022).

* **Wejście** (`src/gt_hcqt.hpp`): harmonicznie ułożone widmo (HCQT, Bittner i in. 2017) całego nagrania: 159 wysokości co 1/3 półtonu
  (MIDI 36–88), klatki co 46 ms wyrównane z ramkami silnika, 9 kanałów: alikwoty 0,5×, 1×, 2×…5× z okna 372 ms i 1×–3× z okna 93 ms;
  dB względem 99,5. percentyla nagrania (niezależne od poziomu).
* **Sieć** (`src/gt_gen5.hpp`, wagi `src/gt_gen5model.hpp`, uczenie `tools/train_gen5.py`): 5 warstw konwolucji z połączeniami
  resztkowymi (alikwoty i sąsiednie wysokości, kontekst ±4 klatki, warstwa z dylatacją 36 binów = oktawa niżej i wyżej), potem
  **blok uwagi w czasie**: dla każdej wysokości klatka patrzy na ostatnią sekundę (22 klatki) tej samej wysokości, 2 głowy, wyuczona
  premia za odległość, feed-forward; na końcu 2 wyjścia na półton: p(brzmi), p(zaczyna się). 37 tys. parametrów.
* **Dekoder**: nuta zaczyna się w lokalnym maksimum p(zaczyna się) ≥ 0,5 (albo przy p(brzmi) ≥ 0,7 przez 2 klatki) i trwa, dopóki
  p(brzmi) ≥ 0,5; nowy początek w trakcie nuty to ponowne szarpnięcie. Potem jak dotąd: docinanie początków krótkim oknem, akordy z nut.
  Duplikaty (ta sama wysokość, początki bliżej niż 30 ms) są scalane.
* **Uczenie**: PyTorch na CPU, 16 epok × 500 kroków (wycinki po 96 klatek), ok. 35 min dla samej konwolucji i 70 min z uwagą; dane jak
  w gen 4 (środowiska, korpusy, GuitarSet 00–02; walidacja: funk gracza 02), wagi źródeł GuitarSet 0,5, reszta po 0,25. Zapis stanu
  po każdej epoce (`--resume`). Inferencja w C++ zgodna z PyTorch do 1e-6.

| zbiory kontrolne | gen 4 | gen 5, sama konwolucja | **gen 5 z uwagą** |
|---|---:|---:|---:|
| GuitarSet 03–05: nuty F1 (50 ms) | 62,5 % | 78,5 % | **79,5 %** |
| … precyzja / czułość | 81,0 / 53,2 % | 81,3 / 77,3 % | **82,0 / 78,2 %** |
| GuitarSet: nuty z początkiem i końcem | 26,9 % | 40,3 % | **40,9 %** |
| GuitarSet: akompaniament / melodie | 52,1 / 73,0 % | 73,8 / 83,3 % | **75,6 / 83,4 %** |
| GuitarSet, akompaniament: prima / dur-moll | 50,0 / 48,2 % | 53,8 / 58,4 % | **54,6 / 59,1 %** |
| nowe środowiska: nuty / początki | 70,9 / 60,6 % | 76,6 / 81,2 % | **79,8 / 83,4 %** |
| korpus kontrolny: akordy / nuty | 98,5 / 92,1 % | 99,7 / 93,9 % | **100 / 95,1 %** |
| korpus: początki nut (50 ms) | 79,6 % | 87,5 % | **87,5 %** |
| czas analizy / czas nagrania (WebAssembly w node) | 0,05 | | 0,15–0,17 |

Gen 5 działa przy analizie nagrania (plik, demo, ponowna analiza po zatrzymaniu mikrofonu); na żywo zostaje klasyczny detektor.
Wykresy uczenia i porównanie generacji: artefakt „Gitara Słuchacz: pomiary”.

### Generacja 6: architektura (bez wag)

Nowa architektura pod nowe dane, w `tools/gen6/` (opis: [`docs/GEN6.md`](docs/GEN6.md)). Ten etap obejmuje tylko kod: modelu jeszcze nie uczono, a silnik nadal używa gen 5.
* dane w dowolnym formacie są sprowadzane do jednego zapisu; adaptery: manifest JSONL, GuitarSet/JAMS, CSV/TSV, MIDI, korpusy, zrzuty silnika; maski etykiet, których źródło nie ma;
* cechy co 23 ms (gen 5: 46 ms), dokładna zmiana próbkowania (gen 5 przy 48 kHz liczyła cechy przy 12 kHz);
* sieć: bloki harmonicznych konwolucji, uwaga w czasie w obie strony i uwaga między wysokościami, 5 głowic (początek, brzmi, koniec, głośność, tabulatura);
* jeden moduł ewaluacji dla wszystkich generacji (także dla JSON silnika C++): nuty, klatki, mapy, podtrzymanie, akordy, tabulatura, stroik, bootstrap; zgodny z mir_eval (testy).

### Generacja 4: losowe środowiska, model maski i model nut

**Środowiska** (`tools/gen_env.cpp`). Każde nagranie losuje wszystko od nowa, żeby model nie mógł nauczyć się jednego szumu ani
jednego utworu: treść (uderzenia w losowe chwyty możliwe do zagrania, także stłumione i niepełne; arpeggia o losowym wzorze,
tempie i wybrzmiewaniu, czasem dwie struny naraz; losowe nuty z procesu Poissona do 4 naraz; melodie legato i staccato),
dynamikę (poziom bazowy, crescendo/decrescendo, akcenty, bardzo ciche nuty), pokój (pogłos 0,15–1,6 s), „kąt mikrofonu” (1–4 losowe
filtry, wczesne odbicie jako filtr grzebieniowy, nachylenie widma) oraz otoczenie: szum o losowej barwie (od brązowego do niebieskiego,
czasem falujący), 1–5 stałych tonów z harmonicznymi (wentylator, silnik), brum 50/60 Hz, stuki (wygasające rezonanse o losowej
wysokości, każdy z innego kierunku, od −36 do +4 dB względem szczytu gitary), kliknięcia, hałas przerywany w rytmie mowy; SNR 3–45 dB,
poziom nagrania od −32 do −1 dBFS. Zapisuje osobno mikrofon i samą gitarę (do uczenia maski). Uczenie: 240 nagrań, test: 60 innych ziaren.

| nowe środowiska (60 nagrań testowych) | bez modelu | model gen 3 | **model gen 4** |
|---|---:|---:|---:|
| nuty (F1 obecności w ramkach) | 64,2 % | 68,9 % | **70,9 %** |
| nuty (F1 z listy nut) | 64,3 % | 68,6 % | **70,3 %** |
| początki nut (120 ms / 50 ms) | 54,9 / 50,3 % | 58,6 / 53,8 % | **60,6 / 55,9 %** |
| pokrycie słyszalnego czasu nuty | 46,3 % | 52,1 % | **53,1 %** |

**Model maski** (`src/gt_mask.hpp`, wagi `src/gt_maskmodel.hpp`, uczenie `tools/train_mask.py`). Widmo w 156 pasmach co pół półtonu
(55 Hz – 5 kHz); dla każdego pasma 15 cech (energia, kontrast z sąsiednimi pasmami, dwie poprzednie klatki, szum lokalny i szum tła,
pasma o oktawę i duodecymę obok, czy jest pik) i sieć 15 → 24 → 12 → 1, która przewiduje, jaka część energii pasma to gitara
(etykieta: idealna maska z osobno zapisanej gitary i otoczenia). Na 60 nagraniach testowych: zgodność decyzji gitara/otoczenie 84,8 %,
usuwa 77 % pasm zdominowanych przez otoczenie i 4,8 % pasm gitary. Użycie: (1) piki w pasmach z maską < 0,3 odpadają, (2) model nut
dostaje maskę na 6 pierwszych alikwotach kandydata, jej średnią i jej narastanie względem poprzedniej klatki (dowód początku nuty).
Samo czyszczenie pików nie zmienia wyników (±0,1 pkt: usuwane piki i tak nie wpływały na decyzje); zysk daje maska jako dowód dla modelu
nut: bez cech z maski gen 4 ma w środowiskach −0,5 pkt i w akompaniamencie GuitarSet −0,7 pkt (w melodiach +0,5 pkt).

**Model nut gen 4** (`src/gt_model.hpp`). 44 cechy (32 jak w gen 3 + maska + dwie poprzednie klatki, zmiana siły, liczba alikwotów),
trzy sieci 44 → 64 → 32 → 1 z różnych ziaren i sieć gen 3 (na 32 pierwszych cechach); wynik = 0,4 · gen 3 + 0,6 · średnia gen 4, próg 0,40.
Dane: środowiska (240), korpusy `dev`, 10000, 15000 i GuitarSet 00–02 (walidacja: funk gracza 02); wagi źródeł: GuitarSet 0,5,
korpus 0,25, środowiska 0,25. Uczenie ok. 2 min na CPU.
Kolejne wersje (zbiory kontrolne): 4a (jedna sieć, źródła po równo): środowiska i akompaniament lepsze od gen 3, ale melodie GuitarSet
72,9 → 71,5 % i akordy korpusu 98,8 → 97,5 %; 4b (zespół 3 sieci, GuitarSet 0,5): melodie 71,8 %; 4c (więcej GuitarSet do uczenia,
próg 0,40): 72,1 %; 4c + pewność nut w akordach: akordy korpusu 97,5 → 97,9 %; zespół z gen 3 (25 %, potem 40 %): melodie 73,0 %,
akordy korpusu 98,5 %. Gen 4 jest lepsza od gen 3 we wszystkich miarach GuitarSet i środowisk; na korpusie kontrolnym akordy
98,5 vs 98,8 % (jedno uderzenie na 325).
**Pewność nut w akordach**: każda nuta pamięta średnie prawdopodobieństwo modelu ze swoich klatek; przy składaniu akordu waży
pewność². Maska i model działają przy analizie nagrania; na żywo maska (uczona z widmem szumu z całego nagrania) psuła akordy (95 → 36 %).

### Model (AI) i odszumianie (generacja 3)

**Model** (`src/gt_model.hpp`, uczony skryptem `tools/train_model.py`). Detektor zachłanny zostaje, ale nie decyduje sam: dla każdej
wysokości, która ma w klatce co najmniej 2 z 6 pierwszych alikwotów, liczone są 32 cechy (siła 10 alikwotów, czy wyjaśniają je
inne wybrane nuty, decyzja detektora i nuty o oktawę, kwintę i duodecymę obok, poprzednia klatka, uderzenie, poziom sygnału),
a sieć 32 → 32 → 16 → 1 (ReLU, sigmoid, 1 601 wag) zwraca prawdopodobieństwo, że to prawdziwa nuta. Zostają wysokości z p ≥ 0,45.
Dane uczące: zrzuty cech z silnika (`GT_DUMP=plik.bin gt_cli analyze ...`) z korpusu `dev` i dwóch dodatkowych korpusów o innych
ziarnach (10000, 15000; nie `holdout`) oraz z GuitarSet, graczy 00–02 (gracz 02 jako walidacja). Etykieta: czy ta wysokość brzmi
według prawdy; klatki przy samej granicy nuty są pomijane. Uczenie trwa ok. 30 s na CPU (numpy), bez GPU.
Na walidacji (klatki, kandydaci): korpus F1 0,787 → 0,949, GuitarSet 0,754 → 0,835 względem samego detektora zachłannego.
Nuta dodana przez model, będąca oktawą innej wybranej nuty, jest oznaczana jak podwojenie oktawowe (stroik ją pomija).
Sprawdzone wersje modelu: (1) tylko korpus `dev` + GuitarSet: dobre nuty, ale w melodiach z szumem dokładał oktawy (stroik 89,5 %);
(2) + dodatkowe korpusy + zrzuty z trybu na żywo: stroik naprawiony, akordy −1,2 pkt; (3) bez zrzutów na żywo: najlepsza, ta w kodzie.
Dane GuitarSet: Xi i in., ISMIR 2018, licencja CC BY 4.0 (https://zenodo.org/records/3371780); wagi modelu powstały częściowo z tych danych.

**Odszumianie z wielu klatek** (`denoise`). W przed-przebiegu analizy pliku dla każdego binu widma zbierany jest histogram amplitud
ze wszystkich klatek nagrania (także cichych); 15. percentyl to widmo szumu tła. Pik liczy się tylko, gdy jest ≥ 3× (ok. 10 dB) ponad nim.
Lokalny próg w klatce (4,5× średniej z ±100 Hz) i tak usuwa szum szerokopasmowy, więc zysk widać przy szumie tonalnym (wentylator,
piszczący zasilacz, buczenie poza 50/60 Hz). Test: 18 nagrań z korpusu z dodanymi 4 stałymi tonami: akordy 90,1 → 91,6 %, początki nut
w melodiach 90,2 → 97,4 %, stroik 94,4 → 98,5 %; na czystym korpusie i GuitarSet ±0,2 pkt. Na żywo wyłączone: statystyka minimów
(Martin 2001) uznawała długo brzmiące struny za szum (akordy na żywo 95,4 → 81,2 %), a szum z klatek ciszy obejmował ogony strun (stroik 96,8 → 91,8 %).

Wnioski: (1) na prawdziwych nagraniach nuty są dużo trudniejsze niż w korpusie: wykrywana jest mniej więcej połowa nut, a w akompaniamencie
jedna trzecia (szybkie, tłumione uderzenia, krótkie nuty). Nuty krótsze niż 0,2 s to większość nut w melodiach i z nich trafiamy 26–40 %.
(2) Krótsze okno (186 ms, w ustawieniach „Szybkie melodie”) daje lepsze nuty na GuitarSet, ale na korpusie syntetycznym akordy spadają
(98,5 → 93,9 %, na żywo 95,4 → 92,6 %), a fałszywych dźwięków w akordach jest prawie 2× więcej, dlatego domyślne zostaje 372 ms.
(3) Akordy w jazzie, funku i bossa novie (septymy, nony, często bez prymy) są rozpoznawane słabo (prima 18–28 %); rock i singer-songwriter 70–74 %.

**Ostatnia runda: metody z `docs/BADANIA.md`** (efekty na zbiorach kontrolnych):

| zmiana | efekt |
|---|---|
| **akordy z listy nut** (`chordsFromNotes`): uderzenia = grupy początków nut, nowe nuty w uderzeniu albo (arpeggio) także nuty brzmiące wcześniej, z wagą malejącą w czasie; spóźnione struny do 0,6 s dopełniają akord; nuty pasujące do akordu go nie zmieniają; wysokości widoczne w ramkach, ale niepotwierdzone jako nuty, dokładają słaby dowód (0,6) | korpus: akordy 96,3 → 98,5 %, ramki 95,5 → 97,5 %; GuitarSet (akompaniament): prima 40,4 → 45,7 %, dur/moll 34,0 → 41,9 %. Bez słabego dowodu z ramek prima na GuitarSet była gorsza od dawnej metody (48,7 vs 50,2 % na graczach 00–02), z nim 54,8 % |
| **początek nuty liczony na wysokość** (`refineEvents`): energia każdego alikwotu osobno, okno 93 ms co 11,6 ms; alikwot nie świadczy w chwili, w której zaczyna się inna nuta, która go dzieli | korpus: początki w tolerancji 50 ms 54 → 74 %; w uderzeniu każda struna ma własny czas (mediana błędu początku 31 → 14 ms, zbiór roboczy) |
| **ponowne szarpnięcie tej samej struny** dzielone na dwie nuty (skok ≥ 8 dB w alikwotach niewspólnych z nutami zaczynającymi się w tej chwili) | korpus, arpeggio: F1 początków 53 → 58 %; pokrycie nut +1 pkt. Wcześniejsza próba (README niżej) odrzucona, bo brała pod uwagę wszystkie wspólne alikwoty |
| **model miejsca szarpnięcia w teście oktaw** (Traube i Smith): \|sin(π h p)\| dopasowane do nieparzystych alikwotów przewiduje parzyste | korpus, melodie: F1 początków 95,6 → 98,2 % (zbiór roboczy), mniej fałszywych oktaw nad pojedynczą struną |
| **ocena łączna zbioru nut**: usuwanie nut, których alikwoty w całości wyjaśniają inne (poza podwojeniami oktawowymi) | mały zysk (F1 nut +0,1 pkt na zbiorze roboczym) |
| **nieharmoniczność mierzona dla każdej wysokości**, potem węższe dopasowanie alikwotów | na korpusie bez efektu do oceny: syntezator losuje nieharmoniczność dla każdej nuty osobno, a w gitarze jest stała dla struny. Kontrolny: nuty +0,1 pkt, stroik −0,6 pkt |
| przy analizie pliku nuty w ramkach i dowód akordu tylko z nut potwierdzonych przez tracker | korpus: F1 nut w ramkach +0,6 pkt |

**Sprawdzone w tej rundzie i odrzucone**: zamiana poduktawy na oktawę wyżej w ocenie łącznej (duchy −25 %, ale gubi prawdziwy bas,
bo słaby ton podstawowy niskiej struny wygląda tak samo jak duch; zostawiona w kodzie, wyłączona: `jointSwap`), dwa okna naraz
(piki poniżej 400 Hz z okna 372 ms, powyżej z 186 ms; bez zysku na GuitarSet, zysk krótkiego okna bierze się z rozdzielczości czasu
całego potoku), akord na żywo tylko z nut potwierdzonych przez tracker (na żywo akordy −0,9 pkt, większe opóźnienie i migotanie;
dostępne jako `liveNotes`), okno 186 ms jako domyślne (patrz wyżej). Sieć neuronowa (Basic Pitch i podobne) nie jest dodana: wymaga
dołączenia wag modelu i osobnego środowiska uruchomieniowego, to osobna decyzja.

**Kontekst czasowy: poprzednie i następne chwile** (sprawdzone, w pomiarze bez zysku, domyślnie wyłączone). Silnik już korzysta z historii:
nuta musi być widoczna przez 85 ms, przerwy do 130 ms są mostkowane, nuta, która brzmiała, jest szukana dalej z obniżonym progiem
(podtrzymanie), ręka nie skacze szybciej, niż zdąży, a akord dopełniają spóźnione struny. Dodatkowo sprawdzone (zbiór roboczy korpusu
i GuitarSet, gracze 00–02):

| mechanizm | parametr | wynik |
|---|---|---|
| dopowiadanie nut z sąsiednich uderzeń (±4 s): wysokość grana obok, a tu niewykryta, jeśli po uderzeniu ma ≥ 4 własne alikwoty ponad szumem i nie brzmiała tuż przed nim | `context`, `ctxFill` | korpus: 17 trafnych i 12 błędnych dodanych nut (akordy −0,3 pkt); GuitarSet: prawie nic nie dodaje. Pierwsza wersja (dowodem był atak w alikwotach) dodawała 655 błędnych nut na 7 trafnych: szum uderzenia podnosi wszystkie alikwoty naraz |
| sklejanie przerwanej nuty bez nowego ataku | `ctxMerge` | GuitarSet: F1 nut −1 pkt (skleja ponowne uderzenia tego samego akordu) |
| usuwanie krótkich nut bez ataku | `ctxPrune` | bez wpływu (±0,03 pkt) |
| premia w detektorze dla wysokości słyszanych w ostatnich 3 s (działa też na żywo) | `prior` 1,3 / 1,6 | korpus: akordy 96,8 → 95,9 / 94,5 %; GuitarSet: nuty w akompaniamencie 35,5 → 34,5 %. System trzyma się starego akordu, gdy gracz zmienia chwyt |
| dłuższe mostkowanie przerw | `release` 0,22 s | zbiory kontrolne: wynik mieszany (korpus: akordy −0,6, nuty +0,4 pkt; GuitarSet: akordy +0,7, nuty z końcem −0,5 pkt), zostaje 0,13 s |

Wniosek: tam, gdzie nuta istnieje w widmie, historia jest już wykorzystana; brakujące nuty na prawdziwych nagraniach to głównie krótkie
nuty rozmyte przez długie okno i ciche struny w akompaniamencie, których historia nie podpowiada.

**Co poprawiło dokładność w poprzedniej rundzie** (zbiór kontrolny, względem wersji wcześniejszej):

| zmiana | efekt |
|---|---|
| kontekstowy próg oktaw: w akordzie 1,4, przy pojedynczej nucie 2,2 | F1 nut 80,0 → 80,9 %, czułość nut w uderzeniach 71 → 74 %, pokrycie ogona +3 pkt, melodie bez zmian |
| docinanie granic krótkim oknem (energia w alikwotach znanej nuty, 93 ms) | początek przesuwany przy wyraźnej pomyłce, koniec do ostrego spadku; mediana błędu końca nuty w melodiach +0,185 → +0,075 s |
| historia uderzeń w trackerze (ostatnie uderzenie sprzed pierwszego wykrycia) | w arpeggio nuta nie dostaje już czasu następnej struny; F1 początków +1,4 pkt łącznie z docinaniem |
| nuty "świeże" (niebrzmiące przed uderzeniem) liczą się do akordu od pierwszej ramki | akordy 95,7 → 96,3 % razem z progiem oktaw |

**Sprawdzone i odrzucone** (gorsze albo bez efektu w pomiarze): kasowanie z gładkością widma (Klapuri) zamiast binarnego "wyjaśnione"
(na pojedynczych ramkach znajduje oktawy, ale w całym potoku akordy −3…−5 pkt i początki nut −6…−8 pkt), słabi kandydaci jako dowód akordu,
dzielenie nut na ponowne szarpnięcia po skoku energii (fałszywe podziały, gdy inna struna o wspólnych alikwotach zaczyna brzmieć),
obecność nut w ramkach brana z dociętych zdarzeń.

**Podtrzymanie nut** (`addSustained` w `src/gt_engine.hpp`). Nuta, która już brzmi, a w danej ramce nie przechodzi zwykłych progów, jest
sprawdzana jeszcze raz w widmie z obniżonym progiem szumu (2,0 zamiast 4,5), tylko w miejscach jej alikwotów. Próg rośnie z czasem od ostatniego mocnego
wykrycia (po 4 s zaczyna wracać do zwykłego, po 14 s koniec). Dowodem są alikwoty niezależne (1 pkt) albo wspólne z nutą **niższą** (0,5 pkt, typowa wyższa oktawa);
alikwoty wspólne z nutą wyższą nie liczą się wcale, żeby poduktawa nie podtrzymywała się na energii wyższej nuty. Po nowym uderzeniu stara nuta bez potwierdzenia
przeżywa tylko na własnych alikwotach, a w oknie tuż po uderzeniu nuty podtrzymane nie są dowodem dla akordu. Poziomy w ustawieniach: wyłączone, normalne, mocne.
Do tego koniec nuty to ostatnie wykrycie minus 0,25 okna (było 0,5), bo okno analizy wygładza koniec, ale nie aż tak mocno dla nut zanikających.

Miara `cov` w `tools/score.py`: jaką część słyszalnego czasu nuty (do spadku dominującego alikwotu o 40 dB albo do zwolnienia struny) pokrywają wykryte nuty
tej wysokości. Poprzednia wersja silnika miała 61,7 % (gorzej od oryginału), po zmianie 71,4 %, a nuty pokryte w co najmniej 80 % to 52,1 → 60,9 % (mocne: 67,1 %).
Koszt: akordy w ramkach 95,9 → 95,1 %, a fałszywych dźwięków przybywa (2,0 → 2,7 % ramek) przy 15 % więcej prawdziwych ramek nut. Ok. 15 % nut z długim ogonem
to podwojenia oktawowe, których silnik w ogóle nie wykrywa (osobny problem).

Śledzenie ręki osobno (`tools/ghost.py`, zbiór kontrolny z wcześniejszej generacji, uderzenia, przed dodaniem podtrzymania): fałszywe dźwięki w ramkach (wysokość, której nie ma w granym chwycie)
**966 → 776 (−20 %)**, segmenty z duchem 128 → 102, różne wysokości-duchy 161 → 124, kosztem 0,1 % prawdziwych ramek. Pozostałe duchy
to głównie **poduktawy zagranych nut** (np. E2 zamiast E3), które da się fizycznie zagrać na sąsiedniej strunie, więc reguły ręki ich nie wykluczą.
Próba odrzucania poduktaw po braku nieparzystych alikwotów nie zadziałała (usunięta), bo w akordzie te alikwoty pokrywają się z innymi nutami.

Gorzej niż w pierwowzorze jest na czystych, jednogłosowych melodiach (F1 początków 97,4 → 93,9 %): detektor oktaw
czasem dokłada fałszywą oktawę do pojedynczej struny.

**Ograniczenia pomiaru.** Korpus jest syntetyczny, a nie nagraniem prawdziwej gitary. Liczby pokazują różnicę między silnikami
na identycznych danych, nie dokładność na żywym instrumencie. Nuty (F1) pozostają niskie, bo wiele strun w akordzie to podwojenia
oktawowe lub struny wybrzmiewające szybciej niż okno analizy.

## Testy

```bash
node tools/wasm_run.js nagranie.wav wynik.json     # silnik z pliku .wasm w node (te same metryki co natywnie)
node tools/test_exports.js nagranie.wav katalog    # eksporty: ZIP, WAV, MIDI, tabulatura, JSON
node tools/ui_test.js katalog nagranie.wav         # Chromium (Playwright): demo, odtwarzanie, pobieranie, plik, mikrofon, tryb artefaktu
# prawdziwe nagrania: GuitarSet (https://zenodo.org/records/3371780, annotation.zip + audio_mono-mic.zip), pip install mir_eval
for f in mic/*.wav; do ./gt_cli analyze $f wyniki/$(basename $f _mic.wav).json; done
python3 tools/guitarset_eval.py annotation wyniki --by-style
# ponowne uczenie modelu (zrzuty cech + prawda; szczegóły w nagłówku tools/train_model.py)
for f in korpus/*.wav; do GT_DUMP=zrzuty/$(basename $f .wav).bin ./gt_cli analyze $f /dev/null; done
python3 tools/train_model.py --syn zrzuty korpus --gs zrzuty_gs annotation --out src/gt_model.hpp
# gen 4: środowiska, maska i model nut
g++ -std=c++17 -O2 tools/gen_env.cpp -o gen_env && ./gen_env env_train 100000 240 && ./gen_env env_test 900000 60
for f in env_train/env_*[0-9].wav; do GT_DUMPM=zrzuty_maski/$(basename $f .wav).bin ./gt_cli analyze $f /dev/null; done
# gen 5: zrzut wejścia HCQT i uczenie (PyTorch)
for f in env_train/env_*[0-9].wav; do GT_DUMPH=hcqt/env/$(basename $f .wav).bin ./gt_cli analyze $f /dev/null; done
python3 tools/train_gen5.py --src środowiska hcqt/env env_train 0.25 --src korpus hcqt/syn prawda 0.25 --src GuitarSet hcqt/gs annotation 0.5 --attn --resume
python3 tools/train_mask.py --train env_train zrzuty_maski --test env_test zrzuty_maski_test
python3 tools/train_model.py --env zrzuty_env env_train --syn ... --gs ... --ensemble 3 --weights "korpus=0.25,środowiska=0.25,GuitarSet=0.5"
# gen 6: korpus klasyczny MIDI, nagrania (train/validation/test) i zrzuty HCQT; próba: LIMIT=20 tools/gen6/make_gen6.sh gen6_proba
tools/gen6/make_gen6.sh gen6
./build/gen_classical x x x --list                 # instrumenty i miejsca; --inst gitara_klasyczna,harfa --place kosciol zawęża
python3 tools/train_gen5.py --lazy --attn --src klasyka gen6/hcqt/train gen6/train 0.3 --src środowiska hcqt/env env_train 0.2 ...
```

## Układ kodu

| plik | zawartość |
|---|---|
| `src/gt_dsp.hpp` | FFT, decymator, bufor kołowy |
| `src/gt_spectrum.hpp` | widmo, piki, detektor uderzeń |
| `src/gt_pitch.hpp` | wielogłosowa detekcja wysokości, YIN |
| `src/gt_chords.hpp` | szablony i ocena akordów |
| `src/gt_tracker.hpp` | nuty w czasie |
| `src/gt_engine.hpp` | silnik: strumień → ramki, strój, próg, akordy, stroik |
| `src/gt_fingering.hpp` | struny i progi, ograniczenia fizyczne ręki |
| `src/gt_hand.hpp` | śledzenie ręki: filtr nut niemożliwych do zagrania, strefa ręki |
| `src/gt_hcqt.hpp`, `src/gt_gen5.hpp`, `src/gt_gen5model.hpp` | gen 5: wejście HCQT, sieć z uwagą i dekoder nut, wagi (z `tools/train_gen5.py`) |
| `src/gt_model.hpp` | wagi modelu nut gen 4 (generowane przez `tools/train_model.py`) |
| `src/gt_mask.hpp`, `src/gt_maskmodel.hpp` | model maski: ile w każdym paśmie jest gitary (wagi z `tools/train_mask.py`) |
| `tools/gen_env.cpp` | generator losowych środowisk (gitara + pokój + mikrofon + otoczenie, osobno sama gitara) |
| `tools/gt_envfx.hpp` | otoczenie wspólne dla generatorów: kąt mikrofonu, szumy, tony, brum, stuki, kliknięcia, rozmowa |
| `tools/gen_classical.cpp`, `tools/gt_instruments.hpp` | gen 6: MIDI → wersje utworu → 27 instrumentów → 11 miejsc nagrania |
| `tools/gen6/` | gen 6: pobranie i konwersja korpusu (`fetch_classical.py`), całość jednym poleceniem (`make_gen6.sh`) |
| `data/gen6/manifest.csv` | spis 3236 utworów korpusu gen 6 z podziałem train / validation / test |
| `src/gt_export.hpp` | MIDI, WAV, ZIP, tabulatura, JSON |
| `src/gt_synth.hpp` | syntezator szarpanej struny (odsłuch i korpus testowy) |
| `src/wasm_api.cpp` | interfejs C dla przeglądarki |
| `web/` | interfejs (HTML, CSS, JS) i skrypt składający plik |

## Dalsze kierunki

Przegląd metod i prac naukowych, które mogą poprawić wykrywanie dźwięków (z odniesieniami do kodu): [`docs/BADANIA.md`](docs/BADANIA.md).
