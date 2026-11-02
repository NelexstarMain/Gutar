# Metody i prace naukowe do poprawy rozpoznawania dźwięków

Cel: znajdować **wszystkie** grane dźwięki (czułość) i **nie dodawać fałszywych** (precyzja), z dokładnymi
granicami nut. Poniżej przegląd literatury dopasowany do obecnego silnika: każda pozycja mówi, który błąd
z README atakuje, gdzie w kodzie ją wpiąć i jak sprawdzić, czy pomogła. Kolejność to szacowany zysk do kosztu.

## Stan wdrożenia (listopad 2026)

Każdy punkt wdrożony i zmierzony na korpusie syntetycznym (zbiór kontrolny) oraz na prawdziwych nagraniach **GuitarSet**
(strojenie na graczach 00–02, wynik na 03–05). Szczegóły i liczby: README, sekcje „Prawdziwe nagrania” i „Ostatnia runda”.

| # | metoda | stan | wynik |
|---|---|---|---|
| 1 | ocena łączna zbioru nut | wdrożone usuwanie nut w całości wyjaśnionych przez inne; zamiana poduktawy na oktawę wyżej **wyłączona** | mały zysk; zamiana gubiła prawdziwy bas |
| 2 | model miejsca szarpnięcia w teście oktaw | wdrożone | mniej fałszywych oktaw w melodiach (F1 początków 95,6 → 98,2 % na zbiorze roboczym) |
| 3 | nieharmoniczność na wysokość | wdrożone | korpus nie pozwala ocenić (losowa nieharmoniczność na nutę); neutralne |
| 4 | początki nut na wysokość, ponowne szarpnięcia | wdrożone (po analizie pliku) | początki w 50 ms: 54 → 74 % (korpus); GuitarSet: F1 nut 47,7 → 56,0 % łącznie z resztą zmian |
| 5 | krótsze okno / dwa okna | dwa okna bez zysku (odrzucone); okno 186 ms dostępne w ustawieniach | lepsze nuty na GuitarSet, gorsze akordy na korpusie, więc nie domyślnie |
| 6 | ComplexFlux, lepszy wybór pików | nie wdrożone | początki poprawiono przez pkt 4 (funkcja początku na wysokość) |
| 7 | model uczony (AI) | wdrożone: mała sieć (1 601 wag) oceniająca kandydatów na nuty, uczona na korpusie i GuitarSet, działa w WebAssembly; przy analizie nagrania | GuitarSet 03–05: F1 nut 56,2 → 61,7 %, akompaniament: prima 45,7 → 49,2 %; korpus: nuty 81,6 → 91,6 % |
| + | odszumianie z wielu klatek (widmo szumu tła z całego nagrania) | wdrożone przy analizie nagrania; na żywo odrzucone | szum tonalny: początki nut w melodiach 90,2 → 97,4 %; czyste nagrania bez zmian |
| 8 | pomiar na prawdziwych nagraniach | wdrożone: `tools/guitarset_eval.py`, mir_eval, 50 ms | patrz README |
| + | **akordy składane z nut** (prośba użytkownika) | wdrożone przy analizie pliku; na żywo zostaje dowód z ramek (z samych nut gorzej) | GuitarSet, akompaniament: prima 40,4 → 45,7 %, dur/moll 34,0 → 41,9 % |

Stan wyjściowy (holdout, z README): F1 nut 81,0 %, F1 początków 79,5 %, pokrycie czasu nuty 74,3 %,
fałszywe dźwięki to głównie **poduktawy** (E2 zamiast E3), a na czystych melodiach zdarza się **fałszywa oktawa wyżej**.
Ok. 15 % nut z długim ogonem to niewykryte podwojenia oktawowe.

---

## 1. Ocena łączna zbioru nut zamiast samego zachłannego wyboru

