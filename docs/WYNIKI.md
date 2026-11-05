# Wyniki gen 6: wszystkie kroki po kolei

Stan na 5 listopada 2026. Sesje 1, 3 i 4 zakończone; wyniki końcowe (sesja 4) w sekcji 7 na dole. Pliki obok: `wyniki/uczenie.png` (krzywe),
`wyniki/epoki.csv` (wszystkie epoki), `wyniki/test_grupy.csv` (wszystkie grupy testowe, mikro i makro, 24 miary).

## 1. Dane

| zbiór | nagrania | opis |
|---|---:|---|
| klasyka, zestaw 1: uczenie / walidacja / test | 5502 / 450 / 520 | 27 instrumentów, 11 miejsc, 4 formy utworu (oryginał, odwrócenie, rak, rak odwrócenia); utwór zawsze w jednym zbiorze |
| środowiska gitarowe (gen 4) | 888 (z tego ok. 10 % do walidacji) | gitara w losowym pokoju z szumem, brumem, stukami |
| GuitarSet (prawdziwa gitara) | 168 / 12 / 180 | gracze 00–02 uczenie, funk gracza 02 walidacja, gracze 03–05 test; 85 / 6,5 / 91 min |
| klasyka, zestaw 2 (`dane2`) | 9135 (tylko uczenie, od sesji 3) | inne ziarna: inne transpozycje, tempa, obsady, miejsca; 3 formy utworu |
| korpus MIDI | 3236 utworów, 282 h muzyki, 8,2 mln nut | MAESTRO v3 (1276) + music21 (1960, minus 9 nieczytelnych) |

Razem ok. 16 850 nagrań. Do uczenia w sesji 1 ok. 6400 (ok. 27 h), w sesji 3 i 4 ok. 15 600 (ok. 56 h; godziny to szacunek z liczby nagrań).
Cechy HCQT: krok 23 ms, 9 kanałów × 159 binów, float16; razem 14,8 GB (zestaw 1) i 15,3 GB (zestaw 2).

## 2. Model i przebieg uczenia

| | |
|---|---|
| sieć | 249 219 parametrów: 3 bloki harmoniczne, 2 warstwy kontekstu (uwaga w czasie w obie strony + uwaga między wysokościami), głowice: początek, brzmi, koniec, głośność (nieuczona), tabulatura |
| sprzęt | Kaggle, Tesla T4, mieszana precyzja fp16, paczka 16 × 192 klatki (4,4 s) |
| sesja 1 | 36 epok × 1000 kroków, lr 1e-3 → 0 (kosinus); 7,3 h uczenia (nowa wersja kodu skończyłaby ok. 3 h później, patrz niżej); 12 min/epoka |
| sesja 2 | zatrzymana na prośbę po kilku minutach (bez wyników) |
| sesja 3 | 12 epok (36–47), lr 4e-4, dane zestawów 1 i 2, augmentacje; zatrzymana przez early stop po 12 epokach bez poprawy rekordu (plan: do 22:00 UTC) |
| sesja 4 | 14:26–01:24 UTC, 49 epok (48–96), wznowienie od epoki 47, lr 3e-4 → 0; najlepsza epoka 81 (90,27 %) |
| limit GPU | zużyte 22,6 h z 30 h (po sesji 4), wolne 7,4 h (odnowienie 7 listopada) |

Wybór najlepszej epoki: po F1 nut na walidacji (180 nagrań ze wszystkich źródeł, stała próba). Najlepsza: **epoka 29, 89,42 %**.

## Sesja 1 i sesja 3: wyniki po epokach (walidacja)

