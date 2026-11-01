#!/usr/bin/env bash
# run_bench.sh - porównanie silnika C++ z oryginałem JS na korpusie syntetycznym.
# Użycie: tools/run_bench.sh <katalog_roboczy> [dev|holdout] [flagi gt_cli...]
#   dev     - zbiór roboczy (do strojenia parametrów)
#   holdout - zbiór kontrolny (inne ziarna; raportujemy tylko jego wyniki końcowe)
set -euo pipefail
cd "$(dirname "$0")/.."
W=${1:?podaj katalog roboczy}; SET=${2:-dev}; shift 2 || shift $# || true
case "$SET" in dev) OFF=0;; holdout) OFF=5000;; *) echo "zbiór: dev|holdout"; exit 2;; esac
C="$W/corpus_$SET"; mkdir -p "$W/bin" "$C" "$W/res_cpp_$SET" "$W/res_old_$SET"
g++ -std=c++17 -O2 -o "$W/bin/gen_corpus" tools/gen_corpus.cpp
g++ -std=c++17 -O2 -o "$W/bin/gt_cli" src/cli.cpp
[ -f "$C/strum_clean_00.wav" ] || "$W/bin/gen_corpus" "$C" $OFF
rm -f "$W/res_cpp_$SET"/*.json
ls "$C"/*.wav | xargs -P 4 -I{} sh -c 'b=$(basename {} .wav); '"$W"'/bin/gt_cli analyze {} '"$W"'/res_cpp_'"$SET"'/$b.json '"$*"
if [ ! -f "$W/res_old_$SET/strum_clean_00.json" ]; then
  ls "$C"/*.wav | xargs -P 4 -I{} sh -c 'b=$(basename {} .wav); node tools/baseline/run_old.js {} '"$W"'/res_old_'"$SET"'/$b.json'
fi
echo "=== ORYGINAŁ (JS), zbiór $SET ==="; python3 tools/score.py "$C" "$W/res_old_$SET"
echo "=== NOWY SILNIK (C++), zbiór $SET ==="; python3 tools/score.py "$C" "$W/res_cpp_$SET"
