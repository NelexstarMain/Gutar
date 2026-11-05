"""gen6 - architektura generacji 6 Gitary Słuchacza (Python / PyTorch).

Pakiet jest niezależny od formatu danych: każde źródło (GuitarSet, korpusy syntetyczne, środowiska, CSV, MIDI, zrzuty silnika
C++ albo dowolny nowy format) jest sprowadzane do jednego, wspólnego zapisu `Example` (dźwięk albo gotowe cechy + lista nut).
Od tego miejsca cała reszta (cechy, etykiety, sieć, dekoder, ewaluacja) jest wspólna.

Moduły:
  config    - konfiguracja (dataclasses, zapis/odczyt JSON)
  audio     - wczytywanie WAV i zmiana częstotliwości próbkowania (sam numpy)
  features  - HCQT w numpy (zgodne z src/gt_hcqt.hpp, ale z konfigurowalnym krokiem)
  data      - wspólny zapis danych, adaptery formatów (rejestr), manifest JSONL, zbiór do uczenia
  labels    - mapy celów: brzmi / początek / koniec / głośność / struna-próg (z maskami dostępności)
  model     - sieć gen 6 (harmoniczne konwolucje + uwaga w czasie i między wysokościami + 5 głowic)
  losses    - funkcje straty z maskami (źródła bez części etykiet)
  decode    - dekoder nut z map sieci
  metrics   - WSZYSTKIE funkcje ewaluacyjne (nuty, klatki, mapy, podtrzymanie, akordy, tabulatura, przedziały ufności)
  evaluate  - ewaluacja modelu albo plików JSON silnika C++ (te same funkcje dla wszystkich generacji)
  train     - pętla uczenia (szkielet, wznawianie, wybór najlepszej epoki)
  synth     - małe syntetyczne przykłady do testów
"""
__version__ = '6.0.0'