| epoka | sesja | lr | czas [min] | strata onset | frame | offset | tab | **F1 nut razem** | początek+koniec | klatki | GuitarSet | klasyka | środowiska |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 1 | 1.0e-03 | 12 | 0.0562 | 0.0871 | 0.0391 | 0.6135 | **69.66** | 37.7 | 82.9 | 74.2 | 67.4 | 71.1 |
| 1 | 1 | 1.0e-03 | 28 | 0.0315 | 0.0489 | 0.0289 | 0.2109 | **79.04** | 48.7 | 85.9 | 82.4 | 74.9 | 82.5 |
| 2 | 1 | 9.9e-04 | 40 | 0.0276 | 0.0418 | 0.0260 | 0.1702 | **80.71** | 51.8 | 87.2 | 84.3 | 76.5 | 84.2 |
| 3 | 1 | 9.8e-04 | 52 | 0.0262 | 0.0381 | 0.0246 | 0.1477 | **82.93** | 57.1 | 88.0 | 86.6 | 77.9 | 87.2 |
| 4 | 1 | 9.7e-04 | 64 | 0.0247 | 0.0360 | 0.0234 | 0.1342 | **83.14** | 56.6 | 87.7 | 86.6 | 77.8 | 87.8 |
| 5 | 1 | 9.5e-04 | 76 | 0.0239 | 0.0336 | 0.0227 | 0.1230 | **84.22** | 60.9 | 89.1 | 86.2 | 79.0 | 89.0 |
| 6 | 1 | 9.3e-04 | 88 | 0.0240 | 0.0329 | 0.0226 | 0.1143 | **84.17** | 60.2 | 89.0 | 86.2 | 79.2 | 88.7 |
| 7 | 1 | 9.0e-04 | 100 | 0.0232 | 0.0314 | 0.0220 | 0.1057 | **85.12** | 60.3 | 90.0 | 86.3 | 80.1 | 89.9 |
| 8 | 1 | 8.8e-04 | 112 | 0.0225 | 0.0296 | 0.0214 | 0.0994 | **85.53** | 62.1 | 89.9 | 86.6 | 81.0 | 89.8 |
| 9 | 1 | 8.5e-04 | 124 | 0.0221 | 0.0295 | 0.0212 | 0.0938 | **85.21** | 62.6 | 90.8 | 86.3 | 80.8 | 89.4 |
| 10 | 1 | 8.1e-04 | 136 | 0.0217 | 0.0283 | 0.0207 | 0.0864 | **86.06** | 63.1 | 90.3 | 86.1 | 81.7 | 90.4 |
| 11 | 1 | 7.8e-04 | 148 | 0.0214 | 0.0274 | 0.0205 | 0.0842 | **86.33** | 63.0 | 91.0 | 87.0 | 81.6 | 90.9 |
| 12 | 1 | 7.4e-04 | 161 | 0.0215 | 0.0271 | 0.0206 | 0.0777 | **86.78** | 64.5 | 91.1 | 86.5 | 82.2 | 91.4 |
| 13 | 1 | 7.0e-04 | 173 | 0.0210 | 0.0263 | 0.0202 | 0.0783 | **86.79** | 64.4 | 91.1 | 86.7 | 82.5 | 91.1 |
| 14 | 1 | 6.5e-04 | 185 | 0.0206 | 0.0254 | 0.0199 | 0.0696 | **87.63** | 65.2 | 91.0 | 86.5 | 83.9 | 91.5 |
| 15 | 1 | 6.1e-04 | 197 | 0.0207 | 0.0249 | 0.0199 | 0.0659 | **86.82** | 64.6 | 91.1 | 86.7 | 83.1 | 90.5 |
| 16 | 1 | 5.7e-04 | 209 | 0.0202 | 0.0245 | 0.0196 | 0.0650 | **87.75** | 66.1 | 91.2 | 86.5 | 83.8 | 92.0 |
| 17 | 1 | 5.2e-04 | 221 | 0.0201 | 0.0240 | 0.0195 | 0.0622 | **87.51** | 65.4 | 90.6 | 86.7 | 83.8 | 91.4 |
| 18 | 1 | 4.8e-04 | 233 | 0.0198 | 0.0236 | 0.0193 | 0.0600 | **87.71** | 66.3 | 91.4 | 86.4 | 84.0 | 91.7 |
| 19 | 1 | 4.3e-04 | 245 | 0.0195 | 0.0228 | 0.0190 | 0.0559 | **88.55** | 67.8 | 91.7 | 86.8 | 84.7 | 92.7 |
| 20 | 1 | 3.9e-04 | 257 | 0.0198 | 0.0228 | 0.0193 | 0.0545 | **88.30** | 67.1 | 91.4 | 86.5 | 84.5 | 92.4 |
| 21 | 1 | 3.5e-04 | 269 | 0.0191 | 0.0221 | 0.0186 | 0.0515 | **88.19** | 66.5 | 91.5 | 86.9 | 84.3 | 92.3 |
| 22 | 1 | 3.0e-04 | 281 | 0.0192 | 0.0219 | 0.0187 | 0.0508 | **88.43** | 67.4 | 91.6 | 87.1 | 84.6 | 92.5 |
| 23 | 1 | 2.6e-04 | 293 | 0.0191 | 0.0216 | 0.0186 | 0.0487 | **88.37** | 67.6 | 92.1 | 87.1 | 84.6 | 92.4 |
| 24 | 1 | 2.2e-04 | 305 | 0.0194 | 0.0218 | 0.0189 | 0.0471 | **89.00** | 67.6 | 91.9 | 86.9 | 85.3 | 93.2 |
| 25 | 1 | 1.9e-04 | 317 | 0.0189 | 0.0210 | 0.0185 | 0.0453 | **88.66** | 67.8 | 92.0 | 86.7 | 85.0 | 92.7 |
| 26 | 1 | 1.5e-04 | 329 | 0.0187 | 0.0204 | 0.0182 | 0.0435 | **88.89** | 68.1 | 92.1 | 87.0 | 85.2 | 93.0 |
| 27 | 1 | 1.2e-04 | 341 | 0.0189 | 0.0208 | 0.0185 | 0.0443 | **89.02** | 67.7 | 92.1 | 86.7 | 85.6 | 92.9 |
| 28 | 1 | 9.6e-05 | 353 | 0.0187 | 0.0206 | 0.0184 | 0.0421 | **89.14** | 68.5 | 92.0 | 86.8 | 85.6 | 93.2 |
| 29 | 1 | 7.1e-05 | 366 | 0.0185 | 0.0200 | 0.0182 | 0.0427 | **89.42** | 68.8 | 92.4 | 86.8 | 86.0 | 93.4 |
| 30 | 1 | 5.0e-05 | 378 | 0.0186 | 0.0200 | 0.0182 | 0.0419 | **89.20** | 68.4 | 92.3 | 87.0 | 85.7 | 93.1 |
| 31 | 1 | 3.2e-05 | 390 | 0.0186 | 0.0198 | 0.0181 | 0.0406 | **89.26** | 68.7 | 92.4 | 87.1 | 85.9 | 93.1 |
| 32 | 1 | 1.8e-05 | 402 | 0.0185 | 0.0199 | 0.0182 | 0.0407 | **89.26** | 68.7 | 92.3 | 86.9 | 85.7 | 93.3 |
| 33 | 1 | 8.0e-06 | 414 | 0.0182 | 0.0198 | 0.0180 | 0.0406 | **89.28** | 68.7 | 92.3 | 87.0 | 85.9 | 93.1 |
| 34 | 1 | 2.0e-06 | 426 | 0.0183 | 0.0198 | 0.0180 | 0.0397 | **89.32** | 68.8 | 92.3 | 86.9 | 86.0 | 93.1 |
| 35 | 1 | 2.0e-12 | 438 | 0.0185 | 0.0202 | 0.0181 | 0.0398 | **89.29** | 68.7 | 92.3 | 86.9 | 86.0 | 93.1 |
| 36 | 3 | 4.0e-04 | 11 | 0.0234 | 0.0289 | 0.0210 | 0.1534 | **88.86** | 68.0 | 91.7 | 87.3 | 84.8 | 93.3 |
| 37 | 3 | 4.0e-04 | 26 | 0.0232 | 0.0286 | 0.0207 | 0.0881 | **88.84** | 67.6 | 91.8 | 87.4 | 84.6 | 93.4 |
| 38 | 3 | 4.0e-04 | 37 | 0.0234 | 0.0283 | 0.0209 | 0.0792 | **88.69** | 67.1 | 91.9 | 86.3 | 84.9 | 92.9 |
| 39 | 3 | 3.9e-04 | 49 | 0.0230 | 0.0285 | 0.0206 | 0.0765 | **88.63** | 66.5 | 90.8 | 86.3 | 84.6 | 93.1 |
| 40 | 3 | 3.9e-04 | 60 | 0.0227 | 0.0278 | 0.0204 | 0.0741 | **88.63** | 67.3 | 91.7 | 86.3 | 84.7 | 93.0 |
| 41 | 3 | 3.9e-04 | 72 | 0.0228 | 0.0279 | 0.0204 | 0.0712 | **88.77** | 67.6 | 91.8 | 87.2 | 84.3 | 93.5 |
| 42 | 3 | 3.8e-04 | 83 | 0.0227 | 0.0272 | 0.0203 | 0.0694 | **88.73** | 67.9 | 91.9 | 86.6 | 84.9 | 93.0 |
| 43 | 3 | 3.8e-04 | 95 | 0.0230 | 0.0276 | 0.0205 | 0.0696 | **89.08** | 68.5 | 91.7 | 87.6 | 85.0 | 93.4 |
| 44 | 3 | 3.7e-04 | 106 | 0.0228 | 0.0268 | 0.0204 | 0.0686 | **89.10** | 68.2 | 91.7 | 87.0 | 85.4 | 93.2 |
| 45 | 3 | 3.6e-04 | 118 | 0.0222 | 0.0270 | 0.0200 | 0.0691 | **88.96** | 68.1 | 91.8 | 87.1 | 85.1 | 93.2 |
| 46 | 3 | 3.6e-04 | 130 | 0.0227 | 0.0274 | 0.0204 | 0.0669 | **89.14** | 67.9 | 91.9 | 87.0 | 85.4 | 93.3 |
| 47 | 3 | 3.5e-04 | 141 | 0.0226 | 0.0266 | 0.0202 | 0.0669 | **89.15** | 68.4 | 91.8 | 87.1 | 85.3 | 93.4 |

