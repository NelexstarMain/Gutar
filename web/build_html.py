#!/usr/bin/env python3
"""build_html.py - składa aplikację w jeden plik HTML (silnik C++ jako WebAssembly + rezerwa asm.js wewnątrz).

Wejście:  dist/gt_engine.wasm, build/gt_engine.asm.js (opcjonalnie), web/{style.css,body.html,app.js}, src/*
Wyjście:  dist/gitara-sluchacz.html   samodzielny dokument (do pobrania, działa offline, z mikrofonem)
          dist/artifact-page.html     ten sam kod jako fragment strony artefaktu (bez <html>/<head>/<body>)
"""
import base64, json, os, re, sys

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
rd = lambda *p: open(os.path.join(root, *p), encoding='utf-8').read()

wasm = open(os.path.join(root, 'dist', 'gt_engine.wasm'), 'rb').read()
b64 = base64.b64encode(wasm).decode()
asm_path = os.path.join(root, 'build', 'gt_engine.asm.js')
asm = open(asm_path, encoding='utf-8').read() if os.path.exists(asm_path) else None

order = ['gt_dsp.hpp', 'gt_spectrum.hpp', 'gt_model.hpp', 'gt_maskmodel.hpp', 'gt_mask.hpp', 'gt_hcqt.hpp', 'gt_gen5model.hpp', 'gt_gen5.hpp', 'gt_pitch.hpp', 'gt_chords.hpp', 'gt_tracker.hpp', 'gt_engine.hpp',
         'gt_fingering.hpp', 'gt_hand.hpp', 'gt_export.hpp', 'gt_synth.hpp', 'wasm_api.cpp']
sources = {'files': [{'name': n, 'code': rd('src', n)} for n in order]}
src_json = json.dumps(sources, ensure_ascii=False).replace('</', '<\\/')

css, body, app = rd('web', 'style.css'), rd('web', 'body.html'), rd('web', 'app.js')
fonts = ('<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
         '<link href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,500..800&family=Hanken+Grotesk:wght@400;500;600'
         '&display=swap" rel="stylesheet">')
scripts = ['<script type="text/plain" id="wasmB64">' + b64 + '</script>',
           '<script type="application/json" id="srcData">' + src_json + '</script>']
if asm:
    assert '</script' not in asm.lower()
    scripts.append('<script>/* rezerwa: ten sam silnik C++ przetłumaczony na JavaScript (wasm2js), gdy platforma blokuje WebAssembly */\n'
                   'window.__gtAsmEngine = ' + asm + ';</script>')
else:
    print('UWAGA: brak build/gt_engine.asm.js, aplikacja bez rezerwy asm.js', file=sys.stderr)
scripts.append('<script>\n' + app + '\n</script>')
title = '<title>Gitara Słuchacz</title>'
tail = '\n'.join(scripts)

standalone = ('<!doctype html>\n<html lang="pl">\n<head>\n<meta charset="utf-8">\n'
              '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">\n' + title + '\n' + fonts +
              '\n<style>\n' + css + '\n</style>\n</head>\n<body>\n' + body + '\n' + tail + '\n</body>\n</html>\n')
fragment = (title + '\n<meta name="claude:viewport-fit-sides" content="cover">\n' + fonts + '\n<style>\n' + css + '\n</style>\n' + body + '\n' + tail + '\n')

os.makedirs(os.path.join(root, 'dist'), exist_ok=True)
for name, text in (('gitara-sluchacz.html', standalone), ('artifact-page.html', fragment)):
    with open(os.path.join(root, 'dist', name), 'w', encoding='utf-8') as f:
        f.write(text)
    print('%-24s %7.1f KB' % (name, len(text.encode('utf-8')) / 1024))
