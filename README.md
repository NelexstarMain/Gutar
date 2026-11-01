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
| akord rozpoznany poprawnie (uderzenia) | 90,2 % | **96,0 %** |
| akord poprawny w ramkach okna oceny | 87,0 % | **95,9 %** |
| migotanie etykiety akordu (zmian/akord) | 0,48 | **0,09** |
| opóźnienie pierwszego poprawnego akordu | 0,54 s | **0,34 s** |
| akord przy rozstrojonej gitarze (−35…+32¢) | 64,8 % | **100 %** |
| nuty (F1 obecności dźwięku) | 58,5 % | **63,9 %** |
| początki nut (F1, tol. 120 ms) | 70,0 % | **76,6 %** |
| stroik: trafiony dźwięk (melodie) | 90,5 % | **97,6 %** |
| stroik: mediana błędu częstotliwości | 0,72¢ | **0,30¢** |
| czas analizy / czas nagrania (natywnie) | 0,034 | **0,020** |

Śledzenie ręki osobno (`tools/ghost.py`, zbiór kontrolny, uderzenia): fałszywe dźwięki w ramkach (wysokość, której nie ma w granym chwycie)
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