Krzywe: `wyniki/uczenie.png`. Obserwacje:
* Sesja 1: F1 nut rosło z 69,7 % (epoka 0) do 89,4 % (epoka 29) i stało od epoki ok. 25 (89,0–89,4 %); strata tabulatury spadła z 0,61 do 0,040.
* Sesja 3: na początku strata wzrosła (onset 0,018 → 0,023, frame 0,020 → 0,029), bo dane są trudniejsze (augmentacje, nowe nagrania) i lr wzrósł do 4e-4;
  wynik na walidacji najpierw spadł do 88,6 % (epoka 39–40), potem wrócił do 89,15 % (epoka 47). Klasyka na walidacji jest o ok. 0,7 pkt niżej
  niż w sesji 1 (85,3 vs 86,0 %), GuitarSet i środowiska bez zmian (87,1 i 93,4 %). Rekordu z epoki 29 nie przebiła, więc `best.pt` to model z sesji 1.
* Przyczyna zatrzymania sesji 3: wbudowany early stop (12 epok bez poprawy). To był mój błąd konfiguracji; poprawiony, w sesji 4 wyłączony przy uczeniu z terminem.

## 3. Test (model z epoki 29; zbiory, których model nie widział)

Test sesji 3 jest identyczny z testem sesji 1 co do miejsca po przecinku (oceniany jest ten sam `best.pt`). 700 nagrań: 180 GuitarSet + 520 klasyka.

