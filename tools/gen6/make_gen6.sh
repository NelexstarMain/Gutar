#!/usr/bin/env bash
# make_gen6.sh - pełne przygotowanie danych generacji 6 (muzyka klasyczna na wielu instrumentach w wielu miejscach).
#
#   tools/gen6/make_gen6.sh [katalog]          (domyślnie ./gen6)
#
# Kroki:
#   1. korpus MIDI: MAESTRO + korpus music21 -> <katalog>/korpus/midi, manifest.csv (ok. 3200 utworów, 280 h muzyki)
#   2. generatory C++ (gen_classical, gt_cli)
#   3. nagrania: train / validation / test z podziału manifestu (utwór zawsze w jednym zbiorze), osobne ziarna
#   4. zrzuty HCQT (wejście sieci gen 5/6) dla każdego nagrania
# Zmienne (domyślne w nawiasach):
#   VERSIONS (4)  wersje każdego utworu: oryginał, odwrócenie, rak, rak odwrócenia; 8 = każda forma dwa razy (inne transpozycje i tempo)
#   CLIPS (2)     fragmenty na wersję;  LEN ("10 20") długość fragmentu [s];  JOBS (liczba rdzeni)
#   GUITAR (0.35) udział rodziny gitar w obsadzie;  LIMIT (0 = wszystko) najwyżej tyle utworów na zbiór (do prób)
#   CLEAN (0)     1 = zapisz też same instrumenty bez otoczenia (.clean.wav, do uczenia maski)
#   MIDI (1)      1 = zapisz każdą wersję utworu jako MIDI (<katalog>/<zbiór>/midi)
#   DUMP (1)      1 = zrzuty HCQT;  KEEP_WAV (1) 0 = usuń .wav po zrzucie (oszczędza ok. 25 % miejsca)
# Rozmiar (VERSIONS=4, CLIPS=2): ok. 26 tys. nagrań, ok. 115 h dźwięku; .wav ok. 0,7 MB i zrzut ok. 2 MB na nagranie (razem ok. 70 GB).
# Czas: ok. 2 s procesora na nagranie (generowanie) + ok. 2,5 s (zrzut) -> ok. 8 h na 4 rdzeniach.
set -euo pipefail
cd "$(dirname "$0")/../.."
OUT="${1:-gen6}"
VERSIONS="${VERSIONS:-4}"; CLIPS="${CLIPS:-2}"; LEN="${LEN:-10 20}"; JOBS="${JOBS:-$(nproc)}"; GUITAR="${GUITAR:-0.35}"
LIMIT="${LIMIT:-0}"; CLEAN="${CLEAN:-0}"; MIDI="${MIDI:-1}"; DUMP="${DUMP:-1}"; KEEP_WAV="${KEEP_WAV:-1}"

mkdir -p "$OUT" build
if [ ! -f "$OUT/korpus/manifest.csv" ]; then
  python3 -c "import music21" 2>/dev/null || pip install music21
  python3 tools/gen6/fetch_classical.py "$OUT/korpus" --jobs "$JOBS"
fi
g++ -std=c++17 -O2 -pthread tools/gen_classical.cpp -o build/gen_classical
g++ -std=c++17 -O2 src/cli.cpp -o build/gt_cli

opts=(--versions "$VERSIONS" --clips "$CLIPS" --len $LEN --jobs "$JOBS" --guitar "$GUITAR")
[ "$LIMIT" != 0 ] && opts+=(--limit "$LIMIT")
[ "$CLEAN" = 1 ] && opts+=(--clean)
[ "$MIDI" = 1 ] && opts+=(--midi)
seed=1
for split in train validation test; do
  if [ ! -f "$OUT/$split/index.csv" ]; then
    ./build/gen_classical "$OUT/korpus/manifest.csv" "$OUT/korpus" "$OUT/$split" --split "$split" --seed $seed "${opts[@]}"
  fi
  seed=$((seed + 1000))
  if [ "$DUMP" = 1 ]; then
    mkdir -p "$OUT/hcqt/$split"
    find "$OUT/$split" -maxdepth 1 -name 'cls_*.wav' ! -name '*.clean.wav' -print0 |
      xargs -0 -P "$JOBS" -n 1 sh -c 'f="$3"; d="$1/$(basename "$f" .wav).bin"; [ -f "$d" ] || GT_DUMPH="$d" ./build/gt_cli analyze "$f" /dev/null >/dev/null 2>&1; [ "$2" = 1 ] || rm -f "$f"' _ \
        "$OUT/hcqt/$split" "$KEEP_WAV"
  fi
  echo "$split: $(($(wc -l < "$OUT/$split/index.csv") - 1)) nagrań"
done
cat <<EOF

Gotowe. Uczenie (PyTorch), np. razem z danymi gen 5:
  python3 tools/train_gen5.py --lazy --attn --hidden 32 \\
    --src klasyka $OUT/hcqt/train $OUT/train 0.3 \\
    --src środowiska hcqt/env env_train 0.2 --src korpus hcqt/syn prawda 0.15 --src GuitarSet hcqt/gs annotation 0.35
Zbiór kontrolny (utwory, których model nie widział):  $OUT/test (nagrania i prawda), $OUT/hcqt/test (zrzuty)
EOF
