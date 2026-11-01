#!/usr/bin/env bash
# build.sh - kompiluje silnik C++ do WebAssembly i składa jednoplikową aplikację HTML.
#   ./build.sh   ->  dist/gt_engine.wasm, dist/gitara-sluchacz.html, dist/artifact-page.html
# Wymaga: Zig (pip install ziglang), python3, node. Opcjonalnie Binaryen (npm i binaryen) dla rezerwy asm.js.
set -euo pipefail
cd "$(dirname "$0")"
ZIG="${ZIG:-python3 -m ziglang}"
mkdir -p dist build
# -mcpu=mvp: bez rozszerzeń WebAssembly, dzięki temu moduł da się też przetłumaczyć na JS (wasm2js)
$ZIG c++ -target wasm32-wasi -mcpu=mvp -mexec-model=reactor -std=c++17 -O2 -fno-exceptions -fno-rtti \
  -Wall -Wextra -Wno-unused-parameter -Wl,--strip-all -Wl,--gc-sections -o dist/gt_engine.wasm src/wasm_api.cpp
ls -l dist/gt_engine.wasm
W2J="${WASM2JS:-$(command -v wasm2js || true)}"
if [ -z "$W2J" ] && [ -x node_modules/binaryen/bin/wasm2js ]; then W2J=node_modules/binaryen/bin/wasm2js; fi
if [ -n "$W2J" ]; then
  "$W2J" dist/gt_engine.wasm -O2 -o build/gt_engine.es.js
  python3 web/wasm2js_wrap.py build/gt_engine.es.js build/gt_engine.asm.js
else
  echo "brak wasm2js: pomijam rezerwę asm.js (ustaw WASM2JS=/ścieżka/do/wasm2js)" >&2
fi
python3 web/build_html.py