**Problem.** `MultiPitch::detect` (`src/gt_pitch.hpp`) wybiera nuty po jednej (estymacja i kasowanie). Raz wybrana
nuta nie jest już weryfikowana, więc poduktawa wybrana wcześnie (bo zbiera energię wszystkich parzystych alikwotów
nuty właściwej) zostaje do końca. To ten sam mechanizm, który README opisuje jako główne źródło duchów.

**Metody.**
* **Duan, Pardo, Zhang (2010)**: wiarygodność liczona z dwóch części, pików *oraz obszarów bez pików*. Kandydat,
  którego oczekiwane alikwoty wypadają w pustych miejscach widma, traci punkty. Poduktawa E2 dla granego E3 ma
  oczekiwane alikwoty 1, 3, 5 (82, 247, 412 Hz). Gdy w tych miejscach nic nie ma, kara jest bezpośrednia; ocena idzie
  po całym zbiorze nut naraz, więc alikwot „wolny” liczy się inaczej niż alikwot pokryty przez inną strunę.
  Jest też etap szacowania liczby głosów (kiedy przestać dokładać nuty).
* **Klapuri (ISMIR 2006)**: trzy warianty: bezpośredni, iteracyjny z kasowaniem (to, co macie) i **łączny**.
* **Yeh, Röbel, Rodet**: łączna ocena hipotez z trzech zasad: harmoniczność, gładkość widma i
  **wspólna ewolucja amplitud w czasie** jednego źródła.

**Jak wpiąć (tanio, ≤ 6 nut).** Po pętli zachłannej dodać krok „eliminacji wstecznej”: dla każdej wybranej nuty
policzyć, ile łącznej wyjaśnionej salience (suma `w * v` po pikach) traci zbiór po jej usunięciu, i usunąć nutę,
jeśli jej wkład krańcowy jest mniejszy niż próg (np. 0,15 wkładu najsilniejszej). Dodatkowo kara Duana za
oczekiwany alikwot, który w `Spectrum::mag()` nie przekracza ~2× `noiseFloor()` w tym miejscu (liczyć z widma, nie
z listy pików, bo lista ma progi). Karę ograniczyć do alikwotów 1–5 i do miejsc, których nie pokrywa inna nuta.

**Uwaga z README.** Próba „brak nieparzystych alikwotów → odrzuć poduktawę” zawiodła, bo w akordzie nieparzyste
alikwoty poduktawy pokrywają się z innymi strunami. Eliminacja wsteczna rozwiązuje właśnie ten przypadek: jeśli
te alikwoty są już wyjaśnione przez inne nuty, poduktawa nic nie dokłada i odpada. Mierzyć `tools/ghost.py`
(liczba duchów) i F1 nut; obserwować, czy nie spada czułość na prawdziwych podwojeniach E2+E3.

---

## 2. Miejsce szarpnięcia: przewidywalne „dziury” w alikwotach

**Problem.** Struna szarpnięta w punkcie *p* (ułamek długości) ma amplitudy alikwotów mnożone przez
|sin(π h p)|. Przy p ≈ 1/4 znika 4. i 8. alikwot, przy p ≈ 1/3 znika 3. i 6., przy p ≈ 1/5 znika 5. i 10.
Test podwojenia oktawowego `addOctaveDoubles` porównuje a(2k) z sqrt(a(2k−1)·a(2k+1)): gdy szarpnięcie
wytnie nieparzysty alikwot, iloraz rośnie i silnik dokłada **fałszywą oktawę** (problem melodii z README). Gdy wytnie
parzysty, prawdziwe podwojenie znika (część z tych 15 % niewykrytych). Wasz syntezator korpusu już to modeluje
(`pos` w `src/gt_synth.hpp`), więc efekt powinien być widoczny w pomiarach.

**Metody.**
* **Traube, Smith (DAFx 2000)**: estymacja punktu szarpnięcia przez dopasowanie widma do idealnych widm struny
  dla różnych *p*; wersja rozszerzona szacuje też punkt chwytu (próg).
* **Traube, Depalle (DAFx 2003)**: dokładniejsza estymacja, opóźnienie filtra grzebieniowego dopasowywane
  ważonymi najmniejszymi kwadratami.