**Razem (95 % przedział bootstrap po plikach, mikro):** F1 nut 82,6 %; **makro (średnia po nagraniach) F1 nut 84,8 % [83,8; 85,7]**,
początek+koniec 66,9 % [65,4; 68,5], klatki 88,1 % [87,5; 88,6].

Inne miary RAZEM (mikro): mediana błędu początku 7,8 ms (przesunięcie systematyczne 0,8 ms), pokrycie słyszalnego czasu nuty 85,0 %,
poszatkowanie 1,23 odcinka na nutę, AP początków 67,3 %, AP klatek 94,8 %, kalibracja klatek ECE 0,01, najlepszy próg początków
na teście 0,83 (dekoder używa 0,5, więc dostrojenie progu jest możliwym zyskiem).

## Test: główne grupy (mikro: suma po nutach)

| grupa | n | F1 nut | P | R | F1 (100 ms) | początek+koniec | klatki | oktawa błędnie | tab F1 | trafna struna |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| RAZEM | 700 | 82.6 | 86.9 | 84.0 | 84.3 | 63.7 | 87.8 | 26.3 | 80.0 | 86.9 |
| GuitarSet:solo | 90 | 88.8 | 88.3 | 89.8 | 90.4 | 77.9 | 88.2 | 0.5 | 73.8 | 82.6 |
| GuitarSet:comp | 90 | 84.4 | 84.4 | 86.1 | 85.3 | 68.0 | 87.9 | 20.6 | 81.9 | 91.2 |
| klasyka:solo:gitara_klasyczna | 74 | 85.2 | 90.4 | 89.9 | 86.5 | 68.8 | 88.8 | 36.8 | nan | nan |
| klasyka:solo:gitara_stalowa | 16 | 78.6 | 88.4 | 80.3 | 79.9 | 64.5 | 81.9 | 35.0 | nan | nan |
| klasyka:solo:gitara_elektryczna | 9 | 88.6 | 94.1 | 86.9 | 89.4 | 76.1 | 92.6 | 33.1 | nan | nan |
| klasyka:gitara+zespol | 49 | 86.1 | 88.7 | 88.4 | 86.9 | 69.8 | 89.3 | 37.4 | nan | nan |
| klasyka:zespol | 139 | 78.7 | 86.2 | 79.9 | 81.1 | 56.7 | 85.9 | 31.5 | nan | nan |

