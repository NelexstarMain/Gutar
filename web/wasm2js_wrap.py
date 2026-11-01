#!/usr/bin/env python3
"""wasm2js_wrap.py - zamienia moduł ES z wasm2js (Binaryen) na funkcję makeEngine(wasi) bez importów/eksportów.

Użycie: wasm2js_wrap.py engine.js out.js
Wynik: kod JS definiujący `function (wasi_snapshot_preview1) { ...; return exports; }` (wyrażenie funkcyjne).
"""
import re, sys
src = open(sys.argv[1], encoding='utf-8').read()
src = re.sub(r"^import \* as wasi_snapshot_preview1 from 'wasi_snapshot_preview1';\n", "", src, count=1)
src = re.sub(r"^export var [A-Za-z0-9_$]+ = retasmFunc\.[A-Za-z0-9_$]+;\n?", "", src, flags=re.M)
out = "(function (wasi_snapshot_preview1) {\n" + src + "\nreturn retasmFunc;\n})"
open(sys.argv[2], 'w', encoding='utf-8').write(out)
print("zapisano", sys.argv[2], len(out), "B")