* **Mohamad, Dixon, Harte (DAFx 2017)**: punkt szarpnięcia i przetwornika także dla akordów i z efektami.

**Jak wpiąć.** Dla nuty o ≥ 6 znalezionych alikwotach dopasować *p* z siatki 0,05…0,35 (minimalizacja błędu
log-amplitud względem modelu |sin(π h p)|/h^s). Potem w teście oktaw **pomijać alikwoty leżące w pobliżu zera
modelu** (|sin(π h p)| < 0,3) albo dzielić amplitudy przez model przed porównaniem. Ocena *p* jest stabilna przez
całą nutę, więc można ją liczyć raz po potwierdzeniu nuty w `NoteTracker` i przechowywać w `Active`.
Mierzyć: F1 początków na melodiach (fałszywe oktawy) i odsetek wykrytych podwojeń oktawowych.

---

## 3. Nieharmoniczność i strój mierzone osobno dla każdej struny

**Problem.** Kandydaci w `setA4` mają stałe B = 2,5e-4 i tolerancję 28 + 1,5·h centów. Szeroka tolerancja
pozwala obcym pikom „przykleić się” do kandydata (więcej duchów), a przy wysokich alikwotach strun o innym B
prawdziwe piki mogą wypaść poza okno.

**Metody.**
* **Rigaud, David, Daudet**: estymacja nieharmoniczności i stroju z pojedynczych nut i akordów (NMF z modelem
  parametrycznym, EUSIPCO 2012) oraz model B w funkcji wysokości (DAFx 2011, JASA 2013, fortepian, ale fizyka ta sama).
* **Barbancho i in. (IEEE TASLP 2012)**, *Inharmonicity-Based Method for the Automatic Generation of Guitar
  Tablature*: B zależy od struny, więc z nieharmoniczności da się rozpoznać, **na której strunie** zagrano dźwięk.

**Jak wpiąć.** Regresja (f_h/h)² = f0²(1 + B h²) w `detect` już liczy B dla każdej nuty, ale wynik jest wyrzucany.
Wystarczy zbierać go (mediana ważona amplitudą) na wysokość MIDI, jak histogram rozstrojenia `tuneHist_`, i po
zebraniu kilkunastu pomiarów przebudować `c.hf` z własnym B oraz zwęzić tolerancję (np. do 15 + 0,8·h centów).
Ten sam pomiar B można przekazać do `gt_hand.hpp` jako wskazówkę struny (rozstrzyga np. E4 na pustej strunie e
od E4 na 5. progu struny B).

---

## 4. Śledzenie nut modelem stanów zamiast reguł progowych

**Problem.** `NoteTracker` (`src/gt_tracker.hpp`) to zbiór reguł: potwierdzenie po 85 ms, zakończenie po 130 ms
niewidoczności, ponowne szarpnięcie po wzroście amplitudy ×1,5. Każda reguła ma próg dobrany na korpusie, a błędy
na granicach nut (pokrycie 74 %) i nieudane dzielenie ponownych szarpnięć wynikają z tych progów.

**Metody.**
* **Ryynänen, Klapuri (WASPAA 2005)**, *Polyphonic Music Transcription Using Note Event Modeling*: każda nuta to
  ukryty model Markowa (stany: atak, trwanie, cisza), cechy ramki są obserwacjami, przebieg wybiera algorytm Viterbiego.
* **Mauch, Dixon (ICASSP 2014), pYIN**: wielu kandydatów na ramkę i dekodowanie Viterbiego po czasie, z jawnym
  stanem dźwięczności. Dla stroika bezpośrednio zastępuje obecne YIN + medianę z 5 ramek.
* **Hawthorne i in. (ISMIR 2018), Onsets and Frames**: nuta może się zacząć **tylko** tam, gdzie detektor
  początków dla tej wysokości to potwierdza. Ta zasada zmniejsza liczbę fałszywych nut niezależnie od tego, czy
  używa się sieci.