Tabulatura (tylko GuitarSet): akompaniament tab F1 81,9 %, trafna struna 91,2 %, TDR 91,3 %; melodie tab F1 73,8 %, struna 82,6 %, TDR 83,9 %.
Akordy z nut (GuitarSet comp): prima 71,9 %, dur/moll 79,4 %.
Uwaga: tabulatura na klasyce jest „nan”, bo te nagrania nie mają strun.

## Test: wszystkie instrumenty (makro: średnia po nagraniach)

| grupa | n | F1 nut | P | R | początek+koniec | klatki | mediana błędu początku [ms] |
|---|---:|---:|---:|---:|---:|---:|---:|
| klasyka:solo:ukulele | 12 | 94.2 | 96.1 | 92.6 | 82.8 | 92.0 | 6.1 |
| klasyka:solo:pizzicato | 13 | 93.7 | 92.4 | 95.3 | 73.7 | 88.2 | 6.2 |
| klasyka:solo:gitara_elektryczna | 9 | 90.0 | 94.1 | 86.9 | 79.3 | 93.4 | 7.0 |
| klasyka:solo:gitara_klasyczna | 74 | 89.9 | 90.4 | 89.9 | 76.0 | 90.0 | 6.9 |
| klasyka:solo:klarnet | 6 | 89.7 | 93.4 | 86.4 | 79.0 | 90.8 | 7.1 |
| GuitarSet:solo | 90 | 88.9 | 88.3 | 89.8 | 78.0 | 87.8 | 6.4 |
| klasyka:solo:harfa | 10 | 88.8 | 89.6 | 88.6 | 74.4 | 92.0 | 6.3 |
| klasyka:solo:marimba | 11 | 88.5 | 86.0 | 91.4 | 57.7 | 86.2 | 7.0 |
| klasyka:solo:lutnia | 8 | 88.1 | 85.2 | 91.5 | 69.4 | 91.6 | 6.9 |
| klasyka:gitara+zespol | 49 | 87.9 | 88.7 | 88.4 | 71.7 | 89.5 | 7.0 |
| klasyka:solo:fortepian | 9 | 86.3 | 84.5 | 88.8 | 58.3 | 87.4 | 7.1 |
| klasyka:solo:trabka | 8 | 85.2 | 93.4 | 79.5 | 62.5 | 86.5 | 9.7 |
| klasyka:solo:mandolina | 9 | 85.0 | 86.0 | 85.3 | 64.8 | 87.3 | 7.3 |
| GuitarSet:comp | 90 | 84.9 | 84.4 | 86.1 | 69.1 | 86.7 | 7.4 |
| RAZEM | 700 | 84.8 | 86.9 | 84.0 | 66.9 | 88.1 | 7.8 |
| klasyka:solo:waltornia | 8 | 84.3 | 92.8 | 78.5 | 71.5 | 92.3 | 9.4 |
| klasyka:solo:wibrafon | 9 | 84.2 | 83.3 | 86.2 | 44.4 | 83.4 | 7.0 |
| klasyka:solo:dzwonki | 13 | 83.6 | 80.9 | 87.5 | 57.8 | 91.0 | 7.5 |
| klasyka:solo:organy | 9 | 83.4 | 86.2 | 81.4 | 64.3 | 88.5 | 10.9 |
| klasyka:solo:gitara_stalowa | 16 | 83.2 | 88.4 | 80.3 | 70.7 | 88.5 | 7.1 |
| klasyka:solo:altowka | 12 | 82.7 | 88.9 | 78.3 | 62.2 | 91.5 | 9.2 |
| klasyka:solo:fagot | 19 | 82.5 | 90.2 | 77.3 | 67.3 | 90.0 | 8.1 |
| klasyka:zespol | 139 | 82.2 | 86.2 | 79.9 | 61.8 | 86.2 | 8.2 |
| klasyka:solo:flet | 9 | 81.3 | 85.0 | 78.2 | 59.4 | 93.0 | 9.1 |
| klasyka:solo:klawesyn | 9 | 79.8 | 85.7 | 75.7 | 64.2 | 81.6 | 7.8 |
| klasyka:solo:oboj | 8 | 78.1 | 86.4 | 73.3 | 67.0 | 90.6 | 7.6 |
| klasyka:solo:skrzypce | 19 | 75.4 | 80.8 | 72.2 | 45.8 | 89.0 | 10.8 |
| klasyka:solo:akordeon | 2 | 74.6 | 79.5 | 70.4 | 50.8 | 93.0 | 9.4 |
| klasyka:solo:syntezator | 6 | 72.8 | 72.7 | 76.1 | 33.0 | 83.0 | 10.5 |
| klasyka:solo:wiolonczela | 9 | 71.3 | 80.6 | 64.5 | 43.8 | 87.9 | 13.7 |
| klasyka:solo:kontrabas | 7 | 71.0 | 78.6 | 70.0 | 40.0 | 86.4 | 10.1 |
| klasyka:solo:chor | 8 | 56.0 | 66.0 | 51.5 | 29.4 | 84.6 | 15.5 |

