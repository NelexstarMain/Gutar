# Serwer transkrypcji gen 6 (ESP32 → telefon → serwer)

Telefon wysyła nagranie WAV (odebrane z ESP32 przez Bluetooth) na serwer, serwer zwraca nuty. Kod: `tools/gen6/server/`
(FastAPI), model: `tools/gen6/server/model/best.pt` (1 MB; po kolejnych sesjach treningu podmień plik i wdróż ponownie).

## Interfejs

| zapytanie | wynik |
|---|---|
| `GET /health` | `{"ok": true, "model": {"epoch", "score", "params"}}` |
| `POST /transcribe` (ciało = plik WAV, nagłówek `X-Token`) | JSON: `notes[]` z polami `pitch` (MIDI), `onset`, `offset` [s], `confidence`, `string` (0 = najniższa), `fret`; `timing` (czasy etapów) |
| `POST /transcribe?format=midi` | plik `.mid` |

Brak `X-Token` albo zły: 401; plik powyżej 30 MB: 413; nie WAV: 400. Serwer bez ustawionego `GUTAR_TOKEN` nie przyjmuje zapytań
(do prób lokalnych: `GUTAR_ALLOW_OPEN=1`). Głośność nut nie jest zwracana: głowica głośności nie była uczona (żadne źródło danych
nie ma etykiet głośności), w MIDI wszystkie nuty mają tę samą.

```bash
curl -s -H "X-Token: $TOKEN" --data-binary @nagranie.wav "$URL/transcribe" | jq '.n_notes, .timing'
curl -s -H "X-Token: $TOKEN" --data-binary @nagranie.wav "$URL/transcribe?format=midi" -o nagranie.mid
```

## Lokalnie

```bash
pip install torch numpy fastapi uvicorn
GUTAR_TOKEN=tajny uvicorn tools.gen6.server.app:app --port 8080
```

Test na GuitarSet (04_SS1-100-C#_solo, 29 s, mikrofon): 72 nuty (prawda 71), F1 nut 0,84, 5 s na 4 rdzeniach
(3 s model, 2 s cechy), czyli ok. 0,17 czasu nagrania; 3 minuty gry to ok. 30 s na 4 rdzeniach, na Cloud Run z 2 vCPU pewnie
ok. 1 min (szacunek, nie pomiar).

## Wdrożenie na Google Cloud Run (darmowy limit: 2 mln zapytań, 180 tys. vCPU-s i 360 tys. GB-s miesięcznie)

Wymaga konta Google Cloud z kartą płatniczą i zainstalowanego `gcloud`. Kolejność:

1. **Najpierw zabezpiecz koszty:** w konsoli Billing → Budgets & alerts utwórz budżet np. 5 zł z alertami e-mail.
2. Projekt i usługi:
   ```bash
   gcloud projects create gutar-NNNN && gcloud config set project gutar-NNNN   # albo istniejący projekt; podłącz billing w konsoli
   gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com
   ```
3. Wdrożenie z katalogu głównego repozytorium (obraz buduje się w chmurze według `Dockerfile`):
   ```bash
   TOKEN=$(openssl rand -hex 16); echo "$TOKEN"      # zapisz w menedżerze haseł, to hasło do serwera
   gcloud run deploy gutar --source . --region europe-central2 --allow-unauthenticated \
     --memory 2Gi --cpu 2 --max-instances 1 --timeout 300 --concurrency 1 \
     --set-env-vars GUTAR_TOKEN=$TOKEN
   ```
   `--max-instances 1` nie pozwala wyjść poza darmowy limit przy lawinie zapytań; `--allow-unauthenticated` jest potrzebne, bo
   ESP32/telefon nie loguje się kontem Google, a dostęp chroni `X-Token`.
4. Adres usługi (`https://gutar-….run.app`) wpisz w telefonie jako `$URL`.

Pierwsze zapytanie po przerwie czeka kilka do kilkunastu sekund na start kontenera (PyTorch). Obrazu nie budowałem lokalnie
(brak działającego daemona Dockera w środowisku pracy), więc pierwsze wdrożenie może wymagać poprawek.