**Jak wpiąć.** Dla każdej wysokości MIDI osobny HMM z 3 stanami; obserwacje: znormalizowane `score` z `NoteDet`
i **początek liczony na wysokość**, czyli spectral flux tylko w binach jej *niewspólnych* alikwotów. README podaje,
że dzielenie na ponowne szarpnięcia po skoku energii dawało fałszywe podziały, gdy zaczynała brzmieć inna struna
o wspólnych alikwotach; flux liczony tylko na alikwotach niewspólnych omija dokładnie ten przypadek. W trybie
offline (po zatrzymaniu mikrofonu) Viterbi po całym nagraniu jest tani; na żywo wystarczy okno opóźnienia 0,2–0,3 s.

---

## 5. Rozdzielczość czasowa: okno zależne od wysokości

**Problem.** Okno 4096 próbek przy 11 025 Hz to 372 ms. Wysokie i krótkie nuty (arpeggio, melodie) są rozmyte
w czasie, początek i koniec są przesunięte, a dwie szybkie nuty tej samej struny zlewają się. Docinanie granic
oknem 93 ms (`refineEvents`) działa tylko offline i tylko na znanych już nutach, więc nie odzyskuje nut pominiętych.

**Metody.**
* **Brown (JASA 1991)**, transformacja stałego Q (CQT): okno odwrotnie proporcjonalne do częstotliwości, czyli długie
  dla basu i krótkie dla wysokich dźwięków. **Schörkhuber, Klapuri (SMC 2010)**: wydajna implementacja przez FFT.
* **Bittner i in. (ISMIR 2017)**, harmoniczne CQT (HCQT): kilka CQT przesuniętych o kolejne alikwoty,
  ułożonych tak, że alikwoty jednej nuty leżą w tej samej kolumnie. To daje salience bez jawnego grzebienia.

**Jak wpiąć (bez przepisywania całości).** Dwa widma na ramkę: obecne 4096 dla kandydatów poniżej ~200 Hz
(E2…G3) i 1024 lub 2048 dla wyższych. `detect` wybiera, z której listy pików czytać alikwot, zależnie od jego
częstotliwości (alikwoty niskiej nuty powyżej ~400 Hz też można brać z krótszego okna). Koszt: druga FFT na ramkę,
przy obecnym RTF 0,02 do przyjęcia. Mierzyć: F1 początków (tolerancja 50 ms, patrz pkt 8) i pokrycie czasu nuty.

---

## 6. Detektor uderzeń

Obecny `OnsetDetector` to już w praktyce **SuperFlux** (Böck, Widmer, DAFx 2013): log-widmo, filtr maksimum po
sąsiednich binach, próg z mediany. Możliwe dalsze kroki:
* **ComplexFlux** (Böck, Widmer, ISMIR 2013): dodatkowe ważenie lokalnym opóźnieniem grupowym, jeszcze mniej
  fałszywych uderzeń przy vibrato i tremolo.
* Wybór pików z warunkami „maksimum w oknie przed i po” oraz „średnia w oknie przed” (jak w madmom) zamiast
  porównania trzech sąsiednich wartości.
* Flux liczony w pasmach alikwotów konkretnej wysokości (patrz pkt 4), co pozwala przypisać uderzenie do nuty,
  a nie tylko do chwili.

---

## 7. Sieć neuronowa jako dodatkowy dowód (dłuższa perspektywa)

Najlepsze wyniki na prawdziwych nagraniach gitary mają dziś modele uczone na danych:
* **Basic Pitch** (Bittner i in., ICASSP 2022, Spotify): mały model niezależny od instrumentu, przewiduje naraz
  początki, wysokości wielogłosowe i aktywność nut, działa szybciej niż czas rzeczywisty; jest wersja TypeScript
  i ONNX/TFLite, więc da się go uruchomić w przeglądarce obok silnika WebAssembly (sprawdzić licencję przed użyciem).