Najsłabiej: chór (56 %), kontrabas (71 %), wiolonczela (71 %), syntezator (73 %), akordeon (75 %), skrzypce (75 %).
Najlepiej: ukulele (94 %), pizzicato (94 %), gitara elektryczna (90 %), klarnet (90 %), gitara klasyczna (90 %).

## 4. Porównanie z gen 5 (README, ten sam podział GuitarSet 03–05)

| | gen 5 z uwagą | gen 6 (epoka 29) |
|---|---:|---:|
| GuitarSet 03–05: F1 nut, razem | 79,5 % | **86,6 %** (średnia ważona solo i comp) |
| GuitarSet: akompaniament / melodie | 75,6 / 83,4 % | **84,4 / 88,8 %** (mikro) |
| GuitarSet: nuty z początkiem i końcem | 40,9 % | **68,0 / 77,9 %** (comp / solo) |
| klasyka, F1 nut | 62,4 % (próba walidacyjna gen 6, bez douczenia) | ok. 80 % (test; inny zbiór, nie wprost porównywalne) |

## 5. Serwer (ESP32 → telefon → serwer)

Test na nagraniu GuitarSet spoza uczenia (04_SS1-100-C#_solo, 28,8 s): 72 nuty (prawda 71), P 0,83, R 0,85, F1 0,839 przy tolerancji 50 ms;
czas 5,0 s na 4 rdzeniach (cechy 2,0 s, sieć 3,0 s), czyli ok. 0,17 czasu nagrania. Drugie nagranie (39 s, akompaniament): 199 nut, 5,3 s.

## 6. Stan i problemy

* Sesja 4 zakończona; wyniki w sekcji 7.
* Głowica głośności jest nieuczona (żadne źródło nie ma etykiet głośności), jej wartości nie są zwracane.
* Wpływ augmentacji (rozstrojenie, przesunięcia etykiet) na wynik nie jest zmierzony osobno; w sesji 3 wynik był ok. 0,3 pkt niżej niż rekord z sesji 1.
* Wcześniejsze podejrzenie błędu miary AP_frame (wartość powyżej 1 na próbie syntetycznej) nie potwierdziło się na prawdziwych danych: 94,8 %.
* Dane do dostrajania na piezo: jeszcze brak (strona do opisywania i etap `push.py piezo` są gotowe).

## 7. Wynik końcowy: sesja 4 (stan z 5 listopada 2026)

Sesja 4 trwała od 14:26 do 01:24 UTC: **49 epok (48–96), 11 h**, lr 3e-4 → 0 (kosinus od czasu), bez wczesnego zatrzymania. Razem trening to **97 epok w 3 sesjach**.
Najlepsza epoka według walidacji: **81, F1 nut 90,27 %** (rekord sesji 1: 89,42 %). Wykresy: `wyniki/trening_calosc.png`, `wyniki/benchmarki.png`. Model w serwerze (`tools/gen6/server/model/best.pt`) to teraz ten z epoki 81.

### Test, 700 nagrań (utwory i gracze spoza uczenia)

| | sesja 1 (epoka 29) | **końcowy (epoka 81)** | zmiana |
|---|---:|---:|---:|
| F1 nut, makro razem | 84.8 | **85.9** | +1.1 |
| nuty z końcem, makro razem | 66.9 | **69.4** | +2.5 |
| klatki, makro razem | 88.1 | **88.5** | +0.4 |
| F1 nut, mikro razem | 82.6 | **83.7** | +1.2 |
| nuty z końcem, mikro razem | 63.7 | **66.2** | +2.5 |
| GuitarSet akompaniament: F1 nut | 84.4 | **85.1** | +0.8 |
| GuitarSet akompaniament: z końcem | 68.0 | **70.2** | +2.2 |
| GuitarSet akompaniament: klatki | 87.9 | **87.9** | +0.0 |
| GuitarSet akompaniament: tab F1 | 81.9 | **82.2** | +0.4 |
| GuitarSet akompaniament: trafna struna | 91.2 | **91.3** | +0.1 |
| GuitarSet akompaniament: TDR | 91.3 | **91.7** | +0.4 |
| GuitarSet melodie: F1 nut | 88.8 | **89.2** | +0.4 |
| GuitarSet melodie: z końcem | 77.9 | **79.4** | +1.6 |
| GuitarSet melodie: klatki | 88.2 | **88.7** | +0.5 |
| GuitarSet melodie: tab F1 | 73.8 | **75.1** | +1.2 |
| GuitarSet melodie: trafna struna | 82.6 | **83.2** | +0.6 |
| GuitarSet melodie: TDR | 83.9 | **84.6** | +0.7 |

**Istotność (sparowany bootstrap po tych samych 700 plikach, 95 %):** F1 nut +1,14 pkt [0,98; 1,32], z końcem +2,50 pkt [2,19; 2,81], klatki +0,43 pkt [0,32; 0,54]; we wszystkich trzech p < 0,0001.
Przedziały ufności makro razem: F1 nut **85,9 % [85,0; 86,8]** (było 84,8 [83,8; 85,7]), z końcem **69,4 % [67,9; 71,0]** (było 66,9 [65,4; 68,5]), klatki **88,5 % [87,9; 89,1]** (było 88,1 [87,5; 88,6]).
Inne miary razem (mikro): mediana błędu początku 7.8 ms (bias 1.0 ms), AP początków 67.7 %, AP klatek 95.2 %, najlepszy próg początków 0.82 (dekoder: 0,5), ECE 0.01, pokrycie nut 85.1 %, poszatkowanie 1.20, błąd oktawowy 24.4 %.

**Gdzie poprawa jest największa:** grupy z mniej niż 12 nagraniami są niepewne. Przy większych grupach (zespoły n=139: +1,2 pkt, gitara klasyczna n=74: +1,0, GuitarSet: +0,4 / +0,7) poprawa jest umiarkowana i zgodna z całością. **GuitarSet poprawił się najmniej**, bo nowe dane są syntetyczne, a prawdziwej gitary nie przybyło.
Jedyny spadek: gitara elektryczna (n=9, −0,3 pkt, w granicach szumu).

### Porównanie z gen 5 (README, GuitarSet 03–05)

| | gen 5 | gen 6, sesja 1 | **gen 6, końcowy** |
|---|---:|---:|---:|
| F1 nut razem | 79,5 | 86,6 | **87.2** |
| akompaniament / melodie | 75,6 / 83,4 | 84,4 / 88,8 | **85.1 / 89.2** |
| z końcem (razem) | 40,9 | 73,0 | **74.8** |

### Szybkość serwera (nagranie 39 s, CPU, 192 nuty)

| wątki | cechy | sieć | razem | ułamek czasu nagrania | 3 min gry |
|---:|---:|---:|---:|---:|---:|
| 1 | 1.6 s | 10.1 s | 11.7 s | 0.30 | 54 s |
| 2 | 1.9 s | 3.7 s | 5.7 s | 0.14 | 26 s |
| 4 | 1.9 s | 2.1 s | 4.0 s | 0.10 | 19 s |

Na Cloud Run z 1–2 rdzeniami to 26–54 s na 3 minuty gry (plus start kontenera). Maszyna pomiarowa: 4 rdzenie.

### Przebieg treningu (97 epok)

* Sesja 1 (epoki 0–35, 7,3 h): kosinus od 1e-3, 12 min/epoka; walidacja 69,7 → 89,3 %; najlepsza epoka 29 (89,42 %).
* Sesja 3 (epoki 36–47, 2,9 h): restart lr 4e-4, dane zestawów 1 i 2, augmentacje; wynik na walidacji 88,6–89,15 %; zatrzymana przez early stop (błąd konfiguracji).
* Sesja 4 (epoki 48–96, 11 h): lr 3e-4 → 0; walidacja rosła od 89,05 % (epoka 48) do 90,0–90,3 % w epokach 74–96; najlepsza epoka 81 (90,27 %).
* Strata tabulatury: 0,61 (epoka 0) → 0,040 (epoka 35) → 0,153 po restarcie (epoka 36) → 0,046 (epoka 96).
* Zużycie limitu GPU: 22,6 h z 30 h (wolne 7,4 h do odnowienia 7 listopada).

### Co nie wyszło lub jest niepewne

* Wynik na walidacji GuitarSet i tabulatura (F1 na walidacji 12 nagrań) są po sesjach 3–4 nieco niższe niż w sesji 1 (tab F1 83,6 vs 85,2 %), choć na teście są podobne; walidacja GuitarSet to tylko 12 nagrań.
* Wpływu poszczególnych augmentacji (rozstrojenie, przesunięcia etykiet) nie mierzyłem osobno; poprawa wynika łącznie z dodatkowych danych, dłuższego uczenia i augmentacji.
* Progi dekodera nie były stroione: najlepszy próg początków na teście wychodzi 0,82, dekoder używa 0,5. Dostrojenie na walidacji jest następnym krokiem.
* Głowica głośności nadal nieuczona.

## 8. Dostrojony dekoder (5 listopada 2026)

Strojenie na walidacji (222 nagrania: 12 GuitarSet, 150 klasyka, 60 środowisk; cel = średnia z F1 nut i F1 nut z końcem, wagi źródeł 0,4 / 0,4 / 0,2), przeszukiwanie po współrzędnych w 2 przebiegach, **test na 700 nagraniach, których strojenie nie widziało**. Kod: `tools/gen6/tune_decoder.py`, wynik: `tools/gen6/server/model/decode.json` (serwer czyta go sam obok `best.pt`; usunięcie pliku wraca do progów domyślnych).

| parametr | domyślny | dostrojony | znaczenie |
|---|---:|---:|---|
| th_onset | 0.5 | **0.6** | próg początku nuty |
| th_onset_frame | 0.3 | **0.1** | wymagane p(brzmi) przy początku |
| th_frame | 0.5 | **0.6** | próg trwania nuty |
| th_offset | 0.5 | **0.8** | próg maksimum końca |
| th_start | 0.7 | **1.01** | nuta bez początku (1,01 = wyłączone) |
| min_frames | 2 | **2** | minimalna długość [klatki] |
| gap_frames | 1 | **2** | przerwa kończąca nutę [klatki] |
| merge_sec | 0.03 | **0.08** | scalanie duplikatów [s] |
| min_dur | 0.06 | **0.06** | najkrótsza nuta [s] |

Cel na walidacji: 79.57 → **80.87** (GuitarSet 81.2, klasyka 79.0, środowiska 83.8). Największy wkład: **wyłączenie nut bez wykrytego początku** (`th_start` 0,7 → 1,01: +0,75 celu); pozostałe zmiany po 0,02–0,12 (na granicy szumu).

### Test (700 nagrań, makro)

| | domyślny | dostrojony | zmiana (sparowany bootstrap 95 %) |
|---|---:|---:|---|
| F1 nut razem | 85.9 | **86.6** | **+0,64** [0,46; 0,83] |
| nuty z końcem razem | 69.4 | **70.0** | **+0,59** [0,32; 0,85] |
| klatki razem | 88.5 | 87.3 | **−1,29** [−1,50; −1,10] |
| precyzja / czułość razem | 88.8 / 84.2 | 93.5 / 82.1 | precyzja w górę, czułość w dół |
| GuitarSet akompaniament: F1 nut / z końcem | 85.6 / 71.4 | **87.3 / 72.7** | +1.6 / +1.2 |
| GuitarSet melodie: F1 nut / z końcem | 89.3 / 79.6 | **90.7 / 80.7** | +1.4 / +1.1 |

**Co to znaczy:** dostrojony dekoder jest ostrożniejszy: tworzy mniej fałszywych nut (precyzja 88,8 → 93,5 %), a przy tym trochę częściej gubi prawdziwe (czułość 84,2 → 82,1 %). Dla listy nut (MIDI, tabulatura) to lepszy kompromis: F1 nut i F1 z końcem rosną istotnie, na **GuitarSet o 1,4–1,6 pkt**. Płaci za to miara klatkowa (−1,3 pkt) i pokrycie czasu nut (85,1 → 81,1 %): nuty są nieco krótsze. Lepiej wypada 19 z 31 grup (makro); klasyka zespołowa (mikro) bez zmiany.
Wzrost na teście (+0,64) jest o połowę mniejszy niż na walidacji (+1,30), co jest typowe dla strojenia na ograniczonym zbiorze. Miary tabulatury, mediana błędu początku (7,3 ms) i błąd oktawowy (20 %) bez zmian.
Dwa nagrania GuitarSet z testu (nie używane do strojenia): melodia 04_SS1-100-C# F1 0,819 → **0,847**, akompaniament 05_Funk3-98-A 0,941 → **0,945** (tolerancja 50 ms).

**Gdy ważniejsza jest czułość** (nic nie zgubić, a fałszywe nuty poprawia człowiek): usuń `decode.json`, albo ustaw `th_start` 0,7 i `th_frame` 0,5.
