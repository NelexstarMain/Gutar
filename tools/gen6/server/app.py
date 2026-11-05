"""app.py - serwer transkrypcji gen 6 (FastAPI). ESP32 -> telefon -> serwer: telefon wysyła WAV, serwer zwraca nuty.

  GUTAR_TOKEN=tajny GUTAR_CKPT=model/best.pt uvicorn tools.gen6.server.app:app --host 0.0.0.0 --port 8080

  GET  /health                       -> {"ok": true, "model": {...}}
  POST /transcribe[?format=json|midi] ciało = surowy plik WAV (PCM 8/16/24/32 bit albo float, dowolna częstotliwość próbkowania),
                                      nagłówek X-Token: <GUTAR_TOKEN>.  json: nuty (wysokość MIDI, początek, koniec, głośność, struna, próg),
                                      midi: plik .mid.
Zmienne: GUTAR_TOKEN (wymagane; GUTAR_ALLOW_OPEN=1 pozwala uruchomić bez, tylko do prób lokalnych), GUTAR_CKPT (domyślnie
model/best.pt), GUTAR_MAX_MB (domyślnie 30; Cloud Run odrzuca zapytania powyżej 32 MB), GUTAR_THREADS.
"""
from __future__ import annotations
import hmac
import os
import tempfile
import threading
import time

import numpy as np
import torch
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response

from ..config import Config
from ..decode import decode_notes
from ..features import hcqt
from ..audio import load_audio
from ..model import Gen6
from .midi_out import notes_to_midi

app = FastAPI(title='Gitara Słuchacz gen 6')
_state = {}
_lock = threading.Lock()  # jedno nagranie naraz: model i pamięć są na jedną instancję


def _load():
    if 'net' in _state:
        return _state
    ck = os.environ.get('GUTAR_CKPT', os.path.join(os.path.dirname(__file__), 'model', 'best.pt'))
    st = torch.load(ck, weights_only=False, map_location='cpu')
    cfg = Config.from_dict(st['config'])
    net = Gen6(cfg)
    net.load_state_dict(st['net'])
    net.eval()
    torch.set_num_threads(int(os.environ.get('GUTAR_THREADS', os.cpu_count() or 1)))
    _state.update(net=net, cfg=cfg, info={'epoch': st.get('epoch'), 'score': st.get('score'), 'params': net.n_params()})
    return _state


def _check_token(req: Request):
    want = os.environ.get('GUTAR_TOKEN')
    if not want:
        if os.environ.get('GUTAR_ALLOW_OPEN') == '1':
            return
        raise HTTPException(503, 'serwer bez GUTAR_TOKEN')
    got = req.headers.get('x-token', '')
    if not hmac.compare_digest(got.encode(), want.encode()):
        raise HTTPException(401, 'zły token')


@app.on_event('startup')
def _startup():
    if os.environ.get('GUTAR_PRELOAD', '1') == '1':
        _load()


@app.get('/', response_class=HTMLResponse)
def index():
    """Strona do wypróbowania modelu: wczytaj nagranie (WAV, MP3, M4A…), zobacz nuty, pobierz MIDI / CSV."""
    return HTMLResponse(open(os.path.join(os.path.dirname(__file__), 'ui.html'), encoding='utf-8').read())


@app.get('/health')
def health():
    return {'ok': True, 'model': _load()['info']}


def transcribe_wav(data: bytes):
    s = _load()
    cfg, net = s['cfg'], s['net']
    with tempfile.NamedTemporaryFile(suffix='.wav') as f:
        f.write(data)
        f.flush()
        try:
            x = load_audio(f.name, cfg.features.sr, cfg.features.frontend)
        except Exception as e:
            raise HTTPException(400, 'nie można wczytać WAV: %s' % e)
    if len(x) < cfg.features.sr * 0.5:
        raise HTTPException(400, 'nagranie krótsze niż 0,5 s')
    t0 = time.time()
    X = hcqt(x, cfg.features)
    t1 = time.time()
    with torch.no_grad():
        p = net.predict(X)
    t2 = time.time()
    notes = decode_notes(p, cfg.features, cfg.decode, cfg.labels)
    return notes, {'duration_s': round(len(x) / cfg.features.sr, 2), 'features_s': round(t1 - t0, 2),
                   'model_s': round(t2 - t1, 2), 'total_s': round(time.time() - t0, 2)}


@app.post('/transcribe')
async def transcribe(req: Request, format: str = 'json'):
    _check_token(req)
    limit = int(float(os.environ.get('GUTAR_MAX_MB', '30')) * 1e6)
    if int(req.headers.get('content-length', 0)) > limit:
        raise HTTPException(413, 'plik za duży (limit %d MB)' % (limit // 1000000))
    data = await req.body()
    if len(data) > limit:
        raise HTTPException(413, 'plik za duży')
    if data[:4] != b'RIFF':
        raise HTTPException(400, 'to nie jest plik WAV')
    with _lock:
        notes, timing = await _run(data)
    # głowica głośności nie była uczona (żadne źródło danych nie ma etykiet głośności), więc jej wartości są przypadkowe:
    # nie zwracamy ich, a w MIDI wszystkie nuty mają tę samą głośność
    for n in notes:
        n.velocity = None
    if format == 'midi':
        return Response(notes_to_midi(notes), media_type='audio/midi',
                        headers={'Content-Disposition': 'attachment; filename="nagranie.mid"'})
    lc = _load()['cfg'].labels
    out = []
    for n in notes:
        o = {'pitch': int(round(n.pitch)), 'onset': round(n.onset, 3), 'offset': round(n.offset, 3),
             'confidence': round(float(getattr(n, 'conf', 0.0)), 3)}
        if n.string is not None:
            o['string'] = int(n.string)  # 0 = najniższa struna
            o['fret'] = int(round(n.pitch)) - lc.tuning[n.string]
        out.append(o)
    return JSONResponse({'n_notes': len(out), 'timing': timing, 'model': _load()['info'], 'notes': out})


async def _run(data):
    import asyncio
    return await asyncio.get_running_loop().run_in_executor(None, transcribe_wav, data)