* **Riley, Edwards, Dixon (ICASSP 2024)**: model transkrypcji fortepianu wysokiej rozdzielczości dostrojony
  do gitary; najlepszy wynik zero-shot na GuitarSet w chwili publikacji. **GAPS** (Riley i in., ISMIR 2024):
  14 h klasycznej gitary, 300 wykonań, model bazowy.
* Tabulatura wprost z dźwięku: **TabCNN** (Wiggins, Kim, ISMIR 2019), **FretNet** (Cwitkowitz, Hirvonen,
  Klapuri, ICASSP 2023; ciągła wysokość, czyli także podciągnięcia i vibrato), **SynthTab** (Zang i in., ICASSP 2024;
  dane syntetyczne z DadaGP do wstępnego uczenia), separacja strun przed transkrypcją (Bastas i in., IEEE TASLP 2025).
* Wiedza o wykonalności chwytu: Cwitkowitz i in. (arXiv 2204.08094) uczą prawdopodobieństwa par (struna, próg)
  z tabulatur; to uczony odpowiednik waszych reguł z `gt_hand.hpp`.

Praktyczna droga hybrydowa: mapa salience z sieci (lub z HCQT) jako dodatkowy składnik `score` kandydata,
a reszta potoku (ręka, akordy, palcowanie) bez zmian. Wtedy każdy element da się włączyć i zmierzyć osobno.

---

## 8. Pomiar na prawdziwych nagraniach (warunek, żeby ocenić punkty 1–7)

README słusznie zaznacza, że korpus jest syntetyczny i parametry były na nim strojone. Bez prawdziwych nagrań
łatwo „poprawić” silnik pod własny syntezator. Zalecenia:
* **GuitarSet** (Xi i in., ISMIR 2018): 360 fragmentów gitary akustycznej (6 gitarzystów) z adnotacjami nut
  i strun z przetwornika heksafonicznego. Standardowy zbiór testowy w pracach powyżej.
* **GAPS** (klasyczna, nuty z partytur wyrównanych do nagrań) oraz **IDMT-SMT-Guitar** (Fraunhofer IDMT, nagrania
  pojedynczych technik, także elektryk).
* Metryki jak w literaturze: **mir_eval** (Raffel i in., ISMIR 2014), F1 nut z tolerancją początku **50 ms**
  (wasz `score.py` używa 120 ms, więc liczby nie są porównywalne z publikacjami), osobno F1 z kryterium końca nuty.
* Raportować oba zbiory naraz: zmiana, która poprawia syntetyczny korpus, a pogarsza GuitarSet, to dopasowanie
  do syntezatora.

---

## Kolejność prac (propozycja)

| # | zmiana | zysk | koszt | błąd z README |
|---|---|---|---|---|
| 8 | ewaluacja na GuitarSet + mir_eval 50 ms | warunek wiarygodności reszty | mały | korpus syntetyczny |
| 1 | eliminacja wsteczna + kara Duana za puste miejsca | duży (duchy) | mały | poduktawy |
| 2 | model miejsca szarpnięcia w teście oktaw | średni | mały | fałszywa oktawa na melodiach, 15 % pominiętych podwojeń |
| 3 | B i strój na wysokość, węższa tolerancja | średni | mały | duchy, rozpoznanie struny |
| 5 | drugie, krótsze okno dla wysokich nut | średni | średni | granice nut, szybkie arpeggio |
| 4 | HMM nut + początki na wysokość | duży | średni | pokrycie 74 %, ponowne szarpnięcia |
| 6 | ComplexFlux, lepszy wybór pików | mały | mały | fałszywe uderzenia |
| 7 | salience z sieci jako dodatkowy dowód | duży na prawdziwym audio | duży | ogólna dokładność |

---

## Bibliografia

