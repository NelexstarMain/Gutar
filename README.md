# Gitara Słuchacz (silnik C++17 → WebAssembly)

Rozpoznawanie nut, akordów i stroju gitary na żywo z mikrofonu albo z pliku audio.
Cała analiza dźwięku jest napisana w **C++17** (`src/`), kompilowana do **WebAssembly** i osadzona
w jednym pliku HTML. Ten plik działa jako artefakt i jako samodzielna aplikacja offline.

* `dist/gitara-sluchacz.html`: gotowa aplikacja (jeden plik, ok. 2 MB, mikrofon działa po otwarciu z dysku)
* `dist/gt_engine.wasm`: sam silnik (ok. 280 KB)

## Co potrafi

* wielogłosowe wykrywanie nut (grzebień alikwotów + kasowanie), z podwojeniami oktawowymi (E2+E3),
* akordy (20 typów, chwyty z basem, np. `C/G`), stroik z wskaźnikiem w centach i wskazaniem struny,
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

| metryka (holdout) | oryginał JS | nowy C++ |
|---|---:|---:|
| akord rozpoznany poprawnie (uderzenia) | 90,2 % | **96,3 %** |
| akord poprawny w ramkach okna oceny | 87,0 % | **95,5 %** |
| migotanie etykiety akordu (zmian/akord) | 0,48 | **0,13** |
| opóźnienie pierwszego poprawnego akordu | 0,54 s | **0,34 s** |
| akord przy rozstrojonej gitarze (−35…+32¢) | 64,8 % | **100 %** |
| nuty (F1 obecności dźwięku) | 74,2 % | **81,0 %** |
| początki nut (F1, tol. 120 ms) | 70,0 % | **79,5 %** |
| pokrycie słyszalnego czasu nuty | 64,8 % | **74,3 %** |
| stroik: trafiony dźwięk (melodie) | 90,5 % | **97,6 %** |
| stroik: mediana błędu częstotliwości | 0,72¢ | **0,30¢** |
| czas analizy / czas nagrania (natywnie; WebAssembly ok. 0,03) | 0,033 | **0,021** |

Nuta "brzmi" w miarach od 0,12 s po uderzeniu do końca słyszalności (spadek dominującego alikwotu o 40 dB) albo zwolnienia struny.
Wcześniejsza wersja miary liczyła tylko pierwsze 1,2 s i karała poprawnie podtrzymane nuty; liczby w tabeli są z poprawionej miary dla obu silników.

**Co poprawiło dokładność w ostatniej rundzie** (zbiór kontrolny, względem poprzedniej wersji):

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
| `src/gt_export.hpp` | MIDI, WAV, ZIP, tabulatura, JSON |
| `src/gt_synth.hpp` | syntezator szarpanej struny (odsłuch i korpus testowy) |
| `src/wasm_api.cpp` | interfejs C dla przeglądarki |
| `web/` | interfejs (HTML, CSS, JS) i skrypt składający plik |

## Dalsze kierunki

Przegląd metod i prac naukowych, które mogą poprawić wykrywanie dźwięków (z odniesieniami do kodu): [`docs/BADANIA.md`](docs/BADANIA.md).
