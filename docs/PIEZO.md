# Dostrajanie na piezo (gitara z czujnikiem piezoelektrycznym)

Model gen 6 jest wstępnie nauczony na mikrofonie (klasyka, środowiska, GuitarSet). Piezo brzmi inaczej (pudło i mostek, mało
pogłosu i szumu pokoju), więc na własnych nagraniach z piezo model się dostraja: krótko, z małym tempem uczenia, z domieszką
poprzednich danych, żeby niczego nie zapomniał.

## 1. Nagrywanie

* Format WAV, dowolna częstotliwość próbkowania (model sam zmienia na 11 025 Hz), mono, bez kompresji stratnej.
* Ile: **już 20–30 minut daje efekt, 1–3 godziny to dobry zapas.** Najlepiej wiele krótkich nagrań (30 s – 3 min) zamiast kilku długich.
* Różnorodnie: pojedyncze nuty, melodie, akordy, arpeggia; wolno i szybko; różne struny i progi; ciche i głośne granie; różne utwory.
* Jeśli możesz, nagrywaj **równocześnie mikrofon i piezo** (ta sama gra): model opisze nuty z mikrofonu, a Ty tylko poprawisz.

## 2. Opisywanie (strona `tools/gen6/piezo/annotator.html`)

Otwórz plik w Chrome (dwuklik, bez serwera). Wczytaj WAV, przeciągaj myszą po widmie (poziomo = czas i długość nuty,
pionowo = wysokość MIDI), zapisz CSV. Przy odtwarzaniu słychać zaznaczone nuty, więc błędy wychwycisz uchem.

Szybciej: **wstępny opis modelem**, który potem poprawiasz na stronie (przycisk „Wczytaj opis (CSV)”):

```bash
python3 tools/gen6/piezo/preannotate.py model/best.pt folder_z_wav/ --out folder_z_wav/
```

(najlepiej na nagraniach z mikrofonu, wynik skopiuj pod nazwą nagrania z piezo: `take1_mic.csv` → `take1_piezo.csv`.)

Zasady, które mają znaczenie dla jakości:
* początek nuty z dokładnością do ok. 30 ms (okno oceny to 50 ms); koniec do ok. 100 ms;
* **opisuj końce nut** (zwykły zapis); tryb „tylko początki” uczy tylko głowicę początków;
* ta sama nuta zagrana dwa razy to dwie nuty; struny zagrane razem to osobne nuty o tym samym początku;
* nuty poza zakresem E2–E6 (MIDI 36–88) są pomijane;
* pliki pod tą samą nazwą: `nazwa.wav` + `nazwa.csv` (albo `nazwa.mid`).

## 3. Manifest i wysłanie na Kaggle

```bash
python3 tools/gen6/piezo/make_manifest.py folder_z_nagraniami/ --val-every 5      # co 5. nagranie do walidacji
kaggle datasets create -p folder_z_nagraniami/     # wcześniej dodaj dataset-metadata.json: {"title":"gutar-piezo","id":"UŻYTKOWNIK/gutar-piezo","licenses":[{"name":"CC0-1.0"}]}
```

Walidacja musi mieć kilka nagrań (przy małym zbiorze `--val-every 3`), bo na niej wybierana jest najlepsza epoka. Opcjonalnie
`--test-every 6`: osobne nagrania testowe, na których model oceniany jest na końcu.

## 4. Dostrajanie

```bash
python3 tools/gen6/kaggle/push.py piezo --user UŻYTKOWNIK            # ok. 2,5 h; --args "--hours 1.5" skraca
```

Notatnik bierze wstępnie nauczony model z `gutar-gen6-trening-3`, dane z `gutar-gen6-dane` i Twój zbiór `gutar-piezo`.
Konfiguracja `tools/gen6/configs/gen6_piezo.json`: źródło `piezo` 50 %, GuitarSet 20 %, klasyka 20 %, środowiska 10 % (żeby model
nie zapomniał), lr 1,5e-4, nowy cykl lr, epoka wybierana **tylko po walidacji na piezo** (`select_source`). Przed uczeniem liczony
jest wynik wyjściowy na Twojej walidacji, a `best.pt` zapisze się tylko wtedy, gdy dostrojony model go przebije: dostrojenie nie może
wyjść gorsze od modelu wejściowego. W dzienniku: `stan wyjściowy przed dostrajaniem` i po każdej epoce wynik na piezo.

Wynik: `run/best.pt` (kopiujesz do `tools/gen6/server/model/best.pt`) i `run/test.json`.

## Czego nie wiadomo

Ile da dostrojenie, zależy od jakości Twoich opisów i zróżnicowania nagrań; to dopiero się okaże. Przy bardzo małym zbiorze
(poniżej ok. 20 minut) wynik walidacji będzie niepewny, bo kilka nagrań to kilkaset nut.