Przeglądy
* E. Benetos, S. Dixon, Z. Duan, S. Ewert, *Automatic Music Transcription: An Overview*, IEEE Signal Processing
  Magazine 36(1), 2019, s. 20–30. [PDF](https://audiolabs-erlangen.de/content/05_fau/professor/00_mueller/02_teaching/2024s_sarntal/03_group_AMT/2019_BenetosDDE_MusicTranscription_SPM.pdf)
* A. Klapuri, M. Davy (red.), *Signal Processing Methods for Music Transcription*, Springer, 2006.

Wielogłosowa estymacja wysokości
* A. Klapuri, *Multiple Fundamental Frequency Estimation by Summing Harmonic Amplitudes*, ISMIR 2006.
  [PDF](https://archives.ismir.net/ismir2006/paper/000125.pdf), implementacja: [Essentia MultiPitchKlapuri](https://essentia.upf.edu/reference/std_MultiPitchKlapuri.html)
* Z. Duan, B. Pardo, C. Zhang, *Multiple Fundamental Frequency Estimation by Modeling Spectral Peaks and Non-peak
  Regions*, IEEE TASLP, 2010. [PDF](https://labsites.rochester.edu/air/publications/DuanPardoZhang_MF0E_TASLP10.pdf)
* C. Yeh, A. Röbel, *A New Score Function for Joint Evaluation of Multiple F0 Hypotheses*, DAFx 2004.
  [PDF](https://dafx.de/paper-archive/2004/P_234.PDF); rozwinięcie: C. Yeh, A. Röbel, X. Rodet, IEEE TASLP 2010
  (ocena łączna i szacowanie liczby głosów).
* V. Emiya, R. Badeau, B. David, *Multipitch Estimation of Quasi-Harmonic Sounds in Colored Noise*, DAFx 2007.
  [link](https://dafx.de/paper-archive/details/fwG1bTohHdW3B3zV01Rxvw)
* R. Bittner, B. McFee, J. Salamon, P. Li, J. P. Bello, *Deep Salience Representations for F0 Estimation in
  Polyphonic Music*, ISMIR 2017. [PDF](https://archives.ismir.net/ismir2017/paper/000085.pdf)

Fizyka struny gitarowej
* C. Traube, J. O. Smith, *Estimating the Plucking Point on a Guitar String*, DAFx 2000.
  [link](https://dafx.de/paper-archive/details/z7bOpgD8bdEUM5ImiJuQqQ), [PDF wersji rozszerzonej](https://www.ee.columbia.edu/~dpwe/papers/TraubS01-guitar.pdf)
* C. Traube, P. Depalle, *Extraction of the Excitation Point Location on a String Using Weighted Least-Square
  Estimation of a Comb Filter Delay*, DAFx 2003. [link](https://dafx.de/paper-archive/details/Kc6vbDzVhVwDgiZSuvm12A)
* Z. Mohamad, S. Dixon, C. Harte, *Estimating Pickup and Plucking Positions of Guitar Tones and Chords with Audio
  Effects*, DAFx 2017. [PDF](https://webspace.eecs.qmul.ac.uk/s.e.dixon/pub/2017/MohamadHarteDixon-DAFx2017.pdf)
* F. Rigaud, B. David, L. Daudet, *Piano Sound Analysis Using NMF with Inharmonicity Constraint*, EUSIPCO 2012
  [PDF](https://new.eurasip.org/Proceedings/Eusipco/Eusipco2012/Conference/papers/1569585169.pdf);
  *A Parametric Model and Estimation Techniques for the Inharmonicity and Tuning of the Piano*, JASA 133(5), 2013.
* I. Barbancho, L. J. Tardón, S. Sammartino, A. M. Barbancho, *Inharmonicity-Based Method for the Automatic
  Generation of Guitar Tablature*, IEEE TASLP 20(6), 2012.
* C. Kehling, J. Abeßer, C. Dittmar, G. Schuller, *Automatic Tablature Transcription of Electric Guitar Recordings
  by Estimation of Score- and Instrument-Related Parameters*, DAFx 2014.
  [PDF](https://www.dafx14.fau.de/papers/dafx14_christian_kehling_automatic_tablature_trans.pdf)

Czas: uderzenia, śledzenie nut, rozdzielczość
* S. Böck, G. Widmer, *Maximum Filter Vibrato Suppression for Onset Detection* (SuperFlux), DAFx 2013.
  [link](https://dafx.de/paper-archive/details/0oee-99Z88WL7pSo749gcA)
* S. Böck, G. Widmer, *Local Group Delay Based Vibrato and Tremolo Suppression for Onset Detection*, ISMIR 2013.
  [PDF](https://archives.ismir.net/ismir2013/paper/000175.pdf)
* M. Ryynänen, A. Klapuri, *Polyphonic Music Transcription Using Note Event Modeling*, WASPAA 2005.
* M. Mauch, S. Dixon, *pYIN: A Fundamental Frequency Estimator Using Probabilistic Threshold Distributions*,
  ICASSP 2014. [projekt](https://code.soundsoftware.ac.uk/projects/pyin)
* C. Hawthorne i in., *Onsets and Frames: Dual-Objective Piano Transcription*, ISMIR 2018.
* J. C. Brown, *Calculation of a Constant Q Spectral Transform*, JASA 89(1), 1991.
* C. Schörkhuber, A. Klapuri, *Constant-Q Transform Toolbox for Music Processing*, SMC 2010.

Modele uczone i dane
* R. Bittner i in., *A Lightweight Instrument-Agnostic Model for Polyphonic Note Transcription and Multipitch
  Estimation* (Basic Pitch), ICASSP 2022. [arXiv 2203.09893](https://arxiv.org/abs/2203.09893), [kod](https://github.com/spotify/basic-pitch), [wersja TS](https://github.com/spotify/basic-pitch-ts)
* X. Riley, D. Edwards, S. Dixon, *High Resolution Guitar Transcription via Domain Adaptation*, ICASSP 2024.
  [arXiv 2402.15258](https://arxiv.org/abs/2402.15258)
* X. Riley, Z. Guo, D. Edwards, S. Dixon, *GAPS: A Large and Diverse Classical Guitar Dataset and Benchmark
  Transcription Model*, ISMIR 2024. [arXiv 2408.08653](https://arxiv.org/abs/2408.08653)
* A. Wiggins, Y. Kim, *Guitar Tablature Estimation with a Convolutional Neural Network* (TabCNN), ISMIR 2019.
* F. Cwitkowitz, T. Hirvonen, A. Klapuri, *FretNet: Continuous-Valued Pitch Contour Streaming for Polyphonic Guitar
  Tablature Transcription*, ICASSP 2023. [arXiv 2212.03023](https://arxiv.org/abs/2212.03023)
* *A Data-Driven Methodology for Considering Feasibility and Pairwise Likelihood in Deep Learning Based Guitar
  Tablature Transcription Systems*. [arXiv 2204.08094](https://arxiv.org/abs/2204.08094)
* Y. Zang, Y. Zhong, F. Cwitkowitz, Z. Duan, *SynthTab: Leveraging Synthesized Data for Guitar Tablature
  Transcription*, ICASSP 2024. [arXiv 2309.09085](https://arxiv.org/abs/2309.09085)
* G. Bastas, V. Katsouros i in., *Separate and Transcribe: Deep Guitar String Separation and its Application for
  Tablature Transcription Enhancement*, IEEE TASLP 33, 2025, s. 4184–4195.
  [PDF](https://robotics.ntua.gr/wp-content/uploads/sites/2/2025_Bastas_Deep-Guitar-StringSeparation-TablatureTranscription_TASLP_final.pdf)
* Q. Xi, R. Bittner, J. Pauwels, X. Ye, J. P. Bello, *GuitarSet: A Dataset for Guitar Transcription*, ISMIR 2018.
* C. Raffel i in., *mir_eval: A Transparent Implementation of Common MIR Metrics*, ISMIR 2014.

Pozycje bez linku są cytowane z pamięci (tytuł, autorzy, miejsce publikacji); przed cytowaniem w pracy warto
sprawdzić dokładne strony w IEEE Xplore lub archiwum ISMIR/DAFx.
